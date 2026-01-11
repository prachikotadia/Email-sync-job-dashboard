from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, RedirectResponse
from app.clients.auth_client import auth_client
from app.middleware.auth import require_auth, UserContext
from app.utils.errors import create_error_response, get_request_id, add_user_headers
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/auth/register")
async def register_proxy(request: Request):
    """Proxy registration request to auth-service (no JWT required)."""
    try:
        import json
        body_bytes = await request.body()
        
        if not body_bytes:
            request_id = get_request_id(request)
            logger.error("Registration request received with empty body")
            return create_error_response(
                code="INVALID_REQUEST",
                message="Request body is required",
                status_code=400,
                request_id=request_id
            )
        
        try:
            body_dict = json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            request_id = get_request_id(request)
            logger.error(f"Invalid JSON in registration request: {e}")
            return create_error_response(
                code="INVALID_REQUEST",
                message="Invalid JSON in request body",
                status_code=400,
                request_id=request_id
            )
        
        logger.info(f"Forwarding registration request for email: {body_dict.get('email', 'unknown')}")
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        headers["content-type"] = "application/json"
        
        response = await auth_client.forward_request(
            method="POST",
            path="/auth/register",
            headers=headers,
            data=body_dict
        )
        
        # Log the response for debugging
        if response.status_code >= 400:
            logger.error(f"Auth service returned error: {response.status_code} - {response.text}")
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying registration: {e}", exc_info=True)
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message=f"Failed to process registration request: {str(e)}",
            status_code=500,
            request_id=request_id
        )


@router.post("/auth/login")
async def login_proxy(request: Request):
    """Proxy login request to auth-service (no JWT required)."""
    try:
        import json
        body_bytes = await request.body()
        body_dict = json.loads(body_bytes) if body_bytes else None
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        headers["content-type"] = "application/json"
        
        response = await auth_client.forward_request(
            method="POST",
            path="/auth/login",
            headers=headers,
            data=body_dict
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying login: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to process login request",
            status_code=500,
            request_id=request_id
        )


@router.post("/auth/refresh")
async def refresh_proxy(request: Request):
    """Proxy refresh request to auth-service (no JWT required)."""
    try:
        import json
        body_bytes = await request.body()
        body_dict = json.loads(body_bytes) if body_bytes else None
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        headers["content-type"] = "application/json"
        
        response = await auth_client.forward_request(
            method="POST",
            path="/auth/refresh",
            headers=headers,
            data=body_dict
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying refresh: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to process refresh request",
            status_code=500,
            request_id=request_id
        )


@router.post("/auth/logout")
async def logout_proxy(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy logout request to auth-service (JWT required)."""
    try:
        # Attach user context to request state for downstream services
        request.state.user_id = current_user.user_id
        request.state.user_email = current_user.email
        request.state.user_role = current_user.role
        
        import json
        body_bytes = await request.body()
        body_dict = json.loads(body_bytes) if body_bytes else None
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        headers["content-type"] = "application/json"
        headers = add_user_headers(request, headers)
        
        response = await auth_client.forward_request(
            method="POST",
            path="/auth/logout",
            headers=headers,
            data=body_dict
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying logout: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to process logout request",
            status_code=500,
            request_id=request_id
        )


@router.get("/auth/me")
async def me_proxy(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy /auth/me request to auth-service (JWT required)."""
    try:
        # Attach user context to request state for downstream services
        request.state.user_id = current_user.user_id
        request.state.user_email = current_user.email
        request.state.user_role = current_user.role
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers = add_user_headers(request, headers)
        
        response = await auth_client.forward_request(
            method="GET",
            path="/auth/me",
            headers=headers
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        logger.error(f"Error proxying /auth/me: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to get user info",
            status_code=500,
            request_id=request_id
        )


@router.get("/auth/google/login")
async def google_login_proxy(request: Request):
    """Proxy Google OAuth login initiation to auth-service (no JWT required)."""
    try:
        import httpx
        from app.config import get_settings
        
        settings = get_settings()
        redirect_uri = request.query_params.get("redirect_uri")
        
        # Build query params
        params = {}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/google/login",
                params=params
            )
            
            # If it's a redirect, return redirect response
            if response.status_code in [302, 301, 307, 308]:
                redirect_url = response.headers.get("location")
                if redirect_url:
                    return RedirectResponse(url=redirect_url, status_code=response.status_code)
            
            # Otherwise return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )
    except Exception as e:
        logger.error(f"Error proxying Google login: {e}", exc_info=True)
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to initiate Google login",
            status_code=500,
            request_id=request_id
        )


@router.get("/auth/google/callback")
async def google_callback_proxy(request: Request):
    """Proxy Google OAuth callback to auth-service (no JWT required)."""
    try:
        import httpx
        from app.config import get_settings
        
        settings = get_settings()
        query_params = dict(request.query_params)
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/google/callback",
                params=query_params
            )
            
            # If it's a redirect, return redirect response
            if response.status_code in [302, 301, 307, 308]:
                redirect_url = response.headers.get("location")
                if redirect_url:
                    return RedirectResponse(url=redirect_url, status_code=response.status_code)
            
            # Otherwise return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )
    except Exception as e:
        logger.error(f"Error proxying Google callback: {e}", exc_info=True)
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to process Google OAuth callback",
            status_code=500,
            request_id=request_id
        )