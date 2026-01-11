from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from app.clients.application_client import application_client
from app.middleware.auth import require_auth, UserContext, check_rbac
from app.utils.errors import create_error_response, get_request_id, add_user_headers
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/resumes/upload")
async def upload_resume(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy POST /resumes/upload to application-service (JWT required, RBAC enforced)."""
    try:
        # Attach user context to request state for downstream services
        request.state.user_id = current_user.user_id
        request.state.user_email = current_user.email
        request.state.user_role = current_user.role
        
        if not check_rbac(current_user, "POST"):
            request_id = get_request_id(request)
            return create_error_response(
                code="FORBIDDEN",
                message="Insufficient permissions. Viewers can only read data.",
                status_code=403,
                request_id=request_id
            )
        
        # Forward multipart/form-data as-is with proper content-type and boundary
        headers = dict(request.headers)
        headers.pop("host", None)
        # Preserve the original content-type header which includes the boundary
        content_type = request.headers.get("content-type", "multipart/form-data")
        if "boundary" not in content_type and "multipart" in content_type:
            # If boundary is missing, httpx will add it, but preserve original if present
            pass
        headers["content-type"] = content_type
        headers = add_user_headers(request, headers)
        
        # Read the raw body for multipart forwarding
        body = await request.body()
        
        # Use httpx to forward the raw multipart request
        from httpx import AsyncClient
        async with AsyncClient(timeout=application_client.timeout) as client:
            response = await client.post(
                f"{application_client.base_url}/resumes/upload",
                headers=headers,
                content=body
            )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying POST /resumes/upload: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="APPLICATION_SERVICE_ERROR",
            message="Failed to upload resume",
            status_code=500,
            request_id=request_id
        )


@router.get("/resumes")
async def list_resumes(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy GET /resumes to application-service (JWT required, RBAC enforced)."""
    try:
        # Attach user context to request state for downstream services
        request.state.user_id = current_user.user_id
        request.state.user_email = current_user.email
        request.state.user_role = current_user.role
        
        if not check_rbac(current_user, "GET"):
            request_id = get_request_id(request)
            return create_error_response(
                code="FORBIDDEN",
                message="Insufficient permissions",
                status_code=403,
                request_id=request_id
            )
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers = add_user_headers(request, headers)
        
        response = await application_client.forward_request(
            method="GET",
            path="/resumes",
            headers=headers
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying GET /resumes: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="APPLICATION_SERVICE_ERROR",
            message="Failed to list resumes",
            status_code=500,
            request_id=request_id
        )
