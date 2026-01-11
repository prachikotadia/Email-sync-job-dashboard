"""
Gmail OAuth 2.0 helper functions.
"""
import secrets
import json
from typing import Optional, Dict
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Store state tokens temporarily (in production, use Redis or similar)
# Format: {state: {"user_id": str, "access_token": str, "expires_at": datetime}}
_state_store = {}


def generate_state_token(user_id: str, access_token: str) -> str:
    """Generate a secure state token for OAuth flow."""
    from datetime import datetime, timedelta
    state = secrets.token_urlsafe(32)
    _state_store[state] = {
        "user_id": user_id,
        "access_token": access_token,
        "expires_at": datetime.utcnow() + timedelta(minutes=10)  # State expires in 10 min
    }
    return state


def verify_state_token(state: str) -> Optional[dict]:
    """Verify and retrieve state data (user_id and access_token)."""
    from datetime import datetime
    state_data = _state_store.pop(state, None)
    
    if not state_data:
        return None
    
    # Check expiration
    if datetime.utcnow() > state_data["expires_at"]:
        return None
    
    return state_data


def get_oauth_flow(redirect_uri: str) -> Flow:
    """Create OAuth 2.0 flow for Gmail authorization."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ValueError("Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")
    
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.get_scopes(),
        redirect_uri=redirect_uri
    )
    
    return flow


def get_authorization_url(flow: Flow, state: str) -> str:
    """Generate authorization URL for Gmail OAuth."""
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=state,
        prompt='consent'  # Force consent to get refresh token
    )
    return authorization_url


def exchange_code_for_tokens(flow: Flow, code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for OAuth tokens."""
    flow.fetch_token(code=code, redirect_uri=redirect_uri)
    credentials = flow.credentials
    
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None
    }


def get_gmail_profile(credentials_dict: dict) -> dict:
    """Get Gmail profile information (email, name) using OAuth credentials."""
    try:
        credentials = Credentials(
            token=credentials_dict.get("token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
            scopes=credentials_dict.get("scopes")
        )
        
        # Refresh token if expired
        if credentials.expired:
            credentials.refresh(Request())
        
        # Get Gmail profile
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        
        return {
            "email": profile.get('emailAddress'),
            "messages_total": profile.get('messagesTotal', 0),
            "threads_total": profile.get('threadsTotal', 0)
        }
    except Exception as e:
        logger.error(f"Error getting Gmail profile: {e}")
        raise


def refresh_gmail_credentials(credentials_dict: dict) -> dict:
    """Refresh expired Gmail OAuth credentials."""
    try:
        credentials = Credentials(
            token=credentials_dict.get("token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
            scopes=credentials_dict.get("scopes")
        )
        
        if credentials.expired:
            credentials.refresh(Request())
            # Update credentials dict with new token
            credentials_dict["token"] = credentials.token
            if credentials.expiry:
                credentials_dict["expiry"] = credentials.expiry.isoformat()
        
        return credentials_dict
    except Exception as e:
        logger.error(f"Error refreshing Gmail credentials: {e}")
        raise