from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.app.models.models import User
from backend.app.schemas.users import UserCreate

def create_user(db: Session, user_data: UserCreate):
    """Service function to create a new user"""
    # Check if user with this email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    new_user = User(
        email=user_data.email,
        display_name=user_data.display_name
    )
    
    # Add to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user 