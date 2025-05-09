from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field

class BudgetBase(BaseModel):
    category_id: str
    amount: float
    period: str  # monthly, weekly, etc.
    start_date: date

class BudgetCreate(BudgetBase):
    couple_id: str
    created_by: str  # User ID of the creator for ledger tracking

class BudgetUpdate(BaseModel):
    category_id: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    period: Optional[str] = None
    start_date: Optional[date] = None
    updated_by: str  # User ID of the updater for ledger tracking
    previous_amount: Optional[float] = None  # For tracking in the ledger

class BudgetInDB(BudgetBase):
    id: str
    couple_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True 