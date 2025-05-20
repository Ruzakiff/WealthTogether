import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.models import PendingApproval, ApprovalStatus, ApprovalSettings, Couple, User, LedgerEvent
from backend.app.schemas.approvals import (
    ApprovalCreate, ApprovalUpdate, ApprovalFilter, ApprovalActionType,
    ApprovalSettingsUpdate
)
from backend.app.services.approval_service import (
    create_pending_approval, get_pending_approvals, get_approval_by_id,
    update_approval_status, get_approval_settings, update_approval_settings,
    check_approval_required, create_default_approval_settings, execute_approved_action
)

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    return db

@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = "user123"
    return user

@pytest.fixture
def mock_partner():
    """Create a mock partner user."""
    partner = MagicMock(spec=User)
    partner.id = "partner456"
    return partner

@pytest.fixture
def mock_couple(mock_user, mock_partner):
    """Create a mock couple."""
    couple = MagicMock(spec=Couple)
    couple.id = "couple789"
    couple.partner_1_id = mock_user.id
    couple.partner_2_id = mock_partner.id
    return couple

@pytest.fixture
def mock_approval():
    """Create a mock pending approval."""
    approval = MagicMock(spec=PendingApproval)
    approval.id = "approval123"
    approval.couple_id = "couple789"
    approval.initiated_by = "user123"
    approval.action_type = ApprovalActionType.BUDGET_CREATE.value
    approval.payload = {"budget_name": "Groceries", "amount": 500}
    approval.status = ApprovalStatus.PENDING.value
    approval.created_at = datetime.now(timezone.utc)
    approval.expires_at = datetime.now(timezone.utc) + timedelta(hours=72)
    approval.resolved_at = None
    approval.resolved_by = None
    approval.resolution_note = None
    return approval

@pytest.fixture
def mock_settings():
    """Create mock approval settings."""
    settings = MagicMock(spec=ApprovalSettings)
    settings.id = "settings123"
    settings.couple_id = "couple789"
    settings.enabled = True
    settings.budget_creation_threshold = 500.0
    settings.budget_update_threshold = 200.0
    settings.goal_allocation_threshold = 500.0
    settings.goal_reallocation_threshold = 300.0
    settings.auto_rule_threshold = 300.0
    settings.approval_expiration_hours = 72
    settings.notify_on_create = True
    settings.notify_on_resolve = True
    return settings

class TestCreatePendingApproval:
    """Test create_pending_approval function."""
    
    def test_create_valid_approval(self, mock_db, mock_user, mock_couple, mock_settings):
        """Test creating a valid approval."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_couple,  # First call returns couple
            mock_user,    # Second call returns user
            mock_settings # Third call returns settings
        ]
        approval_data = ApprovalCreate(
            couple_id=mock_couple.id,
            initiated_by=mock_user.id,
            action_type=ApprovalActionType.BUDGET_CREATE,
            payload={"budget_name": "Groceries", "amount": 500}
        )
        
        # Execute
        result = create_pending_approval(mock_db, approval_data)
        
        # Assert
        assert mock_db.add.call_count == 2  # Approval and LedgerEvent
        assert mock_db.commit.call_count == 1
        assert mock_db.refresh.call_count == 1
        
    def test_couple_not_found(self, mock_db):
        """Test error when couple not found."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        approval_data = ApprovalCreate(
            couple_id="nonexistent",
            initiated_by="user123",
            action_type=ApprovalActionType.BUDGET_CREATE,
            payload={"budget_name": "Groceries", "amount": 500}
        )
        
        # Execute and assert
        with pytest.raises(HTTPException) as exc:
            create_pending_approval(mock_db, approval_data)
        assert exc.value.status_code == 404
        assert "Couple not found" in exc.value.detail
        
    def test_user_not_found(self, mock_db, mock_couple):
        """Test error when user not found."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_couple,  # Couple found
            None         # User not found
        ]
        approval_data = ApprovalCreate(
            couple_id=mock_couple.id,
            initiated_by="nonexistent",
            action_type=ApprovalActionType.BUDGET_CREATE,
            payload={"budget_name": "Groceries", "amount": 500}
        )
        
        # Execute and assert
        with pytest.raises(HTTPException) as exc:
            create_pending_approval(mock_db, approval_data)
        assert exc.value.status_code == 404
        assert "User not found" in exc.value.detail
        
    def test_user_not_part_of_couple(self, mock_db, mock_couple):
        """Test error when user is not part of the couple."""
        # Setup
        unrelated_user = MagicMock(spec=User)
        unrelated_user.id = "unrelated"
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_couple,      # Couple found
            unrelated_user    # User found but not in couple
        ]
        approval_data = ApprovalCreate(
            couple_id=mock_couple.id,
            initiated_by=unrelated_user.id,
            action_type=ApprovalActionType.BUDGET_CREATE,
            payload={"budget_name": "Groceries", "amount": 500}
        )
        
        # Execute and assert
        with pytest.raises(HTTPException) as exc:
            create_pending_approval(mock_db, approval_data)
        assert exc.value.status_code == 403
        assert "User is not part of this couple" in exc.value.detail

class TestGetPendingApprovals:
    """Test get_pending_approvals function."""
    
    def test_get_all_approvals(self, mock_db, mock_approval):
        """Test getting all approvals with no filters."""
        # Setup
        mock_db.query.return_value.order_by.return_value.all.return_value = [mock_approval]
        
        # Execute
        result = get_pending_approvals(mock_db)
        
        # Assert
        assert len(result) == 1
        assert result[0] == mock_approval
        mock_db.query.assert_called_once_with(PendingApproval)
        
    def test_get_filtered_approvals(self, mock_db, mock_approval):
        """Test filtering approvals."""
        # Setup
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_approval]
        
        filters = ApprovalFilter(
            couple_id="couple789",
            status=ApprovalStatus.PENDING
        )
        
        # Execute
        result = get_pending_approvals(mock_db, filters)
        
        # Assert
        assert result == [mock_approval]
        assert mock_db.query.call_count == 1
        # Don't assert on filter_by call count as it's not used in the actual implementation
        # Instead check that filter and order_by are called
        assert mock_query.filter.call_count >= 1 
        assert mock_query.order_by.call_count == 1
        assert mock_query.all.call_count == 1

class TestGetApprovalById:
    """Test get_approval_by_id function."""
    
    def test_get_existing_approval(self, mock_db, mock_approval):
        """Test getting an existing approval."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_approval
        
        # Execute
        result = get_approval_by_id(mock_db, mock_approval.id)
        
        # Assert
        assert result == mock_approval
        mock_db.query.assert_called_once_with(PendingApproval)
        
    def test_approval_not_found(self, mock_db):
        """Test error when approval not found."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute and assert
        with pytest.raises(HTTPException) as exc:
            get_approval_by_id(mock_db, "nonexistent")
        assert exc.value.status_code == 404
        assert "Approval not found" in exc.value.detail

class TestUpdateApprovalStatus:
    """Test update_approval_status function."""
    
    def test_approve_valid_approval(self, mock_db, mock_approval, mock_couple):
        """Test approving a valid approval."""
        # Setup - create real datetime objects instead of MagicMocks
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Replace MagicMock properties with real datetime objects
        mock_approval.created_at = now - timedelta(hours=1)
        mock_approval.expires_at = now + timedelta(hours=71)
        mock_approval.resolved_at = None
        mock_approval.status = ApprovalStatus.PENDING.value
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_approval,  # First call returns approval
            mock_couple     # Second call returns couple
        ]
        
        update_data = ApprovalUpdate(
            status=ApprovalStatus.APPROVED,
            resolved_by=mock_couple.partner_2_id,  # Partner (not the initiator)
            resolution_note="Looks good!"
        )
        
        # Create a class to properly monkey-patch datetime in the module
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return now
            
            @classmethod
            def utcnow(cls):
                return now
            
            # Add the timezone attribute that will be accessed
            timezone = timezone
        
        # Patch the datetime function in the service with our custom class
        with patch('backend.app.services.approval_service.datetime', MockDateTime):
            # Also patch execute_approved_action to avoid errors
            with patch("backend.app.services.approval_service.execute_approved_action") as mock_execute:
                mock_execute.return_value = {"message": "Action executed"}
                
                # Execute
                approval, result = update_approval_status(mock_db, mock_approval.id, update_data)
                
                # Assert
                assert approval.status == ApprovalStatus.APPROVED.value
                assert approval.resolved_by == update_data.resolved_by
                assert approval.resolution_note == update_data.resolution_note
                assert mock_db.commit.call_count == 1
                assert mock_execute.call_count == 1
    
    def test_reject_valid_approval(self, mock_db, mock_approval, mock_couple):
        """Test rejecting a valid approval."""
        # Setup - create real datetime objects instead of MagicMocks
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Replace MagicMock properties with real datetime objects
        mock_approval.created_at = now - timedelta(hours=1)
        mock_approval.expires_at = now + timedelta(hours=71)
        mock_approval.resolved_at = None
        mock_approval.status = ApprovalStatus.PENDING.value
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_approval,  # First call returns approval
            mock_couple     # Second call returns couple
        ]
        
        update_data = ApprovalUpdate(
            status=ApprovalStatus.REJECTED,
            resolved_by=mock_couple.partner_2_id,  # Partner (not the initiator)
            resolution_note="Too expensive"
        )
        
        # Create a class to properly monkey-patch datetime in the module
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return now
            
            @classmethod
            def utcnow(cls):
                return now
            
            # Add the timezone attribute that will be accessed
            timezone = timezone
        
        # Patch the datetime function in the service with our custom class
        with patch('backend.app.services.approval_service.datetime', MockDateTime):
            # Execute
            approval, result = update_approval_status(mock_db, mock_approval.id, update_data)
            
            # Assert
            assert approval.status == ApprovalStatus.REJECTED.value
            assert approval.resolved_by == update_data.resolved_by
            assert approval.resolution_note == update_data.resolution_note
            assert mock_db.commit.call_count == 1
    
    def test_expired_approval(self, mock_db, mock_approval, mock_couple):
        """Test error when approval has expired."""
        # Setup - create real datetime objects instead of MagicMocks
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Replace MagicMock properties with real datetime objects - set expired
        mock_approval.created_at = now - timedelta(days=4)
        mock_approval.expires_at = now - timedelta(hours=1)  # Expired 1 hour ago
        mock_approval.resolved_at = None
        mock_approval.status = ApprovalStatus.PENDING.value
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_approval,  # First call returns approval
            mock_couple     # Second call returns couple
        ]
        
        update_data = ApprovalUpdate(
            status=ApprovalStatus.APPROVED,
            resolved_by=mock_couple.partner_2_id,  # Partner (not the initiator)
            resolution_note="Looks good!"
        )
        
        # Create a class to properly monkey-patch datetime in the module
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return now
            
            @classmethod
            def utcnow(cls):
                return now
            
            # Add the timezone attribute that will be accessed
            timezone = timezone
        
        # Patch the datetime function in the service with our custom class
        with patch('backend.app.services.approval_service.datetime', MockDateTime):
            # Execute and assert
            with pytest.raises(HTTPException) as exc:
                update_approval_status(mock_db, mock_approval.id, update_data)
            assert exc.value.status_code == 400
            assert "expired" in exc.value.detail.lower()
    
    def test_already_resolved(self, mock_db, mock_approval, mock_couple):
        """Test error when approval is already resolved."""
        # Setup - create real datetime objects instead of MagicMocks
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Replace MagicMock properties with real datetime objects - already resolved
        mock_approval.created_at = now - timedelta(hours=2)
        mock_approval.expires_at = now + timedelta(hours=70)
        mock_approval.resolved_at = now - timedelta(minutes=30)  # Resolved 30 mins ago
        mock_approval.status = ApprovalStatus.APPROVED.value
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_approval,  # First call returns approval
            mock_couple     # Second call returns couple
        ]
        
        update_data = ApprovalUpdate(
            status=ApprovalStatus.REJECTED,
            resolved_by=mock_couple.partner_2_id,  # Partner (not the initiator)
            resolution_note="Changed my mind"
        )
        
        # Create a class to properly monkey-patch datetime in the module
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return now
            
            @classmethod
            def utcnow(cls):
                return now
            
            # Add the timezone attribute that will be accessed
            timezone = timezone
        
        # Patch the datetime function in the service with our custom class
        with patch('backend.app.services.approval_service.datetime', MockDateTime):
            # Execute and assert
            with pytest.raises(HTTPException) as exc:
                update_approval_status(mock_db, mock_approval.id, update_data)
            assert exc.value.status_code == 400
            # Update to match the exact error message pattern in the code
            assert "this approval has already been" in exc.value.detail.lower()
    
    def test_unauthorized_resolver(self, mock_db, mock_approval, mock_couple):
        """Test error when resolver is not authorized."""
        # Setup - create real datetime objects instead of MagicMocks
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Replace MagicMock properties with real datetime objects
        mock_approval.created_at = now - timedelta(hours=1)
        mock_approval.expires_at = now + timedelta(hours=71)
        mock_approval.resolved_at = None
        mock_approval.status = ApprovalStatus.PENDING.value
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_approval,  # First call returns approval
            mock_couple     # Second call returns couple
        ]
        
        update_data = ApprovalUpdate(
            status=ApprovalStatus.APPROVED,
            resolved_by="unauthorized_user",  # Not a partner
            resolution_note="Looks good!"
        )
        
        # Create a class to properly monkey-patch datetime in the module
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return now
            
            @classmethod
            def utcnow(cls):
                return now
            
            # Add the timezone attribute that will be accessed
            timezone = timezone
        
        # Patch the datetime function in the service with our custom class
        with patch('backend.app.services.approval_service.datetime', MockDateTime):
            # Execute and assert
            with pytest.raises(HTTPException) as exc:
                update_approval_status(mock_db, mock_approval.id, update_data)
            assert exc.value.status_code == 403
            assert "only partners in this couple can approve or reject" in exc.value.detail.lower()
    
    def test_self_approval(self, mock_db, mock_approval, mock_couple):
        """Test error when initiator tries to approve own request."""
        # Setup - create real datetime objects instead of MagicMocks
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Replace MagicMock properties with real datetime objects
        mock_approval.created_at = now - timedelta(hours=1)
        mock_approval.expires_at = now + timedelta(hours=71)
        mock_approval.resolved_at = None
        mock_approval.status = ApprovalStatus.PENDING.value
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_approval,  # First call returns approval
            mock_couple     # Second call returns couple
        ]
        
        update_data = ApprovalUpdate(
            status=ApprovalStatus.APPROVED,
            resolved_by=mock_approval.initiated_by,  # Same as initiator
            resolution_note="Looks good!"
        )
        
        # Create a class to properly monkey-patch datetime in the module
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return now
            
            @classmethod
            def utcnow(cls):
                return now
            
            # Add the timezone attribute that will be accessed
            timezone = timezone
        
        # Patch the datetime function in the service with our custom class
        with patch('backend.app.services.approval_service.datetime', MockDateTime):
            # Execute and assert
            with pytest.raises(HTTPException) as exc:
                update_approval_status(mock_db, mock_approval.id, update_data)
            assert exc.value.status_code == 403
            assert "you cannot approve your own request" in exc.value.detail.lower()

class TestApprovalSettings:
    """Test approval settings functions."""
    
    def test_get_existing_settings(self, mock_db, mock_settings):
        """Test getting existing approval settings."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        # Execute
        result = get_approval_settings(mock_db, mock_settings.couple_id)
        
        # Assert
        assert result == mock_settings
    
    def test_create_default_settings(self, mock_db, mock_couple):
        """Test creating default settings when none exist."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,         # No existing settings
            mock_couple   # Couple exists
        ]
        
        # Execute
        result = get_approval_settings(mock_db, mock_couple.id)
        
        # Assert
        assert mock_db.add.call_count == 1
        assert mock_db.commit.call_count == 1
        assert mock_db.refresh.call_count == 1
    
    def test_update_settings(self, mock_db, mock_settings):
        """Test updating approval settings."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        settings_data = ApprovalSettingsUpdate(
            enabled=False,
            budget_creation_threshold=1000.0,
            approval_expiration_hours=48
        )
        
        # Execute
        result = update_approval_settings(mock_db, mock_settings.couple_id, settings_data)
        
        # Assert
        assert mock_db.commit.call_count == 1
        assert mock_db.refresh.call_count == 1

class TestCheckApprovalRequired:
    """Test check_approval_required function."""
    
    def test_approval_disabled(self, mock_db, mock_settings):
        """Test when approvals are disabled."""
        # Modify settings to disable approvals
        mock_settings.enabled = False
        
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        # Execute
        result = check_approval_required(
            mock_db,
            mock_settings.couple_id,
            ApprovalActionType.BUDGET_CREATE,
            amount=1000.0
        )
        
        # Assert
        assert result == False
    
    def test_below_threshold(self, mock_db, mock_settings):
        """Test when amount is below threshold."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        # Execute
        result = check_approval_required(
            mock_db,
            mock_settings.couple_id,
            ApprovalActionType.BUDGET_CREATE,
            amount=100.0  # Below threshold of 500.0
        )
        
        # Assert
        assert result == False
    
    def test_above_threshold(self, mock_db, mock_settings):
        """Test when amount is above threshold."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        # Execute
        result = check_approval_required(
            mock_db,
            mock_settings.couple_id,
            ApprovalActionType.BUDGET_CREATE,
            amount=600.0  # Above threshold of 500.0
        )
        
        # Assert
        assert result == True
    
    def test_different_action_types(self, mock_db, mock_settings):
        """Test different action types have different thresholds."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        # Execute and assert
        assert check_approval_required(
            mock_db, mock_settings.couple_id, ApprovalActionType.BUDGET_UPDATE, amount=250.0
        ) == True  # Above budget_update_threshold of 200.0
        
        # For GOAL_UPDATE, default behavior is to require approval (return True)
        assert check_approval_required(
            mock_db, mock_settings.couple_id, ApprovalActionType.GOAL_UPDATE, amount=100.0
        ) == True  # Default behavior for types without specific thresholds 