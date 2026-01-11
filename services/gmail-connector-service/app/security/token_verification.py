"""
Runtime token verification using Google's tokeninfo endpoint.
Verifies that the actual access token has the required gmail.readonly scope.
"""
import httpx
import logging
from typing import Dict, Optional, List
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_token_scopes(access_token: str) -> Dict[str, any]:
    """
    Verify access token scopes using Google's tokeninfo endpoint.
    
    Args:
        access_token: The OAuth access token to verify
        
    Returns:
        Dict with:
        - scopes: List of scopes from tokeninfo
        - has_readonly: bool - whether gmail.readonly is present
        - has_metadata: bool - whether gmail.metadata is present
        - user_id: str - Google user ID (if available)
        - expires_in: int - seconds until expiration (if available)
        
    Raises:
        ValueError: If token is invalid or verification fails
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": access_token}
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Tokeninfo verification failed: {response.status_code} - {error_text}")
                raise ValueError(f"Token verification failed: {error_text}")
            
            tokeninfo = response.json()
            
            # Extract scopes from tokeninfo
            scope_str = tokeninfo.get("scope", "")
            scopes = scope_str.split() if scope_str else []
            
            # Check for required scopes
            has_readonly = "https://www.googleapis.com/auth/gmail.readonly" in scopes
            has_metadata = "https://www.googleapis.com/auth/gmail.metadata" in scopes
            
            logger.info(f"Tokeninfo verification: scopes={scopes}, has_readonly={has_readonly}, has_metadata={has_metadata}")
            
            return {
                "scopes": scopes,
                "has_readonly": has_readonly,
                "has_metadata": has_metadata,
                "user_id": tokeninfo.get("user_id"),
                "expires_in": tokeninfo.get("expires_in"),
                "audience": tokeninfo.get("aud"),
                "issued_to": tokeninfo.get("issued_to")
            }
    except httpx.RequestError as e:
        logger.error(f"Network error verifying token: {e}")
        raise ValueError(f"Failed to verify token: network error")
    except Exception as e:
        logger.error(f"Error verifying token: {e}", exc_info=True)
        raise ValueError(f"Token verification failed: {str(e)}")


def require_readonly_scope(tokeninfo_result: Dict) -> None:
    """
    Verify that tokeninfo result includes gmail.readonly scope and does NOT include metadata scope.
    
    CRITICAL: If metadata scope is present (even with readonly), Google's API will use metadata
    scope restrictions, which do NOT support search queries (q parameter). This causes 403 errors.
    
    Args:
        tokeninfo_result: Result from verify_token_scopes()
        
    Raises:
        ValueError: If gmail.readonly scope is missing OR if metadata scope is present
    """
    has_readonly = tokeninfo_result.get("has_readonly", False)
    has_metadata = tokeninfo_result.get("has_metadata", False)
    scopes = tokeninfo_result.get("scopes", [])
    
    # CRITICAL: If metadata is present, fail immediately
    # Even if readonly is also present, Google's API will use metadata scope restrictions
    # Metadata scope does NOT support search queries (q parameter)
    if has_metadata:
        logger.error(
            f"❌ Gmail token has metadata scope (even with readonly). "
            f"This causes 403 errors because metadata doesn't support search queries. "
            f"Tokeninfo scopes: {scopes}. "
            f"User MUST disconnect and reconnect to get ONLY readonly scope."
        )
        raise ValueError(
            "Gmail connection has metadata scope. "
            "Even if readonly is present, metadata scope takes precedence and doesn't support search queries. "
            "Please disconnect and reconnect your Gmail account to get ONLY readonly scope."
        )
    
    # If readonly is missing, fail
    if not has_readonly:
        logger.error(
            f"Gmail connection missing gmail.readonly scope. "
            f"Tokeninfo scopes: {scopes}. "
            f"Please disconnect and reconnect your Gmail account."
        )
        raise ValueError(
            "Gmail connection missing gmail.readonly scope. "
            "Please disconnect and reconnect your Gmail account."
        )
