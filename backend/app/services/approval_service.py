from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from fastapi import HTTPException
from sqlalchemy.orm import Session
import json

from backend.app.models.models import PendingApproval, ApprovalStatus, ApprovalActionType, ApprovalSettings, Couple, User, LedgerEvent
from backend.app.schemas.approvals import ApprovalCreate, ApprovalUpdate, ApprovalFilter, ApprovalSettingsCreate, ApprovalSettingsUpdate
from backend.app.schemas.ledger import LedgerEventType

# Create a new pending approval
def create_pending_approval(
    db: Session, 
    approval_data: ApprovalCreate
) -> PendingApproval:
    """Create a pending approval request"""
    
    # Verify couple exists
    couple = db.query(Couple).filter(Couple.id == approval_data.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    # Verify user exists
    user = db.query(User).filter(User.id == approval_data.initiated_by).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify user is part of the couple
    if user.id not in [couple.partner_1_id, couple.partner_2_id]:
        raise HTTPException(status_code=403, detail="User is not part of this couple")
    
    # Set expiration if not provided
    settings = get_approval_settings(db, approval_data.couple_id)
    if not approval_data.expires_at:
        hours = settings.approval_expiration_hours if settings else 72  # Default to 72 hours if no settings
        approval_data.expires_at = datetime.utcnow() + timedelta(hours=hours)
    
    # Create pending approval
    db_approval = PendingApproval(
        couple_id=approval_data.couple_id,
        initiated_by=approval_data.initiated_by,
        action_type=approval_data.action_type,
        payload=approval_data.payload,
        status=ApprovalStatus.PENDING.value,
        expires_at=approval_data.expires_at
    )
    
    db.add(db_approval)
    
    # Log the approval request creation in the ledger
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM.value,
        user_id=approval_data.initiated_by,
        event_metadata={
            "action": "approval_requested",
            "approval_id": str(db_approval.id),
            "action_type": approval_data.action_type,
            "summary": f"Approval requested for {approval_data.action_type}"
        }
    )
    db.add(log_event)
    
    db.commit()
    db.refresh(db_approval)
    
    # TODO: Send notification to partner about the pending approval
    
    return db_approval

# Get pending approvals with optional filtering
def get_pending_approvals(
    db: Session, 
    filters: Optional[ApprovalFilter] = None
) -> List[PendingApproval]:
    """Get pending approvals with optional filtering"""
    
    query = db.query(PendingApproval)
    
    if filters:
        if filters.couple_id:
            query = query.filter(PendingApproval.couple_id == filters.couple_id)
        
        if filters.status:
            query = query.filter(PendingApproval.status == filters.status)
        
        if filters.action_type:
            query = query.filter(PendingApproval.action_type == filters.action_type)
        
        if filters.initiated_by:
            query = query.filter(PendingApproval.initiated_by == filters.initiated_by)
        
        if filters.created_after:
            query = query.filter(PendingApproval.created_at >= filters.created_after)
        
        if filters.created_before:
            query = query.filter(PendingApproval.created_at <= filters.created_before)
    
    return query.order_by(PendingApproval.created_at.desc()).all()

# Get a single approval by ID
def get_approval_by_id(db: Session, approval_id: str) -> PendingApproval:
    """Get a specific approval by ID"""
    
    approval = db.query(PendingApproval).filter(PendingApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return approval

# Update approval status (approve/reject)
def update_approval_status(
    db: Session, 
    approval_id: str, 
    update_data: ApprovalUpdate
) -> Tuple[PendingApproval, Dict[str, Any]]:
    """Update an approval status (approve/reject)"""
    
    approval = get_approval_by_id(db, approval_id)
    
    # Check if already resolved
    if approval.status != ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=400, 
            detail=f"This approval has already been {approval.status}"
        )
    
    # Check if expired
    if approval.expires_at and approval.expires_at < datetime.utcnow():
        approval.status = ApprovalStatus.EXPIRED.value
        approval.resolved_at = datetime.utcnow()
        
        db.commit()
        db.refresh(approval)
        
        raise HTTPException(
            status_code=400,
            detail="This approval request has expired"
        )
    
    # Verify resolver is authorized (partner of initiator)
    couple = db.query(Couple).filter(Couple.id == approval.couple_id).first()
    if update_data.resolved_by not in [couple.partner_1_id, couple.partner_2_id]:
        raise HTTPException(
            status_code=403,
            detail="Only partners in this couple can approve or reject"
        )
    
    # Prevent self-approval
    if update_data.resolved_by == approval.initiated_by:
        raise HTTPException(
            status_code=403,
            detail="You cannot approve your own request"
        )
    
    # Update approval status
    approval.status = update_data.status.value
    approval.resolved_at = datetime.utcnow()
    approval.resolved_by = update_data.resolved_by
    approval.resolution_note = update_data.resolution_note
    
    # Log in ledger
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM.value,
        user_id=update_data.resolved_by,
        event_metadata={
            "action": f"approval_{update_data.status.value}",
            "approval_id": approval_id,
            "action_type": approval.action_type,
            "summary": f"{update_data.status.value.capitalize()} {approval.action_type}"
        }
    )
    db.add(log_event)
    
    db.commit()
    db.refresh(approval)
    
    result = {"status": "success", "message": f"Approval {update_data.status.value}"}
    
    # Execute the approved action if status is APPROVED
    if update_data.status == ApprovalStatus.APPROVED:
        execution_result = execute_approved_action(db, approval)
        result["execution_result"] = execution_result
    
    # TODO: Send notification about approval resolution
    
    return approval, result

# Execute an approved action
def execute_approved_action(db: Session, approval: PendingApproval) -> Dict[str, Any]:
    """Execute the action specified in the approved request."""
    action_type = approval.action_type
    payload = approval.payload
    
    # Process date fields in payload if present
    if "start_date" in payload and isinstance(payload["start_date"], str):
        from datetime import date
        payload["start_date"] = date.fromisoformat(payload["start_date"])
    
    if action_type == ApprovalActionType.BUDGET_CREATE.value:
        from backend.app.services.budget_service import create_budget_internal
        result = create_budget_internal(db, payload)
        
        # Convert the SQLAlchemy model to a dictionary for JSON serialization
        if hasattr(result, "__dict__"):
            # Handle SQLAlchemy models by converting to dict
            result_dict = {
                "id": str(result.id),
                "couple_id": str(result.couple_id),
                "category_id": str(result.category_id),
                "amount": result.amount,
                "period": result.period,
                "start_date": result.start_date.isoformat() if hasattr(result.start_date, "isoformat") else str(result.start_date),
                "created_at": result.created_at.isoformat() if hasattr(result.created_at, "isoformat") else str(result.created_at)
            }
            return result_dict
        return result
    
    elif action_type == ApprovalActionType.BUDGET_UPDATE.value:
        from backend.app.services.budget_service import update_budget_internal
        budget_id = payload.pop("budget_id", None)
        if not budget_id:
            raise HTTPException(status_code=400, detail="Missing budget_id in approval payload")
        
        result = update_budget_internal(db, budget_id, payload)
        
        # Convert the SQLAlchemy model to a dictionary for JSON serialization
        if hasattr(result, "__dict__"):
            # Handle SQLAlchemy models
            result_dict = {
                "id": str(result.id),
                "couple_id": str(result.couple_id),
                "category_id": str(result.category_id),
                "amount": result.amount,
                "period": result.period,
                "start_date": result.start_date.isoformat() if hasattr(result.start_date, "isoformat") else str(result.start_date),
                "created_at": result.created_at.isoformat() if hasattr(result.created_at, "isoformat") else str(result.created_at)
            }
            return result_dict
        return result
    
    elif approval.action_type == ApprovalActionType.GOAL_CREATE.value:
        return {"message": "Goal creation would be executed here"}
    
    elif approval.action_type == ApprovalActionType.GOAL_UPDATE.value:
        return {"message": "Goal update would be executed here"}
    
    elif approval.action_type == ApprovalActionType.ALLOCATION.value:
        return {"message": "Allocation would be executed here"}
    
    elif approval.action_type == ApprovalActionType.REALLOCATION.value:
        return {"message": "Reallocation would be executed here"}
    
    elif approval.action_type == ApprovalActionType.AUTO_RULE_CREATE.value:
        return {"message": "Auto rule creation would be executed here"}
    
    elif approval.action_type == ApprovalActionType.AUTO_RULE_UPDATE.value:
        return {"message": "Auto rule update would be executed here"}
    
    # Default case - unknown action type
    raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")

# Approval settings functions
def get_approval_settings(db: Session, couple_id: str) -> ApprovalSettings:
    """Get approval settings for a couple"""
    
    settings = db.query(ApprovalSettings).filter(ApprovalSettings.couple_id == couple_id).first()
    
    # Create default settings if none exist
    if not settings:
        settings = create_default_approval_settings(db, couple_id)
    
    return settings

def create_default_approval_settings(db: Session, couple_id: str) -> ApprovalSettings:
    """Create default approval settings for a couple"""
    
    # Verify couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")
    
    settings = ApprovalSettings(couple_id=couple_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    
    return settings

def update_approval_settings(
    db: Session, 
    couple_id: str, 
    settings_data: ApprovalSettingsUpdate
) -> ApprovalSettings:
    """Update approval settings for a couple"""
    
    settings = get_approval_settings(db, couple_id)
    
    # Update fields
    for key, value in settings_data.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(settings)
    
    return settings

# Helper to check if an action requires approval
def check_approval_required(
    db: Session,
    couple_id: str,
    action_type: ApprovalActionType,
    amount: float = 0.0
) -> bool:
    """Check if an action requires approval based on settings and amount"""
    
    settings = get_approval_settings(db, couple_id)
    
    # If approvals are disabled, nothing requires approval
    if not settings.enabled:
        return False
    
    if action_type == ApprovalActionType.BUDGET_CREATE:
        return amount >= settings.budget_creation_threshold
    
    elif action_type == ApprovalActionType.BUDGET_UPDATE:
        return amount >= settings.budget_update_threshold
    
    elif action_type == ApprovalActionType.ALLOCATION:
        return amount >= settings.goal_allocation_threshold
    
    elif action_type == ApprovalActionType.REALLOCATION:
        return amount >= settings.goal_reallocation_threshold
    
    elif action_type in [ApprovalActionType.AUTO_RULE_CREATE, ApprovalActionType.AUTO_RULE_UPDATE]:
        return amount >= settings.auto_rule_threshold
    
    # Default to requiring approval for unknown action types
    return True