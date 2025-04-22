from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.schemas.ledger import LedgerEventCreate, LedgerEventResponse
from backend.app.services.ledger_service import (
    create_ledger_event, 
    get_user_ledger_events,
    get_couple_ledger_events,
    get_account_ledger_events,
    get_goal_ledger_events
)
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=LedgerEventResponse)
async def create_event(
    event_data: LedgerEventCreate, 
    db: Session = Depends(get_db_session)
):
    """
    Create a new ledger event.
    
    - Records financial actions like allocations, transactions, etc.
    - Requires at least a user, event type, and amount
    - Optional source account and destination goal
    """
    return create_ledger_event(db, event_data)

@router.get("/", response_model=List[LedgerEventResponse])
async def get_ledger_events(
    user_id: Optional[str] = Query(None, description="Filter events by user ID"),
    couple_id: Optional[str] = Query(None, description="Filter events by couple ID"),
    account_id: Optional[str] = Query(None, description="Filter events by account ID"),
    goal_id: Optional[str] = Query(None, description="Filter events by goal ID"),
    limit: int = Query(100, le=500, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    db: Session = Depends(get_db_session)
):
    """
    Get ledger events with various filters.
    
    - Can filter by user, couple, account, or goal
    - Exactly one filter must be provided
    - Results are paginated and sorted by timestamp (newest first)
    """
    filter_count = sum(1 for f in [user_id, couple_id, account_id, goal_id] if f is not None)
    
    if filter_count == 0:
        raise HTTPException(status_code=400, detail="At least one filter must be provided")
    elif filter_count > 1:
        raise HTTPException(status_code=400, detail="Only one filter can be applied at a time")
    
    if user_id:
        return get_user_ledger_events(db, user_id, limit, offset)
    elif couple_id:
        return get_couple_ledger_events(db, couple_id, limit, offset)
    elif account_id:
        return get_account_ledger_events(db, account_id, limit, offset)
    else:  # goal_id
        return get_goal_ledger_events(db, goal_id, limit, offset) 