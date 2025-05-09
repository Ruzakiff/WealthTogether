from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timedelta

from backend.app.models.models import BankAccount, FinancialGoal, Transaction, LedgerEvent, LedgerEventType
from backend.app.services.goal_service import allocate_to_goal
from backend.app.schemas.goals import GoalAllocation
from backend.app.database import get_db_session

router = APIRouter()

class SurplusCalculateRequest(BaseModel):
    account_ids: List[str]
    buffer_percent: float = 30.0  # Default 30% buffer

class SurplusAllocation(BaseModel):
    account_id: str
    goal_id: str
    amount: float
    note: str = None

class SurplusAllocateRequest(BaseModel):
    surplus_id: str = None
    allocations: List[SurplusAllocation]

@router.post("/calculate")
async def calculate_surplus(
    request: SurplusCalculateRequest,
    couple_id: str = Query(..., description="ID of the couple"),
    db: Session = Depends(get_db_session)
):
    """
    Calculate available surplus funds and suggest goal allocations
    """
    accounts = []
    for account_id in request.account_ids:
        account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
        accounts.append(account)
    
    # Calculate total available balance
    total_balance = sum(account.balance for account in accounts)
    
    # Calculate expenses over the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    expenses = db.query(Transaction).filter(
        Transaction.account_id.in_(request.account_ids),
        Transaction.amount < 0,  # Only expenses (negative amounts)
        Transaction.date >= thirty_days_ago
    ).all()
    
    monthly_expenses = sum(abs(t.amount) for t in expenses)
    
    # Calculate buffer amount
    buffer_amount = monthly_expenses * (request.buffer_percent / 100)
    
    # Calculate available surplus
    available_surplus = max(0, total_balance - buffer_amount)
    
    # Get goals and calculate allocation suggestions
    goals = db.query(FinancialGoal).filter(
        FinancialGoal.couple_id == couple_id
    ).order_by(FinancialGoal.priority).all()
    
    suggested_allocations = []
    remaining_surplus = available_surplus
    
    for goal in goals:
        # Skip completed goals
        if goal.current_allocation >= goal.target_amount:
            continue
            
        # Calculate gap to target
        gap = goal.target_amount - goal.current_allocation
        
        # Calculate suggested amount (higher priority = larger share)
        priority_factor = (6 - goal.priority) / 5  # Convert 1-5 priority to 1.0-0.2 factor
        suggested_amount = min(
            gap,  # Don't allocate more than needed
            remaining_surplus * priority_factor * 0.5  # Allocate proportionally but don't use all surplus at once
        )
        
        if suggested_amount > 0:
            # Choose the first account for simplicity
            account = accounts[0] if accounts else None
            
            if account:
                suggested_allocations.append({
                    "goal_id": goal.id,
                    "goal_name": goal.name,
                    "account_id": account.id,
                    "account_name": account.name,
                    "suggested_amount": round(suggested_amount, 2),
                    "gap_to_target": round(gap, 2),
                    "priority": goal.priority
                })
                
                remaining_surplus -= suggested_amount
    
    return {
        "total_balance": total_balance,
        "monthly_expenses": monthly_expenses,
        "buffer_amount": buffer_amount,
        "available_surplus": available_surplus,
        "suggested_allocations": suggested_allocations
    }

@router.post("/allocate")
async def allocate_surplus(
    request: SurplusAllocateRequest,
    user_id: str = Query(..., description="ID of the user performing the allocation"),
    db: Session = Depends(get_db_session)
):
    """
    Allocate surplus funds to goals and create ledger events
    """
    if not request.allocations:
        raise HTTPException(status_code=400, detail="No allocations specified")
    
    # Generate surplus ID if not provided
    surplus_id = request.surplus_id or str(uuid4())
    
    results = []
    for allocation in request.allocations:
        # Verify account and goal exist
        account = db.query(BankAccount).filter(BankAccount.id == allocation.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account {allocation.account_id} not found")
            
        goal = db.query(FinancialGoal).filter(FinancialGoal.id == allocation.goal_id).first()
        if not goal:
            raise HTTPException(status_code=404, detail=f"Goal {allocation.goal_id} not found")
        
        # Create allocation data for existing function
        allocation_data = GoalAllocation(
            goal_id=allocation.goal_id,
            account_id=allocation.account_id,
            amount=allocation.amount
        )
        
        # Use existing allocation function
        result = allocate_to_goal(db, allocation_data, user_id)
        
        results.append({
            "goal_id": allocation.goal_id,
            "goal_name": goal.name,
            "account_id": allocation.account_id,
            "account_name": account.name,
            "amount": allocation.amount,
            "successful": True
        })
    
    # Create a summary ledger event
    summary_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=sum(a.amount for a in request.allocations),
        user_id=user_id,
        event_metadata={
            "action": "surplus_allocation",
            "surplus_id": surplus_id,
            "allocation_count": len(request.allocations)
        }
    )
    db.add(summary_event)
    db.commit()
    
    return {
        "surplus_id": surplus_id,
        "allocations": results,
        "total_amount": sum(a.amount for a in request.allocations)
    } 