from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os


class Settings(BaseSettings):
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/gmail/callback"  # Goes through API Gateway
    
    # Auth Service URL (to get user info from JWT)
    AUTH_SERVICE_URL: str = "http://localhost:8003"
    
    # Service
    SERVICE_NAME: str = "gmail-connector-service"
    SERVICE_PORT: int = 8001
    
    # Database for storing OAuth tokens (use auth-service database or separate)
    # For simplicity, we'll use a shared database or API calls to auth-service
    DATABASE_URL: str = "sqlite:///./gmail_tokens.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_scopes(self) -> List[str]:
        """Gmail API scopes - read-only email access."""
        return [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.metadata"
        ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()