import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status

from backend.app.services.user_service import create_user
from backend.app.schemas.users import UserCreate

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