from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path


class Settings(BaseSettings):
    # Database - Cross-platform path handling
    AUTH_DATABASE_URL: str = os.getenv(
        "AUTH_DATABASE_URL",
        f"sqlite:///{Path(__file__).parent.parent.parent / 'auth.db'}"
    )
    
    # JWT
    JWT_SECRET: str = "change_me"
    JWT_ISSUER: str = "email-sync-job-dashboard"
    JWT_AUDIENCE: str = "email-sync-job-dashboard-users"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    
    # Google OAuth (for unified login + Gmail connection)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    
    # Frontend URL (for redirects)
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Service
    SERVICE_NAME: str = "auth-service"
    SERVICE_PORT: int = 8003
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
