"""
Resume Router - Proxies resume file management requests to resume-service
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

RESUME_SERVICE_URL = os.getenv("RESUME_SERVICE_URL", "http://resume-service:8004")


class ResumeRenameRequest(BaseModel):
    file_name: str


def _get_auth_header(request: Request) -> str:
    """Extract Authorization header from request"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    return auth_header


# Resume Upload
@router.post("/upload")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    file_name: Optional[str] = Query(None),
    token_data: dict = Depends(verify_token)
):
    """Upload a resume file (PDF or DOCX)"""
    auth_header = _get_auth_header(request)
    try:
        # Read file content
        file_content = await file.read()
        
        # Forward to resume service
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (file.filename, file_content, file.content_type)}
            params = {}
            if file_name:
                params["file_name"] = file_name
            
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes/upload",
                files=files,
                params=params,
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# List Resumes
@router.get("")
async def list_resumes(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """List all resumes for current user"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Preview Resume (MUST be before /{resume_id} to avoid route conflict)
@router.get("/{resume_id}/preview")
async def preview_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Preview resume file (opens in browser)"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/preview",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            
            # Stream the file
            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get("content-type", "application/pdf"),
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", f'inline; filename="resume.pdf"')
                }
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Download Resume (MUST be before /{resume_id} to avoid route conflict)
@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Download resume file"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/download",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            
            # Stream the file
            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", f'attachment; filename="resume.pdf"')
                }
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Rename Resume (MUST be before /{resume_id} to avoid route conflict)
@router.put("/{resume_id}/rename")
async def rename_resume(
    resume_id: str,
    request: ResumeRenameRequest,
    http_request: Request,
    token_data: dict = Depends(verify_token)
):
    """Rename a resume"""
    auth_header = _get_auth_header(http_request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/rename",
                json=request.dict(),
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Set Default Resume (MUST be before /{resume_id} to avoid route conflict)
@router.post("/{resume_id}/set-default")
async def set_default_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Set a resume as default"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/set-default",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Get Single Resume (MUST be after all /{resume_id}/* routes)
@router.get("/{resume_id}")
async def get_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Get a specific resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Delete Resume
@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Delete a resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.status_code == 204
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Get Default Resume
@router.get("/default")
async def get_default_resume(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Get the default resume for current user"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes/default",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Link Resume to Application
@router.post("/applications/{application_id}/resume/{resume_id}")
async def link_resume_to_application(
    application_id: str,
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Link a resume to an application"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RESUME_SERVICE_URL}/applications/{application_id}/resume/{resume_id}",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


# Get Resume for Application
@router.get("/applications/{application_id}/resume")
async def get_application_resume(
    application_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Get the resume linked to an application"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/applications/{application_id}/resume",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json().get("detail", str(e)))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")
