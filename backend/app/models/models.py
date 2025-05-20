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

class ApprovalActionType(str, Enum):
    """Types of actions that can require approval"""
    BUDGET_CREATE = "budget_create"
    BUDGET_UPDATE = "budget_update"
    GOAL_CREATE = "goal_create"
    GOAL_UPDATE = "goal_update"
    ALLOCATION = "allocation"
    REALLOCATION = "reallocation"
    AUTO_RULE_CREATE = "auto_rule_create"
    AUTO_RULE_UPDATE = "auto_rule_update"

class ApprovalStatus(str, Enum):
    """Status of an approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELED = "canceled"

# --- SQLALCHEMY MODELS ---

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    allocation_rules = relationship("AutoAllocationRule", back_populates="user")
    journal_entries = relationship("JournalEntry", back_populates="user")
    goal_reactions = relationship("GoalReaction", back_populates="user")
    initiated_approvals = relationship("PendingApproval", foreign_keys="PendingApproval.initiated_by", back_populates="initiator")
    resolved_approvals = relationship("PendingApproval", foreign_keys="PendingApproval.resolved_by", back_populates="resolver")

class Couple(Base):
    __tablename__ = "couples"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    partner_1_id = Column(String, ForeignKey("users.id"))
    partner_2_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    journal_entries = relationship("JournalEntry", back_populates="couple")
    pending_approvals = relationship("PendingApproval", back_populates="couple")
    approval_settings = relationship("ApprovalSettings", back_populates="couple", uselist=False)

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
    
    # Relationships
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
    
    # Relationships
    journal_entries = relationship("JournalEntry", back_populates="goal")
    reactions = relationship("GoalReaction", back_populates="goal")

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
    reaction_type = Column(String)  # Could use an enum for standard reactions: "happy", "excited", "concerned", etc.
    note = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="goal_reactions")
    goal = relationship("FinancialGoal", back_populates="reactions")

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

class PendingApproval(Base):
    """Partner approval workflow for financial actions"""
    __tablename__ = "pending_approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    couple_id = Column(String, ForeignKey("couples.id"), nullable=False)
    initiated_by = Column(String, ForeignKey("users.id"), nullable=False)
    action_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, default=ApprovalStatus.PENDING.value)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, ForeignKey("users.id"), nullable=True)
    resolution_note = Column(String, nullable=True)
    
    # Relationships
    couple = relationship("Couple", back_populates="pending_approvals")
    initiator = relationship("User", foreign_keys=[initiated_by], back_populates="initiated_approvals")
    resolver = relationship("User", foreign_keys=[resolved_by], back_populates="resolved_approvals")

class ApprovalSettings(Base):
    """Settings for approval thresholds and behavior"""
    __tablename__ = "approval_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    couple_id = Column(String, ForeignKey("couples.id"), nullable=False, unique=True)
    enabled = Column(Boolean, default=True)
    
    # Thresholds
    budget_creation_threshold = Column(Float, default=500.0)
    budget_update_threshold = Column(Float, default=200.0)
    goal_allocation_threshold = Column(Float, default=500.0)
    goal_reallocation_threshold = Column(Float, default=300.0)
    auto_rule_threshold = Column(Float, default=300.0)
    
    # Configuration
    approval_expiration_hours = Column(Integer, default=72)  # Default: 3 days
    notify_on_create = Column(Boolean, default=True)
    notify_on_resolve = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    couple = relationship("Couple", back_populates="approval_settings")

class AutoAllocationRule(Base):
    """Automated fund distribution rules"""
    __tablename__ = "auto_allocation_rules"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    source_account_id = Column(String, ForeignKey("bank_accounts.id"), nullable=False)
    goal_id = Column(String, ForeignKey("financial_goals.id"), nullable=False)
    percent = Column(Float, nullable=False)  # Changed from 'percentage' to 'percent'
    trigger = Column(PgEnum(AllocationTrigger), default=AllocationTrigger.DEPOSIT)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_executed = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="allocation_rules")
    source_account = relationship("BankAccount")
    goal = relationship("FinancialGoal")
