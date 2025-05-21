from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.app.models.models import LedgerEvent, User, BankAccount, FinancialGoal, Couple, LedgerEventType
from backend.app.schemas.ledger import LedgerEventCreate

def create_ledger_event(db: Session, event_data: LedgerEventCreate):
    """Service function to create a new ledger event"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == event_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {event_data.user_id} not found")
    
    # If source account is provided, verify it exists
    if event_data.source_account_id:
        source_account = db.query(BankAccount).filter(BankAccount.id == event_data.source_account_id).first()
        if not source_account:
            raise HTTPException(status_code=404, detail=f"Source account with id {event_data.source_account_id} not found")
    
    # If destination goal is provided, verify it exists
    if event_data.dest_goal_id:
        dest_goal = db.query(FinancialGoal).filter(FinancialGoal.id == event_data.dest_goal_id).first()
        if not dest_goal:
            raise HTTPException(status_code=404, detail=f"Destination goal with id {event_data.dest_goal_id} not found")
    
    # Create new ledger event
    new_event = LedgerEvent(
        event_type=event_data.event_type,
        amount=event_data.amount,
        source_account_id=event_data.source_account_id,
        dest_goal_id=event_data.dest_goal_id,
        user_id=event_data.user_id,
        event_metadata=event_data.event_metadata
    )
    
    # Add to database
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    return new_event

def get_user_ledger_events(db: Session, user_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for a specific user"""
    
    # Verify the user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    
    # Return events for this user with pagination
    return db.query(LedgerEvent).filter(LedgerEvent.user_id == user_id)\
        .order_by(LedgerEvent.timestamp.desc())\
        .offset(offset).limit(limit).all()

def get_couple_ledger_events(db: Session, couple_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for both partners in a couple"""
    
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Return events for either partner in this couple
    return db.query(LedgerEvent).filter(
        (LedgerEvent.user_id == couple.partner_1_id) |
        (LedgerEvent.user_id == couple.partner_2_id)
    ).order_by(LedgerEvent.timestamp.desc())\
      .offset(offset).limit(limit).all()

def get_account_ledger_events(db: Session, account_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for a specific account"""
    
    # Verify the account exists
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Account with id {account_id} not found")
    
    # Return events that involve this account
    return db.query(LedgerEvent).filter(
        LedgerEvent.source_account_id == account_id
    ).order_by(LedgerEvent.timestamp.desc())\
      .offset(offset).limit(limit).all()

def get_goal_ledger_events(db: Session, goal_id: str, limit: int = 100, offset: int = 0) -> List[LedgerEvent]:
    """Get ledger events for a specific goal"""
    
    # Verify the goal exists
    goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal with id {goal_id} not found")
    
    # Return events that involve this goal
    return db.query(LedgerEvent).filter(
        LedgerEvent.dest_goal_id == goal_id
    ).order_by(LedgerEvent.timestamp.desc())\
      .offset(offset).limit(limit).all()

def summarize_ledger_by_category(db: Session, couple_id: str, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Summarize ledger events by category for a couple
    
    Args:
        db: Database session
        couple_id: The couple ID to get events for
        from_date: Optional start date for filtering events
        to_date: Optional end date for filtering events
        
    Returns:
        List of dictionaries with category name and total amount
    """
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Get events for either partner in this couple with date filtering
    query = db.query(LedgerEvent).filter(
        (LedgerEvent.user_id == couple.partner_1_id) |
        (LedgerEvent.user_id == couple.partner_2_id)
    )
    
    if from_date:
        query = query.filter(LedgerEvent.timestamp >= from_date)
    if to_date:
        query = query.filter(LedgerEvent.timestamp <= to_date)
    
    events = query.all()
    
    # Group by category and sum amounts
    category_totals = {}
    for event in events:
        # Skip events without metadata or category info
        if not event.event_metadata:
            continue
            
        # Try to get category from metadata
        category = None
        if "category_id" in event.event_metadata and "category_name" in event.event_metadata:
            category = event.event_metadata["category_name"]
        elif "category" in event.event_metadata:
            category = event.event_metadata["category"]
        
        if not category:
            continue
            
        # Add to category total (withdrawals are positive for expense reporting)
        if event.event_type == LedgerEventType.WITHDRAWAL:
            amount = event.amount
        else:
            continue  # Only count withdrawals/expenses for category summaries
            
        if category in category_totals:
            category_totals[category] += amount
        else:
            category_totals[category] = amount
    
    # Convert to list of dictionaries
    result = [
        {"category_id": None, "category_name": category, "total_amount": amount}
        for category, amount in category_totals.items()
    ]
    
    return result


def calculate_monthly_surplus(db: Session, couple_id: str, year: int, month: int) -> Dict[str, float]:
    """
    Calculate monthly surplus (income minus expenses) for a couple
    
    Args:
        db: Database session
        couple_id: The couple ID to calculate surplus for
        year: The year to calculate for
        month: The month to calculate for (1-12)
        
    Returns:
        Dictionary with income, expenses, and surplus amounts
    """
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Calculate start and end dates for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    # Get events for either partner in this couple within the date range
    events = db.query(LedgerEvent).filter(
        ((LedgerEvent.user_id == couple.partner_1_id) |
         (LedgerEvent.user_id == couple.partner_2_id)) &
        (LedgerEvent.timestamp >= start_date) &
        (LedgerEvent.timestamp < end_date)
    ).all()
    
    # Calculate income and expenses
    income = 0.0
    expenses = 0.0
    
    for event in events:
        if event.event_type == LedgerEventType.DEPOSIT:
            income += event.amount
        elif event.event_type == LedgerEventType.WITHDRAWAL:
            expenses += event.amount
    
    # Calculate surplus
    surplus = income - expenses
    
    return {
        "income": income,
        "expenses": expenses,
        "surplus": surplus
    }

def get_spending_insights(db: Session, couple_id: str, 
                         start_date: datetime, end_date: datetime,
                         threshold_percent: int = 50) -> List[Dict[str, Any]]:
    """
    Analyze spending patterns to generate insights
    
    Args:
        db: Database session
        couple_id: Couple ID to analyze
        start_date: Start of analysis period
        end_date: End of analysis period
        threshold_percent: Threshold % change to flag as significant
        
    Returns:
        List of insight dictionaries with message, category, and percent change
    """
    # Verify couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise HTTPException(status_code=404, detail=f"Couple with id {couple_id} not found")
    
    # Find the midpoint to compare two equal time periods
    time_span = end_date - start_date
    midpoint = start_date + (time_span / 2)
    
    # Get all withdrawal events in the period
    events = db.query(LedgerEvent).filter(
        ((LedgerEvent.user_id == couple.partner_1_id) |
         (LedgerEvent.user_id == couple.partner_2_id)) &
        (LedgerEvent.event_type == LedgerEventType.WITHDRAWAL) &
        (LedgerEvent.timestamp >= start_date) &
        (LedgerEvent.timestamp <= end_date)
    ).all()
    
    # Group by category and by period (before/after midpoint)
    first_period = {}
    second_period = {}
    
    for event in events:
        # Skip events without metadata or category info
        if not event.event_metadata:
            continue
            
        # Get category from metadata
        category = None
        if "category_id" in event.event_metadata and "category_name" in event.event_metadata:
            category = event.event_metadata["category_name"]
        elif "category" in event.event_metadata:
            category = event.event_metadata["category"]
            
        if not category:
            continue
        
        # Add to appropriate period
        if event.timestamp < midpoint:
            if category in first_period:
                first_period[category] += event.amount
            else:
                first_period[category] = event.amount
        else:
            if category in second_period:
                second_period[category] += event.amount
            else:
                second_period[category] = event.amount
    
    # Generate insights by comparing the two periods
    insights = []
    
    for category, period2_amount in second_period.items():
        period1_amount = first_period.get(category, 0)
        
        # Skip if no data from first period or zero amount
        if period1_amount == 0:
            continue
            
        # Calculate percent change
        percent_change = ((period2_amount - period1_amount) / period1_amount) * 100
        
        # Generate insight if change exceeds threshold
        if abs(percent_change) >= threshold_percent:
            direction = "increase" if percent_change > 0 else "decrease"
            message = f"Your {category} spending had a significant {direction} of {abs(int(percent_change))}%"
            
            insights.append({
                "category": category,
                "message": message,
                "percent_change": percent_change,
                "period1_amount": period1_amount,
                "period2_amount": period2_amount
            })
    
    # Sort insights by absolute percent change (largest first)
    insights.sort(key=lambda x: abs(x["percent_change"]), reverse=True)
    
    return insights 