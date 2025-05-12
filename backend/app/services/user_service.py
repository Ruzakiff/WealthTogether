from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.app.models.models import User
from backend.app.schemas.users import UserCreate, UserUpdate

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

def get_all_users(db: Session):
    """Service function to get all users"""
    return db.query(User).all()

def get_user_by_id(db: Session, user_id: str):
    """Service function to get a user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    return user

def get_user_by_email(db: Session, email: str):
    """Service function to get a user by email"""
    return db.query(User).filter(User.email == email).first()

def update_user(db: Session, user_id: str, user_data: UserUpdate):
    """Service function to update a user's information"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    # Update user attributes
    if user_data.display_name is not None:
        user.display_name = user_data.display_name
    
    # Update any other fields here when they're added to the schema
    
    db.commit()
    db.refresh(user)
    return user 