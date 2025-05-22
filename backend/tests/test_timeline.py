import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from backend.app.models.models import (
    User, Couple, FinancialGoal, JournalEntry, GoalReaction, 
    LedgerEvent, LedgerEventType, JournalEntryType
)
from backend.app.schemas.timeline import TimelineItemType

# Add a fixture for the second test user
@pytest.fixture
def test_user2(db_session):
    """Create a second test user for timeline tests"""
    user = User(
        email="partner2@example.com",
        display_name="Partner Two"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def timeline_test_data(db_session, test_user, test_user2, test_couple, test_goal, test_account):
    """Create a variety of timeline-related test data"""
    
    # Create a few ledger events
    ledger_event1 = LedgerEvent(
        event_type=LedgerEventType.ALLOCATION,
        amount=100.0,
        user_id=test_user.id,
        dest_goal_id=test_goal.id,
        timestamp=datetime.utcnow() - timedelta(days=1),
        event_metadata={"note": "First allocation"}
    )
    
    # Make sure ledger_event2 is connected to the couple through the user
    # and add a source_account_id to ensure it's included in the queries
    ledger_event2 = LedgerEvent(
        event_type=LedgerEventType.DEPOSIT,
        amount=500.0,
        user_id=test_user2.id,
        source_account_id=test_account.id,
        timestamp=datetime.utcnow() - timedelta(days=2),
        event_metadata={"source": "Paycheck"}
    )
    
    # Create a journal entry
    journal_entry = JournalEntry(
        user_id=test_user.id,
        couple_id=test_couple.id,
        entry_type="reflection",
        content="I'm feeling good about our savings progress",
        is_private=False,
        timestamp=datetime.utcnow() - timedelta(days=3)
    )
    
    # Create a goal reaction
    goal_reaction = GoalReaction(
        user_id=test_user2.id,
        goal_id=test_goal.id,
        reaction_type="excited",
        note="We're making great progress!",
        timestamp=datetime.utcnow() - timedelta(days=4)
    )
    
    # Add to database
    db_session.add_all([ledger_event1, ledger_event2, journal_entry, goal_reaction])
    db_session.commit()
    
    # Refresh objects
    db_session.refresh(ledger_event1)
    db_session.refresh(ledger_event2)
    db_session.refresh(journal_entry)
    db_session.refresh(goal_reaction)
    
    # Return objects for test use
    return {
        "ledger_event1": ledger_event1,
        "ledger_event2": ledger_event2,
        "journal_entry": journal_entry,
        "goal_reaction": goal_reaction
    }

def test_get_timeline(client, test_couple, timeline_test_data):
    """Test getting the full timeline feed"""
    
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that we got all 4 items
    assert len(data) == 4
    
    # Verify the data structure of the first item
    item = data[0]  # Most recent item (ledger_event1)
    assert "id" in item
    assert "item_type" in item
    assert "timestamp" in item
    assert "title" in item
    assert "description" in item
    
    # Check that items are sorted by timestamp (newest first)
    timestamps = [item["timestamp"] for item in data]
    assert all(timestamps[i] >= timestamps[i+1] for i in range(len(timestamps)-1))

def test_get_timeline_with_filters(client, test_couple, test_user, test_goal, timeline_test_data):
    """Test getting the timeline with various filters"""
    
    # Test filtering by item type
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&item_types=ledger_event"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["item_type"] == TimelineItemType.LEDGER_EVENT for item in data)
    
    # Test filtering by user
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&user_id={test_user.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # ledger_event1 and journal_entry
    assert all(item["user_id"] == test_user.id for item in data)
    
    # Test filtering by goal
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&goal_id={test_goal.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # ledger_event1 and goal_reaction
    
    # Test filtering by date range
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).isoformat()
    one_day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
    
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&start_date={three_days_ago}&end_date={one_day_ago}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Includes ledger_event1 and ledger_event2 (excludes journal_entry from exactly 3 days ago due to time precision)

def test_get_timeline_with_pagination(client, test_couple, timeline_test_data):
    """Test timeline pagination"""
    
    # Test limit
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&limit=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Test offset
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&offset=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # We have 4 items total, offset 2 should return 2 items

def test_get_timeline_milestone_only(client, test_couple, db_session, test_user, test_goal):
    """Test getting only milestone events"""
    
    # Create a milestone event (goal completed)
    milestone_event = LedgerEvent(
        event_type=LedgerEventType.SYSTEM,
        amount=0.0,
        user_id=test_user.id,
        dest_goal_id=test_goal.id,
        timestamp=datetime.utcnow(),
        event_metadata={
            "action": "goal_milestone",
            "milestone_type": "complete",
            "percentage": 100
        }
    )
    db_session.add(milestone_event)
    db_session.commit()
    
    # Get only milestone events
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&milestone_only=true"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["is_milestone"] == True

def test_get_timeline_celebration_only(client, test_couple, db_session, test_user2, test_goal):
    """Test getting only celebration events"""
    
    # Create a celebration reaction
    celebration_reaction = GoalReaction(
        user_id=test_user2.id,
        goal_id=test_goal.id,
        reaction_type="love",
        note="Let's celebrate this amazing achievement!",
        timestamp=datetime.utcnow()
    )
    db_session.add(celebration_reaction)
    db_session.commit()
    
    # Get only celebration events
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&celebration_only=true"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1  # Should include the celebration reaction and potentially others
    assert all(item["is_celebration"] == True for item in data)

def test_timeline_includes_private_entries(client, test_couple, db_session, test_user):
    """Test that private journal entries are only included when requested"""
    
    # Create a private journal entry
    private_entry = JournalEntry(
        user_id=test_user.id,
        couple_id=test_couple.id,
        entry_type="concern",
        content="I'm worried about our spending habits",
        is_private=True,
        timestamp=datetime.utcnow()
    )
    db_session.add(private_entry)
    db_session.commit()
    
    # Without include_private flag
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    private_items = [item for item in data if 
                    item["item_type"] == TimelineItemType.JOURNAL_ENTRY and 
                    "is_private" in item["metadata"] and 
                    item["metadata"]["is_private"] == True]
    assert len(private_items) == 0
    
    # With include_private flag
    response = client.get(
        f"/api/v1/timeline/?couple_id={test_couple.id}&include_private=true"
    )
    
    assert response.status_code == 200
    data = response.json()
    private_items = [item for item in data if 
                    item["item_type"] == TimelineItemType.JOURNAL_ENTRY and 
                    "is_private" in item["metadata"] and 
                    item["metadata"]["is_private"] == True]
    assert len(private_items) == 1

def test_get_timeline_summary(client, test_couple, timeline_test_data):
    """Test getting the timeline summary"""
    
    response = client.get(
        f"/api/v1/timeline/summary?couple_id={test_couple.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check summary structure
    assert "period" in data
    assert "total_events" in data
    assert "type_breakdown" in data
    assert "participation" in data
    
    # Check counts
    assert data["total_events"] == 4
    assert TimelineItemType.LEDGER_EVENT in data["type_breakdown"]
    assert TimelineItemType.JOURNAL_ENTRY in data["type_breakdown"]
    assert TimelineItemType.GOAL_REACTION in data["type_breakdown"]
    
    # Check there are participation stats for both partners
    assert len(data["participation"]) == 2

def test_get_timeline_invalid_couple(client):
    """Test error when requesting timeline for non-existent couple"""
    
    fake_id = str(uuid.uuid4())
    response = client.get(
        f"/api/v1/timeline/?couple_id={fake_id}"
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_get_timeline_summary_invalid_couple(client):
    """Test error when requesting summary for non-existent couple"""
    
    fake_id = str(uuid.uuid4())
    response = client.get(
        f"/api/v1/timeline/summary?couple_id={fake_id}"
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower() 