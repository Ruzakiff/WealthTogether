from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = Field(None, min_length=1)  # This enforces non-empty strings

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    # Add other updatable fields here in the future

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)  # Modern Pydantic v2 syntax 