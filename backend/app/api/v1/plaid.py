from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.app.services.plaid_service import create_link_token, exchange_public_token, sync_transactions
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/link/{user_id}", response_model=Dict[str, str])
async def generate_link_token(
    user_id: str,
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

@router.post("/sync", response_model=Dict[str, Any])
async def manual_sync(
    user_id: str = Body(...),
    db: Session = Depends(get_db_session)
):
    """
    Manual trigger to sync recent transactions from connected accounts.
    
    - Updates transactions for all Plaid-connected accounts owned by the user
    - Returns count of newly synced transactions
    """
    # This is a simplified version - in a real implementation, you would:
    # 1. Get all Plaid-connected accounts for this user
    # 2. Retrieve the access tokens for each
    # 3. Call sync_transactions for each token
    
    # For simplicity, returning a placeholder response
    return {"status": "Not implemented"} 