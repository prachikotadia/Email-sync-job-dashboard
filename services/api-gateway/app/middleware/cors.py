from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.config import get_settings
import logging

settings = get_settings()


def setup_cors(app: FastAPI):
    """Configure CORS middleware.
    
    CRITICAL: Cannot use wildcard "*" with credentials: "include".
    Must use explicit origins.
    """
    origins = settings.get_cors_origins()
    logger = logging.getLogger(__name__)
    
    # CRITICAL FIX: Reject wildcard when credentials are enabled
    if "*" in origins:
        logger.error("❌ CORS ERROR: Cannot use wildcard '*' with credentials: 'include'")
        logger.error("   Browsers reject this combination. Using explicit origins instead.")
        # Fallback to explicit localhost origins
        origins = ["http://localhost:5173", "http://localhost:5174"]
        logger.warning(f"   Using fallback origins: {origins}")
    
    # Ensure no wildcard remains
    origins = [origin for origin in origins if origin != "*"]
    
    if not origins:
        logger.error("❌ No valid CORS origins configured. Using default localhost:5173")
        origins = ["http://localhost:5173"]
    
    logger.info(f"✅ Configuring CORS with explicit origins: {origins}")
    logger.info(f"   allow_credentials=True (required for cookies)")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # Explicit origins only, NO wildcard
        allow_credentials=True,  # Required for cookies
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
