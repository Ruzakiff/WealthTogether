import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status, HTTPException
from uuid import uuid4, UUID

from backend.app.services.user_service import create_user, get_user_by_id, get_user_by_email, update_user
from backend.app.schemas.users import UserCreate, UserUpdate
from backend.app.models.models import User

# Service layer tests
def test_create_user_service(db_session):
    """Test user creation at the service layer"""
    user_data = UserCreate(email="newuser@example.com", display_name="New User")
    user = create_user(db_session, user_data)
    
    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.display_name == "New User"
    
def test_create_duplicate_user_service(db_session, test_user):
    """Test that creating a user with an existing email raises an error"""
    user_data = UserCreate(email=test_user.email, display_name="Duplicate User")
    
    with pytest.raises(Exception) as excinfo:
        create_user(db_session, user_data)
    assert "Email already registered" in str(excinfo.value)

def test_get_user_by_id_service(db_session, test_user):
    """Test retrieving a user by ID at the service layer"""
    user = get_user_by_id(db_session, test_user.id)
    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email

def test_get_nonexistent_user_by_id_service(db_session):
    """Test that retrieving a nonexistent user by ID raises an exception"""
    random_id = str(uuid4())
    
    with pytest.raises(HTTPException) as excinfo:
        get_user_by_id(db_session, random_id)
    
    assert excinfo.value.status_code == 404
    assert f"User with id {random_id} not found" in str(excinfo.value.detail)

def test_get_user_by_email_service(db_session, test_user):
    """Test retrieving a user by email at the service layer"""
    user = get_user_by_email(db_session, test_user.email)
    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email

def test_get_nonexistent_user_by_email_service(db_session):
    """Test retrieving a nonexistent user by email returns None"""
    user = get_user_by_email(db_session, "nonexistent@example.com")
    assert user is None

def test_update_user_service(db_session, test_user):
    """Test updating user information"""
    update_data = UserUpdate(display_name="Updated Name")
    updated_user = update_user(db_session, test_user.id, update_data)
    
    assert updated_user is not None
    assert updated_user.id == test_user.id
    assert updated_user.display_name == "Updated Name"
    assert updated_user.email == test_user.email  # Email should remain unchanged

# API layer tests
def test_create_user_api(client):
    """Test user creation through the API"""
    response = client.post(
        "/api/v1/users/",
        json={"email": "apiuser@example.com", "display_name": "API User"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "apiuser@example.com"
    assert data["display_name"] == "API User"
    
def test_create_duplicate_user_api(client, test_user):
    """Test that the API correctly handles duplicate user creation"""
    response = client.post(
        "/api/v1/users/",
        json={"email": test_user.email, "display_name": "Duplicate API User"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in response.json()["detail"]
    
def test_invalid_email_format(client):
    """Test that the API validates email format"""
    response = client.post(
        "/api/v1/users/",
        json={"email": "notanemail", "display_name": "Invalid Email User"}
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_get_user_by_id_api(client, test_user):
    """Test retrieving a user by ID through the API"""
    response = client.get(f"/api/v1/users/{test_user.id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["display_name"] == test_user.display_name

def test_get_nonexistent_user_api(client):
    """Test retrieving a nonexistent user returns 404"""
    random_id = str(uuid4())
    response = client.get(f"/api/v1/users/{random_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

def test_update_user_api(client, test_user):
    """Test updating a user through the API"""
    response = client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"display_name": "Updated via API"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_user.id
    assert data["display_name"] == "Updated via API"
    assert data["email"] == test_user.email  # Email should remain unchanged

def test_update_nonexistent_user_api(client):
    """Test updating a nonexistent user returns 404"""
    random_id = str(uuid4())
    response = client.patch(
        f"/api/v1/users/{random_id}",
        json={"display_name": "This should fail"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

def test_get_user_accounts(client, test_user, test_account):
    """Test retrieving accounts for a specific user"""
    response = client.get(f"/api/v1/accounts/?user_id={test_user.id}")
    
    assert response.status_code == status.HTTP_200_OK
    accounts = response.json()
    assert len(accounts) >= 1
    # Verify the test account is in the results
    account_ids = [a["id"] for a in accounts]
    assert test_account.id in account_ids

def test_invalid_user_id_format(client):
    """Test handling of invalid UUID format for user ID"""
    response = client.get("/api/v1/users/not-a-valid-uuid")
    
    # FastAPI's UUID validation should cause a 422 Unprocessable Entity
    assert response.status_code in (status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_404_NOT_FOUND)
    # Different versions of FastAPI/Pydantic might handle this differently

def test_empty_display_name(client):
    """Test handling of empty display name"""
    response = client.post(
        "/api/v1/users/",
        json={"email": "valid@example.com", "display_name": ""}
    )
    
    # Should reject with 422 Unprocessable Entity due to validation rules
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY 