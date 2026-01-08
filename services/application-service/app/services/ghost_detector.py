from sqlalchemy.orm import Session
from sqlalchemy import select, update, and_
from app.models import Application
from datetime import datetime, timedelta

class GhostDetector:
    def __init__(self, db: Session):
        self.db = db
        # 14-21 days as requested, picking 14 for strictness or make it configurable
        self.inactive_threshold_days = 14

    def run(self) -> int:
        """
        Marks applications as 'Ghosted' if:
        - No update for X days
        - Status is NOT 'Rejected', 'Offer', 'Hired'
        - Currently NOT 'Ghosted'
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.inactive_threshold_days)
        
        # Find candidates
        stmt = (
            update(Application)
            .where(
                and_(
                    Application.last_email_date < cutoff_date,
                    Application.ghosted == False,
                    Application.status.notin_(["Rejected", "Offer", "Hired", "Ghosted"])
                )
            )
            .values(ghosted=True)
        )
        
        result = self.db.execute(stmt)
        self.db.commit()
        
        return result.rowcount
