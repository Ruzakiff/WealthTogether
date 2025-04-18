from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.schemas.couples import CoupleCreate, CoupleResponse
from backend.app.services.couple_service import create_couple
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