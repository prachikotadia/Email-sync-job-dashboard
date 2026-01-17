from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.google_oauth import GoogleOAuth
from app.jwt import create_access_token, verify_token
from pydantic import BaseModel
import os

app = FastAPI(title="Auth Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OAuth
oauth = GoogleOAuth(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8001/auth/callback")
)

class CallbackRequest(BaseModel):
    code: str

class LogoutRequest(BaseModel):
    user_id: str

@app.get("/auth/login")
async def login():
    """
    Initiate Google OAuth login
    Returns OAuth URL
    """
    try:
        auth_url = oauth.get_authorization_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate login: {str(e)}")

@app.post("/auth/callback")
async def callback(request: CallbackRequest):
    """
    Handle OAuth callback and return JWT token
    """
    try:
        # Exchange code for tokens
        tokens = await oauth.exchange_code(request.code)
        
        # Get user info
        user_info = await oauth.get_user_info(tokens["access_token"])
        
        # Create JWT token with user_id (email as sub for now, can be changed to numeric ID)
        token_data = {
            "sub": user_info["email"],  # Using email as user_id for now
            "email": user_info["email"],
            "name": user_info.get("name", ""),
        }
        jwt_token = create_access_token(token_data)
        
        return {
            "token": jwt_token,
            "user": {
                "email": user_info["email"],
                "name": user_info.get("name", ""),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to handle callback: {str(e)}")

@app.get("/auth/me")
async def get_me():
    """
    Get current user (requires JWT in header)
    """
    # This would be called via API gateway with verified token
    # For now, return a placeholder
    return {"email": "user@example.com", "name": "User"}

@app.post("/auth/logout")
async def logout(request: LogoutRequest):
    """
    Logout - clear session
    Note: Actual data clearing happens in gmail-connector
    """
    # Session clearing logic if needed
    return {"message": "Logged out"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}
