from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BankAccountCreate(BaseModel):
    user_id: str
    name: str
    balance: float
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