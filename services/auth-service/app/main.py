"""
Auth Service - Google OAuth 2.0 + OpenID Connect + JWT

This service handles:
1. Google OAuth 2.0 authorization flow with OpenID Connect
2. JWT token generation for authenticated users
3. User information retrieval and validation
4. OAuth token storage for Gmail connector service

Security Features:
- CSRF protection via OAuth state parameter
- Scope validation to prevent scope mismatch errors
- OpenID Connect ID token verification
- Secure token storage (never logged)
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from app.google_oauth import GoogleOAuth
from app.jwt import create_access_token, verify_token
from app.oauth_config import OAUTH_SCOPES
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import time
import httpx
import logging
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_health_start = time.time()

app = FastAPI(
    title="Auth Service",
    description="Google OAuth 2.0 + OpenID Connect authentication service"
)

# CORS configuration
# In production, restrict allow_origins to your frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OAuth client
# All configuration comes from environment variables
oauth = GoogleOAuth(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8000/api/auth/callback"),
)


class CallbackRequest(BaseModel):
    """OAuth callback request with authorization code and optional state."""
    code: str
    state: Optional[str] = None  # CSRF protection token


class LogoutRequest(BaseModel):
    user_id: str


def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[7:].strip()


# --- OAuth Login Endpoint ---
@app.get("/auth/login")
async def login(state: Optional[str] = Query(None)):
    """
    Initiate Google OAuth 2.0 + OpenID Connect flow.
    
    Returns authorization URL that the frontend should redirect the user to.
    The same scopes are used here and in the callback to prevent scope mismatch errors.
    
    Args:
        state: Optional state parameter for CSRF protection.
              If not provided, a random state is generated and returned.
    
    Returns:
        {
            "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
            "state": "csrf_protection_token"
        }
    """
    try:
        auth_url, state_token = oauth.get_authorization_url(state=state)
        
        logger.info(f"Generated OAuth authorization URL")
        logger.info(f"Requested scopes: {', '.join(OAUTH_SCOPES)}")
        logger.info(f"State token: {state_token[:16]}...")
        
        return {
            "auth_url": auth_url,
            "state": state_token,  # Frontend should store this for CSRF validation
        }
    except Exception as e:
        logger.error(f"Failed to initiate OAuth login: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate login: {str(e)}"
        )


# --- OAuth Callback Endpoint ---
@app.post("/auth/callback")
async def callback(request: CallbackRequest):
    """
    Exchange OAuth authorization code for tokens and issue backend JWT.
    
    This endpoint:
    1. Validates the authorization code and optional state parameter
    2. Exchanges code for OAuth tokens using the SAME scopes as login
    3. Validates returned scopes match requested scopes
    4. Verifies OpenID Connect ID token (if present)
    5. Retrieves user information from Google
    6. Stores OAuth tokens in gmail-connector service
    7. Issues backend JWT token for the user
    
    Args:
        request: CallbackRequest with code and optional state
    
    Returns:
        {
            "token": "backend_jwt_token",
            "user": {
                "email": "user@example.com",
                "name": "User Name"
            }
        }
    
    Raises:
        HTTPException: 400 if OAuth exchange fails or scopes don't match
        HTTPException: 500 for unexpected errors (with request_id for tracking)
    """
    # Generate request ID for error tracking
    request_id = str(uuid.uuid4())[:8]
    
    try:
        # Validate authorization code
        if not request.code:
            logger.error("Missing authorization code in request")
            raise HTTPException(
                status_code=400,
                detail="Missing authorization code"
            )
        
        logger.info(f"Processing OAuth callback")
        logger.info(f"Code length: {len(request.code)}")
        logger.info(f"State provided: {bool(request.state)}")
        logger.info(f"Redirect URI: {os.getenv('REDIRECT_URI')}")
        logger.info(f"Requested scopes: {', '.join(OAUTH_SCOPES)}")
        
        # Exchange authorization code for tokens
        # This uses the SAME scopes and redirect_uri as get_authorization_url()
        try:
            tokens = await oauth.exchange_code(
                code=request.code,
                state=request.state
            )
            logger.info("Successfully exchanged code for tokens")
            logger.info(f"Granted scopes: {', '.join(tokens.get('scopes', []))}")
        except ValueError as e:
            # Scope validation error
            error_detail = str(e)
            logger.error(f"OAuth scope validation failed: {error_detail}")
            raise HTTPException(
                status_code=400,
                detail=f"OAuth scope validation failed: {error_detail}"
            )
        except Exception as e:
            # Other OAuth errors
            error_detail = str(e)
            logger.error(f"OAuth exchange failed: {error_detail}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange authorization code: {error_detail}"
            )
        
        # Validate tokens were received
        if not tokens or "access_token" not in tokens:
            logger.error("No access token in token response")
            raise HTTPException(
                status_code=400,
                detail="Failed to obtain access token from Google"
            )
        
        # Get user information from Google
        try:
            user_info = await oauth.get_user_info(tokens["access_token"])
            logger.info(f"Retrieved user info for: {user_info.get('email', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to retrieve user information: {str(e)}"
            )
        
        # Calculate token expiration
        expires_at = datetime.utcnow() + timedelta(hours=1)
        if "expires_at" in tokens:
            try:
                expires_at = datetime.fromisoformat(tokens["expires_at"].replace('Z', '+00:00'))
            except Exception:
                pass
        elif "expires_in" in tokens:
            expires_at = datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
        
        # Store OAuth tokens in gmail-connector service for Gmail access
        gmail_service_url = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                store_response = await client.post(
                    f"{gmail_service_url}/oauth/store",
                    json={
                        "user_email": user_info["email"],
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens.get("refresh_token"),
                        "token_uri": tokens.get("token_uri"),
                        "client_id": tokens.get("client_id"),
                        "client_secret": tokens.get("client_secret"),
                        "scopes": tokens.get("scopes", []),
                        "expires_at": expires_at.isoformat(),
                    }
                )
                store_response.raise_for_status()
                logger.info("OAuth tokens stored in gmail-connector service")
        except Exception as e:
            # Log but don't fail - tokens can be stored later or user can re-authenticate
            logger.warning(f"Failed to store OAuth tokens in gmail service: {e}")
            # In production, you might want to queue this for retry
        
        # Create backend JWT token
        token_data = {
            "sub": user_info["email"],
            "email": user_info["email"],
            "name": user_info.get("name", ""),
        }
        jwt_token = create_access_token(token_data)
        
        logger.info(f"Successfully authenticated user: {user_info.get('email')}")
        
        return {
            "token": jwt_token,
            "user": {
                "email": user_info["email"],
                "name": user_info.get("name", ""),
            },
        }
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        
        # Log full error details (but never log secrets)
        logger.error(
            f"Unexpected error in OAuth callback [request_id={request_id}]: "
            f"type={error_type}, message={error_message}",
            exc_info=True
        )
        
        # Return structured error response without exposing internals
        raise HTTPException(
            status_code=500,
            detail={
                "error": "OAuth callback failed",
                "detail": "An unexpected error occurred during authentication",
                "request_id": request_id
            }
        )


# --- /auth/me: verify backend JWT, return current user ---
@app.get("/auth/me")
async def get_me(token: str = Depends(get_bearer_token)):
    """
    Verify backend JWT from Authorization: Bearer <token>. Return { email, name }.
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"email": payload.get("email", ""), "name": payload.get("name", "")}


@app.post("/auth/logout")
async def logout(request: LogoutRequest):
    """Acknowledge logout. Data clearing is done in gmail-connector."""
    return {"message": "Logged out"}


@app.get("/health")
async def health():
    goog = bool(os.getenv("GOOGLE_CLIENT_ID")) and bool(os.getenv("GOOGLE_CLIENT_SECRET"))
    return {
        "status": "ok",
        "service": "auth-service",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "uptime_seconds": round(time.time() - _health_start, 2),
        "google_oauth_configured": goog,
    }
