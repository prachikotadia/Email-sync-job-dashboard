from fastapi import HTTPException, Depends, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    token: str = Query(None)
):
    """
    Verify JWT token from Authorization header or query parameter (for SSE)
    """
    # Try to get token from header first, then query param
    token_value = None
    if credentials:
        token_value = credentials.credentials
    elif token:
        token_value = token
    else:
        # Try Authorization header directly
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token_value = auth_header[7:]
    
    if not token_value:
        raise HTTPException(status_code=401, detail="Missing token")
    
    try:
        payload = jwt.decode(token_value, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
