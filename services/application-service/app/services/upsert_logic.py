from sqlalchemy.orm import Session
from app.db.repositories import ApplicationRepository
from app.services.status_rules import StatusPriority
from datetime import datetime

class UpsertLogic:
    def __init__(self, db: Session):
        self.repo = ApplicationRepository(db)
        self.db = db

    def process(self, 
                company_name: str, 
                role_title: str, 
                status: str, 
                confidence: float, 
                email_date: datetime):
        
        # 1. Deduplicate Company & Role
        company = self.repo.get_or_create_company(company_name)
        role = self.repo.get_or_create_role(company.id, role_title)
        
        # 2. Find Existing or Create New
        app = self.repo.upsert_application(
            company_id=company.id,
            role_id=role.id,
            status=status,
            confidence=confidence,
            email_date=email_date
        )
        
        # 3. If it already existed, we apply Logic
        if app.created_at != app.updated_at: # Simple check if it's not brand new (rough proxy)
             # Or more robustly check if we just created it.
             # Actually `upsert_application` above returns *existing* OR *new*.
             # If it was existing, we need to update it here.
             pass
             
        # Re-fetch or check logic
        # Status Priority Rule: rejected > interview > applied
        if StatusPriority.should_update(app.status, status):
            self.repo.update_application_status(app.id, StatusPriority.normalize(status))
            
        # Update Counts & Dates
        app.applied_count += 1 # Auto-increment on new email signal? Or strict logic?
        # Let's assume every ingest signal allows increment
        
        if not app.last_email_date or email_date > app.last_email_date:
            app.last_email_date = email_date
            
        if app.ghosted:
            app.ghosted = False
            
        self.db.commit()
        return app
