from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from app.config import get_settings
from jose import JWTError, jwt
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
security = HTTPBearer(auto_error=False)


class UserContext:
    """User context extracted from JWT."""
    def __init__(self, user_id: str, email: str, role: str):
        self.user_id = user_id
        self.email = email
        self.role = role


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserContext]:
    """
    Dependency to extract user context from JWT.
    Returns None if no token provided (for optional auth routes).
    Raises HTTPException if token is invalid.
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    email = payload.get("email", "")
    role = payload.get("role", "viewer")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return UserContext(user_id=user_id, email=email, role=role)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserContext:
    """
    Dependency that requires authentication (raises 401 if no token).
    Returns UserContext with user information.
    Note: Request state is set in route handlers after getting UserContext.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    email = payload.get("email", "")
    role = payload.get("role", "viewer")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return UserContext(user_id=user_id, email=email, role=role)


def check_rbac(user: Optional[UserContext], method: str) -> bool:
    """
    Check if user has permission for the HTTP method.
    - viewer: GET only
    - editor: all methods
    """
    if not user:
        return False
    
    if user.role == "editor":
        return True
    
    if user.role == "viewer":
        return method.upper() == "GET"
    
    return False
