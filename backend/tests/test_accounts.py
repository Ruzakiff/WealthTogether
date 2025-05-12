import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status
from uuid import uuid4

from backend.app.services.account_service import create_bank_account, get_user_accounts, get_couple_accounts, adjust_account_balance
from backend.app.schemas.accounts import BankAccountCreate, AccountAdjustment
from backend.app.database import get_db_session
from backend.app.models.models import BankAccount

# Service layer tests
def test_create_account_service(db_session, test_user):
    """Test account creation at the service layer"""
    account_data = BankAccountCreate(
        user_id=test_user.id,
        name="Service Test Account",
        balance=5000.0,
        is_manual=True,
        institution_name="Test Bank"
    )
    account = create_bank_account(db_session, account_data)
    
    assert account.id is not None
    assert account.user_id == test_user.id
    assert account.name == "Service Test Account"
    assert account.balance == 5000.0

def test_create_account_nonexistent_user(db_session):
    """Test that creating an account for a non-existent user raises an error"""
    account_data = BankAccountCreate(
        user_id="nonexistent-id",
        name="Invalid Account",
        balance=1000.0,
        is_manual=True
    )
    
    with pytest.raises(Exception) as excinfo:
        create_bank_account(db_session, account_data)
    assert "not found" in str(excinfo.value)

def test_get_user_accounts(db_session, test_user, test_account):
    """Test retrieving accounts for a user"""
    # Create a second account for the same user
    from backend.app.models.models import BankAccount
    from uuid import uuid4
    
    second_account = BankAccount(
        id=str(uuid4()),
        user_id=test_user.id,
        name="Second Account",
        balance=2000.0,
        is_manual=True
    )
    db_session.add(second_account)
    db_session.commit()
    
    # Get accounts
    accounts = get_user_accounts(db_session, test_user.id)
    
    assert len(accounts) == 2
    account_names = [a.name for a in accounts]
    assert "Test Account" in account_names
    assert "Second Account" in account_names

def test_get_couple_accounts(db_session, test_couple, test_account):
    """Test retrieving accounts for a couple"""
    # Create an account for partner 2
    from backend.app.models.models import BankAccount
    from uuid import uuid4
    
    partner_account = BankAccount(
        id=str(uuid4()),
        user_id=test_couple.partner_2_id,
        name="Partner Account",
        balance=3000.0,
        is_manual=True
    )
    db_session.add(partner_account)
    db_session.commit()
    
    # Get accounts
    accounts = get_couple_accounts(db_session, test_couple.id)
    
    assert len(accounts) == 2
    account_names = [a.name for a in accounts]
    assert "Test Account" in account_names
    assert "Partner Account" in account_names

# API layer tests
def test_create_account_api(client, test_user):
    """Test account creation through the API"""
    response = client.post(
        "/api/v1/accounts/",
        json={
            "user_id": test_user.id,
            "name": "API Test Account",
            "balance": 7500.0,
            "is_manual": True,
            "institution_name": "API Bank"
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["name"] == "API Test Account"
    assert data["balance"] == 7500.0

def test_get_user_accounts_api(client, test_user, test_account):
    """Test getting user accounts through the API"""
    response = client.get(f"/api/v1/accounts/?user_id={test_user.id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 1
    assert any(account["name"] == "Test Account" for account in data)

def test_get_couple_accounts_api(client, test_couple, test_account):
    """Test getting couple accounts through the API"""
    # Create a partner account first
    from backend.app.models.models import BankAccount
    from uuid import uuid4
    
    # Get the database session
    db_session = next(client.app.dependency_overrides[get_db_session]())
    
    partner_account = BankAccount(
        id=str(uuid4()),
        user_id=test_couple.partner_2_id,
        name="API Partner Account",
        balance=4500.0,
        is_manual=True
    )
    db_session.add(partner_account)
    db_session.commit()
    
    response = client.get(f"/api/v1/accounts/?couple_id={test_couple.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

# New tests aligned with PRD requirements
def test_adjust_account_balance_service(db_session, test_account):
    """Test the account balance adjustment service"""
    initial_balance = test_account.balance
    adjustment_amount = 1500.0
    
    # Get user ID for the account
    user_id = test_account.user_id
    
    # Call the service function
    updated_account = adjust_account_balance(
        db_session, 
        test_account.id, 
        adjustment_amount, 
        user_id, 
        "Test adjustment via service"
    )
    
    # Verify the balance increased correctly
    assert updated_account.balance == initial_balance + adjustment_amount
    
    # Verify the account was updated in the database
    db_account = db_session.query(BankAccount).filter(BankAccount.id == test_account.id).first()
    assert db_account.balance == initial_balance + adjustment_amount

def test_adjust_account_balance_api(client, test_user, test_account):
    """Test adjusting an account balance through the API"""
    # Get the current balance from the database first
    db_session = next(client.app.dependency_overrides[get_db_session]())
    account = db_session.query(BankAccount).filter(BankAccount.id == test_account.id).first()
    initial_balance = account.balance
    
    adjustment_data = {
        "amount": 1000.0,
        "user_id": test_user.id,
        "reason": "Test adjustment"
    }
    
    response = client.post(
        f"/api/v1/accounts/{test_account.id}/adjust",
        json=adjustment_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == initial_balance + 1000.0

def test_account_validation_negative_balance(client, test_user):
    """Test that account creation validates against negative balances"""
    response = client.post(
        "/api/v1/accounts/",
        json={
            "user_id": test_user.id,
            "name": "Negative Balance Account",
            "balance": -100.0,  # Negative balance
            "is_manual": True
        }
    )
    
    # Should reject with validation error
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_negative_adjustment_validation(client, test_user, test_account):
    """Test that negative adjustments that would result in negative balances are rejected"""
    # Get current balance
    db_session = next(client.app.dependency_overrides[get_db_session]())
    account = db_session.query(BankAccount).filter(BankAccount.id == test_account.id).first()
    current_balance = account.balance
    
    # Try to decrease balance by more than its current value
    adjustment_data = {
        "amount": -(current_balance + 500.0),  # More than current balance
        "user_id": test_user.id,
        "reason": "This should fail"
    }
    
    response = client.post(
        f"/api/v1/accounts/{test_account.id}/adjust",
        json=adjustment_data
    )
    
    # Should be rejected
    assert response.status_code == 400
    assert "negative balance" in response.json()["detail"].lower()

# Placeholder for Phase 2.5 Plaid integration tests
@pytest.mark.skip(reason="Plaid integration not implemented yet - Phase 2.5")
def test_plaid_link_token(client, test_user):
    """Test generating a Plaid link token"""
    response = client.post(
        "/api/v1/plaid/link",
        json={"user_id": test_user.id}
    )
    
    assert response.status_code == 200
    assert "link_token" in response.json()

@pytest.mark.skip(reason="Plaid integration not implemented yet - Phase 2.5")
def test_plaid_exchange_token(client, test_user):
    """Test exchanging a Plaid public token for access tokens"""
    # This will be implemented in Phase 2.5
    response = client.post(
        "/api/v1/plaid/exchange",
        json={
            "user_id": test_user.id,
            "public_token": "mock_public_token",
            "metadata": {"accounts": [{"id": "mock_account_id", "name": "Checking Account"}]}
        }
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()

# Phase 3 functionality tests (to be implemented later)
@pytest.mark.skip(reason="Phase 3 functionality not implemented yet")
def test_calculate_account_surplus(client, test_couple, test_account):
    """Test calculating surplus funds across accounts"""
    # Will be implemented when the surplus endpoint is added 