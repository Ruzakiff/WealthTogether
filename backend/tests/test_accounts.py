import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status
from uuid import uuid4
from unittest.mock import patch, MagicMock

from backend.app.services.account_service import create_bank_account, get_user_accounts, get_couple_accounts, adjust_account_balance
from backend.app.schemas.accounts import BankAccountCreate, AccountAdjustment
from backend.app.database import get_db_session
from backend.app.models.models import BankAccount, PlaidItem

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

# Modified Plaid integration tests
@patch('backend.app.services.plaid_service.client.link_token_create')
def test_plaid_link_token(mock_link_token_create, client, test_user):
    """Test generating a Plaid Link token"""
    # Mock the Plaid API response
    mock_response = {
        'link_token': 'test-link-token-123',
        'request_id': 'request-id-123'
    }
    mock_link_token_create.return_value = mock_response
    
    response = client.post(
        "/api/v1/plaid/link",
        json={"user_id": test_user.id}
    )
    
    assert response.status_code == 200
    assert "link_token" in response.json()
    assert response.json()["link_token"] == "test-link-token-123"

@patch('backend.app.services.plaid_service.client.item_public_token_exchange')
@patch('backend.app.services.plaid_service.client.accounts_get')
@patch('backend.app.services.plaid_service.sync_transactions')
def test_plaid_exchange_token(mock_sync_transactions, mock_accounts_get, mock_exchange, client, test_user):
    """Test exchanging a Plaid public token for access tokens"""
    # Mock the Plaid API responses
    mock_exchange.return_value = {
        'access_token': 'test-access-token',
        'item_id': 'test-item-id',
        'request_id': 'test-request-id'
    }
    
    mock_accounts_get.return_value = {
        'accounts': [
            {
                'account_id': 'mock_account_id',
                'name': 'Checking Account',
                'balances': {'current': 1000.0},
                'type': 'depository'
            }
        ]
    }
    
    mock_sync_transactions.return_value = {
        'status': 'success',
        'added': 5,
        'modified': 0,
        'removed': 0
    }
    
    response = client.post(
        "/api/v1/plaid/exchange",
        json={
            "user_id": test_user.id,
            "public_token": "mock_public_token",
            "metadata": {
                "institution": {
                    "institution_id": "ins_123",
                    "name": "Test Bank"
                },
                "accounts": [{"id": "mock_account_id", "name": "Checking Account"}]
            }
        }
    )
    
    assert response.status_code == 200
    assert "accounts" in response.json()
    # Verify an account was created
    accounts = response.json()["accounts"]
    assert len(accounts) > 0
    assert accounts[0]["name"] == "Checking Account"

@patch('backend.app.services.plaid_service.client.accounts_get')
@patch('backend.app.services.plaid_service.sync_transactions')
def test_transactions_sync(mock_sync_transactions, mock_accounts_get, client, test_user, db_session):
    """Test manual transaction sync endpoint"""
    # Create a plaid item for the test user
    plaid_item = PlaidItem(
        user_id=test_user.id,
        access_token="test-access-token",
        item_id="test-item-id",
        institution_id="ins_123",
        institution_name="Test Bank"
    )
    db_session.add(plaid_item)
    
    # Create a plaid-linked account
    plaid_account = BankAccount(
        user_id=test_user.id,
        name="Plaid Test Account",
        balance=1000.0,
        is_manual=False,
        plaid_account_id="mock_account_id",
        institution_name="Test Bank"
    )
    db_session.add(plaid_account)
    db_session.commit()
    
    # Mock Plaid API responses
    mock_accounts_get.return_value = {
        'accounts': [
            {
                'account_id': 'mock_account_id',
                'name': 'Plaid Test Account'
            }
        ]
    }
    
    mock_sync_transactions.return_value = {
        'status': 'success',
        'added': 3,
        'modified': 1, 
        'removed': 0
    }
    
    response = client.post(
        "/api/v1/plaid/transactions/sync",
        json={"user_id": test_user.id}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "sync_results" in response.json()

# Phase 3 functionality tests (to be implemented later)
@pytest.mark.skip(reason="Phase 3 functionality not implemented yet")
def test_calculate_account_surplus(client, test_couple, test_account):
    """Test calculating surplus funds across accounts"""
    # Will be implemented when the surplus endpoint is added

# Add these new edge case tests to the end of your test file

def test_unauthorized_account_adjustment(client, test_user, db_session):
    """Test that a user cannot adjust another user's account"""
    # Create a second user
    from backend.app.models.models import User
    from uuid import uuid4
    
    second_user = User(
        id=str(uuid4()),
        email="second@example.com",
        display_name="Second User"
    )
    db_session.add(second_user)
    
    # Create an account for the second user
    second_account = BankAccount(
        id=str(uuid4()),
        user_id=second_user.id,
        name="Second User Account",
        balance=3000.0,
        is_manual=True
    )
    db_session.add(second_account)
    db_session.commit()
    
    # Try to adjust the second user's account with test_user's credentials
    adjustment_data = {
        "amount": 500.0,
        "user_id": test_user.id,  # First user trying to adjust second user's account
        "reason": "Unauthorized adjustment"
    }
    
    response = client.post(
        f"/api/v1/accounts/{second_account.id}/adjust",
        json=adjustment_data
    )
    
    # Should be rejected with 403 Forbidden
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()

def test_get_nonexistent_account(client, test_user):
    """Test getting accounts for a non-existent user"""
    response = client.get("/api/v1/accounts/?user_id=nonexistent-user-id")
    
    # Should return 404 Not Found
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_missing_query_parameters(client):
    """Test accounts endpoint with missing query parameters"""
    response = client.get("/api/v1/accounts/")
    
    # Should be rejected with 400 Bad Request
    assert response.status_code == 400
    assert "must be provided" in response.json()["detail"].lower()

def test_very_large_balance(client, test_user):
    """Test creating an account with a very large balance"""
    response = client.post(
        "/api/v1/accounts/",
        json={
            "user_id": test_user.id,
            "name": "Large Balance Account",
            "balance": 9999999999.99,  # Very large balance
            "is_manual": True
        }
    )
    
    # Should succeed
    assert response.status_code == 200
    assert response.json()["balance"] == 9999999999.99

def test_zero_adjustment(client, test_user, test_account):
    """Test a zero-value balance adjustment"""
    # Get current balance
    db_session = next(client.app.dependency_overrides[get_db_session]())
    account = db_session.query(BankAccount).filter(BankAccount.id == test_account.id).first()
    initial_balance = account.balance
    
    adjustment_data = {
        "amount": 0.0,  # Zero adjustment
        "user_id": test_user.id,
        "reason": "Zero adjustment test"
    }
    
    response = client.post(
        f"/api/v1/accounts/{test_account.id}/adjust",
        json=adjustment_data
    )
    
    # Should succeed but balance remains unchanged
    assert response.status_code == 200
    assert response.json()["balance"] == initial_balance

def test_invalid_account_id_format(client, test_user):
    """Test adjustment with an invalid account ID format"""
    adjustment_data = {
        "amount": 100.0,
        "user_id": test_user.id,
        "reason": "Invalid account test"
    }
    
    response = client.post(
        "/api/v1/accounts/not-a-valid-uuid/adjust",
        json=adjustment_data
    )
    
    # Should be rejected with 422 Unprocessable Entity or similar error code
    assert response.status_code in (422, 404, 400)

@patch('backend.app.services.plaid_service.client.accounts_get')
def test_plaid_account_sync_error(mock_accounts_get, client, test_user, db_session):
    """Test error handling during transaction sync"""
    # Create a plaid item for testing
    plaid_item = PlaidItem(
        user_id=test_user.id,
        access_token="test-access-token-error",
        item_id="test-item-id-error",
        institution_id="ins_error",
        institution_name="Error Test Bank"
    )
    db_session.add(plaid_item)
    
    # Create a plaid-linked account - this was missing from the original test
    plaid_account = BankAccount(
        user_id=test_user.id,
        name="Plaid Error Test Account",
        balance=500.0,
        is_manual=False,  # Must be False to be detected as Plaid-connected
        plaid_account_id="mock_error_account_id",
        institution_name="Error Test Bank"
    )
    db_session.add(plaid_account)
    db_session.commit()
    
    # Make the Plaid API call raise an exception
    mock_accounts_get.side_effect = Exception("Simulated Plaid API error")
    
    response = client.post(
        "/api/v1/plaid/transactions/sync",
        json={"user_id": test_user.id}
    )
    
    # Should handle the error gracefully
    assert response.status_code == 200
    # The results should include the error
    results = response.json()
    assert "sync_results" in results
    assert any("error" in result for result in results["sync_results"])
    assert "Simulated Plaid API error" in str(results)

def test_precision_rounding(client, test_user, test_account):
    """Test precision handling with small decimal adjustments"""
    # Get current balance
    db_session = next(client.app.dependency_overrides[get_db_session]())
    account = db_session.query(BankAccount).filter(BankAccount.id == test_account.id).first()
    initial_balance = account.balance
    
    # Series of small adjustments that should test floating point precision
    adjustments = [0.1, 0.02, 0.003, 0.0004]
    total_adjustment = sum(adjustments)
    
    for adjustment in adjustments:
        adjustment_data = {
            "amount": adjustment,
            "user_id": test_user.id,
            "reason": f"Small adjustment: {adjustment}"
        }
        
        response = client.post(
            f"/api/v1/accounts/{test_account.id}/adjust",
            json=adjustment_data
        )
        
        assert response.status_code == 200
    
    # Get the final balance and verify precision
    db_session = next(client.app.dependency_overrides[get_db_session]())
    account = db_session.query(BankAccount).filter(BankAccount.id == test_account.id).first()
    
    # Should have added exactly the sum of all adjustments
    assert round(account.balance - initial_balance, 4) == round(total_adjustment, 4) 