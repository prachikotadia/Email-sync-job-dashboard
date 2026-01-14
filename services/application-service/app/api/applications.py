from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.application import ApplicationResponse, ApplicationUpdate
from app.db.repositories import ApplicationRepository
from app.db.supabase import get_db
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[ApplicationResponse])
def get_applications(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
):
    """Get all applications with error handling."""
    try:
        repo = ApplicationRepository(db)
        apps = repo.list_applications()
        
        # Handle empty results gracefully
        if not apps:
            logger.info("No applications found in database")
            return []
        
        # Valid job application statuses - filter out anything else
        VALID_STATUSES = ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer", 
                         "Screening", "Interview (R1)", "Interview (R2)", "Interview (Final)",
                         "Offer", "Accepted", "Hired"]
        
        results = []
        filtered_count = 0
        for app in apps:
            try:
                # Get status and check if it's valid
                app_status = app.status or "Applied"
                
                # Check if status is valid (includes variations like "Interview R1", etc.)
                is_valid_status = (
                    app_status in VALID_STATUSES or
                    "Interview" in app_status or  # Allow any Interview variation
                    app_status in ["Offer", "Accepted", "Hired"]  # Allow offer variations
                )
                
                # FILTER OUT: Skip applications with invalid/Unknown statuses
                if not is_valid_status or app_status == "Unknown":
                    filtered_count += 1
                    logger.debug(f"Skipping application {app.id} - invalid status: '{app_status}'")
                    continue  # Don't show this application
                
                # Safely access relationships with null checks
                company_name = app.company.name.title() if app.company and app.company.name else "Unknown"
                role_title = app.role.title if app.role and app.role.title else "Unknown"
                resume_url = app.resume.storage_url if app.resume and app.resume.storage_url else None
                
                results.append(ApplicationResponse(
                    id=app.id,
                    company_name=company_name,
                    role_title=role_title,
                    status=app_status,
                    applied_count=app.applied_count or 0,
                    last_email_date=app.last_email_date,
                    ghosted=app.ghosted if app.ghosted is not None else False,
                    resume_url=resume_url
                ))
            except Exception as e:
                logger.error(f"Error processing application {app.id}: {e}", exc_info=True)
                # Skip this application but continue processing others
                continue
        
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} applications with invalid/Unknown statuses")
        
        logger.info(f"Successfully retrieved {len(results)} applications")
        return results
        
    except Exception as e:
        logger.error(f"Error fetching applications: {e}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}", exc_info=True)
        # Return empty list instead of 500 to prevent frontend breaking
        # In production, you might want to return 500, but for development, empty list is safer
        # However, we should still log the full error for debugging
        return []

@router.get("/{application_id}")
@router.get("/{application_id}/")
def get_application_by_id(
    application_id: str,
    db: Session = Depends(get_db)
):
    """Get a single application by ID with error handling."""
    try:
        repo = ApplicationRepository(db)
        app = repo.get_by_id(application_id)
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        company_name = app.company.name.title() if app.company and app.company.name else "Unknown"
        role_title = app.role.title if app.role and app.role.title else "Unknown"
        resume_url = app.resume.storage_url if app.resume and app.resume.storage_url else None
        
        return ApplicationResponse(
            id=app.id,
            company_name=company_name,
            role_title=role_title,
            status=app.status or "Applied",
            applied_count=app.applied_count or 0,
            last_email_date=app.last_email_date,
            ghosted=app.ghosted if app.ghosted is not None else False,
            resume_url=resume_url
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching application {application_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.patch("/{id}", response_model=ApplicationResponse)
def update_application(id: uuid.UUID, update: ApplicationUpdate, db: Session = Depends(get_db)):
    """Update an application with error handling."""
    try:
        repo = ApplicationRepository(db)
        
        # Logic to update status
        if update.status:
            repo.update_application_status(str(id), update.status)
        
        # Logic to update resume
        if update.resume_id:
            from app.services.resume_matcher import ResumeMatcher
            matcher = ResumeMatcher(db)
            matcher.link_resume_to_application(str(id), str(update.resume_id))

        # Logic to manual override ghosted
        if update.ghosted is not None:
            app = repo.get_by_id(str(id))
            if app:
                app.ghosted = update.ghosted
                db.commit()
            else:
                raise HTTPException(status_code=404, detail="Application not found")

        app = repo.get_by_id(str(id))
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
            
        company_name = app.company.name.title() if app.company and app.company.name else "Unknown"
        role_title = app.role.title if app.role and app.role.title else "Unknown"
        resume_url = app.resume.storage_url if app.resume and app.resume.storage_url else None
        
        return ApplicationResponse(
            id=app.id,
            company_name=company_name,
            role_title=role_title,
            status=app.status or "Applied",
            applied_count=app.applied_count or 0,
            last_email_date=app.last_email_date,
            ghosted=app.ghosted if app.ghosted is not None else False,
            resume_url=resume_url
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating application {id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
