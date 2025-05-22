from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.app.models.models import (
    LedgerEvent, JournalEntry, GoalReaction, User, Couple, 
    FinancialGoal, BankAccount, LedgerEventType
)
from backend.app.schemas.timeline import TimelineItemResponse, TimelineFilter, TimelineItemType

def get_timeline_feed(
    db: Session, 
    filter_options: TimelineFilter,
    limit: int = 20, 
    offset: int = 0
) -> List[TimelineItemResponse]:
    """
    Generate a unified timeline feed combining ledger events, journal entries,
    and goal reactions with smart grouping and milestone identification.
    """
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == filter_options.couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {filter_options.couple_id} not found")
    
    # Initialize the timeline items list
    timeline_items = []
    
    # 1. Get ledger events
    if not filter_options.item_types or TimelineItemType.LEDGER_EVENT in filter_options.item_types:
        # Create query
        ledger_query = db.query(
            LedgerEvent, User.display_name.label("user_display_name")
        ).join(
            User, LedgerEvent.user_id == User.id
        )
        
        # Filter by couple (through goals and user accounts)
        couple_goals = db.query(FinancialGoal.id).filter(FinancialGoal.couple_id == filter_options.couple_id).subquery()
        
        # Fix: BankAccount doesn't have couple_id, so filter by user_id instead
        couple_user_ids = [couple.partner_1_id, couple.partner_2_id]
        couple_accounts = db.query(BankAccount.id).filter(BankAccount.user_id.in_(couple_user_ids)).subquery()
        
        ledger_query = ledger_query.filter(
            (LedgerEvent.dest_goal_id.in_(couple_goals)) | 
            (LedgerEvent.source_account_id.in_(couple_accounts)) |
            (LedgerEvent.user_id == couple.partner_1_id) |
            (LedgerEvent.user_id == couple.partner_2_id)
        )
        
        # Apply date filters if provided
        if filter_options.start_date:
            ledger_query = ledger_query.filter(LedgerEvent.timestamp >= filter_options.start_date)
        if filter_options.end_date:
            ledger_query = ledger_query.filter(LedgerEvent.timestamp <= filter_options.end_date)
            
        # Apply user filter if provided
        if filter_options.user_id:
            ledger_query = ledger_query.filter(LedgerEvent.user_id == filter_options.user_id)
            
        # Apply goal filter if provided
        if filter_options.goal_id:
            ledger_query = ledger_query.filter(LedgerEvent.dest_goal_id == filter_options.goal_id)
        
        # Execute query
        ledger_events = ledger_query.all()
        
        # Transform into timeline items
        for event, user_display_name in ledger_events:
            # Base item details
            item = {
                "id": f"ledger_{event.id}",
                "item_id": event.id,
                "item_type": TimelineItemType.LEDGER_EVENT,
                "timestamp": event.timestamp,
                "user_id": event.user_id,
                "user_display_name": user_display_name,
                "related_goal_id": event.dest_goal_id,
                "related_account_id": event.source_account_id,
                "is_milestone": False,
                "is_celebration": False,
                "metadata": event.event_metadata or {}
            }
            
            # Set details based on event type
            if event.event_type == LedgerEventType.ALLOCATION:
                item["title"] = "Goal Allocation"
                item["description"] = f"${event.amount:.2f} allocated to goal"
                item["icon"] = "💰"
                
            elif event.event_type == LedgerEventType.WITHDRAWAL:
                item["title"] = "Goal Withdrawal"
                item["description"] = f"${event.amount:.2f} withdrawn from goal"
                item["icon"] = "💸"
                
            elif event.event_type == LedgerEventType.DEPOSIT:
                item["title"] = "Account Deposit"
                item["description"] = f"${event.amount:.2f} deposited"
                item["icon"] = "📥"
                
            elif event.event_type == LedgerEventType.SYSTEM:
                # For system events, check the action in metadata
                action = event.event_metadata.get("action", "") if event.event_metadata else ""
                
                if action:
                    if action == "goal_created":
                        item["title"] = "New Goal Created"
                        item["description"] = f"Goal: {event.event_metadata.get('goal_name', 'Unknown')}"
                        item["icon"] = "🎯"
                        item["is_milestone"] = True
                    elif action == "goal_milestone":
                        item["title"] = "Goal Milestone"
                        milestone_type = event.event_metadata.get("milestone_type", "")
                        percentage = event.event_metadata.get("percentage", 0)
                        
                        if milestone_type == "complete":
                            item["description"] = "Goal completed! 🎉"
                        else:
                            item["description"] = f"Goal reached {percentage}% funded"
                        
                        item["icon"] = "🏆"
                        item["is_milestone"] = True
                        item["is_celebration"] = True
                    elif action == "batch_rebalance_complete":
                        item["title"] = "Goals Rebalanced"
                        item["description"] = f"Rebalanced {event.event_metadata.get('reallocation_count', 0)} goals"
                        item["icon"] = "⚖️"
                    elif "approval" in action:
                        item["title"] = "Approval Activity"
                        item["description"] = event.event_metadata.get("summary", "Approval action")
                        item["icon"] = "✅"
                    else:
                        item["title"] = "System Event"
                        item["description"] = "System event occurred"
                        item["icon"] = "🔄"
                else:
                    item["title"] = "System Event"
                    item["description"] = "System event occurred"
                    item["icon"] = "🔄"
            else:
                item["title"] = f"{event.event_type.capitalize()} Event"
                item["description"] = f"${event.amount:.2f} event"
                item["icon"] = "📝"
                
            # Add to timeline
            timeline_items.append(TimelineItemResponse(**item))
    
    # 2. Get journal entries
    if not filter_options.item_types or TimelineItemType.JOURNAL_ENTRY in filter_options.item_types:
        journal_query = db.query(
            JournalEntry, User.display_name.label("user_display_name")
        ).join(
            User, JournalEntry.user_id == User.id
        ).filter(
            JournalEntry.couple_id == filter_options.couple_id
        )
        
        # Only include private entries if specified
        if not filter_options.include_private:
            journal_query = journal_query.filter(JournalEntry.is_private == False)
            
        # Apply date filters if provided
        if filter_options.start_date:
            journal_query = journal_query.filter(JournalEntry.timestamp >= filter_options.start_date)
        if filter_options.end_date:
            journal_query = journal_query.filter(JournalEntry.timestamp <= filter_options.end_date)
            
        # Apply user filter if provided
        if filter_options.user_id:
            journal_query = journal_query.filter(JournalEntry.user_id == filter_options.user_id)
            
        # Apply goal filter if provided
        if filter_options.goal_id:
            journal_query = journal_query.filter(JournalEntry.goal_id == filter_options.goal_id)
        
        # Execute query
        journal_entries = journal_query.all()
        
        # Transform into timeline items
        for entry, user_display_name in journal_entries:
            # Set icon based on entry type
            icon = "📝"  # Default
            if entry.entry_type == "reflection":
                icon = "🤔"
            elif entry.entry_type == "celebration":
                icon = "🎉"
            elif entry.entry_type == "concern":
                icon = "😟"
                
            # Create timeline item
            item = {
                "id": f"journal_{entry.id}",
                "item_id": entry.id,
                "item_type": TimelineItemType.JOURNAL_ENTRY,
                "timestamp": entry.timestamp,
                "user_id": entry.user_id,
                "user_display_name": user_display_name,
                "related_goal_id": entry.goal_id,
                "related_account_id": None,
                "title": f"{entry.entry_type.capitalize()} Journal Entry",
                "description": entry.content[:100] + ("..." if len(entry.content) > 100 else ""),
                "icon": icon,
                "is_milestone": entry.entry_type == "celebration",
                "is_celebration": entry.entry_type == "celebration",
                "metadata": {
                    "full_content": entry.content,
                    "is_private": entry.is_private
                }
            }
            
            # Add to timeline
            timeline_items.append(TimelineItemResponse(**item))
    
    # 3. Get goal reactions
    if not filter_options.item_types or TimelineItemType.GOAL_REACTION in filter_options.item_types:
        reaction_query = db.query(
            GoalReaction, User.display_name.label("user_display_name"), FinancialGoal.name.label("goal_name")
        ).join(
            User, GoalReaction.user_id == User.id
        ).join(
            FinancialGoal, GoalReaction.goal_id == FinancialGoal.id
        ).filter(
            FinancialGoal.couple_id == filter_options.couple_id
        )
        
        # Apply date filters if provided
        if filter_options.start_date:
            reaction_query = reaction_query.filter(GoalReaction.timestamp >= filter_options.start_date)
        if filter_options.end_date:
            reaction_query = reaction_query.filter(GoalReaction.timestamp <= filter_options.end_date)
            
        # Apply user filter if provided
        if filter_options.user_id:
            reaction_query = reaction_query.filter(GoalReaction.user_id == filter_options.user_id)
            
        # Apply goal filter if provided
        if filter_options.goal_id:
            reaction_query = reaction_query.filter(GoalReaction.goal_id == filter_options.goal_id)
        
        # Execute query
        reactions = reaction_query.all()
        
        # Transform into timeline items
        for reaction, user_display_name, goal_name in reactions:
            # Map reaction types to emojis
            reaction_emoji = "👍"  # Default
            if reaction.reaction_type == "love":
                reaction_emoji = "❤️"
            elif reaction.reaction_type == "excited":
                reaction_emoji = "🎉"
            elif reaction.reaction_type == "proud":
                reaction_emoji = "🏆"
            elif reaction.reaction_type == "worried":
                reaction_emoji = "😟"
            
            # Create timeline item
            item = {
                "id": f"reaction_{reaction.id}",
                "item_id": reaction.id,
                "item_type": TimelineItemType.GOAL_REACTION,
                "timestamp": reaction.timestamp,
                "user_id": reaction.user_id,
                "user_display_name": user_display_name,
                "related_goal_id": reaction.goal_id,
                "related_account_id": None,
                "title": f"Reaction to {goal_name}",
                "description": reaction.note if reaction.note else f"Reacted with {reaction.reaction_type}",
                "icon": reaction_emoji,
                "is_milestone": False,
                "is_celebration": reaction.reaction_type in ["love", "excited", "proud"],
                "metadata": {
                    "reaction_type": reaction.reaction_type,
                    "goal_name": goal_name
                }
            }
            
            # Add to timeline
            timeline_items.append(TimelineItemResponse(**item))
    
    # Filter for milestones or celebrations if requested
    if filter_options.milestone_only:
        timeline_items = [item for item in timeline_items if item.is_milestone]
    if filter_options.celebration_only:
        timeline_items = [item for item in timeline_items if item.is_celebration]
    
    # Sort by timestamp descending (newest first)
    timeline_items.sort(key=lambda x: x.timestamp, reverse=True)
    
    # Apply pagination
    paginated_items = timeline_items[offset:offset + limit]
    
    return paginated_items


def get_timeline_summary(db: Session, couple_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Generate a summary of timeline activity for a specified period.
    
    Args:
        db: Database session
        couple_id: The ID of the couple to summarize
        days: Number of days to include in summary
        
    Returns:
        Dictionary with activity counts, participation stats, and highlights
    """
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get timeline items for the period
    filter_options = TimelineFilter(
        couple_id=couple_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    timeline_items = get_timeline_feed(db, filter_options, limit=100)
    
    # Count item types
    type_counts = {}
    for item in timeline_items:
        if item.item_type in type_counts:
            type_counts[item.item_type] += 1
        else:
            type_counts[item.item_type] = 1
    
    # Identify milestones
    milestones = [item for item in timeline_items if item.is_milestone]
    
    # Count user participation
    user_participation = {}
    for item in timeline_items:
        if item.user_id in user_participation:
            user_participation[item.user_id] += 1
        else:
            user_participation[item.user_id] = 1
    
    # Get couple details
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    partner1 = db.query(User).filter(User.id == couple.partner_1_id).first()
    partner2 = db.query(User).filter(User.id == couple.partner_2_id).first()
    
    # Create participation percentages
    total_items = len(timeline_items)
    partner1_participation = user_participation.get(partner1.id, 0) / total_items if total_items > 0 else 0
    partner2_participation = user_participation.get(partner2.id, 0) / total_items if total_items > 0 else 0
    
    # Return summary
    return {
        "period": f"Last {days} days",
        "total_events": total_items,
        "type_breakdown": type_counts,
        "milestone_count": len(milestones),
        "recent_milestones": [
            {
                "title": m.title,
                "description": m.description,
                "timestamp": m.timestamp,
                "type": m.item_type
            } for m in milestones[:5]  # Just the 5 most recent
        ],
        "participation": {
            partner1.display_name: f"{partner1_participation:.0%}",
            partner2.display_name: f"{partner2_participation:.0%}"
        },
        "has_journal_entries": TimelineItemType.JOURNAL_ENTRY in type_counts,
        "has_goal_reactions": TimelineItemType.GOAL_REACTION in type_counts
    }


def detect_milestones(db: Session, goal_id: str, allocation_amount: float = None) -> Optional[Dict[str, Any]]:
    """
    Detect if an allocation creates a milestone for a goal
    
    Args:
        db: Database session
        goal_id: ID of the goal to check
        allocation_amount: Optional amount that was allocated
        
    Returns:
        Dictionary with milestone details if a milestone was reached, None otherwise
    """
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        return None
        
    # Calculate percentage of goal achieved
    percentage = (goal.current_allocation / goal.target_amount) * 100 if goal.target_amount > 0 else 0
    
    # Check for milestone percentages
    milestone = None
    if 24 <= percentage < 26:  # ~25%
        milestone = {"type": "quarter", "percentage": 25}
    elif 49 <= percentage < 51:  # ~50%
        milestone = {"type": "half", "percentage": 50}
    elif 74 <= percentage < 76:  # ~75%
        milestone = {"type": "three_quarters", "percentage": 75}
    elif percentage >= 99:  # Goal achieved
        milestone = {"type": "complete", "percentage": 100}
        
    return milestone 