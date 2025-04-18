import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status

from backend.app.services.couple_service import create_couple
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