from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.db.models import Application
from app.config import settings
from datetime import datetime, timedelta

class GhostDetector:
    def __init__(self, db: Session):
        self.db = db

    def detect_and_mark_ghosted(self) -> int:
        """
        Scans for applications with no activity for N days and marks them as ghosted.
        Returns the number of applications updated.
        """
        threshold_date = datetime.utcnow() - timedelta(days=settings.GHOSTED_DAYS_THRESHOLD)
        
        # Query: Active apps (not Rejected, not Offered, not already ghosted)
        # whose last activity was before threshold
        
        stmt = (
            update(Application)
            .where(
                Application.last_email_date < threshold_date,
                Application.ghosted == False,
                Application.status.notin_(["Rejected", "Offer", "Ghosted"])
            )
            .values(ghosted=True, updated_at=datetime.utcnow())
        )
        
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount
