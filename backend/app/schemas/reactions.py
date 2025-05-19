from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class ReactionType(str, Enum):
    HAPPY = "happy"
    EXCITED = "excited"
    PROUD = "proud"
    CONCERNED = "concerned"
    DISAPPOINTED = "disappointed"
    MOTIVATED = "motivated"
    CELEBRATING = "celebrating"
    DETERMINED = "determined"


class GoalReactionCreate(BaseModel):
    user_id: str
    goal_id: str
    reaction_type: ReactionType
    note: Optional[str] = None


class GoalReactionUpdate(BaseModel):
    reaction_type: Optional[ReactionType] = None
    note: Optional[str] = None


class GoalReactionResponse(BaseModel):
    id: str
    user_id: str
    goal_id: str
    reaction_type: str
    note: Optional[str] = None
    timestamp: datetime
    
    class Config:
        orm_mode = True
        json_encoders = {
            # Ensure timestamps are serialized with timezone info, but don't add Z if already has timezone
            datetime: lambda dt: dt.isoformat() if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc).isoformat()
        }


class GoalReactionFilter(BaseModel):
    goal_id: Optional[str] = None
    user_id: Optional[str] = None
    after_date: Optional[datetime] = None
    before_date: Optional[datetime] = None 