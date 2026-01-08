from fastapi import APIRouter, File, UploadFile
from typing import List

router = APIRouter()

@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    # Stub for resume upload
    return {"filename": file.filename, "status": "uploaded", "id": "stub-uuid"}

@router.get("/")
def get_resumes():
    # Stub list
    return []
