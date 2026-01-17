from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://jobpulse:jobpulse_password@db:5432/jobpulse_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    sync_state = relationship("SyncState", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gmail_message_id = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=False, index=True)
    role = Column(String)
    category = Column(String, nullable=False, index=True)  # applied, rejected, interview, offer, accepted, ghosted
    subject = Column(Text)
    from_email = Column(String)
    received_at = Column(DateTime, nullable=False, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    snippet = Column(Text)
    
    # Relationships
    user = relationship("User", back_populates="applications")

class SyncState(Base):
    __tablename__ = "sync_states"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    gmail_history_id = Column(String, index=True)
    last_synced_at = Column(DateTime)
    is_sync_running = Column(Boolean, default=False, index=True)
    sync_lock_expires_at = Column(DateTime, index=True)
    lock_job_id = Column(String)
    
    # Relationships
    user = relationship("User", back_populates="sync_state")

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
