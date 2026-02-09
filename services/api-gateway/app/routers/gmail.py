from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
import httpx
import os
import logging
from app.middleware.auth_middleware import verify_token

router = APIRouter()
logger = logging.getLogger(__name__)

GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")

class SyncRequest(BaseModel):
    mode: Optional[str] = "full_history"  # "full_history" or "time_range"
    time_range_months: Optional[int] = None  # For time_range mode: 3, 6, 12, or 16
    
    @field_validator('time_range_months')
    @classmethod
    def validate_time_range_months(cls, v):
        """Validate time_range_months is one of the allowed values."""
        if v is not None:
            valid_months = [3, 6, 12, 16]
            if v not in valid_months:
                raise ValueError(f"Invalid time_range_months: {v}. Must be one of: {valid_months}")
        return v
    
    @model_validator(mode='after')
    def validate_mode_and_months(self):
        """Validate that mode and time_range_months are consistent."""
        if self.time_range_months is not None:
            # If time_range_months is provided, mode MUST be time_range
            if self.mode != "time_range":
                self.mode = "time_range"
        elif self.mode == "time_range":
            # Mode is time_range but no months provided - invalid
            raise ValueError("time_range mode requires time_range_months parameter (3, 6, 12, or 16)")
        return self

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
async def start_sync(
    request: Optional[SyncRequest] = Body(None),
    token_data: dict = Depends(verify_token)
):
    """
    Start Gmail sync
    Supports Mode A (Full History) and Mode B (Time Range)
    Returns sync_id and status immediately - sync runs in background
    Contract: { "sync_id": "uuid", "status": "started" }
    """
    user_id = token_data.get("sub")
    user_email = token_data.get("email")  # Get email from JWT for validation
    
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Prepare request body - convert mode/time_range_months to range field
    request_body = {
        "user_id": user_id,
        "user_email": user_email
    }
    
    # PERFECT TIME RANGE CONVERSION: Convert mode/time_range_months to range field
    # CRITICAL: If time_range_months is provided, it MUST be used (strict enforcement)
    if request:
        mode = request.mode or "full_history"
        time_range_months = request.time_range_months
        
        # STRICT LOGIC: If time_range_months is provided, it MUST be time_range mode
        if time_range_months is not None:
            # Validate time_range_months is one of the allowed values
            valid_months = [3, 6, 12, 16]
            if time_range_months not in valid_months:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid time_range_months: {time_range_months}. Must be one of: {', '.join(map(str, valid_months))}"
                )
            # Force time_range mode when months are specified
            mode = "time_range"
            request_body["range"] = f"{time_range_months}M"
            logger.info(f"TIME RANGE SYNC: {time_range_months} months (strict enforcement)")
        elif mode == "full_history" or not time_range_months:
            # Full history mode
            request_body["range"] = "FULL"
            logger.info("FULL HISTORY SYNC: All emails (no time filter)")
        else:
            # Invalid state: mode is time_range but no months provided
            raise HTTPException(
                status_code=400,
                detail="time_range mode requires time_range_months parameter (3, 6, 12, or 16)"
            )
    else:
        # Default to full history if no request body provided
        request_body["range"] = "FULL"
        logger.info("FULL HISTORY SYNC: Default (no request body)")
    
    url = f"{GMAIL_SERVICE_URL}/sync/start"
    logger.info(f"API Gateway: Calling Gmail service at {url} for user {user_email}, mode={request_body.get('mode')}")
    
    try:
        # Reduced timeout since /sync/start should return immediately (sync runs in background)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    url,
                    json=request_body,
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

@router.post("/sync/stop/{sync_id}")
async def stop_sync(sync_id: str, token_data: dict = Depends(verify_token)):
    """
    Cancel/stop a running sync job.
    Returns immediately after setting CANCEL_REQUESTED status.
    Worker will detect cancellation and stop mid-sync.
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/sync/stop/{sync_id}",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Sync job not found")
        elif e.response.status_code == 403:
            raise HTTPException(status_code=403, detail="Unauthorized")
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to cancel sync: {str(e)}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.post("/backfill/company")
async def backfill_company(
    user_id: Optional[str] = Query(None, description="User email; if omitted, backfill for current user"),
    token_data: dict = Depends(verify_token)
):
    """
    Backfill company_name (and company_source, company_confidence, company_debug)
    for applications that have Unknown/Unknown Company. Uses subject, snippet, from_email.
    """
    try:
        params = {}
        if user_id:
            params["user_id"] = user_id
        else:
            params["user_id"] = token_data.get("sub")
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/backfill/company",
                params=params
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="Gmail service unavailable")


@router.get("/applications")
async def get_applications(
    search: str = Query(None),
    status: str = Query(None),
    company: Optional[str] = Query(None, description="Filter by company name"),
    token_data: dict = Depends(verify_token)
):
    """
    Get all applications (flat list)
    NO pagination limits - returns ALL fetched emails
    Response includes gmail_web_url for opening emails
    
    Supports filtering by company name.
    """
    user_id = token_data.get("sub")
    
    try:
        params = {"user_id": user_id}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        if company:
            params["company"] = company
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications",
                params=params
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")


@router.get("/applications/company/{company_name}")
async def get_company_applications(
    company_name: str,
    search: Optional[str] = Query(None),
    status: Optional[List[str]] = Query(None),
    sort_by: str = Query("received_at"),
    sort_order: str = Query("desc"),
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    token_data: dict = Depends(verify_token)
):
    """
    Get applications for a specific company.
    Supports search, filters, sorting, and cursor-based pagination.
    """
    user_id = token_data.get("sub")
    
    try:
        query_params = [("user_id", user_id)]
        if search:
            query_params.append(("search", search))
        if status:
            for s in status:
                query_params.append(("status", s))
        query_params.append(("sort_by", sort_by))
        query_params.append(("sort_order", sort_order))
        if cursor:
            query_params.append(("cursor", cursor))
        query_params.append(("limit", str(limit)))
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications/company/{company_name}",
                params=query_params
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")


@router.get("/applications/grouped-by-company")
async def get_applications_grouped_by_company(
    token_data: dict = Depends(verify_token)
):
    """
    Get applications grouped by company (summary only).
    
    Returns company summary with:
    - company_name
    - total_applications
    - status breakdown
    - latest_applied_at
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications/grouped-by-company",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")


@router.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    fuzzy: bool = Query(False, description="Enable fuzzy/typo-tolerant search"),
    token_data: dict = Depends(verify_token)
):
    """
    Production-grade global search endpoint.
    
    Searches across company name, role, subject, and status.
    Returns ranked, paginated results.
    """
    user_id = token_data.get("sub")
    
    try:
        params = {
            "user_id": user_id,
            "q": q,
            "limit": limit,
            "offset": offset
        }
        if fuzzy:
            params["fuzzy"] = "true"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/search",
                params=params
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")


@router.get("/applications/search")
async def search_applications_advanced(
    q: Optional[str] = Query(None, description="Global search query"),
    status: Optional[List[str]] = Query(None, description="Status filter (multi-select)"),
    company: Optional[str] = Query(None, description="Company filter (exact match)"),
    role: Optional[str] = Query(None, description="Role filter (partial match)"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: str = Query("received_at", description="Sort field: received_at, company_name, or last_activity_at"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    token_data: dict = Depends(verify_token)
):
    """
    Advanced unified search endpoint with filters, pagination, and sorting.
    
    All logic is backend-driven for performance with large datasets.
    """
    user_id = token_data.get("sub")
    
    try:
        # Build query params list for httpx (handles multi-value params correctly)
        query_params = [("user_id", user_id)]
        
        if q:
            query_params.append(("q", q))
        
        if status:
            # Multi-value query param - add each status value
            for s in status:
                query_params.append(("status", s))
        
        if date_from:
            query_params.append(("date_from", date_from))
        
        if date_to:
            query_params.append(("date_to", date_to))
        
        if company:
            query_params.append(("company", company))
        
        if role:
            query_params.append(("role", role))
        
        query_params.extend([
            ("page", str(page)),
            ("page_size", str(page_size)),
            ("sort_by", sort_by),
            ("sort_order", sort_order)
        ])
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/applications/search",
                params=query_params
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

@router.get("/debug/email/{message_id}")
async def debug_email(
    message_id: str,
    token_data: dict = Depends(verify_token)
):
    """
    Debug endpoint to inspect firewall decision and classification for an email.
    Returns firewall decision, matched rules, and classification outputs.
    """
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/debug/email/{message_id}",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Email not found")
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to get debug info: {str(e)}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")
