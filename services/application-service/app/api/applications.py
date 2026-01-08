from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.application import ApplicationResponse, ApplicationUpdate
from app.db.repository import ApplicationRepository
from app.utils.db_session import get_db
import uuid

router = APIRouter()

@router.get("/", response_model=List[ApplicationResponse])
def get_applications(
    status: Optional[str] = None,
    ghosted: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    repo = ApplicationRepository(db)
    apps = repo.get_applications(
        status=status, 
        ghosted=ghosted, 
        search=search, 
        limit=limit, 
        offset=offset
    )
    
    # Map to schema (doing manual mapping to be explicit, usually Pydantic handles this)
    results = []
    for app in apps:
        results.append(ApplicationResponse(
            id=app.id,
            company_name=app.company.name.title(), # capitalization for display
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
    app = repo.get_application_by_id(id)
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if update.status:
        app.status = update.status
    if update.ghosted is not None:
        app.ghosted = update.ghosted
    if update.resume_id:
        # TODO: verify resume exists
        app.resume_id = update.resume_id
        
    updated_app = repo.update_application(app)
    
    return ApplicationResponse(
        id=updated_app.id,
        company_name=updated_app.company.name.title(),
        role_title=updated_app.role.title,
        status=updated_app.status,
        applied_count=updated_app.applied_count,
        last_email_date=updated_app.last_email_date,
        ghosted=updated_app.ghosted,
        resume_url=updated_app.resume.storage_url if updated_app.resume else None
    )
