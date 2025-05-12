from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from backend.app.schemas.couples import CoupleCreate, CoupleResponse
from backend.app.services.couple_service import create_couple, get_couple_by_id, get_couples_by_user_id
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=CoupleResponse)
async def create_couple_route(couple_data: CoupleCreate, db: Session = Depends(get_db_session)):
    """
    Create a new couple relationship.
    
    - Links two users together in a financial partnership
    - Validates that both users exist
    - Checks that the relationship doesn't already exist
    """
    return create_couple(db, couple_data)

@router.get("/{couple_id}", response_model=CoupleResponse)
async def get_couple_route(couple_id: UUID, db: Session = Depends(get_db_session)):
    """
    Get a specific couple by ID.
    
    - Returns the couple object if found
    - Returns 404 if couple not found
    """
    return get_couple_by_id(db, str(couple_id))

@router.get("/user/{user_id}", response_model=List[CoupleResponse])
async def get_user_couples_route(user_id: str, db: Session = Depends(get_db_session)):
    """
    Get all couples for a specific user.
    
    - Returns list of all couple relationships the user is part of
    """
    return get_couples_by_user_id(db, user_id) 
