from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import date
from uuid import uuid4

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
    
    # Create a ledger event for goal creation
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=goal_data.target_amount,
        user_id=goal_data.created_by,  # Assuming this exists or can be passed
        event_metadata={
            "action": "goal_created",
            "goal_id": str(new_goal.id),
            "goal_name": new_goal.name,
            "goal_type": str(new_goal.type)
        }
    )
    db.add(log_event)
    db.commit()
    
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
        raise HTTPException(status_code=403, detail=f"User does not own this account")
    
    # Check available funds (account balance minus existing allocations)
    existing_allocations = db.query(AllocationMap).filter(
        AllocationMap.account_id == allocation_data.account_id
    ).all()
    
    allocated_sum = sum(alloc.allocated_amount for alloc in existing_allocations)
    available_balance = account.balance - allocated_sum
    
    if available_balance < allocation_data.amount:
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

def reallocate_between_goals(db: Session, source_goal_id: str, dest_goal_id: str, 
                            amount: float, user_id: str):
    """Move allocation from one goal to another"""
    
    # Verify goals exist
    source_goal = db.query(FinancialGoal).filter(FinancialGoal.id == source_goal_id).first()
    dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == dest_goal_id).first()
    
    if not source_goal or not dest_goal:
        raise HTTPException(status_code=404, detail="One or both goals not found")
    
    # Verify sufficient funds in source goal
    if source_goal.current_allocation < amount:
        raise HTTPException(status_code=400, 
                           detail=f"Insufficient funds in source goal. Available: {source_goal.current_allocation}")
    
    # Update allocations
    source_goal.current_allocation -= amount
    dest_goal.current_allocation += amount
    
    # Create ledger event
    log_event = LedgerEvent(
        event_type=LedgerEventType.REALLOCATION,
        amount=amount,
        dest_goal_id=dest_goal_id,
        user_id=user_id,
        event_metadata={"source_goal_id": source_goal_id}
    )
    
    db.add(log_event)
    db.commit()
    
    return {"source_goal": source_goal, "dest_goal": dest_goal} 

def suggest_goal_rebalance(db: Session, couple_id: str) -> List[Dict[str, Any]]:
    """
    Analyze goals and suggest optimal rebalancing based on priority and progress
    """
    # Get all goals for the couple
    goals = db.query(FinancialGoal).filter(FinancialGoal.couple_id == couple_id).all()
    if not goals:
        return []
        
    # Logic to analyze goals and suggest rebalancing
    suggestions = []
    for goal in goals:
        # ... similar logic from earlier example, but simpler
        # Find goals that are high priority but underfunded
        if goal.priority <= 2 and goal.current_allocation / goal.target_amount < 0.5:
            # Find potential source goals
            for source in goals:
                if source.priority > goal.priority and source.current_allocation > 0:
                    # ... calculate suggested amount
                    suggestions.append({
                        "source_goal_id": source.id,
                        "source_goal_name": source.name,
                        "dest_goal_id": goal.id,
                        "dest_goal_name": goal.name,
                        "suggested_amount": min(source.current_allocation * 0.2, 
                                               goal.target_amount - goal.current_allocation)
                    })
    
    return suggestions

def batch_reallocate_goals(db: Session, rebalance_data: dict, user_id: str) -> Dict[str, Any]:
    """
    Process multiple goal reallocations in a single operation
    """
    results = {}
    total_amount = 0
    
    # Process each reallocation move
    for move in rebalance_data["moves"]:
        # Use the existing reallocate_between_goals function
        result = reallocate_between_goals(
            db, 
            move["source_goal_id"],
            move["dest_goal_id"],
            move["amount"],
            user_id,
            metadata={"batch_id": rebalance_data.get("rebalance_id", str(uuid4()))}
        )
        
        # Store the result
        key = f"{move['source_goal_id']}_to_{move['dest_goal_id']}"
        results[key] = result
        total_amount += move["amount"]
    
    # Create a summary ledger event
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=total_amount,
        user_id=user_id,
        event_metadata={
            "action": "batch_rebalance",
            "rebalance_id": rebalance_data.get("rebalance_id"),
            "move_count": len(rebalance_data["moves"])
        }
    )
    db.add(log_event)
    db.commit()
    
    return {
        "rebalance_id": rebalance_data.get("rebalance_id"),
        "results": results,
        "total_amount": total_amount
    } 