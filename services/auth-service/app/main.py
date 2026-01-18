# Section 2 / Step 4: Auth Service only. Google OAuth, backend JWT, /auth/me.
# No Gmail, no sync, no classification.

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from app.google_oauth import GoogleOAuth
from app.jwt import create_access_token, verify_token
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import time
import httpx
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_health_start = time.time()

app = FastAPI(title="Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth = GoogleOAuth(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8001/auth/callback"),
)


class CallbackRequest(BaseModel):
    code: str


class LogoutRequest(BaseModel):
    user_id: str


def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[7:].strip()


# --- Section 2.1: Login ---
@app.get("/auth/login")
async def login():
    """
    Initiate Google OAuth. Returns auth_url for redirect. Backend will validate
    Google token on callback and issue its own JWT. Frontend stores ONLY backend JWT.
    """
    try:
        auth_url = oauth.get_authorization_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate login: {str(e)}")


# --- Section 2.1: Callback — validate Google token, issue backend JWT ---
@app.post("/auth/callback")
async def callback(request: CallbackRequest):
    """
    Exchange code with Google (validates Google token). Get user info. Issue backend JWT.
    Store OAuth tokens in gmail-connector service for Gmail access.
    Returns { token, user }. Frontend must store ONLY this token; never Google tokens.
    """
    try:
        if not request.code:
            logger.error("Missing authorization code in request")
            raise HTTPException(status_code=400, detail="Missing authorization code")
        
        logger.info(f"Processing OAuth callback with code (length: {len(request.code)})")
        logger.info(f"Redirect URI configured: {os.getenv('REDIRECT_URI')}")
        logger.info(f"Code starts with: {request.code[:20]}...")
        
        try:
            tokens = await oauth.exchange_code(request.code)
            logger.info("Successfully exchanged code for tokens")
        except Exception as e:
            error_detail = str(e)
            logger.error(f"OAuth exchange failed: {error_detail}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception args: {e.args if hasattr(e, 'args') else 'N/A'}")
            # Print full traceback
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=400, detail=f"Failed to exchange authorization code: {error_detail}")
        
        if not tokens or "access_token" not in tokens:
            raise HTTPException(status_code=400, detail="Failed to obtain access token from Google")
        
        user_info = await oauth.get_user_info(tokens["access_token"])
        
        # Calculate token expiration (default 1 hour, but check actual expiry if available)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        if "expires_in" in tokens:
            expires_at = datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
        
        # Store OAuth tokens in gmail-connector service
        gmail_service_url = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
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
        except Exception as e:
            # Log but don't fail - tokens can be stored later
            print(f"Warning: Failed to store OAuth tokens in gmail service: {e}")
        
        token_data = {
            "sub": user_info["email"],
            "email": user_info["email"],
            "name": user_info.get("name", ""),
        }
        jwt_token = create_access_token(token_data)
        return {
            "token": jwt_token,
            "user": {"email": user_info["email"], "name": user_info.get("name", "")},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to handle callback: {str(e)}")


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
