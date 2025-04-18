from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from backend.app.models.models import GoalType

class FinancialGoalCreate(BaseModel):
    couple_id: str
    name: str
    target_amount: float = Field(gt=0)
    type: GoalType
    priority: int = Field(ge=1, le=5, description="1-5 priority scale, 1 being highest")
    deadline: Optional[date] = None
    notes: Optional[str] = None

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
