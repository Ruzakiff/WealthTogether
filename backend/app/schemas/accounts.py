from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class BankAccountCreate(BaseModel):
    user_id: str
    name: str
    balance: float = Field(..., ge=0)  # Add validation: greater than or equal to 0
    is_manual: bool = True
    plaid_account_id: Optional[str] = None
    institution_name: Optional[str] = None

class BankAccountResponse(BaseModel):
    id: str
    user_id: str
    name: str
    balance: float
    is_manual: bool
    plaid_account_id: Optional[str] = None
    institution_name: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True 

class AccountAdjustment(BaseModel):
    user_id: str
    amount: float  # Can be positive (increase) or negative (decrease)
    reason: Optional[str] = None 