from sqlalchemy.orm import Session
from sqlalchemy import select, update, desc, or_
from app.db.models import Application, Company, Role, Resume, ApplicationEvent
from typing import List, Optional
from datetime import datetime

class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_company(self, name: str) -> Company:
        normalized_name = name.lower().strip()
        # Simple normalization rules could go here (e.g., removing Inc., Ltd.)
        
        company = self.db.execute(select(Company).where(Company.name == normalized_name)).scalar_one_or_none()
        if not company:
            company = Company(name=normalized_name)
            self.db.add(company)
            self.db.flush() # flush to get ID
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

    def get_application(self, company_id: str, role_id: str) -> Optional[Application]:
        return self.db.execute(select(Application).where(
            Application.company_id == company_id,
            Application.role_id == role_id
        )).scalar_one_or_none()

    def create_application(self, application: Application) -> Application:
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application

    def update_application(self, application: Application) -> Application:
        application.updated_at = datetime.utcnow()
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application

    def get_applications(self, 
                         status: Optional[str] = None, 
                         ghosted: Optional[bool] = None, 
                         search: Optional[str] = None,
                         limit: int = 50, 
                         offset: int = 0) -> List[Application]:
        
        query = select(Application).join(Company).join(Role).order_by(desc(Application.last_email_date))
        
        if status:
            query = query.where(Application.status == status)
        if ghosted is not None:
            query = query.where(Application.ghosted == ghosted)
        if search:
            search_term = f"%{search.lower()}%"
            query = query.where(or_(
                Company.name.ilike(search_term),
                Role.title.ilike(search_term)
            ))
            
        return self.db.execute(query.limit(limit).offset(offset)).scalars().all()

    def get_application_by_id(self, app_id: str) -> Optional[Application]:
        return self.db.execute(select(Application).where(Application.id == app_id)).scalar_one_or_none()

    def log_event(self, app_id: str, event_type: str, payload: dict = None):
        event = ApplicationEvent(
            application_id=app_id,
            event_type=event_type,
            raw_payload=payload
        )
        self.db.add(event)
        self.db.commit()

    def create_resume(self, resume: Resume) -> Resume:
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        return resume
