from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from pydantic import BaseModel

from backend.app.database import get_db_session
from backend.app.services.goal_service import (
    simulate_goal_forecast,
    suggest_goal_rebalance,
    commit_goal_rebalance
)

router = APIRouter()

class RebalanceRequest(BaseModel):
    user_id: str
    from_goal_id: str
    to_goal_id: str
    amount: float

@router.post("/simulate", response_model=Dict[str, Any])
async def forecast_goal_endpoint(
    goal_id: str = Query(..., description="The goal ID to forecast"),
    monthly_contribution: float = Query(..., gt=0, description="Monthly contribution amount"),
    db: Session = Depends(get_db_session)
):
    """
    Simulate how long it will take to complete a goal given a monthly contribution.
    
    - Calculate the time to reach the target amount
    - Project the completion date
    - Check if completion date meets the deadline (if set)
    """
    return simulate_goal_forecast(db, goal_id, monthly_contribution)

@router.get("/rebalance/suggest", response_model=List[Dict[str, Any]])
async def suggest_rebalance_endpoint(
    couple_id: str = Query(..., description="The couple ID to suggest rebalancing for"),
    db: Session = Depends(get_db_session)
):
    """
    Suggest a rebalancing of funds between goals based on priorities and deadlines.
    
    - Analyze all goals and their current allocations
    - Identify low-priority goals with funds that could be moved
    - Recommend moves to higher-priority or deadline-sensitive goals
    """
    return suggest_goal_rebalance(db, couple_id)

@router.post("/rebalance/commit", response_model=Dict[str, Any])
async def commit_rebalance_endpoint(
    rebalance_data: RebalanceRequest,
    db: Session = Depends(get_db_session)
):
    """
    Commit a rebalancing action by moving funds from one goal to another.
    
    - Move specified amount from source goal to destination goal
    - Create ledger event to track the reallocation
    - Update goal allocation amounts
    """
    return commit_goal_rebalance(
        db,
        rebalance_data.user_id,
        rebalance_data.from_goal_id,
        rebalance_data.to_goal_id,
        rebalance_data.amount
    ) 