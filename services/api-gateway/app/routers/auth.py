from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
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
async def handle_callback(request: dict):
    """
    Handle OAuth callback and return JWT token
    """
    code = request.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    full_url = f"{AUTH_SERVICE_URL}/auth/callback"
    print(f"API Gateway: Calling auth-service at {full_url}")
    print(f"API Gateway: Code length: {len(code)}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                full_url,
                json={"code": code}
            )
            print(f"API Gateway: Auth service response status: {response.status_code}")
            if response.status_code != 200:
                error_text = response.text
                print(f"API Gateway: Auth service error response: {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Auth service error ({response.status_code}): {error_text[:200]}"
                )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_text = e.response.text if e.response else str(e)
        print(f"API Gateway: HTTP error calling {full_url}: {e.response.status_code} - {error_text}")
        raise HTTPException(
            status_code=e.response.status_code if e.response else 503,
            detail=f"Auth service error at {full_url}: {error_text[:200]}"
        )
    except httpx.RequestError as e:
        print(f"API Gateway: Request error calling {full_url}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Auth service unavailable at {full_url}: {str(e)}")
    except Exception as e:
        print(f"API Gateway: Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

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
