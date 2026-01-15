"""
Environment variable validation for cross-platform compatibility.
Validates all required environment variables at startup.
"""
import os
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

def validate_required_env_vars(required_vars: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that all required environment variables are set.
    
    Returns:
        (is_valid, missing_vars)
    """
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing.append(var)
    
    return len(missing) == 0, missing

def validate_google_oauth_config() -> Tuple[bool, List[str]]:
    """Validate Google OAuth configuration."""
    required = [
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET',
    ]
    
    is_valid, missing = validate_required_env_vars(required)
    
    if not is_valid:
        logger.error(f"❌ Missing required Google OAuth environment variables: {', '.join(missing)}")
        logger.error("   Please set these in your .env file")
        logger.error("   Get credentials from: https://console.cloud.google.com/apis/credentials")
    
    return is_valid, missing

def validate_service_urls() -> Tuple[bool, List[str]]:
    """Validate service URLs are configured."""
    required = [
        'AUTH_SERVICE_URL',
    ]
    
    is_valid, missing = validate_required_env_vars(required)
    
    if not is_valid:
        logger.warning(f"⚠️  Missing service URL environment variables: {', '.join(missing)}")
        logger.warning("   Using default values")
    
    return True, []  # Service URLs have defaults, so don't fail

def validate_all() -> bool:
    """Validate all environment variables. Returns True if all validations pass."""
    logger.info("🔍 Validating environment variables...")
    
    oauth_valid, oauth_missing = validate_google_oauth_config()
    urls_valid, urls_missing = validate_service_urls()
    
    if not oauth_valid:
        logger.error("❌ Environment validation failed. Please fix the issues above.")
        return False
    
    logger.info("✅ Environment validation passed")
    return True
