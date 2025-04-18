from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import uuid4

# Import your database models and session management
from backend.app.models.models import User
from database import get_db_session  # Assuming you have this function to get DB session

app = FastAPI()

class UserCreate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    
    class Config:
        from_attributes = True  # For Pydantic v2 (was orm_mode in v1)

@app.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db_session)):
    """
    Create a new user account.
    
    - Checks if user with email already exists
    - Creates new user in database
    - Returns user object with user_id
    """
    # Check if user with this email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    new_user = User(
        email=user_data.email,
        display_name=user_data.display_name
    )
    # The id and created_at fields will be auto-populated by the model defaults
    
    # Add to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Return user data
    return new_user
