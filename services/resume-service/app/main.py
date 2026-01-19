"""
Resume Service - Production-grade resume file management
Handles resume upload, storage, linking to applications, and default resume management
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Header, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
import time
import uuid
import hashlib
from app.database import get_db, init_db, Resume, ApplicationResume, TESTING
from app.storage import get_storage, validate_file, StorageError
from app.jwt_utils import get_user_from_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_health_start = time.time()

app = FastAPI(title="Resume Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Resume Service database initialized")


# Pydantic models
class ResumeResponse(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_size_kb: int
    is_default: bool
    created_at: str
    updated_at: str
    usage_count: Optional[int] = 0  # Number of applications using this resume

    class Config:
        orm_mode = True


class ResumeUploadRequest(BaseModel):
    file_name: Optional[str] = None  # Optional custom name, defaults to original filename


class ResumeRenameRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=200)


# Dependency to get current user
async def get_current_user(authorization: str = Header(...)) -> str:
    """Get current user email from JWT"""
    return get_user_from_token(authorization)


# Helper to get user_id (UUID) from email
def get_user_id_from_email(db: Session, user_email: str):
    """
    Get user UUID from email
    Note: This queries the users table from the shared database
    Returns string UUID in TESTING mode, UUID object in production
    """
    from sqlalchemy import text
    result = db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": user_email}
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = result[0]
    # In TESTING mode, SQLite returns strings, so return as-is
    # In production, PostgreSQL returns UUID objects, so return as-is
    return user_id


# Resume Upload Endpoint
@app.post("/resumes/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    file_name: Optional[str] = Query(None, description="Custom name for the resume"),
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a resume file (PDF or DOCX)
    
    Validates file type, size, and stores securely.
    Returns resume metadata.
    """
    try:
        # Get user_id
        user_id = get_user_id_from_email(db, user_email)
        
        # Read file content
        file_content = await file.read()
        
        # Validate file
        file_type, file_size_kb = validate_file(file_content, file.filename)
        
        # Calculate checksum for deduplication
        checksum = hashlib.sha256(file_content).hexdigest()
        
        # Check for duplicate (same checksum, same user, not deleted)
        existing = db.query(Resume).filter(
            and_(
                Resume.user_id == user_id,
                Resume.checksum == checksum,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="A resume with identical content already exists. Please use a different file."
            )
        
        # Get storage instance
        storage = get_storage()
        
        # Determine file name
        display_name = file_name or file.filename.rsplit('.', 1)[0]  # Remove extension
        
        # Save file
        file_url, _ = storage.save_file(file_content, str(user_id), file.filename)
        
        # Create resume record
        resume_id = str(uuid.uuid4()) if TESTING else uuid.uuid4()
        resume = Resume(
            id=resume_id,
            user_id=user_id,
            file_name=display_name,
            file_url=file_url,
            file_type=file_type,
            file_size_kb=file_size_kb,
            checksum=checksum,
            is_default=False,  # New resumes are not default by default
        )
        
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        logger.info(f"Resume uploaded: {resume.id} by user {user_email}")
        
        # Get usage count
        usage_count = db.query(ApplicationResume).filter(
            ApplicationResume.resume_id == resume.id
        ).count()
        
        return ResumeResponse(
            id=str(resume.id),
            file_name=resume.file_name,
            file_type=resume.file_type,
            file_size_kb=resume.file_size_kb,
            is_default=resume.is_default,
            created_at=resume.created_at.isoformat(),
            updated_at=resume.updated_at.isoformat(),
            usage_count=usage_count,
        )
    
    except StorageError as e:
        logger.error(f"Storage error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload resume: {str(e)}")


# List Resumes
@app.get("/resumes", response_model=List[ResumeResponse])
async def list_resumes(
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all resumes for current user (excluding deleted)"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        
        resumes = db.query(Resume).filter(
            and_(
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).order_by(Resume.created_at.desc()).all()
        
        result = []
        for resume in resumes:
            # Get usage count
            usage_count = db.query(ApplicationResume).filter(
                ApplicationResume.resume_id == resume.id
            ).count()
            
            result.append(ResumeResponse(
                id=str(resume.id),
                file_name=resume.file_name,
                file_type=resume.file_type,
                file_size_kb=resume.file_size_kb,
                is_default=resume.is_default,
                created_at=resume.created_at.isoformat(),
                updated_at=resume.updated_at.isoformat(),
                usage_count=usage_count,
            ))
        
        return result
    
    except Exception as e:
        logger.error(f"Error listing resumes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list resumes: {str(e)}")


# Get Default Resume (MUST be before /resumes/{resume_id} to avoid route conflict)
@app.get("/resumes/default")
async def get_default_resume(
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the default resume for current user"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.user_id == user_id,
                Resume.is_default == True,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            return {"resume": None}
        
        return {
            "resume": {
                "id": str(resume.id),
                "file_name": resume.file_name,
                "file_type": resume.file_type,
                "file_size_kb": resume.file_size_kb,
                "created_at": resume.created_at.isoformat(),
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting default resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get default resume: {str(e)}")


# Get Single Resume
@app.get("/resumes/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific resume"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        # In TESTING mode, keep resume_id as string (SQLite)
        # In production, convert to UUID object (PostgreSQL)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Get usage count
        usage_count = db.query(ApplicationResume).filter(
            ApplicationResume.resume_id == resume.id
        ).count()
        
        return ResumeResponse(
            id=str(resume.id),
            file_name=resume.file_name,
            file_type=resume.file_type,
            file_size_kb=resume.file_size_kb,
            is_default=resume.is_default,
            created_at=resume.created_at.isoformat(),
            updated_at=resume.updated_at.isoformat(),
            usage_count=usage_count,
        )
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get resume: {str(e)}")


# Rename Resume
@app.put("/resumes/{resume_id}/rename", response_model=ResumeResponse)
async def rename_resume(
    resume_id: str,
    request: ResumeRenameRequest,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rename a resume"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        resume.file_name = request.file_name
        resume.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(resume)
        
        logger.info(f"Resume renamed: {resume_id} to '{request.file_name}' by user {user_email}")
        
        # Get usage count
        usage_count = db.query(ApplicationResume).filter(
            ApplicationResume.resume_id == resume.id
        ).count()
        
        return ResumeResponse(
            id=str(resume.id),
            file_name=resume.file_name,
            file_type=resume.file_type,
            file_size_kb=resume.file_size_kb,
            is_default=resume.is_default,
            created_at=resume.created_at.isoformat(),
            updated_at=resume.updated_at.isoformat(),
            usage_count=usage_count,
        )
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to rename resume: {str(e)}")


# Set Default Resume
@app.post("/resumes/{resume_id}/set-default", response_model=ResumeResponse)
async def set_default_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set a resume as default
    
    Atomically unsets previous default and sets new default.
    Transactional operation.
    """
    try:
        user_id = get_user_id_from_email(db, user_email)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Unset previous default (atomic operation)
        db.query(Resume).filter(
            and_(
                Resume.user_id == user_id,
                Resume.is_default == True,
                Resume.deleted_at.is_(None)
            )
        ).update({"is_default": False})
        
        # Set new default
        resume.is_default = True
        resume.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(resume)
        
        logger.info(f"Default resume set: {resume_id} by user {user_email}")
        
        # Get usage count
        usage_count = db.query(ApplicationResume).filter(
            ApplicationResume.resume_id == resume.id
        ).count()
        
        return ResumeResponse(
            id=str(resume.id),
            file_name=resume.file_name,
            file_type=resume.file_type,
            file_size_kb=resume.file_size_kb,
            is_default=resume.is_default,
            created_at=resume.created_at.isoformat(),
            updated_at=resume.updated_at.isoformat(),
            usage_count=usage_count,
        )
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set default resume: {str(e)}")


# Delete Resume
@app.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a resume (soft delete)
    
    If resume is linked to applications, deletion is blocked.
    """
    try:
        user_id = get_user_id_from_email(db, user_email)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Check if linked to applications
        link_count = db.query(ApplicationResume).filter(
            ApplicationResume.resume_id == resume.id
        ).count()
        
        if link_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete resume: It is linked to {link_count} application(s). Please unlink it first or reassign applications to another resume."
            )
        
        # Soft delete
        resume.deleted_at = datetime.now(timezone.utc)
        if resume.is_default:
            resume.is_default = False
        
        db.commit()
        
        logger.info(f"Resume deleted (soft): {resume_id} by user {user_email}")
        
        return None
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete resume: {str(e)}")


# Download Resume File
@app.get("/resumes/{resume_id}/download")
async def download_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download resume file"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Get file from storage
        storage = get_storage()
        file_content = storage.get_file(resume.file_url)
        
        # Determine media type
        media_type = "application/pdf" if resume.file_type == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        # Determine file extension
        extension = ".pdf" if resume.file_type == "pdf" else ".docx"
        
        return StreamingResponse(
            iter([file_content]),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{resume.file_name}{extension}"'
            }
        )
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    except StorageError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to download resume: {str(e)}")


# Preview Resume File (opens in browser)
@app.get("/resumes/{resume_id}/preview")
async def preview_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Preview resume file (opens in browser)"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Get file from storage
        storage = get_storage()
        file_content = storage.get_file(resume.file_url)
        
        # Determine media type
        media_type = "application/pdf" if resume.file_type == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        return StreamingResponse(
            iter([file_content]),
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{resume.file_name}"'
            }
        )
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    except StorageError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to preview resume: {str(e)}")


# Link Resume to Application
@app.post("/applications/{application_id}/resume/{resume_id}", status_code=status.HTTP_201_CREATED)
async def link_resume_to_application(
    application_id: str,
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Link a resume to an application
    
    Replaces existing link if present.
    """
    try:
        user_id = get_user_id_from_email(db, user_email)
        application_id_value = application_id if TESTING else uuid.UUID(application_id)
        resume_id_value = resume_id if TESTING else uuid.UUID(resume_id)
        
        # Verify resume ownership
        resume = db.query(Resume).filter(
            and_(
                Resume.id == resume_id_value,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Verify application ownership (query applications table)
        from sqlalchemy import text
        app_result = db.execute(
            text("SELECT id FROM applications WHERE id = :app_id AND user_id = :user_id"),
            {"app_id": application_id_value, "user_id": user_id}
        ).first()
        
        if not app_result:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Check for existing link
        existing_link = db.query(ApplicationResume).filter(
            ApplicationResume.application_id == application_id_value
        ).first()
        
        if existing_link:
            # Replace existing link
            existing_link.resume_id = resume_id_value
            existing_link.linked_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Resume link updated: {resume_id} -> {application_id} by user {user_email}")
        else:
            # Create new link
            link_id = str(uuid.uuid4()) if TESTING else uuid.uuid4()
            link = ApplicationResume(
                id=link_id,
                application_id=application_id_value,
                resume_id=resume_id_value,
            )
            db.add(link)
            db.commit()
            logger.info(f"Resume linked: {resume_id} -> {application_id} by user {user_email}")
        
        return {"message": "Resume linked successfully"}
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to link resume: {str(e)}")


# Get Resume for Application
@app.get("/applications/{application_id}/resume")
async def get_application_resume(
    application_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the resume linked to an application"""
    try:
        user_id = get_user_id_from_email(db, user_email)
        application_id_value = application_id if TESTING else uuid.UUID(application_id)
        
        # Verify application ownership
        from sqlalchemy import text
        app_result = db.execute(
            text("SELECT id FROM applications WHERE id = :app_id AND user_id = :user_id"),
            {"app_id": application_id_value, "user_id": user_id}
        ).first()
        
        if not app_result:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Get link
        link = db.query(ApplicationResume).filter(
            ApplicationResume.application_id == application_id_value
        ).first()
        
        if not link:
            return {"resume": None}
        
        # Get resume
        resume = db.query(Resume).filter(
            and_(
                Resume.id == link.resume_id,
                Resume.deleted_at.is_(None)
            )
        ).first()
        
        if not resume:
            return {"resume": None}
        
        return {
            "resume": {
                "id": str(resume.id),
                "file_name": resume.file_name,
                "file_type": resume.file_type,
                "linked_at": link.linked_at.isoformat(),
            }
        }
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get application resume: {str(e)}")


# Health endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "resume-service",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": round(time.time() - _health_start, 2),
    }
