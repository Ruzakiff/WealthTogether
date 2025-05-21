from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from fastapi import HTTPException

from backend.app.models.models import Budget, Transaction, Category, LedgerEvent, Couple, ApprovalStatus, ApprovalActionType
from backend.app.schemas.budgets import BudgetCreate, BudgetUpdate
from backend.app.schemas.ledger import LedgerEventType
from backend.app.schemas.approvals import ApprovalCreate
from backend.app.services.approval_service import check_approval_required, create_pending_approval

def create_budget(db: Session, budget: BudgetCreate) -> Dict[str, Any]:
    """Create a new budget for a category"""
    # Check if category exists
    category = db.query(Category).filter(Category.id == budget.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if approval is required
    if check_approval_required(db, budget.couple_id, ApprovalActionType.BUDGET_CREATE, amount=budget.amount):
        # Create approval request
        budget_dict = budget.dict() if hasattr(budget, 'dict') else budget.model_dump()
        
        # Serialize date objects to strings
        if 'start_date' in budget_dict and isinstance(budget_dict['start_date'], date):
            budget_dict['start_date'] = budget_dict['start_date'].isoformat()
            
        approval_data = ApprovalCreate(
            couple_id=budget.couple_id,
            initiated_by=budget.created_by,
            action_type=ApprovalActionType.BUDGET_CREATE,
            payload=budget_dict
        )
        approval = create_pending_approval(db, approval_data)
        return {
            "status": "pending_approval",
            "message": "Budget creation requires partner approval",
            "approval_id": approval.id
        }
    
    # If no approval required, create budget directly
    return create_budget_internal(db, budget.dict() if hasattr(budget, 'dict') else budget.model_dump())

def create_budget_internal(db: Session, budget_data: Dict[str, Any]) -> Budget:
    """Internal function to create budget once approved"""
    # Create new budget
    db_budget = Budget(
        couple_id=budget_data["couple_id"],
        category_id=budget_data["category_id"],
        amount=budget_data["amount"],
        period=budget_data["period"],
        start_date=budget_data["start_date"]
    )
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    
    # Create a ledger event
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=budget_data["amount"],
        user_id=budget_data["created_by"],
        event_metadata={
            "action": "budget_created",
            "category_id": str(db_budget.category_id),
            "budget_id": str(db_budget.id),
            "period": db_budget.period
        }
    )
    db.add(log_event)
    db.commit()
    
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

def update_budget(db: Session, budget_id: str, budget_update: BudgetUpdate) -> Union[Dict[str, Any], Budget]:
    """Update an existing budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Check if approval is required for the update (only when amount is being changed)
    if budget_update.amount is not None and budget_update.amount != budget.amount:
        # Get the couple_id from the budget
        couple_id = budget.couple_id
        
        # Check if the change requires approval
        # We're checking the absolute difference between new and old amount
        amount_difference = abs(budget_update.amount - budget.amount)
        if check_approval_required(db, couple_id, ApprovalActionType.BUDGET_UPDATE, amount=amount_difference):
            # Store the current budget data for the approval payload
            update_data = budget_update.dict(exclude_unset=True) if hasattr(budget_update, 'dict') else budget_update.model_dump(exclude_unset=True)
            update_data["budget_id"] = budget_id
            update_data["previous_amount"] = budget.amount
            
            # Serialize date objects to strings
            if 'start_date' in update_data and isinstance(update_data['start_date'], date):
                update_data['start_date'] = update_data['start_date'].isoformat()
            
            # Create approval request
            approval_data = ApprovalCreate(
                couple_id=couple_id,
                initiated_by=budget_update.updated_by,
                action_type=ApprovalActionType.BUDGET_UPDATE,
                payload=update_data
            )
            approval = create_pending_approval(db, approval_data)
            return {
                "status": "pending_approval",
                "message": "Budget update requires partner approval",
                "approval_id": approval.id
            }
    
    # If no approval required, update budget directly
    return update_budget_internal(db, budget_id, budget_update.dict(exclude_unset=True) if hasattr(budget_update, 'dict') else budget_update.model_dump(exclude_unset=True))

def update_budget_internal(db: Session, budget_id: str, update_data: Dict[str, Any]) -> Budget:
    """Internal function to update budget once approved"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Store previous amount before update
    previous_amount = budget.amount
    
    # Update fields
    for key, value in update_data.items():
        if key not in ['updated_by', 'previous_amount', 'budget_id']:  # Skip non-model fields
            setattr(budget, key, value)
    
    # Create and commit the ledger event
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=budget.amount,
        user_id=update_data.get('updated_by'),
        event_metadata={
            "action": "budget_updated",
            "budget_id": str(budget_id),  # Ensure it's a string
            "previous_amount": float(previous_amount),
            "new_amount": float(budget.amount)
        }
    )
    db.add(log_event)
    
    # Now commit the budget update and ledger event together
    db.commit()
    db.refresh(budget)
    return budget

def delete_budget(db: Session, budget_id: str, user_id: str) -> Dict[str, bool]:
    """Delete a budget"""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Create a ledger event before deleting the budget
    log_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=budget.amount,
        user_id=user_id,
        event_metadata={
            "action": "budget_deleted",
            "budget_id": str(budget_id),  # Ensure it's a string
            "category_id": str(budget.category_id),
            "period": budget.period
        }
    )
    db.add(log_event)
    
    # Commit the ledger event first
    db.commit()
    
    # Now delete the budget and commit again
    db.delete(budget)
    db.commit()
    return {"success": True} 