from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional

from backend.app.models.models import Category
from backend.app.schemas.categories import CategoryCreate

def create_category(db: Session, category_data: CategoryCreate):
    """Service function to create a new category"""
    
    # If parent category is provided, verify it exists
    if category_data.parent_category_id:
        parent = db.query(Category).filter(Category.id == category_data.parent_category_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail=f"Parent category with id {category_data.parent_category_id} not found")
    
    # Create new category
    new_category = Category(
        name=category_data.name,
        parent_category_id=category_data.parent_category_id,
        icon=category_data.icon
    )
    
    # Add to database
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    
    return new_category

def get_all_categories(db: Session) -> List[Category]:
    """Get all categories"""
    return db.query(Category).all()

def get_top_level_categories(db: Session) -> List[Category]:
    """Get only top-level categories (those without parents)"""
    return db.query(Category).filter(Category.parent_category_id == None).all()

def get_category_by_id(db: Session, category_id: str) -> Optional[Category]:
    """Get a specific category by ID"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail=f"Category with id {category_id} not found")
    return category

def get_subcategories(db: Session, parent_id: str) -> List[Category]:
    """Get all subcategories for a specific parent category"""
    # Verify parent exists
    parent = db.query(Category).filter(Category.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail=f"Parent category with id {parent_id} not found")
    
    # Get all subcategories
    return db.query(Category).filter(Category.parent_category_id == parent_id).all() 