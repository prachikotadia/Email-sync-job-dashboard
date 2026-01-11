from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.config import get_settings

settings = get_settings()


def setup_cors(app: FastAPI):
    """Configure CORS middleware."""
    origins = settings.get_cors_origins()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
