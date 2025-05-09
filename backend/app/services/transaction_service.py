from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from datetime import date, datetime, timedelta
from uuid import uuid4

from backend.app.models.models import Transaction, BankAccount, Category, LedgerEvent, LedgerEventType
from backend.app.schemas.transactions import TransactionCreate, TransactionCategorize

def create_transaction(db: Session, transaction: TransactionCreate):
    """
    Create a new transaction record from Plaid data
    """
    # Create the Transaction record directly without using LedgerEvent
    db_transaction = Transaction(
        id=str(uuid4()),
        account_id=transaction.account_id,
        amount=transaction.amount,
        description=transaction.description,
        merchant_name=transaction.merchant_name,
        date=transaction.date,
        category_id=transaction.category_id,
        is_pending=transaction.is_pending,
        plaid_transaction_id=transaction.plaid_transaction_id
    )
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    # Create corresponding ledger event
    event_type = LedgerEventType.DEPOSIT if transaction.amount > 0 else LedgerEventType.WITHDRAWAL
    
    # Get the user_id from the account
    account = db.query(BankAccount).filter(BankAccount.id == transaction.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {transaction.account_id} not found")
    
    log_event = LedgerEvent(
        event_type=event_type,
        amount=abs(transaction.amount),  # Ledger amounts should be positive
        source_account_id=transaction.account_id,
        user_id=account.user_id,
        event_metadata={
            "transaction_id": db_transaction.id,
            "description": transaction.description,
            "merchant_name": transaction.merchant_name,
            "is_pending": transaction.is_pending
        }
    )
    db.add(log_event)
    db.commit()
    
    return db_transaction

def get_transactions_by_account(db: Session, account_id: str, 
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None,
                               limit: int = 100,
                               offset: int = 0) -> List[Transaction]:
    """Get transactions for a specific account with optional date filtering"""
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {account_id} not found")
    
    # Build query
    query = db.query(Transaction).filter(Transaction.account_id == account_id)
    
    # Add date filters if provided
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    
    # Return with pagination, sorted by date
    return query.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

def get_user_transactions(db: Session, user_id: str,
                         start_date: Optional[date] = None,
                         end_date: Optional[date] = None,
                         category_id: Optional[str] = None,
                         limit: int = 100,
                         offset: int = 0) -> List[Transaction]:
    """Get transactions for all accounts owned by a user"""
    
    # Get all accounts for this user
    accounts = db.query(BankAccount).filter(BankAccount.user_id == user_id).all()
    if not accounts:
        raise HTTPException(status_code=404, detail=f"No accounts found for user with id {user_id}")
    
    account_ids = [account.id for account in accounts]
    
    # Build query
    query = db.query(Transaction).filter(Transaction.account_id.in_(account_ids))
    
    # Add additional filters
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    
    # Return with pagination, sorted by date
    return query.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

def categorize_transaction(db: Session, categorize_data: TransactionCategorize, user_id: str):
    """Categorize a transaction"""
    
    # Get the transaction
    transaction = db.query(Transaction).filter(Transaction.id == categorize_data.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction with id {categorize_data.transaction_id} not found")
    
    # Verify the category exists
    category = db.query(Category).filter(Category.id == categorize_data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail=f"Category with id {categorize_data.category_id} not found")
    
    # Verify user owns the account this transaction belongs to
    account = db.query(BankAccount).filter(BankAccount.id == transaction.account_id).first()
    if account.user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to categorize this transaction")
    
    # Update category
    old_category_id = transaction.category_id
    transaction.category_id = categorize_data.category_id
    db.commit()
    db.refresh(transaction)
    
    # Log the change
    log_event = LedgerEvent(
        event_type=LedgerEventType.CATEGORIZATION,
        amount=transaction.amount,
        source_account_id=transaction.account_id,
        user_id=user_id,
        event_metadata={
            "transaction_id": transaction.id,
            "old_category_id": old_category_id,
            "new_category_id": categorize_data.category_id
        }
    )
    db.add(log_event)
    db.commit()
    
    return transaction 