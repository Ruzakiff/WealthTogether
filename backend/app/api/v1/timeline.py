from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.app.schemas.timeline import TimelineItemResponse, TimelineFilter, TimelineItemType
from backend.app.services.timeline_service import get_timeline_feed, get_timeline_summary
from backend.app.database import get_db_session

router = APIRouter()

@router.get("/", response_model=List[TimelineItemResponse])
async def get_timeline(
    couple_id: str = Query(..., description="The couple ID to get timeline for"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering timeline items"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering timeline items"),
    item_types: Optional[List[TimelineItemType]] = Query(None, description="Types of items to include"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    goal_id: Optional[str] = Query(None, description="Filter by goal ID"),
    include_private: bool = Query(False, description="Include private journal entries"),
    milestone_only: bool = Query(False, description="Only include milestone events"),
    celebration_only: bool = Query(False, description="Only include celebration events"),
    limit: int = Query(20, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: Session = Depends(get_db_session)
):
    """
    Get a unified timeline feed of all couple activity including:
    - Financial transactions and allocations
    - Journal entries and reflections
    - Goal reactions and emotional responses
    - System events and milestones
    
    Results are sorted by timestamp (newest first) and can be filtered.
    """
    filter_options = TimelineFilter(
        couple_id=couple_id,
        start_date=start_date,
        end_date=end_date,
        item_types=item_types,
        user_id=user_id,
        goal_id=goal_id,
        include_private=include_private,
        milestone_only=milestone_only,
        celebration_only=celebration_only
    )
    
    return get_timeline_feed(db, filter_options, limit, offset)

@router.get("/summary", response_model=Dict[str, Any])
async def get_timeline_activity_summary(
    couple_id: str = Query(..., description="The couple ID to get summary for"),
    days: int = Query(30, description="Number of days to include in summary"),
    db: Session = Depends(get_db_session)
):
    """
    Get a summarized view of timeline activity for a specified period.
    
    Returns counts, participation stats, and milestone highlights.
    """
    return get_timeline_summary(db, couple_id, days)