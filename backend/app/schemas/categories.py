from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CategoryCreate(BaseModel):
    name: str
    parent_category_id: Optional[str] = None
    icon: Optional[str] = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    parent_category_id: Optional[str] = None
    icon: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True 