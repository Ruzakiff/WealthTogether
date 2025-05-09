from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import uuid4

from backend.app.services.goal_service import reallocate_between_goals
from backend.app.database import get_db_session
from backend.app.models.models import FinancialGoal

router = APIRouter()

class RebalanceMove(BaseModel):
    source_goal_id: str
    dest_goal_id: str
    amount: float
    note: str = None

class RebalanceRequest(BaseModel):
    rebalance_id: str = None
    moves: List[RebalanceMove]

@router.get("/suggest")
async def get_rebalance_suggestions(
    couple_id: str = Query(..., description="ID of the couple"),
    db: Session = Depends(get_db_session)
):
    """
    Get suggested goal rebalancing based on priority and progress
    """
    # Find all goals for this couple
    goals = db.query(FinancialGoal).filter(FinancialGoal.couple_id == couple_id).all()
    if not goals:
        return []
    
    # Simple logic: find high priority goals that need more funding
    suggestions = []
    for dest_goal in goals:
        # Goals that need funding (less than 50% funded and high priority)
        funding_percent = dest_goal.current_allocation / dest_goal.target_amount if dest_goal.target_amount > 0 else 1.0
        if dest_goal.priority <= 3 and funding_percent < 0.5:
            # Look for lower priority goals with funds
            for source_goal in goals:
                if source_goal.id != dest_goal.id and source_goal.priority > dest_goal.priority and source_goal.current_allocation > 0:
                    # Suggest moving some funds (up to 20% of source goal)
                    suggested_amount = min(
                        source_goal.current_allocation * 0.2,  # 20% max from source
                        dest_goal.target_amount - dest_goal.current_allocation  # amount needed
                    )
                    
                    if suggested_amount > 0:
                        suggestions.append({
                            "source_goal_id": source_goal.id,
                            "source_goal_name": source_goal.name,
                            "dest_goal_id": dest_goal.id,
                            "dest_goal_name": dest_goal.name,
                            "suggested_amount": round(suggested_amount, 2),
                            "source_priority": source_goal.priority,
                            "dest_priority": dest_goal.priority
                        })
    
    return suggestions

@router.post("/commit")
async def execute_rebalance(
    rebalance_data: RebalanceRequest,
    user_id: str = Query(..., description="ID of the user performing the rebalance"),
    db: Session = Depends(get_db_session)
):
    """
    Execute a rebalance operation, moving funds between goals
    """
    if not rebalance_data.moves:
        raise HTTPException(status_code=400, detail="No moves specified")
    
    # Generate rebalance ID if not provided
    rebalance_id = rebalance_data.rebalance_id or str(uuid4())
    
    results = []
    for move in rebalance_data.moves:
        # Call existing reallocation function for each move
        result = reallocate_between_goals(
            db=db,
            source_goal_id=move.source_goal_id,
            dest_goal_id=move.dest_goal_id,
            amount=move.amount,
            user_id=user_id,
            metadata={"rebalance_id": rebalance_id, "note": move.note}
        )
        
        # Get goal names for better response
        source_goal = db.query(FinancialGoal).filter(FinancialGoal.id == move.source_goal_id).first()
        dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == move.dest_goal_id).first()
        
        results.append({
            "source_goal_id": move.source_goal_id,
            "source_goal_name": source_goal.name if source_goal else "Unknown",
            "dest_goal_id": move.dest_goal_id,
            "dest_goal_name": dest_goal.name if dest_goal else "Unknown",
            "amount": move.amount,
            "successful": True
        })
    
    return {
        "rebalance_id": rebalance_id,
        "moves": results,
        "total_amount": sum(move.amount for move in rebalance_data.moves)
    } 