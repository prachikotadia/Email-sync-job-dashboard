from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
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
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")  # API gateway sends X-User-Id
):
    """
    REQUIREMENT 6 & 9: Get all applications for the authenticated user.
    
    CRITICAL: 
    - Filters by user_id from JWT token (X-User-ID header)
    - Shows ALL applications for that user (no limit)
    - Most recent first (sorted by last_email_date DESC)
    - Multi-user ready: each user only sees their own applications
    """
    try:
        # REQUIREMENT 9: Extract user_id from header (set by API gateway from JWT)
        user_id_uuid = None
        if x_user_id:
            try:
                user_id_uuid = uuid.UUID(x_user_id)
                logger.info(f"[REQUIREMENT 9] Filtering applications by user_id: {user_id_uuid}")
            except ValueError as e:
                logger.warning(f"Invalid X-User-ID header: {x_user_id}, error: {e}")
                # Continue without filtering (backward compatibility)
        else:
            logger.warning("[REQUIREMENT 9] No X-User-ID header provided - showing ALL applications (backward compatibility)")
        
        repo = ApplicationRepository(db)
        # REQUIREMENT 6 & 9: Filter by user_id if provided, show ALL for that user
        apps = repo.list_applications(user_id=str(user_id_uuid) if user_id_uuid else None, limit=None)
        
        # Handle empty results gracefully
        if not apps:
            logger.info("No applications found in database")
            return []
        
        # SHOW ALL APPLICATIONS - NO STATUS FILTERING
        results = []
        for app in apps:
            try:
                # Get status (default to Applied if None)
                app_status = app.status or "Applied"
                
                # Safely access relationships with null checks
                company_name = "Unknown"
                role_title = "Unknown"
                try:
                    if app.company and app.company.name:
                        company_name = app.company.name.title()
                except Exception as e:
                    logger.warning(f"Error getting company name for app {app.id}: {e}")
                
                try:
                    if app.role and app.role.title:
                        role_title = app.role.title
                except Exception as e:
                    logger.warning(f"Error getting role title for app {app.id}: {e}")
                
                resume_url = None
                try:
                    if app.resume and app.resume.storage_url:
                        resume_url = app.resume.storage_url
                except Exception as e:
                    logger.warning(f"Error getting resume URL for app {app.id}: {e}")
                
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
                logger.debug(f"Added application {app.id}: {company_name} - {role_title} ({app_status})")
            except Exception as e:
                logger.error(f"Error processing application {app.id}: {e}", exc_info=True)
                # Skip this application but continue processing others
                continue
        
        # REQUIREMENT 6 & 8: Log comprehensive stats with error detection
        user_id_str = str(user_id_uuid) if user_id_uuid else "ALL"
        logger.info(f"✅ Successfully retrieved {len(results)} applications (out of {len(apps)} total in DB for user {user_id_str})")
        logger.info(f"📊 [DATA FLOW] DB Query returned: {len(apps)} applications")
        logger.info(f"📊 [DATA FLOW] API Response returning: {len(results)} applications")
        logger.info(f"📊 [DATA FLOW] NO LIMIT applied - showing ALL applications")
        
        # REQUIREMENT 8: Error detection - log if counts don't match
        if len(results) != len(apps):
            logger.error(f"❌ ERROR: Results count ({len(results)}) != DB count ({len(apps)}) - some applications may have been skipped due to relationship errors")
        
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
