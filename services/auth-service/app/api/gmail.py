"""
Gmail connection management endpoints (stores OAuth tokens).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.repo import GmailConnectionRepository, UserRepository
from app.db.models import GmailConnection
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
    try:
        repo = GmailConnectionRepository(db)
        
        # Validate JSON and check size
        try:
            tokens_dict = json.loads(request.tokens_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid tokens JSON format for user {current_user.id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tokens JSON format: {str(e)}"
            )
        
        # Check if tokens JSON is too long (max 2000 chars)
        if len(request.tokens_json) > 2000:
            logger.error(f"Tokens JSON too long for user {current_user.id}: {len(request.tokens_json)} chars (max 2000)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tokens JSON too long: {len(request.tokens_json)} chars (max 2000). Consider compressing or storing only essential fields."
            )
        
        logger.info(f"Storing Gmail tokens for user {current_user.id}, email: {request.gmail_email}, tokens size: {len(request.tokens_json)} chars")
        
        try:
            connection = repo.create_or_update_connection(
                user_id=current_user.id,
                tokens_json=request.tokens_json,
                gmail_email=request.gmail_email
            )
            
            logger.info(f"Gmail tokens stored successfully for user {current_user.id}, connection_id: {connection.id}")
            return {"message": "Tokens stored successfully", "connection_id": connection.id}
            
        except Exception as db_error:
            logger.error(f"Database error storing Gmail tokens for user {current_user.id}: {db_error}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store Gmail tokens in database: {str(db_error)}"
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error storing Gmail tokens for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store Gmail tokens: {str(e)}"
        )


@router.get("/gmail/status", response_model=GmailConnectionResponse)
def get_gmail_connection_status(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Gmail connection status for authenticated user."""
    repo = GmailConnectionRepository(db)
    # Ensure user_id is string for consistent lookup
    user_id = str(current_user.id) if current_user.id else None
    
    if not user_id:
        logger.warning(f"User ID is None for user {current_user.email}")
        return GmailConnectionResponse(is_connected=False)
    
    # Try multiple lookup strategies to handle any ID format issues
    connection = repo.get_by_user_id(user_id)
    
    # If not found, try fallback strategies
    if not connection:
        logger.warning(f"Gmail connection not found for user_id: '{user_id}'. Trying fallback search...")
        # Get user from database to ensure we have the exact ID format
        user_repo = UserRepository(db)
        db_user = user_repo.get_by_id(user_id)
        if db_user:
            logger.info(f"User found in DB: id='{db_user.id}', email='{db_user.email}'")
            # Try with exact database user.id
            if str(db_user.id) != user_id:
                logger.info(f"Trying with database user.id: {db_user.id} (was: {user_id})")
                connection = repo.get_by_user_id(str(db_user.id))
        
        # If still not found, check all active connections
        if not connection:
            all_connections = db.query(GmailConnection).filter(GmailConnection.is_active == True).all()
            logger.warning(f"Total active connections in DB: {len(all_connections)}")
            for conn in all_connections:
                logger.info(f"  Connection: user_id='{conn.user_id}', email={conn.gmail_email}, match={str(conn.user_id).strip() == str(user_id).strip()}")
                # Try case-insensitive match
                if str(conn.user_id).strip().lower() == str(user_id).strip().lower():
                    logger.info(f"  MATCH FOUND (case-insensitive): {conn.user_id}")
                    connection = conn
                    break
    
    if connection:
        logger.info(f"Gmail connection found for user {user_id}: {connection.gmail_email}")
        return GmailConnectionResponse(
            is_connected=True,
            gmail_email=connection.gmail_email,
            connected_at=connection.connected_at,
            last_synced_at=connection.last_synced_at
        )
    else:
        logger.info(f"No Gmail connection found for user {user_id}")
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
        # Log scopes for debugging
        scopes = tokens.get("scopes", [])
        has_readonly = 'https://www.googleapis.com/auth/gmail.readonly' in scopes
        has_metadata = 'https://www.googleapis.com/auth/gmail.metadata' in scopes
        
        logger.info(f"Gmail tokens retrieved for user {current_user.id}")
        logger.info(f"Scopes: {scopes}")
        logger.info(f"Has readonly: {has_readonly}, Has metadata: {has_metadata}")
        
        # WARNING: If user has metadata scope, they need to reconnect
        # Metadata scope does NOT support search queries (q parameter) and will fail
        if has_metadata:
            logger.warning(
                f"WARNING: User {current_user.id} has metadata scope in stored tokens. "
                "Metadata scope does NOT support search queries. "
                "They need to disconnect and reconnect to get ONLY readonly scope."
            )
        
        # Filter out metadata scope before returning (only return readonly)
        if has_metadata:
            filtered_scopes = [
                scope for scope in scopes 
                if 'gmail.metadata' not in scope
            ]
            tokens["scopes"] = filtered_scopes
            logger.info(f"Filtered scopes: {scopes} -> {filtered_scopes} (removed metadata)")
        
        return {"tokens": tokens}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Gmail connection found"
        )


@router.post("/gmail/update-sync-time")
def update_sync_time(
    request: dict,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update last_synced_at timestamp for Gmail connection."""
    from datetime import datetime
    repo = GmailConnectionRepository(db)
    connection = repo.get_by_user_id(current_user.id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Gmail connection found"
        )
    
    last_synced_at = request.get("last_synced_at")
    if last_synced_at:
        try:
            connection.last_synced_at = datetime.fromisoformat(last_synced_at.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Error parsing sync time: {e}")
            connection.last_synced_at = datetime.utcnow()
    else:
        connection.last_synced_at = datetime.utcnow()
    
    db.commit()
    db.refresh(connection)
    
    return {"message": "Sync time updated", "last_synced_at": connection.last_synced_at.isoformat()}