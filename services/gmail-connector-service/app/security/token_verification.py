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


async def verify_token_scopes(access_token: str) -> tuple[bool, Optional[List[str]]]:
    """
    Verify access token scopes using Google's tokeninfo endpoint (OPTIONAL DEBUG ONLY).
    
    This is NOT a blocking gate - Gmail API 401 is authoritative.
    If tokeninfo fails, we return (False, None) and continue with Gmail API call.
    
    Args:
        access_token: The OAuth access token to verify
        
    Returns:
        Tuple of (success: bool, scopes: List[str]|None):
        - If tokeninfo succeeds: (True, list of scopes)
        - If tokeninfo fails: (False, None)
        
    NEVER raises exceptions - always returns a result.
    """
    if not access_token:
        logger.warning("Tokeninfo: Access token is empty")
        return False, None
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": access_token}
            )
            
            if response.status_code != 200:
                # Tokeninfo failed - log warning but don't block
                logger.warning(f"Tokeninfo returned {response.status_code} (non-blocking, continuing with Gmail API)")
                return False, None
            
            tokeninfo = response.json()
            
            # Extract scopes from tokeninfo
            scope_str = tokeninfo.get("scope", "")
            scopes = scope_str.split() if scope_str else []
            
            logger.debug(f"Tokeninfo verification: scopes={scopes}")
            
            return True, scopes
            
    except httpx.RequestError as e:
        logger.warning(f"Tokeninfo network error (non-blocking): {e}")
        return False, None
    except Exception as e:
        logger.warning(f"Tokeninfo error (non-blocking): {e}")
        return False, None


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
