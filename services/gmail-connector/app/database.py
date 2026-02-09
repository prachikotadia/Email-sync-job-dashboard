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

# Category ENUM - strict 6 categories, uppercase (includes WITHDRAWN)
class ApplicationCategory(enum.Enum):
    ACTIVE = "ACTIVE"  # Renamed from APPLIED for clarity
    REJECTED = "REJECTED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"  # Renamed from OFFER_ACCEPTED
    GHOSTED = "GHOSTED"
    WITHDRAWN = "WITHDRAWN"

# Classification source ENUM
class ClassificationSource(enum.Enum):
    RULE = "RULE"  # Rule-based classification
    LLM = "LLM"  # LLM-based classification
    FILTERED = "FILTERED"  # Filtered out (promotions, etc.)
    THREAD_CONTEXT = "THREAD_CONTEXT"  # Classified based on thread history

# Profile Link Type ENUM
class ProfileLinkType(enum.Enum):
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    CUSTOM = "custom"

class ProfileLinkType(enum.Enum):
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    CUSTOM = "custom"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    sync_state = relationship("SyncState", back_populates="user", uselist=False, cascade="all, delete-orphan")
    oauth_tokens = relationship("OAuthToken", back_populates="user", uselist=False, cascade="all, delete-orphan")
    profile_links = relationship("ProfileLink", back_populates="user", cascade="all, delete-orphan")
    profile_links = relationship("ProfileLink", back_populates="user", cascade="all, delete-orphan")

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
    company_name = Column(Text, nullable=False, index=True)  # Must never be null - canonical normalized name
    company_slug = Column(String, index=True)  # Lowercase, normalized slug for URL routing and deduplication
    company_domain = Column(Text, index=True)  # Company domain for normalization
    company_source = Column(String, nullable=True)  # Resolution source: FROM_NAME, ROOT_DOMAIN, GREENHOUSE_URL, etc.
    company_confidence = Column(String, nullable=True)  # Resolution confidence 0.0-1.0 (stored as string)
    company_debug = Column(JSON, nullable=True)  # Debug trail for company resolution (list of strings)
    company_aliases = Column(JSON, nullable=True)  # Array of company aliases (e.g., ["Facebook", "Meta Platforms"] for "Meta")
    role = Column(String)  # role_title equivalent
    application_name = Column(Text)  # Derived from email subject + company + role for search
    category = Column(String, nullable=False, index=True)  # ACTIVE, REJECTED, INTERVIEW, OFFER, GHOSTED, WITHDRAWN (uppercase)
    subject = Column(Text, nullable=False)  # NOT NULL
    snippet = Column(Text)
    from_email = Column(String)
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)  # applied_at equivalent
    last_activity_at = Column(DateTime(timezone=True), index=True)  # Last activity timestamp (updates on status change)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    # source_email_permalink: Use gmail_web_url field (already exists)
    
    # Classification traceability fields (NON-NEGOTIABLE)
    classification_source = Column(String, nullable=True, index=True)  # RULE, LLM, FILTERED, THREAD_CONTEXT
    rule_name = Column(String, nullable=True)  # Name of the rule that matched (e.g., "rejected_keywords", "interview_keywords")
    llm_reason = Column(Text, nullable=True)  # LLM explanation for classification
    classification_confidence = Column(String, nullable=True)  # Confidence score 0.0-1.0 (stored as string for flexibility)
    classified_at = Column(DateTime(timezone=True), nullable=True, index=True)  # When classification was performed
    # Enhanced traceability (9-layer pipeline)
    signals_used = Column(JSON, nullable=True)  # List of signals used: ["calendar_invite", "sender_intelligence", etc.]
    rules_triggered = Column(JSON, nullable=True)  # List of rules triggered: ["REJECTED_RULE_1.0", "INTERVIEW_RULE_1.0"]
    classification_version = Column(String, nullable=True)  # Rule version (e.g., "1.0")
    
    # STEP 10: Additional classification fields for ONNX integration
    raw_label = Column(String, nullable=True)  # Raw HF model label (e.g., "confirmation", "interview", "rejection")
    model_name = Column(String, nullable=True)  # Model name (e.g., "job_email_classifier_v1")
    decision_path = Column(JSON, nullable=True)  # Decision path array: ["passed_ignore_filter", "hf_model:interview:0.91", "saved"]
    needs_review = Column(Boolean, default=False, nullable=False, index=True)  # Flag for manual review
    
    # Email Firewall fields (pre-classification filtering)
    firewall_decision = Column(String, nullable=True, index=True)  # ALLOW or DENY
    firewall_category = Column(String, nullable=True)  # NON_JOB_AUTH, NON_JOB_PROMO, NON_JOB_SUPPORT, NON_JOB_BILLING, NON_JOB_DEPLOY, UNKNOWN, JOB
    firewall_reason = Column(Text, nullable=True)  # Human-readable reason for firewall decision
    firewall_matched_rules = Column(JSON, nullable=True)  # List of matched rule IDs: ["domain_exact:render.com", "keyword:otp"]
    is_job_email = Column(Boolean, nullable=True, index=True)  # Derived from firewall_decision (True if ALLOW, False if DENY)
    
    # Relationships
    user = relationship("User", back_populates="applications")
    classification_audit_logs = relationship("ClassificationAuditLog", back_populates="application", cascade="all, delete-orphan")

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

class ProfileLink(Base):
    __tablename__ = "profile_links"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(SQLEnum(ProfileLinkType, name="profile_link_type"), nullable=False, index=True)
    label = Column(String, nullable=True)  # Required for CUSTOM type, null for others
    url = Column(Text, nullable=False)  # Normalized URL with scheme (https://...)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="profile_links")

class ClassificationAuditLog(Base):
    """
    Audit log for classification changes (re-classification support).
    
    Tracks:
    - old_status -> new_status transitions
    - reason for re-classification
    - timestamp
    - source of classification (rule/LLM/manual)
    """
    __tablename__ = "classification_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String, nullable=True)  # Previous category (null for first classification)
    new_status = Column(String, nullable=False)  # New category
    reason = Column(Text, nullable=False)  # Explanation for the change
    classification_source = Column(String, nullable=False)  # RULE, LLM, MANUAL, THREAD_CONTEXT
    rule_name = Column(String, nullable=True)  # Rule name if source is RULE
    confidence = Column(String, nullable=True)  # Confidence score if available
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Relationships
    application = relationship("Application", back_populates="classification_audit_logs")

class SyncJobStatus(enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"  # Cancellation requested by user
    CANCELED = "CANCELED"  # Cancellation completed
    COMPLETED = "COMPLETED"
    DONE = "DONE"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_FOUND = "NOT_FOUND"

class SyncStateEnum(enum.Enum):
    """
    Formal sync state model for retry + resume support.
    
    Rules:
    - Only ONE active sync per user (states != IDLE and != COMPLETED and != FAILED_FATAL)
    - State must persist in DB
    - On crash → resume from last state
    """
    IDLE = "IDLE"                          # No active sync (initial/default state)
    QUEUED = "QUEUED"                      # Job queued, waiting for worker
    FETCHING_HEADERS = "FETCHING_HEADERS"  # Fetching message headers/list (pagination)
    FETCHING_BODIES = "FETCHING_BODIES"    # Fetching full message bodies
    CLASSIFYING = "CLASSIFYING"            # Classifying emails (rule-based + LLM)
    PERSISTING = "PERSISTING"              # Saving to database
    COMPLETED = "COMPLETED"                # Sync completed successfully
    FAILED_RETRYABLE = "FAILED_RETRYABLE"  # Failed but can retry (rate limits, network)
    FAILED_FATAL = "FAILED_FATAL"          # Failed permanently (auth revoked, invalid data)

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
    canceled_at = Column(DateTime(timezone=True), nullable=True)  # When job was canceled
    cancel_reason = Column(Text, nullable=True)  # Reason for cancellation (e.g., "Canceled by user")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    error_message = Column(Text, nullable=True)  # last_error_message
    error_code = Column(String, nullable=True)  # last_error_code (e.g., "REAUTH_REQUIRED", "RATE_LIMIT", etc.)
    expires_at = Column(DateTime(timezone=True), index=True)  # TTL safety - default 24 hours
    logs = Column(JSON, default=list)  # Store log entries as JSON array
    email_entries = Column(JSON, default=list)  # Store email entries as JSON array
    checkpoint = Column(JSON, nullable=True)  # Store pagination token, lastMessageInternalDate, etc.
    current_phase = Column(String, nullable=True)  # Legacy: progress phase for SSE events
    current_page = Column(Integer, default=0)  # Current pagination page
    sync_state = Column(SQLEnum(SyncStateEnum), nullable=False, default=SyncStateEnum.IDLE, index=True)  # Formal sync state for retry/resume
    
    # Progress event persistence
    last_event_json = Column(JSON, nullable=True)  # Last progress event for SSE reconnection
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)  # Last activity timestamp
    error_json = Column(JSON, nullable=True)  # Error details as JSON
    
    # Counts for progress tracking (can also be in JSON, but separate columns for easier querying)
    counts_listed = Column(Integer, default=0)
    counts_fetched = Column(Integer, default=0)
    counts_parsed = Column(Integer, default=0)
    counts_classified = Column(Integer, default=0)
    counts_saved = Column(Integer, default=0)
    counts_skipped = Column(Integer, default=0)
    counts_failed = Column(Integer, default=0)
    
    # Rate tracking
    rate_emails_per_sec = Column(Integer, default=0)
    rate_bytes_per_sec = Column(Integer, default=0)
    
    # Sync range: 3M, 6M, 12M, 16M, FULL
    sync_range = Column(String, nullable=True, index=True)  # Store range as string: "3M", "6M", "12M", "16M", "FULL"
    
    # Relationships
    user = relationship("User")

def init_db():
    """Initialize database tables with schema migration support"""
    try:
        # Enable pg_trgm extension for fuzzy search (if not already enabled)
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                logger.info("pg_trgm extension enabled for fuzzy search")
        except Exception as e:
            # Extension might already exist or user might not have permission
            logger.warning(f"Could not enable pg_trgm extension: {e}")
        
        # Refresh inspector first to check existing tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Migrate sync_jobs table FIRST (before creating tables) if it exists
        # This must run before any queries to avoid "column does not exist" errors
        # Migrate enum values for SyncJobStatus (add CANCEL_REQUESTED and CANCELED if missing)
        try:
            with engine.begin() as conn:
                # Check existing enum values
                result = conn.execute(text("SELECT unnest(enum_range(NULL::syncjobstatus))::text"))
                existing_enum_values = {row[0] for row in result}
                
                # Add CANCEL_REQUESTED if missing
                if 'CANCEL_REQUESTED' not in existing_enum_values:
                    try:
                        conn.execute(text("ALTER TYPE syncjobstatus ADD VALUE IF NOT EXISTS 'CANCEL_REQUESTED'"))
                        logger.info("Added CANCEL_REQUESTED to syncjobstatus enum")
                    except Exception as e:
                        # IF NOT EXISTS might not be supported in older PostgreSQL versions
                        # Try without it, ignore if already exists
                        if 'already exists' not in str(e).lower():
                            logger.warning(f"Could not add CANCEL_REQUESTED to enum: {e}")
                
                # Add CANCELED if missing
                if 'CANCELED' not in existing_enum_values:
                    try:
                        conn.execute(text("ALTER TYPE syncjobstatus ADD VALUE IF NOT EXISTS 'CANCELED'"))
                        logger.info("Added CANCELED to syncjobstatus enum")
                    except Exception as e:
                        if 'already exists' not in str(e).lower():
                            logger.warning(f"Could not add CANCELED to enum: {e}")
        except Exception as e:
            logger.warning(f"Could not migrate enum values: {e}")
        
        if 'sync_jobs' in tables:
            existing_columns = {col['name'] for col in inspector.get_columns('sync_jobs')}
            required_columns = {
                'processed_failed', 'error_code', 'checkpoint', 
                'finished_at', 'canceled_at', 'cancel_reason', 'current_phase', 'current_page',
                'last_event_json', 'last_heartbeat_at', 'error_json',
                'counts_listed', 'counts_fetched', 'counts_parsed',
                'counts_classified', 'counts_saved', 'counts_skipped', 'counts_failed',
                'rate_emails_per_sec', 'rate_bytes_per_sec', 'sync_state', 'sync_range'
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
                    if 'canceled_at' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP WITH TIME ZONE"))
                    if 'cancel_reason' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS cancel_reason TEXT"))
                    if 'current_phase' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS current_phase VARCHAR"))
                    if 'current_page' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS current_page INTEGER DEFAULT 0"))
                    # New columns for progress events and SSE
                    if 'last_event_json' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS last_event_json JSON"))
                    if 'last_heartbeat_at' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP WITH TIME ZONE"))
                    if 'error_json' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS error_json JSON"))
                    # Count columns
                    if 'counts_listed' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_listed INTEGER DEFAULT 0"))
                    if 'counts_fetched' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_fetched INTEGER DEFAULT 0"))
                    if 'counts_parsed' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_parsed INTEGER DEFAULT 0"))
                    if 'counts_classified' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_classified INTEGER DEFAULT 0"))
                    if 'counts_saved' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_saved INTEGER DEFAULT 0"))
                    if 'counts_skipped' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_skipped INTEGER DEFAULT 0"))
                    if 'counts_failed' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS counts_failed INTEGER DEFAULT 0"))
                    # Rate columns
                    if 'rate_emails_per_sec' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS rate_emails_per_sec INTEGER DEFAULT 0"))
                    if 'rate_bytes_per_sec' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS rate_bytes_per_sec INTEGER DEFAULT 0"))
                    # Sync state column (formal state model for retry/resume)
                    if 'sync_state' in missing_columns:
                        # Create enum type if it doesn't exist
                        conn.execute(text("""
                            DO $$ BEGIN
                                CREATE TYPE syncstateenum AS ENUM (
                                    'IDLE', 'QUEUED', 'FETCHING_HEADERS', 'FETCHING_BODIES',
                                    'CLASSIFYING', 'PERSISTING', 'COMPLETED', 'FAILED_RETRYABLE', 'FAILED_FATAL'
                                );
                            EXCEPTION
                                WHEN duplicate_object THEN null;
                            END $$;
                        """))
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS sync_state syncstateenum DEFAULT 'IDLE'"))
                    # Sync range column (3M, 6M, 12M, 16M, FULL)
                    if 'sync_range' in missing_columns:
                        conn.execute(text("ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS sync_range VARCHAR"))
                logger.info("sync_jobs table migration completed")
        
        # Migrate applications table - add new columns if missing
        if 'applications' in tables:
            existing_app_columns = {col['name'] for col in inspector.get_columns('applications')}
            missing_columns = []
            
            if 'company_aliases' not in existing_app_columns:
                missing_columns.append(('company_aliases', 'JSON'))
            if 'company_slug' not in existing_app_columns:
                missing_columns.append(('company_slug', 'VARCHAR'))
            if 'application_name' not in existing_app_columns:
                missing_columns.append(('application_name', 'TEXT'))
            if 'last_activity_at' not in existing_app_columns:
                missing_columns.append(('last_activity_at', 'TIMESTAMP WITH TIME ZONE'))
            
            # Classification traceability fields
            if 'classification_source' not in existing_app_columns:
                missing_columns.append(('classification_source', 'VARCHAR'))
            if 'rule_name' not in existing_app_columns:
                missing_columns.append(('rule_name', 'VARCHAR'))
            if 'llm_reason' not in existing_app_columns:
                missing_columns.append(('llm_reason', 'TEXT'))
            if 'classification_confidence' not in existing_app_columns:
                missing_columns.append(('classification_confidence', 'VARCHAR'))
            if 'classified_at' not in existing_app_columns:
                missing_columns.append(('classified_at', 'TIMESTAMP WITH TIME ZONE'))
            # Enhanced traceability (9-layer pipeline)
            if 'signals_used' not in existing_app_columns:
                missing_columns.append(('signals_used', 'JSON'))
            if 'rules_triggered' not in existing_app_columns:
                missing_columns.append(('rules_triggered', 'JSON'))
            if 'classification_version' not in existing_app_columns:
                missing_columns.append(('classification_version', 'VARCHAR'))
            
            # STEP 10: ONNX classification fields
            if 'raw_label' not in existing_app_columns:
                missing_columns.append(('raw_label', 'VARCHAR'))
            if 'model_name' not in existing_app_columns:
                missing_columns.append(('model_name', 'VARCHAR'))
            if 'decision_path' not in existing_app_columns:
                missing_columns.append(('decision_path', 'JSON'))
            if 'needs_review' not in existing_app_columns:
                missing_columns.append(('needs_review', 'BOOLEAN'))
            
            # Email Firewall fields
            if 'firewall_decision' not in existing_app_columns:
                missing_columns.append(('firewall_decision', 'VARCHAR'))
            if 'firewall_category' not in existing_app_columns:
                missing_columns.append(('firewall_category', 'VARCHAR'))
            if 'firewall_reason' not in existing_app_columns:
                missing_columns.append(('firewall_reason', 'TEXT'))
            if 'firewall_matched_rules' not in existing_app_columns:
                missing_columns.append(('firewall_matched_rules', 'JSON'))
            if 'is_job_email' not in existing_app_columns:
                missing_columns.append(('is_job_email', 'BOOLEAN'))
            # Company resolution fields (deterministic resolver)
            if 'company_source' not in existing_app_columns:
                missing_columns.append(('company_source', 'VARCHAR'))
            if 'company_confidence' not in existing_app_columns:
                missing_columns.append(('company_confidence', 'VARCHAR'))
            if 'company_debug' not in existing_app_columns:
                missing_columns.append(('company_debug', 'JSON'))
            
            if missing_columns:
                try:
                    with engine.begin() as conn:
                        for col_name, col_type in missing_columns:
                            if col_name == 'needs_review' or col_name == 'is_job_email':
                                # Special handling for boolean columns with default
                                conn.execute(text(f"ALTER TABLE applications ADD COLUMN IF NOT EXISTS {col_name} {col_type} DEFAULT false"))
                            else:
                                conn.execute(text(f"ALTER TABLE applications ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        logger.info(f"Added columns to applications table: {[c[0] for c in missing_columns]}")
                except Exception as e:
                    logger.warning(f"Could not add columns to applications table: {e}")
        
        # Create classification_audit_logs table if it doesn't exist
        if 'classification_audit_logs' not in tables:
            try:
                Base.metadata.create_all(bind=engine, tables=[ClassificationAuditLog.__table__])
                logger.info("Created classification_audit_logs table")
            except Exception as e:
                logger.warning(f"Could not create classification_audit_logs table: {e}")
        
        # Create search indexes for applications table (for fuzzy search)
        if 'applications' in tables:
            try:
                with engine.begin() as conn:
                    # Check if search index exists
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_search'
                    """))
                    if not result.fetchone():
                        # Create GIN index for full-text search using tsvector
                        conn.execute(text("""
                            CREATE INDEX idx_applications_search
                            ON applications
                            USING GIN (
                                to_tsvector(
                                    'english',
                                    coalesce(company_name, '') || ' ' ||
                                    coalesce(role, '') || ' ' ||
                                    coalesce(subject, '')
                                )
                            )
                        """))
                        logger.info("Created full-text search index on applications")
                    
                    # Create GIN index for trigram (fuzzy) search on company_name
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_company_trgm'
                    """))
                    if not result.fetchone():
                        conn.execute(text("""
                            CREATE INDEX idx_applications_company_trgm
                            ON applications
                            USING GIN (company_name gin_trgm_ops)
                        """))
                        logger.info("Created trigram index for fuzzy company search")
                    
                    # Create combined index for (status, received_at) for filter performance
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_category_received_at'
                    """))
                    if not result.fetchone():
                        conn.execute(text("""
                            CREATE INDEX idx_applications_category_received_at
                            ON applications (category, received_at DESC)
                        """))
                        logger.info("Created combined index for category and received_at")
                    
                    # Create index on company_slug if column exists
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_company_slug'
                    """))
                    if not result.fetchone():
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_applications_company_slug ON applications (company_slug)"))
                            logger.info("Created index on company_slug")
                        except Exception:
                            # Column might not exist yet, skip
                            pass
                    
                    # Create index on last_activity_at if column exists
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_last_activity_at'
                    """))
                    if not result.fetchone():
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_applications_last_activity_at ON applications (last_activity_at DESC)"))
                            logger.info("Created index on last_activity_at")
                        except Exception:
                            # Column might not exist yet, skip
                            pass
                    
                    # STEP 10: Create indexes for classification fields
                    # Index on (user_id, status) for filtering by status
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_user_status'
                    """))
                    if not result.fetchone():
                        try:
                            conn.execute(text("""
                                CREATE INDEX IF NOT EXISTS idx_applications_user_status 
                                ON applications (user_id, category)
                            """))
                            logger.info("Created index on (user_id, category)")
                        except Exception:
                            pass
                    
                    # Index on (user_id, classified_at) for time-based queries
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_user_classified_at'
                    """))
                    if not result.fetchone():
                        try:
                            conn.execute(text("""
                                CREATE INDEX IF NOT EXISTS idx_applications_user_classified_at 
                                ON applications (user_id, classified_at DESC)
                            """))
                            logger.info("Created index on (user_id, classified_at)")
                        except Exception:
                            pass
                    
                    # Index on (user_id, gmail_thread_id) for thread-based queries
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_user_thread'
                    """))
                    if not result.fetchone():
                        try:
                            conn.execute(text("""
                                CREATE INDEX IF NOT EXISTS idx_applications_user_thread 
                                ON applications (user_id, gmail_thread_id)
                            """))
                            logger.info("Created index on (user_id, gmail_thread_id)")
                        except Exception:
                            pass
                    
                    # Index on needs_review for filtering
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE tablename = 'applications' AND indexname = 'idx_applications_needs_review'
                    """))
                    if not result.fetchone():
                        try:
                            conn.execute(text("""
                                CREATE INDEX IF NOT EXISTS idx_applications_needs_review 
                                ON applications (needs_review) WHERE needs_review = true
                            """))
                            logger.info("Created partial index on needs_review")
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Could not create search indexes: {e}")
        
        # Now create all tables (this will create new tables but won't modify existing ones)
        # This must come AFTER migration to avoid column errors
        Base.metadata.create_all(bind=engine)
    
    except Exception as e:
        logger.error(f"Error during database initialization: {e}", exc_info=True)
        # Try to create tables anyway
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e2:
            logger.error(f"Error creating tables: {e2}", exc_info=True)
    
    # Refresh inspector after migration for users check
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
    except Exception as e:
        logger.error(f"Error inspecting database: {e}", exc_info=True)
        return
    
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
