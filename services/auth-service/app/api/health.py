from fastapi import APIRouter
from app.db.session import engine
from sqlalchemy import text
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    """Health check endpoint with database status."""
    db_status = "unknown"
    db_error = None
    
    try:
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = "disconnected"
        db_error = str(e)
        logger.warning(f"Database health check failed: {e}")
    
    if db_status == "connected":
        return {
            "status": "ok",
            "database": "connected"
        }
    else:
        return {
            "status": "degraded",
            "database": "disconnected",
            "error": db_error,
            "message": "Service is running but database is unavailable. Check AUTH_DATABASE_URL in .env"
        }
