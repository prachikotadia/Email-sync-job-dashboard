from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import Response
from app.clients.application_client import application_client
from app.middleware.auth import require_auth, UserContext, check_rbac
from app.utils.errors import create_error_response, get_request_id, add_user_headers
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/applications")
async def get_applications(
    request: Request,
    current_user: UserContext = Depends(require_auth),
    status: str = Query(None)
):
    """Proxy GET /applications to application-service (JWT required, RBAC enforced)."""
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
        
        params = {}
        if status:
            params["status"] = status
        
        response = await application_client.forward_request(
            method="GET",
            path="/applications",
            headers=headers,
            params=params
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error proxying GET /applications: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="APPLICATION_SERVICE_ERROR",
            message="Failed to fetch applications",
            status_code=500,
            request_id=request_id
        )


@router.patch("/applications/{application_id}")
async def update_application(
    application_id: str,
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy PATCH /applications/{id} to application-service (JWT required, RBAC enforced)."""
    try:
        # Attach user context to request state for downstream services
        request.state.user_id = current_user.user_id
        request.state.user_email = current_user.email
        request.state.user_role = current_user.role
        
        if not check_rbac(current_user, "PATCH"):
            request_id = get_request_id(request)
            return create_error_response(
                code="FORBIDDEN",
                message="Insufficient permissions. Viewers can only read data.",
                status_code=403,
                request_id=request_id
            )
        
        import json
        body_bytes = await request.body()
        body_dict = json.loads(body_bytes) if body_bytes else None
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        headers["content-type"] = "application/json"
        headers = add_user_headers(request, headers)
        
        response = await application_client.forward_request(
            method="PATCH",
            path=f"/applications/{application_id}",
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
        logger.error(f"Error proxying PATCH /applications/{application_id}: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="APPLICATION_SERVICE_ERROR",
            message="Failed to update application",
            status_code=500,
            request_id=request_id
        )
