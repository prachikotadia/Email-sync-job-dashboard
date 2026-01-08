from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.supabase import get_db
from app.models import Resume
import os
import shutil
import uuid
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "uploads/resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
def upload_resume(file: UploadFile = File(...), tags: str = "general", db: Session = Depends(get_db)):
    """
    Uploads a resume PDF/Doc to local storage (stub for Supabase Storage).
    Tags can be comma-separated strings (e.g. "frontend,fullstack").
    """
    file_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1]
    safe_filename = f"{file_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # Save file locally
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {str(e)}")
        
    # Process Tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Create DB Record
    resume = Resume(
        file_name=file.filename,
        storage_url=file_path, # In prod, this would be a Supabase/S3 URL
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
