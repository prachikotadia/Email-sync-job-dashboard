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
    expires_at = datetime.utcnow() + timedelta(minutes=10)  # State expires in 10 min
    _state_store[state] = {
        "user_id": user_id,
        "access_token": access_token,
        "expires_at": expires_at
    }
    logger.info(f"Generated state token for user {user_id}, expires at {expires_at}, store size: {len(_state_store)}")
    return state


def verify_state_token(state: str) -> Optional[dict]:
    """Verify and retrieve state data (user_id and access_token)."""
    from datetime import datetime
    logger.info(f"Verifying state token, store size: {len(_state_store)}, state: {state[:20]}...")
    
    # Check if state exists in store (without popping first)
    if state not in _state_store:
        logger.warning(f"State token not found in store. Available states: {list(_state_store.keys())[:5]}")
        return None
    
    state_data = _state_store.pop(state, None)
    
    if not state_data:
        logger.warning(f"State token was removed or invalid")
        return None
    
    # Check expiration
    if datetime.utcnow() > state_data["expires_at"]:
        logger.warning(f"State token expired. Expires at: {state_data['expires_at']}, now: {datetime.utcnow()}")
        return None
    
    logger.info(f"State token verified successfully for user {state_data.get('user_id')}")
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
    # Log detailed information for debugging
    logger.info(f"=== AUTHORIZATION URL GENERATION DEBUG ===")
    logger.info(f"Redirect URI in flow: '{flow.redirect_uri}'")
    logger.info(f"Redirect URI length: {len(flow.redirect_uri) if flow.redirect_uri else 0}")
    logger.info(f"Redirect URI bytes: {flow.redirect_uri.encode('utf-8') if flow.redirect_uri else None}")
    logger.info(f"Client ID: {settings.GOOGLE_CLIENT_ID[:20]}...")
    logger.info(f"State token: {state[:30]}...")
    logger.info(f"==========================================")
    
    authorization_url, _ = flow.authorization_url(
        access_type='offline',  # Required to get refresh_token (allows offline access)
        include_granted_scopes='false',  # CRITICAL: Set to 'false' to prevent Google from adding previously granted scopes (like metadata)
                                         # This ensures ONLY the scopes we request (readonly) are granted
        state=state,
        prompt='consent'  # CRITICAL: Forces consent screen again so scope upgrades apply.
                         # Without this, Google may reuse old grant and keep old scope (e.g., metadata instead of readonly).
                         # This ensures users see consent screen and get new permissions with refresh_token.
    )
    
    # Extract redirect_uri from the generated URL for verification
    import urllib.parse
    parsed_url = urllib.parse.urlparse(authorization_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    redirect_uri_in_url = query_params.get('redirect_uri', [None])[0]
    
    logger.info(f"=== AUTHORIZATION URL DETAILS ===")
    logger.info(f"Generated authorization URL (first 200 chars): {authorization_url[:200]}...")
    logger.info(f"Redirect URI in authorization URL: '{redirect_uri_in_url}'")
    logger.info(f"Flow redirect URI matches URL: {flow.redirect_uri == redirect_uri_in_url}")
    logger.info(f"=================================")
    
    return authorization_url


def exchange_code_for_tokens(flow: Flow, code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for OAuth tokens.
    
    The redirect_uri must match exactly what was used in the authorization URL.
    Note: The flow object already has redirect_uri set, so we don't pass it to fetch_token.
    """
    try:
        # Log detailed information for debugging
        logger.info(f"=== TOKEN EXCHANGE DEBUG INFO ===")
        logger.info(f"Redirect URI parameter: '{redirect_uri}'")
        logger.info(f"Redirect URI length: {len(redirect_uri)}")
        logger.info(f"Redirect URI bytes: {redirect_uri.encode('utf-8')}")
        logger.info(f"Flow redirect_uri: '{flow.redirect_uri}'")
        logger.info(f"Flow redirect_uri length: {len(flow.redirect_uri) if flow.redirect_uri else 0}")
        logger.info(f"Redirect URIs match: {redirect_uri == flow.redirect_uri}")
        logger.info(f"Client ID: {settings.GOOGLE_CLIENT_ID[:20]}...")
        logger.info(f"Code length: {len(code) if code else 0}")
        
        # Verify redirect_uri matches what's in the flow
        if redirect_uri != flow.redirect_uri:
            logger.error(f"REDIRECT URI MISMATCH! Parameter: '{redirect_uri}' != Flow: '{flow.redirect_uri}'")
            raise ValueError(
                f"Redirect URI mismatch: parameter '{redirect_uri}' does not match flow redirect_uri '{flow.redirect_uri}'. "
                f"They must be identical."
            )
        
        logger.info(f"=================================")
        
        # DON'T pass redirect_uri to fetch_token - it's already set in the flow object
        # Passing it again causes "got multiple values for keyword argument 'redirect_uri'" error
        
        # CRITICAL: Suppress scope change warnings from oauthlib
        # These warnings are raised when Google returns additional scopes (like metadata from previous grants)
        # The warning prevents credentials from being set, but the token exchange actually succeeded
        # We need to suppress the warning BEFORE calling fetch_token
        import oauthlib.oauth2.rfc6749.parameters as oauthlib_params
        
        # Temporarily monkey-patch the warning to log it instead of raising it
        original_validate = oauthlib_params.validate_token_parameters
        
        def validate_with_warning_suppression(params):
            """Suppress scope change warnings - they're informational, not errors."""
            try:
                return original_validate(params)
            except Warning as w:
                warning_msg = str(w)
                if 'scope' in warning_msg.lower() and 'changed' in warning_msg.lower():
                    logger.warning(f"⚠️ Scope change detected (non-fatal): {warning_msg}")
                    logger.warning("Google returned additional scopes (likely from previous grants)")
                    logger.warning("This is expected - we'll filter out unwanted scopes later")
                    # Return without raising - allow token exchange to complete
                    return
                else:
                    # Re-raise non-scope warnings
                    raise
        
        # Apply monkey-patch
        oauthlib_params.validate_token_parameters = validate_with_warning_suppression
        
        try:
            flow.fetch_token(code=code)
        finally:
            # Restore original function
            oauthlib_params.validate_token_parameters = original_validate
        
        credentials = flow.credentials
        
        if not credentials or not credentials.token:
            raise ValueError("Failed to obtain OAuth tokens from Google")
        
        logger.info("Token exchange successful!")
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Extract detailed error information
        detailed_error = {
            "error_type": error_type,
            "error_message": error_msg,
            "redirect_uri_used": redirect_uri,
            "flow_redirect_uri": flow.redirect_uri if hasattr(flow, 'redirect_uri') else None,
            "client_id": settings.GOOGLE_CLIENT_ID[:20] + "..." if settings.GOOGLE_CLIENT_ID else "NOT_SET",
        }
        
        # Check for specific OAuth errors
        error_lower = error_msg.lower()
        if "redirect_uri_mismatch" in error_lower or "redirecturimismatcherror" in error_lower:
            detailed_error["diagnosis"] = (
                f"REDIRECT URI MISMATCH DETECTED!\n"
                f"Redirect URI used in token exchange: '{redirect_uri}'\n"
                f"Flow redirect URI: '{flow.redirect_uri}'\n"
                f"These must match EXACTLY (character-for-character).\n"
                f"Also verify this URI is registered in Google Cloud Console:\n"
                f"1. Go to Google Cloud Console → APIs & Services → Credentials\n"
                f"2. Click your OAuth 2.0 Client ID\n"
                f"3. Check 'Authorized redirect URIs'\n"
                f"4. Make sure '{redirect_uri}' is listed EXACTLY (no trailing slash, correct port, etc.)"
            )
        elif "invalid_grant" in error_lower or "invalidgranterror" in error_lower:
            detailed_error["diagnosis"] = (
                f"INVALID GRANT ERROR!\n"
                f"This usually means:\n"
                f"1. The authorization code has expired (codes expire quickly)\n"
                f"2. The code was already used\n"
                f"3. The redirect_uri doesn't match what was used in the authorization URL\n"
                f"Redirect URI used: '{redirect_uri}'"
            )
        elif "invalid_client" in error_lower:
            detailed_error["diagnosis"] = (
                f"INVALID CLIENT ERROR!\n"
                f"Client ID or Client Secret is incorrect.\n"
                f"Client ID: {settings.GOOGLE_CLIENT_ID[:20]}...\n"
                f"Verify GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env file"
            )
        else:
            detailed_error["diagnosis"] = f"Unknown OAuth error. Check Google Cloud Console configuration."
        
        logger.error(f"=== TOKEN EXCHANGE ERROR ===")
        logger.error(f"Error Type: {error_type}")
        logger.error(f"Error Message: {error_msg}")
        logger.error(f"Redirect URI Used: '{redirect_uri}'")
        logger.error(f"Flow Redirect URI: '{flow.redirect_uri}'")
        logger.error(f"Diagnosis: {detailed_error.get('diagnosis', 'N/A')}")
        logger.error(f"Full error details: {json.dumps(detailed_error, indent=2)}")
        logger.error(f"============================", exc_info=True)
        
        # Re-raise with detailed context
        raise ValueError(
            f"OAuth Token Exchange Failed\n\n"
            f"Error: {error_type}: {error_msg}\n\n"
            f"Details:\n"
            f"- Redirect URI used: '{redirect_uri}'\n"
            f"- Flow redirect URI: '{flow.redirect_uri}'\n"
            f"- Client ID: {settings.GOOGLE_CLIENT_ID[:30]}...\n\n"
            f"Diagnosis:\n{detailed_error.get('diagnosis', 'Unknown error')}"
        )


def get_gmail_profile(credentials_dict: dict) -> dict:
    """Get Gmail profile information (email, name) using OAuth credentials."""
    try:
        # CRITICAL: Filter out metadata scope when creating Credentials
        # Only use readonly scope for API calls
        original_scopes = credentials_dict.get("scopes", [])
        filtered_scopes = [
            scope for scope in original_scopes
            if 'gmail.metadata' not in scope
        ]
        
        credentials = Credentials(
            token=credentials_dict.get("token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
            scopes=filtered_scopes  # Use filtered scopes (readonly only, no metadata)
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