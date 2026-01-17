"""
Resume Service - Production-grade resume management
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import time
import uuid
from app.database import get_db, init_db, Resume, ResumeVersion, ResumeUpload
from app.jwt_utils import get_user_from_token
from app.resume_parser import parse_pdf, parse_docx
from app.resume_exporter import export_to_pdf, export_to_docx

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
class ResumeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: Optional[str] = None
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[Dict[str, Any]] = Field(default_factory=list)


class ResumeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    summary: Optional[str] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


# Dependency to get current user
async def get_current_user(authorization: str = Header(...)) -> str:
    """Get current user email from JWT"""
    return get_user_from_token(authorization)


# Helper function to verify resume ownership
def verify_resume_ownership(db: Session, resume_id: str, user_email: str) -> Resume:
    """Verify user owns the resume"""
    try:
        resume_uuid = uuid.UUID(resume_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    
    resume = db.query(Resume).filter(Resume.id == resume_uuid).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    if resume.user_id != user_email:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return resume


# Resume CRUD Endpoints
@app.post("/resumes")
async def create_resume(
    resume_data: ResumeCreate,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new resume"""
    try:
        # Validate required fields
        if not resume_data.title:
            raise HTTPException(status_code=400, detail="Title is required")
        
        # Create resume
        resume = Resume(
            id=uuid.uuid4(),
            user_id=user_email,
            title=resume_data.title,
            summary=resume_data.summary,
            experience=resume_data.experience,
            education=resume_data.education,
            skills=resume_data.skills,
            projects=resume_data.projects,
            certifications=resume_data.certifications,
            is_active=True,
        )
        
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        logger.info(f"Resume created: {resume.id} by user {user_email}")
        
        return {
            "id": str(resume.id),
            "title": resume.title,
            "summary": resume.summary,
            "experience": resume.experience,
            "education": resume.education,
            "skills": resume.skills,
            "projects": resume.projects,
            "certifications": resume.certifications,
            "created_at": resume.created_at.isoformat(),
            "updated_at": resume.updated_at.isoformat(),
            "is_active": resume.is_active,
        }
    except Exception as e:
        logger.error(f"Error creating resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create resume: {str(e)}")


@app.get("/resumes")
async def list_resumes(
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(None)
):
    """List all resumes for current user"""
    try:
        query = db.query(Resume).filter(Resume.user_id == user_email)
        
        if is_active is not None:
            query = query.filter(Resume.is_active == is_active)
        
        resumes = query.order_by(Resume.updated_at.desc()).all()
        
        return [
            {
                "id": str(r.id),
                "title": r.title,
                "summary": r.summary,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "is_active": r.is_active,
            }
            for r in resumes
        ]
    except Exception as e:
        logger.error(f"Error listing resumes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list resumes: {str(e)}")


@app.get("/resumes/{resume_id}")
async def get_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific resume"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    return {
        "id": str(resume.id),
        "title": resume.title,
        "summary": resume.summary,
        "experience": resume.experience,
        "education": resume.education,
        "skills": resume.skills,
        "projects": resume.projects,
        "certifications": resume.certifications,
        "created_at": resume.created_at.isoformat(),
        "updated_at": resume.updated_at.isoformat(),
        "is_active": resume.is_active,
    }


@app.put("/resumes/{resume_id}")
async def update_resume(
    resume_id: str,
    resume_data: ResumeUpdate,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a resume"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    try:
        # Update fields
        if resume_data.title is not None:
            resume.title = resume_data.title
        if resume_data.summary is not None:
            resume.summary = resume_data.summary
        if resume_data.experience is not None:
            resume.experience = resume_data.experience
        if resume_data.education is not None:
            resume.education = resume_data.education
        if resume_data.skills is not None:
            resume.skills = resume_data.skills
        if resume_data.projects is not None:
            resume.projects = resume_data.projects
        if resume_data.certifications is not None:
            resume.certifications = resume_data.certifications
        if resume_data.is_active is not None:
            resume.is_active = resume_data.is_active
        
        resume.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(resume)
        
        logger.info(f"Resume updated: {resume.id} by user {user_email}")
        
        return {
            "id": str(resume.id),
            "title": resume.title,
            "summary": resume.summary,
            "experience": resume.experience,
            "education": resume.education,
            "skills": resume.skills,
            "projects": resume.projects,
            "certifications": resume.certifications,
            "created_at": resume.created_at.isoformat(),
            "updated_at": resume.updated_at.isoformat(),
            "is_active": resume.is_active,
        }
    except Exception as e:
        logger.error(f"Error updating resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update resume: {str(e)}")


@app.delete("/resumes/{resume_id}")
async def delete_resume(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a resume"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    try:
        db.delete(resume)
        db.commit()
        
        logger.info(f"Resume deleted: {resume_id} by user {user_email}")
        
        return {"message": "Resume deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete resume: {str(e)}")


# Resume Version Endpoints
@app.post("/resumes/{resume_id}/version")
async def create_version(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a version snapshot of a resume"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    try:
        # Get current version number
        latest_version = db.query(ResumeVersion).filter(
            ResumeVersion.resume_id == resume.id
        ).order_by(ResumeVersion.version_number.desc()).first()
        
        next_version = (latest_version.version_number + 1) if latest_version else 1
        
        # Create snapshot
        snapshot = {
            "title": resume.title,
            "summary": resume.summary,
            "experience": resume.experience,
            "education": resume.education,
            "skills": resume.skills,
            "projects": resume.projects,
            "certifications": resume.certifications,
        }
        
        version = ResumeVersion(
            id=uuid.uuid4(),
            resume_id=resume.id,
            version_number=next_version,
            snapshot_json=snapshot,
        )
        
        db.add(version)
        db.commit()
        db.refresh(version)
        
        logger.info(f"Version created: {version.id} for resume {resume_id}")
        
        return {
            "id": str(version.id),
            "version_number": version.version_number,
            "created_at": version.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error creating version: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create version: {str(e)}")


@app.get("/resumes/{resume_id}/versions")
async def list_versions(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all versions of a resume"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    versions = db.query(ResumeVersion).filter(
        ResumeVersion.resume_id == resume.id
    ).order_by(ResumeVersion.version_number.desc()).all()
    
    return [
        {
            "id": str(v.id),
            "version_number": v.version_number,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


# Resume Upload & Parsing
@app.post("/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and parse a resume file (PDF or DOCX)"""
    try:
        # Validate file type
        file_type = None
        if file.filename.endswith('.pdf'):
            file_type = 'pdf'
        elif file.filename.endswith('.docx'):
            file_type = 'docx'
        else:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
        
        # Validate file size (max 10MB)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Parse file
        if file_type == 'pdf':
            parsed_data = parse_pdf(file_content)
        else:
            parsed_data = parse_docx(file_content)
        
        # Create upload record
        upload = ResumeUpload(
            id=uuid.uuid4(),
            user_id=user_email,
            file_type=file_type,
            original_filename=file.filename,
            parsed_content_json=parsed_data,
        )
        
        db.add(upload)
        db.commit()
        db.refresh(upload)
        
        logger.info(f"Resume uploaded and parsed: {upload.id} by user {user_email}")
        
        return {
            "id": str(upload.id),
            "file_type": upload.file_type,
            "original_filename": upload.original_filename,
            "parsed_data": upload.parsed_content_json,
            "created_at": upload.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload resume: {str(e)}")


# Resume Export Endpoints
@app.post("/resumes/{resume_id}/export/pdf")
async def export_resume_pdf(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export resume as PDF"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    try:
        # Prepare resume data
        resume_data = {
            "title": resume.title,
            "summary": resume.summary,
            "experience": resume.experience,
            "education": resume.education,
            "skills": resume.skills,
            "projects": resume.projects,
            "certifications": resume.certifications,
        }
        
        # Generate PDF
        pdf_bytes = export_to_pdf(resume_data)
        
        logger.info(f"Resume exported to PDF: {resume_id} by user {user_email}")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{resume.title.replace(" ", "_")}_resume.pdf"',
            },
        )
    except Exception as e:
        logger.error(f"Error exporting PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export PDF: {str(e)}")


@app.post("/resumes/{resume_id}/export/docx")
async def export_resume_docx(
    resume_id: str,
    user_email: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export resume as DOCX"""
    resume = verify_resume_ownership(db, resume_id, user_email)
    
    try:
        # Prepare resume data
        resume_data = {
            "title": resume.title,
            "summary": resume.summary,
            "experience": resume.experience,
            "education": resume.education,
            "skills": resume.skills,
            "projects": resume.projects,
            "certifications": resume.certifications,
        }
        
        # Generate DOCX
        docx_bytes = export_to_docx(resume_data)
        
        logger.info(f"Resume exported to DOCX: {resume_id} by user {user_email}")
        
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{resume.title.replace(" ", "_")}_resume.docx"',
            },
        )
    except Exception as e:
        logger.error(f"Error exporting DOCX: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export DOCX: {str(e)}")


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
