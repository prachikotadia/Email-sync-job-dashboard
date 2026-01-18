from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, inspect
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
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

def init_db():
    """Initialize database tables"""
    # Check if schema migration is needed (users.id should be UUID, not integer)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'users' in tables:
        # Check if users.id is integer (wrong) or UUID (correct)
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
            else:
                # Schema is correct, just ensure all tables exist
                Base.metadata.create_all(bind=engine)
        else:
            # Column doesn't exist, create tables
            Base.metadata.create_all(bind=engine)
    else:
        # Tables don't exist, create them
        Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
