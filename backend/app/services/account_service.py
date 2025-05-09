from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List

from backend.app.models.models import BankAccount, User, Couple, LedgerEvent, LedgerEventType
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
    
    # Create a ledger event for account creation
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=account_data.balance,
        source_account_id=None,
        dest_goal_id=None,
        user_id=account_data.user_id,
        event_metadata={
            "action": "account_created",
            "account_id": new_account.id,
            "account_name": new_account.name,
            "is_manual": new_account.is_manual
        }
    )
    
    db.add(log_event)
    db.commit()
    
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

def adjust_account_balance(db: Session, account_id: str, adjustment_amount: float, user_id: str, reason: str = None):
    """Adjust the balance of an account and log in ledger"""
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {account_id} not found")
    
    # For security, verify user owns the account
    if account.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to adjust this account")
    
    # Record previous balance
    previous_balance = account.balance
    
    # Update balance
    account.balance += adjustment_amount
    
    # Create ledger event
    log_event = LedgerEvent(
        event_type=LedgerEventType.ADJUSTMENT,
        amount=abs(adjustment_amount),  # Ledger amount is always positive
        source_account_id=account_id if adjustment_amount < 0 else None,
        dest_goal_id=None,
        user_id=user_id,
        event_metadata={
            "action": "balance_adjusted",
            "account_id": account_id,
            "previous_balance": previous_balance,
            "new_balance": account.balance,
            "reason": reason
        }
    )
    
    db.add(log_event)
    db.commit()
    db.refresh(account)
    
    return account