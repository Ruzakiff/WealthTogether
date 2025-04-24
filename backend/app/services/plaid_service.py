import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from fastapi import HTTPException
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from backend.app.models.models import User, BankAccount
from backend.app.schemas.transactions import TransactionCreate
from backend.app.config import get_settings
from backend.app.services.transaction_service import create_transaction

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
        
        # Store these securely (you may want to encrypt)
        # This is simplified - in production use encryption for sensitive tokens
        
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
        sync_transactions(access_token, db, created_accounts)
        
        return {
            "item_id": item_id,
            "accounts": [
                {"id": acc.id, "name": acc.name, "balance": acc.balance}
                for acc in created_accounts
            ]
        }
        
    except plaid.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange Plaid token: {str(e)}")

def sync_transactions(access_token: str, db: Session, accounts: List[BankAccount]) -> Dict[str, Any]:
    """Sync transactions from Plaid for the given accounts"""
    
    try:
        # Initial sync with empty cursor
        sync_request = TransactionsSyncRequest(
            access_token=access_token,
            cursor=""  # Start with empty cursor for initial sync
        )
        
        sync_response = client.transactions_sync(sync_request)
        
        added = sync_response['added']
        cursor = sync_response['next_cursor']
        has_more = sync_response['has_more']
        
        # Process initial batch of transactions
        process_transactions(added, db, accounts)
        
        # Continue syncing if there are more transactions
        while has_more:
            sync_request = TransactionsSyncRequest(
                access_token=access_token,
                cursor=cursor
            )
            sync_response = client.transactions_sync(sync_request)
            
            process_transactions(sync_response['added'], db, accounts)
            
            cursor = sync_response['next_cursor']
            has_more = sync_response['has_more']
        
        return {"status": "success", "transactions_synced": len(added)}
        
    except plaid.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync transactions: {str(e)}")

def process_transactions(transactions: List[Dict[str, Any]], db: Session, accounts: List[BankAccount]) -> None:
    """Process transactions from Plaid and create them in our database"""
    
    # Create a mapping of Plaid account IDs to our account IDs
    account_map = {account.plaid_account_id: account.id for account in accounts}
    
    for transaction in transactions:
        # Skip if we don't have this account
        if transaction['account_id'] not in account_map:
            continue
        
        # Create transaction in our database
        trans_data = TransactionCreate(
            account_id=account_map[transaction['account_id']],
            amount=transaction['amount'],
            description=transaction['name'],
            merchant_name=transaction.get('merchant_name'),
            date=datetime.strptime(transaction['date'], '%Y-%m-%d').date(),
            is_pending=transaction['pending'],
            plaid_transaction_id=transaction['transaction_id'],
            # We'll handle categorization separately
            category_id=None
        )
        
        create_transaction(db, trans_data) 