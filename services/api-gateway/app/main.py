from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.middleware.cors import setup_cors
from app.middleware.request_id import RequestIDMiddleware
from app.routes import health, auth_proxy, applications_proxy, resumes_proxy, export_proxy, gmail_proxy, metrics_proxy, debug
from app.utils.errors import create_error_response, get_request_id
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Validate redirect URI on startup
try:
    settings.validate_redirect_uri()
    redirect_uri = settings.get_google_redirect_uri()
    logger.info(f"Google OAuth redirect URI validated: {redirect_uri}")
except ValueError as e:
    logger.error(f"Invalid GOOGLE_REDIRECT_URI configuration: {e}")
    raise

app = FastAPI(
    title="API Gateway",
    description="API Gateway for Email Sync Job Dashboard",
    version="1.0.0",
    redirect_slashes=False  # Disable automatic redirects for trailing slashes
)

# Middleware (order matters - CORS should be added first to handle preflight requests)
setup_cors(app)
app.add_middleware(RequestIDMiddleware)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    request_id = get_request_id(request)
    return create_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        status_code=500,
        request_id=request_id
    )


# Routes
app.include_router(health.router)
app.include_router(auth_proxy.router)
app.include_router(applications_proxy.router)
app.include_router(metrics_proxy.router)
app.include_router(resumes_proxy.router)
app.include_router(export_proxy.router)
app.include_router(gmail_proxy.router)
app.include_router(debug.router)  # Debug endpoints (dev only)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
