from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.models import Application, Company, Role, StatusHistory, User
from typing import List, Optional
from datetime import datetime

class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_company(self, name: str) -> Company:
        normalized_name = name.lower().strip()
        company = self.db.execute(select(Company).where(Company.name == normalized_name)).scalar_one_or_none()
        if not company:
            company = Company(name=normalized_name)
            self.db.add(company)
            self.db.flush()
        return company

    def get_or_create_role(self, company_id: str, title: str) -> Role:
        normalized_title = title.lower().strip()
        role = self.db.execute(select(Role).where(
            Role.company_id == company_id, 
            Role.title == normalized_title
        )).scalar_one_or_none()
        
        if not role:
            role = Role(company_id=company_id, title=normalized_title)
            self.db.add(role)
            self.db.flush()
        return role

    def upsert_application(self, 
                           company_id: str, 
                           role_id: str, 
                           status: str, 
                           confidence: float = 0.0,
                           email_date: datetime = None) -> Application:
        
        app = self.db.execute(select(Application).where(
            Application.company_id == company_id,
            Application.role_id == role_id
        )).scalar_one_or_none()
        
        if app:
            # Update logic is handled by caller (UpsertLogic) usually, 
            # but repository just saves the object. 
            # We return existing to let Logic decide.
            return app
        else:
            new_app = Application(
                company_id=company_id,
                role_id=role_id,
                status=status,
                status_confidence=confidence,
                last_email_date=email_date or datetime.utcnow(),
                applied_count=1
            )
            self.db.add(new_app)
            self.db.commit()
            self.db.refresh(new_app)
            
            # Initial status history
            self.log_status_change(new_app.id, status, None)
            return new_app

    def update_application_status(self, app_id: str, new_status: str) -> Optional[Application]:
        app = self.db.execute(select(Application).where(Application.id == app_id)).scalar_one_or_none()
        if app and app.status != new_status:
            old_status = app.status
            app.status = new_status
            app.updated_at = datetime.utcnow()
            self.db.add(app)
            # Log history
            self.log_status_change(app_id, new_status, old_status)
            self.db.commit()
            self.db.refresh(app)
        return app
        
    def log_status_change(self, app_id: str, new_status: str, old_status: Optional[str]):
        history = StatusHistory(
            application_id=app_id,
            status=new_status,
            previous_status=old_status
        )
        self.db.add(history)

    def list_applications(self, user_id: Optional[str] = None, limit: int = 50) -> List[Application]:
        query = select(Application).order_by(desc(Application.last_email_date)).limit(limit)
        if user_id:
            query = query.where(Application.user_id == user_id)
        return self.db.execute(query).scalars().all()
    
    def get_by_id(self, app_id: str) -> Optional[Application]:
        return self.db.execute(select(Application).where(Application.id == app_id)).scalar_one_or_none()
