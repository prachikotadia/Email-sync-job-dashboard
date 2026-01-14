from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
from app.clients.application_client import application_client
from app.middleware.auth import require_auth, get_current_user, UserContext, check_rbac
from app.utils.errors import create_error_response, get_request_id, add_user_headers
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
async def get_metrics(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy GET /metrics to application-service (JWT required, RBAC enforced)."""
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
            path="/metrics/",
            headers=headers
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 401 from require_auth)
        raise
    except Exception as e:
        logger.error(f"Error proxying GET /metrics: {e}", exc_info=True)
        request_id = get_request_id(request)
        return create_error_response(
            code="APPLICATION_SERVICE_ERROR",
            message="Failed to fetch metrics",
            status_code=500,
            request_id=request_id
        )
