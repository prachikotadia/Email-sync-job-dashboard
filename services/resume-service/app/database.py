"""
Database models and session management for Resume Service
"""
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import os
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://jobpulse:jobpulse_password@db:5432/jobpulse_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String, nullable=False, index=True)  # User email from JWT
    title = Column(String, nullable=False)
    summary = Column(Text)
    experience = Column(JSON, default=list)  # Array of experience objects
    education = Column(JSON, default=list)  # Array of education objects
    skills = Column(JSON, default=list)  # Array of strings
    projects = Column(JSON, default=list)  # Array of project objects
    certifications = Column(JSON, default=list)  # Array of certification objects
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationships
    versions = relationship("ResumeVersion", back_populates="resume", cascade="all, delete-orphan")
    uploads = relationship("ResumeUpload", back_populates="resume", cascade="all, delete-orphan")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False)  # Full resume state at this version
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    resume = relationship("Resume", back_populates="versions")


class ResumeUpload(Base):
    __tablename__ = "resume_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String, nullable=False, index=True)  # User email from JWT
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=True, index=True)
    file_type = Column(String, nullable=False)  # 'pdf' or 'docx'
    original_filename = Column(String, nullable=False)
    file_path = Column(String)  # Path to stored file (if storing files)
    parsed_content_json = Column(JSON)  # Parsed structured data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    resume = relationship("Resume", back_populates="uploads")


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
