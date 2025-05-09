from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Dict, Any
from datetime import datetime, timedelta

from backend.app.models.models import BankAccount, User, Couple, LedgerEvent, LedgerEventType, FinancialGoal, Transaction
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

def calculate_account_surplus(db: Session, couple_id: str, account_ids: List[str], buffer_percent: float = 30) -> Dict[str, Any]:
    """
    Calculate available surplus funds across specified accounts
    """
    # Get accounts
    accounts = db.query(BankAccount).filter(BankAccount.id.in_(account_ids)).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="No accounts found")
    
    # Calculate total balance
    total_balance = sum(account.balance for account in accounts)
    
    # Get recent expenses (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    expenses = db.query(Transaction).filter(
        Transaction.account_id.in_(account_ids),
        Transaction.amount < 0,
        Transaction.date >= thirty_days_ago
    ).all()
    
    total_expenses = sum(abs(expense.amount) for expense in expenses)
    
    # Calculate buffer amount
    buffer_amount = total_expenses * (buffer_percent / 100)
    
    # Calculate available surplus
    available_surplus = max(0, total_balance - buffer_amount)
    
    # Get goals to suggest allocations
    goals = db.query(FinancialGoal).filter(
        FinancialGoal.couple_id == couple_id
    ).order_by(FinancialGoal.priority).all()
    
    # Create allocation suggestions
    suggestions = []
    for goal in goals:
        gap = goal.target_amount - goal.current_allocation
        if gap > 0:
            suggestions.append({
                "goal_id": goal.id,
                "goal_name": goal.name,
                "gap_to_target": gap,
                "suggested_allocation": min(gap, available_surplus * 0.2)  # Simple allocation logic
            })
    
    return {
        "total_balance": total_balance,
        "buffer_amount": buffer_amount,
        "available_surplus": available_surplus,
        "suggested_allocations": suggestions
    }

def distribute_surplus(db: Session, user_id: str, allocations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Distribute surplus funds to goals based on provided allocations
    """
    from backend.app.services.goal_service import allocate_to_goal
    from backend.app.schemas.goals import GoalAllocation
    
    results = []
    total_allocated = 0
    
    # Process each allocation
    for allocation in allocations:
        # Create allocation data
        allocation_data = GoalAllocation(
            account_id=allocation["account_id"],
            goal_id=allocation["goal_id"],
            amount=allocation["amount"]
        )
        
        # Use existing allocate_to_goal function
        result = allocate_to_goal(db, allocation_data, user_id)
        
        results.append({
            "goal_id": allocation["goal_id"],
            "account_id": allocation["account_id"],
            "amount": allocation["amount"],
            "success": True
        })
        
        total_allocated += allocation["amount"]
    
    # Create a summary ledger event
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=total_allocated,
        user_id=user_id,
        event_metadata={
            "action": "surplus_distribution",
            "allocation_count": len(allocations)
        }
    )
    db.add(log_event)
    db.commit()
    
    return {
        "total_allocated": total_allocated,
        "allocations": results
    }