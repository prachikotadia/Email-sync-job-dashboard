from sqlalchemy.orm import Session
from app.models import Application, Resume, application_resumes
from typing import Optional
import uuid

class ResumeMatcher:
    def __init__(self, db: Session):
        self.db = db

    def link_resume_to_application(self, app_id: str, resume_id: str) -> bool:
        """
        Links a resume to an application.
        Updates the 'current' resume_id on the application and adds entry to history.
        """
        app = self.db.query(Application).filter(Application.id == app_id).first()
        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        
        if not app or not resume:
            return False
            
        # Update current pointer
        app.resume_id = resume.id
        
        # Ensure it's in history (if using M2M table)
        # Check if already linked
        # Note: SQLAlchemy M2M append might duplicate if not careful with list vs set, 
        # but pure append usually works if relationship is set up.
        # However, we defined `resume_history` as M2M.
        
        if resume not in app.resume_history:
            app.resume_history.append(resume)
            
        self.db.commit()
        return True
