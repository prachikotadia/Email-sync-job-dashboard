"""
Gmail connection management endpoints (stores OAuth tokens).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.repo import GmailConnectionRepository, UserRepository
from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GmailTokenStoreRequest(BaseModel):
    """Request to store Gmail OAuth tokens."""
    tokens_json: str  # JSON string of OAuth tokens
    gmail_email: str


class GmailConnectionResponse(BaseModel):
    """Response with Gmail connection status."""
    is_connected: bool
    gmail_email: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None


@router.post("/gmail/store-tokens", status_code=status.HTTP_201_CREATED)
def store_gmail_tokens(
    request: GmailTokenStoreRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Store Gmail OAuth tokens for authenticated user (called by gmail-connector-service)."""
    repo = GmailConnectionRepository(db)
    
    try:
        # Validate JSON
        json.loads(request.tokens_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tokens JSON format"
        )
    
    connection = repo.create_or_update_connection(
        user_id=current_user.id,
        tokens_json=request.tokens_json,
        gmail_email=request.gmail_email
    )
    
    logger.info(f"Gmail tokens stored for user {current_user.id}")
    return {"message": "Tokens stored successfully", "connection_id": connection.id}


@router.get("/gmail/status", response_model=GmailConnectionResponse)
def get_gmail_connection_status(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Gmail connection status for authenticated user."""
    repo = GmailConnectionRepository(db)
    connection = repo.get_by_user_id(current_user.id)
    
    if connection:
        return GmailConnectionResponse(
            is_connected=True,
            gmail_email=connection.gmail_email,
            connected_at=connection.connected_at,
            last_synced_at=connection.last_synced_at
        )
    else:
        return GmailConnectionResponse(is_connected=False)


@router.post("/gmail/disconnect", status_code=status.HTTP_200_OK)
def disconnect_gmail(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Gmail account for authenticated user."""
    repo = GmailConnectionRepository(db)
    success = repo.revoke_connection(current_user.id)
    
    if success:
        logger.info(f"Gmail disconnected for user {current_user.id}")
        return {"message": "Gmail account disconnected successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Gmail connection found"
        )


@router.get("/gmail/tokens")
def get_gmail_tokens(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Gmail OAuth tokens for authenticated user (called by gmail-connector-service)."""
    repo = GmailConnectionRepository(db)
    tokens = repo.get_connection_tokens(current_user.id)
    
    if tokens:
        return {"tokens": tokens}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Gmail connection found"
        )