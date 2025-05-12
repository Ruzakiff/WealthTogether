import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status
import uuid

from backend.app.services.couple_service import create_couple, get_couple_by_id, get_couples_by_user_id
from backend.app.schemas.couples import CoupleCreate

# Service layer tests
def test_create_couple_service(db_session, test_user):
    """Test couple creation at the service layer"""
    # Create a second user first
    from backend.app.models.models import User
    from uuid import uuid4
    
    partner = User(
        id=str(uuid4()),
        email="partner_service@example.com",
        display_name="Partner Service"
    )
    db_session.add(partner)
    db_session.commit()
    
    # Create couple
    couple_data = CoupleCreate(partner_1_id=test_user.id, partner_2_id=partner.id)
    couple = create_couple(db_session, couple_data)
    
    assert couple.id is not None
    assert couple.partner_1_id == test_user.id
    assert couple.partner_2_id == partner.id

def test_create_couple_nonexistent_user(db_session, test_user):
    """Test that creating a couple with a non-existent user raises an error"""
    couple_data = CoupleCreate(partner_1_id=test_user.id, partner_2_id="nonexistent-id")
    
    with pytest.raises(Exception) as excinfo:
        create_couple(db_session, couple_data)
    assert "not found" in str(excinfo.value)

def test_create_duplicate_couple(db_session, test_couple):
    """Test that creating a duplicate couple raises an error"""
    couple_data = CoupleCreate(
        partner_1_id=test_couple.partner_1_id, 
        partner_2_id=test_couple.partner_2_id
    )
    
    with pytest.raises(Exception) as excinfo:
        create_couple(db_session, couple_data)
    assert "already exists" in str(excinfo.value)

# Add new service layer tests
def test_get_couple_by_id_service(db_session, test_couple):
    """Test retrieving a couple by ID at the service layer"""
    couple = get_couple_by_id(db_session, test_couple.id)
    assert couple is not None
    assert couple.id == test_couple.id
    assert couple.partner_1_id == test_couple.partner_1_id
    assert couple.partner_2_id == test_couple.partner_2_id

def test_get_nonexistent_couple_by_id_service(db_session):
    """Test retrieving a nonexistent couple by ID raises 404"""
    nonexistent_id = str(uuid.uuid4())
    
    with pytest.raises(Exception) as excinfo:
        get_couple_by_id(db_session, nonexistent_id)
    assert "not found" in str(excinfo.value)

def test_get_couples_by_user_id_service(db_session, test_user, test_couple):
    """Test retrieving all couples a user belongs to"""
    couples = get_couples_by_user_id(db_session, test_user.id)
    assert len(couples) >= 1
    # Check that test_couple is in the results
    couple_ids = [c.id for c in couples]
    assert test_couple.id in couple_ids

def test_get_couples_by_nonexistent_user_id_service(db_session):
    """Test retrieving couples for a nonexistent user returns empty list"""
    nonexistent_id = str(uuid.uuid4())
    couples = get_couples_by_user_id(db_session, nonexistent_id)
    assert len(couples) == 0

# API layer tests
def test_create_couple_api(client, test_user):
    """Test couple creation through the API"""
    # Create a partner first
    partner_response = client.post(
        "/api/v1/users/",
        json={"email": "api_partner@example.com", "display_name": "API Partner"}
    )
    partner_id = partner_response.json()["id"]
    
    # Create the couple
    response = client.post(
        "/api/v1/couples/",
        json={"partner_1_id": test_user.id, "partner_2_id": partner_id}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["partner_1_id"] == test_user.id
    assert data["partner_2_id"] == partner_id

def test_create_couple_nonexistent_user_api(client, test_user):
    """Test API handling of couple creation with non-existent user"""
    response = client.post(
        "/api/v1/couples/",
        json={"partner_1_id": test_user.id, "partner_2_id": "nonexistent-id"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"]

# Add new API layer tests
def test_get_couple_by_id_api(client, test_couple):
    """Test retrieving a couple by ID through the API"""
    response = client.get(f"/api/v1/couples/{test_couple.id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_couple.id
    assert data["partner_1_id"] == test_couple.partner_1_id
    assert data["partner_2_id"] == test_couple.partner_2_id

def test_get_nonexistent_couple_api(client):
    """Test API handling of retrieving a nonexistent couple"""
    nonexistent_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/couples/{nonexistent_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"]

def test_get_user_couples_api(client, test_user, test_couple):
    """Test retrieving all couples for a user through the API"""
    response = client.get(f"/api/v1/couples/user/{test_user.id}")
    
    assert response.status_code == status.HTTP_200_OK
    couples = response.json()
    assert len(couples) >= 1
    # Check that test_couple is in the results
    couple_ids = [c["id"] for c in couples]
    assert test_couple.id in couple_ids

def test_get_nonexistent_user_couples_api(client):
    """Test API handling of retrieving couples for a nonexistent user"""
    nonexistent_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/couples/user/{nonexistent_id}")
    
    assert response.status_code == status.HTTP_200_OK
    couples = response.json()
    assert len(couples) == 0  # Should return empty list, not an error

def test_invalid_couple_id_format(client):
    """Test handling of invalid UUID format for couple ID"""
    response = client.get("/api/v1/couples/not-a-valid-uuid")
    
    # FastAPI's UUID validation should cause a 422 Unprocessable Entity
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY 