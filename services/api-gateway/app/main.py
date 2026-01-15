from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, RedirectResponse
from starlette.routing import Route
from app.config import get_settings
from app.middleware.cors import setup_cors
from app.middleware.request_id import RequestIDMiddleware
from app.routes import health, auth_proxy, applications_proxy, resumes_proxy, export_proxy, gmail_proxy, metrics_proxy, debug
from app.utils.errors import create_error_response, get_request_id
from app.utils.env_validation import validate_all
import logging
import httpx
import sys
import platform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log platform information for debugging
logger.info(f"🚀 Starting API Gateway on {platform.system()} {platform.release()}")
logger.info(f"   Python: {platform.python_version()}")
logger.info(f"   Platform: {platform.platform()}")

settings = get_settings()

# Validate environment variables at startup
if not validate_all():
    logger.error("❌ Environment validation failed. Please check your .env file.")
    sys.exit(1)

# Validate redirect URI on startup
try:
    settings.validate_redirect_uri()
    redirect_uri = settings.get_google_redirect_uri()
    logger.info(f"✅ Google OAuth redirect URI validated: {redirect_uri}")
except ValueError as e:
    logger.error(f"❌ Invalid GOOGLE_REDIRECT_URI configuration: {e}")
    raise

app = FastAPI(
    title="API Gateway",
    description="API Gateway for Email Sync Job Dashboard",
    version="1.0.0",
    redirect_slashes=False,
    docs_url=None,
    redoc_url=None
)

# Handler functions for Google OAuth routes
async def google_status_handler(request: Request):
    """Handler for /auth/google/status."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/google/status",
                cookies=request.cookies
            )
            if response.status_code == 200:
                data = response.json()
                return JSONResponse(content={
                    "authenticated": data.get("isAuthenticated", False),
                    "isAuthenticated": data.get("isAuthenticated", False),
                    "hasAccessToken": data.get("hasAccessToken", False),
                    "hasRefreshToken": data.get("hasRefreshToken", False),
                    "user": data.get("user") if data.get("user") else None,
                    "configured": data.get("configured", False),
                    "redirect_uri": data.get("redirect_uri", ""),
                }, status_code=200)
            return JSONResponse(content={
                "authenticated": False,
                "isAuthenticated": False,
                "hasAccessToken": False,
                "hasRefreshToken": False,
                "user": None,
                "configured": False,
                "redirect_uri": "",
            }, status_code=200)
    except Exception as e:
        logger.error(f"Error getting Google status: {e}", exc_info=True)
        return JSONResponse(content={
            "authenticated": False,
            "isAuthenticated": False,
            "hasAccessToken": False,
            "hasRefreshToken": False,
            "user": None,
            "configured": False,
            "redirect_uri": "",
        }, status_code=200)

async def google_login_handler(request: Request):
    """Handler for /auth/google/login."""
    try:
        redirect_uri = request.query_params.get("redirect_uri")
        params = {}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/google/login",
                params=params
            )
            
            if response.status_code in [302, 301, 307, 308]:
                redirect_url = response.headers.get("location")
                if redirect_url:
                    return RedirectResponse(url=redirect_url, status_code=response.status_code)
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )
    except Exception as e:
        logger.error(f"Error initiating Google login: {e}", exc_info=True)
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message=f"Failed to initiate Google login: {str(e)}",
            status_code=500,
            request_id=request_id
        )

async def google_callback_handler(request: Request):
    """Handler for /auth/google/callback - CRITICAL for OAuth flow."""
    try:
        query_params = dict(request.query_params)
        logger.info(f"✅ Google callback received: {list(query_params.keys())}")
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/google/callback",
                params=query_params,
                cookies=request.cookies
            )
            
            logger.info(f"✅ Auth service callback response: {response.status_code}")
            
            if response.status_code in [302, 301, 307, 308]:
                redirect_url = response.headers.get("location")
                if redirect_url:
                    logger.info(f"✅ Redirecting to: {redirect_url[:100]}...")
                    redirect_response = RedirectResponse(url=redirect_url, status_code=response.status_code)
                    # Copy Set-Cookie headers from auth service
                    for header, value in response.headers.items():
                        if header.lower() == "set-cookie":
                            redirect_response.headers.append("Set-Cookie", value)
                    return redirect_response
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )
    except Exception as e:
        logger.error(f"❌ Error processing Google callback: {e}", exc_info=True)
        request_id = get_request_id(request)
        return create_error_response(
            code="AUTH_SERVICE_ERROR",
            message="Failed to process Google OAuth callback",
            status_code=500,
            request_id=request_id
        )

async def favicon_handler(request: Request):
    """Handler for /favicon.ico."""
    return Response(status_code=204)

# CRITICAL: Add routes using Starlette Route BEFORE middleware
# This ensures they're registered at the lowest level and take precedence
app.router.routes.insert(0, Route("/auth/google/status", google_status_handler, methods=["GET", "OPTIONS"]))
app.router.routes.insert(0, Route("/auth/google/login", google_login_handler, methods=["GET", "OPTIONS"]))
app.router.routes.insert(0, Route("/auth/google/callback", google_callback_handler, methods=["GET", "OPTIONS"]))
app.router.routes.insert(0, Route("/favicon.ico", favicon_handler, methods=["GET", "HEAD", "OPTIONS"]))
logger.info("✅ Added Google OAuth routes via Starlette Route at router level")

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
        code="INTERNAL_SERVICE_ERROR",
        message="An unexpected error occurred",
        status_code=500,
        request_id=request_id
    )

# Routes - Include routers AFTER direct routes
app.include_router(health.router)
app.include_router(auth_proxy.router, tags=["auth"])
app.include_router(applications_proxy.router)
app.include_router(metrics_proxy.router)
app.include_router(resumes_proxy.router)
app.include_router(export_proxy.router)
app.include_router(gmail_proxy.router)
app.include_router(debug.router)

# Verify routes on startup
@app.on_event("startup")
async def verify_routes():
    """Verify Google OAuth routes are registered."""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and 'google' in route.path:
            methods = getattr(route, 'methods', [])
            routes.append(f"{route.path} - {methods}")
    if routes:
        logger.info(f"✅ Registered Google OAuth routes: {routes}")
    else:
        logger.warning("⚠️ No Google OAuth routes found!")

@app.get("/login")
@app.post("/login")
async def login_redirect():
    """Redirect /login to /auth/login for convenience."""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": "Use /auth/login for authentication"
            }
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
