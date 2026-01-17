import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
    gmail_service_url: str = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector:8002")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

    class Config:
        env_file = ".env"

settings = Settings()
