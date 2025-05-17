from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timezone

from backend.app.schemas.transactions import TransactionCreate, TransactionResponse, TransactionCategorize
from backend.app.services.transaction_service import (
    create_transaction,
    get_transactions_by_account,
    get_user_transactions,
    categorize_transaction
)
from backend.app.database import get_db_session
from backend.app.models.models import BankAccount, LedgerEvent, LedgerEventType
from backend.app.schemas.allocation_rules import ExecuteRulesRequest
from backend.app.services.allocation_rule_service import execute_account_rules

router = APIRouter()

@router.post("/", response_model=TransactionResponse)
async def create_new_transaction(
    transaction_data: TransactionCreate, 
    db: Session = Depends(get_db_session)
):
    """
    Create a new transaction.
    
    - Links to a specific account
    - Can be manually created or from Plaid sync
    - Updates account balance for non-pending transactions
    """
    return create_transaction(db, transaction_data)

@router.get("/", response_model=List[TransactionResponse])
async def get_transactions(
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID (gets transactions from all user's accounts)"),
    start_date: Optional[date] = Query(None, description="Filter transactions on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter transactions on or before this date"),
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    limit: int = Query(100, le=500, description="Maximum number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
    db: Session = Depends(get_db_session)
):
    """
    Get transactions with various filters.
    
    - Can filter by account or user (one required)
    - Optional date range and category filtering
    - Results are paginated and sorted by date (newest first)
    """
    if not account_id and not user_id:
        raise HTTPException(status_code=400, detail="Either account_id or user_id must be provided")
    
    if account_id and user_id:
        raise HTTPException(status_code=400, detail="Provide either account_id or user_id, not both")
    
    if account_id:
        return get_transactions_by_account(db, account_id, start_date, end_date, limit, offset)
    else:  # user_id
        return get_user_transactions(db, user_id, start_date, end_date, category_id, limit, offset)

@router.post("/categorize", response_model=TransactionResponse)
async def categorize_transaction_endpoint(
    categorize_data: TransactionCategorize,
    user_id: str = Query(..., description="ID of the user performing the categorization"),
    db: Session = Depends(get_db_session)
):
    """
    Categorize a transaction.
    
    - Updates transaction's category
    - Creates a ledger event to track the change
    - User must own the account the transaction belongs to
    """
    return categorize_transaction(db, categorize_data, user_id)

@router.post("/simulate-deposit", response_model=Dict[str, Any])
async def simulate_deposit(
    deposit_data: Dict[str, Any],
    user_id: str = Query(..., description="ID of the user"),
    db: Session = Depends(get_db_session)
):
    """
    Simulate a deposit into an account and trigger any auto allocation rules.
    
    - For testing/demo purposes only
    - Simulates what would happen when a real deposit is detected
    - Executes all active rules for the account
    """
    account_id = deposit_data.get("account_id")
    amount = deposit_data.get("amount")
    
    if not account_id or not amount:
        raise HTTPException(status_code=400, detail="Account ID and amount are required")
    
    # Get the account and verify ownership
    account = db.query(BankAccount).filter(
        BankAccount.id == account_id,
        BankAccount.user_id == user_id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found or not owned by user")
    
    # Update account balance to simulate deposit
    account.balance += amount
    db.commit()
    
    # Create a ledger event for the deposit
    deposit_event = LedgerEvent(
        event_type=LedgerEventType.DEPOSIT,
        user_id=user_id,
        amount=amount,
        source_account_id=account_id,
        event_metadata={
            "description": deposit_data.get("description", "Simulated deposit")
        }
    )
    db.add(deposit_event)
    db.commit()
    
    # Execute auto allocation rules
    execute_request = ExecuteRulesRequest(
        account_id=account_id,
        deposit_amount=amount,
        manual_trigger=True
    )
    
    results = execute_account_rules(db, execute_request, user_id)
    
    # Calculate total allocated
    total_allocated = sum(item["amount"] for item in results if item["success"])
    
    return {
        "deposit_amount": amount,
        "rules_executed": len(results),
        "total_allocated": total_allocated,
        "rule_results": results
    } 