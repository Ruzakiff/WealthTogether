from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.schemas.categories import CategoryCreate, CategoryResponse
from backend.app.services.category_service import (
    create_category, 
    get_all_categories,
    get_top_level_categories,
    get_category_by_id,
    get_subcategories
)
from backend.app.database import get_db_session

router = APIRouter()

@router.post("/", response_model=CategoryResponse)
async def create_new_category(
    category_data: CategoryCreate, 
    db: Session = Depends(get_db_session)
):
    """
    Create a new transaction category.
    
    - Can be a top-level category or a subcategory
    - Used for transaction categorization and budget tracking
    """
    return create_category(db, category_data)

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    parent_id: Optional[str] = Query(None, description="Get subcategories of this parent"),
    top_level_only: bool = Query(False, description="Get only top-level categories"),
    db: Session = Depends(get_db_session)
):
    """
    Get transaction categories.
    
    - Returns all categories by default
    - Can filter to only top-level categories
    - Can get subcategories of a specific parent
    """
    if parent_id:
        return get_subcategories(db, parent_id)
    elif top_level_only:
        return get_top_level_categories(db)
    else:
        return get_all_categories(db)

@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get a specific category by ID.
    """
    return get_category_by_id(db, category_id) 