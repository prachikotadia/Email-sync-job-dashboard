from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, inspect, JSON, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone, timedelta
import os
import uuid
import enum
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://jobpulse:jobpulse_password@db:5432/jobpulse_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Category ENUM - strict 5 categories, uppercase
class ApplicationCategory(enum.Enum):
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    INTERVIEW = "INTERVIEW"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    GHOSTED = "GHOSTED"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    sync_state = relationship("SyncState", back_populates="user", uselist=False, cascade="all, delete-orphan")
    oauth_tokens = relationship("OAuthToken", back_populates="user", uselist=False, cascade="all, delete-orphan")

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    access_token = Column(Text, nullable=False)  # Encrypted in production
    refresh_token = Column(Text)  # Encrypted in production
    token_uri = Column(String)
    client_id = Column(String)
    client_secret = Column(String)
    scopes = Column(Text)  # JSON array of scopes
    expires_at = Column(DateTime(timezone=True))  # When access_token expires (timezone-aware)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="oauth_tokens")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_message_id = Column(Text, unique=True, index=True, nullable=False)
    gmail_thread_id = Column(Text, nullable=False, index=True)  # NOT NULL
    gmail_web_url = Column(Text, nullable=False)  # NOT NULL
    company_name = Column(Text, nullable=False, index=True)  # Must never be null
    company_domain = Column(Text, index=True)  # Company domain for normalization
    role = Column(String)
    category = Column(String, nullable=False, index=True)  # APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED (uppercase)
    subject = Column(Text, nullable=False)  # NOT NULL
    snippet = Column(Text)
    from_email = Column(String)
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="applications")

class SyncState(Base):
    __tablename__ = "sync_states"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    gmail_history_id = Column(String, index=True)
    last_synced_at = Column(DateTime(timezone=True))
    is_sync_running = Column(Boolean, default=False, index=True)
    sync_lock_expires_at = Column(DateTime(timezone=True), index=True)
    lock_job_id = Column(String)
    
    # Relationships
    user = relationship("User", back_populates="sync_state")

class SyncJobStatus(enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DONE = "DONE"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_FOUND = "NOT_FOUND"

class SyncJob(Base):
    __tablename__ = "sync_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SQLEnum(SyncJobStatus), nullable=False, default=SyncJobStatus.PENDING, index=True)
    total_emails = Column(Integer, default=0)  # total_estimated
    processed_emails = Column(Integer, default=0)  # processed_ok
    processed_failed = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)  # When job completed/failed
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    error_message = Column(Text, nullable=True)  # last_error_message
    error_code = Column(String, nullable=True)  # last_error_code (e.g., "REAUTH_REQUIRED", "RATE_LIMIT", etc.)
    expires_at = Column(DateTime(timezone=True), index=True)  # TTL safety - default 24 hours
    logs = Column(JSON, default=list)  # Store log entries as JSON array
    email_entries = Column(JSON, default=list)  # Store email entries as JSON array
    checkpoint = Column(JSON, nullable=True)  # Store pagination token, lastMessageInternalDate, etc.
    current_phase = Column(String, nullable=True)  # e.g., "fetching_ids", "processing_messages", "completed"
    current_page = Column(Integer, default=0)  # Current pagination page
    
    # Relationships
    user = relationship("User")

def init_db():
    """Initialize database tables with schema migration support"""
    # Ensure all tables exist first
    Base.metadata.create_all(bind=engine)
    
    # Refresh inspector after table creation
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Migrate sync_jobs table if needed (add missing columns)
    if 'sync_jobs' in tables:
        existing_columns = {col['name'] for col in inspector.get_columns('sync_jobs')}
        required_columns = {
            'processed_failed', 'error_code', 'checkpoint', 
            'finished_at', 'current_phase', 'current_page'
        }
        missing_columns = required_columns - existing_columns
        
        if missing_columns:
            logger.info(f"Migrating sync_jobs table: adding columns {missing_columns}")
            with engine.begin() as conn:
                # Use ALTER TABLE to add missing columns
                if 'processed_failed' in missing_columns:
                    conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS processed_failed INTEGER DEFAULT 0"))
                if 'error_code' in missing_columns:
                    conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS error_code VARCHAR"))
                if 'checkpoint' in missing_columns:
                    conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS checkpoint JSON"))
                if 'finished_at' in missing_columns:
                    conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP WITH TIME ZONE"))
                if 'current_phase' in missing_columns:
                    conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS current_phase VARCHAR"))
                if 'current_page' in missing_columns:
                    conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS current_page INTEGER DEFAULT 0"))
            logger.info("sync_jobs table migration completed")
    
    # Check if schema migration is needed (users.id should be UUID, not integer)
    if 'users' in tables:
        columns = inspector.get_columns('users')
        users_id_col = next((col for col in columns if col['name'] == 'id'), None)
        
        if users_id_col:
            col_type = str(users_id_col['type']).upper()
            # Check if it's integer (wrong schema) - PostgreSQL integer types include INTEGER, INT, SERIAL, etc.
            if 'INT' in col_type and 'UUID' not in col_type:
                # Schema mismatch detected - drop and recreate (development only)
                # WARNING: This will delete all data!
                logger.warning("Schema mismatch detected: users.id is INTEGER but should be UUID. Dropping and recreating tables (development only).")
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)
                logger.info("Database schema migrated successfully")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
