from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # JWT (must match auth-service)
    JWT_SECRET: str = "change_me"
    JWT_ISSUER: str = "email-sync-job-dashboard"
    JWT_AUDIENCE: str = "email-sync-job-dashboard-users"
    
    # Service URLs
    APPLICATION_SERVICE_URL: str = "http://application-service:8002"
    AUTH_SERVICE_URL: str = "http://auth-service:8003"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"
    
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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
