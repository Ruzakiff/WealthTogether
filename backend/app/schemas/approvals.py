from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
from uuid import UUID

class ApprovalActionType(str, Enum):
    BUDGET_CREATE = "budget_create"
    BUDGET_UPDATE = "budget_update"
    GOAL_CREATE = "goal_create"
    GOAL_UPDATE = "goal_update"
    ALLOCATION = "allocation"
    REALLOCATION = "reallocation"
    AUTO_RULE_CREATE = "auto_rule_create"
    AUTO_RULE_UPDATE = "auto_rule_update"

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELED = "canceled"

# Base schema with common attributes
class ApprovalBase(BaseModel):
    couple_id: str
    action_type: ApprovalActionType
    payload: Dict[str, Any]

# Schema for creating a new approval
class ApprovalCreate(ApprovalBase):
    initiated_by: str
    expires_at: Optional[datetime] = None

# Schema for updating an approval status
class ApprovalUpdate(BaseModel):
    status: ApprovalStatus
    resolved_by: str
    resolution_note: Optional[str] = None

# Schema for returning approval details
class ApprovalResponse(ApprovalBase):
    id: str
    initiated_by: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None

    class Config:
        orm_mode = True

# Schema for filtering approvals
class ApprovalFilter(BaseModel):
    couple_id: Optional[str] = None
    status: Optional[ApprovalStatus] = None
    action_type: Optional[ApprovalActionType] = None
    initiated_by: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

# Approval settings
class ApprovalSettingsBase(BaseModel):
    enabled: bool = True
    budget_creation_threshold: float = 500.0
    budget_update_threshold: float = 200.0
    goal_allocation_threshold: float = 500.0
    goal_reallocation_threshold: float = 300.0
    auto_rule_threshold: float = 300.0
    approval_expiration_hours: int = 72
    notify_on_create: bool = True
    notify_on_resolve: bool = True

class ApprovalSettingsCreate(ApprovalSettingsBase):
    couple_id: str

class ApprovalSettingsUpdate(ApprovalSettingsBase):
    pass

class ApprovalSettingsResponse(ApprovalSettingsBase):
    id: str
    couple_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True