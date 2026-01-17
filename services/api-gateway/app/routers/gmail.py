from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector:8002")

@router.get("/status")
async def get_status(token_data: dict = Depends(verify_token)):
    """
    Get Gmail connection status
    Returns 503 ONLY if service is down
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/status",
                params={"user_id": user_id},
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Gmail service timeout")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            raise HTTPException(status_code=503, detail="Gmail service unavailable")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Gmail service unavailable")

@router.post("/sync/start")
async def start_sync(token_data: dict = Depends(verify_token)):
    """
    Start Gmail sync
    Returns job ID for progress tracking
    """
    user_id = token_data.get("sub")
    user_email = token_data.get("email")  # Get email from JWT for validation
    
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/sync/start",
                json={"user_id": user_id, "user_email": user_email}
            )
            
            if response.status_code == 409:
                # Sync already running
                raise HTTPException(status_code=409, detail=response.json().get("detail", "Sync already running"))
            
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/sync/progress/{job_id}")
async def get_sync_progress(job_id: str, token_data: dict = Depends(verify_token)):
    """
    Get sync progress (for polling)
    Returns real-time counts from backend
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/sync/progress/{job_id}",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/applications")
async def get_applications(
    search: str = Query(None),
    status: str = Query(None),
    token_data: dict = Depends(verify_token)
):
    """
    Get all applications
    NO pagination limits - returns ALL fetched emails
    """
    user_id = token_data.get("sub")
    
    try:
        params = {"user_id": user_id}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications",
                params=params
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/stats")
async def get_stats(token_data: dict = Depends(verify_token)):
    """
    Get dashboard statistics
    Returns REAL counts from backend, never estimated
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/stats",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")
