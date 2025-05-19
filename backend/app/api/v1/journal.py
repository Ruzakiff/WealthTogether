from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.app.schemas.journal import (
    JournalEntryCreate, 
    JournalEntryUpdate, 
    JournalEntryResponse,
    JournalEntryFilter
)
from backend.app.services.journal_service import (
    create_journal_entry,
    get_journal_entries,
    get_journal_entry_by_id,
    update_journal_entry,
    delete_journal_entry
)
from backend.app.database import get_db_session
from backend.app.models.models import JournalEntryType

router = APIRouter()

@router.post("/", response_model=JournalEntryResponse)
async def create_entry(
    entry_data: JournalEntryCreate,
    db: Session = Depends(get_db_session)
):
    """
    Create a new journal entry.
    
    - Records financial reflections, celebrations, or concerns
    - Can be linked to specific goals
    - Privacy controls for sensitive entries
    """
    return create_journal_entry(db, entry_data)

@router.get("/", response_model=List[JournalEntryResponse])
async def get_entries(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    couple_id: Optional[str] = Query(None, description="Filter by couple ID"),
    entry_type: Optional[JournalEntryType] = Query(None, description="Filter by entry type"),
    goal_id: Optional[str] = Query(None, description="Filter by associated goal"),
    start_date: Optional[datetime] = Query(None, description="Filter entries from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter entries until this date"),
    include_private: bool = Query(False, description="Include private entries (only works for your own entries)"),
    requesting_user_id: str = Query(..., description="ID of the user making the request"),
    db: Session = Depends(get_db_session)
):
    """
    Get journal entries with various filters.
    
    - Filter by user, couple, entry type, or goal
    - Date range filtering
    - Respects privacy settings
    """
    filters = JournalEntryFilter(
        user_id=user_id,
        couple_id=couple_id,
        entry_type=entry_type,
        goal_id=goal_id,
        start_date=start_date,
        end_date=end_date,
        include_private=include_private
    )
    
    return get_journal_entries(db, filters, requesting_user_id)

@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_entry(
    entry_id: str,
    requesting_user_id: str = Query(..., description="ID of the user making the request"),
    db: Session = Depends(get_db_session)
):
    """
    Get a specific journal entry by ID.
    
    - Access controls based on relationship to entry author
    - Respects privacy settings
    """
    return get_journal_entry_by_id(db, entry_id, requesting_user_id)

@router.put("/{entry_id}", response_model=JournalEntryResponse)
async def update_entry(
    entry_id: str,
    update_data: JournalEntryUpdate,
    requesting_user_id: str = Query(..., description="ID of the user making the request"),
    db: Session = Depends(get_db_session)
):
    """
    Update an existing journal entry.
    
    - Can modify content, type, or privacy setting
    - Only the author can update their entries
    """
    return update_journal_entry(db, entry_id, update_data, requesting_user_id)

@router.delete("/{entry_id}", response_model=Dict[str, Any])
async def delete_entry(
    entry_id: str,
    requesting_user_id: str = Query(..., description="ID of the user making the request"),
    db: Session = Depends(get_db_session)
):
    """
    Delete a journal entry.
    
    - Only the author can delete their entries
    - Returns success status
    """
    return delete_journal_entry(db, entry_id, requesting_user_id) 