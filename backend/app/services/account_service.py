from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List

from backend.app.models.models import BankAccount, User, Couple
from backend.app.schemas.accounts import BankAccountCreate

def create_bank_account(db: Session, account_data: BankAccountCreate):
    """Service function to create a new bank account"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == account_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {account_data.user_id} not found")
    
    # Create new bank account
    new_account = BankAccount(
        user_id=account_data.user_id,
        name=account_data.name,
        balance=account_data.balance,
        is_manual=account_data.is_manual,
        plaid_account_id=account_data.plaid_account_id,
        institution_name=account_data.institution_name
    )
    
    # Add to database
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    
    return new_account

def get_user_accounts(db: Session, user_id: str) -> List[BankAccount]:
    """Get all bank accounts owned by a user"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    # Return all accounts owned by this user
    return db.query(BankAccount).filter(BankAccount.user_id == user_id).all()

def get_couple_accounts(db: Session, couple_id: str) -> List[BankAccount]:
    """Get all bank accounts owned by both partners in a couple"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Get all accounts owned by either partner
    return db.query(BankAccount).filter(
        (BankAccount.user_id == couple.partner_1_id) | 
        (BankAccount.user_id == couple.partner_2_id)
    ).all()