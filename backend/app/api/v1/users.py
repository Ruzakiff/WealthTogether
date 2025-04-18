from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.schemas.users import UserCreate, UserResponse
from backend.app.services.user_service import create_user
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