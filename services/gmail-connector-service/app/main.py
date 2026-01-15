from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import gmail_auth, gmail_sync
from app.config import get_settings
from app.utils.env_validation import validate_all
import logging
import sys
import platform

# Import debug router conditionally
settings = get_settings()
if settings.ENV == "dev":
    from app.api import debug

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log platform information for debugging
logger.info(f"🚀 Starting Gmail Connector Service on {platform.system()} {platform.release()}")
logger.info(f"   Python: {platform.python_version()}")
logger.info(f"   Platform: {platform.platform()}")

settings = get_settings()

# Validate environment variables at startup
if not validate_all():
    logger.error("❌ Environment validation failed. Please check your .env file.")
    sys.exit(1)

app = FastAPI(
    title="Gmail Connector Service",
    description="Gmail OAuth and email sync service",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(gmail_auth.router, tags=["gmail"])
app.include_router(gmail_sync.router, tags=["gmail"])

# Debug routes (DEV ONLY)
if settings.ENV == "dev":
    app.include_router(debug.router, tags=["debug"])

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "gmail-connector-service"}