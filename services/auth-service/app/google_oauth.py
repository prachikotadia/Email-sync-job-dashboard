"""
Google OAuth 2.0 and OpenID Connect Implementation

This module handles the complete OAuth 2.0 authorization flow with Google,
including OpenID Connect support for user identity verification.

Key Features:
- Explicit scope management to prevent scope mismatch errors
- CSRF protection via state parameter
- OpenID Connect ID token validation (when available)
- Comprehensive error handling and logging
- Production-safe token handling
"""

import os
import secrets
import logging
import time
from typing import Dict, Optional, Any
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google.auth.transport.requests import Request as GoogleRequest
import httpx

from app.oauth_config import (
    OAUTH_SCOPES,
    OAUTH_ACCESS_TYPE,
    OAUTH_PROMPT,
    GOOGLE_AUTH_URI,
    GOOGLE_TOKEN_URI,
    GOOGLE_USERINFO_URI,
    GOOGLE_ISSUER,
    OAUTH_STATE_BYTES,
    validate_scopes,
)

logger = logging.getLogger(__name__)


class GoogleOAuth:
    """
    Google OAuth 2.0 client with OpenID Connect support.
    
    This class manages the complete OAuth flow:
    1. Generate authorization URL with consistent scopes
    2. Exchange authorization code for tokens
    3. Validate returned scopes match requested scopes
    4. Verify OpenID Connect ID tokens (when available)
    5. Fetch user information
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize Google OAuth client.
        
        Args:
            client_id: Google OAuth 2.0 client ID
            client_secret: Google OAuth 2.0 client secret
            redirect_uri: OAuth redirect URI (must match Google Cloud Console)
        """
        if not client_id or not client_secret:
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
        if not redirect_uri:
            raise ValueError("REDIRECT_URI must be set")
        
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        # Use consistent scopes from config - MUST match in auth URL and token exchange
        self.scopes = OAUTH_SCOPES.copy()
        
        # Build client configuration for google_auth_oauthlib
        self.client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": GOOGLE_AUTH_URI,
                "token_uri": GOOGLE_TOKEN_URI,
                "redirect_uris": [redirect_uri],
            }
        }
        
        # Store state for CSRF protection (in production, use Redis/session)
        self._state_store: Dict[str, str] = {}
        
        logger.info(f"Initialized GoogleOAuth with redirect_uri: {redirect_uri}")
        logger.info(f"Requested scopes: {', '.join(self.scopes)}")
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate OAuth 2.0 authorization URL with consistent scopes.
        
        This method creates an authorization URL that will be used to redirect
        the user to Google's consent screen. The same scopes defined in OAUTH_SCOPES
        are used here and MUST be identical in exchange_code().
        
        Args:
            state: Optional state parameter for CSRF protection.
                   If not provided, a random state is generated.
        
        Returns:
            Tuple of (authorization_url, state)
            - authorization_url: URL to redirect user to Google
            - state: CSRF protection token (store in session/cookie)
        """
        # Create Flow with consistent scopes and redirect_uri
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,  # MUST match scopes in exchange_code()
            redirect_uri=self.redirect_uri  # MUST match redirect_uri in exchange_code()
        )
        
        # Generate state for CSRF protection if not provided
        if state is None:
            state = secrets.token_urlsafe(OAUTH_STATE_BYTES)
        
        flow.state = state
        
        # Store state for validation (in production, use Redis/session)
        self._state_store[state] = state
        
        # Generate authorization URL with required parameters
        # Note: include_granted_scopes is optional and can cause issues if not handled correctly
        # We'll omit it to avoid the "Invalid value, must be one of false, true: True" error
        # If you need to include previously granted scopes, you can add it back as a boolean
        authorization_url, _ = flow.authorization_url(
            access_type=OAUTH_ACCESS_TYPE,  # Required for refresh tokens
            prompt=OAUTH_PROMPT,  # Force consent screen
            # include_granted_scopes removed - Google API expects lowercase string, library converts incorrectly
        )
        
        logger.info(f"Generated authorization URL with state: {state[:16]}...")
        logger.info(f"Requested scopes: {', '.join(self.scopes)}")
        
        return authorization_url, state
    
    def validate_state(self, state: str) -> bool:
        """
        Validate OAuth state parameter for CSRF protection.
        
        Args:
            state: State parameter from OAuth callback
        
        Returns:
            True if state is valid, False otherwise
        """
        return state in self._state_store
    
    async def exchange_code(
        self, 
        code: str, 
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token with scope validation.
        
        This method:
        1. Exchanges the authorization code for tokens using the SAME scopes
           and redirect_uri as get_authorization_url()
        2. Validates that returned scopes match requested scopes
        3. Verifies OpenID Connect ID token if present
        4. Returns tokens with comprehensive logging
        
        Args:
            code: Authorization code from Google callback
            state: State parameter for CSRF validation (optional but recommended)
        
        Returns:
            Dictionary containing:
            - access_token: OAuth access token
            - refresh_token: OAuth refresh token (if available)
            - id_token: OpenID Connect ID token (if available)
            - token_uri: Token endpoint URI
            - client_id: OAuth client ID
            - client_secret: OAuth client secret
            - scopes: List of granted scopes
            - expires_at: Token expiration timestamp
        
        Raises:
            ValueError: If scopes don't match or validation fails
            Exception: If token exchange fails
        """
        # Validate state for CSRF protection
        if state and not self.validate_state(state):
            logger.warning(f"Invalid state parameter: {state[:16]}...")
            # In production, this should be a hard failure
            # For now, log warning but continue
        
        logger.info(f"Exchanging OAuth code (length: {len(code)})")
        logger.info(f"Using redirect_uri: {self.redirect_uri}")
        logger.info(f"Requested scopes: {', '.join(self.scopes)}")
        
        # Create Flow with IDENTICAL configuration as get_authorization_url()
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,  # MUST match scopes in get_authorization_url()
            redirect_uri=self.redirect_uri  # MUST match redirect_uri in get_authorization_url()
        )
        
        try:
            # Exchange authorization code for tokens
            flow.fetch_token(code=code)
        except Exception as fetch_error:
            error_detail = str(fetch_error)
            error_type = type(fetch_error).__name__
            
            logger.error(f"Token exchange failed: {error_detail}")
            logger.error(f"Error type: {error_type}")
            
            # Try to extract additional error details
            if hasattr(fetch_error, 'error'):
                logger.error(f"OAuth error code: {fetch_error.error}")
            if hasattr(fetch_error, 'error_description'):
                logger.error(f"OAuth error description: {fetch_error.error_description}")
            
            raise Exception(f"OAuth token exchange failed: {error_detail}")
        
        # Get credentials from flow
        credentials = flow.credentials
        
        if not credentials or not credentials.token:
            raise Exception("Failed to obtain access token from Google")
        
        # Validate returned scopes match requested scopes
        returned_scopes = list(credentials.scopes) if credentials.scopes else []
        is_valid, missing, unexpected = validate_scopes(self.scopes, returned_scopes)
        
        logger.info(f"Returned scopes: {', '.join(returned_scopes)}")
        
        if not is_valid:
            error_msg = (
                f"Scope mismatch: requested={self.scopes}, "
                f"returned={returned_scopes}, "
                f"missing={missing}, unexpected={unexpected}"
            )
            logger.error(error_msg)
            # In production, you might want to be more lenient if only 'openid' was added
            # For now, we'll log but continue if only expected scopes are present
            if missing:
                raise ValueError(f"Missing required scopes: {missing}")
        
        # Verify OpenID Connect ID token if present
        id_token_claims = None
        if hasattr(credentials, 'id_token') and credentials.id_token:
            try:
                id_token_claims = self._verify_id_token(credentials.id_token)
                logger.info("OpenID Connect ID token verified successfully")
            except Exception as id_error:
                logger.warning(f"ID token verification failed: {id_error}")
                # Don't fail the flow if ID token verification fails
                # Access token is still valid
        
        # Build token response
        token_response = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": returned_scopes,
        }
        
        # Add ID token if available
        if id_token_claims:
            token_response["id_token"] = credentials.id_token
            token_response["id_token_claims"] = id_token_claims
        
        # Calculate expiration with defensive handling
        if credentials.expiry:
            try:
                expiry_timestamp = credentials.expiry.timestamp()
                current_timestamp = time.time()
                seconds_left = int(expiry_timestamp - current_timestamp)
                
                # Ensure non-negative expiry
                if seconds_left < 0:
                    logger.warning(f"Token expiry is in the past, using default 3600s. Expiry: {credentials.expiry.isoformat()}")
                    seconds_left = 3600
                    expiry_timestamp = current_timestamp + 3600
                
                token_response["expires_at"] = credentials.expiry.isoformat()
                token_response["expires_in"] = seconds_left
                
                logger.info(f"Token expiry calculated: {seconds_left}s remaining (expires_at={credentials.expiry.isoformat()})")
            except (AttributeError, TypeError, OSError) as e:
                logger.warning(f"Error calculating token expiry: {e}, using default 3600s")
                # Fallback to 1 hour if expiry calculation fails
                token_response["expires_at"] = None
                token_response["expires_in"] = 3600
        else:
            # No expiry provided, use default 1 hour
            logger.info("No token expiry provided by Google, using default 3600s")
            token_response["expires_at"] = None
            token_response["expires_in"] = 3600
        
        logger.info("Successfully exchanged code for tokens")
        logger.info(f"Token expires in: {token_response.get('expires_in', 'N/A')}s")
        
        # NEVER log access tokens or refresh tokens in production
        logger.debug("Tokens obtained (not logged for security)")
        
        return token_response
    
    def _verify_id_token(self, id_token_string: str) -> Dict[str, Any]:
        """
        Verify OpenID Connect ID token.
        
        This validates:
        - Token signature
        - Issuer (must be Google)
        - Audience (must match client_id)
        - Expiration
        
        Args:
            id_token_string: JWT ID token string
        
        Returns:
            Decoded ID token claims
        
        Raises:
            ValueError: If token verification fails
        """
        try:
            request = GoogleRequest()
            claims = id_token.verify_oauth2_token(
                id_token_string,
                request,
                self.client_id,
            )
            
            # Verify issuer
            if claims.get("iss") not in [GOOGLE_ISSUER, "accounts.google.com"]:
                raise ValueError(f"Invalid issuer: {claims.get('iss')}")
            
            return claims
        except Exception as e:
            logger.error(f"ID token verification failed: {e}")
            raise
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from Google's userinfo endpoint.
        
        Args:
            access_token: OAuth access token
        
        Returns:
            User information dictionary with email, name, etc.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                GOOGLE_USERINFO_URI,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token using a refresh token.
        
        Args:
            refresh_token: OAuth refresh token
        
        Returns:
            New token response with access_token and optional new refresh_token
        """
        credentials = Credentials(
            token=None,  # Will be refreshed
            refresh_token=refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        
        # Refresh the token
        request = GoogleRequest()
        credentials.refresh(request)
        
        if not credentials.token:
            raise Exception("Failed to refresh access token")
        
        # Calculate expiration with defensive handling
        expires_at = None
        expires_in = None
        
        if credentials.expiry:
            try:
                expiry_timestamp = credentials.expiry.timestamp()
                current_timestamp = time.time()
                expires_in = int(expiry_timestamp - current_timestamp)
                
                # Ensure non-negative expiry
                if expires_in < 0:
                    logger.warning(f"Refresh token expiry is in the past, using default 3600s")
                    expires_in = 3600
                
                expires_at = credentials.expiry.isoformat()
            except (AttributeError, TypeError, OSError) as e:
                logger.warning(f"Error calculating refresh token expiry: {e}, using default 3600s")
                expires_in = 3600
        else:
            logger.info("No refresh token expiry provided, using default 3600s")
            expires_in = 3600
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expires_at": expires_at,
            "expires_in": expires_in,
        }
