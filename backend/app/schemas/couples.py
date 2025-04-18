from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CoupleCreate(BaseModel):
    partner_1_id: str
    partner_2_id: str

class CoupleResponse(BaseModel):
    id: str
    partner_1_id: str
    partner_2_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True
