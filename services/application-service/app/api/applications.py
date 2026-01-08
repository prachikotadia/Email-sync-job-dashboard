from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.application import ApplicationResponse, ApplicationUpdate
from app.db.repositories import ApplicationRepository
from app.db.supabase import get_db
import uuid

router = APIRouter()

@router.get("/", response_model=List[ApplicationResponse])
def get_applications(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    # other filters...
):
    repo = ApplicationRepository(db)
    apps = repo.list_applications() 
    # Mappers...
    results = []
    for app in apps:
        results.append(ApplicationResponse(
            id=app.id,
            company_name=app.company.name.title(),
            role_title=app.role.title,
            status=app.status,
            applied_count=app.applied_count,
            last_email_date=app.last_email_date,
            ghosted=app.ghosted,
            resume_url=app.resume.storage_url if app.resume else None
        ))
    return results

@router.patch("/{id}", response_model=ApplicationResponse)
def update_application(id: uuid.UUID, update: ApplicationUpdate, db: Session = Depends(get_db)):
    repo = ApplicationRepository(db)
    # Logic to update
    if update.status:
        repo.update_application_status(str(id), update.status)
        
    app = repo.get_by_id(str(id))
    if not app:
        raise HTTPException(status_code=404, detail="Not found")
        
    return ApplicationResponse(
            id=app.id,
            company_name=app.company.name.title(),
            role_title=app.role.title,
            status=app.status,
            applied_count=app.applied_count,
            last_email_date=app.last_email_date,
            ghosted=app.ghosted,
            resume_url=app.resume.storage_url if app.resume else None
    )
