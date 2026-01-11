"""
Gmail OAuth 2.0 endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query
from fastapi.responses import RedirectResponse
from app.schemas.gmail import (
    GmailAuthUrlResponse,
    GmailConnectionStatus,
    GmailDisconnectResponse
)
from app.security.oauth import (
    generate_state_token,
    verify_state_token,
    get_oauth_flow,
    get_authorization_url,
    exchange_code_for_tokens,
    get_gmail_profile
)
from app.config import get_settings
import httpx
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


async def get_user_from_jwt(authorization: str = Header(None)) -> dict:
    """Extract user info from JWT token (validated by API Gateway)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    token = authorization.replace("Bearer ", "")
    
    # Verify token with auth-service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error verifying token with auth-service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable"
        )


async def store_gmail_tokens(user_id: str, tokens: dict, gmail_email: str, access_token: str):
    """Store Gmail OAuth tokens via auth-service API."""
    try:
        tokens_json = json.dumps(tokens)
        logger.info(f"Storing Gmail tokens for user {user_id}, email: {gmail_email}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/gmail/store-tokens",
                json={
                    "tokens_json": tokens_json,
                    "gmail_email": gmail_email
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0
            )
            if response.status_code != 201:
                logger.error(f"Failed to store tokens for user {user_id}: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to store Gmail tokens"
                )
            result = response.json()
            logger.info(f"Gmail tokens stored successfully for user {user_id}, connection_id: {result.get('connection_id')}")
    except httpx.RequestError as e:
        logger.error(f"Network error calling auth-service to store tokens for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable"
        )


@router.get("/auth/gmail/url", response_model=GmailAuthUrlResponse)
async def get_gmail_auth_url(
    redirect_uri: str = Query(None),
    authorization: str = Header(None),
    user: dict = Depends(get_user_from_jwt)
):
    """
    Get Gmail OAuth authorization URL for the authenticated user.
    
    This is an internal endpoint called by the API Gateway.
    The redirect_uri MUST be passed from the gateway (single source of truth).
    """
    try:
        user_id = user.get("id")
        access_token = authorization.replace("Bearer ", "") if authorization else None
        
        if not user_id:
            logger.error("User ID not found in JWT token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in token. Authentication required."
            )
        
        if not access_token:
            logger.error("Access token not provided in authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token required. Please login first."
            )
        
        # Redirect URI MUST come from gateway (passed as query parameter)
        if not redirect_uri:
            logger.error("redirect_uri parameter is required (must be passed from API Gateway)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="redirect_uri parameter is required. This endpoint must be called by the API Gateway."
            )
        
        logger.info(f"Generating Gmail OAuth URL for user {user_id} with redirect_uri: {redirect_uri}")
        
        # Generate state token for CSRF protection (includes user_id and access_token)
        # State token ensures only the authenticated user who initiated the flow can complete it
        state = generate_state_token(user_id, access_token)
        
        # Use the redirect_uri passed from gateway (single source of truth)
        flow = get_oauth_flow(redirect_uri)
        
        # Generate authorization URL
        auth_url = get_authorization_url(flow, state)
        logger.info(f"Generated authorization URL successfully")
        
        return GmailAuthUrlResponse(auth_url=auth_url, state=state)
    except HTTPException:
        # Re-raise HTTP exceptions (like 401 from get_user_from_jwt)
        raise
    except ValueError as e:
        logger.error(f"OAuth configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth configuration error: {str(e)}. Please check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    except Exception as e:
        logger.error(f"Error generating Gmail auth URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authorization URL"
        )


@router.get("/auth/gmail/callback")
async def gmail_oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    redirect_uri: str = Query(None)
):
    """
    Handle Gmail OAuth callback.
    
    This is the public callback endpoint that Google redirects to.
    If redirect_uri is provided (from gateway), use it. Otherwise, use the configured one.
    """
    try:
        # Check for OAuth errors
        if error:
            logger.warning(f"OAuth error: {error}")
            # Redirect to frontend with error
            frontend_url = "http://localhost:5173"
            return RedirectResponse(
                url=f"{frontend_url}/settings?gmail_error={error}",
                status_code=302
            )
        
        # If code or state is missing, redirect with error
        if not code or not state:
            logger.error(f"Missing required parameters: code={code is not None}, state={state is not None}")
            frontend_url = "http://localhost:5173"
            return RedirectResponse(
                url=f"{frontend_url}/settings?gmail_error=invalid_callback",
                status_code=302
            )
        
        # Use redirect_uri from parameter if provided (from gateway), otherwise use configured one
        # This allows the gateway to pass the redirect_uri, but also works if called directly by Google
        if not redirect_uri:
            redirect_uri = settings.GOOGLE_REDIRECT_URI
            logger.info(f"Using configured redirect_uri: {redirect_uri}")
        else:
            logger.info(f"Using redirect_uri from gateway: {redirect_uri}")
        
        logger.info(f"Processing OAuth callback with redirect_uri: {redirect_uri}")
        
        # Verify state token (contains user_id and access_token)
        logger.info(f"Received callback with state: {state[:30]}... (truncated)")
        state_data = verify_state_token(state)
        if not state_data:
            logger.error(f"Invalid or expired state token. State not found in store or expired.")
            frontend_url = "http://localhost:5173"
            return RedirectResponse(
                url=f"{frontend_url}/settings?gmail_error=invalid_state",
                status_code=302
            )
        
        user_id = state_data["user_id"]
        access_token = state_data["access_token"]
        
        # Verify the access token is still valid by checking with auth-service
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                verify_response = await client.get(
                    f"{settings.AUTH_SERVICE_URL}/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if verify_response.status_code != 200:
                    logger.error(f"Access token invalid or expired for user {user_id}")
                    frontend_url = "http://localhost:5173"
                    return RedirectResponse(
                        url=f"{frontend_url}/?gmail_error=session_expired&message=Your session has expired. Please login again.",
                        status_code=302
                    )
                # Verify the user_id matches
                user_info = verify_response.json()
                if str(user_info.get("id")) != str(user_id):
                    logger.error(f"User ID mismatch: state={user_id}, token={user_info.get('id')}")
                    frontend_url = "http://localhost:5173"
                    return RedirectResponse(
                        url=f"{frontend_url}/?gmail_error=invalid_user",
                        status_code=302
                    )
        except httpx.RequestError as e:
            logger.error(f"Error verifying access token: {e}")
            frontend_url = "http://localhost:5173"
            return RedirectResponse(
                url=f"{frontend_url}/settings?gmail_error=auth_service_unavailable",
                status_code=302
            )
        
        # Exchange code for tokens using the SAME redirect_uri from gateway
        # This MUST match exactly what was used in the authorization URL
        logger.info(f"Exchanging authorization code for tokens with redirect_uri: {redirect_uri}")
        flow = get_oauth_flow(redirect_uri)
        tokens = exchange_code_for_tokens(flow, code, redirect_uri)
        
        # Get Gmail profile to get email
        profile = get_gmail_profile(tokens)
        gmail_email = profile.get("email")
        
        # Store tokens via auth-service API
        await store_gmail_tokens(user_id, tokens, gmail_email, access_token)
        
        # Redirect to frontend Settings page with success
        frontend_url = "http://localhost:5173"
        return RedirectResponse(
            url=f"{frontend_url}/settings?gmail_connected=true&email={gmail_email}",
            status_code=302
        )
    except ValueError as e:
        # OAuth configuration errors (missing credentials, etc.)
        error_msg = str(e)
        logger.error(f"OAuth configuration error in callback: {error_msg}", exc_info=True)
        frontend_url = "http://localhost:5173"
        
        # Detect specific error types from the error message
        error_msg_lower = error_msg.lower()
        if "redirect_uri_mismatch" in error_msg_lower or "redirect_uri" in error_msg_lower:
            error_code = "redirect_uri_mismatch"
        elif "invalid_grant" in error_msg_lower:
            error_code = "invalid_grant"
        elif "invalid_client" in error_msg_lower:
            error_code = "invalid_client"
        elif "oauthlib" in error_msg_lower:
            # Extract oauthlib error type if possible
            if "invalidgranterror" in error_msg_lower or "invalid_grant" in error_msg_lower:
                error_code = "invalid_grant"
            elif "redirecturimismatcherror" in error_msg_lower:
                error_code = "redirect_uri_mismatch"
            else:
                error_code = "oauth_error"
        else:
            error_code = "oauth_config_error"
        
        return RedirectResponse(
            url=f"{frontend_url}/settings?gmail_error={error_code}",
            status_code=302
        )
    except Exception as e:
        # Log the full exception for debugging
        logger.error(f"Error in Gmail OAuth callback: {type(e).__name__}: {str(e)}", exc_info=True)
        frontend_url = "http://localhost:5173"
        # Try to provide a more specific error based on exception type
        if "redirect_uri_mismatch" in str(e).lower():
            error_code = "redirect_uri_mismatch"
        elif "invalid_grant" in str(e).lower():
            error_code = "invalid_grant"
        elif "access_denied" in str(e).lower():
            error_code = "access_denied"
        else:
            error_code = "callback_failed"
        return RedirectResponse(
            url=f"{frontend_url}/settings?gmail_error={error_code}",
            status_code=302
        )


@router.get("/gmail/status", response_model=GmailConnectionStatus)
async def get_gmail_status(
    user: dict = Depends(get_user_from_jwt),
    authorization: str = Header(None)
):
    """Get Gmail connection status for authenticated user."""
    user_id = user.get("id")
    access_token = authorization.replace("Bearer ", "") if authorization else None
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    # Query auth-service for connection status
    try:
        logger.info(f"Checking Gmail status for user {user_id}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/gmail/status",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Gmail status for user {user_id}: {data}")
                return GmailConnectionStatus(**data)
            else:
                logger.warning(f"Auth service returned status {response.status_code} for user {user_id}: {response.text}")
                return GmailConnectionStatus(is_connected=False)
    except httpx.RequestError as e:
        logger.error(f"Network error getting Gmail status for user {user_id}: {e}")
        return GmailConnectionStatus(is_connected=False)
    except Exception as e:
        logger.error(f"Error getting Gmail status for user {user_id}: {e}", exc_info=True)
        return GmailConnectionStatus(is_connected=False)


@router.post("/gmail/disconnect", response_model=GmailDisconnectResponse)
async def disconnect_gmail(
    user: dict = Depends(get_user_from_jwt),
    authorization: str = Header(None)
):
    """Disconnect Gmail account for authenticated user."""
    user_id = user.get("id")
    access_token = authorization.replace("Bearer ", "") if authorization else None
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    # Revoke tokens via auth-service API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/gmail/disconnect",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                return GmailDisconnectResponse(
                    message="Gmail account disconnected successfully",
                    success=True
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to disconnect Gmail"
                )
    except httpx.RequestError as e:
        logger.error(f"Error calling auth-service to disconnect: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable"
        )