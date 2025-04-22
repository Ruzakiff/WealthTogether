from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from backend.app.models.models import LedgerEventType

class LedgerEventCreate(BaseModel):
    event_type: LedgerEventType
    amount: float = Field(gt=0)
    source_account_id: Optional[str] = None
    dest_goal_id: Optional[str] = None
    user_id: str
    event_metadata: Optional[Dict[str, Any]] = None

class LedgerEventResponse(BaseModel):
    id: str
    event_type: LedgerEventType
    amount: float
    source_account_id: Optional[str] = None
    dest_goal_id: Optional[str] = None
    user_id: str
    timestamp: datetime
    event_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True 