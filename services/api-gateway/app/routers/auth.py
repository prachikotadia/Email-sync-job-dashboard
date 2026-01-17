from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")

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

@router.post("/callback")
async def handle_callback(request: dict):
    """
    Handle OAuth callback and return JWT token
    """
    code = request.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/callback",
                json={"code": code}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {str(e)}")

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
