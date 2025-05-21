import pytest
from fastapi import status, HTTPException
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
from uuid import uuid4
import json

from backend.app.models.models import (
    User, Couple, Category, Budget, Transaction, LedgerEvent, 
    LedgerEventType, ApprovalSettings, ApprovalStatus, ApprovalActionType, PendingApproval
)
from backend.app.schemas.budgets import BudgetCreate, BudgetUpdate
from backend.app.services.budget_service import (
    create_budget, 
    get_budgets, 
    get_budget_spending, 
    get_all_budgets_spending, 
    update_budget, 
    delete_budget
)


# Helper function to handle date serialization
def date_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# Create a patched JSON dumps function that uses our custom serializer
def serialize_json(obj, *args, **kwargs):
    """Serialize an object to JSON with custom date handling"""
    return json.dumps(obj, default=date_serializer, *args, **kwargs)


# Service layer tests
@patch('backend.app.services.budget_service.check_approval_required')
def test_create_budget(mock_check_approval, db_session: Session, test_couple, test_user, test_category):
    """Test creating a budget"""
    # Configure mock to bypass approval check
    mock_check_approval.return_value = False
    
    budget_data = BudgetCreate(
        couple_id=test_couple.id,
        category_id=test_category.id,
        amount=500.00,
        period="monthly",
        start_date=date.today(),
        created_by=test_user.id
    )
    
    budget = create_budget(db_session, budget_data)
    
    assert budget.id is not None
    assert budget.couple_id == test_couple.id
    assert budget.category_id == test_category.id
    assert budget.amount == 500.00
    assert budget.period == "monthly"

    # Verify ledger event was created
    event = db_session.query(LedgerEvent).filter(
        LedgerEvent.event_type == LedgerEventType.SYSTEM
    ).order_by(LedgerEvent.timestamp.desc()).first()
    
    assert event is not None
    assert event.event_metadata.get("action") == "budget_created"
    assert event.event_metadata.get("budget_id") == str(budget.id)


@patch('backend.app.services.budget_service.check_approval_required')
@patch('backend.app.services.budget_service.create_pending_approval')
def test_create_budget_with_approval(mock_create_approval, mock_check_approval, db_session: Session, test_couple, test_user, test_category):
    """Test creating a budget that requires approval"""
    # Configure mock to require approval
    mock_check_approval.return_value = True
    
    # Mock the approval creation response
    mock_approval = MagicMock()
    mock_approval.id = str(uuid4())
    mock_create_approval.return_value = mock_approval
    
    budget_data = BudgetCreate(
        couple_id=test_couple.id,
        category_id=test_category.id,
        amount=1500.00,  # High amount to trigger approval
        period="monthly",
        start_date=date.today(),
        created_by=test_user.id
    )
    
    result = create_budget(db_session, budget_data)
    
    # Should return a dict with approval info
    assert isinstance(result, dict)
    assert result["status"] == "pending_approval"
    assert result["message"] == "Budget creation requires partner approval"
    assert "approval_id" in result
    
    # Verify the create_pending_approval was called
    mock_create_approval.assert_called_once()
    
    # Verify no budget was created
    budget_count = db_session.query(Budget).filter(
        Budget.couple_id == test_couple.id,
        Budget.category_id == test_category.id
    ).count()
    assert budget_count == 0


def test_get_budgets(db_session: Session, test_couple, test_category, test_user):
    """Test retrieving all budgets for a couple"""
    # Patch to bypass approval check
    with patch('backend.app.services.budget_service.check_approval_required', return_value=False):
        # Create multiple budgets
        create_budget(db_session, BudgetCreate(
            couple_id=test_couple.id,
            category_id=test_category.id,
            amount=300.00,
            period="monthly",
            start_date=date.today(),
            created_by=test_user.id
        ))
        
        # Create another category and budget
        category2 = Category(name="Entertainment")
        db_session.add(category2)
        db_session.commit()
        
        create_budget(db_session, BudgetCreate(
            couple_id=test_couple.id,
            category_id=category2.id,
            amount=200.00,
            period="monthly",
            start_date=date.today(),
            created_by=test_user.id
        ))
        
        # Retrieve budgets
        budgets = get_budgets(db_session, test_couple.id)
        
        assert len(budgets) == 2
        assert budgets[0].couple_id == test_couple.id
        assert budgets[1].couple_id == test_couple.id


@patch('backend.app.services.budget_service.check_approval_required')
def test_update_budget(mock_check_approval, db_session: Session, test_budget, test_user):
    """Test updating a budget"""
    # Configure mock to bypass approval check
    mock_check_approval.return_value = False
    
    update_data = BudgetUpdate(
        amount=600.00,
        period="weekly",
        previous_amount=test_budget.amount,
        updated_by=test_user.id
    )
    
    updated_budget = update_budget(db_session, test_budget.id, update_data)
    
    assert updated_budget.amount == 600.00
    assert updated_budget.period == "weekly"
    
    # Verify ledger event was created
    event = db_session.query(LedgerEvent).filter(
        LedgerEvent.event_type == LedgerEventType.SYSTEM
    ).order_by(LedgerEvent.timestamp.desc()).first()
    
    assert event is not None
    assert event.event_metadata.get("action") == "budget_updated"
    assert event.event_metadata.get("budget_id") == str(test_budget.id)


@patch('backend.app.services.budget_service.check_approval_required')
def test_update_budget_with_approval(mock_check_approval, db_session: Session, test_budget, test_user):
    """Test updating a budget that requires approval"""
    # Configure mock to require approval
    mock_check_approval.return_value = True
    
    update_data = BudgetUpdate(
        amount=1000.00,  # Big change that would trigger approval
        period="weekly",
        previous_amount=test_budget.amount,
        updated_by=test_user.id
    )
    
    result = update_budget(db_session, test_budget.id, update_data)
    
    # Should return a dict with approval info
    assert isinstance(result, dict)
    assert result["status"] == "pending_approval"
    assert result["message"] == "Budget update requires partner approval"
    assert "approval_id" in result

    # Verify budget was not updated
    db_session.refresh(test_budget)
    assert test_budget.amount != 1000.00  # Should still have original value


@patch('backend.app.services.budget_service.check_approval_required')
def test_delete_budget(mock_check_approval, db_session: Session, test_budget, test_user):
    """Test deleting a budget"""
    result = delete_budget(db_session, test_budget.id, test_user.id)
    
    assert result["success"] is True
    
    # Verify budget was deleted
    budget = db_session.query(Budget).filter(Budget.id == test_budget.id).first()
    assert budget is None
    
    # Verify ledger event was created
    event = db_session.query(LedgerEvent).filter(
        LedgerEvent.event_type == LedgerEventType.SYSTEM
    ).order_by(LedgerEvent.timestamp.desc()).first()
    
    assert event is not None
    assert event.event_metadata.get("action") == "budget_deleted"
    assert event.event_metadata.get("budget_id") == str(test_budget.id)


@patch('backend.app.services.budget_service.check_approval_required')
def test_budget_spending(mock_check_approval, db_session: Session, test_budget, test_category):
    """Test budget spending analysis"""
    # Create transactions
    today = datetime.now().date()
    
    # Add multiple transactions
    transaction1 = Transaction(
        account_id=str(uuid4()),
        amount=50.0,
        description="Grocery store",
        date=today,
        category_id=test_category.id
    )
    
    transaction2 = Transaction(
        account_id=str(uuid4()),
        amount=100.0,
        description="Supermarket",
        date=today,
        category_id=test_category.id
    )
    
    transaction3 = Transaction(
        account_id=str(uuid4()),
        amount=150.0,
        description="Wholesale club",
        date=today,
        category_id=test_category.id
    )
    
    db_session.add_all([transaction1, transaction2, transaction3])
    db_session.commit()
    
    # Get spending analysis
    now = datetime.now()
    analysis = get_budget_spending(db_session, test_budget.id, now.month, now.year)
    
    assert analysis["budget_id"] == test_budget.id
    assert analysis["category_id"] == test_category.id
    assert analysis["total_spent"] == 300.0  # 50 + 100 + 150
    assert analysis["remaining"] == test_budget.amount - 300.0
    assert analysis["percent_used"] == (300.0 / test_budget.amount) * 100


def test_all_budgets_spending(db_session: Session, test_couple, test_user):
    """Test getting spending analysis for all budgets"""
    # Create categories
    category1 = Category(name="Groceries")
    category2 = Category(name="Entertainment")
    db_session.add_all([category1, category2])
    db_session.commit()
    
    # Create budgets
    budget1 = create_budget(db_session, BudgetCreate(
        couple_id=test_couple.id,
        category_id=category1.id,
        amount=400.00,
        period="monthly",
        start_date=date.today(),
        created_by=test_user.id
    ))
    
    budget2 = create_budget(db_session, BudgetCreate(
        couple_id=test_couple.id,
        category_id=category2.id,
        amount=200.00,
        period="monthly",
        start_date=date.today(),
        created_by=test_user.id
    ))
    
    # Create transactions for each category
    today = datetime.now().date()
    
    transaction1 = Transaction(
        account_id=str(uuid4()),
        amount=150.0,
        description="Grocery shopping",
        date=today,
        category_id=category1.id
    )
    
    transaction2 = Transaction(
        account_id=str(uuid4()),
        amount=75.0,
        description="Movie tickets",
        date=today,
        category_id=category2.id
    )
    
    db_session.add_all([transaction1, transaction2])
    db_session.commit()
    
    # Get all budgets analysis
    now = datetime.now()
    analyses = get_all_budgets_spending(db_session, test_couple.id, now.month, now.year)
    
    assert len(analyses) == 2
    
    # Find the right analysis for each budget
    grocery_analysis = next((a for a in analyses if a["category_name"] == "Groceries"), None)
    entertainment_analysis = next((a for a in analyses if a["category_name"] == "Entertainment"), None)
    
    assert grocery_analysis is not None
    assert entertainment_analysis is not None
    
    assert grocery_analysis["total_spent"] == 150.0
    assert grocery_analysis["percent_used"] == (150.0 / 400.0) * 100
    
    assert entertainment_analysis["total_spent"] == 75.0
    assert entertainment_analysis["percent_used"] == (75.0 / 200.0) * 100


# API layer tests
@patch('backend.app.services.budget_service.check_approval_required')
def test_create_budget_endpoint(mock_check_approval, client, test_couple, test_category, test_user):
    """Test POST /budgets endpoint"""
    # Configure mock to bypass approval check
    mock_check_approval.return_value = False
    
    response = client.post(
        "/api/v1/budgets/",
        json={
            "couple_id": str(test_couple.id),
            "category_id": str(test_category.id),
            "amount": 500.00,
            "period": "monthly",
            "start_date": date.today().isoformat(),
            "created_by": str(test_user.id)
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["couple_id"] == str(test_couple.id)
    assert data["amount"] == 500.00


@patch('backend.app.services.budget_service.check_approval_required')
def test_create_budget_requiring_approval_endpoint(mock_check_approval, client, test_couple, test_user, test_category):
    """Test POST /budgets/ endpoint when approval is required"""
    # Configure mock to require approval
    mock_check_approval.return_value = True
    
    # Use today's date as a string to avoid serialization issues
    today_str = date.today().isoformat()
    
    response = client.post(
        "/api/v1/budgets/",
        json={
            "couple_id": str(test_couple.id),
            "category_id": str(test_category.id),
            "amount": 1500.00,  # High amount that would trigger approval
            "period": "monthly",
            "start_date": today_str,
            "created_by": str(test_user.id)
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "pending_approval"
    assert "approval_id" in data


@patch('backend.app.services.budget_service.check_approval_required')
def test_get_budgets_endpoint(mock_check_approval, client, test_couple, test_category, test_user, db_session):
    """Test GET /budgets endpoint"""
    # Configure mock to bypass approval check
    mock_check_approval.return_value = False
    
    # Create a budget first
    create_budget(db_session, BudgetCreate(
        couple_id=test_couple.id,
        category_id=test_category.id,
        amount=300.00,
        period="monthly",
        start_date=date.today(),
        created_by=test_user.id
    ))
    
    # Test the endpoint
    response = client.get(f"/api/v1/budgets/?couple_id={test_couple.id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["couple_id"] == str(test_couple.id)
    assert data[0]["amount"] == 300.00


@patch('backend.app.services.budget_service.check_approval_required')
def test_budget_analysis_endpoint(mock_check_approval, client, test_budget, test_category, db_session):
    """Test GET /budgets/{budget_id}/analysis endpoint"""
    # Create a transaction
    today = datetime.now().date()
    transaction = Transaction(
        account_id=str(uuid4()),
        amount=100.0,
        description="Test transaction",
        date=today,
        category_id=test_category.id
    )
    db_session.add(transaction)
    db_session.commit()
    
    # Test the endpoint
    now = datetime.now()
    response = client.get(
        f"/api/v1/budgets/{test_budget.id}/analysis?month={now.month}&year={now.year}"
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["budget_id"] == str(test_budget.id)
    assert data["total_spent"] == 100.0
    assert data["remaining"] == test_budget.amount - 100.0


@patch('backend.app.services.budget_service.check_approval_required')
def test_all_budgets_analysis_endpoint(mock_check_approval, client, test_couple, test_category, test_user, db_session):
    """Test GET /budgets/analysis endpoint"""
    # Configure mock to bypass approval check
    mock_check_approval.return_value = False
    
    # Create a budget
    create_budget(db_session, BudgetCreate(
        couple_id=test_couple.id,
        category_id=test_category.id,
        amount=300.00,
        period="monthly",
        start_date=date.today(),
        created_by=test_user.id
    ))
    
    # Create a transaction
    today = datetime.now().date()
    transaction = Transaction(
        account_id=str(uuid4()),
        amount=75.0,
        description="Test transaction",
        date=today,
        category_id=test_category.id
    )
    db_session.add(transaction)
    db_session.commit()
    
    # Test the endpoint
    now = datetime.now()
    response = client.get(
        f"/api/v1/budgets/analysis?couple_id={test_couple.id}&month={now.month}&year={now.year}"
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["total_spent"] == 75.0
    assert data[0]["percent_used"] == (75.0 / 300.0) * 100


@patch('backend.app.services.budget_service.check_approval_required')
def test_update_budget_endpoint(mock_check_approval, client, test_budget, test_user):
    """Test PUT /budgets/{budget_id} endpoint"""
    # Configure mock to bypass approval check
    mock_check_approval.return_value = False
    
    response = client.put(
        f"/api/v1/budgets/{test_budget.id}",
        json={
            "amount": 700.00,
            "period": "biweekly",
            "updated_by": str(test_user.id),
            "previous_amount": 500.00
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["amount"] == 700.00
    assert data["period"] == "biweekly"


@patch('backend.app.services.budget_service.check_approval_required')
def test_update_budget_requiring_approval_endpoint(mock_check_approval, client, test_budget, test_user):
    """Test PUT /budgets/{budget_id} endpoint when approval is required"""
    # Configure mock to require approval
    mock_check_approval.return_value = True
    
    response = client.put(
        f"/api/v1/budgets/{test_budget.id}",
        json={
            "amount": 1500.00,  # Big increase that would trigger approval
            "period": "biweekly",
            "updated_by": str(test_user.id),
            "previous_amount": 500.00
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "pending_approval"
    assert "approval_id" in data


@patch('backend.app.services.budget_service.check_approval_required')
def test_delete_budget_endpoint(mock_check_approval, client, test_budget, test_user):
    """Test DELETE /budgets/{budget_id} endpoint"""
    response = client.delete(
        f"/api/v1/budgets/{test_budget.id}?user_id={test_user.id}"
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True


def test_create_budget_invalid_category(client, test_couple, test_user):
    """Test creating a budget with invalid category"""
    response = client.post(
        "/api/v1/budgets/",
        json={
            "couple_id": str(test_couple.id),
            "category_id": "nonexistent-category-id",
            "amount": 500.00,
            "period": "monthly",
            "start_date": date.today().isoformat(),
            "created_by": str(test_user.id)
        }
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Category not found" in response.json()["detail"]


@patch('backend.app.services.budget_service.check_approval_required')
def test_budget_with_zero_spending(mock_check_approval, client, test_budget, db_session):
    """Test budget analysis with no spending"""
    now = datetime.now()
    response = client.get(
        f"/api/v1/budgets/{test_budget.id}/analysis?month={now.month}&year={now.year}"
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_spent"] == 0.0
    assert data["remaining"] == test_budget.amount
    assert data["percent_used"] == 0.0


@patch('backend.app.services.budget_service.check_approval_required')
def test_budget_with_non_current_month(mock_check_approval, client, test_budget, test_category, db_session):
    """Test budget analysis for past month"""
    # Create a transaction for last month
    last_month = datetime.now().replace(day=1) - timedelta(days=1)
    transaction = Transaction(
        account_id=str(uuid4()),
        amount=125.0,
        description="Last month transaction",
        date=last_month.date(),
        category_id=test_category.id
    )
    db_session.add(transaction)
    db_session.commit()
    
    # Get analysis for last month
    response = client.get(
        f"/api/v1/budgets/{test_budget.id}/analysis?month={last_month.month}&year={last_month.year}"
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_spent"] == 125.0


# Fixtures
@pytest.fixture
def test_category(db_session):
    """Create a test category."""
    category = Category(
        id=str(uuid4()),
        name="Groceries"
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_budget(db_session, test_couple, test_category, test_user):
    """Create a test budget."""
    with patch('backend.app.services.budget_service.check_approval_required', return_value=False):
        budget_data = BudgetCreate(
            couple_id=test_couple.id,
            category_id=test_category.id,
            amount=500.00,
            period="monthly",
            start_date=date.today(),
            created_by=test_user.id
        )
        budget = create_budget(db_session, budget_data)
        return budget


@pytest.fixture
def test_approval_settings(db_session, test_couple):
    """Create test approval settings with high thresholds to bypass approvals."""
    settings = ApprovalSettings(
        couple_id=test_couple.id,
        enabled=True,
        budget_creation_threshold=5000.0,  # Set high to bypass normal approvals
        budget_update_threshold=2000.0,
        goal_allocation_threshold=5000.0,
        goal_reallocation_threshold=3000.0,
        auto_rule_threshold=3000.0,
        approval_expiration_hours=72,
        notify_on_create=True,
        notify_on_resolve=True
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    return settings 