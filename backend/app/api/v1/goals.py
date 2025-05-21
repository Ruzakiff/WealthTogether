from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID

from backend.app.schemas.goals import (
    FinancialGoalCreate, FinancialGoalUpdate, FinancialGoalResponse, 
    GoalAllocation, GoalReallocation
)
from backend.app.services.goal_service import (
    create_financial_goal, get_goals_by_couple, allocate_to_goal, 
    reallocate_between_goals, update_financial_goal, forecast_goal_completion,
    suggest_goal_rebalance, batch_reallocate_goals
)
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=Dict[str, Any])
async def create_goal(goal_data: FinancialGoalCreate, db: Session = Depends(get_db_session)):
    """
    Create a new financial goal.
    
    - Associates goal with a couple
    - Sets target amount, priority, and deadline
    - Initial allocation is zero
    - May require partner approval based on settings
    """
    return create_financial_goal(db, goal_data)

@router.get("/", response_model=List[FinancialGoalResponse])
async def get_goals(
    couple_id: str = Query(..., description="ID of the couple to get goals for"),
    db: Session = Depends(get_db_session)
):
    """
    Get all financial goals for a couple.
    """
    return get_goals_by_couple(db, couple_id)

@router.post("/allocate", response_model=Dict[str, Any])
async def allocate_funds(
    allocation_data: GoalAllocation, 
    user_id: str = Query(..., description="ID of the user performing the allocation"),
    db: Session = Depends(get_db_session)
):
    """
    Allocate funds from an account to a goal.
    
    - Updates AllocationMap
    - Adjusts goal's current_allocation
    - Creates a LedgerEvent to track the action
    - May require partner approval based on settings
    """
    return allocate_to_goal(db, allocation_data, user_id)

@router.post("/reallocate", response_model=Dict[str, Any])
async def reallocate_funds(
    reallocation_data: GoalReallocation,
    user_id: str = Query(..., description="ID of the user performing the reallocation"),
    db: Session = Depends(get_db_session)
):
    """
    Reallocate funds from one goal to another.
    
    - Moves funds between goals
    - Updates both goals' current_allocation
    - Creates a LedgerEvent to track the reallocation
    - May require partner approval based on settings
    """
    return reallocate_between_goals(
        db,
        reallocation_data.source_goal_id,
        reallocation_data.dest_goal_id,
        reallocation_data.amount,
        user_id
    )

@router.put("/{goal_id}", response_model=Dict[str, Any])
async def update_goal(
    goal_id: str, 
    update_data: FinancialGoalUpdate,
    user_id: str = Query(..., description="ID of the user performing the update"),
    db: Session = Depends(get_db_session)
):
    """
    Update an existing financial goal.
    
    - Can modify name, target amount, priority, deadline, or notes
    - Returns the updated goal object
    - May require partner approval based on settings
    """
    return update_financial_goal(db, goal_id, update_data, user_id)

@router.post("/{goal_id}/forecast")
async def forecast_goal(
    goal_id: str,
    monthly_contribution: float = Query(..., gt=0, description="Monthly contribution amount"),
    db: Session = Depends(get_db_session)
):
    """
    Forecast when a goal will be completed based on monthly contributions.
    
    - Projects months to completion
    - Calculates estimated completion date
    - Shows remaining amount needed
    """
    return forecast_goal_completion(db, goal_id, monthly_contribution)

@router.get("/rebalance/suggest", response_model=List[Dict[str, Any]])
async def suggest_rebalance(
    couple_id: str = Query(..., description="ID of the couple to analyze goals for"),
    db: Session = Depends(get_db_session)
):
    """
    Get recommendations for rebalancing funds between goals.
    
    - Analyzes goal priorities and funding levels
    - Suggests moving money from lower to higher priority goals
    - Returns specific amounts and goal pairs for rebalancing
    """
    return suggest_goal_rebalance(db, couple_id)

@router.post("/rebalance/commit", response_model=Dict[str, Any])
async def batch_rebalance(
    rebalance_data: Dict[str, Any],
    user_id: str = Query(..., description="ID of the user performing the rebalance"),
    db: Session = Depends(get_db_session)
):
    """
    Process multiple goal reallocations in a single operation.
    
    - Takes a list of moves (source goal, destination goal, amount)
    - Processes all moves in a batch
    - Creates a single summary ledger event
    - May require partner approval based on settings
    """
    # Validate amount
    if "amount" in rebalance_data and rebalance_data["amount"] <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
        
    # Ensure a user ID is present either in the URL or JSON body
    if "user_id" not in rebalance_data and not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
        
    # Use the user_id from the query parameter if not in the JSON
    if "user_id" not in rebalance_data:
        rebalance_data["user_id"] = user_id
    
    return batch_reallocate_goals(db, rebalance_data, user_id) 