from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, auth, gmail, google_auth
from app.config import get_settings
from app.db.session import init_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Auth Service",
    description="Authentication and authorization service",
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

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting auth-service...")
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        error_str = str(e).lower()
        # Check if it's a connection error (network/DNS issue)
        if 'could not translate host name' in error_str or 'name or service not known' in error_str or 'operationalerror' in error_str:
            logger.error(f"❌ Database connection failed: {e}")
            logger.error("⚠️  Service will start but database operations will fail until connection is restored.")
            logger.error("💡 Tip: For local development, use SQLite by setting AUTH_DATABASE_URL=sqlite:///./auth.db in .env")
            # Don't raise - allow service to start, but database operations will fail
            # This allows the service to at least respond to health checks
        else:
            logger.error(f"Failed to initialize database: {e}")
            raise  # Re-raise for other errors


# Routes
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(gmail.router, prefix="/api", tags=["gmail"])
app.include_router(google_auth.router)  # Google OAuth unified login


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
