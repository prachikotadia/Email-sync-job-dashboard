from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.supabase import get_db
from app.models import Resume
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

router = APIRouter()

# Cross-platform path handling
# Use pathlib for cross-platform compatibility
BASE_DIR = Path(__file__).parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads" / "resumes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
def upload_resume(file: UploadFile = File(...), tags: str = "general", db: Session = Depends(get_db)):
    """
    Uploads a resume PDF/Doc to local storage (stub for Supabase Storage).
    Tags can be comma-separated strings (e.g. "frontend,fullstack").
    """
    file_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1] if "." in file.filename else "pdf"
    safe_filename = f"{file_id}.{ext}"
    # Use pathlib for cross-platform path handling
    file_path = UPLOAD_DIR / safe_filename
    
    # Save file locally
    try:
        with open(str(file_path), "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {str(e)}")
        
    # Process Tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Create DB Record
    # Convert path to string for storage (use forward slashes for cross-platform compatibility)
    storage_url = str(file_path).replace("\\", "/")
    
    resume = Resume(
        file_name=file.filename,
        storage_url=storage_url, # In prod, this would be a Supabase/S3 URL
        tags=tag_list
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    
    return {"id": resume.id, "filename": resume.file_name, "url": resume.storage_url}

@router.get("/", response_model=List[dict]) 
def list_resumes(db: Session = Depends(get_db)):
    # Simple list for selection dropdowns
    resumes = db.query(Resume).order_by(Resume.created_at.desc()).all()
    return [{"id": r.id, "name": r.file_name, "tags": r.tags, "created_at": r.created_at} for r in resumes]
