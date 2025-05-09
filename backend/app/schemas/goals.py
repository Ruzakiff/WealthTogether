from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum
from backend.app.models.models import GoalType



class FinancialGoalCreate(BaseModel):
    couple_id: str
    name: str
    target_amount: float
    type: GoalType
    priority: int = 3
    deadline: Optional[date] = None
    notes: Optional[str] = None
    created_by: str  # Add this line

class FinancialGoalResponse(BaseModel):
    id: str
    couple_id: str
    name: str
    target_amount: float
    type: GoalType
    current_allocation: float
    priority: int
    deadline: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class GoalAllocation(BaseModel):
    account_id: str
    goal_id: str
    amount: float = Field(gt=0)

class GoalReallocation(BaseModel):
    source_goal_id: str
    dest_goal_id: str
    amount: float = Field(gt=0)
