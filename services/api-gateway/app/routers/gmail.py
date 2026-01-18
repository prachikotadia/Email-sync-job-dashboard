from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import httpx
import os
import logging
from app.middleware.auth_middleware import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()

GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")

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
async def start_sync_job(token_data: dict = Depends(verify_token)):
    """Start a new Gmail sync job or return existing running job."""
    user_id = token_data.get("sub")
    user_email = token_data.get("email")
    
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    try:
        # No timeout - sync start should return immediately after queuing background job
        # Use a very high timeout value (1 hour) to effectively disable timeout
        timeout_config = httpx.Timeout(3600.0, connect=60.0)  # 1 hour total, 60s connect
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            logger.info(f"Calling Gmail service at {GMAIL_SERVICE_URL}/gmail/sync/start for user {user_email}")
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/gmail/sync/start",
                json={"user_id": user_id, "user_email": user_email},
                timeout=timeout_config
            )
            
            logger.info(f"Gmail service response status: {response.status_code}")
            
            if response.status_code == 409:
                try:
                    detail = response.json().get("detail", "Sync already running")
                except:
                    detail = "Sync already running"
                raise HTTPException(status_code=409, detail=detail)
            
            response.raise_for_status()
            
            try:
                return response.json()
            except Exception as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}, response text: {response.text[:200]}")
                raise HTTPException(status_code=503, detail=f"Gmail service returned invalid response: {str(json_error)}")
                
    except HTTPException:
        raise
    except httpx.TimeoutException as e:
        logger.error(f"Gmail service timeout after 1 hour: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Gmail service is not responding. This should not happen - the sync start endpoint should return immediately. Please check service logs.")
    except httpx.ConnectError as e:
        logger.error(f"Gmail service connection error: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Gmail service connection failed. Is the service running at {GMAIL_SERVICE_URL}? Error: {str(e)}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Gmail service HTTP error: {e.response.status_code}, {str(e)}")
        try:
            detail = e.response.json().get("detail", str(e))
        except:
            detail = str(e)
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except httpx.RequestError as e:
        logger.error(f"Gmail service request error: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Gmail service request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error calling Gmail service: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/sync/status")
async def get_sync_status(token_data: dict = Depends(verify_token)):
    """Get current sync status for user."""
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/gmail/sync/status",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.post("/sync")
async def start_sync(token_data: dict = Depends(verify_token)):
    """
    Start Gmail sync - Legacy endpoint (for backward compatibility)
    Redirects to /sync/start
    """
    # Redirect to new endpoint
    return await start_sync_job(token_data)

@router.get("/sync/progress/{job_id}")
async def get_sync_progress(job_id: str, token_data: dict = Depends(verify_token)):
    """
    Get sync progress (for polling) - uses database job system
    Returns real-time counts from backend matching exact response format
    
    STRICT: job_id must be valid (not undefined/null/empty)
    """
    # Validate job_id before forwarding
    if not job_id or job_id in ['undefined', 'null', '']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job_id: '{job_id}'. Cannot poll progress."
        )
    
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try database-based endpoint first
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/gmail/sync/progress/{job_id}",
                params={"user_id": user_id}
            )
            
            # Handle specific error cases
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Sync job '{job_id}' not found. It may have completed or been cleared."
                )
            
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=503,
            detail="Gmail service timeout. Please try again."
        )
    except httpx.HTTPStatusError as e:
        # Forward specific status codes from downstream
        if e.response.status_code in [404, 403]:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", str(e))
            )
        raise HTTPException(
            status_code=503,
            detail=f"Gmail service unavailable: {str(e)}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Gmail service connection failed: {str(e)}"
        )

@router.get("/sync/logs/{job_id}")
async def get_sync_logs(
    job_id: str,
    after_seq: int = Query(0),
    token_data: dict = Depends(verify_token)
):
    """Get sync logs for a job."""
    # Validate job_id
    if not job_id or job_id in ['undefined', 'null', '']:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/gmail/sync/logs/{job_id}",
                params={"user_id": user_id, "after_seq": after_seq}
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
    Response includes gmail_web_url for opening emails
    """
    user_id = token_data.get("sub")
    
    try:
        params = {"user_id": user_id}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        
        # No timeout - sync start is a quick operation that just queues a background job
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications",
                params=params
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")


@router.get("/applications/{app_id}")
async def get_application(
    app_id: int,
    token_data: dict = Depends(verify_token)
):
    """
    Get a specific application by ID
    Returns full application data with Gmail web URL
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications/{app_id}",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Application not found")
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to get application: {str(e)}")
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
