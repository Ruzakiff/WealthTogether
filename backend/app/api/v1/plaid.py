from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from pydantic import BaseModel

from backend.app.services.plaid_service import create_link_token, exchange_public_token, sync_transactions, create_sandbox_token
from backend.app.database import get_db_session
from backend.app.models.models import BankAccount, PlaidItem
from backend.app.services.plaid_service import client

router = APIRouter()

class SandboxTokenRequest(BaseModel):
    institution_id: str
    initial_products: List[str]

@router.post("/link", response_model=Dict[str, str])
async def generate_link_token(
    user_id: str = Body(..., embed=True),
    db: Session = Depends(get_db_session)
):
    """
    Generate a Plaid Link token to initiate account linking.
    
    - Required to start the Plaid Link flow
    - Frontend will use this token with Plaid Link
    """
    return create_link_token(user_id, db)

@router.post("/exchange", response_model=Dict[str, Any])
async def exchange_token(
    public_token: str = Body(...),
    metadata: Dict[str, Any] = Body(...),
    user_id: str = Body(...),
    db: Session = Depends(get_db_session)
):
    """
    Exchange a public token for access tokens and initialize account sync.
    
    - Called after successful Plaid Link flow
    - Creates bank accounts in our system
    - Initiates transaction sync
    """
    return exchange_public_token(public_token, metadata, user_id, db)

@router.post("/transactions/sync", response_model=Dict[str, Any])
async def manual_sync(
    user_id: str = Body(..., embed=True),
    db: Session = Depends(get_db_session)
):
    """
    Manual trigger to sync recent transactions from connected accounts.
    
    - Updates transactions for all Plaid-connected accounts owned by the user
    - Returns count of newly synced transactions
    """
    # Get all bank accounts for this user that have Plaid connections
    accounts = db.query(BankAccount).filter(
        BankAccount.user_id == user_id,
        BankAccount.plaid_account_id.isnot(None),
        BankAccount.is_manual == False
    ).all()
    
    if not accounts:
        return {"status": "no_accounts", "message": "No Plaid-connected accounts found for this user"}
    
    # Get the user's Plaid items
    plaid_items = db.query(PlaidItem).filter(PlaidItem.user_id == user_id).all()
    
    if not plaid_items:
        return {"status": "no_items", "message": "No Plaid items found for this user"}
    
    # Sync transactions for each Plaid item
    all_results = []
    for plaid_item in plaid_items:
        try:
            # Get current accounts for this Plaid item by fetching account info from Plaid
            accounts_response = client.accounts_get({"access_token": plaid_item.access_token})
            plaid_account_ids = [account['account_id'] for account in accounts_response['accounts']]
            
            # Filter accounts that match this Plaid item's account IDs
            item_accounts = [a for a in accounts if a.plaid_account_id in plaid_account_ids]
            
            if not item_accounts:
                continue
                
            sync_result = sync_transactions(plaid_item.access_token, db, item_accounts, plaid_item.id)
            all_results.append({
                "item_id": plaid_item.item_id,
                "institution": plaid_item.institution_name,
                "result": sync_result,
                "last_sync": plaid_item.last_sync_at.isoformat() if plaid_item.last_sync_at else None
            })
        except Exception as e:
            all_results.append({
                "item_id": plaid_item.item_id,
                "institution": plaid_item.institution_name,
                "error": str(e)
            })
    
    if not all_results:
        return {"status": "no_sync", "message": "No accounts were synced"}
        
    return {"status": "success", "accounts_synced": len(accounts), "sync_results": all_results}

@router.post("/sandbox/create_token", response_model=Dict[str, str])
async def create_sandbox_token_endpoint(
    request_data: SandboxTokenRequest,
    db: Session = Depends(get_db_session)
):
    """
    Create a sandbox public token for testing.
    
    - Creates a test token that can be exchanged just like a real one
    - For development/testing only
    """
    return create_sandbox_token(
        request_data.institution_id,
        request_data.initial_products
    ) 