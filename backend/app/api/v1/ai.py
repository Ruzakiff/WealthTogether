from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.app.services.ai_service import generate_spending_insights
from backend.app.database import get_db_session

router = APIRouter()

@router.get("/insights", response_model=Dict[str, Any])
async def get_ai_insights(
    couple_id: str = Query(..., description="The couple ID to analyze"),
    timeframe: str = Query("last_3_months", description="Timeframe to analyze (last_3_months, last_6_months, last_year)"),
    db: Session = Depends(get_db_session)
):
    """
    Get AI-generated insights about spending patterns and recommendations.
    
    - Analyzes spending by category over the specified timeframe
    - Detects trends (increasing/decreasing spending)
    - Identifies anomalies (unusually high spending)
    - Provides personalized recommendations
    """
    return generate_spending_insights(db, couple_id, timeframe) 