from typing import List, Optional, Literal
from uuid import UUID, uuid4
from datetime import datetime, date
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import (
    Column, String, Integer, DateTime, Float, Boolean, ForeignKey, Enum as PgEnum, JSON, Table, Date, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# --- ENUMS ---

class GoalType(str, Enum):
    EMERGENCY = "emergency"
    VACATION = "vacation"
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    CUSTOM = "custom"

class LedgerEventType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    ALLOCATION = "ALLOCATION"
    REALLOCATION = "REALLOCATION"
    CATEGORIZATION = "CATEGORIZATION"
    ADJUSTMENT = "ADJUSTMENT"  # For manual account adjustments
    SYSTEM = "SYSTEM"  # For system events like goal/budget creation

class Frequency(str, Enum):
    MONTHLY = "monthly"
    BIWEEKLY = "biweekly"
    IRREGULAR = "irregular"

class EntryType(str, Enum):
    REFLECTION = "reflection"
    CELEBRATION = "celebration"
    CONCERN = "concern"

class AllocationTrigger(str, Enum):
    DEPOSIT = "deposit"
    SCHEDULE = "schedule"

class JournalEntryType(str, Enum):
    REFLECTION = "reflection"
    CELEBRATION = "celebration"
    CONCERN = "concern"

# --- SQLALCHEMY MODELS ---

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    allocation_rules = relationship("AutoAllocationRule", back_populates="user")
    journal_entries = relationship("JournalEntry", back_populates="user")

class Couple(Base):
    __tablename__ = "couples"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    partner_1_id = Column(String, ForeignKey("users.id"))
    partner_2_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    journal_entries = relationship("JournalEntry", back_populates="couple")

class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    plaid_account_id = Column(String, nullable=True)
    name = Column(String)
    balance = Column(Float, default=0.0)
    institution_name = Column(String, nullable=True)
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    transactions = relationship("Transaction", back_populates="account")

class FinancialGoal(Base):
    __tablename__ = "financial_goals"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    couple_id = Column(String, ForeignKey("couples.id"))
    name = Column(String)
    target_amount = Column(Float)
    type = Column(PgEnum(GoalType), default=GoalType.CUSTOM)
    current_allocation = Column(Float, default=0.0)
    priority = Column(Integer, default=1)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    journal_entries = relationship("JournalEntry", back_populates="goal")

class AllocationMap(Base):
    __tablename__ = "goal_account_allocations"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    goal_id = Column(String, ForeignKey("financial_goals.id"))
    account_id = Column(String, ForeignKey("bank_accounts.id"))
    allocated_amount = Column(Float)

class LedgerEvent(Base):
    __tablename__ = "ledger_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    event_type = Column(PgEnum(LedgerEventType))
    amount = Column(Float)
    source_account_id = Column(String, ForeignKey("bank_accounts.id"), nullable=True)
    dest_goal_id = Column(String, ForeignKey("financial_goals.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_metadata = Column(JSON, nullable=True)

class SyncPrompt(Base):
    __tablename__ = "sync_prompts"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    couple_id = Column(String, ForeignKey("couples.id"))
    type = Column(String)
    triggered_by = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)

class GoalChangeLog(Base):
    __tablename__ = "goal_change_logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    goal_id = Column(String, ForeignKey("financial_goals.id"))
    user_id = Column(String, ForeignKey("users.id"))
    change_type = Column(String)
    notes = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DriftFlag(Base):
    __tablename__ = "drift_flags"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    couple_id = Column(String, ForeignKey("couples.id"))
    reason = Column(String)
    goal_id = Column(String, ForeignKey("financial_goals.id"), nullable=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)

class IncomeStream(Base):
    __tablename__ = "income_streams"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    amount = Column(Float)
    frequency = Column(PgEnum(Frequency))
    source = Column(String)
    start_date = Column(DateTime)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    couple_id = Column(String, ForeignKey("couples.id"))
    goal_id = Column(String, ForeignKey("financial_goals.id"), nullable=True)
    entry_type = Column(PgEnum(JournalEntryType))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_private = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="journal_entries")
    couple = relationship("Couple", back_populates="journal_entries")
    goal = relationship("FinancialGoal", back_populates="journal_entries")

class GoalReaction(Base):
    __tablename__ = "goal_reactions"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    goal_id = Column(String, ForeignKey("financial_goals.id"))
    reaction_type = Column(String)  # emoji or stamp identifier
    note = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False)
    parent_category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    icon = Column(String, nullable=True)
    plaid_category_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    parent_category = relationship("Category", remote_side=[id], backref="subcategories")
    transactions = relationship("Transaction", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String, ForeignKey("bank_accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    merchant_name = Column(String, nullable=True)
    date = Column(Date, nullable=False)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    is_pending = Column(Boolean, default=False)
    plaid_transaction_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    account = relationship("BankAccount", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

class PlaidItem(Base):
    __tablename__ = "plaid_items"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    access_token = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    institution_id = Column(String, nullable=True)
    institution_name = Column(String, nullable=True)
    cursor = Column(String, nullable=True)  # Store the cursor for incremental syncs
    last_sync_at = Column(DateTime, nullable=True)  # Track when we last synced
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="plaid_items")

class Budget(Base):
    __tablename__ = "budgets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    couple_id = Column(String, ForeignKey("couples.id"))
    category_id = Column(String, ForeignKey("categories.id"))
    amount = Column(Float, nullable=False)
    period = Column(String, nullable=False)  # monthly, weekly, etc.
    start_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    couple = relationship("Couple")

class AutoAllocationRule(Base):
    __tablename__ = "auto_allocation_rules"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    source_account_id = Column(String, ForeignKey("bank_accounts.id"))
    goal_id = Column(String, ForeignKey("financial_goals.id"))
    percent = Column(Float)  # percentage of deposit/available funds to allocate
    trigger = Column(String, default=AllocationTrigger.DEPOSIT)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_executed = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="allocation_rules")
    source_account = relationship("BankAccount")
    goal = relationship("FinancialGoal")
