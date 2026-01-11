from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.config import get_settings
from app.db.models import Base
import logging
import os

logger = logging.getLogger(__name__)

settings = get_settings()

# Get database URL and strip any whitespace/newlines
db_url = settings.AUTH_DATABASE_URL.strip().replace('\n', '').replace('\r', '')

# Validate database URL
if not db_url:
    raise ValueError("AUTH_DATABASE_URL is empty. Please set it in .env file.")

logger.info(f"Initializing database connection: {db_url.split('@')[-1] if '@' in db_url else db_url}")

# Determine database URL and engine kwargs
try:
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        logger.info("Using SQLite database")
    else:
        # PostgreSQL or other databases
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            echo=False
        )
        logger.info("Using PostgreSQL database")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    logger.error(f"Database URL (first 50 chars): {db_url[:50]}...")
    raise ValueError(f"Invalid database URL. Check your AUTH_DATABASE_URL in .env file. Error: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables and perform migrations."""
    try:
        Base.metadata.create_all(bind=engine)
        
        # Handle migration: Add full_name column to users table if it doesn't exist (for existing databases)
        try:
            if db_url.startswith("sqlite"):
                # SQLite migration
                with engine.begin() as conn:
                    # Check if full_name column exists
                    result = conn.execute(
                        text("SELECT name FROM pragma_table_info('users') WHERE name='full_name'")
                    ).fetchone()
                    
                    if not result:
                        logger.info("Adding 'full_name' column to users table...")
                        conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)"))
                        logger.info("Migration completed: full_name column added")
            else:
                # PostgreSQL migration
                with engine.begin() as conn:
                    # Check if column exists
                    result = conn.execute(
                        text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='full_name'")
                    ).fetchone()
                    
                    if not result:
                        logger.info("Adding 'full_name' column to users table...")
                        conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)"))
                        logger.info("Migration completed: full_name column added")
        except Exception as e:
            # Migration errors are non-fatal - column might already exist or table might be new
            logger.debug(f"Migration check completed: {e}")
            pass
        
        # gmail_connections table is created automatically by Base.metadata.create_all()
        logger.info("Database tables initialized successfully (users, refresh_tokens, gmail_connections)")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db() -> Session:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
