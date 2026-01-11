from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    # Use String for cross-database compatibility (works with both SQLite and PostgreSQL)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)  # Full name of the user
    role = Column(String(50), nullable=False, default="viewer")  # "viewer" | "editor"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(512), unique=True, nullable=False, index=True)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="refresh_tokens")


class GmailConnection(Base):
    __tablename__ = "gmail_connections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    # Store encrypted OAuth tokens (access_token, refresh_token, etc.) as JSON
    tokens = Column(String(2000), nullable=False)  # JSON string with encrypted tokens
    gmail_email = Column(String(255), nullable=True, index=True)  # Connected Gmail account email
    is_active = Column(Boolean, default=True, nullable=False)
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    user = relationship("User", backref="gmail_connection")
