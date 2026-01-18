from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import httpx
import os
import logging
from app.middleware.auth_middleware import verify_token

router = APIRouter()
logger = logging.getLogger(__name__)

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

@router.post("/sync")
async def start_sync(token_data: dict = Depends(verify_token)):
    """
    Start Gmail sync
    Returns sync_id and status
    Contract: { "sync_id": "uuid", "status": "started" }
    """
    user_id = token_data.get("sub")
    user_email = token_data.get("email")  # Get email from JWT for validation
    
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    url = f"{GMAIL_SERVICE_URL}/sync/start"
    logger.info(f"API Gateway: Calling Gmail service at {url} for user {user_email}")
    
    try:
        # Reduced timeout since /sync/start should return immediately (sync runs in background)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    url,
                    json={"user_id": user_id, "user_email": user_email},
                    follow_redirects=True
                )
            except httpx.ConnectError as conn_err:
                logger.error(f"API Gateway: Cannot connect to Gmail service at {url}: {conn_err}")
                raise HTTPException(
                    status_code=503, 
                    detail=f"Cannot connect to Gmail service. Check if gmail-connector-service is running."
                )
            except httpx.TimeoutException as timeout_err:
                logger.error(f"API Gateway: Gmail service timeout after 30s: {timeout_err}")
                raise HTTPException(status_code=503, detail="Gmail service timeout")
            
            logger.info(f"API Gateway: Gmail service response status: {response.status_code}")
            
            if response.status_code == 409:
                # Sync already running
                detail = "Sync already running"
                try:
                    detail = response.json().get("detail", detail)
                except:
                    pass
                raise HTTPException(status_code=409, detail=detail)
            
            # Handle 202 Accepted (sync started)
            if response.status_code == 202:
                try:
                    data = response.json()
                    sync_id = data.get("job_id") or data.get("sync_id")
                    if not sync_id:
                        logger.error(f"API Gateway: Gmail service 202 response missing sync_id: {data}")
                        raise HTTPException(status_code=503, detail="Gmail service response missing sync_id")
                    logger.info(f"API Gateway: Sync started successfully with ID: {sync_id}")
                    return {
                        "sync_id": sync_id,
                        "status": data.get("status", "pending")
                    }
                except Exception as parse_err:
                    logger.error(f"API Gateway: Failed to parse Gmail service 202 response: {parse_err}")
                    raise HTTPException(status_code=503, detail="Gmail service returned invalid response")
            
            # Check for error status codes
            if response.status_code >= 500:
                logger.error(f"API Gateway: Gmail service returned {response.status_code}")
                raise HTTPException(status_code=503, detail="Gmail service unavailable")
            
            if response.status_code >= 400:
                try:
                    error_detail = response.json().get("detail", f"Gmail service error: {response.status_code}")
                except:
                    error_detail = f"Gmail service error: {response.status_code}"
                logger.error(f"API Gateway: Gmail service error {response.status_code}: {error_detail}")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            
            # Parse response
            try:
                data = response.json()
            except Exception as parse_err:
                logger.error(f"API Gateway: Failed to parse Gmail service response: {parse_err}")
                raise HTTPException(status_code=503, detail="Gmail service returned invalid response")
            
            # Map job_id to sync_id for contract compliance
            sync_id = data.get("job_id") or data.get("sync_id")
            if not sync_id:
                logger.error(f"API Gateway: Gmail service response missing sync_id: {data}")
                raise HTTPException(status_code=503, detail="Gmail service response missing sync_id")
            
            logger.info(f"API Gateway: Sync started successfully with ID: {sync_id}")
            return {
                "sync_id": sync_id,
                "status": data.get("status", "started")
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Gateway: Unexpected error calling Gmail service: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Gmail service error: {str(e)}")

@router.post("/sync/start")
async def start_sync_legacy(token_data: dict = Depends(verify_token)):
    """
    Legacy endpoint - redirects to /sync
    """
    return await start_sync(token_data)

@router.get("/sync/status")
async def get_sync_status(sync_id: str = Query(..., alias="sync_id"), token_data: dict = Depends(verify_token)):
    """
    Get sync status (for polling)
    Returns real-time counts from backend
    NEVER returns 503 to frontend - returns 200 with state:"unavailable" if service down
    Contract format: { "status": "running|completed|failed|unavailable", "emails_fetched": ..., "counts": {...}, ... }
    """
    user_id = token_data.get("sub")
    
    try:
        # Use short timeout for inter-service call (2-5s) - status should be fast
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/sync/status",
                params={"sync_id": sync_id, "user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as timeout_err:
        # Service timeout - return 200 with unavailable state (NOT 503)
        logger.warning(f"API Gateway: Gmail service timeout for /sync/status: {timeout_err}")
        return {
            "status": "unavailable",
            "sync_id": sync_id,
            "error": "Gmail service timeout",
            "retryAfterSeconds": 5,
            "emails_fetched": 0,
            "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0}
        }
    except httpx.ConnectError as conn_err:
        # Service unreachable - return 200 with unavailable state (NOT 503)
        logger.warning(f"API Gateway: Cannot connect to Gmail service at {GMAIL_SERVICE_URL}: {conn_err}")
        return {
            "status": "unavailable",
            "sync_id": sync_id,
            "error": "Gmail service unavailable",
            "retryAfterSeconds": 10,
            "emails_fetched": 0,
            "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0}
        }
    except httpx.HTTPStatusError as status_err:
        # Forward status codes from Gmail service (404, 403, etc.) - these are NOT 503
        if status_err.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Sync job not found")
        elif status_err.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized")
        else:
            # Other errors - return 200 with unavailable state (NOT 503)
            logger.warning(f"API Gateway: Gmail service returned {status_err.response.status_code}: {status_err}")
            return {
                "status": "unavailable",
                "sync_id": sync_id,
                "error": f"Gmail service error: {status_err.response.status_code}",
                "retryAfterSeconds": 10,
                "emails_fetched": 0,
                "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0}
            }
    except httpx.HTTPError as e:
        # Generic HTTP error - return 200 with unavailable state (NOT 503)
        logger.warning(f"API Gateway: HTTP error calling Gmail service: {e}")
        return {
            "status": "unavailable",
            "sync_id": sync_id,
            "error": "Gmail service unavailable",
            "retryAfterSeconds": 10,
            "emails_fetched": 0,
            "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0}
        }

@router.get("/sync/progress/{job_id}")
async def get_sync_progress(job_id: str, token_data: dict = Depends(verify_token)):
    """
    Legacy endpoint - redirects to /sync/status
    """
    return await get_sync_status(sync_id=job_id, token_data=token_data)

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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
