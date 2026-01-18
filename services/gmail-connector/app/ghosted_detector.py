from sqlalchemy.orm import Session
from app.database import Application, User
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

class GhostedDetector:
    """
    Time-based ghosted detection
    Moves applications to "ghosted" category after N days of no response
    """
    
    def __init__(self, days: int = 21):
        self.days = days
    
    def check_all_users(self, db: Session):
        """
        Background job to check all users for ghosted applications
        """
        logger.info("Starting ghosted detection check")
        
        users = db.query(User).all()
        
        for user in users:
            try:
                self._check_user(user.id, db)
            except Exception as e:
                logger.error(f"Error checking ghosted for user {user.id}: {e}")
        
        logger.info("Ghosted detection check complete")
    
    def _check_user(self, user_id, db: Session):
        """
        Check and update ghosted applications for a user
        Definition: Applied exists, no reply after N days (default 21),
        no rejection/interview/offer after that
        """
        # Get all "APPLIED" applications (uppercase per schema)
        applied_apps = db.query(Application).filter(
            Application.user_id == user_id,
            Application.category == "APPLIED"  # Uppercase per schema
        ).all()
        
        cutoff_date = datetime.utcnow(timezone.utc) - timedelta(days=self.days)
        
        ghosted_count = 0
        for app in applied_apps:
            # Check if application is old enough
            if app.received_at and app.received_at.replace(tzinfo=timezone.utc) < cutoff_date:
                # Check if there's been any update in the same thread/company
                # Look for rejection, interview, or offer for same company
                has_response = db.query(Application).filter(
                    Application.user_id == user_id,
                    Application.company_name == app.company_name,
                    Application.category.in_(["REJECTED", "INTERVIEW", "OFFER_ACCEPTED"])  # Uppercase
                ).first()
                
                if not has_response:
                    # Mark as ghosted
                    app.category = "GHOSTED"  # Uppercase per schema
                    app.last_updated = datetime.now(timezone.utc)
                    ghosted_count += 1
                    logger.info(f"Marked application {app.id} as GHOSTED (no response after {self.days} days)")
        
        if ghosted_count > 0:
            db.commit()
            logger.info(f"Updated {ghosted_count} applications to GHOSTED for user {user_id}")
