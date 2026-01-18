"""
JWT utilities for Resume Service
Validates JWT tokens from auth service
"""
from jose import jwt, JWTError
import os
import httpx
import logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")


def verify_token(token: str) -> dict:
    """
    Verify JWT token and return payload
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise ValueError("Invalid token")


def get_user_from_token(authorization: str) -> str:
    """
    Extract user email from Authorization header
    Returns user email (user_id)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    user_email = payload.get("sub")  # Email is stored in 'sub' claim
    
    if not user_email:
        raise ValueError("User email not found in token")
    
    return user_email
