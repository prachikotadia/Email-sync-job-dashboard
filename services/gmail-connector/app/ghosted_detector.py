from sqlalchemy.orm import Session
from app.database import Application, User
from datetime import datetime, timedelta
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
    
    def _check_user(self, user_id: int, db: Session):
        """
        Check and update ghosted applications for a user
        """
        # Get all "applied" applications
        applied_apps = db.query(Application).filter(
            Application.user_id == user_id,
            Application.category == "applied"
        ).all()
        
        cutoff_date = datetime.utcnow() - timedelta(days=self.days)
        
        for app in applied_apps:
            # Check if application is old enough
            if app.received_at and app.received_at < cutoff_date:
                # Check if there's been any update (rejection, interview, offer)
                has_response = db.query(Application).filter(
                    Application.user_id == user_id,
                    Application.company_name == app.company_name,
                    Application.category.in_(["rejected", "interview", "offer", "accepted"])
                ).first()
                
                if not has_response:
                    # Mark as ghosted
                    app.category = "ghosted"
                    app.last_updated = datetime.utcnow()
                    logger.info(f"Marked application {app.id} as ghosted (no response after {self.days} days)")
        
        db.commit()
