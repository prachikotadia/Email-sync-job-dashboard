from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.repo import UserRepository, RefreshTokenRepository
from app.schemas.auth import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse, RefreshRequest, RefreshResponse,
    LogoutRequest, LogoutResponse
)
from app.schemas.user import UserResponse
from app.security.passwords import hash_password, verify_password
from app.security.jwt import (
    create_access_token, create_refresh_token, verify_token, decode_token_unverified
)
from app.security.rbac import Role
from datetime import datetime, timedelta
from app.config import get_settings
from typing import Optional
from app.api.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    user_repo = UserRepository(db)
    
    # Check if user already exists
    existing_user = user_repo.get_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Determine role: first user gets 'editor', others default to 'viewer' unless specified
    user_count = user_repo.get_user_count()
    if request.role:
        # Validate role
        if request.role not in ["viewer", "editor"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be either 'viewer' or 'editor'"
            )
        role: Role = request.role
    else:
        # Auto-assign: first user = editor, others = viewer
        role: Role = "editor" if user_count == 0 else "viewer"
    
    # Hash password
    password_hash = hash_password(request.password)
    
    # Create user
    user = user_repo.create_user(
        email=request.email,
        password_hash=password_hash,
        role=role,
        full_name=request.full_name
    )
    
    logger.info(f"User registered: {user.email} with role: {user.role}")
    
    return RegisterResponse(
        message="User registered successfully",
        user=UserResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
    )


@router.post("/auth/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint. Authenticates existing users only."""
    user_repo = UserRepository(db)
    refresh_token_repo = RefreshTokenRepository(db)
    
    # Get user by email
    user = user_repo.get_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role
    })
    
    refresh_token_value = create_refresh_token(str(user.id))
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Store refresh token (user.id is already a string from the model)
    refresh_token_repo.create_token(
        user_id=str(user.id),
        token=refresh_token_value,
        expires_at=expires_at
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        token_type="bearer",
        user=UserResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
    )


@router.post("/auth/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    refresh_token_repo = RefreshTokenRepository(db)
    user_repo = UserRepository(db)
    
    # Verify refresh token is valid in DB
    stored_token = refresh_token_repo.get_valid_token(request.refresh_token)
    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Also verify JWT structure (optional but good practice)
    payload = decode_token_unverified(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token format"
        )
    
    # Get user
    user = user_repo.get_by_id(stored_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new access token
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role
    })
    
    return RefreshResponse(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/auth/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
def logout(
    request: LogoutRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout endpoint. Revokes refresh token."""
    refresh_token_repo = RefreshTokenRepository(db)
    
    success = refresh_token_repo.revoke_token(request.refresh_token)
    
    if not success:
        logger.warning(f"Attempted to revoke non-existent token")
        # Still return success for idempotency
    
    return LogoutResponse(message="Logged out successfully")


@router.get("/auth/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user
