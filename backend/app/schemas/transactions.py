from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date

class TransactionCreate(BaseModel):
    account_id: str
    amount: float
    description: str
    merchant_name: Optional[str] = None
    date: date
    category_id: Optional[str] = None
    is_pending: bool = False
    plaid_transaction_id: Optional[str] = None

class TransactionResponse(BaseModel):
    id: str
    account_id: str
    amount: float
    description: str
    merchant_name: Optional[str] = None
    date: date
    category_id: Optional[str] = None
    is_pending: bool
    plaid_transaction_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionCategorize(BaseModel):
    transaction_id: str
    category_id: str 