from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class AllocationTrigger(str, Enum):
    DEPOSIT = "deposit"
    SCHEDULE = "schedule"

class AutoAllocationRuleCreate(BaseModel):
    user_id: str
    source_account_id: str
    goal_id: str
    percent: float = Field(..., ge=0, le=100)
    trigger: AllocationTrigger = AllocationTrigger.DEPOSIT
    
    @validator('percent')
    def validate_percent(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Percent must be between 0 and 100')
        return v

class AutoAllocationRuleUpdate(BaseModel):
    percent: Optional[float] = Field(None, ge=0, le=100)
    trigger: Optional[AllocationTrigger] = None
    is_active: Optional[bool] = None
    
    @validator('percent')
    def validate_percent(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Percent must be between 0 and 100')
        return v

class AutoAllocationRuleResponse(BaseModel):
    id: str
    user_id: str
    source_account_id: str
    goal_id: str
    percent: float
    trigger: str
    is_active: bool
    created_at: datetime
    last_executed: Optional[datetime] = None
    
    # Include related entity names for UI convenience
    source_account_name: Optional[str] = None
    goal_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class ExecuteRulesRequest(BaseModel):
    account_id: str
    deposit_amount: Optional[float] = None
    manual_trigger: bool = False 