"""
Environment variable validation for cross-platform compatibility.
"""
import os
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

def validate_required_env_vars(required_vars: List[str]) -> Tuple[bool, List[str]]:
    """Validate that all required environment variables are set."""
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing.append(var)
    
    return len(missing) == 0, missing

def validate_all() -> bool:
    """Validate all environment variables."""
    logger.info("🔍 Validating environment variables...")
    
    required = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']
    is_valid, missing = validate_required_env_vars(required)
    
    if not is_valid:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing)}")
        logger.error("   Please set these in your .env file")
        logger.error("   Get credentials from: https://console.cloud.google.com/apis/credentials")
        return False
    
    logger.info("✅ Environment validation passed")
    return True
