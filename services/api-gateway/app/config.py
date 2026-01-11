from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import re


class Settings(BaseSettings):
    # JWT (must match auth-service)
    JWT_SECRET: str = "change_me"
    JWT_ISSUER: str = "email-sync-job-dashboard"
    JWT_AUDIENCE: str = "email-sync-job-dashboard-users"
    
    # Service URLs
    APPLICATION_SERVICE_URL: str = "http://application-service:8002"
    AUTH_SERVICE_URL: str = "http://auth-service:8003"
    GMAIL_SERVICE_URL: str = "http://localhost:8001"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"
    
    # Google OAuth
    # This can point to either the gateway (http://localhost:8000/auth/gmail/callback)
    # or directly to gmail-connector-service (http://localhost:8001/auth/gmail/callback)
    # Must match EXACTLY what's registered in Google Cloud Console
    GOOGLE_REDIRECT_URI: str = "http://localhost:8001/auth/gmail/callback"
    
    # Environment
    ENV: str = "dev"  # dev, staging, production
    
    # Service
    SERVICE_NAME: str = "api-gateway"
    SERVICE_PORT: int = 8000
    
    # HTTP Client settings
    HTTP_TIMEOUT: float = 30.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    def get_google_redirect_uri(self) -> str:
        """
        Get the Google OAuth redirect URI.
        This is the single source of truth for the redirect URI.
        Must match exactly what's registered in Google Cloud Console.
        """
        return self.GOOGLE_REDIRECT_URI.strip()
    
    def validate_redirect_uri(self) -> None:
        """
        Validate redirect URI format on startup.
        Raises ValueError if invalid.
        """
        redirect_uri = self.get_google_redirect_uri()
        
        if not redirect_uri:
            raise ValueError(
                "GOOGLE_REDIRECT_URI is required. "
                "Set it in .env file (e.g., GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback)"
            )
        
        # Must start with http://localhost or https://
        if not (redirect_uri.startswith("http://localhost") or redirect_uri.startswith("https://")):
            raise ValueError(
                f"GOOGLE_REDIRECT_URI must start with 'http://localhost' (for local dev) or 'https://' (for production). "
                f"Got: {redirect_uri}"
            )
        
        # No trailing slash
        if redirect_uri.endswith("/"):
            raise ValueError(
                f"GOOGLE_REDIRECT_URI must not have a trailing slash. "
                f"Got: {redirect_uri}"
            )
        
        # Basic URL validation - allow both gateway and gmail-connector-service URLs
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(localhost|127\.0\.0\.1|'  # localhost or 127.0.0.1
            r'([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})'  # domain
            r'(:\d+)?'  # optional port
            r'/.+$'  # path (must have a path)
        )
        
        if not url_pattern.match(redirect_uri):
            raise ValueError(
                f"GOOGLE_REDIRECT_URI has invalid format. "
                f"Must be a valid URL like: http://localhost:8000/auth/gmail/callback "
                f"Got: {redirect_uri}"
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_google_redirect_uri() -> str:
    """
    Get the Google OAuth redirect URI from settings.
    This is the single source of truth - use this function everywhere.
    """
    settings = get_settings()
    return settings.get_google_redirect_uri()
