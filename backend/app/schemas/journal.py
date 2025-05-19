from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from backend.app.models.models import JournalEntryType

class JournalEntryBase(BaseModel):
    entry_type: JournalEntryType
    content: str
    goal_id: Optional[str] = None
    is_private: bool = False

class JournalEntryCreate(JournalEntryBase):
    user_id: str
    couple_id: str

class JournalEntryUpdate(BaseModel):
    entry_type: Optional[JournalEntryType] = None
    content: Optional[str] = None
    is_private: Optional[bool] = None

class JournalEntryResponse(JournalEntryBase):
    id: str
    user_id: str
    couple_id: str
    timestamp: datetime
    
    class Config:
        orm_mode = True

class JournalEntryFilter(BaseModel):
    user_id: Optional[str] = None
    couple_id: Optional[str] = None
    entry_type: Optional[JournalEntryType] = None
    goal_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_private: bool = False 