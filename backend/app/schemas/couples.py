from pydantic import BaseModel, ConfigDict
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
    
    model_config = ConfigDict(from_attributes=True)  # Modern Pydantic v2 syntax
