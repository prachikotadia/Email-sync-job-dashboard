"""
Google OAuth login endpoint - unified flow for authentication and Gmail connection.
"""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.repo import UserRepository, RefreshTokenRepository, GmailConnectionRepository
from app.security.jwt import create_access_token, create_refresh_token
from app.security.rbac import Role
from app.schemas.user import UserResponse
from app.config import get_settings
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import secrets
import json
import httpx
import logging
import urllib.parse

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Store state tokens temporarily (in production, use Redis or similar)
# Format: {state: {"expires_at": datetime}}
_state_store = {}


def get_google_oauth_flow(redirect_uri: str) -> Flow:
    """Create OAuth 2.0 flow for Google login (with user info + Gmail scopes)."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ValueError("Google OAuth credentials not configured")
    
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    
    # Request both user info and Gmail scopes
    # CRITICAL: Use gmail.readonly (NOT gmail.metadata) to support Gmail search queries (q parameter)
    # - ✅ gmail.readonly: Allows messages.list with q parameter for searching
    # - ❌ gmail.metadata: Does NOT support q parameter and will return 403 error:
    #   "Metadata scope does not support 'q' parameter"
    #
    # IMPORTANT WARNING: If SCOPES are modified, existing OAuth tokens must be deleted to trigger
    # re-authentication. Users should disconnect and reconnect Gmail in Settings UI.
    SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/gmail.readonly"  # Required for Gmail search queries - NOT metadata!
    ]
    scopes = SCOPES
    
    flow = Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=redirect_uri
    )
    
    return flow


def generate_state_token(redirect_uri: str) -> str:
    """Generate a secure state token for OAuth flow, storing the redirect_uri."""
    from datetime import datetime, timedelta
    state = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    _state_store[state] = {
        "expires_at": expires_at,
        "redirect_uri": redirect_uri  # Store redirect_uri to ensure it matches in callback
    }
    logger.info(f"Generated state token with redirect_uri: {redirect_uri}, expires at: {expires_at}")
    return state


def verify_state_token(state: str) -> dict:
    """Verify state token is valid and not expired. Returns state data including redirect_uri."""
    if not state:
        return None
    
    state_data = _state_store.pop(state, None)
    if not state_data:
        logger.warning("State token not found in store")
        return None
    
    if datetime.utcnow() > state_data["expires_at"]:
        logger.warning(f"State token expired. Expires at: {state_data['expires_at']}, now: {datetime.utcnow()}")
        return None
    
    logger.info(f"State token verified successfully, redirect_uri: {state_data.get('redirect_uri')}")
    return state_data


def get_user_info_from_google(credentials: Credentials) -> dict:
    """Get user info from Google using OAuth credentials."""
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "verified_email": user_info.get("verified_email", False)
        }
    except Exception as e:
        logger.error(f"Error getting user info from Google: {e}")
        raise ValueError(f"Failed to get user info from Google: {str(e)}")


def get_gmail_email_from_google(credentials: Credentials) -> str:
    """Get Gmail email address from Google using OAuth credentials."""
    try:
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress')
    except Exception as e:
        logger.error(f"Error getting Gmail profile: {e}")
        raise ValueError(f"Failed to get Gmail profile: {str(e)}")


@router.get("/auth/google/login")
async def google_login(redirect_uri: str = Query(None)):
    """
    Initiate Google OAuth login flow.
    Requests both user info and Gmail access in one flow.
    """
    try:
        # Use configured redirect URI if not provided
        if not redirect_uri:
            redirect_uri = settings.GOOGLE_REDIRECT_URI
        
        logger.info(f"=== GOOGLE LOGIN OAUTH DEBUG ===")
        logger.info(f"Redirect URI being used: '{redirect_uri}'")
        logger.info(f"Redirect URI length: {len(redirect_uri)}")
        logger.info(f"Client ID: {settings.GOOGLE_CLIENT_ID[:20] if settings.GOOGLE_CLIENT_ID else 'NOT_SET'}...")
        logger.info(f"=================================")
        
        # Generate state token and store redirect_uri with it
        state = generate_state_token(redirect_uri)
        
        # Create OAuth flow with the redirect_uri
        flow = get_google_oauth_flow(redirect_uri)
        
        # Generate authorization URL
        authorization_url, _ = flow.authorization_url(
            access_type='offline',  # Required to get refresh_token (allows offline access)
            include_granted_scopes='false',  # CRITICAL: Set to 'false' to prevent Google from adding previously granted scopes (like metadata)
                                             # This ensures ONLY the scopes we request (readonly) are granted
            state=state,
            prompt='consent'  # CRITICAL: Forces consent screen again so scope upgrades apply.
                             # Without this, Google may reuse old grant and keep old scope (e.g., metadata instead of readonly).
                             # This ensures users see consent screen and get new permissions with refresh_token.
        )
        
        # Extract redirect_uri from authorization URL to verify it matches
        import urllib.parse
        parsed_url = urllib.parse.urlparse(authorization_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        redirect_uri_in_auth_url = query_params.get('redirect_uri', [None])[0]
        
        logger.info(f"=== AUTHORIZATION URL GENERATION ===")
        logger.info(f"Flow redirect_uri: '{flow.redirect_uri}'")
        logger.info(f"Redirect URI in auth URL: '{redirect_uri_in_auth_url}'")
        logger.info(f"Match: {flow.redirect_uri == redirect_uri_in_auth_url}")
        logger.info(f"Authorization URL (first 200 chars): {authorization_url[:200]}...")
        logger.info(f"====================================")
        
        return RedirectResponse(url=authorization_url, status_code=302)
        
    except Exception as e:
        logger.error(f"Error initiating Google OAuth login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate Google login: {str(e)}"
        )


@router.get("/auth/google/callback")
async def google_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    redirect_uri: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback.
    Creates user account if new, logs in if existing, and connects Gmail.
    """
    frontend_url = settings.FRONTEND_URL or "http://localhost:5173"
    
    try:
        # Check for OAuth errors
        # NOTE: Google may return "Scope has changed" as a warning, not an error
        # This happens when scopes change between authorizations (e.g., from metadata to readonly)
        # We should ignore this warning and continue with the flow
        if error:
            error_lower = error.lower()
            # Ignore scope change warnings - these are informational, not errors
            if 'scope' in error_lower and 'changed' in error_lower:
                logger.info(f"Ignoring scope change warning from Google (this is normal): {error}")
                # Continue with the flow - don't treat as error
                # But we still need code and state to proceed
            else:
                logger.warning(f"OAuth error from Google: {error}")
                return RedirectResponse(
                    url=f"{frontend_url}/?google_error={error}",
                    status_code=302
                )
        
        # Validate required parameters
        # Even if there's a scope change warning, we still need code and state
        if not code or not state:
            logger.error(f"Missing required parameters: code={code is not None}, state={state is not None}")
            return RedirectResponse(
                url=f"{frontend_url}/?google_error=invalid_callback",
                status_code=302
            )
        
        # Verify state token and get stored redirect_uri
        state_data = verify_state_token(state)
        if not state_data:
            logger.error("Invalid or expired state token")
            return RedirectResponse(
                url=f"{frontend_url}/?google_error=invalid_state",
                status_code=302
            )
        
        # Use redirect_uri from state token (must match what was used in authorization URL)
        # This ensures the redirect_uri used in token exchange matches exactly
        stored_redirect_uri = state_data.get("redirect_uri")
        if stored_redirect_uri:
            redirect_uri = stored_redirect_uri
            logger.info(f"Using redirect_uri from state token: {redirect_uri}")
        elif redirect_uri:
            # If provided as query param, use it (but log warning)
            logger.warning(f"Using redirect_uri from query param (not from state): {redirect_uri}")
        else:
            # Fallback to configured redirect URI
            redirect_uri = settings.GOOGLE_REDIRECT_URI
            logger.info(f"Using configured redirect_uri: {redirect_uri}")
        
        logger.info(f"=== CALLBACK RECEIVED ===")
        logger.info(f"Authorization code received: {code[:20]}..." if code else "No code")
        logger.info(f"State token: {state[:30]}..." if state else "No state")
        logger.info(f"Redirect URI from query param: {redirect_uri}")
        logger.info(f"Redirect URI from state token: {stored_redirect_uri}")
        logger.info(f"Redirect URI being used: {redirect_uri}")
        logger.info(f"==========================")
        
        # Create OAuth flow with the same redirect_uri used in authorization URL
        flow = get_google_oauth_flow(redirect_uri)
        
        # Verify flow is configured correctly
        logger.info(f"=== FLOW CONFIGURATION ===")
        logger.info(f"Flow redirect_uri: '{flow.redirect_uri}'")
        logger.info(f"Flow redirect_uri length: {len(flow.redirect_uri)}")
        logger.info(f"Flow redirect_uri bytes: {flow.redirect_uri.encode('utf-8')}")
        logger.info(f"Flow client_id: {flow.client_config.get('web', {}).get('client_id', 'NOT_SET')[:20]}...")
        logger.info(f"==========================")
        
        # Exchange authorization code for tokens
        # CRITICAL: fetch_token MUST succeed for credentials to be set
        # NOTE: oauthlib raises Warning for scope changes, but credentials may still be valid
        import warnings
        
        logger.info(f"=== TOKEN EXCHANGE ===")
        logger.info(f"About to call flow.fetch_token(code)...")
        logger.info(f"Using redirect_uri: '{flow.redirect_uri}'")
        logger.info(f"Redirect URI from state token: '{stored_redirect_uri}'")
        logger.info(f"Match: {flow.redirect_uri == stored_redirect_uri if stored_redirect_uri else 'N/A'}")
        logger.info(f"Authorization code: {code[:30]}..." if code else "No code")
        
        try:
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
            
            # Check if credentials were obtained
            if not flow.credentials or not flow.credentials.token:
                logger.error("❌ No credentials obtained after fetch_token")
                raise ValueError("Failed to obtain OAuth credentials - fetch_token completed but no token present")
            
            logger.info("✅ flow.fetch_token() completed successfully")
            logger.info(f"Access token obtained: {flow.credentials.token[:20]}...")
            logger.info(f"Refresh token present: {flow.credentials.refresh_token is not None}")
            logger.info(f"Granted scopes: {flow.credentials.scopes}")
            
        except Warning as warn:
            # This shouldn't happen now since we suppress them, but handle just in case
            warning_msg = str(warn)
            logger.warning(f"⚠️ Warning raised (but may be non-fatal): {warning_msg}")
            
            # Check if credentials were still set despite warning
            if flow.credentials and flow.credentials.token:
                logger.info("✅ Credentials obtained despite warning - continuing")
                logger.info(f"Granted scopes: {flow.credentials.scopes}")
            else:
                logger.error("❌ No credentials obtained after warning")
                raise ValueError(f"Token exchange failed: {warning_msg}")
                
        except Exception as token_error:
            error_str = str(token_error).lower()
            error_msg_full = str(token_error)
            error_type = type(token_error).__name__
            
            # Log the full error for debugging
            logger.error(f"❌ Token exchange failed with {error_type}: {error_msg_full}", exc_info=True)
            
            # Check if credentials were obtained despite the exception
            if flow.credentials and flow.credentials.token:
                logger.warning(f"⚠️ Credentials obtained despite {error_type} - continuing")
            else:
                logger.error(f"CRITICAL: fetch_token() failed - no credentials obtained")
                logger.error(f"Error type: {error_type}")
                logger.error(f"Error message: {error_msg_full}")
                
                # Check for specific error patterns
                if 'redirect_uri_mismatch' in error_str or 'redirect_uri' in error_str:
                    logger.error(f"❌ REDIRECT_URI_MISMATCH DETECTED!")
                    logger.error(f"The redirect_uri '{flow.redirect_uri}' doesn't match what Google expects")
                
                # Re-raise with clearer message
                raise ValueError(
                    f"Failed to exchange authorization code for tokens: {error_msg_full}. "
                    f"Redirect URI used: '{flow.redirect_uri}'. "
                    f"This usually means the redirect_uri doesn't match or the authorization code is invalid/expired."
                )
        
        # Get credentials from flow - should be set after successful fetch_token
        credentials = flow.credentials
        
        # Verify credentials were obtained successfully
        if not credentials:
            logger.error("No credentials object obtained from OAuth flow after fetch_token")
            raise ValueError("Failed to obtain OAuth credentials from Google - fetch_token may have failed silently")
        
        if not credentials.token:
            logger.error("Credentials object exists but has no access token")
            raise ValueError("Failed to obtain OAuth access token from Google - credentials.token is None")
        
        logger.info(f"OAuth credentials verified - access token obtained: {credentials.token[:20]}...")
        logger.info(f"Refresh token present: {credentials.refresh_token is not None}")
        logger.info(f"Original scopes from Google: {credentials.scopes}")
        
        # CRITICAL: Filter out metadata scope from credentials IMMEDIATELY after token exchange
        # Google may return metadata scope from previous grants, but we ONLY want readonly
        original_scopes = credentials.scopes if credentials.scopes else []
        filtered_scopes = [
            scope for scope in original_scopes 
            if 'gmail.metadata' not in scope  # Remove metadata scope completely
        ]
        
        # Verify we still have readonly scope after filtering
        has_readonly = 'https://www.googleapis.com/auth/gmail.readonly' in filtered_scopes
        if not has_readonly and 'gmail' in str(original_scopes).lower():
            logger.error(f"ERROR: No gmail.readonly scope after filtering. Original: {original_scopes}, Filtered: {filtered_scopes}")
            raise ValueError("Gmail connection does not have readonly scope. Please reconnect.")
        
        # If scopes changed, create new Credentials object with filtered scopes
        if original_scopes != filtered_scopes:
            logger.warning(f"⚠️ Filtering metadata scope from credentials")
            logger.info(f"Original scopes: {original_scopes}")
            logger.info(f"Filtered scopes: {filtered_scopes}")
            
            # Create new Credentials object with filtered scopes
            from google.oauth2.credentials import Credentials as GoogleCredentials
            credentials = GoogleCredentials(
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=filtered_scopes  # Use filtered scopes (readonly only)
            )
            logger.info(f"✅ Created new Credentials object with filtered scopes (metadata removed)")
        
        logger.info(f"Final credentials scopes: {credentials.scopes}")
        logger.info("Successfully exchanged authorization code for tokens")
        
        # CRITICAL: Runtime verification - verify actual access token has ONLY readonly scope (not metadata)
        # This ensures the token being used truly has gmail.readonly, not metadata
        logger.info(f"=== RUNTIME TOKEN VERIFICATION (tokeninfo) ===")
        try:
            import httpx
            
            # Verify access token scopes using Google's tokeninfo endpoint
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"access_token": credentials.token}
                )
                if response.status_code != 200:
                    raise ValueError(f"Token verification failed: {response.text}")
                tokeninfo = response.json()
                scope_str = tokeninfo.get("scope", "")
                tokeninfo_scopes = scope_str.split() if scope_str else []
                has_readonly = "https://www.googleapis.com/auth/gmail.readonly" in tokeninfo_scopes
                has_metadata = "https://www.googleapis.com/auth/gmail.metadata" in tokeninfo_scopes
                
                logger.info(f"Tokeninfo scopes: {tokeninfo_scopes}")
                logger.info(f"Has gmail.readonly: {has_readonly}")
                logger.info(f"Has gmail.metadata: {has_metadata}")
                
                # CRITICAL: REJECT tokens with metadata scope - we only want readonly scope
                # Do NOT store tokens with metadata scope (even if readonly is also present)
                if has_metadata:
                    error_msg = (
                        "Gmail token has metadata scope. "
                        "We only store tokens with readonly scope (not metadata). "
                        "Please try logging in again. "
                        f"Current token scopes: {tokeninfo_scopes}"
                    )
                    logger.error(f"❌ {error_msg}")
                    raise ValueError(error_msg)
                
                # If readonly is missing, fail
                if not has_readonly:
                    logger.error(
                        f"Gmail token missing gmail.readonly scope. "
                        f"Tokeninfo scopes: {tokeninfo_scopes}. "
                        f"Please disconnect and reconnect."
                    )
                    raise ValueError(
                        "Gmail token missing gmail.readonly scope. "
                        "Please disconnect and reconnect your Gmail account."
                    )
                
                logger.info("✅ Token verification passed: has_readonly=True, has_metadata=False")
            
        except ValueError as verify_error:
            # Re-raise ValueError (scope errors) - these should fail the login
            logger.error(f"Token verification failed: {verify_error}")
            raise
        except Exception as verify_error:
            logger.error(f"Token verification error: {verify_error}", exc_info=True)
            # Don't fail the login for network errors - just log the warning
            # The filtering above should have already handled scope issues
            logger.warning("⚠️ Token verification failed (non-critical), but continuing with filtered scopes")
        
        logger.info(f"========================================")
        
        # Get user info from Google
        user_info = get_user_info_from_google(credentials)
        google_email = user_info["email"]
        
        if not google_email:
            raise ValueError("Email not found in Google user info")
        
        logger.info(f"Retrieved user info from Google: {google_email}")
        
        # Get Gmail email (should be same as Google email, but verify)
        try:
            gmail_email = get_gmail_email_from_google(credentials)
            logger.info(f"Retrieved Gmail email: {gmail_email}")
        except Exception as e:
            logger.warning(f"Could not get Gmail email, using Google email: {e}")
            gmail_email = google_email
        
        # Check if user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(google_email)
        
        # Create user if doesn't exist
        if not user:
            # Determine role: first user gets 'editor', others default to 'viewer'
            user_count = user_repo.get_user_count()
            role: Role = "editor" if user_count == 0 else "viewer"
            
            # Create user with empty password (OAuth users don't need password)
            # Use a random hash that can't be guessed
            import hashlib
            password_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
            
            user = user_repo.create_user(
                email=google_email,
                password_hash=password_hash,
                role=role,
                full_name=user_info.get("name")
            )
            logger.info(f"Created new user account: {user.email} with role: {user.role}")
        else:
            logger.info(f"Existing user logged in: {user.email}")
        
        # Create auth tokens
        access_token = create_access_token({
            "sub": str(user.id),
            "email": user.email,
            "role": user.role
        })
        
        refresh_token_value = create_refresh_token(str(user.id))
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Store refresh token
        refresh_token_repo = RefreshTokenRepository(db)
        refresh_token_repo.create_token(
            user_id=str(user.id),
            token=refresh_token_value,
            expires_at=expires_at
        )
        
        # Store Gmail tokens
        # IMPORTANT: Filter out metadata scope - only store readonly scope for Gmail
        # Even if Google returns both scopes (due to previous grants), we only want readonly
        original_scopes = credentials.scopes if credentials.scopes else []
        filtered_scopes = [
            scope for scope in original_scopes 
            if 'gmail.metadata' not in scope  # Remove metadata scope, keep readonly
        ]
        
        if 'https://www.googleapis.com/auth/gmail.readonly' in original_scopes and 'https://www.googleapis.com/auth/gmail.metadata' in original_scopes:
            logger.warning(
                f"Google returned both readonly and metadata scopes. "
                f"Filtering to keep only readonly. Original: {original_scopes}, Filtered: {filtered_scopes}"
            )
        
        tokens_dict = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": filtered_scopes,  # Store only filtered scopes (readonly only)
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
        tokens_json = json.dumps(tokens_dict)
        
        gmail_repo = GmailConnectionRepository(db)
        connection = gmail_repo.create_or_update_connection(
            user_id=str(user.id),
            tokens_json=tokens_json,
            gmail_email=gmail_email
        )
        logger.info(f"Gmail tokens stored for user {user.id} (user_id: {str(user.id)}), gmail_email: {gmail_email}, connection_id: {connection.id}")
        
        # Verify the connection was stored
        verify_connection = gmail_repo.get_by_user_id(str(user.id))
        if verify_connection:
            logger.info(f"Verified: Gmail connection exists for user {user.id} with email {verify_connection.gmail_email}")
        else:
            logger.error(f"ERROR: Gmail connection was NOT found after storing for user {user.id}")
        
        # Redirect to frontend with tokens in URL (frontend will extract and store)
        # Encode tokens for URL - redirect to /login to ensure Login component handles callback
        params = urllib.parse.urlencode({
            "access_token": access_token,
            "refresh_token": refresh_token_value,
            "user_id": str(user.id),
            "email": user.email,
            "google_login": "true"
        })
        
        logger.info(f"Redirecting to frontend with Google login success: {frontend_url}/?{params[:100]}...")
        return RedirectResponse(
            url=f"{frontend_url}/?{params}",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}", exc_info=True)
        error_msg = urllib.parse.quote(str(e))
        return RedirectResponse(
            url=f"{frontend_url}/?google_error={error_msg}",
            status_code=302
        )
