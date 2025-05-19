import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from backend.app.models.models import User, Couple, FinancialGoal, JournalEntry, JournalEntryType

def test_create_journal_entry(client, test_user, test_couple):
    # Create an entry
    entry_data = {
        "user_id": test_user.id,
        "couple_id": test_couple.id,
        "entry_type": "reflection",
        "content": "I'm really happy with our progress on the emergency fund.",
        "is_private": False
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == entry_data["content"]
    assert data["entry_type"] == entry_data["entry_type"]
    assert data["user_id"] == test_user.id
    assert data["couple_id"] == test_couple.id
    assert "id" in data
    assert "timestamp" in data

def test_create_journal_entry_with_invalid_user(client, test_couple):
    # Create an entry with non-existent user
    invalid_user_id = str(uuid.uuid4())
    entry_data = {
        "user_id": invalid_user_id,
        "couple_id": test_couple.id,
        "entry_type": "reflection",
        "content": "This should fail",
        "is_private": False
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 404
    assert f"User with id {invalid_user_id} not found" in response.json()["detail"]

def test_create_journal_entry_with_invalid_couple(client, test_user):
    # Create an entry with non-existent couple
    invalid_couple_id = str(uuid.uuid4())
    entry_data = {
        "user_id": test_user.id,
        "couple_id": invalid_couple_id,
        "entry_type": "reflection",
        "content": "This should fail",
        "is_private": False
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 404
    assert f"Couple with id {invalid_couple_id} not found" in response.json()["detail"]

def test_create_journal_entry_with_user_not_in_couple(client, db_session):
    # Create test user and couple where user isn't part of the couple
    user = User(id=str(uuid.uuid4()), email="test@example.com", display_name="Test User")
    couple = Couple(
        id=str(uuid.uuid4()),
        partner_1_id=str(uuid.uuid4()),
        partner_2_id=str(uuid.uuid4())
    )
    
    db_session.add(user)
    db_session.add(couple)
    db_session.commit()
    
    entry_data = {
        "user_id": user.id,
        "couple_id": couple.id,
        "entry_type": "reflection",
        "content": "This should fail",
        "is_private": False
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 403
    assert "User does not belong to this couple" in response.json()["detail"]

def test_create_journal_entry_with_goal(client, db_session, test_user, test_couple):
    # Create a test goal
    goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Test Goal",
        target_amount=1000,
        current_allocation=0
    )
    db_session.add(goal)
    db_session.commit()
    
    # Create entry linked to goal
    entry_data = {
        "user_id": test_user.id,
        "couple_id": test_couple.id,
        "entry_type": "celebration",
        "content": "We're making progress on our goal!",
        "is_private": False,
        "goal_id": goal.id
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["goal_id"] == goal.id

def test_create_journal_entry_with_invalid_goal(client, test_user, test_couple):
    # Create entry with non-existent goal
    invalid_goal_id = str(uuid.uuid4())
    entry_data = {
        "user_id": test_user.id,
        "couple_id": test_couple.id,
        "entry_type": "concern",
        "content": "This should fail",
        "is_private": False,
        "goal_id": invalid_goal_id
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 404
    assert f"Goal with id {invalid_goal_id} not found" in response.json()["detail"]

def test_create_journal_entry_with_goal_from_different_couple(client, db_session, test_user, test_couple):
    # Create a goal for a different couple
    other_couple = Couple(
        id=str(uuid.uuid4()),
        partner_1_id=str(uuid.uuid4()),
        partner_2_id=str(uuid.uuid4())
    )
    db_session.add(other_couple)
    db_session.commit()
    
    goal = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=other_couple.id,
        name="Other Couple's Goal",
        target_amount=1000,
        current_allocation=0
    )
    db_session.add(goal)
    db_session.commit()
    
    # Try to create entry with goal from different couple
    entry_data = {
        "user_id": test_user.id,
        "couple_id": test_couple.id,
        "entry_type": "concern",
        "content": "This should fail",
        "is_private": False,
        "goal_id": goal.id
    }
    
    response = client.post(
        "/api/v1/journal/",
        json=entry_data
    )
    
    assert response.status_code == 403
    assert "Goal does not belong to this couple" in response.json()["detail"]

def test_get_journal_entries(client, db_session, test_user, test_couple):
    # Create some test entries
    entries = [
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content=f"Test entry {i}",
            is_private=(i % 2 == 0)  # Every other entry is private
        )
        for i in range(5)
    ]
    
    for entry in entries:
        db_session.add(entry)
    db_session.commit()
    
    # Get all entries (should exclude private ones by default)
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should only see non-private entries
    assert len(data) == 2
    
    # Include private entries (only works for own entries)
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}&include_private=true"
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should see all entries since user is requesting their own
    assert len(data) == 5

def test_partner_journal_entries_visibility(client, db_session):
    # Create partner users and couple
    partner1 = User(id=str(uuid.uuid4()), email="partner1@example.com", display_name="Partner 1")
    partner2 = User(id=str(uuid.uuid4()), email="partner2@example.com", display_name="Partner 2")
    
    couple = Couple(
        id=str(uuid.uuid4()),
        partner_1_id=partner1.id,
        partner_2_id=partner2.id
    )
    
    db_session.add_all([partner1, partner2, couple])
    db_session.commit()
    
    # Create entries by both partners, some private some not
    partner1_entries = [
        JournalEntry(
            id=str(uuid.uuid4()),
            user_id=partner1.id,
            couple_id=couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content=f"Partner 1 entry {i}",
            is_private=(i % 2 == 0)  # Entries 0, 2, 4 are private
        )
        for i in range(5)
    ]
    
    partner2_entries = [
        JournalEntry(
            id=str(uuid.uuid4()),
            user_id=partner2.id,
            couple_id=couple.id,
            entry_type=JournalEntryType.CONCERN,
            content=f"Partner 2 entry {i}",
            is_private=(i % 2 == 0)  # Entries 0, 2, 4 are private
        )
        for i in range(5)
    ]
    
    db_session.add_all(partner1_entries + partner2_entries)
    db_session.commit()
    
    # Partner 1 gets all entries - should see partner2's public entries and all of their own
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={partner1.id}&couple_id={couple.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # P1 should see all their own public entries and P2's public entries
    p1_entries = [e for e in data if e["user_id"] == partner1.id]
    p2_entries = [e for e in data if e["user_id"] == partner2.id]
    
    # Should see all their own public entries (2, 3)
    assert len(p1_entries) == 2
    # Should see partner's public entries (1, 3)
    assert len(p2_entries) == 2
    
    # Test include_private flag - should only include Partner 1's private entries
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={partner1.id}&couple_id={couple.id}&include_private=true"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    p1_entries = [e for e in data if e["user_id"] == partner1.id]
    p2_entries = [e for e in data if e["user_id"] == partner2.id]
    
    # Should see all their own entries (5)
    assert len(p1_entries) == 5
    # Should still only see partner's public entries (2)
    assert len(p2_entries) == 2
    
    # Test filtering by user - Partner 1 asking for Partner 2's entries
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={partner1.id}&user_id={partner2.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should only see Partner 2's public entries
    assert len(data) == 2
    assert all(e["user_id"] == partner2.id for e in data)
    assert all(e["is_private"] == False for e in data)

def test_filter_journal_entries_by_type(client, db_session, test_user, test_couple):
    # Create entries with different types
    entries = [
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="Reflection entry",
            is_private=False
        ),
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.CELEBRATION,
            content="Celebration entry",
            is_private=False
        ),
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.CONCERN,
            content="Concern entry",
            is_private=False
        )
    ]
    
    for entry in entries:
        db_session.add(entry)
    db_session.commit()
    
    # Filter by reflection type
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}&entry_type=reflection"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_type"] == "reflection"
    
    # Filter by celebration type
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}&entry_type=celebration"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entry_type"] == "celebration"

def test_filter_journal_entries_by_date(client, db_session, test_user, test_couple):
    # Create entries with different dates
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    entries = [
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="Today's entry",
            is_private=False,
            timestamp=today
        ),
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="Yesterday's entry",
            is_private=False,
            timestamp=yesterday
        ),
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="Week ago entry",
            is_private=False,
            timestamp=week_ago
        )
    ]
    
    for entry in entries:
        db_session.add(entry)
    db_session.commit()
    
    # Filter for entries from yesterday onwards
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}"
        f"&start_date={yesterday.isoformat()}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Today and yesterday
    
    # Filter for entries until yesterday
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}"
        f"&end_date={yesterday.isoformat()}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Yesterday and week ago
    
    # Filter for entries between specific dates
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}"
        f"&start_date={week_ago.isoformat()}&end_date={yesterday.isoformat()}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Yesterday and week ago

def test_filter_journal_entries_by_goal(client, db_session, test_user, test_couple):
    # Create test goals
    goal1 = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Goal 1",
        target_amount=1000,
        current_allocation=0
    )
    
    goal2 = FinancialGoal(
        id=str(uuid.uuid4()),
        couple_id=test_couple.id,
        name="Goal 2",
        target_amount=2000,
        current_allocation=0
    )
    
    db_session.add_all([goal1, goal2])
    db_session.commit()
    
    # Create entries linked to different goals
    entries = [
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="Goal 1 entry",
            is_private=False,
            goal_id=goal1.id
        ),
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="Goal 2 entry",
            is_private=False,
            goal_id=goal2.id
        ),
        JournalEntry(
            user_id=test_user.id,
            couple_id=test_couple.id,
            entry_type=JournalEntryType.REFLECTION,
            content="No goal entry",
            is_private=False
        )
    ]
    
    for entry in entries:
        db_session.add(entry)
    db_session.commit()
    
    # Filter by goal1
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}&goal_id={goal1.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["goal_id"] == goal1.id
    
    # Filter by goal2
    response = client.get(
        f"/api/v1/journal/?requesting_user_id={test_user.id}&couple_id={test_couple.id}&goal_id={goal2.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["goal_id"] == goal2.id

def test_get_single_journal_entry(client, db_session, test_user, test_couple):
    # Create a journal entry
    entry = JournalEntry(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        couple_id=test_couple.id,
        entry_type=JournalEntryType.REFLECTION,
        content="Test entry",
        is_private=False
    )
    
    db_session.add(entry)
    db_session.commit()
    
    # Get the entry by ID
    response = client.get(
        f"/api/v1/journal/{entry.id}?requesting_user_id={test_user.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == entry.id
    assert data["content"] == "Test entry"

def test_get_single_private_journal_entry(client, db_session, test_user, test_couple):
    # Create a private journal entry
    entry = JournalEntry(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        couple_id=test_couple.id,
        entry_type=JournalEntryType.CONCERN,
        content="Private entry",
        is_private=True
    )
    
    db_session.add(entry)
    db_session.commit()
    
    # Owner can access their private entry
    response = client.get(
        f"/api/v1/journal/{entry.id}?requesting_user_id={test_user.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == entry.id
    
    # Create partner with a unique email
    partner = User(id=str(uuid.uuid4()), email=f"partner_{uuid.uuid4()}@example.com", display_name="Partner")
    db_session.add(partner)
    
    # Update couple to include the partner
    test_couple.partner_2_id = partner.id
    db_session.commit()
    
    # Partner should not be able to access private entry
    response = client.get(
        f"/api/v1/journal/{entry.id}?requesting_user_id={partner.id}"
    )
    
    assert response.status_code == 403
    assert "This is a private journal entry" in response.json()["detail"]

def test_update_journal_entry(client, db_session, test_user):
    # Create a test entry
    entry = JournalEntry(
        user_id=test_user.id,
        couple_id="test-couple-id",
        entry_type=JournalEntryType.CELEBRATION,
        content="Original content"
    )
    db_session.add(entry)
    db_session.commit()
    
    # Update the entry
    update_data = {
        "content": "Updated content",
        "entry_type": "concern"
    }
    
    response = client.put(
        f"/api/v1/journal/{entry.id}?requesting_user_id={test_user.id}",
        json=update_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Updated content"
    assert data["entry_type"] == "concern"

def test_update_journal_entry_by_nonowner(client, db_session, test_user):
    # Create a test entry
    entry = JournalEntry(
        user_id=test_user.id,
        couple_id="test-couple-id",
        entry_type=JournalEntryType.CELEBRATION,
        content="Original content"
    )
    db_session.add(entry)
    
    # Create a different user
    other_user = User(id=str(uuid.uuid4()), email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    # Try to update entry as different user
    update_data = {
        "content": "This should fail",
        "entry_type": "concern"
    }
    
    response = client.put(
        f"/api/v1/journal/{entry.id}?requesting_user_id={other_user.id}",
        json=update_data
    )
    
    assert response.status_code == 403
    assert "Only the author can update a journal entry" in response.json()["detail"]

def test_update_journal_entry_change_privacy(client, db_session, test_user):
    # Create a test entry that's not private
    entry = JournalEntry(
        user_id=test_user.id,
        couple_id="test-couple-id",
        entry_type=JournalEntryType.REFLECTION,
        content="Public entry",
        is_private=False
    )
    db_session.add(entry)
    db_session.commit()
    
    # Change entry to private
    update_data = {
        "is_private": True
    }
    
    response = client.put(
        f"/api/v1/journal/{entry.id}?requesting_user_id={test_user.id}",
        json=update_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_private"] == True
    
    # Verify in database
    updated_entry = db_session.query(JournalEntry).filter(JournalEntry.id == entry.id).first()
    assert updated_entry.is_private == True

def test_delete_journal_entry(client, db_session, test_user):
    # Create a test entry
    entry = JournalEntry(
        user_id=test_user.id,
        couple_id="test-couple-id",
        entry_type=JournalEntryType.CONCERN,
        content="Entry to delete"
    )
    db_session.add(entry)
    db_session.commit()
    
    # Delete the entry
    response = client.delete(
        f"/api/v1/journal/{entry.id}?requesting_user_id={test_user.id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    # Verify it's deleted
    entry_check = db_session.query(JournalEntry).filter(JournalEntry.id == entry.id).first()
    assert entry_check is None

def test_delete_journal_entry_by_nonowner(client, db_session, test_user):
    # Create a test entry
    entry = JournalEntry(
        user_id=test_user.id,
        couple_id="test-couple-id",
        entry_type=JournalEntryType.CONCERN,
        content="Entry to delete"
    )
    db_session.add(entry)
    
    # Create a different user
    other_user = User(id=str(uuid.uuid4()), email="other@example.com", display_name="Other User")
    db_session.add(other_user)
    db_session.commit()
    
    # Try to delete as different user
    response = client.delete(
        f"/api/v1/journal/{entry.id}?requesting_user_id={other_user.id}"
    )
    
    assert response.status_code == 403
    assert "Only the author can delete a journal entry" in response.json()["detail"]
    
    # Verify entry still exists
    entry_check = db_session.query(JournalEntry).filter(JournalEntry.id == entry.id).first()
    assert entry_check is not None

def test_get_nonexistent_journal_entry(client, test_user):
    # Try to get a non-existent entry
    fake_id = str(uuid.uuid4())
    response = client.get(
        f"/api/v1/journal/{fake_id}?requesting_user_id={test_user.id}"
    )
    
    assert response.status_code == 404
    assert f"Journal entry with id {fake_id} not found" in response.json()["detail"]

def test_update_nonexistent_journal_entry(client, test_user):
    # Try to update a non-existent entry
    fake_id = str(uuid.uuid4())
    update_data = {
        "content": "This should fail",
    }
    
    response = client.put(
        f"/api/v1/journal/{fake_id}?requesting_user_id={test_user.id}",
        json=update_data
    )
    
    assert response.status_code == 404
    assert f"Journal entry with id {fake_id} not found" in response.json()["detail"]

def test_delete_nonexistent_journal_entry(client, test_user):
    # Try to delete a non-existent entry
    fake_id = str(uuid.uuid4())
    response = client.delete(
        f"/api/v1/journal/{fake_id}?requesting_user_id={test_user.id}"
    )
    
    assert response.status_code == 404
    assert f"Journal entry with id {fake_id} not found" in response.json()["detail"] 