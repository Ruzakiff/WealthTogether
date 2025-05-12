from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.schemas.users import UserCreate, UserResponse, UserUpdate
from backend.app.services.user_service import create_user, get_user_by_id, get_all_users, update_user
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=UserResponse)
async def create_user_route(user_data: UserCreate, db: Session = Depends(get_db_session)):
    """
    Create a new user account.
    
    - Checks if user with email already exists
    - Creates new user in database
    - Returns user object with user_id
    """
    return create_user(db, user_data)

@router.get("/", response_model=List[UserResponse])
async def get_users_route(db: Session = Depends(get_db_session)):
    """
    Get all users.
    
    - Returns list of all users in the system
    """
    return get_all_users(db)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_route(user_id: str, db: Session = Depends(get_db_session)):
    """
    Get a specific user by ID.
    
    - Returns the user object if found
    - Returns 404 if user not found
    """
    return get_user_by_id(db, user_id)

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user_route(user_id: str, user_data: UserUpdate, db: Session = Depends(get_db_session)):
    """
    Update a user's information.
    
    - Updates the specified user fields
    - Returns the updated user object
    - Returns 404 if user not found
    """
    return update_user(db, user_id, user_data) 