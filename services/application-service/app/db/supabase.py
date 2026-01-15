from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models import Base
import logging

logger = logging.getLogger(__name__)

# SQLAlchemy setup
# We use synchronous engine for simplicity in this phase
# Cross-platform: SQLite paths are handled automatically
# Convert file:// URLs to proper SQLite paths for Windows compatibility
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    # Handle both sqlite:///./file.db and sqlite:///path/to/file.db
    # SQLAlchemy handles this correctly, but we log for debugging
    logger.info(f"📊 Database URL: {db_url}")

engine = create_engine(
    db_url, 
    connect_args={"check_same_thread": False} if "sqlite" in db_url.lower() else {},
    # Cross-platform: Ensure SQLite works on Windows
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)
