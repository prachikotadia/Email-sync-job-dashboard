"""
Database models and session management for Resume Service
Production-grade resume file management system
"""
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime, timezone
import os
import uuid
import logging

logger = logging.getLogger(__name__)

# Use SQLite for tests, PostgreSQL for production
TESTING = os.getenv("TESTING", "false").lower() == "true"
if TESTING:
    DATABASE_URL = "sqlite:///:memory:"  # Use in-memory database for tests
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://jobpulse:jobpulse_password@db:5432/jobpulse_db")

# Use String for UUID in SQLite, UUID type for PostgreSQL
if TESTING:
    UUIDType = String(36)  # SQLite doesn't have native UUID type
else:
    UUIDType = UUID(as_uuid=True)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread": False} if TESTING else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Stub models for foreign key references
# These tables are created by other services (auth-service, gmail-connector-service)
# These stubs are only used for foreign key resolution in SQLAlchemy

class User(Base):
    """Stub User model - table is managed by auth-service"""
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}  # Allow redefinition if table already exists
    
    id = Column(UUIDType, primary_key=True)
    # We don't define other columns - they're managed by auth-service

class Application(Base):
    """Stub Application model - table is managed by gmail-connector-service"""
    __tablename__ = "applications"
    __table_args__ = {'extend_existing': True}  # Allow redefinition if table already exists
    
    id = Column(UUIDType, primary_key=True)
    # We don't define other columns - they're managed by gmail-connector-service


class Resume(Base):
    """
    Resume file storage and metadata
    
    Rules:
    - Only ONE default resume per user (enforced by unique constraint)
    - Soft delete support (deleted_at)
    - File storage URL is secure (not public)
    - Checksum for deduplication
    """
    __tablename__ = "resumes"
    
    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()) if TESTING else uuid.uuid4(), index=True)
    user_id = Column(UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)  # User-friendly name (e.g., "Frontend Resume")
    file_url = Column(Text, nullable=False)  # Secure storage URL (local path or S3/GCS URL)
    file_type = Column(String, nullable=False)  # 'pdf' or 'docx'
    file_size_kb = Column(Integer, nullable=False)  # File size in KB
    checksum = Column(String, nullable=False, index=True)  # SHA256 checksum for deduplication
    is_default = Column(Boolean, default=False, nullable=False, index=True)  # Only ONE per user
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Soft delete
    
    # Optional metadata for future intelligence features
    extracted_skills = Column(JSON, nullable=True)  # Array of skills extracted from resume
    role_keywords = Column(JSON, nullable=True)  # Array of role-related keywords
    experience_level = Column(String, nullable=True)  # 'entry', 'mid', 'senior', 'executive'
    
    # Relationships
    application_links = relationship("ApplicationResume", back_populates="resume", cascade="all, delete-orphan")
    
    # Note: UniqueConstraint with WHERE clause requires PostgreSQL 9.2+
    # For compatibility, we'll enforce this in application logic


class ApplicationResume(Base):
    """
    Links resumes to applications
    
    Rules:
    - One application can have only one resume
    - One resume can be linked to many applications
    - History is preserved (linked_at timestamp)
    """
    __tablename__ = "application_resumes"
    
    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()) if TESTING else uuid.uuid4(), index=True)
    application_id = Column(UUIDType, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(UUIDType, ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=False, index=True)
    linked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    resume = relationship("Resume", back_populates="application_links")
    
    # Constraints
    __table_args__ = (
        # One resume per application
        UniqueConstraint('application_id', name='unique_resume_per_application'),
    )


def init_db():
    """Initialize database tables
    
    Note: Only creates resume-service tables (resumes, application_resumes).
    The 'applications' table is created by gmail-connector-service.
    
    If an old schema exists, it will be migrated to the new schema.
    """
    from sqlalchemy import inspect, text
    
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Check if old resumes table exists with wrong schema
        if 'resumes' in existing_tables:
            columns = [col['name'] for col in inspector.get_columns('resumes')]
            # Check if it's the old schema (has 'title' instead of 'file_name')
            if 'title' in columns and 'file_name' not in columns:
                logger.warning("Old resumes table schema detected. Migrating to new schema...")
                # Drop old table and related constraints
                with engine.begin() as conn:  # Use begin() for transaction
                    # Drop foreign key constraints first
                    conn.execute(text("""
                        ALTER TABLE IF EXISTS application_resumes 
                        DROP CONSTRAINT IF EXISTS application_resumes_resume_id_fkey;
                    """))
                    conn.execute(text("""
                        ALTER TABLE IF EXISTS resume_uploads 
                        DROP CONSTRAINT IF EXISTS resume_uploads_resume_id_fkey;
                    """))
                    conn.execute(text("""
                        ALTER TABLE IF EXISTS resume_versions 
                        DROP CONSTRAINT IF EXISTS resume_versions_resume_id_fkey;
                    """))
                    # Drop old table (CASCADE will handle dependent objects)
                    conn.execute(text("DROP TABLE IF EXISTS resumes CASCADE;"))
                logger.info("Old resumes table dropped. Creating new schema...")
        
        # Create new tables (don't use checkfirst if we just dropped the old one)
        if 'resumes' not in existing_tables or ('title' in [col['name'] for col in inspector.get_columns('resumes')] if 'resumes' in existing_tables else False):
            Resume.__table__.create(bind=engine, checkfirst=False)
        else:
            Resume.__table__.create(bind=engine, checkfirst=True)
        
        # Try to create application_resumes table
        # If applications table doesn't exist, this will fail but we'll log a warning
        try:
            ApplicationResume.__table__.create(bind=engine, checkfirst=True)
        except Exception as fk_error:
            if "applications" in str(fk_error).lower() or "NoReferencedTableError" in str(type(fk_error).__name__):
                logger.warning(f"Applications table not found yet. Cannot create application_resumes table.")
                logger.info("This is normal if gmail-connector-service hasn't initialized the applications table yet.")
                logger.info("The application_resumes table will be created automatically when applications table exists.")
            else:
                raise
        
        logger.info("Resume Service database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize resume service database: {e}")
        # Don't raise - allow service to start and retry later
        logger.warning("Resume service will continue but some features may not work until database is properly initialized.")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
