"""
Gmail OAuth and connection proxy routes.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from app.middleware.auth import require_auth, UserContext
from app.utils.errors import create_error_response, get_request_id
from app.config import get_settings, get_google_redirect_uri
import httpx
import logging
import json
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Gmail connector service URL
GMAIL_SERVICE_URL = settings.GMAIL_SERVICE_URL

# Per-user sync lock (in-memory). Prevents accidental duplicate sync triggers.
_ACTIVE_GMAIL_SYNCS = set()
_ACTIVE_GMAIL_SYNCS_LOCK = asyncio.Lock()


@router.get("/gmail/connect")
async def connect_gmail(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """
    Initiate Gmail OAuth flow (redirects browser to Google).
    
    This is the entry point for Gmail connection. The gateway owns the OAuth flow.
    """
    request_id = get_request_id(request)
    
    try:
        # Get redirect URI (single source of truth)
        redirect_uri = get_google_redirect_uri()
        logger.info(f"Initiating Gmail OAuth flow with redirect_uri: {redirect_uri}")
        
        # Forward request to gmail-connector-service to get auth URL
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        # Pass redirect_uri as query parameter to gmail-connector-service
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/auth/gmail/url",
                headers=headers,
                params={"redirect_uri": redirect_uri}
            )
            
            if response.status_code == 200:
                data = response.json()
                auth_url = data.get("auth_url")
                if auth_url:
                    logger.info(f"Redirecting to Google OAuth URL")
                    return RedirectResponse(url=auth_url, status_code=302)
                else:
                    logger.error("Auth URL not found in response")
                    return create_error_response(
                        code="GMAIL_SERVICE_ERROR",
                        message="Failed to get Gmail auth URL: auth_url missing in response",
                        status_code=500,
                        request_id=request_id
                    )
            else:
                logger.error(f"Gmail service returned error: {response.status_code} - {response.text}")
                return create_error_response(
                    code="GMAIL_SERVICE_ERROR",
                    message=f"Failed to get Gmail auth URL: {response.text}",
                    status_code=response.status_code,
                    request_id=request_id
                )
    except httpx.RequestError as e:
        logger.error(f"Network error connecting to gmail-service: {e}")
        return create_error_response(
            code="NETWORK_ERROR",
            message="Could not connect to Gmail connector service",
            status_code=503,
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Unexpected error initiating Gmail OAuth: {e}", exc_info=True)
        return create_error_response(
            code="GATEWAY_ERROR",
            message="An unexpected error occurred in the API Gateway",
            status_code=500,
            request_id=request_id
        )


# Keep /gmail/auth/url for backward compatibility (but recommend /gmail/connect)
@router.get("/gmail/auth/url")
async def get_gmail_auth_url(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """
    Get Gmail OAuth authorization URL (JWT required).
    
    DEPRECATED: Use /gmail/connect instead, which redirects directly.
    This endpoint is kept for backward compatibility.
    """
    request_id = get_request_id(request)
    
    # Attach user context to request state
    request.state.user_context = current_user
    
    try:
        # Get redirect URI (single source of truth)
        redirect_uri = get_google_redirect_uri()
        
        # Forward request to gmail-connector-service
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/auth/gmail/url",
                headers=headers,
                params={"redirect_uri": redirect_uri}
            )
            
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    status_code=200,
                    headers=dict(response.headers),
                    media_type="application/json"
                )
            else:
                logger.error(f"Gmail service returned error: {response.status_code} - {response.text}")
                return create_error_response(
                    code="GMAIL_SERVICE_ERROR",
                    message=f"Failed to get Gmail auth URL: {response.text}",
                    status_code=response.status_code,
                    request_id=request_id
                )
    except httpx.RequestError as e:
        logger.error(f"Network error connecting to gmail-service: {e}")
        return create_error_response(
            code="NETWORK_ERROR",
            message="Could not connect to Gmail connector service",
            status_code=503,
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Unexpected error proxying Gmail auth URL request: {e}", exc_info=True)
        return create_error_response(
            code="GATEWAY_ERROR",
            message="An unexpected error occurred in the API Gateway",
            status_code=500,
            request_id=request_id
        )


@router.get("/auth/gmail/callback")
async def gmail_oauth_callback(
    request: Request,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None)
):
    """
    Handle Gmail OAuth callback (gateway receives callback from Google).
    
    This is the public callback endpoint registered in Google Cloud Console.
    The gateway validates and forwards to gmail-connector-service internal endpoint.
    """
    request_id = get_request_id(request)
    
    # Get redirect URI (must match what was used in authorization URL)
    redirect_uri = get_google_redirect_uri()
    logger.info(f"OAuth callback received with redirect_uri: {redirect_uri}")
    
    # If there's an error (e.g., user denied access), handle it directly
    if error:
        logger.warning(f"OAuth callback error: {error}")
        return RedirectResponse(
            url=f"http://localhost:5173/settings?gmail_error={error}",
            status_code=302
        )
    
    # If code or state is missing, redirect with error
    if not code or not state:
        logger.error(f"Missing required parameters: code={code is not None}, state={state is not None}")
        return RedirectResponse(
            url="http://localhost:5173/settings?gmail_error=invalid_callback",
            status_code=302
        )
    
    try:
        # Forward callback to gmail-connector-service internal endpoint
        # Pass redirect_uri to ensure token exchange uses the same URI
        query_params = {
            "code": code,
            "state": state,
            "redirect_uri": redirect_uri  # Pass the redirect URI for token exchange
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/auth/gmail/callback",
                params=query_params
            )
            
            # Return redirect response
            if response.status_code in [302, 301, 307, 308]:
                redirect_url = response.headers.get("location")
                if redirect_url:
                    return RedirectResponse(url=redirect_url, status_code=response.status_code)
            
            # If not a redirect, return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )
    except httpx.RequestError as e:
        logger.error(f"Network error in Gmail callback: {e}")
        return RedirectResponse(
            url="http://localhost:5173/settings?gmail_error=network_error",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Unexpected error in Gmail callback: {e}", exc_info=True)
        return RedirectResponse(
            url="http://localhost:5173/settings?gmail_error=callback_failed",
            status_code=302
        )


# Keep /gmail/callback as alias for backward compatibility
@router.get("/gmail/callback")
async def gmail_oauth_callback_alias(
    request: Request,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None)
):
    """Alias for /auth/gmail/callback (for backward compatibility)."""
    return await gmail_oauth_callback(request, code, state, error)


@router.post("/gmail/sync")
async def sync_gmail_emails(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Sync emails from Gmail with real-time progress streaming (JWT required)."""
    request_id = get_request_id(request)
    
    # Attach user context to request state
    request.state.user_context = current_user
    
    try:
        user_id = getattr(current_user, "user_id", None) or getattr(current_user, "id", None)
        if not user_id:
            return create_error_response(
                code="BAD_REQUEST",
                message="User ID missing from auth context",
                status_code=400,
                request_id=request_id,
            )

        # Forward request to gmail-connector-service with streaming support
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async def generate():
            acquired = False
            try:
                # Acquire per-user lock
                async with _ACTIVE_GMAIL_SYNCS_LOCK:
                    if user_id in _ACTIVE_GMAIL_SYNCS:
                        logger.info(f"Gmail sync skipped (already running) user_id={user_id} request_id={request_id}")
                        payload = {
                            "message": "Sync skipped: sync already running",
                            "progress": 100,
                            "stage": "Skipped",
                            "status": "skipped",
                            "reason": "sync already running",
                        }
                        yield f"data: {json.dumps(payload)}\n\n".encode()
                        return
                    _ACTIVE_GMAIL_SYNCS.add(user_id)
                    acquired = True

                logger.info(f"Forwarding sync request to {GMAIL_SERVICE_URL}/gmail/sync")
                # Use a longer timeout for streaming (5 minutes for read, since sync can take time)
                timeout = httpx.Timeout(300.0, connect=10.0, read=300.0, write=10.0, pool=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{GMAIL_SERVICE_URL}/gmail/sync",
                        headers=headers
                    ) as response:
                        # Check if response is successful
                        if response.status_code != 200:
                            error_text = await response.aread()
                            error_msg = error_text.decode() if error_text else f"HTTP {response.status_code}"
                            logger.error(f"Gmail service returned error: {response.status_code} - {error_msg}")
                            yield f"data: {json.dumps({'message': f'Sync failed: {error_msg}', 'progress': 0, 'stage': 'Error'})}\n\n".encode()
                            return
                        
                        logger.info("Streaming SSE response from Gmail service")
                        # Stream the SSE response
                        async for chunk in response.aiter_bytes():
                            yield chunk
            except httpx.ConnectError as e:
                logger.error(f"Connection error in sync stream: {e}")
                error_msg = json.dumps({'message': f'Cannot connect to Gmail service. Please ensure all services are running.', 'progress': 0, 'stage': 'Error'})
                yield f"data: {error_msg}\n\n".encode()
            except httpx.TimeoutException as e:
                logger.error(f"Timeout error in sync stream: {e}")
                error_msg = json.dumps({'message': f'Sync request timed out. Please try again.', 'progress': 0, 'stage': 'Error'})
                yield f"data: {error_msg}\n\n".encode()
            except httpx.RequestError as e:
                logger.error(f"Network error in sync stream: {e}")
                error_msg = json.dumps({'message': f'Network error: {str(e)}', 'progress': 0, 'stage': 'Error'})
                yield f"data: {error_msg}\n\n".encode()
            except Exception as e:
                logger.error(f"Unexpected error in sync stream: {e}", exc_info=True)
                error_msg = json.dumps({'message': f'Unexpected error: {str(e)}', 'progress': 0, 'stage': 'Error'})
                yield f"data: {error_msg}\n\n".encode()
            finally:
                if acquired:
                    async with _ACTIVE_GMAIL_SYNCS_LOCK:
                        _ACTIVE_GMAIL_SYNCS.discard(user_id)
        
        return StreamingResponse(
            generate(),
            status_code=200,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except httpx.RequestError as e:
        logger.error(f"Network error connecting to gmail-service: {e}")
        return create_error_response(
            code="NETWORK_ERROR",
            message="Could not connect to Gmail connector service",
            status_code=503,
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Unexpected error syncing emails: {e}", exc_info=True)
        return create_error_response(
            code="GATEWAY_ERROR",
            message="An unexpected error occurred in the API Gateway",
            status_code=500,
            request_id=request_id
        )


@router.get("/gmail/status")
async def get_gmail_status(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Get Gmail connection status (JWT required)."""
    request_id = get_request_id(request)
    
    # Attach user context to request state
    request.state.user_context = current_user
    
    try:
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/gmail/status",
                headers=headers
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json"
            )
    except httpx.RequestError as e:
        logger.error(f"Network error getting Gmail status: {e}")
        return create_error_response(
            code="NETWORK_ERROR",
            message="Could not connect to Gmail connector service",
            status_code=503,
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Unexpected error getting Gmail status: {e}", exc_info=True)
        return create_error_response(
            code="GATEWAY_ERROR",
            message="An unexpected error occurred",
            status_code=500,
            request_id=request_id
        )


@router.post("/gmail/disconnect")
async def disconnect_gmail(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Disconnect Gmail account (JWT required)."""
    request_id = get_request_id(request)
    
    # Attach user context to request state
    request.state.user_context = current_user
    
    try:
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/gmail/disconnect",
                headers=headers
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json"
            )
    except httpx.RequestError as e:
        logger.error(f"Network error disconnecting Gmail: {e}")
        return create_error_response(
            code="NETWORK_ERROR",
            message="Could not connect to Gmail connector service",
            status_code=503,
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Unexpected error disconnecting Gmail: {e}", exc_info=True)
        return create_error_response(
            code="GATEWAY_ERROR",
            message="An unexpected error occurred",
            status_code=500,
            request_id=request_id
        )
