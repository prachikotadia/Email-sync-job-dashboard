from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "API Gateway"
    
    # Service URLs (default to local dev ports)
    APPLICATION_SERVICE_URL: str = "http://127.0.0.1:8002"
    AUTH_SERVICE_URL: str = "http://127.0.0.1:8003"
    GMAIL_SERVICE_URL: str = "http://127.0.0.1:8001"
    EMAIL_INTELLIGENCE_URL: str = "http://127.0.0.1:8004"
    NOTIFICATION_URL: str = "http://127.0.0.1:8005"

    class Config:
        env_file = ".env"

settings = Settings()
