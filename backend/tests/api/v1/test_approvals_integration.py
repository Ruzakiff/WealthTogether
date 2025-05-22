import pytest
from datetime import datetime, timedelta, timezone, date
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from backend.app.main import app
from backend.app.database import get_db_session
from backend.app.models.models import Base, User, Couple, PendingApproval, ApprovalSettings, ApprovalStatus, ApprovalActionType, Category, BankAccount, FinancialGoal, GoalType, AutoAllocationRule

# Create an in-memory SQLite database for testing
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the dependency to use our test database
@pytest.fixture
def client():
    """Create a test client with the test database."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Override the get_db dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db_session] = override_get_db
    
    # Create a test client
    test_client = TestClient(app)
    
    # Return the client
    yield test_client
    
    # Clean up - drop tables
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides = {}

@pytest.fixture
def db_session():
    """Create a database session for setup."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create a session
    session = TestingSessionLocal()
    
    yield session
    
    # Clean up
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def setup_test_data(db_session):
    """Setup test data in the database."""
    # Create users
    user1 = User(
        id="user1",
        email="user1@example.com",
        display_name="User One"
    )
    user2 = User(
        id="user2",
        email="user2@example.com",
        display_name="User Two"
    )
    db_session.add_all([user1, user2])
    
    # Create couple
    couple = Couple(
        id="couple1",
        partner_1_id=user1.id,
        partner_2_id=user2.id
    )
    db_session.add(couple)
    
    # Create approval settings
    settings = ApprovalSettings(
        id="settings1",
        couple_id=couple.id,
        enabled=True,
        budget_creation_threshold=500.0
    )
    db_session.add(settings)
    
    db_session.commit()
    
    return {
        "user1": user1,
        "user2": user2,
        "couple": couple,
        "settings": settings
    }

class TestApprovalsWorkflow:
    """Test the complete approval workflow."""
    
    def test_create_and_approve_workflow(self, client, setup_test_data, db_session):
        """Test creating and approving an approval."""
        data = setup_test_data
        
        # Create a test category for our budget
        category = Category(
            id=str(uuid4()),
            name="Groceries"
        )
        db_session.add(category)
        db_session.commit()
        
        # Use today's date in ISO format (string) for the payload
        today_str = date.today().isoformat()
        
        # 1. Create an approval with all required budget fields
        approval_data = {
            "couple_id": str(data["couple"].id),  # Convert to string to ensure JSON serialization
            "initiated_by": str(data["user1"].id),
            "action_type": "budget_create",
            "payload": {
                "couple_id": str(data["couple"].id),
                "category_id": str(category.id),
                "amount": 500,
                "period": "monthly",
                "start_date": today_str,
                "created_by": str(data["user1"].id)
            }
        }
        
        create_response = client.post(
            "/api/v1/approvals/",
            json=approval_data
        )
        
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Get the approval
        get_response = client.get(f"/api/v1/approvals/{approval_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == approval_id
        assert get_response.json()["status"] == "pending"
        
        # 3. List approvals and verify the created one is present
        list_response = client.get(f"/api/v1/approvals/?couple_id={str(data['couple'].id)}")
        assert list_response.status_code == 200
        approvals = list_response.json()
        assert len(approvals) == 1
        assert approvals[0]["id"] == approval_id
        
        # 4. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Looks good!"
        }
        
        approve_response = client.put(
            f"/api/v1/approvals/{approval_id}",
            json=approve_data
        )
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
    
    def test_create_and_reject_workflow(self, client, setup_test_data):
        """Test creating and rejecting an approval."""
        data = setup_test_data
        
        # 1. Create an approval
        approval_data = {
            "couple_id": data["couple"].id,
            "initiated_by": data["user1"].id,
            "action_type": "goal_create",
            "payload": {
                "goal_name": "Luxury Vacation",
                "target_amount": 5000,
                "deadline": (datetime.utcnow() + timedelta(days=365)).isoformat()
            }
        }
        
        create_response = client.post(
            "/api/v1/approvals/",
            json=approval_data
        )
        
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Reject the request as the partner
        reject_data = {
            "status": "rejected",
            "resolved_by": data["user2"].id,
            "resolution_note": "Too expensive right now"
        }
        
        reject_response = client.put(
            f"/api/v1/approvals/{approval_id}",
            json=reject_data
        )
        
        assert reject_response.status_code == 200
        result = reject_response.json()
        assert result["status"] == "success"
        assert "execution_result" not in result  # No execution for rejected approvals
        
        # 3. Verify the approval is now rejected
        get_rejected_response = client.get(f"/api/v1/approvals/{approval_id}")
        assert get_rejected_response.status_code == 200
        rejected_approval = get_rejected_response.json()
        assert rejected_approval["status"] == "rejected"
        assert rejected_approval["resolved_by"] == data["user2"].id
        assert rejected_approval["resolution_note"] == "Too expensive right now"
    
    def test_self_approval_error(self, client, setup_test_data):
        """Test that a user cannot approve their own request."""
        data = setup_test_data
        
        # 1. Create an approval
        approval_data = {
            "couple_id": data["couple"].id,
            "initiated_by": data["user1"].id,
            "action_type": "budget_update",
            "payload": {
                "budget_id": "budget123",
                "amount": 300
            }
        }
        
        create_response = client.post(
            "/api/v1/approvals/",
            json=approval_data
        )
        
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Try to approve the request as the same user
        approve_data = {
            "status": "approved",
            "resolved_by": data["user1"].id,
            "resolution_note": "I approve my own request"
        }
        
        approve_response = client.put(
            f"/api/v1/approvals/{approval_id}",
            json=approve_data
        )
        
        assert approve_response.status_code == 403
        assert "own request" in approve_response.json()["detail"]
    
    def test_approve_nonexistent_approval(self, client, setup_test_data):
        """Test error when approving a nonexistent approval."""
        data = setup_test_data
        
        approve_data = {
            "status": "approved",
            "resolved_by": data["user2"].id,
            "resolution_note": "Looks good!"
        }
        
        response = client.put(
            "/api/v1/approvals/nonexistent-id",
            json=approve_data
        )
        
        assert response.status_code == 404
        assert "Approval not found" in response.json()["detail"]

    def test_auto_rule_create_approval_workflow(self, client, setup_test_data, db_session):
        """Test creating and approving an auto allocation rule through approval workflow."""
        data = setup_test_data
        
        # Create a test account and goal for our rule
        account = BankAccount(
            id=str(uuid4()),
            user_id=data["user1"].id,
            name="Test Account",
            balance=1000.0,
            institution_name="Test Bank"
        )
        
        goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=data["couple"].id,
            name="Test Goal",
            target_amount=5000.0,
            current_allocation=0.0,
            type=GoalType.CUSTOM
        )
        
        db_session.add(account)
        db_session.add(goal)
        db_session.commit()
        
        # 1. Create an approval request for auto rule creation
        approval_data = {
            "couple_id": str(data["couple"].id),
            "initiated_by": str(data["user1"].id),
            "action_type": "auto_rule_create",
            "payload": {
                "user_id": str(data["user1"].id),
                "source_account_id": str(account.id),
                "goal_id": str(goal.id),
                "percent": 20.0,
                "trigger": "deposit"
            }
        }
        
        create_response = client.post("/api/v1/approvals/", json=approval_data)
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Looks good!"
        }
        
        approve_response = client.put(f"/api/v1/approvals/{approval_id}", json=approve_data)
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
        
        # 3. Verify the rule was created
        execution_result = result["execution_result"]
        assert execution_result["user_id"] == str(data["user1"].id)
        assert execution_result["source_account_id"] == str(account.id)
        assert execution_result["goal_id"] == str(goal.id)
        assert execution_result["percent"] == 20.0
        
        # Also check in the database
        rule = db_session.query(AutoAllocationRule).filter(
            AutoAllocationRule.user_id == data["user1"].id,
            AutoAllocationRule.goal_id == goal.id
        ).first()
        
        assert rule is not None
        assert rule.percent == 20.0
    
    def test_auto_rule_update_approval_workflow(self, client, setup_test_data, db_session):
        """Test updating an auto allocation rule through approval workflow."""
        data = setup_test_data
        
        # Create test account, goal and rule
        account = BankAccount(
            id=str(uuid4()),
            user_id=data["user1"].id,
            name="Test Account",
            balance=1000.0,
            institution_name="Test Bank"
        )
        
        goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=data["couple"].id,
            name="Test Goal",
            target_amount=5000.0,
            current_allocation=0.0,
            type=GoalType.CUSTOM
        )
        
        # Create the rule directly first
        rule = AutoAllocationRule(
            id=str(uuid4()),
            user_id=data["user1"].id,
            source_account_id=account.id,
            goal_id=goal.id,
            percent=10.0,
            trigger="deposit",
            is_active=True
        )
        
        db_session.add(account)
        db_session.add(goal)
        db_session.add(rule)
        db_session.commit()
        
        # 1. Create an approval request for rule update
        approval_data = {
            "couple_id": str(data["couple"].id),
            "initiated_by": str(data["user1"].id),
            "action_type": "auto_rule_update",
            "payload": {
                "rule_id": str(rule.id),
                "percent": 25.0,
                "is_active": True
            }
        }
        
        create_response = client.post("/api/v1/approvals/", json=approval_data)
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Approved rule update"
        }
        
        approve_response = client.put(f"/api/v1/approvals/{approval_id}", json=approve_data)
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
        
        # 3. Verify the rule was updated
        execution_result = result["execution_result"]
        assert execution_result["percent"] == 25.0
        
        # Also check in the database
        db_session.refresh(rule)
        assert rule.percent == 25.0

    def test_goal_create_approval_workflow(self, client, setup_test_data, db_session):
        """Test creating and approving a financial goal through approval workflow."""
        data = setup_test_data
        
        # 1. Create an approval request for goal creation
        today_str = date.today().isoformat()
        approval_data = {
            "couple_id": str(data["couple"].id),
            "initiated_by": str(data["user1"].id),
            "action_type": "goal_create",
            "payload": {
                "couple_id": str(data["couple"].id),
                "name": "Vacation Fund",
                "target_amount": 5000.0,
                "type": GoalType.VACATION.value,
                "priority": 1,
                "deadline": today_str,
                "notes": "Our dream vacation",
                "created_by": str(data["user1"].id)
            }
        }
        
        create_response = client.post("/api/v1/approvals/", json=approval_data)
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Let's start saving!"
        }
        
        approve_response = client.put(f"/api/v1/approvals/{approval_id}", json=approve_data)
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
        
        # 3. Verify the goal was created
        execution_result = result["execution_result"]
        assert execution_result["name"] == "Vacation Fund"
        assert execution_result["target_amount"] == 5000.0
        
        # Also check in the database
        goal = db_session.query(FinancialGoal).filter(
            FinancialGoal.couple_id == data["couple"].id,
            FinancialGoal.name == "Vacation Fund"
        ).first()
        
        assert goal is not None
        assert goal.target_amount == 5000.0

    def test_goal_update_approval_workflow(self, client, setup_test_data, db_session):
        """Test updating a financial goal through approval workflow."""
        data = setup_test_data
        
        # Create a test goal first
        goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=data["couple"].id,
            name="Test Goal",
            target_amount=3000.0,
            current_allocation=500.0,
            type=GoalType.VACATION,
            priority=2
        )
        
        db_session.add(goal)
        db_session.commit()
        
        # 1. Create an approval request for goal update
        approval_data = {
            "couple_id": str(data["couple"].id),
            "initiated_by": str(data["user1"].id),
            "action_type": "goal_update",
            "payload": {
                "goal_id": str(goal.id),
                "name": "Updated Goal Name",
                "target_amount": 5000.0,
                "priority": 1
            }
        }
        
        create_response = client.post("/api/v1/approvals/", json=approval_data)
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Approved goal update"
        }
        
        approve_response = client.put(f"/api/v1/approvals/{approval_id}", json=approve_data)
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
        
        # 3. Verify the goal was updated
        execution_result = result["execution_result"]
        assert execution_result["name"] == "Updated Goal Name"
        assert execution_result["target_amount"] == 5000.0
        
        # Also check in the database
        db_session.refresh(goal)
        assert goal.name == "Updated Goal Name"
        assert goal.target_amount == 5000.0
        assert goal.priority == 1

    def test_goal_allocation_approval_workflow(self, client, setup_test_data, db_session):
        """Test allocating to a goal through approval workflow."""
        data = setup_test_data
        
        # Create test account and goal
        account = BankAccount(
            id=str(uuid4()),
            user_id=data["user1"].id,
            name="Test Account",
            balance=1000.0,
            institution_name="Test Bank"
        )
        
        goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=data["couple"].id,
            name="Test Goal",
            target_amount=5000.0,
            current_allocation=0.0,
            type=GoalType.CUSTOM
        )
        
        db_session.add(account)
        db_session.add(goal)
        db_session.commit()
        
        # 1. Create an approval request for goal allocation
        approval_data = {
            "couple_id": str(data["couple"].id),
            "initiated_by": str(data["user1"].id),
            "action_type": "allocation",
            "payload": {
                "account_id": str(account.id),
                "goal_id": str(goal.id),
                "amount": 500.0,
                "user_id": str(data["user1"].id)
            }
        }
        
        create_response = client.post("/api/v1/approvals/", json=approval_data)
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Approved allocation"
        }
        
        approve_response = client.put(f"/api/v1/approvals/{approval_id}", json=approve_data)
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
        
        # 3. Verify the allocation was made
        db_session.refresh(goal)
        assert goal.current_allocation == 500.0
        
        # Check account balance was reduced
        db_session.refresh(account)
        assert account.balance == 500.0  # Starting 1000 - 500 allocated

    def test_goal_reallocation_approval_workflow(self, client, setup_test_data, db_session):
        """Test reallocating between goals through approval workflow."""
        data = setup_test_data
        
        # Create source and destination goals
        source_goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=data["couple"].id,
            name="Source Goal",
            target_amount=5000.0,
            current_allocation=1000.0,
            type=GoalType.VACATION,
            priority=2
        )
        
        dest_goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=data["couple"].id,
            name="Destination Goal",
            target_amount=3000.0,
            current_allocation=0.0,
            type=GoalType.EMERGENCY,
            priority=1
        )
        
        db_session.add(source_goal)
        db_session.add(dest_goal)
        db_session.commit()
        
        # 1. Create an approval request for reallocation
        approval_data = {
            "couple_id": str(data["couple"].id),
            "initiated_by": str(data["user1"].id),
            "action_type": "reallocation",
            "payload": {
                "source_goal_id": str(source_goal.id),
                "dest_goal_id": str(dest_goal.id),
                "amount": 500.0,
                "user_id": str(data["user1"].id)
            }
        }
        
        create_response = client.post("/api/v1/approvals/", json=approval_data)
        assert create_response.status_code == 200
        approval = create_response.json()
        approval_id = approval["id"]
        
        # 2. Approve the request as the partner
        approve_data = {
            "status": "approved",
            "resolved_by": str(data["user2"].id),
            "resolution_note": "Approved reallocation"
        }
        
        approve_response = client.put(f"/api/v1/approvals/{approval_id}", json=approve_data)
        
        assert approve_response.status_code == 200
        result = approve_response.json()
        assert result["status"] == "success"
        assert "execution_result" in result
        
        # 3. Verify the reallocation occurred
        db_session.refresh(source_goal)
        db_session.refresh(dest_goal)
        assert source_goal.current_allocation == 500.0  # 1000 - 500
        assert dest_goal.current_allocation == 500.0    # 0 + 500

class TestApprovalSettingsIntegration:
    """Test the approval settings API endpoints with database integration."""
    
    def test_get_default_settings(self, client, setup_test_data):
        """Test getting default approval settings."""
        data = setup_test_data
        
        response = client.get(f"/api/v1/approvals/settings/{data['couple'].id}")
        
        assert response.status_code == 200
        settings = response.json()
        assert settings["couple_id"] == data["couple"].id
        assert settings["enabled"] == True
        assert settings["budget_creation_threshold"] == 500.0
    
    def test_update_settings(self, client, setup_test_data):
        """Test updating approval settings."""
        data = setup_test_data
        
        # Update settings
        update_data = {
            "enabled": False,
            "budget_creation_threshold": 1000.0,
            "budget_update_threshold": 300.0,
            "goal_allocation_threshold": 800.0,
            "approval_expiration_hours": 48
        }
        
        update_response = client.put(
            f"/api/v1/approvals/settings/{data['couple'].id}",
            json=update_data
        )
        
        assert update_response.status_code == 200
        updated_settings = update_response.json()
        assert updated_settings["enabled"] == False
        assert updated_settings["budget_creation_threshold"] == 1000.0
        assert updated_settings["budget_update_threshold"] == 300.0
        assert updated_settings["goal_allocation_threshold"] == 800.0
        assert updated_settings["approval_expiration_hours"] == 48
        
        # Verify settings were updated in database
        get_response = client.get(f"/api/v1/approvals/settings/{data['couple'].id}")
        assert get_response.status_code == 200
        settings = get_response.json()
        assert settings["enabled"] == False
        assert settings["budget_creation_threshold"] == 1000.0
    
    def test_nonexistent_couple_settings(self, client):
        """Test error when getting settings for nonexistent couple."""
        response = client.get("/api/v1/approvals/settings/nonexistent-id")
        
        assert response.status_code == 404
        assert "Couple not found" in response.json()["detail"]

class TestApprovalFiltering:
    """Test filtering approvals."""
    
    def test_filter_by_status(self, client, setup_test_data, db_session):
        """Test filtering approvals by status."""
        data = setup_test_data
        
        # Create two approvals with different statuses
        pending_approval = PendingApproval(
            id="pending-approval",
            couple_id=data["couple"].id,
            initiated_by=data["user1"].id,
            action_type="budget_create",
            payload={"budget_name": "Groceries", "amount": 500},
            status="pending"
        )
        
        approved_approval = PendingApproval(
            id="approved-approval",
            couple_id=data["couple"].id,
            initiated_by=data["user1"].id,
            action_type="goal_create",
            payload={"goal_name": "Vacation", "amount": 1000},
            status="approved",
            resolved_by=data["user2"].id,
            resolved_at=datetime.utcnow()
        )
        
        db_session.add_all([pending_approval, approved_approval])
        db_session.commit()
        
        # Filter by pending status
        pending_response = client.get(f"/api/v1/approvals/?status=pending")
        assert pending_response.status_code == 200
        pending_results = pending_response.json()
        assert len(pending_results) == 1
        assert pending_results[0]["id"] == "pending-approval"
        
        # Filter by approved status
        approved_response = client.get(f"/api/v1/approvals/?status=approved")
        assert approved_response.status_code == 200
        approved_results = approved_response.json()
        assert len(approved_results) == 1
        assert approved_results[0]["id"] == "approved-approval"
        
    def test_filter_by_action_type(self, client, setup_test_data, db_session):
        """Test filtering approvals by action type."""
        data = setup_test_data
        
        # Create approvals with different action types
        budget_approval = PendingApproval(
            id="budget-approval",
            couple_id=data["couple"].id,
            initiated_by=data["user1"].id,
            action_type="budget_create",
            payload={"budget_name": "Groceries", "amount": 500},
            status="pending"
        )
        
        goal_approval = PendingApproval(
            id="goal-approval",
            couple_id=data["couple"].id,
            initiated_by=data["user1"].id,
            action_type="goal_create",
            payload={"goal_name": "Vacation", "amount": 1000},
            status="pending"
        )
        
        allocation_approval = PendingApproval(
            id="allocation-approval",
            couple_id=data["couple"].id,
            initiated_by=data["user1"].id,
            action_type="allocation",
            payload={"goal_id": "goal123", "amount": 300},
            status="pending"
        )
        
        db_session.add_all([budget_approval, goal_approval, allocation_approval])
        db_session.commit()
        
        # Filter by budget_create action type
        budget_response = client.get(f"/api/v1/approvals/?action_type=budget_create")
        assert budget_response.status_code == 200
        budget_results = budget_response.json()
        assert len(budget_results) == 1
        assert budget_results[0]["id"] == "budget-approval"
        
        # Filter by goal_create action type
        goal_response = client.get(f"/api/v1/approvals/?action_type=goal_create")
        assert goal_response.status_code == 200
        goal_results = goal_response.json()
        assert len(goal_results) == 1
        assert goal_results[0]["id"] == "goal-approval" 