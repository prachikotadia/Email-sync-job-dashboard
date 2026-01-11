from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from app.clients.application_client import application_client
from app.middleware.auth import require_auth, UserContext, check_rbac
from app.utils.errors import create_error_response, get_request_id, add_user_headers
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/export/excel")
async def export_excel(
    request: Request,
    current_user: UserContext = Depends(require_auth)
):
    """Proxy GET /export/excel to application-service (JWT required, RBAC enforced)."""
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
            path="/export/excel",
            headers=headers
        )
        
        # For Excel file, preserve content type and headers
        response_headers = dict(response.headers)
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers
        )
    except Exception as e:
        logger.error(f"Error proxying GET /export/excel: {e}")
        request_id = get_request_id(request)
        return create_error_response(
            code="APPLICATION_SERVICE_ERROR",
            message="Failed to export Excel file",
            status_code=500,
            request_id=request_id
        )
