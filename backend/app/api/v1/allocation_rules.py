from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.app.schemas.allocation_rules import (
    AutoAllocationRuleCreate, 
    AutoAllocationRuleUpdate, 
    AutoAllocationRuleResponse, 
    ExecuteRulesRequest
)
from backend.app.services.allocation_rule_service import (
    create_allocation_rule, 
    get_rules_by_user, 
    update_allocation_rule, 
    delete_allocation_rule, 
    execute_rule,
    execute_account_rules
)
from backend.app.database import get_db_session
from backend.app.models.models import BankAccount, LedgerEvent, LedgerEventType

router = APIRouter()

@router.post("/", response_model=AutoAllocationRuleResponse)
async def create_rule(
    rule_data: AutoAllocationRuleCreate,
    db: Session = Depends(get_db_session)
):
    """
    Create a new automatic allocation rule.
    
    - Defines a percentage of funds to automatically allocate
    - Can trigger on deposit or schedule
    - Validates user owns the source account
    """
    return create_allocation_rule(db, rule_data)

@router.get("/", response_model=List[AutoAllocationRuleResponse])
async def get_user_rules(
    user_id: str = Query(..., description="ID of the user"),
    db: Session = Depends(get_db_session)
):
    """
    Get all allocation rules for a user.
    
    - Returns all rules with related account and goal names
    - Includes status and last execution time
    """
    return get_rules_by_user(db, user_id)

@router.put("/{rule_id}", response_model=AutoAllocationRuleResponse)
async def update_rule(
    rule_id: str,
    update_data: AutoAllocationRuleUpdate,
    user_id: str = Query(..., description="ID of the user"),
    db: Session = Depends(get_db_session)
):
    """
    Update an existing allocation rule.
    
    - Can update percentage, trigger type, or active status
    - Verifies the user owns the rule
    """
    return update_allocation_rule(db, rule_id, user_id, update_data)

@router.delete("/{rule_id}", response_model=Dict[str, Any])
async def delete_rule(
    rule_id: str,
    user_id: str = Query(..., description="ID of the user"),
    db: Session = Depends(get_db_session)
):
    """
    Delete an allocation rule.
    
    - Completely removes the rule
    - Verifies the user owns the rule
    """
    result = delete_allocation_rule(db, rule_id, user_id)
    return {"success": result, "rule_id": rule_id}

@router.post("/execute/{rule_id}", response_model=Dict[str, Any])
async def execute_single_rule(
    rule_id: str,
    deposit_amount: float = Query(None, description="Optional deposit amount to allocate from"),
    db: Session = Depends(get_db_session)
):
    """
    Manually execute a single allocation rule.
    
    - Immediately processes the allocation based on rule settings
    - Can specify a deposit amount or use current account balance
    """
    return execute_rule(db, rule_id, deposit_amount)

@router.post("/execute-account", response_model=List[Dict[str, Any]])
async def execute_rules_for_account(
    request: ExecuteRulesRequest,
    user_id: str = Query(..., description="ID of the user"),
    db: Session = Depends(get_db_session)
):
    """
    Execute all active rules for an account.
    
    - Processes all rules in sequence
    - Can specify a deposit amount (e.g. for a new paycheck deposit)
    - Returns results for each rule execution
    """
    return execute_account_rules(db, request, user_id)
