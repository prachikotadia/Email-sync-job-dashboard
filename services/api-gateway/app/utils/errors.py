from fastapi import Request
from fastapi.responses import JSONResponse
from app.schemas.errors import ErrorResponse, ErrorDetail
import logging

logger = logging.getLogger(__name__)


def create_error_response(
    code: str,
    message: str,
    status_code: int,
    request_id: str = None
) -> JSONResponse:
    """Create a standardized error response."""
    error_detail = ErrorDetail(
        code=code,
        message=message,
        request_id=request_id
    )
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error_detail).dict()
    )


def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")


def add_user_headers(request: Request, headers: dict) -> dict:
    """Add user context headers to forwarded request."""
    user_id = getattr(request.state, "user_id", None)
    user_email = getattr(request.state, "user_email", None)
    user_role = getattr(request.state, "user_role", None)
    request_id = get_request_id(request)
    
    if user_id:
        headers["X-User-Id"] = user_id
    if user_email:
        headers["X-User-Email"] = user_email
    if user_role:
        headers["X-User-Role"] = user_role
    if request_id:
        headers["X-Request-Id"] = request_id
    
    return headers
