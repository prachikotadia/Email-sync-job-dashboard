# Section 2 / Step 4: Auth Service only. Google OAuth, backend JWT, /auth/me.
# No Gmail, no sync, no classification.

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from app.google_oauth import GoogleOAuth
from app.jwt import create_access_token, verify_token
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import os
import time

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
    Returns { token, user }. Frontend must store ONLY this token; never Google tokens.
    """
    try:
        tokens = await oauth.exchange_code(request.code)
        user_info = await oauth.get_user_info(tokens["access_token"])
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
