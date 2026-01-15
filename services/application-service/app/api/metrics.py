"""
Metrics API endpoint for dashboard statistics.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, select, or_
from app.db.repositories import ApplicationRepository
from app.db.supabase import get_db
from app.models import Application, Email
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def get_metrics(
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
) -> Dict[str, int]:
    """
    Get dashboard metrics from real application data.
    
    CRITICAL: Filters by user_id to show only the authenticated user's applications.
    Shows ALL applications for that user (no limit).
    
    Returns:
        {
            "total": int,
            "active": int,
            "interviewing": int,
            "offers": int
        }
    """
    try:
        import uuid
        repo = ApplicationRepository(db)
        
        # REQUIREMENT 9: Filter by user_id if provided
        user_id_uuid = None
        if x_user_id:
            try:
                user_id_uuid = uuid.UUID(x_user_id)
                logger.info(f"[METRICS] Filtering by user_id: {user_id_uuid}")
            except ValueError as e:
                logger.warning(f"Invalid X-User-ID header: {x_user_id}, error: {e}")
        else:
            logger.warning("[METRICS] No X-User-ID header provided - showing ALL applications (backward compatibility)")
        
        # Get ALL applications for the user (no limit)
        # CRITICAL: Pass limit=None explicitly to ensure NO LIMIT
        # Also include applications with NULL user_id for backward compatibility
        all_apps = repo.list_applications(user_id=str(user_id_uuid) if user_id_uuid else None, limit=None)
        
        # CRITICAL DEBUG: Log the actual count
        logger.info(f"🔍 [METRICS DEBUG] repo.list_applications returned {len(all_apps)} applications")
        logger.info(f"🔍 [METRICS DEBUG] user_id filter: {user_id_uuid or 'NONE (all users)'}")
        logger.info(f"🔍 [METRICS DEBUG] limit parameter: None (unlimited)")
        
        # Also check direct DB count for comparison
        from sqlalchemy import select, func, or_
        direct_count_query = select(func.count(Application.id))
        if user_id_uuid:
            direct_count_query = direct_count_query.where(
                or_(
                    Application.user_id == user_id_uuid,
                    Application.user_id.is_(None)  # Include NULL for backward compatibility
                )
            )
        direct_count = db.execute(direct_count_query).scalar() or 0
        logger.info(f"🔍 [METRICS DEBUG] Direct DB count (for comparison): {direct_count}")
        
        if len(all_apps) != direct_count:
            logger.error(f"❌ [METRICS DEBUG] MISMATCH: repo returned {len(all_apps)} but direct DB count is {direct_count}")
        
        # Calculate metrics from real data
        total = len(all_apps)
        logger.info(f"📊 [METRICS] Total applications for user {user_id_uuid or 'ALL'}: {total}")
        logger.info(f"📊 [METRICS] NO LIMIT applied - counted ALL applications")
        
        # Helper function to check if status matches (case-insensitive, partial match)
        def status_matches(app_status, status_list):
            if not app_status:
                return False
            app_status_lower = str(app_status).lower()
            return any(status.lower() in app_status_lower for status in status_list)
        
        # Active = applications that are not rejected, ghosted, or accepted/offer
        # Include all variations: Applied, Under_Review, Interview, etc.
        # Also count applications with None/null status as "Applied" (default)
        active_statuses = ["Applied", "Screening", "Assessment", "Interview", "Under_Review", "Under Review"]
        rejected_statuses = ["Rejected"]
        offer_statuses = ["Offer", "Accepted", "Hired", "Accepted/Offer"]
        
        active = 0
        for app in all_apps:
            app_status = app.status or "Applied"  # Default to "Applied" if None
            is_ghosted = app.ghosted or False
            
            # Count as active if:
            # - Status matches active statuses AND
            # - Not rejected AND
            # - Not offer AND
            # - Not ghosted
            if (status_matches(app_status, active_statuses) 
                and not status_matches(app_status, rejected_statuses)
                and not status_matches(app_status, offer_statuses)
                and not is_ghosted):
                active += 1
        
        # Interviewing = applications with interview status
        interview_statuses = ["Interview", "Screening"]
        interviewing = sum(1 for app in all_apps 
                          if app.status and status_matches(app.status, interview_statuses))
        
        # Offers = applications with offer status
        offers = sum(1 for app in all_apps 
                    if app.status and status_matches(app.status, offer_statuses))
        
        # CRITICAL: Also count total emails stored
        email_count_query = select(func.count(Email.id))
        if user_id_uuid:
            email_count_query = email_count_query.where(
                or_(
                    Email.user_id == user_id_uuid,
                    Email.user_id.is_(None)
                )
            )
        total_emails = db.execute(email_count_query).scalar() or 0
        
        logger.info(f"📊 [METRICS] Total emails stored: {total_emails}")
        logger.info(f"📊 [METRICS] Total applications: {total}")
        
        return {
            "total": total,
            "active": active,
            "interviewing": interviewing,
            "offers": offers,
            "total_emails": total_emails,  # NEW: Show email count
            "total_applications": total  # Explicit for clarity
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
