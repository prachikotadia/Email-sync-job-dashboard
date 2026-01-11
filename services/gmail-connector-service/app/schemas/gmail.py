from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class GmailAuthUrlResponse(BaseModel):
    """Response with OAuth URL for Gmail authorization."""
    auth_url: str
    state: str  # State token for CSRF protection


class GmailCallbackRequest(BaseModel):
    """Request from OAuth callback."""
    code: str
    state: str


class GmailConnectionStatus(BaseModel):
    """Gmail connection status for a user."""
    is_connected: bool
    gmail_email: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None


class GmailDisconnectResponse(BaseModel):
    """Response after disconnecting Gmail."""
    message: str
    success: bool