from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from uuid import uuid4

from backend.app.models.models import FinancialGoal, Couple, BankAccount, AllocationMap, LedgerEvent, LedgerEventType
from backend.app.schemas.goals import FinancialGoalCreate, GoalAllocation, FinancialGoalUpdate

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

def reallocate_between_goals(db: Session, 
                           source_goal_id: str, 
                           dest_goal_id: str, 
                           amount: float, 
                           user_id: str,
                           metadata: dict = None) -> Dict[str, Any]:
    """
    Reallocate funds between two goals
    """
    # Get the source and destination goals
    source_goal = db.query(FinancialGoal).filter(FinancialGoal.id == source_goal_id).first()
    if not source_goal:
        raise HTTPException(status_code=404, detail=f"Source goal with id {source_goal_id} not found")
    
    dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == dest_goal_id).first()
    if not dest_goal:
        raise HTTPException(status_code=404, detail=f"Destination goal with id {dest_goal_id} not found")
    
    # Ensure the goals belong to the same couple
    if source_goal.couple_id != dest_goal.couple_id:
        raise HTTPException(status_code=400, detail="Goals must belong to the same couple")
    
    # Check if source goal has enough allocation
    if source_goal.current_allocation < amount:
        raise HTTPException(status_code=400, detail=f"Source goal only has {source_goal.current_allocation} allocated, cannot transfer {amount}")
    
    # Update goal allocations
    source_goal.current_allocation -= amount
    dest_goal.current_allocation += amount
    
    # Create a ledger event for the reallocation
    metadata = metadata or {}
    metadata.update({
        "action": "goal_reallocation",
        "source_goal_id": source_goal_id,
        "source_goal_name": source_goal.name,
        "dest_goal_id": dest_goal_id,
        "dest_goal_name": dest_goal.name
    })
    
    log_event = LedgerEvent(
        event_type=LedgerEventType.REALLOCATION,
        amount=amount,
        user_id=user_id,
        event_metadata=metadata
    )
    
    # Commit changes
    db.add(log_event)
    db.commit()
    db.refresh(source_goal)
    db.refresh(dest_goal)
    
    # Convert model instances to dictionaries for proper serialization
    source_goal_dict = {
        "id": source_goal.id,
        "name": source_goal.name,
        "couple_id": source_goal.couple_id,
        "target_amount": source_goal.target_amount,
        "current_allocation": source_goal.current_allocation,
        "type": source_goal.type.name if hasattr(source_goal.type, "name") else str(source_goal.type),
        "priority": source_goal.priority
    }
    
    dest_goal_dict = {
        "id": dest_goal.id,
        "name": dest_goal.name,
        "couple_id": dest_goal.couple_id,
        "target_amount": dest_goal.target_amount,
        "current_allocation": dest_goal.current_allocation,
        "type": dest_goal.type.name if hasattr(dest_goal.type, "name") else str(dest_goal.type),
        "priority": dest_goal.priority
    }
    
    return {
        "source_goal": source_goal_dict,
        "dest_goal": dest_goal_dict,
        "amount": amount,
        "timestamp": log_event.timestamp.isoformat() if log_event.timestamp else None
    }

def suggest_goal_rebalance(db: Session, couple_id: str) -> List[Dict[str, Any]]:
    """
    Analyze goals and suggest rebalancing between them based on priority
    """
    # Get all goals for the couple
    goals = db.query(FinancialGoal).filter(FinancialGoal.couple_id == couple_id).all()
    
    if not goals:
        return []
    
    # Sort goals by priority (lower number = higher priority)
    goals.sort(key=lambda g: g.priority)
    
    suggestions = []
    
    # Compare each goal to lower priority goals
    for i, high_priority in enumerate(goals):
        # Skip fully funded goals
        if high_priority.current_allocation >= high_priority.target_amount:
            continue
            
        high_priority_percent = high_priority.current_allocation / high_priority.target_amount
        
        # Look at lower priority goals that have more funding percentage-wise
        for low_priority in goals[i+1:]:
            low_priority_percent = low_priority.current_allocation / low_priority.target_amount
            
            # If lower priority goal has higher funding percentage
            if low_priority_percent > high_priority_percent and low_priority.current_allocation > 0:
                # Calculate a reasonable amount to suggest moving
                # This is a simple algorithm - 25% of the lower priority goal's allocation
                # or the amount needed to equalize percentages, whichever is less
                max_move = low_priority.current_allocation * 0.25
                equalize_amount = (low_priority_percent - high_priority_percent) * high_priority.target_amount
                
                suggested_amount = min(max_move, equalize_amount)
                suggested_amount = round(suggested_amount, 2)
                
                if suggested_amount > 0:
                    suggestions.append({
                        "source_goal_id": low_priority.id,
                        "source_goal_name": low_priority.name,
                        "source_priority": low_priority.priority,
                        "dest_goal_id": high_priority.id,
                        "dest_goal_name": high_priority.name,
                        "dest_priority": high_priority.priority,
                        "suggested_amount": suggested_amount,
                        "reason": f"Higher priority goal ({high_priority.name}) is underfunded compared to lower priority goal ({low_priority.name})"
                    })
    
    return suggestions

def batch_reallocate_goals(db: Session, rebalance_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Process multiple goal reallocations in a single batch operation
    """
    if "rebalance_id" not in rebalance_data or "moves" not in rebalance_data:
        raise HTTPException(status_code=400, detail="Invalid rebalance data format")
    
    rebalance_id = rebalance_data["rebalance_id"]
    moves = rebalance_data["moves"]
    
    if not isinstance(moves, list) or len(moves) == 0:
        raise HTTPException(status_code=400, detail="Moves must be a non-empty list")
    
    # Track all movements
    results = []
    total_amount = 0
    
    # Process each move
    for move in moves:
        # Check for required fields
        if not all(k in move for k in ["source_goal_id", "dest_goal_id", "amount"]):
            raise HTTPException(status_code=400, detail="Each move must have source_goal_id, dest_goal_id, and amount")
        
        # Extract move data
        source_goal_id = move["source_goal_id"]
        dest_goal_id = move["dest_goal_id"]
        amount = move["amount"]
        
        # Process the individual reallocation
        try:
            result = reallocate_between_goals(
                db=db,
                source_goal_id=source_goal_id,
                dest_goal_id=dest_goal_id,
                amount=amount,
                user_id=user_id,
                metadata={"batch_id": rebalance_id}
            )
            
            results.append(result)
            total_amount += amount
            
        except HTTPException as e:
            # Roll back any previous reallocations if one fails
            db.rollback()
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Error processing move: {e.detail}"
            )
    
    # Create a summary ledger event for the batch
    batch_summary = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=total_amount,
        user_id=user_id,
        event_metadata={
            "action": "batch_reallocation",
            "rebalance_id": rebalance_id,
            "num_moves": len(moves),
            "total_amount": total_amount
        }
    )
    
    db.add(batch_summary)
    db.commit()
    
    return {
        "rebalance_id": rebalance_id,
        "results": results,
        "total_amount": total_amount,
        "timestamp": batch_summary.timestamp.isoformat() if batch_summary.timestamp else None
    }

def update_financial_goal(db: Session, goal_id: str, update_data: FinancialGoalUpdate):
    """Update an existing financial goal"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Update fields if provided
    if update_data.name is not None:
        goal.name = update_data.name
    
    if update_data.target_amount is not None:
        goal.target_amount = update_data.target_amount
    
    if update_data.priority is not None:
        goal.priority = update_data.priority
    
    if update_data.deadline is not None:
        goal.deadline = update_data.deadline
    
    if update_data.notes is not None:
        goal.notes = update_data.notes
    
    # Save changes
    db.commit()
    db.refresh(goal)
    
    return goal

def forecast_goal_completion(db: Session, goal_id: str, monthly_contribution: float):
    """Forecast when a goal will be completed based on monthly contributions"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Calculate months needed to reach target
    remaining_amount = goal.target_amount - goal.current_allocation
    
    if remaining_amount <= 0:
        months_to_completion = 0
    elif monthly_contribution <= 0:
        raise HTTPException(status_code=400, detail="Monthly contribution must be greater than zero")
    else:
        months_to_completion = int(remaining_amount / monthly_contribution)
        # Add 1 month if there's a remainder
        if remaining_amount % monthly_contribution > 0:
            months_to_completion += 1
    
    # Calculate projected completion date
    today = datetime.now().date()
    if months_to_completion == 0:
        projected_date = today
    else:
        year = today.year + ((today.month - 1 + months_to_completion) // 12)
        month = ((today.month - 1 + months_to_completion) % 12) + 1
        projected_date = date(year, month, min(today.day, 28))  # Using 28 to avoid month length issues
    
    return {
        "goal_id": goal_id,
        "goal_name": goal.name,
        "current_allocation": goal.current_allocation,
        "target_amount": goal.target_amount,
        "remaining_amount": remaining_amount,
        "monthly_contribution": monthly_contribution,
        "months_to_completion": months_to_completion,
        "projected_completion_date": projected_date
    } 