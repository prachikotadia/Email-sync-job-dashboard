from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os
from pathlib import Path


class Settings(BaseSettings):
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/gmail/callback"  # Goes through API Gateway
    
    # Auth Service URL (to get user info from JWT)
    AUTH_SERVICE_URL: str = "http://localhost:8003"
    
    # Application Service URL (for ingesting processed emails)
    APPLICATION_SERVICE_URL: str = "http://localhost:8002"
    
    # Email Intelligence Service URL (for email classification)
    EMAIL_INTELLIGENCE_SERVICE_URL: str = "http://localhost:8004"
    
    # Service
    SERVICE_NAME: str = "gmail-connector-service"
    SERVICE_PORT: int = 8001
    
    # Environment
    ENV: str = "dev"  # dev, staging, production
    
    # Database for storing OAuth tokens (use auth-service database or separate)
    # For simplicity, we'll use a shared database or API calls to auth-service
    # Cross-platform path handling
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).parent.parent.parent / 'gmail_tokens.db'}"
    )
    
    # Job Email Filtering Configuration - PRODUCTION GRADE
    GMAIL_SYNC_DAYS: int = 180  # Days to look back for emails (can extend to years)
    GMAIL_QUERY_DAYS: int = 180  # Days to look back in Gmail query
    GMAIL_MAX_RESULTS: int = 1200  # HARD LIMIT: Maximum emails to fetch per sync (production-grade)
    GMAIL_BATCH_SIZE: int = 100  # Batch size for pagination (Gmail API max is 500, but 100 is optimal)
    CLASSIFIER_MIN_CONFIDENCE: float = 0.5  # Minimum confidence to store (strict classification)
    CLASSIFIER_MIN_SCORE: int = 4  # Minimum score to accept email
    HEURISTIC_ACCEPT: int = 6  # Minimum score to process email
    HEURISTIC_REJECT: int = 0  # Maximum score to reject email
    LLM_MIN_CONFIDENCE: float = 0.75  # Minimum confidence to store email
    MAX_EMAILS_PER_SYNC: int = 200  # Maximum emails to process per sync
    DRY_RUN: bool = False  # If True, don't store emails, only audit
    STORE_CATEGORIES: str = "APPLIED_CONFIRMATION,INTERVIEW,REJECTION,OFFER,ASSESSMENT"  # Comma-separated list of categories to store
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_scopes(self) -> List[str]:
        """
        Gmail API scopes - read-only email access.
        
        CRITICAL: Use gmail.readonly (NOT gmail.metadata) to support Gmail search queries (q parameter).
        
        Scope Requirements:
        - ✅ gmail.readonly: Allows messages.list with q parameter for searching (e.g., is:unread OR subject:application)
        - ❌ gmail.metadata: Does NOT support q parameter and will return 403 error:
          "Metadata scope does not support 'q' parameter"
        
        IMPORTANT WARNING: If SCOPES are modified, delete existing token files/database entries
        to trigger re-authentication. Existing tokens may have been created with different scopes.
        
        To force re-authentication:
        1. Disconnect Gmail in Settings UI, OR
        2. Delete tokens from auth-service database (gmail_connections table), OR
        3. Clear OAuth tokens in your Google Account (https://myaccount.google.com/permissions)
        """
        SCOPES = [
            "https://www.googleapis.com/auth/gmail.readonly"  # Required for Gmail search queries
        ]
        return SCOPES


@lru_cache()
def get_settings() -> Settings:
    return Settings()