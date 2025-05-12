from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.app.models.models import Couple, User
from backend.app.schemas.couples import CoupleCreate

def create_couple(db: Session, couple_data: CoupleCreate):
    """Service function to create a new couple relationship"""
    
    # Verify both users exist
    partner_1 = db.query(User).filter(User.id == couple_data.partner_1_id).first()
    if not partner_1:
        raise HTTPException(status_code=404, detail=f"User with id {couple_data.partner_1_id} not found")
    
    partner_2 = db.query(User).filter(User.id == couple_data.partner_2_id).first()
    if not partner_2:
        raise HTTPException(status_code=404, detail=f"User with id {couple_data.partner_2_id} not found")
    
    # Check if a couple with these partners already exists
    existing_couple = db.query(Couple).filter(
        ((Couple.partner_1_id == couple_data.partner_1_id) & (Couple.partner_2_id == couple_data.partner_2_id)) |
        ((Couple.partner_1_id == couple_data.partner_2_id) & (Couple.partner_2_id == couple_data.partner_1_id))
    ).first()
    
    if existing_couple:
        raise HTTPException(status_code=400, detail="A couple relationship already exists with these partners")
    
    # Create new couple
    new_couple = Couple(
        partner_1_id=couple_data.partner_1_id,
        partner_2_id=couple_data.partner_2_id
    )
    
    # Add to database
    db.add(new_couple)
    db.commit()
    db.refresh(new_couple)
    
    return new_couple

def get_couple_by_id(db: Session, couple_id: str):
    """Service function to get a couple by ID"""
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    return couple

def get_couples_by_user_id(db: Session, user_id: str):
    """Service function to get all couples a user belongs to"""
    couples = db.query(Couple).filter(
        (Couple.partner_1_id == user_id) | (Couple.partner_2_id == user_id)
    ).all()
    return couples 