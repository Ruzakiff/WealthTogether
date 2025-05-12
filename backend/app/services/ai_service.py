from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from backend.app.models.models import LedgerEvent, LedgerEventType, Couple

def generate_spending_insights(db: Session, couple_id: str, timeframe: str = "last_3_months") -> Dict[str, Any]:
    """
    Generate AI-powered insights from ledger data for a couple.
    
    Args:
        db: Database session
        couple_id: The ID of the couple to analyze
        timeframe: The period to analyze (e.g., "last_3_months", "last_year")
        
    Returns:
        Dictionary with trends, anomalies, and recommendations
    """
    # Verify the couple exists
    couple = db.query(Couple).filter(Couple.id == couple_id).first()
    if not couple:
        raise ValueError(f"Couple with id {couple_id} not found")
    
    # Define the time period to analyze
    end_date = datetime.now()
    if timeframe == "last_3_months":
        start_date = end_date - timedelta(days=90)
    elif timeframe == "last_6_months":
        start_date = end_date - timedelta(days=180)
    elif timeframe == "last_year":
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=90)  # Default to 3 months
    
    # Get all withdrawal events in the time period for this couple
    events = db.query(LedgerEvent).filter(
        ((LedgerEvent.user_id == couple.partner_1_id) |
         (LedgerEvent.user_id == couple.partner_2_id)) &
        (LedgerEvent.event_type == LedgerEventType.WITHDRAWAL) &
        (LedgerEvent.timestamp >= start_date) &
        (LedgerEvent.timestamp <= end_date)
    ).all()
    
    # Organize events by month and category
    monthly_category_totals = {}
    all_categories = set()
    
    for event in events:
        if not event.event_metadata:
            continue
        
        # Extract category from metadata
        category = event.event_metadata.get("category")
        if not category:
            continue
        
        # Use year-month as the key
        month_key = event.timestamp.strftime("%Y-%m")
        
        if month_key not in monthly_category_totals:
            monthly_category_totals[month_key] = {}
        
        if category not in monthly_category_totals[month_key]:
            monthly_category_totals[month_key][category] = 0
        
        monthly_category_totals[month_key][category] += event.amount
        all_categories.add(category)
    
    # Sort months chronologically
    sorted_months = sorted(monthly_category_totals.keys())
    
    # Calculate monthly average for each category
    category_averages = {}
    category_trends = {}
    
    for category in all_categories:
        values = []
        for month in sorted_months:
            if category in monthly_category_totals[month]:
                values.append((month, monthly_category_totals[month][category]))
        
        if len(values) >= 2:  # Need at least two months of data
            # Calculate average
            total = sum(amount for _, amount in values)
            avg = total / len(values)
            category_averages[category] = avg
            
            # Check for different trend patterns
            first_month_amount = values[0][1]
            last_month_amount = values[-1][1]
            
            # Calculate overall trend (first to last month)
            overall_change_pct = (last_month_amount - first_month_amount) / first_month_amount if first_month_amount > 0 else 0
            
            # Check for recent spike (if we have at least 3 months of data)
            recent_spike = False
            if len(values) >= 3:
                second_last_month = values[-2][1]
                last_month = values[-1][1]
                recent_change_pct = (last_month - second_last_month) / second_last_month if second_last_month > 0 else 0
                recent_spike = recent_change_pct > 0.2  # 20% increase in most recent month
            
            # Determine trend type
            if overall_change_pct > 0.2 or recent_spike:
                category_trends[category] = "increasing"
            elif overall_change_pct < -0.2:
                category_trends[category] = "decreasing"
            else:
                category_trends[category] = "stable"
    
    # Identify anomalies (unusually high spending in a category for a month)
    anomalies = []
    for month in monthly_category_totals:
        for category in monthly_category_totals[month]:
            if category in category_averages:
                month_amount = monthly_category_totals[month][category]
                avg_amount = category_averages[category]
                
                # If spending is 50% higher than average, flag as anomaly
                if month_amount > avg_amount * 1.5:
                    anomalies.append(
                        f"Spending in {category} was unusually high in {month} (${month_amount:.2f} vs. average of ${avg_amount:.2f})"
                    )
    
    # Generate trend insights
    trends = []
    for category, trend in category_trends.items():
        if trend == "increasing":
            trends.append(f"Spending on {category} has been increasing over the {timeframe}")
        elif trend == "decreasing":
            trends.append(f"Spending on {category} has been decreasing over the {timeframe}")
    
    # Generate recommendations
    recommendations = []
    
    # Recommend budget adjustments for increasing categories
    for category, trend in category_trends.items():
        if trend == "increasing":
            recommendations.append(f"Consider setting a budget for {category} to manage the increasing spending")
    
    # Recommend looking into anomalies
    if anomalies:
        recommendations.append("Review the unusual spending patterns identified in the anomalies section")
    
    # Recommend savings if there are categories with decreasing trends
    decreasing_categories = [cat for cat, trend in category_trends.items() if trend == "decreasing"]
    if decreasing_categories:
        recommendations.append(f"You've reduced spending in {', '.join(decreasing_categories)}. Consider allocating these savings to your goals.")
    
    return {
        "trends": trends,
        "anomalies": anomalies,
        "recommendations": recommendations,
        "timeframe": timeframe
    } 