import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.classification import router as classification_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Email Intelligence Service",
    description="Email classification service for job application status",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(classification_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "email-intelligence-service"}


@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("Email Intelligence Service starting up...")
    logger.info("Phase 1: Rule-based classifier initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information."""
    logger.info("Email Intelligence Service shutting down...")
