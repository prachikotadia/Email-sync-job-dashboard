from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, ForeignKey, JSON, Table
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import uuid
from datetime import datetime

Base = declarative_base()

# Many-to-Many link if strictly needed, though Resume ID in Application is often enough 1:N
application_resumes = Table(
    'application_resumes', Base.metadata,
    Column('application_id', UUID(as_uuid=True), ForeignKey('applications.id')),
    Column('resume_id', UUID(as_uuid=True), ForeignKey('resumes.id'))
)

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    applications = relationship("Application", back_populates="user")
    resumes = relationship("Resume", back_populates="user")

class Company(Base):
    __tablename__ = "companies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    roles = relationship("Role", back_populates="company")
    applications = relationship("Application", back_populates="company")

class Role(Base):
    __tablename__ = "roles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="roles")
    applications = relationship("Application", back_populates="role")

class Resume(Base):
    __tablename__ = "resumes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    file_name = Column(String, nullable=False)
    storage_url = Column(String, nullable=False)
    tags = Column(JSON, default=[])  # JSON for SQLite compatibility, can store array as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="resumes")
    # Relation to applications via many-to-many or logic direct link
    used_in_applications = relationship("Application", secondary=application_resumes, back_populates="resume_history")

class Application(Base):
    __tablename__ = "applications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    
    status = Column(String, default="Applied", index=True)
    status_confidence = Column(Float, default=0.0)
    applied_count = Column(Integer, default=1)
    last_email_date = Column(DateTime, index=True)
    ghosted = Column(Boolean, default=False, index=True)
    
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True) # Current active resume
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="applications")
    company = relationship("Company", back_populates="applications")
    role = relationship("Role", back_populates="applications")
    status_history = relationship("StatusHistory", back_populates="application")
    emails = relationship("Email", back_populates="application", order_by="Email.received_at")
    events = relationship("ApplicationEvent", back_populates="application", order_by="ApplicationEvent.event_date")
    
    # Just for basic access to current resume
    resume = relationship("Resume") 
    
    # History of resumes used
    resume_history = relationship("Resume", secondary=application_resumes, back_populates="used_in_applications")

class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    status = Column(String, nullable=False)
    previous_status = Column(String, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("Application", back_populates="status_history")

class Email(Base):
    """RULE 8: Store all job-related emails."""
    __tablename__ = "emails"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True)
    gmail_message_id = Column(String, unique=True, nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    from_email = Column(String, nullable=False)
    to_email = Column(String, nullable=True)
    body_text = Column(String, nullable=True)
    received_at = Column(DateTime, nullable=False, index=True)
    internal_date = Column(Integer, nullable=True)  # Gmail internal date (milliseconds)
    status = Column(String, nullable=False)  # APPLIED, REJECTED, INTERVIEW, etc.
    confidence_score = Column(Float, default=0.0)
    company_name = Column(String, nullable=True)
    role_title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    application = relationship("Application", back_populates="emails")

class ApplicationEvent(Base):
    """RULE 8: Timeline of events per application."""
    __tablename__ = "application_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=True)
    event_type = Column(String, nullable=False)  # APPLIED, REJECTED, INTERVIEW, etc.
    event_date = Column(DateTime, nullable=False, index=True)
    confidence_score = Column(Float, default=0.0)
    metadata = Column(JSON, nullable=True)  # Additional event data
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("Application", back_populates="events")
    email = relationship("Email")

class GmailAccount(Base):
    """RULE 9: Multi-user Gmail account support."""
    __tablename__ = "gmail_accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    gmail_email = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)
    last_message_internal_date = Column(Integer, nullable=True)  # For incremental sync
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
