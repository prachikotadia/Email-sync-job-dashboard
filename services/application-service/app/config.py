from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Application Service"
    API_V1_STR: str = "/api/v1"
    
    # Supabase / DB
    SUPABASE_URL: str
    SUPABASE_KEY: str
    DATABASE_URL: Optional[str] = None # Optional for SQLAlchemy direct connection

    # Service Configuration
    GHOSTED_DAYS_THRESHOLD: int = 14
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
