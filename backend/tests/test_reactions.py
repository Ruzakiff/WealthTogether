import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from backend.app.models.models import GoalReaction, FinancialGoal, User, GoalType
from backend.app.schemas.reactions import GoalReactionCreate, GoalReactionUpdate, ReactionType

def test_create_reaction(client, db_session, test_user, test_goal):
    """Test creating a new goal reaction"""
    reaction_data = {
        "user_id": test_user.id,
        "goal_id": test_goal.id,
        "reaction_type": "excited",
        "note": "We're making great progress!"
    }
    
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["goal_id"] == test_goal.id
    assert data["reaction_type"] == "excited"
    assert data["note"] == "We're making great progress!"
    
    # Check database
    db_reaction = db_session.query(GoalReaction).filter(GoalReaction.id == data["id"]).first()
    assert db_reaction is not None
    assert db_reaction.user_id == test_user.id

def test_get_reactions_by_goal(client, db_session, test_user, test_goal):
    """Test getting reactions filtered by goal"""
    # Create some reactions first
    reactions = [
        GoalReaction(
            user_id=test_user.id,
            goal_id=test_goal.id,
            reaction_type="happy",
            note="First note",
            timestamp=datetime.now(timezone.utc) - timedelta(days=2)
        ),
        GoalReaction(
            user_id=test_user.id,
            goal_id=test_goal.id,
            reaction_type="concerned",
            note="Second note",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1)
        )
    ]
    
    for reaction in reactions:
        db_session.add(reaction)
    db_session.commit()
    
    # Get reactions for the goal
    response = client.get(f"/api/v1/goals/reactions/?goal_id={test_goal.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 2
    # Most recent should be first due to ordering
    assert data[0]["reaction_type"] == "concerned"
    assert data[1]["reaction_type"] == "happy"

def test_update_reaction(client, db_session, test_user, test_goal):
    """Test updating a reaction"""
    # Create a reaction
    reaction = GoalReaction(
        user_id=test_user.id,
        goal_id=test_goal.id,
        reaction_type="happy",
        note="Original note"
    )
    db_session.add(reaction)
    db_session.commit()
    db_session.refresh(reaction)
    
    # Update the reaction
    update_data = {
        "reaction_type": "motivated",
        "note": "Updated note"
    }
    
    response = client.put(
        f"/api/v1/goals/reactions/{reaction.id}?user_id={test_user.id}", 
        json=update_data
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["reaction_type"] == "motivated"
    assert data["note"] == "Updated note"
    
    # Check database
    db_session.refresh(reaction)
    assert reaction.reaction_type == "motivated"
    assert reaction.note == "Updated note"

def test_delete_reaction(client, db_session, test_user, test_goal):
    """Test deleting a reaction"""
    # Create a reaction
    reaction = GoalReaction(
        user_id=test_user.id,
        goal_id=test_goal.id,
        reaction_type="happy",
        note="Will be deleted"
    )
    db_session.add(reaction)
    db_session.commit()
    db_session.refresh(reaction)
    
    # Delete the reaction
    response = client.delete(f"/api/v1/goals/reactions/{reaction.id}?user_id={test_user.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    
    # Check database
    db_reaction = db_session.query(GoalReaction).filter(GoalReaction.id == reaction.id).first()
    assert db_reaction is None

def test_unauthorized_update(client, db_session, test_user, test_couple):
    """Test that users can't update others' reactions"""
    # Create another user
    other_user = User(email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    # Create a goal
    goal = FinancialGoal(
        couple_id=test_couple.id,
        name="Test Goal",
        target_amount=1000.0,
        type=GoalType.CUSTOM
    )
    db_session.add(goal)
    db_session.commit()
    
    # Create a reaction from the other user
    reaction = GoalReaction(
        user_id=other_user.id,
        goal_id=goal.id,
        reaction_type="happy",
        note="Other user's reaction"
    )
    db_session.add(reaction)
    db_session.commit()
    
    # Try to update as test_user
    update_data = {
        "note": "Trying to change another user's reaction"
    }
    
    response = client.put(
        f"/api/v1/goals/reactions/{reaction.id}?user_id={test_user.id}", 
        json=update_data
    )
    assert response.status_code == 403  # Forbidden 

def test_unauthorized_delete(client, db_session, test_user, test_couple):
    """Test that users can't delete others' reactions"""
    # Create another user
    other_user = User(email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    # Create a goal
    goal = FinancialGoal(
        couple_id=test_couple.id,
        name="Test Goal",
        target_amount=1000.0,
        type=GoalType.CUSTOM
    )
    db_session.add(goal)
    db_session.commit()
    
    # Create a reaction from the other user
    reaction = GoalReaction(
        user_id=other_user.id,
        goal_id=goal.id,
        reaction_type="happy",
        note="Other user's reaction"
    )
    db_session.add(reaction)
    db_session.commit()
    
    # Try to delete as test_user
    response = client.delete(f"/api/v1/goals/reactions/{reaction.id}?user_id={test_user.id}")
    assert response.status_code == 403  # Forbidden

def test_get_reactions_by_user(client, db_session, test_user, test_goal):
    """Test getting reactions filtered by user"""
    # Create another user
    other_user = User(email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    # Create some reactions from different users
    reactions = [
        GoalReaction(
            user_id=test_user.id,
            goal_id=test_goal.id,
            reaction_type="happy",
            note="Test user's reaction",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1)
        ),
        GoalReaction(
            user_id=other_user.id,
            goal_id=test_goal.id,
            reaction_type="concerned",
            note="Other user's reaction",
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    for reaction in reactions:
        db_session.add(reaction)
    db_session.commit()
    
    # Get reactions for test_user
    response = client.get(f"/api/v1/goals/reactions/?user_id={test_user.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["user_id"] == test_user.id
    assert data[0]["reaction_type"] == "happy"

def test_get_single_reaction(client, db_session, test_user, test_goal):
    """Test getting a single reaction by ID"""
    # Create a reaction
    reaction = GoalReaction(
        user_id=test_user.id,
        goal_id=test_goal.id,
        reaction_type="happy",
        note="Test reaction"
    )
    db_session.add(reaction)
    db_session.commit()
    db_session.refresh(reaction)
    
    # Get the specific reaction
    response = client.get(f"/api/v1/goals/reactions/{reaction.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == reaction.id
    assert data["user_id"] == test_user.id
    assert data["goal_id"] == test_goal.id
    assert data["reaction_type"] == "happy"
    assert data["note"] == "Test reaction"

def test_invalid_reaction_type(client, test_user, test_goal):
    """Test validation of invalid reaction types"""
    reaction_data = {
        "user_id": test_user.id,
        "goal_id": test_goal.id,
        "reaction_type": "invalid_type",  # Invalid type
        "note": "This should fail validation"
    }
    
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    assert response.status_code == 422  # Unprocessable Entity

def test_empty_note_reaction(client, db_session, test_user, test_goal):
    """Test creating a reaction without a note"""
    reaction_data = {
        "user_id": test_user.id,
        "goal_id": test_goal.id,
        "reaction_type": "happy"
        # Note field is intentionally omitted
    }
    
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["goal_id"] == test_goal.id
    assert data["reaction_type"] == "happy"
    assert data["note"] is None or data["note"] == ""

def test_reaction_missing_required_fields(client, test_user, test_goal):
    """Test validation when required fields are missing"""
    # Missing goal_id
    reaction_data = {
        "user_id": test_user.id,
        "reaction_type": "happy",
        "note": "Missing goal_id"
    }
    
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    assert response.status_code == 422  # Unprocessable Entity
    
    # Missing user_id
    reaction_data = {
        "goal_id": test_goal.id,
        "reaction_type": "happy",
        "note": "Missing user_id"
    }
    
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    assert response.status_code == 422  # Unprocessable Entity
    
    # Missing reaction_type
    reaction_data = {
        "user_id": test_user.id,
        "goal_id": test_goal.id,
        "note": "Missing reaction_type"
    }
    
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    assert response.status_code == 422  # Unprocessable Entity

def test_reaction_timestamp(client, db_session, test_user, test_goal):
    """Test that timestamp is properly set when creating a reaction"""
    reaction_data = {
        "user_id": test_user.id,
        "goal_id": test_goal.id,
        "reaction_type": "happy",
        "note": "Testing timestamp"
    }
    
    # Create timezone-aware timestamps for comparison
    before_creation = datetime.now(timezone.utc)
    response = client.post("/api/v1/goals/reactions/", json=reaction_data)
    after_creation = datetime.now(timezone.utc)
    
    assert response.status_code == 200
    
    data = response.json()
    # Print the timestamp format for debugging
    timestamp_str = data["timestamp"]
    print(f"API response timestamp: {timestamp_str}")
    
    # Handle the unusual format with both +00:00 and Z
    if timestamp_str.endswith('Z'):
        if '+00:00' in timestamp_str:
            # Remove the Z if we already have +00:00
            timestamp_str = timestamp_str[:-1]
        else:
            # Replace Z with +00:00 if that's the only timezone info
            timestamp_str = timestamp_str.replace('Z', '+00:00')
    
    # Parse with timezone awareness explicitly
    reaction_time = datetime.fromisoformat(timestamp_str)
    
    # Ensure the parsed time has timezone info
    assert reaction_time.tzinfo is not None, "Parsed timestamp is not timezone-aware"
    
    # Now perform the comparison
    assert before_creation <= reaction_time <= after_creation
    
    # Check database
    db_reaction = db_session.query(GoalReaction).filter(GoalReaction.id == data["id"]).first()
    assert db_reaction is not None
    
    # Ensure database timestamp is timezone-aware before comparison
    db_timestamp = db_reaction.timestamp
    if db_timestamp.tzinfo is None:
        db_timestamp = db_timestamp.replace(tzinfo=timezone.utc)
    
    assert before_creation <= db_timestamp <= after_creation

def test_pagination_reactions(client, db_session, test_user, test_goal):
    """Test pagination for reactions"""
    # Create multiple reactions
    for i in range(15):  # Create 15 reactions
        reaction = GoalReaction(
            user_id=test_user.id,
            goal_id=test_goal.id,
            reaction_type="happy",
            note=f"Reaction {i}",
            timestamp=datetime.now(timezone.utc) - timedelta(days=i)
        )
        db_session.add(reaction)
    db_session.commit()
    
    # Test with explicit limit parameter
    response = client.get(f"/api/v1/goals/reactions/?goal_id={test_goal.id}&limit=10")
    assert response.status_code == 200
    first_page = response.json()
    assert len(first_page) == 10
    
    # Test second page
    response = client.get(f"/api/v1/goals/reactions/?goal_id={test_goal.id}&skip=10&limit=10")
    assert response.status_code == 200
    second_page = response.json()
    assert len(second_page) == 5
    
    # Test with custom limit
    response = client.get(f"/api/v1/goals/reactions/?goal_id={test_goal.id}&limit=5")
    assert response.status_code == 200
    custom_limit = response.json()
    assert len(custom_limit) == 5 