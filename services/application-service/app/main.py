from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, applications, resumes, export, ingest, metrics
from app.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# from app.db.supabase import create_tables # Uncomment to auto-migrate on start

app = FastAPI(
    title="Application Service",
    description="Application service for Email Sync Job Dashboard",
    version="1.0.0",
    redirect_slashes=False  # Disable automatic redirects for trailing slashes
)

# CORS middleware - allow gateway and frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],  # Frontend and Gateway
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

logger.info("Application service starting...")

app.include_router(health.router)
app.include_router(applications.router, prefix="/applications", tags=["Applications"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
app.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
app.include_router(export.router, prefix="/export", tags=["Export"])
# Internal Ingest Endpoint (Phase 6 but useful stub)
app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])

logger.info("Application service routes registered")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
