"""
Google OAuth token refresh implementation.
"""
import httpx
import logging
from typing import Dict, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ReauthRequiredError(Exception):
    """Raised when re-authentication is required."""
    pass


async def refresh_access_token(refresh_token: str) -> Dict[str, any]:
    """
    Refresh access token using refresh token via Google OAuth token endpoint.
    
    Args:
        refresh_token: OAuth refresh token
        
    Returns:
        Dict with:
        - access_token: New access token
        - expires_in: Seconds until expiration
        - scope: Token scopes (if provided)
        - token_type: Token type (usually "Bearer")
        
    Raises:
        ReauthRequiredError: If refresh fails (missing refresh_token or API error)
        httpx.RequestError: If network error occurs
    """
    if not refresh_token:
        logger.error("Refresh token is missing - re-auth required")
        raise ReauthRequiredError("Refresh token is missing. Please reconnect your Gmail account.")
    
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    
    if not client_id or not client_secret:
        logger.error("Google OAuth credentials not configured")
        raise ReauthRequiredError("OAuth credentials not configured")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                try:
                    error_json = response.json()
                    error_code = error_json.get("error", "unknown")
                    error_description = error_json.get("error_description", error_text)
                    logger.error(f"Token refresh failed: {response.status_code} - {error_code}: {error_description}")
                except:
                    logger.error(f"Token refresh failed: {response.status_code} - {error_text}")
                
                # 400/401 from refresh endpoint means refresh token is invalid/expired
                if response.status_code in (400, 401):
                    raise ReauthRequiredError("Refresh token is invalid or expired. Please reconnect your Gmail account.")
                else:
                    raise ReauthRequiredError(f"Token refresh failed: {error_text}")
            
            result = response.json()
            logger.info("Access token refreshed successfully")
            
            return {
                "access_token": result.get("access_token"),
                "expires_in": result.get("expires_in", 3600),
                "scope": result.get("scope"),
                "token_type": result.get("token_type", "Bearer")
            }
            
    except ReauthRequiredError:
        raise
    except httpx.RequestError as e:
        logger.error(f"Network error refreshing token: {e}")
        raise ReauthRequiredError(f"Network error during token refresh: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error refreshing token: {e}", exc_info=True)
        raise ReauthRequiredError(f"Token refresh failed: {str(e)}")
