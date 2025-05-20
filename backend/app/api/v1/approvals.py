from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID

from backend.app.schemas.approvals import (
    ApprovalCreate, ApprovalUpdate, ApprovalResponse, 
    ApprovalFilter, ApprovalSettingsCreate, ApprovalSettingsUpdate, 
    ApprovalSettingsResponse, ApprovalStatus, ApprovalActionType
)
from backend.app.services.approval_service import (
    create_pending_approval, get_pending_approvals, get_approval_by_id,
    update_approval_status, get_approval_settings, update_approval_settings
)
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=ApprovalResponse)
async def create_approval(
    approval_data: ApprovalCreate, 
    db: Session = Depends(get_db_session)
):
    """
    Create a new pending approval request.
    
    - Initiates approval workflow for financial decisions
    - Partner will be notified about pending approval
    - Returns the created approval request with status "pending"
    """
    return create_pending_approval(db, approval_data)

@router.get("/", response_model=List[ApprovalResponse])
async def list_approvals(
    couple_id: Optional[str] = None,
    status: Optional[ApprovalStatus] = None,
    action_type: Optional[ApprovalActionType] = None,
    initiated_by: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """
    List approval requests with optional filtering.
    
    - Filter by couple, status, action type, or initiator
    - Returns all matching approval requests
    """
    filters = ApprovalFilter(
        couple_id=couple_id,
        status=status,
        action_type=action_type,
        initiated_by=initiated_by
    )
    return get_pending_approvals(db, filters)

@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str, 
    db: Session = Depends(get_db_session)
):
    """
    Get a specific approval request by ID.
    
    - Returns detailed information about the approval
    - Includes status, payload, timestamps and resolution details if available
    """
    return get_approval_by_id(db, approval_id)

@router.put("/{approval_id}", response_model=Dict[str, Any])
async def resolve_approval(
    approval_id: str, 
    update_data: ApprovalUpdate, 
    db: Session = Depends(get_db_session)
):
    """
    Approve or reject a pending approval.
    
    - Updates the status (approved or rejected)
    - If approved, automatically executes the approved action
    - Creates ledger event recording the approval decision
    - Returns results of both the status update and action execution
    """
    _, result = update_approval_status(db, approval_id, update_data)
    return result

@router.get("/settings/{couple_id}", response_model=ApprovalSettingsResponse)
async def get_couple_approval_settings(
    couple_id: str, 
    db: Session = Depends(get_db_session)
):
    """
    Get approval settings for a couple.
    
    - Returns thresholds and configuration for approval workflows
    - Creates default settings if none exist yet
    """
    return get_approval_settings(db, couple_id)

@router.put("/settings/{couple_id}", response_model=ApprovalSettingsResponse)
async def update_couple_approval_settings(
    couple_id: str, 
    settings_data: ApprovalSettingsUpdate,
    db: Session = Depends(get_db_session)
):
    """
    Update approval settings for a couple.
    
    - Modify thresholds for different action types
    - Configure expiration times and notification preferences
    - Returns the updated settings
    """
    return update_approval_settings(db, couple_id, settings_data) 