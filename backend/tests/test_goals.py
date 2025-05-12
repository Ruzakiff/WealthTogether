import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status, HTTPException
from datetime import date
import uuid

from backend.app.services.goal_service import (
    create_financial_goal, get_goals_by_couple, allocate_to_goal, 
    update_financial_goal, forecast_goal_completion, batch_reallocate_goals, 
    reallocate_between_goals, suggest_goal_rebalance
)
from backend.app.schemas.goals import FinancialGoalCreate, GoalAllocation, FinancialGoalUpdate
from backend.app.models.models import GoalType

# Service layer tests
def test_create_goal_service(db_session, test_couple, test_user):
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
        notes="Test goal for the service layer",
        created_by=test_user.id
    )
    created_goal = create_financial_goal(db_session, goal_data)
    
    assert created_goal.id is not None
    assert created_goal.name == "Service Test Goal"
    assert created_goal.target_amount == 7500.0
    assert created_goal.type == goal_type
    assert created_goal.current_allocation == 0.0

def test_create_goal_nonexistent_couple(db_session, test_user):
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
        priority=1,
        created_by=test_user.id
    )
    
    # Should raise 404 exception
    with pytest.raises(HTTPException) as excinfo:
        create_financial_goal(db_session, goal_data)
    
    assert excinfo.value.status_code == 404
    assert "not found" in str(excinfo.value.detail)

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
def test_create_goal_api(client, test_couple, test_user):
    """Test goal creation through the API"""
    from backend.app.models.models import GoalType
    
    # Print the GoalType enum values to understand what's accepted
    print(f"Available GoalType values: {[t.name for t in GoalType]}")
    
    response = client.post(
        "/api/v1/goals/",
        json={
            "couple_id": test_couple.id,
            "name": "API Test Goal",
            "target_amount": 8000.0,
            "type": GoalType.EMERGENCY.value,  # Use the enum value, not name
            "priority": 1,
            "deadline": "2023-12-31",
            "notes": "Test goal created through API",
            "created_by": test_user.id
        }
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "API Test Goal"
    assert data["target_amount"] == 8000.0

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

def test_update_goal_service(db_session, test_goal):
    """Test updating a goal at the service layer"""
    from backend.app.services.goal_service import update_financial_goal
    from backend.app.schemas.goals import FinancialGoalUpdate
    
    update_data = FinancialGoalUpdate(
        name="Updated Goal Name",
        target_amount=12000.0,
        priority=2
    )
    
    updated_goal = update_financial_goal(db_session, test_goal.id, update_data)
    
    assert updated_goal.id == test_goal.id
    assert updated_goal.name == "Updated Goal Name"
    assert updated_goal.target_amount == 12000.0
    assert updated_goal.priority == 2

def test_update_goal_api(client, test_goal):
    """Test updating a goal through the API"""
    response = client.put(
        f"/api/v1/goals/{test_goal.id}",
        json={
            "name": "API Updated Goal",
            "target_amount": 15000.0,
            "priority": 1
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_goal.id
    assert data["name"] == "API Updated Goal"
    assert data["target_amount"] == 15000.0
    assert data["priority"] == 1

def test_update_nonexistent_goal(client):
    """Test error handling when updating a nonexistent goal"""
    nonexistent_id = str(uuid.uuid4())
    response = client.put(
        f"/api/v1/goals/{nonexistent_id}",
        json={
            "name": "This Goal Doesn't Exist",
            "target_amount": 5000.0
        }
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_invalid_goal_type(client, test_couple):
    """Test handling of invalid goal type"""
    response = client.post(
        "/api/v1/goals/",
        json={
            "couple_id": test_couple.id,
            "name": "Invalid Type Goal",
            "target_amount": 5000.0,
            "type": "not_a_valid_type",  # Invalid type
            "priority": 1,
            "created_by": "user_id"
        }
    )
    
    # Should return validation error
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_negative_allocation(client, test_user, test_account, test_goal):
    """Test handling of negative allocation amount"""
    response = client.post(
        f"/api/v1/goals/allocate?user_id={test_user.id}",
        json={
            "account_id": test_account.id,
            "goal_id": test_goal.id,
            "amount": -500.0  # Negative amount
        }
    )
    
    # Should return validation error
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_forecast_goal_completion(db_session, test_goal):
    """Test goal completion forecasting"""
    from backend.app.services.goal_service import forecast_goal_completion
    
    # Set up test goal with some allocation and target
    test_goal.current_allocation = 2000.0
    test_goal.target_amount = 10000.0
    db_session.commit()
    
    # Test with monthly contribution of $500
    forecast = forecast_goal_completion(db_session, test_goal.id, 500.0)
    
    # Verify forecast structure and basic math
    assert "goal_id" in forecast
    assert "current_allocation" in forecast
    assert "target_amount" in forecast
    assert "monthly_contribution" in forecast
    assert "months_to_completion" in forecast
    assert "projected_completion_date" in forecast
    
    # Basic validation of calculation
    # (10000 - 2000) / 500 = 16 months
    assert forecast["months_to_completion"] == 16

def test_forecast_goal_api(client, test_goal):
    """Test goal forecasting through API"""
    # Monthly contribution is now a query parameter instead of in the body
    response = client.post(
        f"/api/v1/goals/{test_goal.id}/forecast?monthly_contribution=800.0"
    )
    
    assert response.status_code == status.HTTP_200_OK
    forecast = response.json()
    assert forecast["goal_id"] == test_goal.id
    assert "months_to_completion" in forecast
    assert "projected_completion_date" in forecast

def test_batch_reallocation(db_session, test_user, test_couple):
    """Test batch reallocation between goals"""
    from backend.app.models.models import FinancialGoal, GoalType
    from uuid import uuid4
    
    # Create multiple goals with allocations
    goals = []
    for i in range(3):
        goal = FinancialGoal(
            id=str(uuid4()),
            couple_id=test_couple.id,
            name=f"Goal {i+1}",
            target_amount=5000.0,
            type=GoalType.EMERGENCY if i == 0 else GoalType.VACATION,
            current_allocation=2000.0 if i > 0 else 0,
            priority=i+1
        )
        goals.append(goal)
        db_session.add(goal)
    db_session.commit()
    
    # Define batch rebalance data
    rebalance_data = {
        "rebalance_id": str(uuid4()),
        "moves": [
            {
                "source_goal_id": goals[1].id,
                "dest_goal_id": goals[0].id,
                "amount": 500.0
            },
            {
                "source_goal_id": goals[2].id,
                "dest_goal_id": goals[0].id,
                "amount": 700.0
            }
        ]
    }
    
    # Perform batch reallocation
    result = batch_reallocate_goals(db_session, rebalance_data, test_user.id)
    
    # Verify results
    assert result["rebalance_id"] == rebalance_data["rebalance_id"]
    assert len(result["results"]) == 2
    assert result["total_amount"] == 1200.0
    
    # Verify goal balances were updated
    db_session.refresh(goals[0])
    db_session.refresh(goals[1])
    db_session.refresh(goals[2])
    
    assert goals[0].current_allocation == 1200.0  # 0 + 500 + 700
    assert goals[1].current_allocation == 1500.0  # 2000 - 500
    assert goals[2].current_allocation == 1300.0  # 2000 - 700

def test_batch_reallocation_api(client, test_user, test_couple, db_session):
    """Test batch reallocation through API"""
    from backend.app.models.models import FinancialGoal, GoalType
    import uuid
    
    # Create goals with allocation
    source_goal_1 = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Source Goal 1",
        target_amount=5000.0,
        type=GoalType.VACATION,
        current_allocation=1000.0,
        priority=2
    )
    
    source_goal_2 = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Source Goal 2",
        target_amount=3000.0,
        type=GoalType.CUSTOM,
        current_allocation=800.0,
        priority=3
    )
    
    dest_goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Destination Goal",
        target_amount=10000.0,
        type=GoalType.EMERGENCY,
        current_allocation=0.0,
        priority=1
    )
    
    db_session.add(source_goal_1)
    db_session.add(source_goal_2)
    db_session.add(dest_goal)
    db_session.commit()
    
    # Print debug info
    print(f"Source goal 1 ID: {source_goal_1.id}")
    print(f"Source goal 2 ID: {source_goal_2.id}")
    print(f"Destination goal ID: {dest_goal.id}")
    
    rebalance_id = str(uuid.uuid4())
    
    response = client.post(
        f"/api/v1/goals/rebalance/commit",
        params={"user_id": test_user.id},
        json={
            "rebalance_id": rebalance_id,
            "moves": [
                {
                    "source_goal_id": source_goal_1.id,
                    "dest_goal_id": dest_goal.id,
                    "amount": 300.0
                },
                {
                    "source_goal_id": source_goal_2.id,
                    "dest_goal_id": dest_goal.id,
                    "amount": 400.0
                }
            ]
        }
    )
    
    print(f"Response: {response.status_code}")
    print(f"Response body: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["rebalance_id"] == rebalance_id
    assert "results" in result
    assert "total_amount" in result

def test_goal_rebalance_suggestions(db_session, test_couple):
    """Test getting goal rebalance suggestions"""
    from backend.app.models.models import FinancialGoal, GoalType
    from uuid import uuid4
    
    # Create some goals with different priorities and allocations
    high_priority = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_couple.id,
        name="Emergency Fund",
        target_amount=10000.0,
        type=GoalType.EMERGENCY,
        current_allocation=1000.0,  # Underfunded high priority
        priority=1
    )
    
    medium_priority = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_couple.id,
        name="Home Repairs",
        target_amount=5000.0,
        type=GoalType.CUSTOM,  # Changed from HOME to CUSTOM
        current_allocation=4000.0,  # Well-funded medium priority
        priority=3
    )
    
    db_session.add(high_priority)
    db_session.add(medium_priority)
    db_session.commit()
    
    # Get rebalance suggestions
    suggestions = suggest_goal_rebalance(db_session, test_couple.id)
    
    # Verify suggestions
    assert len(suggestions) > 0
    # Check that there's a suggestion to move money from medium to high priority
    suggestion = next((s for s in suggestions 
                      if s["source_goal_id"] == medium_priority.id 
                      and s["dest_goal_id"] == high_priority.id), None)
    assert suggestion is not None
    assert suggestion["suggested_amount"] > 0

def test_goal_rebalance_api(client, test_couple):
    """Test getting goal rebalance suggestions through API"""
    response = client.get(f"/api/v1/goals/rebalance/suggest?couple_id={test_couple.id}")
    
    assert response.status_code == status.HTTP_200_OK
    suggestions = response.json()
    assert isinstance(suggestions, list)
    
    # If there are suggestions, verify their structure
    if suggestions:
        assert "source_goal_id" in suggestions[0]
        assert "dest_goal_id" in suggestions[0]
        assert "suggested_amount" in suggestions[0]

def test_reallocate_between_goals_service(db_session, test_user, test_goal):
    """Test reallocating funds between goals at the service layer"""
    from backend.app.models.models import FinancialGoal, GoalType
    from uuid import uuid4
    
    # Create a second goal with some allocation
    second_goal = FinancialGoal(
        id=str(uuid4()),
        couple_id=test_goal.couple_id,
        name="Second Goal For Reallocation",
        target_amount=5000.0,
        type=GoalType.VACATION,
        current_allocation=2000.0,
        priority=2
    )
    db_session.add(second_goal)
    db_session.commit()
    
    # Test reallocation
    result = reallocate_between_goals(
        db_session,
        second_goal.id,  # source
        test_goal.id,    # destination
        1000.0,          # amount
        test_user.id     # user performing action
    )
    
    # Check results - now expects dictionaries instead of model objects
    source_goal = result["source_goal"]
    dest_goal = result["dest_goal"]
    
    # Use dictionary access instead of attribute access
    assert source_goal["current_allocation"] == 1000.0  # 2000 - 1000
    assert dest_goal["current_allocation"] == 1000.0    # 0 + 1000
    
    # Verify in database
    db_session.refresh(second_goal)
    db_session.refresh(test_goal)
    assert second_goal.current_allocation == 1000.0
    assert test_goal.current_allocation == 1000.0

def test_reallocate_through_api(client, test_user, test_goal, db_session):
    """Test reallocating funds between goals through the API"""
    from backend.app.models.models import FinancialGoal, GoalType
    import uuid
    
    # Create a source goal with allocation
    source_goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_goal.couple_id,
        name="Source Goal",
        target_amount=5000.0,
        type=GoalType.VACATION,
        current_allocation=2000.0,
        priority=2
    )
    
    db_session.add(source_goal)
    db_session.commit()
    db_session.refresh(source_goal)
    
    # Print debug info
    print(f"Source goal ID: {source_goal.id}")
    print(f"Destination goal ID: {test_goal.id}")
    
    response = client.post(
        f"/api/v1/goals/reallocate",
        params={"user_id": test_user.id},
        json={
            "source_goal_id": source_goal.id,
            "dest_goal_id": test_goal.id,
            "amount": 1000.0
        }
    )
    
    print(f"Response: {response.status_code}")
    print(f"Response body: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "source_goal" in data
    assert "dest_goal" in data
    assert data["source_goal"]["id"] == source_goal.id
    assert data["dest_goal"]["id"] == test_goal.id

def test_forecast_simulate_endpoint(client, test_goal):
    """Test the /forecast/simulate endpoint"""
    # Test the endpoint
    response = client.post(
        f"/api/v1/forecast/simulate?goal_id={test_goal.id}&monthly_contribution=600.0"
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["goal_id"] == test_goal.id
    assert data["monthly_contribution"] == 600.0
    assert "months_to_completion" in data
    assert "completion_date" in data
    assert "on_track" in data

def test_rebalance_suggest_endpoint(client, test_couple, test_user, db_session):
    """Test the /forecast/rebalance/suggest endpoint"""
    # Create multiple goals with different priorities
    from backend.app.models.models import FinancialGoal, GoalType
    import uuid
    
    # Create a high-priority goal with low allocation
    high_priority_goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="High Priority Goal",
        target_amount=10000.0,
        type=GoalType.EMERGENCY,
        current_allocation=1000.0,  # Only 10% funded
        priority=1  # Highest priority
    )
    
    # Create a low-priority goal with high allocation
    low_priority_goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Low Priority Goal",
        target_amount=5000.0,
        type=GoalType.VACATION,
        current_allocation=4000.0,  # 80% funded
        priority=3  # Lower priority
    )
    
    db_session.add_all([high_priority_goal, low_priority_goal])
    db_session.commit()
    
    # Test the endpoint
    response = client.get(
        f"/api/v1/forecast/rebalance/suggest?couple_id={test_couple.id}"
    )
    
    assert response.status_code == status.HTTP_200_OK
    suggestions = response.json()
    assert isinstance(suggestions, list)
    # At least one suggestion should be returned
    assert len(suggestions) > 0
    
    # Verify that first suggestion contains expected fields
    first_suggestion = suggestions[0]
    assert "source_goal_id" in first_suggestion
    assert "dest_goal_id" in first_suggestion
    assert "suggested_amount" in first_suggestion
    assert "reason" in first_suggestion

def test_rebalance_commit_endpoint(client, test_user, test_goal, db_session):
    """Test the /forecast/rebalance/commit endpoint"""
    # Create a source goal with allocation
    from backend.app.models.models import FinancialGoal, GoalType
    import uuid
    
    source_goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_goal.couple_id,
        name="Source Goal for Rebalance",
        target_amount=5000.0,
        type=GoalType.VACATION,
        current_allocation=2000.0,
        priority=3  # Lower priority
    )
    
    db_session.add(source_goal)
    db_session.commit()
    
    # Test the endpoint
    response = client.post(
        "/api/v1/forecast/rebalance/commit",
        json={
            "user_id": str(test_user.id),
            "from_goal_id": str(source_goal.id),
            "to_goal_id": str(test_goal.id),
            "amount": 1000.0
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Check the structure matches the actual response
    assert "source_goal" in data
    assert "dest_goal" in data
    assert data["source_goal"]["id"] == str(source_goal.id)
    assert data["dest_goal"]["id"] == str(test_goal.id)
    assert "amount" in data
    assert data["amount"] == 1000.0