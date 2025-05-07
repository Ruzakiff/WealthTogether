from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel

class BudgetBase(BaseModel):
    category_id: str
    amount: float
    period: str  # monthly, weekly, etc.
    start_date: date

class BudgetCreate(BudgetBase):
    couple_id: str

class BudgetUpdate(BaseModel):
    category_id: Optional[str] = None
    amount: Optional[float] = None
    period: Optional[str] = None
    start_date: Optional[date] = None

class BudgetInDB(BudgetBase):
    id: str
    couple_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True 