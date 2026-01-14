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

# Mask password in log for security
log_url = db_url
if '@' in db_url:
    # Hide password in logs: postgresql://user:***@host:port/db
    parts = db_url.split('@')
    if len(parts) == 2:
        user_pass = parts[0].split('://')
        if len(user_pass) == 2:
            protocol = user_pass[0]
            user_part = user_pass[1]
            if ':' in user_part:
                user = user_part.split(':')[0]
                log_url = f"{protocol}://{user}:***@{parts[1]}"

logger.info(f"Initializing database connection: {log_url}")

# Determine database URL and engine kwargs
try:
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        logger.info("✅ Using SQLite database")
    else:
        # PostgreSQL or other databases
        engine = create_engine(
            db_url,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,
            pool_recycle=3600,  # Recycle connections after 1 hour
            connect_args={
                "connect_timeout": 10,  # 10 second connection timeout
                "sslmode": "require"  # Require SSL for Supabase
            } if "supabase.co" in db_url else {}
        )
        logger.info("✅ Using PostgreSQL database")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    logger.error(f"Database URL (first 50 chars): {log_url[:50]}...")
    raise ValueError(f"Invalid database URL. Check your AUTH_DATABASE_URL in .env file. Error: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables and perform migrations."""
    try:
        # Test connection first
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as conn_error:
            error_str = str(conn_error).lower()
            if 'could not translate host name' in error_str or 'name or service not known' in error_str:
                logger.error(f"❌ Cannot connect to database: {conn_error}")
                logger.error("")
                logger.error("=" * 60)
                logger.error("TROUBLESHOOTING SUPABASE CONNECTION:")
                logger.error("=" * 60)
                logger.error("1. Check if your Supabase project is ACTIVE:")
                logger.error("   → Go to https://supabase.com/dashboard")
                logger.error("   → Check if project is paused (free tier pauses after inactivity)")
                logger.error("   → If paused, click 'Restore' to reactivate")
                logger.error("")
                logger.error("2. Verify the connection string:")
                logger.error("   → Go to Settings → Database → Connection string")
                logger.error("   → Copy the URI format (not Session mode)")
                logger.error("   → Make sure password is URL-encoded (% → %25)")
                logger.error("")
                logger.error("3. Try using Connection Pooler URL instead:")
                logger.error("   → Use port 6543 (pooler) instead of 5432 (direct)")
                logger.error("   → Format: postgresql://postgres:PASSWORD@db.xxx.supabase.co:6543/postgres")
                logger.error("")
                logger.error("4. Network/DNS issues:")
                logger.error("   → Check your internet connection")
                logger.error("   → Try: ipconfig /flushdns (Windows)")
                logger.error("   → Check if firewall blocks port 5432")
                logger.error("")
                logger.error("5. Temporary workaround - Use SQLite for local dev:")
                logger.error("   → Set AUTH_DATABASE_URL=sqlite:///./auth.db in .env")
                logger.error("=" * 60)
                logger.error("")
                raise  # Re-raise connection errors so startup can handle them
            raise  # Re-raise other connection errors
        
        # Connection successful, proceed with initialization
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
        logger.info("✅ Database tables initialized successfully (users, refresh_tokens, gmail_connections)")
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
