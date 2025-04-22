from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime, timedelta

from backend.app.models.models import LedgerEvent, User, BankAccount, FinancialGoal, Couple
from backend.app.schemas.ledger import LedgerEventCreate

def create_ledger_event(db: Session, event_data: LedgerEventCreate):
    """Service function to create a new ledger event"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == event_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {event_data.user_id} not found")
    
    # If source account is provided, verify it exists
    if event_data.source_account_id:
        source_account = db.query(BankAccount).filter(BankAccount.id == event_data.source_account_id).first()
        if not source_account:
            raise HTTPException(status_code=404, detail=f"Source account with id {event_data.source_account_id} not found")
    
    # If destination goal is provided, verify it exists
    if event_data.dest_goal_id:
        dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == event_data.dest_goal_id).first()
        if not dest_goal:
            raise HTTPException(status_code=404, detail=f"Destination goal with id {event_data.dest_goal_id} not found")
    
    # Create new ledger event
    new_event = LedgerEvent(
        event_type=event_data.event_type,
        amount=event_data.amount,
        source_account_id=event_data.source_account_id,
        dest_goal_id=event_data.dest_goal_id,
        user_id=event_data.user_id,
        event_metadata=event_data.event_metadata
    )
    
    # Add to database
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    return new_event

def get_user_ledger_events(db: Session, user_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for a specific user"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    # Return events for this user with pagination
    return db.query(LedgerEvent).filter(LedgerEvent.user_id == user_id)\
        .order_by(LedgerEvent.timestamp.desc())\
        .offset(offset).limit(limit).all()

def get_couple_ledger_events(db: Session, couple_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for both partners in a couple"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Return events for either partner in this couple
    return db.query(LedgerEvent).filter(
        (LedgerEvent.user_id == couple.partner_1_id) |
        (LedgerEvent.user_id == couple.partner_2_id)
    ).order_by(LedgerEvent.timestamp.desc())\
      .offset(offset).limit(limit).all()

def get_account_ledger_events(db: Session, account_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for a specific account"""
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {account_id} not found")
    
    # Return events that involve this account
    return db.query(LedgerEvent).filter(
        LedgerEvent.source_account_id == account_id
    ).order_by(LedgerEvent.timestamp.desc())\
      .offset(offset).limit(limit).all()

def get_goal_ledger_events(db: Session, goal_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for a specific goal"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Return events that involve this goal
    return db.query(LedgerEvent).filter(
        LedgerEvent.dest_goal_id == goal_id
    ).order_by(LedgerEvent.timestamp.desc())\
      .offset(offset).limit(limit).all() 