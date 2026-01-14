"""
Metrics API endpoint for dashboard statistics.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.db.repositories import ApplicationRepository
from app.db.supabase import get_db
from app.models import Application
from typing import Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def get_metrics(db: Session = Depends(get_db)) -> Dict[str, int]:
    """
    Get dashboard metrics from real application data.
    
    Returns:
        {
            "total": int,
            "active": int,
            "interviewing": int,
            "offers": int
        }
    """
    try:
        repo = ApplicationRepository(db)
        
        # Get all applications
        all_apps = repo.list_applications()
        
        # Calculate metrics from real data
        total = len(all_apps)
        
        # Active = applications that are not rejected, ghosted, or accepted/offer
        active_statuses = ["Applied", "Screening", "Assessment", "Interview", "Interview (R1)", "Interview (R2)", "Interview (Final)"]
        active = sum(1 for app in all_apps if app.status in active_statuses and not app.ghosted)
        
        # Interviewing = applications with interview status
        interview_statuses = ["Interview", "Interview (R1)", "Interview (R2)", "Interview (Final)", "Screening"]
        interviewing = sum(1 for app in all_apps if app.status in interview_statuses)
        
        # Offers = applications with offer status
        offer_statuses = ["Offer", "Accepted", "Hired"]
        offers = sum(1 for app in all_apps if app.status in offer_statuses)
        
        return {
            "total": total,
            "active": active,
            "interviewing": interviewing,
            "offers": offers
        }
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}", exc_info=True)
        # Return zero metrics instead of 500 to prevent frontend breaking
        return {
            "total": 0,
            "active": 0,
            "interviewing": 0,
            "offers": 0
        }
