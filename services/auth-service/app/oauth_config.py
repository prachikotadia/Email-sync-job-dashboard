"""
OAuth 2.0 and OpenID Connect Configuration

This module defines the OAuth scopes and configuration constants used throughout
the authentication flow. All scopes must be explicitly defined here to ensure
consistency between authorization URL generation and token exchange.

WHY 'openid' IS REQUIRED:
- Google's OAuth 2.0 implementation automatically adds the 'openid' scope when
  using OpenID Connect endpoints (userinfo.email, userinfo.profile)
- To prevent scope mismatch warnings, we must explicitly request 'openid' in our
  authorization request
- This ensures the returned scopes match the requested scopes exactly
- OpenID Connect provides standardized user identity claims via ID tokens
"""

from typing import List, Tuple

# OAuth 2.0 Scopes - MUST be identical in authorization URL and token exchange
# These scopes are used in both get_authorization_url() and exchange_code()
# 
# COMMON GOOGLE OAUTH PITFALLS:
# 1. Scope Mismatch: If you don't include 'openid', Google adds it automatically
#    and you'll get "Scope has changed" warnings. Always include 'openid' explicitly.
# 2. Redirect URI Mismatch: The redirect_uri in authorization URL must EXACTLY
#    match the one in token exchange AND in Google Cloud Console.
# 3. State Parameter: Always validate the state parameter to prevent CSRF attacks.
# 4. Refresh Tokens: Use access_type="offline" and prompt="consent" to get refresh tokens.
OAUTH_SCOPES: List[str] = [
    # OpenID Connect core scope - REQUIRED for userinfo endpoints
    # Without this, Google will add it automatically and cause scope mismatch warnings
    "openid",
    
    # User profile information
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    
    # Gmail read-only access for email synchronization
    "https://www.googleapis.com/auth/gmail.readonly",
]

# OAuth 2.0 Flow Parameters
OAUTH_ACCESS_TYPE: str = "offline"  # Required to get refresh tokens
OAUTH_PROMPT: str = "consent"  # Force consent screen to ensure refresh token
# Note: include_granted_scopes is omitted due to Google API parameter validation issues
# The library converts Python boolean True to string "True" (capitalized) instead of "true"
# This causes "Invalid value, must be one of false, true: True" error
# If needed, you can add it back by modifying google_oauth.py to pass it as a string
# OAUTH_INCLUDE_GRANTED_SCOPES: bool = True  # Include previously granted scopes

# Google OAuth 2.0 Endpoints
GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI: str = "https://www.googleapis.com/oauth2/v2/userinfo"

# OpenID Connect ID Token Validation
# Google's issuer for ID tokens
GOOGLE_ISSUER: str = "https://accounts.google.com"

# Security Settings
# State token length for CSRF protection (32 bytes = 256 bits)
OAUTH_STATE_BYTES: int = 32

# Token expiration defaults (in seconds)
DEFAULT_ACCESS_TOKEN_EXPIRY: int = 3600  # 1 hour


def validate_scopes(requested: List[str], returned: List[str]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate that returned scopes are a superset of requested scopes.
    
    Google may add additional scopes (like 'openid'), so we check that:
    1. All requested scopes are present in returned scopes
    2. Any additional scopes are acceptable (currently only 'openid' is expected)
    
    Args:
        requested: Scopes that were requested in the authorization URL
        returned: Scopes that were returned in the token response
        
    Returns:
        Tuple of (is_valid, missing_scopes, unexpected_scopes)
        - is_valid: True if all requested scopes are present
        - missing_scopes: List of requested scopes not found in returned scopes
        - unexpected_scopes: List of returned scopes not in requested scopes
    """
    requested_set = set(requested)
    returned_set = set(returned)
    
    missing = list(requested_set - returned_set)
    unexpected = list(returned_set - requested_set)
    
    # 'openid' is expected to be added by Google if not explicitly requested
    # Remove it from unexpected if it was added
    # NOTE: With our implementation, 'openid' is always in requested_set,
    # so this should never trigger, but we keep it for defensive programming
    if "openid" in unexpected and "openid" not in requested_set:
        unexpected.remove("openid")
    
    # Validation passes if no requested scopes are missing
    is_valid = len(missing) == 0
    
    return is_valid, missing, unexpected


def assert_scopes_valid(requested: List[str], returned: List[str]) -> None:
    """
    Assert that returned scopes are valid (all requested scopes present).
    
    This is a convenience function that raises ValueError if validation fails.
    Use this in production code to fail fast on scope mismatches.
    
    Args:
        requested: Scopes that were requested
        returned: Scopes that were returned
        
    Raises:
        ValueError: If any requested scopes are missing from returned scopes
    
    Example:
        >>> requested = ["openid", "userinfo.email"]
        >>> returned = ["openid", "userinfo.email"]
        >>> assert_scopes_valid(requested, returned)  # No error
        >>> 
        >>> returned = ["openid"]  # Missing userinfo.email
        >>> assert_scopes_valid(requested, returned)  # Raises ValueError
    """
    is_valid, missing, unexpected = validate_scopes(requested, returned)
    
    if not is_valid:
        error_msg = (
            f"Scope validation failed: "
            f"missing={missing}, "
            f"unexpected={unexpected}, "
            f"requested={requested}, "
            f"returned={returned}"
        )
        raise ValueError(error_msg)
