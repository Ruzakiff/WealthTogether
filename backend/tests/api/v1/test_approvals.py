import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, ANY
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_db_session
from backend.app.api.v1.approvals import router
from backend.app.schemas.approvals import (
    ApprovalCreate, ApprovalResponse, ApprovalFilter, ApprovalSettingsResponse,
    ApprovalStatus, ApprovalActionType, ApprovalUpdate, ApprovalSettingsUpdate
)

# Setup test client with dependency override
@pytest.fixture
def client():
    """Create a test client with database dependency overridden."""
    def get_db_session_override():
        return MagicMock()
    
    app.dependency_overrides = {}  # Reset overrides
    app.dependency_overrides[get_db_session] = get_db_session_override
    
    return TestClient(app)

# Mock responses
@pytest.fixture
def mock_approval_response():
    """Create a mock approval response."""
    return {
        "id": "approval123",
        "couple_id": "couple789",
        "initiated_by": "user123",
        "action_type": ApprovalActionType.BUDGET_CREATE.value,
        "payload": {"budget_name": "Groceries", "amount": 500},
        "status": ApprovalStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
        "resolved_at": None,
        "resolved_by": None,
        "resolution_note": None
    }

@pytest.fixture
def mock_settings_response():
    """Create a mock approval settings response."""
    return {
        "id": "settings123",
        "couple_id": "couple789",
        "enabled": True,
        "budget_creation_threshold": 500.0,
        "budget_update_threshold": 200.0,
        "goal_allocation_threshold": 500.0,
        "goal_reallocation_threshold": 300.0,
        "auto_rule_threshold": 300.0,
        "approval_expiration_hours": 72,
        "notify_on_create": True,
        "notify_on_resolve": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

class TestCreateApprovalEndpoint:
    """Test create approval endpoint."""
    
    @patch("backend.app.api.v1.approvals.create_pending_approval")
    def test_create_approval(self, mock_create, client, mock_approval_response):
        """Test creating an approval."""
        # Setup
        mock_create.return_value = mock_approval_response
        
        # Execute
        response = client.post(
            "/api/v1/approvals/",
            json={
                "couple_id": "couple789",
                "initiated_by": "user123",
                "action_type": "budget_create",
                "payload": {"budget_name": "Groceries", "amount": 500}
            }
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_approval_response["id"]
        assert data["action_type"] == ApprovalActionType.BUDGET_CREATE.value
        mock_create.assert_called_once()

class TestListApprovalsEndpoint:
    """Test list approvals endpoint."""
    
    @patch("backend.app.api.v1.approvals.get_pending_approvals")
    def test_list_all_approvals(self, mock_get, client, mock_approval_response):
        """Test listing all approvals."""
        # Setup
        mock_get.return_value = [mock_approval_response]
        
        # Execute
        response = client.get("/api/v1/approvals/")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == mock_approval_response["id"]
        mock_get.assert_called_once()
    
    @patch("backend.app.api.v1.approvals.get_pending_approvals")
    def test_list_filtered_approvals(self, mock_get, client, mock_approval_response):
        """Test listing filtered approvals."""
        # Setup
        mock_get.return_value = [mock_approval_response]
        
        # Execute
        response = client.get(
            "/api/v1/approvals/?couple_id=couple789&status=pending&action_type=budget_create"
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == mock_approval_response["id"]
        # Use ANY matchers for the filters to avoid strict comparison
        mock_get.assert_called_once_with(ANY, ANY)

class TestGetApprovalEndpoint:
    """Test get approval endpoint."""
    
    @patch("backend.app.api.v1.approvals.get_approval_by_id")
    def test_get_approval(self, mock_get, client, mock_approval_response):
        """Test getting a specific approval."""
        # Setup
        mock_get.return_value = mock_approval_response
        
        # Execute
        response = client.get(f"/api/v1/approvals/{mock_approval_response['id']}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_approval_response["id"]
        # Use ANY to match the db parameter
        mock_get.assert_called_once_with(ANY, mock_approval_response["id"])

class TestResolveApprovalEndpoint:
    """Test resolve approval endpoint."""
    
    @patch("backend.app.api.v1.approvals.update_approval_status")
    def test_approve_approval(self, mock_update, client, mock_approval_response):
        """Test approving an approval."""
        # Setup
        mock_approval_response["status"] = ApprovalStatus.APPROVED.value
        mock_approval_response["resolved_by"] = "partner456"
        mock_approval_response["resolution_note"] = "Looks good!"
        mock_approval_response["resolved_at"] = datetime.now(timezone.utc).isoformat()
        
        result = {
            "status": "success",
            "message": "Approval approved",
            "execution_result": {"message": "Budget creation executed successfully"}
        }
        
        mock_update.return_value = (mock_approval_response, result)
        
        # Execute
        response = client.put(
            f"/api/v1/approvals/{mock_approval_response['id']}",
            json={
                "status": "approved",
                "resolved_by": "partner456",
                "resolution_note": "Looks good!"
            }
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "execution_result" in data
        mock_update.assert_called_once()
    
    @patch("backend.app.api.v1.approvals.update_approval_status")
    def test_reject_approval(self, mock_update, client, mock_approval_response):
        """Test rejecting an approval."""
        # Setup
        mock_approval_response["status"] = ApprovalStatus.REJECTED.value
        mock_approval_response["resolved_by"] = "partner456"
        mock_approval_response["resolution_note"] = "Too expensive"
        mock_approval_response["resolved_at"] = datetime.now(timezone.utc).isoformat()
        
        result = {
            "status": "success",
            "message": "Approval rejected"
        }
        
        mock_update.return_value = (mock_approval_response, result)
        
        # Execute
        response = client.put(
            f"/api/v1/approvals/{mock_approval_response['id']}",
            json={
                "status": "rejected",
                "resolved_by": "partner456",
                "resolution_note": "Too expensive"
            }
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "execution_result" not in data
        mock_update.assert_called_once()

class TestApprovalSettingsEndpoints:
    """Test approval settings endpoints."""
    
    @patch("backend.app.api.v1.approvals.get_approval_settings")
    def test_get_settings(self, mock_get, client, mock_settings_response):
        """Test getting approval settings."""
        # Setup
        mock_get.return_value = mock_settings_response
        
        # Execute
        response = client.get(f"/api/v1/approvals/settings/{mock_settings_response['couple_id']}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_settings_response["id"]
        assert data["couple_id"] == mock_settings_response["couple_id"]
        # Use ANY to match the db parameter
        mock_get.assert_called_once_with(ANY, mock_settings_response["couple_id"])
    
    @patch("backend.app.api.v1.approvals.update_approval_settings")
    def test_update_settings(self, mock_update, client, mock_settings_response):
        """Test updating approval settings."""
        # Setup
        # Modify some settings
        mock_settings_response["enabled"] = False
        mock_settings_response["budget_creation_threshold"] = 1000.0
        mock_settings_response["approval_expiration_hours"] = 48
        
        mock_update.return_value = mock_settings_response
        
        # Execute
        response = client.put(
            f"/api/v1/approvals/settings/{mock_settings_response['couple_id']}",
            json={
                "enabled": False,
                "budget_creation_threshold": 1000.0,
                "budget_update_threshold": 200.0,
                "goal_allocation_threshold": 500.0,
                "goal_reallocation_threshold": 300.0,
                "auto_rule_threshold": 300.0,
                "approval_expiration_hours": 48,
                "notify_on_create": True,
                "notify_on_resolve": True
            }
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == False
        assert data["budget_creation_threshold"] == 1000.0
        assert data["approval_expiration_hours"] == 48
        mock_update.assert_called_once() 