from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.schemas.reactions import (
    GoalReactionCreate, 
    GoalReactionUpdate, 
    GoalReactionResponse,
    GoalReactionFilter
)
from backend.app.services.reaction_service import (
    create_goal_reaction,
    get_reactions,
    get_reaction_by_id,
    update_reaction,
    delete_reaction
)
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=GoalReactionResponse)
async def add_reaction(
    reaction_data: GoalReactionCreate,
    db: Session = Depends(get_db_session)
):
    """
    Add an emotional reaction to a goal.
    
    - Express feelings about goal progress
    - Add optional note for context
    - Creates a social activity in the timeline
    """
    return create_goal_reaction(db, reaction_data)

@router.get("/", response_model=List[GoalReactionResponse])
async def get_goal_reactions(
    goal_id: Optional[str] = None,
    user_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_session)
):
    """
    Get reactions for a goal or by a user.
    
    - Filter by goal, user, or both
    - Returns most recent reactions first
    - Supports pagination with skip and limit parameters
    """
    filters = GoalReactionFilter(
        goal_id=goal_id,
        user_id=user_id
    )
    return get_reactions(db, filters, skip=skip, limit=limit)

@router.get("/{reaction_id}", response_model=GoalReactionResponse)
async def get_single_reaction(
    reaction_id: str,
    db: Session = Depends(get_db_session)
):
    """Get a specific reaction by ID"""
    reaction = get_reaction_by_id(db, reaction_id)
    if not reaction:
        raise HTTPException(status_code=404, detail=f"Reaction with id {reaction_id} not found")
    return reaction

@router.put("/{reaction_id}", response_model=GoalReactionResponse)
async def update_goal_reaction(
    reaction_id: str,
    reaction_data: GoalReactionUpdate,
    user_id: str = Query(..., description="ID of the user updating the reaction"),
    db: Session = Depends(get_db_session)
):
    """
    Update an existing reaction.
    
    - Can change reaction type or note
    - Only the original creator can update
    """
    return update_reaction(db, reaction_id, reaction_data, user_id)

@router.delete("/{reaction_id}")
async def delete_goal_reaction(
    reaction_id: str,
    user_id: str = Query(..., description="ID of the user deleting the reaction"),
    db: Session = Depends(get_db_session)
):
    """
    Delete a reaction.
    
    - Only the original creator can delete
    - Returns success status
    """
    return delete_reaction(db, reaction_id, user_id) 