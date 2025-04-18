from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    
    class Config:
        from_attributes = True  # For Pydantic v2 (was orm_mode in v1) 