from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.models.models import GoalReaction, User, FinancialGoal, LedgerEvent, LedgerEventType
from backend.app.schemas.reactions import GoalReactionCreate, GoalReactionUpdate, GoalReactionFilter

def create_goal_reaction(db: Session, reaction_data: GoalReactionCreate) -> GoalReaction:
    """Create a new goal reaction"""
    
    # Verify user exists
    user = db.query(User).filter(User.id == reaction_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {reaction_data.user_id} not found")
    
    # Verify goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == reaction_data.goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {reaction_data.goal_id} not found")
    
    # Create reaction
    new_reaction = GoalReaction(
        user_id=reaction_data.user_id,
        goal_id=reaction_data.goal_id,
        reaction_type=reaction_data.reaction_type,
        note=reaction_data.note,
        timestamp=datetime.now(timezone.utc)
    )
    
    # Add to database
    db.add(new_reaction)
    db.commit()
    db.refresh(new_reaction)
    
    # Create a ledger event for the reaction
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=0.0,  # No financial impact
        user_id=reaction_data.user_id,
        event_metadata={
            "action": "goal_reaction",
            "goal_id": str(goal.id),
            "goal_name": goal.name,
            "reaction_type": reaction_data.reaction_type,
            "reaction_id": str(new_reaction.id)
        }
    )
    db.add(log_event)
    db.commit()
    
    return new_reaction

def get_reactions(db: Session, filters: GoalReactionFilter, skip: int = 0, limit: int = 100) -> List[GoalReaction]:
    """Get reactions based on filters with pagination"""
    query = db.query(GoalReaction)
    
    if filters.goal_id:
        query = query.filter(GoalReaction.goal_id == filters.goal_id)
    
    if filters.user_id:
        query = query.filter(GoalReaction.user_id == filters.user_id)
    
    if filters.after_date:
        query = query.filter(GoalReaction.timestamp >= filters.after_date)
    
    if filters.before_date:
        query = query.filter(GoalReaction.timestamp <= filters.before_date)
    
    # Order by most recent first
    query = query.order_by(GoalReaction.timestamp.desc())
    
    # Apply pagination
    if limit is not None:
        query = query.limit(limit)
    
    if skip is not None:
        query = query.offset(skip)
    
    return query.all()

def get_reaction_by_id(db: Session, reaction_id: str) -> Optional[GoalReaction]:
    """Get a specific reaction by ID"""
    return db.query(GoalReaction).filter(GoalReaction.id == reaction_id).first()

def update_reaction(db: Session, reaction_id: str, reaction_data: GoalReactionUpdate, user_id: str) -> GoalReaction:
    """Update an existing reaction"""
    reaction = db.query(GoalReaction).filter(GoalReaction.id == reaction_id).first()
    if not reaction:
        raise HTTPException(status_code=404, detail=f"Reaction with id {reaction_id} not found")
    
    # Check if the user owns this reaction
    if reaction.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this reaction")
    
    # Update fields if provided
    if reaction_data.reaction_type is not None:
        reaction.reaction_type = reaction_data.reaction_type
    
    if reaction_data.note is not None:
        reaction.note = reaction_data.note
    
    db.commit()
    db.refresh(reaction)
    return reaction

def delete_reaction(db: Session, reaction_id: str, user_id: str) -> Dict[str, bool]:
    """Delete a reaction"""
    reaction = db.query(GoalReaction).filter(GoalReaction.id == reaction_id).first()
    if not reaction:
        raise HTTPException(status_code=404, detail=f"Reaction with id {reaction_id} not found")
    
    # Check if the user owns this reaction
    if reaction.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this reaction")
    
    db.delete(reaction)
    db.commit()
    return {"success": True} 