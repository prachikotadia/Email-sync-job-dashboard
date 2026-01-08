from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Application Service"
    
    # Supabase / DB
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    DATABASE_URL: str = "sqlite:///./app.db" # Default to sqlite for local dev if no env

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
