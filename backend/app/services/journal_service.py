from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.app.models.models import JournalEntry, User, Couple, FinancialGoal, LedgerEvent, LedgerEventType
from backend.app.schemas.journal import JournalEntryCreate, JournalEntryUpdate, JournalEntryFilter

def create_journal_entry(db: Session, entry_data: JournalEntryCreate) -> JournalEntry:
    """Create a new journal entry"""
    
    # Verify user exists
    user = db.query(User).filter(User.id == entry_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {entry_data.user_id} not found")
    
    # Verify couple exists
    couple = db.query(Couple).filter(Couple.id == entry_data.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {entry_data.couple_id} not found")
    
    # Verify user belongs to couple
    if user.id != couple.partner_1_id and user.id != couple.partner_2_id:
        raise HTTPException(status_code=403, detail="User does not belong to this couple")
    
    # Verify goal exists if provided
    if entry_data.goal_id:
        goal = db.query(FinancialGoal).filter(FinancialGoal.id == entry_data.goal_id).first()
        if not goal:
            raise HTTPException(status_code=404, detail=f"Goal with id {entry_data.goal_id} not found")
        
        # Check goal belongs to couple
        if goal.couple_id != entry_data.couple_id:
            raise HTTPException(status_code=403, detail="Goal does not belong to this couple")
    
    # Create journal entry
    new_entry = JournalEntry(
        user_id=entry_data.user_id,
        couple_id=entry_data.couple_id,
        goal_id=entry_data.goal_id,
        entry_type=entry_data.entry_type,
        content=entry_data.content,
        is_private=entry_data.is_private,
        timestamp=datetime.utcnow()
    )
    
    # Add to database
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    # Create a ledger event for this entry with timeline-friendly metadata
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        user_id=entry_data.user_id,
        dest_goal_id=entry_data.goal_id,  # Link to goal if specified
        event_metadata={
            "action": "journal_entry_created",
            "entry_id": str(new_entry.id),
            "entry_type": str(new_entry.entry_type),
            "goal_id": str(new_entry.goal_id) if new_entry.goal_id else None,
            "is_private": new_entry.is_private,
            "title": entry_data.content[:50] + ("..." if len(entry_data.content) > 50 else ""),
            "for_timeline": True  # Flag for timeline service to identify timeline-relevant events
        }
    )
    db.add(log_event)
    db.commit()
    
    return new_entry

def get_journal_entries(db: Session, filters: JournalEntryFilter, requesting_user_id: str) -> List[JournalEntry]:
    """Get journal entries with filters"""
    
    query = db.query(JournalEntry)
    
    # Apply couple filter
    if filters.couple_id:
        query = query.filter(JournalEntry.couple_id == filters.couple_id)
        
        # Verify user belongs to couple
        couple = db.query(Couple).filter(Couple.id == filters.couple_id).first()
        if not couple:
            raise HTTPException(status_code=404, detail=f"Couple with id {filters.couple_id} not found")
        
        if requesting_user_id != couple.partner_1_id and requesting_user_id != couple.partner_2_id:
            raise HTTPException(status_code=403, detail="User does not belong to this couple")
    
    # Apply user filter (only if requesting user is filtering their own entries or is a partner)
    if filters.user_id:
        query = query.filter(JournalEntry.user_id == filters.user_id)
        
        # If filtering someone else's entries, verify requester is a partner
        if filters.user_id != requesting_user_id:
            entries_couple = db.query(Couple).filter(
                ((Couple.partner_1_id == filters.user_id) & (Couple.partner_2_id == requesting_user_id)) |
                ((Couple.partner_1_id == requesting_user_id) & (Couple.partner_2_id == filters.user_id))
            ).first()
            
            if not entries_couple:
                raise HTTPException(status_code=403, detail="Cannot access another user's entries unless you are partners")
    
    # Apply entry type filter
    if filters.entry_type:
        query = query.filter(JournalEntry.entry_type == filters.entry_type)
    
    # Apply goal filter
    if filters.goal_id:
        query = query.filter(JournalEntry.goal_id == filters.goal_id)
    
    # Apply date range filters
    if filters.start_date:
        query = query.filter(JournalEntry.timestamp >= filters.start_date)
    
    if filters.end_date:
        query = query.filter(JournalEntry.timestamp <= filters.end_date)
    
    # Handle private entries - always filter partner's private entries
    # If include_private is True, include the requesting user's private entries
    # If include_private is False, exclude all private entries
    if filters.include_private:
        query = query.filter(
            (JournalEntry.is_private == False) | 
            ((JournalEntry.is_private == True) & (JournalEntry.user_id == requesting_user_id))
        )
    else:
        query = query.filter(JournalEntry.is_private == False)
    
    # Return results sorted by timestamp (newest first)
    return query.order_by(JournalEntry.timestamp.desc()).all()

def get_journal_entry_by_id(db: Session, entry_id: str, requesting_user_id: str) -> JournalEntry:
    """Get a specific journal entry by ID"""
    
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Journal entry with id {entry_id} not found")
    
    # Check if requester can access this entry
    # Either it's their entry, or they're partners and it's not private
    if entry.user_id == requesting_user_id:
        return entry
    
    # Check if they're partners
    couple = db.query(Couple).filter(Couple.id == entry.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple not found")
    
    is_partner = (couple.partner_1_id == requesting_user_id or couple.partner_2_id == requesting_user_id)
    
    if not is_partner:
        raise HTTPException(status_code=403, detail="You do not have access to this journal entry")
    
    # Check privacy setting
    if entry.is_private:
        raise HTTPException(status_code=403, detail="This is a private journal entry")
    
    return entry

def update_journal_entry(db: Session, entry_id: str, update_data: JournalEntryUpdate, requesting_user_id: str) -> JournalEntry:
    """Update a journal entry"""
    
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Journal entry with id {entry_id} not found")
    
    # Only the author can update their entries
    if entry.user_id != requesting_user_id:
        raise HTTPException(status_code=403, detail="Only the author can update a journal entry")
    
    # Update fields if provided
    if update_data.entry_type is not None:
        entry.entry_type = update_data.entry_type
    
    if update_data.content is not None:
        entry.content = update_data.content
    
    if update_data.is_private is not None:
        entry.is_private = update_data.is_private
    
    # Commit changes
    db.commit()
    db.refresh(entry)
    
    # Create log entry for timeline
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        user_id=requesting_user_id,
        dest_goal_id=entry.goal_id,  # Link to goal if specified
        event_metadata={
            "action": "journal_entry_updated",
            "entry_id": str(entry.id),
            "entry_type": str(entry.entry_type),
            "is_private": entry.is_private,
            "title": entry.content[:50] + ("..." if len(entry.content) > 50 else ""),
            "for_timeline": True  # Flag for timeline service
        }
    )
    db.add(log_event)
    db.commit()
    
    return entry

def delete_journal_entry(db: Session, entry_id: str, requesting_user_id: str) -> Dict[str, Any]:
    """Delete a journal entry"""
    
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Journal entry with id {entry_id} not found")
    
    # Only the author can delete their entries
    if entry.user_id != requesting_user_id:
        raise HTTPException(status_code=403, detail="Only the author can delete a journal entry")
    
    # Create log entry for timeline before deleting the entry
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        user_id=requesting_user_id,
        dest_goal_id=entry.goal_id,  # Link to goal if specified
        event_metadata={
            "action": "journal_entry_deleted",
            "entry_id": str(entry.id),
            "entry_type": str(entry.entry_type),
            "for_timeline": True  # Flag for timeline service
        }
    )
    db.add(log_event)
    
    # Delete the entry
    db.delete(entry)
    db.commit()
    
    return {"success": True, "message": "Journal entry deleted"} 