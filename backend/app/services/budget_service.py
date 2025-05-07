from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from fastapi import HTTPException

from backend.app.models.models import Budget, Transaction, Category
from backend.app.schemas.budgets import BudgetCreate, BudgetUpdate

def create_budget(db: Session, budget: BudgetCreate) -> Budget:
    """Create a new budget for a category"""
    # Check if category exists
    category = db.query(Category).filter(Category.id == budget.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Create new budget
    db_budget = Budget(
        couple_id=budget.couple_id,
        category_id=budget.category_id,
        amount=budget.amount,
        period=budget.period,
        start_date=budget.start_date
    )
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget

def get_budgets(db: Session, couple_id: str) -> List[Budget]:
    """Get all budgets for a couple"""
    return db.query(Budget).filter(Budget.couple_id == couple_id).all()

def get_budget_spending(db: Session, budget_id: str, month: int = None, year: int = None) -> Dict[str, Any]:
    """Get spending against a specific budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Default to current month/year if not specified
    if month is None or year is None:
        now = datetime.now()
        month = month or now.month
        year = year or now.year
    
    # Query transactions for this category in the specified month
    transactions = db.query(Transaction).join(
        Category, Transaction.category_id == Category.id
    ).filter(
        Category.id == budget.category_id,
        extract('month', Transaction.date) == month,
        extract('year', Transaction.date) == year
    ).all()
    
    # Calculate total spending
    total_spent = sum(transaction.amount for transaction in transactions)
    
    # Calculate remaining budget
    remaining = budget.amount - total_spent
    
    # Calculate percentage used
    percent_used = (total_spent / budget.amount) * 100 if budget.amount > 0 else 0
    
    return {
        "budget_id": budget.id,
        "category_id": budget.category_id,
        "category_name": db.query(Category).filter(Category.id == budget.category_id).first().name,
        "amount": budget.amount,
        "total_spent": total_spent,
        "remaining": remaining,
        "percent_used": percent_used,
        "transactions_count": len(transactions),
        "period": budget.period,
        "month": month,
        "year": year
    }

def get_all_budgets_spending(db: Session, couple_id: str, month: int = None, year: int = None) -> List[Dict[str, Any]]:
    """Get spending for all budgets of a couple"""
    budgets = get_budgets(db, couple_id)
    
    results = []
    for budget in budgets:
        try:
            budget_spending = get_budget_spending(db, budget.id, month, year)
            results.append(budget_spending)
        except Exception as e:
            # Skip any budget with errors
            print(f"Error getting budget {budget.id}: {str(e)}")
            continue
    
    return results

def update_budget(db: Session, budget_id: str, budget_update: BudgetUpdate) -> Budget:
    """Update an existing budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Update fields
    for key, value in budget_update.dict(exclude_unset=True).items():
        setattr(budget, key, value)
    
    db.commit()
    db.refresh(budget)
    return budget

def delete_budget(db: Session, budget_id: str) -> Dict[str, bool]:
    """Delete a budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    db.delete(budget)
    db.commit()
    return {"success": True} 