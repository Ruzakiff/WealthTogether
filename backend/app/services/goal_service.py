from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from uuid import uuid4

from backend.app.models.models import FinancialGoal, Couple, BankAccount, AllocationMap, LedgerEvent, LedgerEventType, User
from backend.app.schemas.goals import FinancialGoalCreate, GoalAllocation, FinancialGoalUpdate
from backend.app.services.approval_service import check_approval_required, create_pending_approval
from backend.app.schemas.approvals import ApprovalCreate, ApprovalActionType

def create_financial_goal(db: Session, goal_data: FinancialGoalCreate):
    """Service function to create a new financial goal"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == goal_data.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {goal_data.couple_id} not found")
    
    # Check if approval is required
    if check_approval_required(
        db, 
        goal_data.couple_id, 
        ApprovalActionType.GOAL_CREATE, 
        amount=goal_data.target_amount
    ):
        # Create approval request
        # Convert date to string for JSON serialization
        goal_data_dict = goal_data.model_dump()
        if goal_data_dict.get('deadline') and isinstance(goal_data_dict['deadline'], date):
            goal_data_dict['deadline'] = goal_data_dict['deadline'].isoformat()
            
        approval_data = ApprovalCreate(
            couple_id=goal_data.couple_id,
            initiated_by=goal_data.created_by,
            action_type=ApprovalActionType.GOAL_CREATE,
            payload=goal_data_dict
        )
        approval = create_pending_approval(db, approval_data)
        
        # Return a response indicating approval is pending
        # Use a dict with similar structure to FinancialGoal but add pending status
        return {
            "status": "pending_approval",
            "message": "Goal creation requires partner approval",
            "approval_id": approval.id,
            "couple_id": goal_data.couple_id,
            "name": goal_data.name,
            "target_amount": goal_data.target_amount,
            "type": goal_data.type.value,
            "priority": goal_data.priority,
            "deadline": goal_data.deadline.isoformat() if goal_data.deadline else None
        }
    
    # If no approval required, proceed with creation
    return create_financial_goal_internal(db, goal_data.model_dump())

def create_financial_goal_internal(db: Session, goal_data: Dict[str, Any]):
    """
    Internal function to create a financial goal without approval checks.
    Used by approval system when executing approved requests.
    """
    # Convert string date to date object if needed
    if goal_data.get('deadline') and isinstance(goal_data['deadline'], str):
        try:
            goal_data['deadline'] = date.fromisoformat(goal_data['deadline'])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for deadline")
    
    # Create the goal
    goal = FinancialGoal(
        id=str(uuid4()),
        couple_id=goal_data["couple_id"],
        name=goal_data["name"],
        target_amount=goal_data["target_amount"],
        current_allocation=0.0,  # Always start with zero
        type=goal_data["type"],
        priority=goal_data.get("priority", 1),
        deadline=goal_data.get("deadline"),
        notes=goal_data.get("notes", "")
    )
    
    db.add(goal)
    db.commit()
    db.refresh(goal)
    
    # Create a creation event
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        user_id=goal_data.get("created_by"),
        event_metadata={
            "action": "goal_created",
            "goal_id": goal.id,
            "goal_name": goal.name,
            "target_amount": goal.target_amount
        }
    )
    db.add(log_event)
    db.commit()
    
    return goal

def get_goals_by_couple(db: Session, couple_id: str) -> List[FinancialGoal]:
    """Get all financial goals for a couple"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Return all goals for this couple
    return db.query(FinancialGoal).filter(FinancialGoal.couple_id == couple_id).all()
def allocate_to_goal(db: Session, allocation_data: GoalAllocation, user_id: str):
    """Service function to allocate funds to a goal"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == allocation_data.goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {allocation_data.goal_id} not found")
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == allocation_data.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {allocation_data.account_id} not found")
    
    # Check sufficient funds BEFORE approval check to prevent unnecessary approval requests
    if account.balance < allocation_data.amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient funds in account. Available: {account.balance}, Requested: {allocation_data.amount}"
        )
    
    # Check if user is part of the couple that owns the goal
    couple = db.query(Couple).filter(Couple.id == goal.couple_id).first()
    if not couple or (user_id != couple.partner_1_id and user_id != couple.partner_2_id):
        raise HTTPException(status_code=403, detail="User is not part of this couple")
    
    # Check if approval is required
    if check_approval_required(
        db, 
        goal.couple_id, 
        ApprovalActionType.ALLOCATION, 
        amount=allocation_data.amount
    ):
        # Create approval request
        approval_data = ApprovalCreate(
            couple_id=goal.couple_id,
            initiated_by=user_id,
            action_type=ApprovalActionType.ALLOCATION,
            payload={
                "account_id": allocation_data.account_id,
                "goal_id": allocation_data.goal_id,
                "amount": allocation_data.amount
            }
        )
        approval = create_pending_approval(db, approval_data)
        
        # Return a response indicating approval is pending
        return {
            "status": "pending_approval",
            "message": "Allocation requires partner approval",
            "approval_id": approval.id,
            "goal_id": allocation_data.goal_id,
            "account_id": allocation_data.account_id,
            "amount": allocation_data.amount
        }
    
    # If no approval required, proceed with allocation
    goal_result = allocate_to_goal_internal(db, allocation_data.model_dump(), user_id)
    
    # Check for milestones
    from backend.app.services.timeline_service import detect_milestones
    
    milestone = detect_milestones(db, allocation_data.goal_id, allocation_data.amount)
    if milestone:
        # Create milestone event for timeline
        milestone_event = LedgerEvent(
            event_type=LedgerEventType.SYSTEM,
            amount=0.0,  # No financial impact
            user_id=user_id,
            dest_goal_id=allocation_data.goal_id,
            event_metadata={
                "action": "goal_milestone",
                "milestone_type": milestone["type"],
                "percentage": milestone["percentage"],
                "goal_name": goal.name,
                "is_milestone": True
            }
        )
        db.add(milestone_event)
        db.commit()
    
    # Just return the dictionary as is since it's already properly formatted
    return goal_result

def allocate_to_goal_internal(db: Session, allocation_data: Dict[str, Any], user_id: str):
    """
    Internal function to allocate funds to a goal without approval checks.
    Used by approval system when executing approved requests.
    """
    account_id = allocation_data["account_id"]
    goal_id = allocation_data["goal_id"]
    amount = allocation_data["amount"]
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {account_id} not found")
    
    # Verify sufficient funds available in the account
    if account.balance < amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient funds in account. Available: {account.balance}, Requested: {amount}"
        )
    
    # Update goal allocation
    goal.current_allocation += amount
    
    # Create allocation mapping
    allocation_map = AllocationMap(
        goal_id=goal_id,
        account_id=account_id,
        allocated_amount=amount
    )
    
    # Create ledger event for the allocation
    event = LedgerEvent(
        event_type=LedgerEventType.ALLOCATION,
        amount=amount,
        source_account_id=account_id,
        dest_goal_id=goal_id,
        user_id=user_id,
        event_metadata={
            "goal_id": goal_id,
            "goal_name": goal.name,
            "account_id": account_id,
            "account_name": account.name
        }
    )
    
    # Update account balance
    account.balance -= amount
    
    # Save changes
    db.add(allocation_map)
    db.add(event)
    db.commit()
    db.refresh(goal)
    
    # Return a formatted response that matches the expected schema
    return {
        "id": goal.id,
        "couple_id": goal.couple_id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "type": goal.type,
        "current_allocation": goal.current_allocation,
        "priority": goal.priority,
        "deadline": goal.deadline,
        "notes": goal.notes,
        "created_at": goal.created_at,
        "modified_at": goal.modified_at if hasattr(goal, "modified_at") else None
    }

def reallocate_between_goals(
    db: Session, 
    source_goal_id: str, 
    dest_goal_id: str, 
    amount: float, 
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Reallocate funds from one goal to another"""
    
    # Verify both goals exist
    source_goal = db.query(FinancialGoal).filter(FinancialGoal.id == source_goal_id).first()
    if not source_goal:
        raise HTTPException(status_code=404, detail=f"Source goal with id {source_goal_id} not found")
    
    dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == dest_goal_id).first()
    if not dest_goal:
        raise HTTPException(status_code=404, detail=f"Destination goal with id {dest_goal_id} not found")
    
    # Verify goals belong to the same couple
    if source_goal.couple_id != dest_goal.couple_id:
        raise HTTPException(status_code=400, detail="Goals must belong to the same couple")
    
    # Check if user is part of the couple
    couple = db.query(Couple).filter(Couple.id == source_goal.couple_id).first()
    if not couple or (user_id != couple.partner_1_id and user_id != couple.partner_2_id):
        raise HTTPException(status_code=403, detail="User is not part of this couple")
    
    # Check if approval is required
    if check_approval_required(
        db, 
        source_goal.couple_id, 
        ApprovalActionType.REALLOCATION, 
        amount=amount
    ):
        # Create approval request
        approval_data = ApprovalCreate(
            couple_id=source_goal.couple_id,
            initiated_by=user_id,
            action_type=ApprovalActionType.REALLOCATION,
            payload={
                "source_goal_id": source_goal_id,
                "dest_goal_id": dest_goal_id,
                "amount": amount,
                "metadata": metadata or {}
            }
        )
        approval = create_pending_approval(db, approval_data)
        
        # Return a response indicating approval is pending
        return {
            "status": "pending_approval",
            "message": "Reallocation requires partner approval",
            "approval_id": approval.id,
            "source_goal_id": source_goal_id,
            "dest_goal_id": dest_goal_id,
            "amount": amount
        }
    
    # If no approval required, proceed with reallocation
    return reallocate_between_goals_internal(db, {
        "source_goal_id": source_goal_id,
        "dest_goal_id": dest_goal_id,
        "amount": amount,
        "user_id": user_id,
        "metadata": metadata or {}
    })

def reallocate_between_goals_internal(db: Session, realloc_data: Dict[str, Any]):
    """
    Internal function to reallocate funds between goals without approval checks.
    Used by approval system when executing approved requests.
    """
    # Extract data
    source_goal_id = realloc_data.get("source_goal_id")
    dest_goal_id = realloc_data.get("dest_goal_id")
    amount = realloc_data.get("amount")
    user_id = realloc_data.get("user_id")
    metadata = realloc_data.get("metadata", {})
    
    # Verify the source goal exists
    source_goal = db.query(FinancialGoal).filter(FinancialGoal.id == source_goal_id).first()
    if not source_goal:
        raise HTTPException(status_code=404, detail=f"Source goal with id {source_goal_id} not found")
    
    # Verify the destination goal exists
    dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == dest_goal_id).first()
    if not dest_goal:
        raise HTTPException(status_code=404, detail=f"Destination goal with id {dest_goal_id} not found")
    
    # Verify goals are from the same couple
    if source_goal.couple_id != dest_goal.couple_id:
        raise HTTPException(status_code=400, detail="Goals must belong to the same couple")
    
    # Verify sufficient funds
    if source_goal.current_allocation < amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient funds in source goal. Available: {source_goal.current_allocation}, Requested: {amount}"
        )
    
    # Perform the reallocation
    source_goal.current_allocation -= amount
    dest_goal.current_allocation += amount
    
    # Create a ledger event for the reallocation
    event_metadata = {
        "action": "goal_reallocation",
        "source_goal_id": source_goal.id,
        "source_goal_name": source_goal.name,
        "dest_goal_id": dest_goal.id,
        "dest_goal_name": dest_goal.name,
        "amount": amount
    }
    
    # Merge any additional metadata
    if metadata:
        event_metadata.update(metadata)
    
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=amount,
        user_id=user_id,
        event_metadata=event_metadata
    )
    
    db.add(log_event)
    db.commit()
    
    # Refresh the goals to get updated values
    db.refresh(source_goal)
    db.refresh(dest_goal)
    
    return {
        "source_goal": {
            "id": source_goal.id,
            "name": source_goal.name,
            "current_allocation": source_goal.current_allocation,
            "target_amount": source_goal.target_amount
        },
        "dest_goal": {
            "id": dest_goal.id,
            "name": dest_goal.name,
            "current_allocation": dest_goal.current_allocation,
            "target_amount": dest_goal.target_amount
        },
        "amount": amount
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

def batch_reallocate_goals(db: Session, rebalance_data: Dict[str, Any], user_id: str):
    """Process multiple goal reallocations in a batch"""
    
    # Check that we have a valid user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Preserve rebalance_id if provided
    rebalance_id = rebalance_data.get("rebalance_id")
    
    # Handle both API formats: rebalance_commit endpoint and batch reallocations
    if "from_goal_id" in rebalance_data and "to_goal_id" in rebalance_data:
        # Single reallocation from rebalance_commit endpoint
        result = reallocate_between_goals(
            db=db,
            source_goal_id=rebalance_data["from_goal_id"],
            dest_goal_id=rebalance_data["to_goal_id"],
            amount=rebalance_data["amount"],
            user_id=user_id,
            metadata={"action": "batch_rebalance"}
        )
        # Add rebalance_id to the result if it was in the input
        if rebalance_id and isinstance(result, dict):
            result["rebalance_id"] = rebalance_id
        return result
    
    # Handle both "moves" (from tests) and "reallocations" (from production code)
    reallocations = rebalance_data.get("reallocations", rebalance_data.get("moves", []))
    if not reallocations:
        raise HTTPException(status_code=400, detail="No reallocations provided")
    
    # Get total reallocation amount to check for approval
    total_amount = sum(r["amount"] for r in reallocations)
    
    # Get the couple_id from the first goal
    first_goal_id = reallocations[0].get("source_goal_id", reallocations[0].get("from_goal_id"))
    if not first_goal_id:
        raise HTTPException(status_code=400, detail="Missing source goal ID in reallocation data")
        
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == first_goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {first_goal_id} not found")
    
    couple_id = goal.couple_id
    
    # Check if approval is required for the batch (based on total amount)
    if check_approval_required(
        db, 
        couple_id, 
        ApprovalActionType.REALLOCATION, 
        amount=total_amount
    ):
        # Create approval request
        approval_data = ApprovalCreate(
            couple_id=couple_id,
            initiated_by=user_id,
            action_type=ApprovalActionType.REALLOCATION,
            payload=rebalance_data
        )
        approval = create_pending_approval(db, approval_data)
        
        # Return pending approval response with rebalance_id if provided
        response = {
            "status": "pending_approval",
            "message": "Goal reallocation batch requires partner approval",
            "approval_id": approval.id,
            "couple_id": couple_id,
            "total_amount": total_amount,
            "reallocation_count": len(reallocations)
        }
        if rebalance_id:
            response["rebalance_id"] = rebalance_id
        return response
    
    # If no approval required, process all reallocations
    results = []
    for realloc in reallocations:
        # Handle both key formats
        source_goal_id = realloc.get("source_goal_id", realloc.get("from_goal_id"))
        dest_goal_id = realloc.get("dest_goal_id", realloc.get("to_goal_id"))
        
        if not source_goal_id or not dest_goal_id:
            raise HTTPException(
                status_code=400, 
                detail="Each reallocation must have source_goal_id/from_goal_id and dest_goal_id/to_goal_id"
            )
            
        result = reallocate_between_goals(
            db=db,
            source_goal_id=source_goal_id,
            dest_goal_id=dest_goal_id,
            amount=realloc["amount"],
            user_id=user_id,
            metadata={"action": "batch_rebalance_item"}
        )
        results.append(result)
    
    # Create a summary event
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=total_amount,
        user_id=user_id,
        event_metadata={
            "action": "batch_rebalance_complete",
            "reallocation_count": len(reallocations),
            "total_amount": total_amount
        }
    )
    db.add(log_event)
    db.commit()
    
    # Return success response with rebalance_id if provided
    response = {
        "success": True,
        "message": f"Processed {len(results)} reallocation(s)",
        "total_amount": total_amount,
        "details": results
    }
    if rebalance_id:
        response["rebalance_id"] = rebalance_id
    return response

def update_financial_goal(db: Session, goal_id: str, update_data: FinancialGoalUpdate, user_id: str):
    """Update an existing financial goal"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Find the couple
    couple = db.query(Couple).filter(Couple.id == goal.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple for this goal not found")
    
    # Check if user is part of the couple
    if user_id != couple.partner_1_id and user_id != couple.partner_2_id:
        raise HTTPException(status_code=403, detail="User is not part of this couple")
    
    # Check if approval is required (only if target amount is being changed)
    if update_data.target_amount and check_approval_required(
        db, 
        goal.couple_id, 
        ApprovalActionType.GOAL_UPDATE, 
        amount=update_data.target_amount
    ):
        # Create approval request
        update_data_dict = update_data.model_dump(exclude_none=True)
        
        # Convert date to string for JSON serialization
        if update_data_dict.get('deadline') and isinstance(update_data_dict['deadline'], date):
            update_data_dict['deadline'] = update_data_dict['deadline'].isoformat()
            
        approval_data = ApprovalCreate(
            couple_id=goal.couple_id,
            initiated_by=user_id,
            action_type=ApprovalActionType.GOAL_UPDATE,
            payload={
                "goal_id": goal_id,
                **update_data_dict
            }
        )
        approval = create_pending_approval(db, approval_data)
        
        # Return a response indicating approval is pending
        return {
            "status": "pending_approval",
            "message": "Goal update requires partner approval",
            "approval_id": approval.id,
            "goal_id": goal_id,
            **update_data_dict
        }
    
    # If no approval required, proceed with update
    return update_financial_goal_internal(db, goal_id, update_data.model_dump(exclude_none=True))

def update_financial_goal_internal(db: Session, goal_id: str, update_data: Dict[str, Any]):
    """
    Internal function to update a financial goal without approval checks.
    Used by approval system when executing approved requests.
    """
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Update fields
    for key, value in update_data.items():
        if hasattr(goal, key):
            setattr(goal, key, value)
    
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

def simulate_goal_forecast(db: Session, goal_id: str, monthly_contribution: float) -> Dict[str, Any]:
    """
    Simulate how long it will take to complete a goal with a given monthly contribution.
    
    Args:
        db: Database session
        goal_id: ID of the goal to forecast
        monthly_contribution: Monthly amount to be contributed
        
    Returns:
        Dictionary with forecast details
    """
    # Get the goal
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Calculate remaining amount
    remaining_amount = goal.target_amount - goal.current_allocation
    
    if remaining_amount <= 0:
        return {
            "goal_id": goal.id,
            "goal_name": goal.name,
            "already_completed": True,
            "target_amount": goal.target_amount,
            "current_allocation": goal.current_allocation,
            "completion_percentage": 100
        }
    
    if monthly_contribution <= 0:
        raise HTTPException(status_code=400, detail="Monthly contribution must be positive")
    
    # Calculate months to completion
    months_to_completion = remaining_amount / monthly_contribution
    
    # Round up to the nearest month
    months_rounded = int(months_to_completion)
    if months_to_completion > months_rounded:
        months_rounded += 1
    
    # Calculate completion date
    today = date.today()
    completion_date = today + timedelta(days=30 * months_rounded)
    
    # Check if there's a deadline
    on_track = True
    if goal.deadline:
        on_track = completion_date <= goal.deadline
    
    return {
        "goal_id": goal.id,
        "goal_name": goal.name,
        "target_amount": goal.target_amount,
        "current_allocation": goal.current_allocation,
        "remaining_amount": remaining_amount,
        "monthly_contribution": monthly_contribution,
        "months_to_completion": months_rounded,
        "completion_date": completion_date.isoformat(),
        "completion_percentage": (goal.current_allocation / goal.target_amount) * 100,
        "has_deadline": goal.deadline is not None,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "on_track": on_track
    }

def commit_goal_rebalance(
    db: Session, 
    user_id: str,
    from_goal_id: str,
    to_goal_id: str,
    amount: float
) -> Dict[str, Any]:
    """
    Commit a rebalancing action by moving funds from one goal to another.
    This is just a wrapper around reallocate_between_goals for API consistency.
    """
    # Validate inputs
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    # Use the existing reallocate_between_goals function
    return reallocate_between_goals(
        db=db,
        source_goal_id=from_goal_id,
        dest_goal_id=to_goal_id,
        amount=amount,
        user_id=user_id,
        metadata={"action": "goal_rebalance_api"}
    ) 