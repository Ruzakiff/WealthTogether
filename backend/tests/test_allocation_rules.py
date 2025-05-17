import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from backend.app.models.models import (
    AutoAllocationRule, 
    FinancialGoal,
    GoalType,
    User,
    Couple,
    BankAccount
)
from backend.app.schemas.allocation_rules import AutoAllocationRuleCreate, AllocationTrigger

# Add these fixture dependencies
@pytest.fixture
def test_allocation_rule(db_session, test_user, test_account, test_goal):
    """Fixture to create a test allocation rule"""
    rule = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=10.0,
        trigger="deposit",
        is_active=True
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule

def test_create_allocation_rule(client, db_session, test_user, test_account, test_goal):
    """Test creating a new auto allocation rule"""
    # Create rule
    rule_data = {
        "user_id": test_user.id,
        "source_account_id": test_account.id,
        "goal_id": test_goal.id,
        "percent": 25.5,
        "trigger": "deposit"
    }
    
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["percent"] == 25.5
    assert data["trigger"] == "deposit"
    assert data["is_active"] == True

def test_get_user_rules(client, db_session, test_user, test_account, test_goal, test_allocation_rule):
    """Test getting all allocation rules for a user"""
    # Get rules
    response = client.get(f"/api/v1/allocation-rules/?user_id={test_user.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["user_id"] == test_user.id
    assert data[0]["source_account_id"] == test_account.id
    assert data[0]["goal_id"] == test_goal.id

def test_update_allocation_rule(client, db_session, test_user, test_allocation_rule):
    """Test updating an allocation rule"""
    # Update the rule
    update_data = {
        "percent": 15.0,
        "is_active": False
    }
    
    response = client.put(
        f"/api/v1/allocation-rules/{test_allocation_rule.id}?user_id={test_user.id}", 
        json=update_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["percent"] == 15.0
    assert data["is_active"] == False

def test_delete_allocation_rule(client, db_session, test_user, test_allocation_rule):
    """Test deleting an allocation rule"""
    # Delete the rule
    response = client.delete(f"/api/v1/allocation-rules/{test_allocation_rule.id}?user_id={test_user.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    
    # Verify rule is gone
    deleted_rule = db_session.query(AutoAllocationRule).filter(
        AutoAllocationRule.id == test_allocation_rule.id
    ).first()
    assert deleted_rule is None

def test_execute_allocation_rule(client, db_session, test_user, test_account, test_goal):
    """Test executing an allocation rule"""
    # Update account balance to ensure we have funds
    test_account.balance = 1000.0
    db_session.commit()
    
    # Create a rule
    rule = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=10.0,
        trigger="deposit"
    )
    db_session.add(rule)
    db_session.commit()
    
    # Execute the rule with a specific deposit amount
    response = client.post(f"/api/v1/allocation-rules/execute/{rule.id}?deposit_amount=500.0")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["amount"] == 50.0  # 10% of 500
    
    # Check that goal allocation was updated
    db_session.refresh(test_goal)
    assert test_goal.current_allocation == 50.0

def test_execute_account_rules(client, db_session, test_user, test_account, test_goal, test_couple):
    """Test executing all rules for an account"""
    # Update account balance
    test_account.balance = 1000.0
    db_session.commit()
    
    # Create two rules for the same account
    rule1 = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=5.0,
        trigger="deposit"
    )
    
    # Create second goal for testing multiple rules
    goal2 = FinancialGoal(
        couple_id=test_couple.id,
        name="Second Test Goal",
        target_amount=2000.0,
        current_allocation=0.0,
        type=GoalType.CUSTOM
    )
    db_session.add(goal2)
    db_session.commit()
    db_session.refresh(goal2)
    
    rule2 = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=goal2.id,
        percent=10.0,
        trigger="deposit"
    )
    
    db_session.add(rule1)
    db_session.add(rule2)
    db_session.commit()
    
    # Execute all rules for this account
    execute_data = {
        "account_id": test_account.id,
        "deposit_amount": 1000.0
    }
    
    response = client.post(
        f"/api/v1/allocation-rules/execute-account?user_id={test_user.id}", 
        json=execute_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Calculate total allocated
    total_allocated = sum(item["amount"] for item in data if item["success"])
    
    # Should be 5% + 10% = 15% of 1000 = 150
    assert total_allocated == 150.0

def test_create_rule_with_schedule_trigger(client, db_session, test_user, test_account, test_goal):
    """Test creating an allocation rule with a 'schedule' trigger type"""
    rule_data = {
        "user_id": test_user.id,
        "source_account_id": test_account.id,
        "goal_id": test_goal.id,
        "percent": 15.0,
        "trigger": "schedule"
    }
    
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["trigger"] == "schedule"

def test_edge_case_percentages(client, db_session, test_user, test_account, test_goal):
    """Test edge cases for allocation percentages (0%, 100%)"""
    # Test with 0% (should be valid but won't allocate anything)
    rule_data = {
        "user_id": test_user.id,
        "source_account_id": test_account.id,
        "goal_id": test_goal.id,
        "percent": 0.0,
        "trigger": "deposit"
    }
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    assert response.status_code == 200
    
    # Test with 100% (valid, allocates everything)
    rule_data["percent"] = 100.0
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    assert response.status_code == 200
    
    # Test with invalid percentage (negative)
    rule_data["percent"] = -10.0
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    assert response.status_code == 422
    
    # Test with invalid percentage (over 100%)
    rule_data["percent"] = 110.0
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    assert response.status_code == 422

def test_inactive_rule_not_executed(client, db_session, test_user, test_account, test_goal):
    """Test that inactive rules are not executed"""
    # Update account balance
    test_account.balance = 1000.0
    db_session.commit()
    
    # Create an inactive rule
    rule = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=10.0,
        trigger="deposit",
        is_active=False
    )
    db_session.add(rule)
    db_session.commit()
    
    # Try to execute the rule
    response = client.post(f"/api/v1/allocation-rules/execute/{rule.id}?deposit_amount=500.0")
    
    assert response.status_code == 400  # Should fail because rule is inactive
    
    # Verify no allocation happened
    db_session.refresh(test_goal)
    assert test_goal.current_allocation == 0.0

def test_execute_rule_insufficient_funds(client, db_session, test_user, test_account, test_goal):
    """Test executing a rule when account has insufficient funds"""
    # Set account balance to a small amount
    test_account.balance = 10.0
    db_session.commit()
    
    # Create a rule
    rule = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=10.0,
        trigger="deposit"
    )
    db_session.add(rule)
    db_session.commit()
    
    # Try to execute with an amount larger than the balance
    response = client.post(f"/api/v1/allocation-rules/execute/{rule.id}?deposit_amount=5000.0")
    
    # Should still work but with a warning since deposit_amount is just for calculation
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 500.0  # 10% of 5000
    
    # Now try to execute account rules directly - this should check actual balances
    execute_data = {
        "account_id": test_account.id,
        "deposit_amount": 5000.0
    }
    
    response = client.post(
        f"/api/v1/allocation-rules/execute-account?user_id={test_user.id}", 
        json=execute_data
    )
    
    # This might fail or return an error message depending on how the endpoint is implemented
    # Assuming it returns a 400 with insufficient funds
    assert response.status_code == 400
    assert "insufficient" in response.json().get("detail", "").lower()

def test_rule_priority_ordering(client, db_session, test_user, test_account, test_goal, test_couple):
    """Test that rules are executed in the correct order when total percentage exceeds 100%"""
    # Update account balance
    test_account.balance = 1000.0
    db_session.commit()
    
    # Create a second goal
    goal2 = FinancialGoal(
        couple_id=test_couple.id,
        name="Priority Goal",
        target_amount=5000.0,
        current_allocation=0.0,
        type=GoalType.CUSTOM,
        priority=1  # Higher priority
    )
    db_session.add(goal2)
    db_session.commit()
    
    # Create rules with total allocation over 100%
    rule1 = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=goal2.id,
        percent=60.0,  # High priority goal gets 60%
        trigger="deposit"
    )
    
    rule2 = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=60.0,  # Lower priority goal also wants 60%
        trigger="deposit"
    )
    
    db_session.add(rule1)
    db_session.add(rule2)
    db_session.commit()
    
    # Execute all rules - should respect goal priorities
    execute_data = {
        "account_id": test_account.id,
        "deposit_amount": 1000.0
    }
    
    response = client.post(
        f"/api/v1/allocation-rules/execute-account?user_id={test_user.id}", 
        json=execute_data
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Based on priorities, high priority goal should get full allocation
    # and lower priority goal should get remaining (if any)
    high_priority_allocation = next(item["amount"] for item in data if item["goal_id"] == goal2.id)
    low_priority_allocation = next(item["amount"] for item in data if item["goal_id"] == test_goal.id)
    
    assert high_priority_allocation == 600.0  # 60% of 1000
    assert low_priority_allocation == 400.0  # Remaining 40% of 1000

def test_unauthorized_rule_access(client, db_session, test_user, test_account, test_goal):
    """Test that users cannot access or modify rules they don't own"""
    # Create another user
    other_user = User(email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    # Create a rule owned by test_user
    rule = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=10.0,
        trigger="deposit"
    )
    db_session.add(rule)
    db_session.commit()
    
    # Try to access with other_user
    response = client.get(f"/api/v1/allocation-rules/?user_id={other_user.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0  # Should be empty since other_user has no rules
    
    # Try to update with other_user
    update_data = {"percent": 20.0}
    response = client.put(
        f"/api/v1/allocation-rules/{rule.id}?user_id={other_user.id}", 
        json=update_data
    )
    assert response.status_code == 403  # Forbidden
    
    # Try to delete with other_user
    response = client.delete(f"/api/v1/allocation-rules/{rule.id}?user_id={other_user.id}")
    assert response.status_code == 403  # Forbidden

def test_account_ownership_validation(client, db_session, test_user, test_goal):
    """Test that users can only create rules for accounts they own"""
    # Create another user with their own account
    other_user = User(email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    other_account = BankAccount(
        user_id=other_user.id,
        name="Other Account",
        balance=1000.0,
        institution_name="Other Bank"
    )
    db_session.add(other_account)
    db_session.commit()
    
    # Try to create a rule using test_user but other_user's account
    rule_data = {
        "user_id": test_user.id,
        "source_account_id": other_account.id,  # Account belongs to other_user
        "goal_id": test_goal.id,
        "percent": 10.0,
        "trigger": "deposit"
    }
    
    response = client.post("/api/v1/allocation-rules/", json=rule_data)
    assert response.status_code == 403  # Forbidden - can't use someone else's account

def test_automatic_trigger_simulation(client, db_session, test_user, test_account, test_goal):
    """Test automatic execution of rules when a deposit event occurs (simulation)"""
    # Create a deposit-triggered rule
    rule = AutoAllocationRule(
        user_id=test_user.id,
        source_account_id=test_account.id,
        goal_id=test_goal.id,
        percent=15.0,
        trigger="deposit"
    )
    db_session.add(rule)
    db_session.commit()
    
    # Simulate a deposit event (in reality this would be triggered by a webhook or transaction import)
    deposit_data = {
        "account_id": test_account.id,
        "amount": 2000.0,
        "description": "Salary deposit"
    }
    
    # This would typically be an internal service call when a deposit is detected
    # but we'll simulate it with an API call
    response = client.post(
        f"/api/v1/transactions/simulate-deposit?user_id={test_user.id}", 
        json=deposit_data
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify the rule was triggered and correct amount allocated
    assert data["rules_executed"] == 1
    assert data["total_allocated"] == 300.0  # 15% of 2000
    
    # Check that goal allocation was updated
    db_session.refresh(test_goal)
    assert test_goal.current_allocation == 300.0 