import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status
from datetime import date

from backend.app.services.goal_service import create_financial_goal, get_goals_by_couple, allocate_to_goal
from backend.app.schemas.goals import FinancialGoalCreate, GoalAllocation
from backend.app.models.models import GoalType

# Service layer tests
def test_create_goal_service(db_session, test_couple):
    """Test goal creation at the service layer"""
    # Check the real enum values
    from backend.app.models.models import GoalType

    # Print the available enum values to debug
    print("Available GoalType values:", [e.name for e in GoalType])

    # Use the first enum value instead of hardcoding "emergency"
    goal_type = GoalType.EMERGENCY

    goal_data = FinancialGoalCreate(
        couple_id=test_couple.id,
        name="Service Test Goal",
        target_amount=7500.0,
        type=goal_type,
        priority=1,
        deadline=date(2023, 12, 31),
        notes="Test goal for the service layer"
    )
    goal = create_financial_goal(db_session, goal_data)
    
    assert goal.id is not None
    assert goal.couple_id == test_couple.id
    assert goal.name == "Service Test Goal"
    assert goal.target_amount == 7500.0
    assert goal.current_allocation == 0.0

def test_create_goal_nonexistent_couple(db_session):
    """Test that creating a goal for a non-existent couple raises an error"""
    # Check the real enum values
    from backend.app.models.models import GoalType

    # Print the available enum values to debug
    print("Available GoalType values:", [e.name for e in GoalType])

    # Use the first enum value instead of hardcoding "emergency"
    goal_type = GoalType.EMERGENCY

    goal_data = FinancialGoalCreate(
        couple_id="nonexistent-id",
        name="Invalid Goal",
        target_amount=5000.0,
        type=goal_type,
        priority=1
    )
    
    with pytest.raises(Exception) as excinfo:
        create_financial_goal(db_session, goal_data)
    assert "not found" in str(excinfo.value)

def test_get_goals_by_couple(db_session, test_couple):
    """Test retrieving goals for a couple"""
    # Create a couple of test goals
    from backend.app.models.models import FinancialGoal
    from uuid import uuid4
    
    # Check the real enum values
    from backend.app.models.models import GoalType

    # Print the available enum values to debug
    print("Available GoalType values:", [e.name for e in GoalType])

    # Use the first enum value instead of hardcoding "emergency"
    goal_type = GoalType.EMERGENCY

    goal1 = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_couple.id,
        name="First Goal",
        target_amount=5000.0,
        type=goal_type,
        current_allocation=0.0,
        priority=1
    )
    goal2 = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_couple.id,
        name="Second Goal",
        target_amount=10000.0,
        type=GoalType.VACATION,
        current_allocation=0.0,
        priority=2
    )
    db_session.add(goal1)
    db_session.add(goal2)
    db_session.commit()
    
    # Get goals
    goals = get_goals_by_couple(db_session, test_couple.id)
    
    assert len(goals) == 2
    goal_names = [g.name for g in goals]
    assert "First Goal" in goal_names
    assert "Second Goal" in goal_names

def test_allocate_to_goal(db_session, test_user, test_account, test_goal):
    """Test allocating funds to a goal"""
    allocation_data = GoalAllocation(
        account_id=test_account.id,
        goal_id=test_goal.id,
        amount=1000.0
    )
    
    updated_goal = allocate_to_goal(db_session, allocation_data, test_user.id)
    
    assert updated_goal.current_allocation == 1000.0
    
    # Verify the allocation was created
    from backend.app.models.models import AllocationMap
    allocation = db_session.query(AllocationMap).filter(
        AllocationMap.goal_id == test_goal.id,
        AllocationMap.account_id == test_account.id
    ).first()
    
    assert allocation is not None
    assert allocation.allocated_amount == 1000.0
    
    # Verify the ledger event was created
    from backend.app.models.models import LedgerEvent
    event = db_session.query(LedgerEvent).filter(
        LedgerEvent.source_account_id == test_account.id,
        LedgerEvent.dest_goal_id == test_goal.id
    ).first()
    
    assert event is not None
    assert event.amount == 1000.0

def test_allocate_to_goal_insufficient_funds(db_session, test_user, test_account, test_goal):
    """Test that allocating more funds than available raises an error"""
    # Create an initial allocation that uses most of the funds
    from backend.app.models.models import AllocationMap, FinancialGoal, GoalType
    from uuid import uuid4
    
    # Create a second goal
    second_goal = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_goal.couple_id,
        name="Second Goal",
        target_amount=10000.0,
        type=GoalType.EMERGENCY,
        current_allocation=9000.0,
        priority=2
    )
    db_session.add(second_goal)
    
    # Allocate most of the account balance to the second goal
    allocation = AllocationMap(
        id=str(uuid4()),
        goal_id=second_goal.id,
        account_id=test_account.id,
        allocated_amount=9000.0
    )
    db_session.add(allocation)
    db_session.commit()
    
    # Try to allocate more than is available
    allocation_data = GoalAllocation(
        account_id=test_account.id,
        goal_id=test_goal.id,
        amount=2000.0  # Only 1000 available (10000 balance - 9000 allocated)
    )
    
    with pytest.raises(Exception) as excinfo:
        allocate_to_goal(db_session, allocation_data, test_user.id)
    assert "Insufficient" in str(excinfo.value)

# API layer tests
def test_create_goal_api(client, test_couple):
    """Test goal creation through the API"""
    response = client.post(
        "/api/v1/goals/",
        json={
            "couple_id": test_couple.id,
            "name": "API Test Goal",
            "target_amount": 8000.0,
            "type": "emergency",  # String value matches what's defined in the enum
            "priority": 1,
            "deadline": "2023-12-31",
            "notes": "Test goal created through API"
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["couple_id"] == test_couple.id
    assert data["name"] == "API Test Goal"
    assert data["target_amount"] == 8000.0
    assert data["current_allocation"] == 0.0

def test_get_goals_api(client, test_couple, test_goal):
    """Test getting goals through the API"""
    response = client.get(f"/api/v1/goals/?couple_id={test_couple.id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 1
    assert any(goal["name"] == "Test Goal" for goal in data)

def test_allocate_funds_api(client, test_user, test_account, test_goal):
    """Test allocating funds through the API"""
    response = client.post(
        f"/api/v1/goals/allocate?user_id={test_user.id}",
        json={
            "account_id": test_account.id,
            "goal_id": test_goal.id,
            "amount": 1500.0
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_goal.id
    assert data["current_allocation"] == 1500.0 