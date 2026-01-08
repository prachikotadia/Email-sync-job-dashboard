from sqlalchemy.orm import Session
from app.db.repository import ApplicationRepository
from app.db.models import Application
from app.services.status_rules import StatusPriority
from datetime import datetime

class DedupeService:
    def __init__(self, db: Session):
        self.repo = ApplicationRepository(db)

    def process_application(self, 
                            company_name: str, 
                            role_title: str, 
                            status: str, 
                            confidence: float, 
                            email_date: datetime) -> Application:
        
        # 1. Get or Create Company & Role
        company = self.repo.get_or_create_company(company_name)
        role = self.repo.get_or_create_role(company.id, role_title)
        
        # 2. Check for existing application
        app = self.repo.get_application(company.id, role.id)
        
        if app:
            # Update existing
            if StatusPriority.should_update(app.status, status):
                app.status = StatusPriority.normalize(status)
                app.status_confidence = confidence
            
            app.applied_count += 1
            if not app.last_email_date or email_date > app.last_email_date:
                app.last_email_date = email_date
            
            # Reset ghosted status if there's new activity
            if app.ghosted:
                app.ghosted = False
                
            return self.repo.update_application(app)
        else:
            # Create new
            new_app = Application(
                company_id=company.id,
                role_id=role.id,
                status=StatusPriority.normalize(status),
                status_confidence=confidence,
                last_email_date=email_date,
                applied_count=1
            )
            return self.repo.create_application(new_app)
