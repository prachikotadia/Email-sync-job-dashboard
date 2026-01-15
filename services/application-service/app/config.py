from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Application Service"
    
    # Supabase / DB
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    # Cross-platform database path - use absolute path
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).parent.parent.parent / 'app.db'}"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
