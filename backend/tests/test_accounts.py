import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status

from backend.app.services.account_service import create_bank_account, get_user_accounts, get_couple_accounts
from backend.app.schemas.accounts import BankAccountCreate
from backend.app.database import get_db_session

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