"""
Database session for storing Gmail OAuth tokens.
We'll use auth-service database or a separate database for tokens.
For simplicity, we'll store tokens via API calls to auth-service.
"""
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool
from datetime import datetime
import uuid

Base = declarative_base()


class GmailToken(Base):
    """Local cache of Gmail tokens (optional - can use auth-service instead)."""
    __tablename__ = "gmail_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, unique=True, index=True)
    tokens_json = Column(String(2000), nullable=False)  # Encrypted OAuth tokens
    gmail_email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# For now, we'll use auth-service API to store tokens
# This is a placeholder if we want local storage later
_db_engine = None
SessionLocal = None


def init_db():
    """Initialize database (optional - using auth-service for token storage)."""
    pass  # Using auth-service API for token storage