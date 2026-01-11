from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import gmail_auth
from app.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

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

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "gmail-connector-service"}