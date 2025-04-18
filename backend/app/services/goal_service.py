from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import date

from backend.app.models.models import FinancialGoal, Couple, BankAccount, AllocationMap, LedgerEvent, LedgerEventType
from backend.app.schemas.goals import FinancialGoalCreate, GoalAllocation

def create_financial_goal(db: Session, goal_data: FinancialGoalCreate):
    """Service function to create a new financial goal"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == goal_data.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {goal_data.couple_id} not found")
    
    # Create new financial goal
    new_goal = FinancialGoal(
        couple_id=goal_data.couple_id,
        name=goal_data.name,
        target_amount=goal_data.target_amount,
        type=goal_data.type,
        current_allocation=0.0,  # Start with zero allocation
        priority=goal_data.priority,
        deadline=goal_data.deadline,
        notes=goal_data.notes
    )
    
    # Add to database
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    
    return new_goal

def get_goals_by_couple(db: Session, couple_id: str) -> List[FinancialGoal]:
    """Get all financial goals for a couple"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Return all goals for this couple
    return db.query(FinancialGoal).filter(FinancialGoal.couple_id == couple_id).all()

def allocate_to_goal(db: Session, allocation_data: GoalAllocation, user_id: str):
    """Allocate funds from an account to a goal"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == allocation_data.goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {allocation_data.goal_id} not found")
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == allocation_data.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {allocation_data.account_id} not found")
    
    # Verify user owns this account
    if account.user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to allocate from this account")
    
    # Check if amount is available in the account
    existing_allocations = db.query(AllocationMap).filter(
        AllocationMap.account_id == allocation_data.account_id
    ).all()
    
    total_allocated = sum(alloc.allocated_amount for alloc in existing_allocations)
    available_balance = account.balance - total_allocated
    
    if allocation_data.amount > available_balance:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient available funds. Available: {available_balance}, Requested: {allocation_data.amount}"
        )
    
    # Check if allocation already exists - if so, update it
    existing_allocation = db.query(AllocationMap).filter(
        AllocationMap.goal_id == allocation_data.goal_id,
        AllocationMap.account_id == allocation_data.account_id
    ).first()
    
    if existing_allocation:
        # Update the existing allocation
        old_amount = existing_allocation.allocated_amount
        existing_allocation.allocated_amount += allocation_data.amount
        db.commit()
        
        # Update goal's current allocation
        goal.current_allocation += allocation_data.amount
        db.commit()
        
        # Log the change
        log_event = LedgerEvent(
            event_type=LedgerEventType.ALLOCATION,
            amount=allocation_data.amount,
            source_account_id=allocation_data.account_id,
            dest_goal_id=allocation_data.goal_id,
            user_id=user_id,
            event_metadata={"previous_allocation": old_amount}
        )
    else:
        # Create a new allocation
        new_allocation = AllocationMap(
            goal_id=allocation_data.goal_id,
            account_id=allocation_data.account_id,
            allocated_amount=allocation_data.amount
        )
        db.add(new_allocation)
        db.commit()
        
        # Update goal's current allocation
        goal.current_allocation += allocation_data.amount
        db.commit()
        
        # Log the event
        log_event = LedgerEvent(
            event_type=LedgerEventType.ALLOCATION,
            amount=allocation_data.amount,
            source_account_id=allocation_data.account_id,
            dest_goal_id=allocation_data.goal_id,
            user_id=user_id,
            event_metadata={"initial_allocation": True}
        )
    
    # Add the log event
    db.add(log_event)
    db.commit()
    
    # Return the updated goal
    db.refresh(goal)
    return goal 