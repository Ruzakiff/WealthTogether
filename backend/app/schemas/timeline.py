from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class TimelineItemType(str, Enum):
    LEDGER_EVENT = "ledger_event"
    JOURNAL_ENTRY = "journal_entry"
    GOAL_REACTION = "goal_reaction"
    MILESTONE = "milestone"

class TimelineItemBase(BaseModel):
    """Base class for timeline items"""
    timestamp: datetime
    item_type: TimelineItemType
    user_id: str
    metadata: Optional[Dict[str, Any]] = None

class TimelineItemResponse(TimelineItemBase):
    """Response model for timeline items"""
    id: str
    item_id: str  # ID of the original item
    title: str
    description: str
    icon: Optional[str] = None
    is_milestone: bool = False
    is_celebration: bool = False
    related_goal_id: Optional[str] = None
    related_account_id: Optional[str] = None
    user_display_name: str
    
    class Config:
        from_attributes = True

class TimelineFilter(BaseModel):
    """Filter options for timeline items"""
    couple_id: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    item_types: Optional[List[TimelineItemType]] = None
    user_id: Optional[str] = None
    goal_id: Optional[str] = None
    include_private: bool = False
    milestone_only: bool = False
    celebration_only: bool = False 