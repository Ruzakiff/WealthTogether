from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from backend.app.schemas.goals import FinancialGoalCreate, FinancialGoalResponse, GoalAllocation
from backend.app.services.goal_service import create_financial_goal, get_goals_by_couple, allocate_to_goal
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=FinancialGoalResponse)
async def create_goal(goal_data: FinancialGoalCreate, db: Session = Depends(get_db_session)):
    """
    Create a new financial goal.
    
    - Associates goal with a couple
    - Sets target amount, priority, and deadline
    - Initial allocation is zero
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

@router.post("/allocate", response_model=FinancialGoalResponse)
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
    """
    return allocate_to_goal(db, allocation_data, user_id) 