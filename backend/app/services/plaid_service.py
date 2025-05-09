import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from fastapi import HTTPException
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from backend.app.models.models import User, BankAccount, PlaidItem, Transaction, Category
from backend.app.schemas.transactions import TransactionCreate
from backend.app.config import get_settings
from backend.app.services.transaction_service import create_transaction
from backend.app.services.ledger_service import create_ledger_event
from backend.app.models.models import LedgerEventType
from backend.app.schemas.ledger import LedgerEventCreate

# Initialize Plaid client
settings = get_settings()
configuration = plaid.Configuration(
    host=settings.plaid_environment,
    api_key={
        'clientId': settings.plaid_client_id,
        'secret': settings.plaid_secret,
    }
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

def create_link_token(user_id: str, db: Session) -> Dict[str, Any]:
    """Create a Plaid Link token for account linking"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    # Create a Link token
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="CFO Command Center",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en"
    )
    
    try:
        response = client.link_token_create(request)
        return {"link_token": response['link_token']}
    except plaid.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Plaid Link token: {str(e)}")

def exchange_public_token(public_token: str, metadata: Dict[str, Any], user_id: str, db: Session) -> Dict[str, Any]:
    """Exchange public token for access token and initialize account sync"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    # Exchange public token for access token
    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']
        
        # Store the access token in the database
        plaid_item = PlaidItem(
            user_id=user_id,
            access_token=access_token,
            item_id=item_id,
            institution_id=metadata.get('institution', {}).get('institution_id'),
            institution_name=metadata.get('institution', {}).get('name', 'Unknown Institution')
        )
        db.add(plaid_item)
        db.commit()
        db.refresh(plaid_item)
        
        try:
            # Get account info from Plaid
            accounts_response = client.accounts_get({"access_token": access_token})
            
            # Create bank accounts in our system
            created_accounts = []
            for account in accounts_response['accounts']:
                # Create account in our database
                new_account = BankAccount(
                    user_id=user_id,
                    name=account['name'],
                    plaid_account_id=account['account_id'],
                    balance=account['balances']['current'] or 0.0,
                    institution_name=metadata.get('institution', {}).get('name', 'Unknown Institution'),
                    is_manual=False,
                )
                db.add(new_account)
                db.commit()
                db.refresh(new_account)
                created_accounts.append(new_account)
            
            # Initialize transaction sync
            try:
                sync_result = sync_transactions(access_token, db, created_accounts, plaid_item.id)
                
                return {
                    "item_id": item_id,
                    "accounts": [
                        {"id": acc.id, "name": acc.name, "balance": acc.balance}
                        for acc in created_accounts
                    ],
                    "sync_status": sync_result
                }
            except Exception as sync_error:
                # If transactions sync fails, we still want to return the accounts
                # Just log the error and return what we have
                print(f"Transaction sync failed: {str(sync_error)}")
                return {
                    "item_id": item_id,
                    "accounts": [
                        {"id": acc.id, "name": acc.name, "balance": acc.balance}
                        for acc in created_accounts
                    ],
                    "sync_status": {"error": str(sync_error)}
                }
                
        except Exception as accounts_error:
            # If accounts_get fails, provide detailed error
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to get accounts info: {str(accounts_error)}"
            )
            
    except plaid.ApiException as e:
        # Detailed error for token exchange failure
        error_response = e.body
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to exchange Plaid token: {str(e)}, Response: {error_response}"
        )
    except Exception as e:
        # Catch any other exceptions
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error in token exchange: {str(e)}"
        )

def sync_transactions(access_token: str, db: Session, accounts: List[BankAccount], plaid_item_id: str = None) -> Dict[str, Any]:
    """Sync transactions for the given access token and accounts"""
    try:
        # Get the PlaidItem to retrieve the cursor
        cursor = None
        plaid_item = None
        
        if plaid_item_id:
            plaid_item = db.query(PlaidItem).filter(PlaidItem.id == plaid_item_id).first()
            if plaid_item:
                cursor = plaid_item.cursor  # Use saved cursor if available
        
        added = []
        modified = []
        removed = []
        has_more = True
        
        # Keep syncing until we have all available transactions
        while has_more:
            # Create request based on whether we have a cursor
            if cursor:
                # Continue an existing sync with cursor
                sync_request = TransactionsSyncRequest(
                    access_token=access_token,
                    cursor=cursor
                )
            else:
                # Initial sync - don't include cursor parameter at all
                sync_request = TransactionsSyncRequest(
                    access_token=access_token
                )
            
            sync_response = client.transactions_sync(sync_request)
            
            # Debug output for transaction data
            if sync_response['added']:
                first_trans = sync_response['added'][0]
                print(f"Sample transaction data: {first_trans}")
                print(f"Categories available: {first_trans.get('category', 'None')}")
            
            # Process the newly synced transactions
            if sync_response['added']:
                added.extend(sync_response['added'])
                process_added_transactions(sync_response['added'], db, accounts)
            
            if sync_response['modified']:
                modified.extend(sync_response['modified'])
                process_modified_transactions(sync_response['modified'], db, accounts)
            
            if sync_response['removed']:
                removed.extend(sync_response['removed'])
                process_removed_transactions(sync_response['removed'], db)
            
            cursor = sync_response['next_cursor']
            has_more = sync_response['has_more']
        
        # Save the cursor for the next sync
        if plaid_item and cursor:
            plaid_item.cursor = cursor
            plaid_item.last_sync_at = datetime.utcnow()
            db.commit()
        
        # For each transaction, create a ledger event
        for transaction in added:
            event_type = LedgerEventType.DEPOSIT if transaction['amount'] > 0 else LedgerEventType.WITHDRAWAL
            create_ledger_event(db, LedgerEventCreate(
                event_type=event_type,
                amount=abs(transaction['amount']),
                source_account_id=transaction['account_id'],
                user_id=transaction['user_id'],
                event_metadata={"transaction_id": transaction['transaction_id']}
            ))
        
        return {
            "status": "success", 
            "added": len(added),
            "modified": len(modified),
            "removed": len(removed)
        }
        
    except plaid.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync transactions: {str(e)}")
    except Exception as e:
        return {"status": "error", "message": str(e)}

def process_added_transactions(transactions: List[Dict[str, Any]], db: Session, accounts: List[BankAccount]) -> None:
    """Process new transactions from Plaid and create them in our database"""
    
    # Create a mapping of Plaid account IDs to our account IDs
    account_map = {account.plaid_account_id: account.id for account in accounts}
    
    # Track created categories for debugging
    created_categories = []
    
    for transaction in transactions:
        # Skip if we don't have this account
        if transaction['account_id'] not in account_map:
            continue
        
        # Check if transaction already exists (avoid duplicates)
        existing = db.query(Transaction).filter_by(
            plaid_transaction_id=transaction['transaction_id']
        ).first()
        
        if existing:
            continue  # Skip if we already have this transaction
        
        # Get the transaction date field
        transaction_date = transaction['date']
        
        # Process category information - now using personal_finance_category
        category_id = None
        if transaction.get('personal_finance_category'):
            # Use the detailed category if available, otherwise use primary
            pfc = transaction['personal_finance_category']
            category_name = pfc.get('detailed') or pfc.get('primary')
            
            if category_name:
                # Format the category name to be more readable
                # Convert TRANSPORTATION_TAXIS_AND_RIDE_SHARES to Transportation: Taxis and Ride Shares
                readable_name = category_name.replace('_', ' ').title()
                
                # Check if we already have this category in our database
                category = db.query(Category).filter_by(name=readable_name).first()
                
                if not category:
                    # Create a new category
                    category = Category(
                        name=readable_name,
                        plaid_category_id=category_name  # Store the original ID
                    )
                    db.add(category)
                    db.commit()
                    db.refresh(category)
                    created_categories.append(readable_name)
                
                category_id = category.id
                print(f"Assigned category: {readable_name} to transaction: {transaction['name']}")
        
        # Create transaction in our database
        trans_data = TransactionCreate(
            account_id=account_map[transaction['account_id']],
            amount=transaction['amount'],
            description=transaction['name'],
            merchant_name=transaction.get('merchant_name'),
            date=transaction_date,
            is_pending=transaction['pending'],
            plaid_transaction_id=transaction['transaction_id'],
            category_id=category_id
        )
        
        create_transaction(db, trans_data)
    
    # Print debug info about created categories
    if created_categories:
        print(f"Created {len(created_categories)} new categories: {', '.join(created_categories)}")

def process_modified_transactions(transactions: List[Dict[str, Any]], db: Session, accounts: List[BankAccount]) -> None:
    """Update existing transactions based on Plaid modifications"""
    
    account_map = {account.plaid_account_id: account.id for account in accounts}
    
    for transaction in transactions:
        # Find the existing transaction
        existing = db.query(Transaction).filter_by(
            plaid_transaction_id=transaction['transaction_id']
        ).first()
        
        if not existing:
            # If it doesn't exist, treat it as a new transaction
            if transaction['account_id'] in account_map:
                process_added_transactions([transaction], db, accounts)
            continue
        
        # Process category information - now using personal_finance_category
        category_id = None
        if transaction.get('personal_finance_category'):
            # Use the detailed category if available, otherwise use primary
            pfc = transaction['personal_finance_category']
            category_name = pfc.get('detailed') or pfc.get('primary')
            
            if category_name:
                # Format the category name to be more readable
                readable_name = category_name.replace('_', ' ').title()
                
                # Check if we already have this category in our database
                category = db.query(Category).filter_by(name=readable_name).first()
                
                if not category:
                    # Create a new category
                    category = Category(
                        name=readable_name,
                        plaid_category_id=category_name  # Store the original ID
                    )
                    db.add(category)
                    db.commit()
                    db.refresh(category)
                
                category_id = category.id
        
        # Update the transaction fields
        existing.amount = transaction['amount']
        existing.description = transaction['name']
        existing.merchant_name = transaction.get('merchant_name')
        existing.is_pending = transaction['pending']
        existing.date = transaction['date']
        existing.category_id = category_id
        
        db.commit()

def process_removed_transactions(transactions: List[Dict[str, Any]], db: Session) -> None:
    """Handle transactions that have been removed in Plaid"""
    
    for transaction in transactions:
        # Find the transaction to remove
        existing = db.query(Transaction).filter_by(
            plaid_transaction_id=transaction['transaction_id']
        ).first()
        
        if existing:
            # Option 1: Delete the transaction
            db.delete(existing)
            
            # Option 2: Mark as removed but keep the record
            # existing.is_removed = True  # Would need to add this field to model
            
            db.commit()

def create_sandbox_token(institution_id: str, initial_products: List[str]) -> Dict[str, Any]:
    """Create a sandbox public token for testing"""
    try:
        # Convert string product names to Plaid Products enum
        products = [Products(product) for product in initial_products]
        
        # Create sandbox public token
        request = SandboxPublicTokenCreateRequest(
            institution_id=institution_id,
            initial_products=products
        )
        
        response = client.sandbox_public_token_create(request)
        return {
            "public_token": response['public_token'],
            "request_id": response['request_id']
        }
    except plaid.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Failed to create sandbox token: {str(e)}") 