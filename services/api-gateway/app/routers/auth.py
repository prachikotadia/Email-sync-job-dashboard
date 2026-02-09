from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
import httpx
import os
import logging
from typing import Optional
from app.middleware.auth_middleware import verify_token

router = APIRouter()
logger = logging.getLogger(__name__)


class CallbackBody(BaseModel):
    code: str
    state: Optional[str] = None

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://host.docker.internal:8001")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.get("/login")
async def initiate_login():
    """
    Initiate Google OAuth login
    Returns OAuth URL for frontend redirect
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AUTH_SERVICE_URL}/auth/login")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {str(e)}")

@router.get("/callback")
async def oauth_callback_redirect(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None)
):
    """
    OAuth callback redirect handler
    Redirects to frontend with the authorization code
    """
    if error:
        # Redirect to frontend login with error
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error={error}",
            status_code=302
        )
    
    if not code:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=missing_code",
            status_code=302
        )
    
    # Redirect to frontend with code and state
    params = f"?code={code}"
    if state:
        params += f"&state={state}"
    
    return RedirectResponse(
        url=f"{FRONTEND_URL}/auth/callback{params}",
        status_code=302
    )

@router.post("/callback")
async def handle_callback(body: CallbackBody):
    """
    Handle OAuth callback and return JWT token
    """
    code = body.code
    full_url = f"{AUTH_SERVICE_URL}/auth/callback"
    payload = {"code": code}
    if body.state is not None:
        payload["state"] = body.state

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(full_url, json=payload)
            if response.status_code != 200:
                error_text = response.text or ""
                logger.warning(f"Auth callback: auth-service returned {response.status_code}: {error_text[:500]}")
                try:
                    err_json = response.json()
                    detail = err_json.get("detail")
                    if isinstance(detail, dict):
                        msg = detail.get("detail") or detail.get("error") or detail.get("message") or error_text[:300]
                    else:
                        msg = detail if isinstance(detail, str) else error_text[:300]
                except Exception:
                    msg = error_text[:300]
                raise HTTPException(
                    status_code=response.status_code,
                    detail=(msg or f"Auth service error ({response.status_code})").strip()
                )
            return response.json()
    except HTTPException:
        raise
    except httpx.RequestError as e:
        logger.warning(f"Auth callback: cannot reach auth-service at {full_url}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Auth service unavailable. Ensure Docker is running and run: docker compose up -d"
        )
    except Exception as e:
        msg = (str(e) or repr(e) or type(e).__name__ or "unknown").strip()
        logger.exception(f"Auth callback: unexpected error: {msg}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {msg}")

@router.get("/me")
async def get_current_user(token_data: dict = Depends(verify_token)):
    """
    Get current authenticated user
    """
    # Return user data from token payload
    return {
        "email": token_data.get("email"),
        "name": token_data.get("name", ""),
    }

@router.post("/logout")
async def logout(token_data: dict = Depends(verify_token)):
    """
    Logout - clears all cached email data for the user
    """
    user_id = token_data.get("sub")
    
    try:
        # Notify auth service to clear session
        async with httpx.AsyncClient() as client:
            await client.post(f"{AUTH_SERVICE_URL}/auth/logout", json={"user_id": user_id})
        
        # Notify gmail service to clear cached data
        GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector:8002")
        async with httpx.AsyncClient() as client:
            await client.post(f"{GMAIL_SERVICE_URL}/clear", json={"user_id": user_id})
        
        return {"message": "Logged out successfully"}
    except httpx.HTTPError as e:
        # Log error but still return success (frontend will clear state anyway)
        print(f"Logout error: {e}")
        return {"message": "Logged out successfully"}
