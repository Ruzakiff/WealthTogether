from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from backend.app.schemas.accounts import BankAccountCreate, BankAccountResponse
from backend.app.services.account_service import create_bank_account, get_user_accounts, get_couple_accounts
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=BankAccountResponse)
async def create_account(account_data: BankAccountCreate, db: Session = Depends(get_db_session)):
    """
    Create a new bank account.
    
    - Links an account to a specific user
    - Can be manual or Plaid-synced
    """
    return create_bank_account(db, account_data)

@router.get("/", response_model=List[BankAccountResponse])
async def get_accounts(
    user_id: str = Query(None, description="Filter accounts by user ID"),
    couple_id: str = Query(None, description="Filter accounts by couple ID"), 
    db: Session = Depends(get_db_session)
):
    """
    Get accounts by user or couple.
    
    - Returns accounts owned by a specific user if user_id is provided
    - Returns accounts owned by either partner in a couple if couple_id is provided
    - One of user_id or couple_id must be provided
    """
    if not user_id and not couple_id:
        raise HTTPException(status_code=400, detail="Either user_id or couple_id must be provided")
    
    if user_id:
        return get_user_accounts(db, user_id)
    else:
        return get_couple_accounts(db, couple_id) 