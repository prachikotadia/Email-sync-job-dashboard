"""
Resume Router - Proxies resume requests to resume-service
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

RESUME_SERVICE_URL = os.getenv("RESUME_SERVICE_URL", "http://resume-service:8004")


class ResumeCreate(BaseModel):
    title: str
    summary: Optional[str] = None
    experience: List[Dict[str, Any]] = []
    education: List[Dict[str, Any]] = []
    skills: List[str] = []
    projects: List[Dict[str, Any]] = []
    certifications: List[Dict[str, Any]] = []


class ResumeUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


def _get_auth_header(request: Request) -> str:
    """Extract Authorization header from request"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    return auth_header


@router.post("/resumes")
async def create_resume(
    resume_data: ResumeCreate,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Create a new resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes",
                json=resume_data.dict(),
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to create resume")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.get("/resumes")
async def list_resumes(
    request: Request,
    is_active: Optional[bool] = None,
    token_data: dict = Depends(verify_token)
):
    """List all resumes for current user"""
    auth_header = _get_auth_header(request)
    try:
        params = {}
        if is_active is not None:
            params["is_active"] = is_active
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes",
                params=params,
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to list resumes")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.get("/resumes/{resume_id}")
async def get_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Get a specific resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to get resume")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.put("/resumes/{resume_id}")
async def update_resume(
    resume_id: str,
    resume_data: ResumeUpdate,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Update a resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}",
                json=resume_data.dict(exclude_none=True),
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to update resume")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.delete("/resumes/{resume_id}")
async def delete_resume(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Delete a resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to delete resume")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.post("/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...),
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Upload and parse a resume file"""
    auth_header = _get_auth_header(request)
    try:
        file_content = await file.read()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (file.filename, file_content, file.content_type)}
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes/upload",
                files=files,
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to upload resume")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.post("/resumes/{resume_id}/export/pdf")
async def export_resume_pdf(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Export resume as PDF"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/export/pdf",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            
            return Response(
                content=response.content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": response.headers.get("content-disposition", ""),
                },
            )
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to export PDF")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.post("/resumes/{resume_id}/export/docx")
async def export_resume_docx(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Export resume as DOCX"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/export/docx",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            
            return Response(
                content=response.content,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": response.headers.get("content-disposition", ""),
                },
            )
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to export DOCX")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.post("/resumes/{resume_id}/version")
async def create_version(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """Create a version snapshot of a resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/version",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to create version")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")


@router.get("/resumes/{resume_id}/versions")
async def list_versions(
    resume_id: str,
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """List all versions of a resume"""
    auth_header = _get_auth_header(request)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{RESUME_SERVICE_URL}/resumes/{resume_id}/versions",
                headers={"Authorization": auth_header}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Failed to list versions")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Resume service unavailable: {str(e)}")
