from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Union
from datetime import date

from backend.app.database import get_db_session
from backend.app.schemas.budgets import BudgetCreate, BudgetInDB, BudgetUpdate
from backend.app.services.budget_service import (
    create_budget, get_budgets, get_budget_spending, 
    get_all_budgets_spending, update_budget, delete_budget
)

router = APIRouter()

@router.post("/", response_model=Union[BudgetInDB, Dict[str, Any]])
def create_budget_endpoint(
    budget_data: BudgetCreate,
    db: Session = Depends(get_db_session)
):
    """
    Create a new budget for a specific category.
    If the budget amount exceeds the approval threshold, a pending approval will be created.
    """
    result = create_budget(db, budget_data)
    
    # If it's a pending approval
    if isinstance(result, dict) and "status" in result and result["status"] == "pending_approval":
        return result
    
    # Otherwise, it's a budget
    return result

@router.get("/", response_model=List[BudgetInDB])
def get_budgets_endpoint(
    couple_id: str = Query(..., description="ID of the couple"),
    db: Session = Depends(get_db_session)
):
    """
    Get all budgets for a couple
    """
    return get_budgets(db, couple_id)

@router.get("/analysis", response_model=List[Dict[str, Any]])
def get_budgets_analysis_endpoint(
    couple_id: str = Query(..., description="ID of the couple"),
    month: int = Query(None, description="Month (1-12)"),
    year: int = Query(None, description="Year"),
    db: Session = Depends(get_db_session)
):
    """
    Get spending analysis for all budgets of a couple
    """
    return get_all_budgets_spending(db, couple_id, month, year)

@router.get("/{budget_id}/analysis", response_model=Dict[str, Any])
def get_budget_analysis_endpoint(
    budget_id: str,
    month: int = Query(None, description="Month (1-12)"),
    year: int = Query(None, description="Year"),
    db: Session = Depends(get_db_session)
):
    """
    Get spending analysis for a specific budget
    """
    return get_budget_spending(db, budget_id, month, year)

@router.put("/{budget_id}", response_model=Union[BudgetInDB, Dict[str, Any]])
def update_budget_endpoint(
    budget_id: str,
    budget_update: BudgetUpdate,
    db: Session = Depends(get_db_session)
):
    """
    Update an existing budget.
    If the change in budget amount exceeds the approval threshold, a pending approval will be created.
    """
    result = update_budget(db, budget_id, budget_update)
    
    # If it's a pending approval
    if isinstance(result, dict) and "status" in result and result["status"] == "pending_approval":
        return result
    
    # Otherwise, it's a budget
    return result

@router.delete("/{budget_id}", response_model=Dict[str, bool])
def delete_budget_endpoint(
    budget_id: str,
    user_id: str = Query(..., description="ID of the user performing the deletion"),
    db: Session = Depends(get_db_session)
):
    """
    Delete a budget
    """
    return delete_budget(db, budget_id, user_id) 