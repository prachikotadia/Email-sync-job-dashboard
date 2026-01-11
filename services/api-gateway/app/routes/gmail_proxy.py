"""
Gmail OAuth and connection proxy routes.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, Response
from app.middleware.auth import require_auth
from app.utils.errors import create_error_response, get_request_id
from app.config import get_settings
import httpx
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Gmail connector service URL
GMAIL_SERVICE_URL = "http://localhost:8001"  # Default for local dev, override with env var


@router.get("/gmail/auth/url")
async def get_gmail_auth_url(request: Request):
    """Get Gmail OAuth authorization URL (JWT required)."""
    request_id = get_request_id(request)
    
    # Verify JWT
    user_context = await require_auth(request)
    if not user_context:
        return create_error_response(
            code="UNAUTHORIZED",
            message="Authentication required",
            status_code=401,
            request_id=request_id
        )
    
    # Attach user context to request state
    request.state.user_context = user_context
    
    try:
        # Forward request to gmail-connector-service
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/auth/gmail/url",
                headers=headers
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


@router.get("/gmail/callback")
async def gmail_oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    error: str = Query(None)
):
    """Handle Gmail OAuth callback (proxy to gmail-connector-service)."""
    request_id = get_request_id(request)
    
    try:
        # Forward callback to gmail-connector-service
        query_params = {
            "code": code,
            "state": state
        }
        if error:
            query_params["error"] = error
        
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


@router.get("/gmail/status")
async def get_gmail_status(request: Request):
    """Get Gmail connection status (JWT required)."""
    request_id = get_request_id(request)
    
    # Verify JWT
    user_context = await require_auth(request)
    if not user_context:
        return create_error_response(
            code="UNAUTHORIZED",
            message="Authentication required",
            status_code=401,
            request_id=request_id
        )
    
    # Attach user context to request state
    request.state.user_context = user_context
    
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
async def disconnect_gmail(request: Request):
    """Disconnect Gmail account (JWT required)."""
    request_id = get_request_id(request)
    
    # Verify JWT
    user_context = await require_auth(request)
    if not user_context:
        return create_error_response(
            code="UNAUTHORIZED",
            message="Authentication required",
            status_code=401,
            request_id=request_id
        )
    
    # Attach user context to request state
    request.state.user_context = user_context
    
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