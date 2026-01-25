from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, asc, or_, Integer, cast, case
from app.gmail_client import GmailClient
from app.sync_engine import SyncEngine
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import get_db, init_db, engine, SessionLocal, User, Application, SyncState, OAuthToken, SyncJob, SyncJobStatus, ProfileLink, ProfileLinkType
from app.profile_link_validator import validate_url, normalize_url, detect_platform_from_url
from app.gmail_deep_link import build_gmail_deep_link
from app.search import search_applications, search_applications_fuzzy
from app.advanced_search import advanced_search_applications
from app.company_normalizer import normalize_company_name_for_grouping
from app.ghosted_detector import GhostedDetector
from app.export_service import generate_export
from app.services.classifier.schemas import EmailForClassification, ClassificationResult
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import uuid
import logging
import time
import httpx
import json
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_health_start = time.time()

app = FastAPI(title="Gmail Connector Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Database initialized")
    
    # Initialize RejectGate (fast rejection detection)
    try:
        from app.services.reject_gate import init_reject_gate
        init_reject_gate()
        logger.info("RejectGate initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize RejectGate: {e}. RejectGate disabled.")
    
    # Initialize ONNX classifier if enabled
    use_onnx = os.getenv("USE_ONNX_INFERENCE", "false").lower() == "true"
    if use_onnx:
        try:
            from app.services.classifier.hf_onnx_classifier import init_classifier
            
            # Get base directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_dir = os.path.join(base_dir, "models", "job_email")
            onnx_path = os.path.join(model_dir, "onnx", "model_quantized.onnx")
            
            # Allow override via environment variables
            model_dir = os.getenv("ONNX_MODEL_DIR", model_dir)
            onnx_path = os.getenv("ONNX_MODEL_PATH", onnx_path)
            
            if os.path.exists(onnx_path):
                init_classifier(model_dir=model_dir, onnx_path=onnx_path)
                logger.info("ONNX classifier initialized successfully")
            else:
                logger.warning(f"ONNX model not found at {onnx_path}. ONNX inference disabled.")
        except Exception as e:
            logger.warning(f"Failed to initialize ONNX classifier: {e}. ONNX inference disabled.")
    
    # Start scheduled job for ghosted detection (cron)
    _start_ghosted_detection_scheduler()

def _start_ghosted_detection_scheduler():
    """
    Start scheduled job for ghosted detection.
    
    Runs daily at 2 AM UTC to check for ghosted applications.
    Can be configured via GHOSTED_CHECK_SCHEDULE env var (cron format).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = BackgroundScheduler()
        
        # Get schedule from env (default: daily at 2 AM UTC)
        schedule = os.getenv("GHOSTED_CHECK_SCHEDULE", "0 2 * * *")  # Cron format: minute hour day month day_of_week
        
        # Parse cron schedule or use default
        if schedule and len(schedule.split()) == 5:
            parts = schedule.split()
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )
        else:
            # Default: daily at 2 AM UTC
            trigger = CronTrigger(hour=2, minute=0)
        
        def run_ghosted_check():
            """Scheduled task to check for ghosted applications."""
            db = SessionLocal()
            try:
                def gmail_client_factory(user_id, user_email, oauth_token):
                    """Factory to create GmailClient for thread checking."""
                    return GmailClient(user_id, user_email, oauth_token)
                
                count = ghosted_detector.check_all_users(db, gmail_client_factory)
                logger.info(f"Scheduled ghosted check completed. Marked {count} applications as GHOSTED")
            except Exception as e:
                logger.error(f"Error in scheduled ghosted check: {e}", exc_info=True)
            finally:
                db.close()
        
        scheduler.add_job(
            run_ghosted_check,
            trigger=trigger,
            id='ghosted_detection',
            name='Ghosted Detection Job',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info(f"Ghosted detection scheduler started. Schedule: {schedule}")
    except ImportError:
        logger.warning("APScheduler not available. Install with: pip install apscheduler. Scheduled ghosted detection disabled.")
    except Exception as e:
        logger.warning(f"Failed to start ghosted detection scheduler: {e}. Scheduled job disabled.")

# Initialize components
# Use hybrid classifier if enabled, otherwise fallback to basic classifier
use_hybrid_classifier = os.getenv("USE_HYBRID_CLASSIFIER", "true").lower() == "true"
try:
    if use_hybrid_classifier:
        from app.hybrid_classifier import HybridClassifier
        classifier = HybridClassifier()  # Will be initialized with db/gmail_client when needed
    else:
        from app.classifier import Classifier
        classifier = Classifier()
except ImportError:
    # Fallback to basic classifier if hybrid not available
    from app.classifier import Classifier
    classifier = Classifier()
    logger.warning("Hybrid classifier not available, using basic classifier")
company_extractor = CompanyExtractor()
ghosted_detector = GhostedDetector(days=int(os.getenv("GHOSTED_DAYS", "30")))

# In-memory sync jobs - REMOVED, using DB-only SyncJob model

class SyncStartRequest(BaseModel):
    user_id: str
    user_email: str  # Authenticated user email for validation
    range: str  # REQUIRED: "3M" | "6M" | "12M" | "16M" | "FULL"
    # Legacy fields (for backward compatibility, will be converted from range)
    mode: Optional[str] = None  # "full_history" or "time_range" (deprecated, use range)
    time_range_months: Optional[int] = None  # For time_range mode: 3, 6, 12, or 16 (deprecated, use range)

class ClearRequest(BaseModel):
    user_id: str

class OAuthTokenStoreRequest(BaseModel):
    user_email: str
    access_token: str
    refresh_token: Optional[str] = None
    token_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: Optional[list] = None
    expires_at: Optional[str] = None

class ExportRequest(BaseModel):
    format: str  # csv, xlsx, json, pdf
    category: str  # ALL, APPLIED, REJECTED, INTERVIEW, OFFER, GHOSTED
    dateRange: dict  # { "from": "YYYY-MM-DD" | null, "to": "YYYY-MM-DD" | null }
    fields: List[str]  # List of field names to include

@app.get("/status")
async def get_status(user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Get Gmail connection status
    Returns 503 ONLY if service is down
    """
    try:
        # Get user by email (user_id is email in JWT)
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {"connected": False, "error": "User not found"}
        
        # Check sync state
        sync_state = db.query(SyncState).filter(SyncState.user_id == user.id).first()
        
        # Check for active lock
        lock_info = None
        if sync_state and sync_state.is_sync_running:
            if sync_state.sync_lock_expires_at and sync_state.sync_lock_expires_at > datetime.now(timezone.utc):
                lock_info = {
                    "job_id": sync_state.lock_job_id,
                    "reason": "Sync in progress",
                }
            else:
                # Lock expired, clear it
                sync_state.is_sync_running = False
                sync_state.sync_lock_expires_at = None
                db.commit()
        
        return {
            "connected": True,
            "syncJobId": lock_info.get("job_id") if lock_info else None,
            "lockReason": lock_info.get("reason") if lock_info else None,
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        # Return 200 with error details (NOT 503)
        return {
            "connected": False,
            "error": f"Service error: {str(e)}",
            "syncJobId": None,
            "lockReason": None,
        }

@app.post("/sync/start")
async def start_sync(
    request: SyncStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start Gmail sync
    Returns 202 Accepted immediately with sync_id, sync runs in background
    If sync already RUNNING for user → return existing sync_id
    
    CRITICAL: This endpoint MUST return in < 200ms
    All long-running work is done in run_sync() background task
    """
    start_time = time.time()
    user_email = request.user_email
    
    # Validate user_id matches email (user_id is email in JWT)
    if request.user_id != user_email:
        raise HTTPException(status_code=401, detail="User ID does not match authenticated email")
    
    # Get or create user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(email=user_email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Check for existing active sync job (only ONE active sync per user)
    # Active states: QUEUED, FETCHING_HEADERS, FETCHING_BODIES, CLASSIFYING, PERSISTING
    # Non-active states: IDLE, COMPLETED, FAILED_RETRYABLE, FAILED_FATAL
    from app.database import SyncStateEnum
    active_states = [
        SyncStateEnum.QUEUED,
        SyncStateEnum.FETCHING_HEADERS,
        SyncStateEnum.FETCHING_BODIES,
        SyncStateEnum.CLASSIFYING,
        SyncStateEnum.PERSISTING
    ]
    
    existing_job = db.query(SyncJob).filter(
        SyncJob.user_id == user.id,
        SyncJob.sync_state.in_(active_states)
    ).first()
    
    if existing_job:
        # Sync already active - return existing sync_id
        sync_id = str(existing_job.id)
        logger.info(f"Sync already active for user {user_email} (state: {existing_job.sync_state.value}), returning existing sync_id: {sync_id}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"sync_id": sync_id, "status": "running", "state": existing_job.sync_state.value}
        )
    
    # Validate range parameter (REQUIRED)
    valid_ranges = {"3M", "6M", "12M", "16M", "FULL"}
    sync_range = request.range.upper() if request.range else None
    
    if not sync_range or sync_range not in valid_ranges:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range. Must be one of: {', '.join(sorted(valid_ranges))}"
        )
    
    # Convert range to mode/time_range_months for backward compatibility
    if sync_range == "FULL":
        mode = "full_history"
        time_range_months = None
    else:
        mode = "time_range"
        # Extract months from range (e.g., "3M" -> 3)
        time_range_months = int(sync_range.rstrip("M"))
    
    # Create new SyncJob in DB with PENDING status
    job_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)  # 24 hour TTL
    
    # Store mode and time_range_months in checkpoint JSON (for backward compatibility)
    checkpoint_data = {
        "mode": mode,
        "time_range_months": time_range_months,
        "last_message_index": None  # Will be updated during sync
    }
    
    from app.database import SyncStateEnum
    
    sync_job = SyncJob(
        id=job_id,
        user_id=user.id,
        status=SyncJobStatus.PENDING,
        sync_state=SyncStateEnum.QUEUED,  # Start in QUEUED state
        sync_range=sync_range,  # Store range: 3M, 6M, 12M, 16M, FULL
        total_emails=0,
        processed_emails=0,
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        logs=[],
        email_entries=[],
        checkpoint=checkpoint_data
    )
    db.add(sync_job)
    
    # Update SyncState lock
    sync_state = db.query(SyncState).filter(SyncState.user_id == user.id).first()
    if not sync_state:
        sync_state = SyncState(user_id=user.id)
        db.add(sync_state)
    
    sync_state.is_sync_running = True
    sync_state.sync_lock_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    sync_state.lock_job_id = str(job_id)
    
    db.commit()
    
    # Enqueue sync job to RQ worker queue
    enqueued = False  # Default to False (will use async task fallback)
    try:
        from app.queue import enqueue_sync_job
        enqueued = enqueue_sync_job(str(job_id), str(user.id), user_email)
        
        if not enqueued:
            # Failed to enqueue - fallback to async task (backward compatibility)
            logger.warning(f"Failed to enqueue job {job_id}, falling back to async task")
            # Use run_sync_with_progress to ensure events are published
            from app.worker import run_sync_with_progress
            task = asyncio.create_task(run_sync_with_progress(job_id, user.id, user_email))
            logger.info(f"Sync job {job_id} started as async task (fallback mode)")
        else:
            logger.info(f"Sync job {job_id} enqueued successfully")
    except Exception as e:
        # If queue system fails, fallback to async task
        logger.error(f"Queue system error, falling back to async task: {e}", exc_info=True)
        # Use run_sync_with_progress to ensure events are published
        from app.worker import run_sync_with_progress
        task = asyncio.create_task(run_sync_with_progress(job_id, user.id, user_email))
        logger.info(f"Sync job {job_id} started as async task (fallback mode)")
    
    # Log response time to verify endpoint returns quickly
    response_time_ms = (time.time() - start_time) * 1000
    
    # Determine status based on whether job was enqueued or started as async task
    job_status = "queued" if enqueued else "pending"
    logger.info(f"Sync job {job_id} created in {response_time_ms:.1f}ms (status: {job_status})")
    
    # Return 202 Accepted immediately - sync runs in worker or async task
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"sync_id": str(job_id), "status": job_status}
    )

def add_log(db: Session, job_id: uuid.UUID, message: str, log_type: str = "info"):
    """Add a log entry to the sync job in DB"""
    try:
        sync_job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not sync_job:
            return
        
        log_entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "type": log_type  # info, success, warning, error
        }
        
        logs = sync_job.logs or []
        logs.append(log_entry)
        # Keep only last 1000 log entries
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        sync_job.logs = logs
        sync_job.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"Error adding log to sync job {job_id}: {e}")
        db.rollback()

async def run_sync(job_id: uuid.UUID, user_id: int, user_email: str):
    """
    Run Gmail sync - fetches ALL emails, no limits. user_id=DB id, user_email for validation.
    Creates its own DB session - do NOT pass session from request context.
    
    This function runs as a background task and should NOT block the HTTP endpoint.
    All progress is persisted to SyncJob in DB after EVERY batch.
    All errors are caught and logged internally.
    """
    # Create new DB session for background task (request session will be closed)
    db = SessionLocal()
    sync_job = None
    try:
        # Get SyncJob from DB
        sync_job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not sync_job:
            logger.error(f"SyncJob {job_id} not found in DB")
            return
        
        # Update status to RUNNING
        sync_job.status = SyncJobStatus.RUNNING
        sync_job.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        add_log(db, job_id, "Starting Gmail sync...", "info")
        logger.info(f"Starting sync for user {user_id} (job {job_id})")
        
        # Get user's OAuth tokens from database
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
        if not oauth_token:
            error_msg = f"No OAuth tokens found for user {user_email}. Please re-authenticate."
            add_log(db, job_id, f"ERROR: {error_msg}", "error")
            raise Exception(f"REAUTH_REQUIRED: {error_msg}")
        
        # Check if token is expired and refresh if needed
        if oauth_token.expires_at:
            # Ensure expires_at is timezone-aware (handle both naive and aware datetimes)
            expires_at = oauth_token.expires_at
            if expires_at.tzinfo is None:
                # If naive, assume UTC
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                if not oauth_token.refresh_token:
                    error_msg = "Access token expired and no refresh token available. Please re-authenticate."
                    add_log(db, job_id, f"ERROR: {error_msg}", "error")
                    raise Exception(f"REAUTH_REQUIRED: {error_msg}")
        
        add_log(db, job_id, "Initializing Gmail client...", "info")
        # Initialize Gmail client with OAuth tokens
        try:
            gmail_client = GmailClient(user_id, user_email, oauth_token)
            # Attempt token refresh if needed (before first API call)
            try:
                gmail_client._refresh_token_if_needed()
                # Persist refreshed token to DB
                db.refresh(oauth_token)
                db.commit()
            except Exception as refresh_err:
                if "REAUTH_REQUIRED" in str(refresh_err):
                    raise
                # Non-fatal refresh error - continue with existing token
                logger.warning(f"Token refresh attempt failed (non-fatal): {refresh_err}")
            add_log(db, job_id, "Gmail client initialized successfully", "success")
            add_log(db, job_id, "Connected to Gmail API", "success")
        except Exception as init_err:
            if "REAUTH_REQUIRED" in str(init_err):
                raise
            raise Exception(f"Failed to initialize Gmail client: {str(init_err)}")
        
        # Validate email ownership
        add_log(db, job_id, "Validating email ownership...", "info")
        gmail_email = await gmail_client.get_user_email()
        if gmail_email.lower() != user_email.lower():
            error_msg = f"Gmail email ({gmail_email}) does not match authenticated user ({user_email})"
            logger.error(f"Email mismatch: {user_email} != {gmail_email}")
            add_log(db, job_id, f"ERROR: {error_msg}", "error")
            raise Exception(error_msg)
        add_log(db, job_id, f"Email validation successful: {gmail_email}", "success")
        
        # Initialize sync engine
        add_log(db, job_id, "Initializing sync engine...", "info")
        sync_engine = SyncEngine(gmail_client, classifier, company_extractor, db)
        
        # Get sync state
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if not sync_state:
            sync_state = SyncState(user_id=user_id)
            db.add(sync_state)
            db.commit()
        
        # Run sync - fetches ALL emails
        is_incremental = sync_state.gmail_history_id is not None
        if is_incremental:
            add_log(db, job_id, "Starting incremental sync (only new emails)...", "info")
            sync_job.current_phase = "fetching_incremental"
        else:
            add_log(db, job_id, "Starting full sync (scanning all emails)...", "info")
            sync_job.current_phase = "fetching_all"
        db.commit()
        
        last_logged_fetched = 0
        last_logged_scanned = 0
        last_logged_candidates = 0
        last_logged_classified = {}
        batch_count = 0
        
        async for progress in sync_engine.sync_all_emails(user_id, sync_state.gmail_history_id):
            total_scanned = progress.get("total_scanned", 0)
            total_fetched = progress.get("total_fetched", 0)
            candidate_job_emails = progress.get("candidate_job_emails", 0)
            processed_count = progress.get("processed_emails", total_fetched)
            
            # Add email entry to list if present (keep last 100 for UI performance)
            email_entry = progress.get("email_entry")
            if email_entry:
                email_entries = sync_job.email_entries or []
                email_entries.append(email_entry)
                # Keep only last 100 entries
                if len(email_entries) > 100:
                    email_entries = email_entries[-100:]
                sync_job.email_entries = email_entries
            
            # Update SyncJob in DB after EVERY batch (persist progress)
            sync_job.total_emails = total_scanned
            sync_job.processed_emails = processed_count
            sync_job.updated_at = datetime.now(timezone.utc)
            
            # Update current_phase based on progress
            if total_fetched == 0:
                sync_job.current_phase = "fetching_ids"
            elif candidate_job_emails > 0 and processed_count < candidate_job_emails:
                sync_job.current_phase = "classifying"
            else:
                sync_job.current_phase = "processing"
            
            batch_count += 1
            
            # Commit progress every 10 batches or at significant milestones
            if batch_count % 10 == 0 or total_fetched - last_logged_fetched >= 50:
                db.commit()
            
            # Log progress updates (throttled to avoid spam, but more frequent)
            if total_scanned > 0 and (total_scanned - last_logged_scanned) >= 20:
                add_log(db, job_id, f"Scanning Gmail: Found {total_scanned} total emails", "info")
                last_logged_scanned = total_scanned
            
            if total_fetched > 0 and (total_fetched - last_logged_fetched) >= 50:
                add_log(db, job_id, f"Fetched {total_fetched} emails for processing...", "info")
                last_logged_fetched = total_fetched
            
            if candidate_job_emails > 0 and (candidate_job_emails - last_logged_candidates) >= 20:
                add_log(db, job_id, f"Identified {candidate_job_emails} job-related emails", "info")
                last_logged_candidates = candidate_job_emails
            
            # Log classification progress
            classified_counts = progress.get("classified", {})
            for category in ["APPLIED", "REJECTED", "INTERVIEW", "OFFER_ACCEPTED", "GHOSTED"]:
                current_count = classified_counts.get(category, 0)
                last_count = last_logged_classified.get(category, 0)
                if current_count > 0 and (current_count - last_count) >= 10:
                    category_name = category.replace("_", "/")
                    add_log(db, job_id, f"Classified {current_count} as {category_name}", "success")
                    last_logged_classified[category] = current_count
        
        # Final progress log
        final_total_scanned = sync_job.total_emails
        final_total_fetched = sync_job.processed_emails
        
        if final_total_scanned > 0:
            add_log(db, job_id, f"Scanning complete: Found {final_total_scanned} total emails", "success")
        if final_total_fetched > 0:
            add_log(db, job_id, f"Fetched {final_total_fetched} emails for processing", "success")
        if candidate_job_emails > 0:
            add_log(db, job_id, f"Identified {candidate_job_emails} job-related emails", "success")
        
        # Update sync state
        sync_state.gmail_history_id = sync_engine.get_latest_history_id()
        sync_state.last_synced_at = datetime.now(timezone.utc)
        sync_state.is_sync_running = False
        sync_state.sync_lock_expires_at = None
        
        # Get final stats with uppercase categories (must be after DB commit)
        final_stats = calculate_stats(db, user_id)
        db.commit()
        
        # Log summary
        total_classified = sum(final_stats.values())
        add_log(db, job_id, f"Processing complete: {total_classified} applications created from {candidate_job_emails} job emails", "success")
        
        # Log classification results
        if final_stats.get("APPLIED", 0) > 0:
            add_log(db, job_id, f"✓ Classified {final_stats.get('APPLIED', 0)} as Applied", "success")
        if final_stats.get("REJECTED", 0) > 0:
            add_log(db, job_id, f"✓ Classified {final_stats.get('REJECTED', 0)} as Rejected", "success")
        if final_stats.get("INTERVIEW", 0) > 0:
            add_log(db, job_id, f"✓ Classified {final_stats.get('INTERVIEW', 0)} as Interview", "success")
        if final_stats.get("OFFER_ACCEPTED", 0) > 0:
            add_log(db, job_id, f"✓ Classified {final_stats.get('OFFER_ACCEPTED', 0)} as Offer/Accepted", "success")
        if final_stats.get("GHOSTED", 0) > 0:
            add_log(db, job_id, f"✓ Classified {final_stats.get('GHOSTED', 0)} as Ghosted", "success")
        
        skipped_count = final_total_scanned - final_total_fetched if final_total_scanned > final_total_fetched else 0
        if skipped_count > 0:
            add_log(db, job_id, f"Skipped {skipped_count} emails (not job applications)", "warning")
        
        # Mark as completed
        sync_job.status = SyncJobStatus.COMPLETED
        sync_job.finished_at = datetime.now(timezone.utc)
        sync_job.updated_at = datetime.now(timezone.utc)
        sync_job.current_phase = "completed"
        
        # Add final summary log
        total_stored = sum(final_stats.values())
        category_summary = ", ".join([
            f"{count} {cat.replace('_', '/')}" 
            for cat, count in final_stats.items() 
            if count > 0
        ])
        add_log(db, job_id, f"Sync completed! Stored {total_stored} job application emails ({category_summary}).", "success")
        add_log(db, job_id, f"Created/updated {total_stored} applications.", "success")
        add_log(db, job_id, "Updating sync timestamp...", "info")
        
        db.commit()
        
        logger.info(
            f"Job {job_id} completed: Fetched {final_total_fetched} emails. "
            f"Job-related candidates: {candidate_job_emails}. "
            f"APPLIED: {final_stats.get('APPLIED', 0)}, REJECTED: {final_stats.get('REJECTED', 0)}, "
            f"INTERVIEW: {final_stats.get('INTERVIEW', 0)}, OFFER_ACCEPTED: {final_stats.get('OFFER_ACCEPTED', 0)}, "
            f"GHOSTED: {final_stats.get('GHOSTED', 0)}. Skipped: {skipped_count}."
        )
        
    except Exception as e:
        error_msg = str(e)
        error_code = None
        
        # Determine error code
        error_str = error_msg.upper()
        if "REAUTH_REQUIRED" in error_str or "INVALID_GRANT" in error_str:
            error_code = "REAUTH_REQUIRED"
        elif "429" in error_str or "RATE_LIMIT" in error_str:
            error_code = "RATE_LIMIT"
        elif "TIMEOUT" in error_str:
            error_code = "TIMEOUT"
        else:
            error_code = "SYNC_ERROR"
        
        logger.error(f"Sync error for job {job_id} [{error_code}]: {e}", exc_info=True)
        
        # Update SyncJob status to FAILED
        if sync_job:
            try:
                sync_job.status = SyncJobStatus.FAILED
                sync_job.finished_at = datetime.now(timezone.utc)
                sync_job.error_message = error_msg
                sync_job.error_code = error_code
                sync_job.updated_at = datetime.now(timezone.utc)
                sync_job.current_phase = "failed"
                add_log(db, job_id, f"✗ ERROR [{error_code}]: {error_msg}", "error")
                db.commit()
            except Exception as db_err:
                logger.error(f"Error updating SyncJob status: {db_err}")
                db.rollback()
        
        # Release lock
        try:
            sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
            if sync_state:
                sync_state.is_sync_running = False
                sync_state.sync_lock_expires_at = None
                db.commit()
        except Exception as db_err:
            logger.error(f"Error releasing sync lock: {db_err}")
    finally:
        # Always close DB session
        try:
            db.close()
        except Exception:
            pass

@app.get("/sync/status")
async def get_sync_status(sync_id: str = Query(..., alias="sync_id"), user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Get sync status (for polling)
    ALWAYS returns 200 with JSON - NEVER returns 503 or 404
    Reads from DB only - NEVER calls Gmail API
    Returns real-time counts from backend
    Strict API contract format
    OPTIMIZED: Fast queries with minimal DB load
    """
    try:
        # Parse sync_id as UUID
        try:
            job_uuid = uuid.UUID(sync_id)
        except (ValueError, TypeError):
            # Invalid format - return 200 with NOT_FOUND state (NOT 404)
            return {
                "sync_id": sync_id,
                "status": "not_found",
                "state": "NOT_FOUND",
                "total_emails": 0,
                "processed_emails": 0,
                "progress_percentage": 0,
                "emails_fetched": 0,
                "applications_found": 0,
                "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0},
                "errors": ["Invalid sync_id format"],
                "logs": [],
                "email_entries": [],
                "last_error_code": None,
                "last_error_message": None,
                "eta_seconds": None,
            }
        
        # Get SyncJob from DB
        sync_job = db.query(SyncJob).filter(SyncJob.id == job_uuid).first()
        if not sync_job:
            # Job not found - return 200 with NOT_FOUND state (NOT 404)
            return {
                "sync_id": sync_id,
                "status": "not_found",
                "state": "NOT_FOUND",
                "total_emails": 0,
                "processed_emails": 0,
                "progress_percentage": 0,
                "emails_fetched": 0,
                "applications_found": 0,
                "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0},
                "errors": ["Sync job not found"],
                "logs": [],
                "email_entries": [],
                "last_error_code": None,
                "last_error_message": None,
                "eta_seconds": None,
            }
    
        # Validate user (user_id is email from JWT, get user from DB)
        user = db.query(User).filter(User.email == user_id).first()
        if not user or sync_job.user_id != user.id:
            # Unauthorized - return 200 with error (for status polling, 401 is too harsh)
            return {
                "sync_id": sync_id,
                "status": "unauthorized",
                "state": "FAILED",
                "total_emails": 0,
                "processed_emails": 0,
                "progress_percentage": 0,
                "emails_fetched": 0,
                "applications_found": 0,
                "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0},
                "errors": ["Unauthorized"],
                "logs": [],
                "email_entries": [],
                "last_error_code": "UNAUTHORIZED",
                "last_error_message": "Unauthorized",
                "eta_seconds": None,
            }
        
        # OPTIMIZED: Skip expensive DB queries - use lightweight approach for all states
        # Stats can be calculated separately or cached - don't block status endpoint
        # For both running AND completed jobs, use processed_emails to avoid slow GROUP BY queries
        app_count = sync_job.processed_emails  # Use processed count (accurate estimate)
        
        # Initialize empty stats - real counts available in separate endpoint or cached
        # This ensures /sync/status is always fast (<100ms)
        stats = {
            "APPLIED": 0,
            "REJECTED": 0,
            "INTERVIEW": 0,
            "OFFER_ACCEPTED": 0,
            "GHOSTED": 0,
        }
        
        # Map to contract format (lowercase for display, but backend uses uppercase)
        counts_display = {
            "applied": stats.get("APPLIED", 0),
            "rejected": stats.get("REJECTED", 0),
            "interview": stats.get("INTERVIEW", 0),
            "offer": stats.get("OFFER_ACCEPTED", 0),
            "ghosted": stats.get("GHOSTED", 0),
        }
        
        # Map status enum to string
        status_str = sync_job.status.value.lower()
        
        # Get email entries (reverse to show newest first, limit to 50 for performance)
        email_entries = list(reversed(sync_job.email_entries or []))[:50]
        
        # Calculate progress percentage
        progress_percentage = 0.0
        if sync_job.total_emails > 0:
            progress_percentage = (sync_job.processed_emails / sync_job.total_emails) * 100.0
        
        # Calculate ETA (simple estimate: messages_per_sec * remaining)
        eta_seconds = None
        if sync_job.status == SyncJobStatus.RUNNING and sync_job.started_at:
            elapsed = (datetime.now(timezone.utc) - sync_job.started_at).total_seconds()
            if elapsed > 0 and sync_job.processed_emails > 0:
                rate = sync_job.processed_emails / elapsed  # messages per second
                remaining = sync_job.total_emails - sync_job.processed_emails
                if rate > 0:
                    eta_seconds = int(remaining / rate)
        
        # Get last log lines (for UI display)
        last_log_lines = (sync_job.logs or [])[-200:]  # Last 200 log entries
        
        return {
            "sync_id": sync_id,
            "status": status_str,
            "state": sync_job.status.value,  # Uppercase enum value
            "total_emails": sync_job.total_emails,
            "processed_emails": sync_job.processed_emails,
            "processed_failed": getattr(sync_job, 'processed_failed', 0),
            "progress_percentage": round(progress_percentage, 2),
            "emails_fetched": sync_job.processed_emails,  # For backwards compatibility
            "applications_found": app_count,
            "counts": counts_display,
            "skipped": max(0, sync_job.total_emails - sync_job.processed_emails),
            "errors": [sync_job.error_message] if sync_job.error_message else [],
            "logs": last_log_lines,
            "last_log_lines": last_log_lines,  # Alias for clarity
            "email_entries": email_entries,  # Individual email entries (newest first, max 50)
            "started_at": sync_job.started_at.isoformat() if sync_job.started_at else None,
            "updated_at": sync_job.updated_at.isoformat() if sync_job.updated_at else None,
            "finished_at": sync_job.finished_at.isoformat() if sync_job.finished_at else None,
            "last_error_code": sync_job.error_code,
            "last_error_message": sync_job.error_message,
            "eta_seconds": eta_seconds,
            "current_phase": getattr(sync_job, 'current_phase', None),
            "current_page": getattr(sync_job, 'current_page', 0),
        }
    except Exception as e:
        # ANY exception should return 200 with error state (NEVER 500/503)
        logger.error(f"Error in get_sync_status: {e}", exc_info=True)
        return {
            "sync_id": sync_id,
            "status": "error",
            "state": "UNAVAILABLE",
            "total_emails": 0,
            "processed_emails": 0,
            "progress_percentage": 0,
            "emails_fetched": 0,
            "applications_found": 0,
            "counts": {"applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0},
            "errors": [f"Error retrieving sync status: {str(e)}"],
            "logs": [],
            "email_entries": [],
            "last_error_code": "INTERNAL_ERROR",
            "last_error_message": str(e),
            "eta_seconds": None,
    }

@app.get("/sync/progress/{job_id}")
async def get_sync_progress(job_id: str, user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Legacy endpoint - redirects to /sync/status
    """
    return await get_sync_status(sync_id=job_id, user_id=user_id, db=db)

@app.post("/sync/stop/{sync_id}")
async def stop_sync(sync_id: str, user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Cancel/stop a running sync job.
    
    This endpoint:
    - Validates sync_id and user ownership
    - Sets job status to CANCEL_REQUESTED (if not already COMPLETED/FAILED/CANCELED)
    - Persists immediately in DB
    - Returns immediately (does NOT wait for worker to stop)
    
    The worker will check this status and stop mid-sync.
    """
    try:
        # Parse sync_id as UUID
        try:
            job_uuid = uuid.UUID(sync_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=404, detail="Invalid sync_id format")
        
        # Get SyncJob from DB
        sync_job = db.query(SyncJob).filter(SyncJob.id == job_uuid).first()
        if not sync_job:
            raise HTTPException(status_code=404, detail="Sync job not found")
        
        # Validate user ownership
        user = db.query(User).filter(User.email == user_id).first()
        if not user or sync_job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized: job does not belong to user")
        
        # Check current status - if already COMPLETED, FAILED, or CANCELED, return current state
        if sync_job.status in [SyncJobStatus.COMPLETED, SyncJobStatus.FAILED, SyncJobStatus.CANCELED, SyncJobStatus.DONE]:
            return {
                "success": True,
                "status": sync_job.status.value,
                "message": f"Job is already {sync_job.status.value.lower()}"
            }
        
        # If already CANCEL_REQUESTED, return idempotently
        if sync_job.status == SyncJobStatus.CANCEL_REQUESTED:
            return {
                "success": True,
                "status": "CANCEL_REQUESTED",
                "message": "Cancellation already requested"
            }
        
        # Set status to CANCEL_REQUESTED and persist immediately
        sync_job.status = SyncJobStatus.CANCEL_REQUESTED
        sync_job.cancel_reason = "Canceled by user"
        sync_job.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        # Log cancellation request
        add_log(db, job_uuid, "Cancellation requested by user", "info")
        logger.info(f"Sync job {sync_id} cancellation requested by user {user_id}")
        
        return {
            "success": True,
            "status": "CANCEL_REQUESTED",
            "message": "Cancellation requested successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in stop_sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel sync: {str(e)}")

@app.get("/sync/logs/{job_id}")
async def get_sync_logs(
    job_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get structured logs for a sync job.
    
    Returns:
        {
            "job_id": "...",
            "logs": [
                {
                    "job_id": "...",
                    "level": "INFO | WARN | ERROR",
                    "event": "FETCH | RETRY | CLASSIFY | SAVE | CANCEL",
                    "details": "...",
                    "timestamp": "ISO-8601"
                }
            ]
        }
    """
    try:
        # Get user by email (user_id is email in JWT)
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get sync job
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job_id format")
        
        sync_job = db.query(SyncJob).filter(
            SyncJob.id == job_uuid,
            SyncJob.user_id == user.id
        ).first()
        
        if not sync_job:
            raise HTTPException(status_code=404, detail="Sync job not found")
        
        # Convert logs from JSON array to structured format
        logs = sync_job.logs or []
        structured_logs = []
        
        for log_entry in logs:
            # Log entry format: {"time": "...", "message": "...", "type": "info|warning|error"}
            log_type = log_entry.get("type", "info").upper()
            level_map = {
                "INFO": "INFO",
                "WARNING": "WARN",
                "WARN": "WARN",
                "ERROR": "ERROR",
                "SUCCESS": "INFO"
            }
            level = level_map.get(log_type, "INFO")
            
            # Determine event type from message
            message = log_entry.get("message", "")
            message_lower = message.lower()
            if "fetch" in message_lower or "email" in message_lower:
                event = "FETCH"
            elif "retry" in message_lower or "rate limit" in message_lower:
                event = "RETRY"
            elif "classif" in message_lower:
                event = "CLASSIFY"
            elif "save" in message_lower or "stored" in message_lower:
                event = "SAVE"
            elif "cancel" in message_lower:
                event = "CANCEL"
            else:
                event = "INFO"
            
            structured_logs.append({
                "job_id": job_id,
                "level": level,
                "event": event,
                "details": message,
                "timestamp": log_entry.get("time") or datetime.now(timezone.utc).isoformat()
            })
        
        return {
            "job_id": job_id,
            "logs": structured_logs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync logs: {str(e)}")

def calculate_stats(db: Session, user_id) -> dict:
    """
    Returns REAL counts from DB, never estimated.
    Categories: APPLIED (includes ACTIVE), REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED (uppercase).
    ACTIVE is mapped to APPLIED for dashboard compatibility (ACTIVE is the new classification system).
    Returns format: { "APPLIED": count, "REJECTED": count, ... }
    """
    # Query counts grouped by category
    from sqlalchemy import func
    results = db.query(
        Application.category,
        func.count(Application.id).label('count')
    ).filter(
        Application.user_id == user_id
    ).group_by(Application.category).all()
    
    # Initialize with zeros
    stats = {
        "APPLIED": 0,
        "REJECTED": 0,
        "INTERVIEW": 0,
        "OFFER_ACCEPTED": 0,
        "GHOSTED": 0,
    }
    
    # Map results (handle legacy lowercase categories and ACTIVE)
    for category, count in results:
        cat_upper = category.upper() if category else None
        if cat_upper == "OFFER" or cat_upper == "ACCEPTED":
            cat_upper = "OFFER_ACCEPTED"
        elif cat_upper == "ACTIVE":
            # ACTIVE is the new classification system - map to APPLIED for dashboard compatibility
            cat_upper = "APPLIED"
        
        if cat_upper in stats:
            stats[cat_upper] += count  # Use += to accumulate (ACTIVE + APPLIED both go to APPLIED)
    
    return stats

def _generate_gmail_web_url(message_id: str, user_email: str) -> str:
    """
    Generate Gmail web URL for a message (legacy wrapper)
    Uses build_gmail_deep_link for consistency.
    """
    return build_gmail_deep_link(message_id)


@app.get("/applications")
async def get_applications(
    user_id: str = Query(...),
    search: str = Query(None),
    status: str = Query(None),
    company: Optional[str] = Query(None, description="Filter by company name (exact match)"),
    db: Session = Depends(get_db)
):
    """
    Get all applications (flat list)
    NO pagination limits - returns ALL fetched emails
    Response includes gmail_web_url for opening emails
    
    Supports filtering by company name (exact match).
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {"applications": [], "total": 0, "counts": {}, "warning": None}
        
        query = db.query(Application).filter(Application.user_id == user.id)
        
        # Company filter (exact match - case-insensitive)
        if company:
            query = query.filter(func.lower(Application.company_name) == company.lower().strip())
        
        # Apply filters
        if search:
            search_lower = search.lower()
            query = query.filter(
                (Application.company_name.ilike(f"%{search_lower}%")) |
                (Application.role.ilike(f"%{search_lower}%"))
            )
        
        if status:
            # Status filter - convert to uppercase to match database
            status_upper = status.upper()
            if status_upper == "OFFER" or status_upper == "ACCEPTED":
                status_upper = "OFFER_ACCEPTED"
            elif status_upper == "APPLIED":
                # Map APPLIED to ACTIVE (dashboard compatibility - ACTIVE is the actual DB category)
                status_upper = "ACTIVE"
            query = query.filter(Application.category == status_upper)
        
        # Sort by received_at DESC (newest first) - serves as applied_at
        applications = query.order_by(Application.received_at.desc()).all()
        
        # Convert to dict with all required fields (strict API contract)
        apps_data = []
        for app in applications:
            # Category must be uppercase: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED
            category = app.category.upper() if app.category else "APPLIED"
            if category == "ACCEPTED" or category == "OFFER":
                category = "OFFER_ACCEPTED"
            elif category == "ACTIVE":
                # Map ACTIVE to APPLIED for frontend compatibility (dashboard shows ACTIVE as APPLIED)
                category = "APPLIED"
            elif category == "ACTIVE":
                # Map ACTIVE to APPLIED for frontend compatibility (dashboard shows ACTIVE as APPLIED)
                category = "APPLIED"
            
            # Generate Gmail deep link using message ID (single source of truth)
            if not app.gmail_message_id:
                logger.error(f"Application {app.id} missing gmail_message_id - cannot generate deep link")
                gmail_deep_link = None
                gmail_web_url = None  # Legacy field
            else:
                gmail_deep_link = build_gmail_deep_link(app.gmail_message_id)
                gmail_web_url = gmail_deep_link  # Legacy field for backward compatibility
            
            # Ensure gmail_thread_id is never null
            gmail_thread_id = app.gmail_thread_id if app.gmail_thread_id else app.gmail_message_id
            
            apps_data.append({
                "id": str(app.id),
                "company_name": app.company_name or "Unknown Company",  # Ensure never null
                "role_title": app.role,  # Role title (alias for 'role')
                "status": category,  # Uppercase: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED
                "category": category,  # Add category field for frontend compatibility
                "applied_at": app.received_at.isoformat() if app.received_at else None,  # received_at serves as applied_at
                "source": "GMAIL",  # All applications from this endpoint are Gmail-synced
                "email_message_id": app.gmail_message_id,
                "gmail_message_id": app.gmail_message_id,  # Explicit field for deep link
                "thread_id": app.gmail_thread_id,
                "subject": app.subject or "No Subject",  # Ensure never null
                "snippet": app.snippet,
                "received_at": app.received_at.isoformat() if app.received_at else None,
                "gmail_deep_link": gmail_deep_link,  # Primary field (new)
                "gmail_web_url": gmail_web_url,  # Legacy field (backward compatibility)
                "category": category,  # Keep for backward compatibility
            })
        
        # CRITICAL: Ensure API total matches actual DB count for verification
        # Use query.count() to get accurate total (handles filters correctly)
        total_count = query.count()
        
        return {
            "total": total_count,  # Use query count, not len(apps_data) - ensures accuracy with filters
            "applications": apps_data,
            "counts": calculate_stats(db, user.id)  # Include category counts for verification
        }
    except Exception as e:
        logger.error(f"Error getting applications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get applications: {str(e)}")


@app.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    user_id: str = Query(..., description="User email"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    fuzzy: bool = Query(False, description="Enable fuzzy/typo-tolerant search"),
    db: Session = Depends(get_db)
):
    """
    Production-grade global search endpoint.
    
    Searches across:
    - Company name (exact + partial + aliases)
    - Role / Job title
    - Email subject
    - Application status
    
    Ranking: Exact company > Partial company > Alias > Role > Subject > Status
    
    Performance: < 200ms response time, max 50 results per page (default).
    """
    try:
        # Get user by email
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        
        # Use fuzzy search if requested, otherwise use basic ranked search
        if fuzzy:
            result = search_applications_fuzzy(db, user.id, q, limit, offset)
        else:
            result = search_applications(db, user.id, q, limit, offset)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/applications/search")
async def search_applications_unified(
    user_id: str = Query(..., description="User email"),
    q: Optional[str] = Query(None, description="Global search query"),
    status: Optional[List[str]] = Query(None, description="Status filter (multi-select)"),
    company: Optional[str] = Query(None, description="Company filter (exact match)"),
    role: Optional[str] = Query(None, description="Role filter (partial match)"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: str = Query("received_at", description="Sort field: received_at, company_name, or last_activity_at"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db)
):
    """
    Advanced unified search endpoint with filters, pagination, and sorting.
    
    Searches across:
    - Company name (exact + partial + normalized)
    - Role / Job title
    - Application title (email subject)
    - Email subject
    - Sender email/domain
    
    Filters:
    - Status (multi-select)
    - Date range (date_from, date_to) - filters by received_at (applied_at equivalent)
    
    All logic is backend-driven for performance with large datasets.
    """
    try:
        # Get user by email
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {
                "data": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 0
                }
            }
        
        # Parse dates - only parse if not empty/None
        date_from_parsed = None
        date_to_parsed = None
        
        if date_from and date_from.strip():  # Check for empty strings
            try:
                date_from_parsed = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Invalid date_from format: {date_from}")
                date_from_parsed = None  # Don't filter if invalid
        
        if date_to and date_to.strip():  # Check for empty strings
            try:
                date_to_parsed = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Invalid date_to format: {date_to}")
                date_to_parsed = None  # Don't filter if invalid
        
        # Validate sort_by
        if sort_by not in ("received_at", "company_name", "last_activity_at"):
            sort_by = "received_at"
        
        # Validate sort_order
        if sort_order.lower() not in ("asc", "desc"):
            sort_order = "desc"
        
        # Call advanced search
        result = advanced_search_applications(
            db=db,
            user_id=user.id,
            query=q,
            status=status,
            company=company,
            role=role,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in advanced search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/applications/grouped-by-company")
async def get_applications_grouped_by_company(
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get applications grouped by company (summary only - no application details).
    
    Returns company summary with:
    - company_name (normalized canonical name)
    - total_applications count
    - status breakdown (counts per status)
    - latest_applied_at (most recent application date)
    
    Grouping is done in SQL for performance with large datasets.
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {"companies": []}
        
        # SQL GROUP BY with normalization for consistent grouping
        # Use company_name as-is (already normalized in extractor)
        # Group by company_name and aggregate status counts
        
        # Query: GROUP BY company_name, aggregate status counts, get latest received_at
        # Use CASE statements for status counting (more reliable than cast)
        result = db.query(
            Application.company_name,
            func.count(Application.id).label('total_applications'),
            func.max(Application.received_at).label('latest_applied_at'),
            # Count per status using CASE
            func.sum(case((func.lower(Application.category) == 'applied', 1), else_=0)).label('count_applied'),
            func.sum(case((func.lower(Application.category) == 'rejected', 1), else_=0)).label('count_rejected'),
            func.sum(case((func.lower(Application.category) == 'interview', 1), else_=0)).label('count_interview'),
            func.sum(case((func.lower(Application.category).in_(['offer_accepted', 'offer', 'accepted']), 1), else_=0)).label('count_offer'),
            func.sum(case((func.lower(Application.category) == 'ghosted', 1), else_=0)).label('count_ghosted'),
        ).filter(
            Application.user_id == user.id
        ).group_by(
            Application.company_name
        ).order_by(
            func.max(Application.received_at).desc()
        ).all()
        
        companies = []
        for row in result:
            company_name = row.company_name or "Unknown Company"
            
            # Build status counts dict
            statuses = {
                "APPLIED": int(row.count_applied or 0),
                "REJECTED": int(row.count_rejected or 0),
                "INTERVIEW": int(row.count_interview or 0),
                "OFFER_ACCEPTED": int(row.count_offer or 0),
                "GHOSTED": int(row.count_ghosted or 0),
            }
            
            companies.append({
                "company_name": company_name,
                "total_applications": int(row.total_applications),
                "statuses": statuses,
                "latest_applied_at": row.latest_applied_at.isoformat() if row.latest_applied_at else None,
            })
        
        return {"companies": companies}
        
    except Exception as e:
        logger.error(f"Error getting applications grouped by company: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get grouped applications: {str(e)}")


@app.get("/applications/company/{company_name}")
async def get_company_applications(
    company_name: str,
    user_id: str = Query(..., description="User email"),
    search: Optional[str] = Query(None, description="Search within company"),
    status: Optional[List[str]] = Query(None, description="Status filter (multi-select)"),
    sort_by: str = Query("received_at", description="Sort field: received_at or company_name"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    cursor: Optional[str] = Query(None, description="Pagination cursor (application ID)"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db)
):
    """
    Get applications for a specific company.
    Supports search, filters, sorting, and cursor-based pagination.
    
    This endpoint does NOT refetch all data - only returns company-filtered subset.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {
                "applications": [],
                "total_count": 0,
                "next_cursor": None
            }
        
        # Base query: filter by user and company (exact match, case-insensitive)
        query = db.query(Application).filter(
            Application.user_id == user.id,
            func.lower(Application.company_name) == company_name.lower().strip()
        )
        
        # Search filter (within company)
        if search:
            search_lower = search.lower()
            query = query.filter(
                or_(
                    Application.role.ilike(f"%{search_lower}%"),
                    Application.subject.ilike(f"%{search_lower}%"),
                    Application.from_email.ilike(f"%{search_lower}%")
                )
            )
        
        # Status filter (multi-select)
        if status:
            normalized_statuses = []
            for s in status:
                s_upper = s.upper().strip()
                if s_upper in ("OFFER", "ACCEPTED"):
                    s_upper = "OFFER_ACCEPTED"
                normalized_statuses.append(s_upper)
            if normalized_statuses:
                query = query.filter(Application.category.in_(normalized_statuses))
        
        # Get total count (before pagination)
        total_count = query.count()
        
        # Sorting
        if sort_by == "company_name":
            order_field = Application.company_name
        elif sort_by == "received_at":
            order_field = Application.received_at
        else:
            order_field = Application.received_at
        
        if sort_order.lower() == "asc":
            query = query.order_by(asc(order_field))
        else:
            query = query.order_by(desc(order_field))
        
        # Cursor-based pagination (if cursor provided, filter by ID > cursor)
        if cursor:
            try:
                cursor_id = uuid.UUID(cursor)
                query = query.filter(Application.id > cursor_id)
            except ValueError:
                pass  # Invalid cursor, ignore
        
        # Apply limit
        applications = query.limit(limit + 1).all()  # Fetch one extra to check for next page
        
        # Check if there's a next page
        has_next = len(applications) > limit
        if has_next:
            applications = applications[:-1]  # Remove extra item
            next_cursor = str(applications[-1].id) if applications else None
        else:
            next_cursor = None
        
        # Format results
        apps_data = []
        for app in applications:
            category = app.category.upper() if app.category else "APPLIED"
            if category in ("ACCEPTED", "OFFER"):
                category = "OFFER_ACCEPTED"
            
            # Generate Gmail deep link using message ID
            if not app.gmail_message_id:
                logger.error(f"Application {app.id} missing gmail_message_id - cannot generate deep link")
                gmail_deep_link = None
                gmail_web_url = None
            else:
                gmail_deep_link = build_gmail_deep_link(app.gmail_message_id)
                gmail_web_url = gmail_deep_link  # Legacy field
            
            apps_data.append({
                "id": str(app.id),
                "company_name": app.company_name or "Unknown Company",
                "role_title": app.role,
                "status": category,
                "applied_at": app.received_at.isoformat() if app.received_at else None,
                "source": "GMAIL",
                "email_message_id": app.gmail_message_id,
                "gmail_message_id": app.gmail_message_id,  # Explicit field
                "thread_id": app.gmail_thread_id or app.gmail_message_id,
                "subject": app.subject or "No Subject",
                "snippet": app.snippet,
                "received_at": app.received_at.isoformat() if app.received_at else None,
                "gmail_deep_link": gmail_deep_link,  # Primary field (new)
                "gmail_web_url": gmail_web_url,  # Legacy field
                "category": category,
            })
        
        return {
            "applications": apps_data,
            "total_count": total_count,
            "next_cursor": next_cursor
        }
        
    except Exception as e:
        logger.error(f"Error getting company applications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get company applications: {str(e)}")


@app.get("/applications/{app_id}")
async def get_application(
    app_id: int,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get a specific application by ID
    Returns full application data with Gmail web URL
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        application = db.query(Application).filter(
            Application.id == app_id,
            Application.user_id == user.id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Normalize category
        category = application.category.lower()
        if category == "accepted":
            category = "offer"
        
        # Generate Gmail deep link
        if not application.gmail_message_id:
            logger.error(f"Application {application.id} missing gmail_message_id")
            gmail_deep_link = None
            gmail_web_url = None
        else:
            gmail_deep_link = build_gmail_deep_link(application.gmail_message_id)
            gmail_web_url = gmail_deep_link  # Legacy field
        
        return {
            "id": str(application.id),
            "company_name": application.company_name or "Unknown Company",
            "category": category,
            "received_at": application.received_at.isoformat() if application.received_at else None,
            "gmail_message_id": application.gmail_message_id,
            "gmail_thread_id": application.gmail_thread_id,
            "gmail_deep_link": gmail_deep_link,  # Primary field (new)
            "gmail_web_url": gmail_web_url,  # Legacy field
            "gmail_web_url": gmail_web_url,
            "role": application.role,
            "subject": application.subject,
            "from_email": application.from_email,
            "snippet": application.snippet,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get application: {str(e)}")

@app.get("/applications/stats")
async def get_applications_stats(user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Get application statistics by category
    Returns: { "APPLIED": count, "REJECTED": count, "INTERVIEW": count, "OFFER_ACCEPTED": count, "GHOSTED": count }
    Strict API contract - uppercase categories only
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {
                "APPLIED": 0,
                "REJECTED": 0,
                "INTERVIEW": 0,
                "OFFER_ACCEPTED": 0,
                "GHOSTED": 0,
            }
        return calculate_stats(db, user.id)
    except Exception as e:
        logger.error(f"Error getting application stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get application stats: {str(e)}")

@app.get("/stats")
async def get_stats(user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Get dashboard statistics (legacy endpoint)
    Returns REAL counts from backend, never estimated
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {"total": 0, "applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0}
        stats = calculate_stats(db, user.id)
        # Convert to lowercase for backward compatibility
        return {
            "total": sum(stats.values()),
            "applied": stats.get("APPLIED", 0),
            "rejected": stats.get("REJECTED", 0),
            "interview": stats.get("INTERVIEW", 0),
            "offer": stats.get("OFFER_ACCEPTED", 0),
            "ghosted": stats.get("GHOSTED", 0),
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.post("/clear")
async def clear_user_data(request: ClearRequest, db: Session = Depends(get_db)):
    """
    Clear all cached email data for user
    Called on logout or account switch
    """
    # user_id is email, get database user
    user = db.query(User).filter(User.email == request.user_id).first()
    if not user:
        return {"message": "User not found"}
    
    user_id = user.id
    
    try:
        # Delete all applications
        db.query(Application).filter(Application.user_id == user_id).delete()
        
        # Delete OAuth tokens
        db.query(OAuthToken).filter(OAuthToken.user_id == user_id).delete()
        
        # Clear sync state
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if sync_state:
            sync_state.gmail_history_id = None
            sync_state.last_synced_at = None
            sync_state.is_sync_running = False
            sync_state.sync_lock_expires_at = None
            sync_state.lock_job_id = None
        
        db.commit()
        
        # Clear sync jobs for this user (DB-based, no in-memory cleanup needed)
        # Old sync jobs will expire based on expires_at TTL
        logger.info(f"Cleared all data for user {user_id}")
        return {"message": "User data cleared"}
    except Exception as e:
        logger.error(f"Error clearing data: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

@app.post("/oauth/store")
async def store_oauth_tokens(request: OAuthTokenStoreRequest, db: Session = Depends(get_db)):
    """
    Store OAuth tokens for a user (called by auth-service after OAuth callback)
    """
    try:
        # Get or create user
        user = db.query(User).filter(User.email == request.user_email).first()
        if not user:
            user = User(email=request.user_email)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Parse expires_at
        expires_at = None
        if request.expires_at:
            try:
                expires_at = datetime.fromisoformat(request.expires_at.replace('Z', '+00:00'))
                # Ensure timezone-aware (if naive, assume UTC)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            except:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store or update OAuth tokens
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
        if oauth_token:
            # Update existing tokens
            oauth_token.access_token = request.access_token
            if request.refresh_token:
                oauth_token.refresh_token = request.refresh_token
            if request.token_uri:
                oauth_token.token_uri = request.token_uri
            if request.client_id:
                oauth_token.client_id = request.client_id
            if request.client_secret:
                oauth_token.client_secret = request.client_secret
            if request.scopes:
                oauth_token.scopes = json.dumps(request.scopes)
            if expires_at:
                oauth_token.expires_at = expires_at
            oauth_token.updated_at = datetime.now(timezone.utc)
        else:
            # Create new tokens
            oauth_token = OAuthToken(
                user_id=user.id,
                access_token=request.access_token,
                refresh_token=request.refresh_token,
                token_uri=request.token_uri,
                client_id=request.client_id,
                client_secret=request.client_secret,
                scopes=json.dumps(request.scopes or []),
                expires_at=expires_at,
            )
            db.add(oauth_token)
        
        db.commit()
        logger.info(f"Stored OAuth tokens for user {user.email}")
        return {"message": "OAuth tokens stored successfully"}
    except Exception as e:
        logger.error(f"Error storing OAuth tokens: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to store OAuth tokens: {str(e)}")

@app.post("/ghosted/check")
async def check_ghosted(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Scheduled job endpoint to check and update ghosted applications.
    
    This is a cron/scheduled job that should run periodically (e.g., daily).
    
    Rules:
    - Last status in thread is ACTIVE/INTERVIEW
    - No new recruiter/company emails for 30 days
    - → Set GHOSTED
    
    This is separate from model classification (time-based, not content-based).
    """
    def gmail_client_factory(user_id, user_email, oauth_token):
        """Factory to create GmailClient for thread checking."""
        return GmailClient(user_id, user_email, oauth_token)
    
    background_tasks.add_task(ghosted_detector.check_all_users, db, gmail_client_factory)
    return {"message": "Ghosted check started", "threshold_days": ghosted_detector.days}

@app.post("/export")
async def export_applications(
    request: ExportRequest,
    user_id: str = Query(...),  # user_id is email from JWT
    db: Session = Depends(get_db)
):
    """
    Export applications in various formats (CSV, Excel, JSON, PDF)
    Production-grade export with real data from database
    """
    try:
        # Get user by email
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Parse date range
        date_from = None
        date_to = None
        if request.dateRange:
            if request.dateRange.get("from"):
                try:
                    date_from = datetime.fromisoformat(request.dateRange["from"].replace("Z", "+00:00"))
                except:
                    date_from = datetime.strptime(request.dateRange["from"], "%Y-%m-%d")
            if request.dateRange.get("to"):
                try:
                    date_to = datetime.fromisoformat(request.dateRange["to"].replace("Z", "+00:00"))
                except:
                    date_to = datetime.strptime(request.dateRange["to"], "%Y-%m-%d")
                    # Include entire day
                    date_to = date_to.replace(hour=23, minute=59, second=59)
        
        # Validate format
        valid_formats = ["csv", "xlsx", "json", "pdf"]
        if request.format.lower() not in valid_formats:
            raise HTTPException(status_code=400, detail=f"Invalid format. Must be one of: {valid_formats}")
        
        # Validate fields
        valid_fields = [
            "company_name",
            "category",
            "received_at",
            "last_updated",
            "source_email",
            "gmail_message_id",
        ]
        if not request.fields:
            raise HTTPException(status_code=400, detail="At least one field must be selected")
        for field in request.fields:
            if field not in valid_fields:
                raise HTTPException(status_code=400, detail=f"Invalid field: {field}")
        
        # Generate export
        file_bytes, mime_type, filename = generate_export(
            db=db,
            user_id=user.id,
            user_email=user.email,
            format_type=request.format.lower(),
            category=request.category,
            date_from=date_from,
            date_to=date_to,
            fields=request.fields,
        )
        
        logger.info(
            f"Export SUCCESS: user={user.email}, format={request.format}, "
            f"category={request.category}, fields={len(request.fields)}"
        )
        
        # Return file response
        return Response(
            content=file_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            },
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Export validation error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export generation failed: {str(e)}")

@app.post("/applications/{app_id}/reclassify")
async def reclassify_application(
    app_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Re-classify an application.
    
    Triggers full re-run of classification pipeline and creates audit log entry.
    Supports manual re-classification with full traceability.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        application = db.query(Application).filter(
            Application.id == app_id,
            Application.user_id == user.id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Prepare email data for classification
        email_data = {
            "message_id": application.gmail_message_id,
            "thread_id": application.gmail_thread_id,
            "subject": application.subject,
            "snippet": application.snippet or "",
            "sender_email": application.from_email or "",
            "sender_domain": application.company_domain or "",
            "received_at": application.received_at.isoformat() if application.received_at else None,
            "body": ""  # Full body not available in re-classification
        }
        
        # Set db session and get gmail_client on classifier
        if hasattr(classifier, 'db'):
            classifier.db = db
        
        # Get gmail_client for hybrid classifier (if needed)
        if hasattr(classifier, 'gmail_client'):
            # Try to get gmail_client from OAuth token
            oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
            if oauth_token:
                try:
                    from app.gmail_client import GmailClient
                    gmail_client = GmailClient(user.id, user.email, oauth_token)
                    classifier.gmail_client = gmail_client
                except Exception as e:
                    logger.debug(f"Failed to initialize gmail_client for re-classification: {e}")
        
        # Re-classify using full pipeline
        old_category = application.category
        
        # Use hybrid classifier if available
        from app.hybrid_classifier import HybridClassifier
        if isinstance(classifier, HybridClassifier):
            classification_result = classifier.classify(
                email_data=email_data,
                thread_id=application.gmail_thread_id,
                company_name=application.company_name,
                role=application.role
            )
            new_category = classification_result.status.value
            classification_trace = classification_result.to_dict()
            
            # Update with enhanced traceability
            application.category = new_category
            application.classification_source = "HYBRID"
            application.rule_name = ", ".join(classification_result.signals.matched_rules[:3]) if classification_result.signals.matched_rules else None
            application.llm_reason = classification_result.signals.llm_reason
            application.classification_confidence = str(classification_result.confidence)
            application.classified_at = datetime.now(timezone.utc)
            if hasattr(application, 'signals_used'):
                application.signals_used = classification_trace.get("signals_used")
            if hasattr(application, 'rules_triggered'):
                application.rules_triggered = classification_trace.get("rules_triggered")
            if hasattr(application, 'classification_version'):
                application.classification_version = classification_trace.get("version")
        else:
            # Fallback to old classifier
            thread_history = []
            if hasattr(classifier, 'get_thread_history'):
                try:
                    thread_history = classifier.get_thread_history(str(user.id), application.gmail_thread_id)
                except Exception as e:
                    logger.debug(f"Failed to get thread history: {e}")
            
            classification_result = classifier.classify(email_data, thread_history)
            
            if thread_history and hasattr(classifier, 'apply_thread_context'):
                classification_result = classifier.apply_thread_context(
                    email_data,
                    thread_history,
                    classification_result
                )
            
            new_category = classification_result.status.value if hasattr(classification_result, 'status') else str(classification_result)
            application.category = new_category
            if hasattr(classification_result, 'source'):
                application.classification_source = classification_result.source.value
            if hasattr(classification_result, 'rule_name'):
                application.rule_name = classification_result.rule_name
            if hasattr(classification_result, 'llm_reason'):
                application.llm_reason = classification_result.llm_reason
            if hasattr(classification_result, 'confidence') and classification_result.confidence is not None:
                application.classification_confidence = str(classification_result.confidence)
            application.classified_at = datetime.now(timezone.utc)
        
        # Update last_activity_at if category changed
        if old_category != new_category:
            application.last_activity_at = datetime.now(timezone.utc)
        
        # Create audit log entry
        from app.database import ClassificationAuditLog
        reason = classification_result.explanation if isinstance(classifier, HybridClassifier) and hasattr(classification_result, 'explanation') else (
            classification_result.reason if hasattr(classification_result, 'reason') else "Re-classified"
        )
        source = "HYBRID" if isinstance(classifier, HybridClassifier) else (
            classification_result.source.value if hasattr(classification_result, 'source') else "MANUAL"
        )
        rule_name = ", ".join(classification_result.signals.matched_rules[:3]) if isinstance(classifier, HybridClassifier) and hasattr(classification_result, 'signals') else (
            classification_result.rule_name if hasattr(classification_result, 'rule_name') else None
        )
        confidence = str(classification_result.confidence) if hasattr(classification_result, 'confidence') and classification_result.confidence else None
        
        audit_log = ClassificationAuditLog(
            application_id=application.id,
            old_status=old_category,
            new_status=new_category,
            reason=reason,
            classification_source=source,
            rule_name=rule_name,
            confidence=confidence
        )
        db.add(audit_log)
        
        db.commit()
        
        return {
            "success": True,
            "application_id": str(application.id),
            "old_status": old_category,
            "new_status": new_category,
            "classification_source": classification_result.source.value,
            "reason": classification_result.reason,
            "confidence": classification_result.confidence
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error re-classifying application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to re-classify application: {str(e)}")

@app.post("/applications/reclassify/thread/{thread_id}")
async def reclassify_thread(
    thread_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    STEP 10: Re-classify all applications in a thread.
    
    Re-runs classifier pipeline on all emails in the specified Gmail thread.
    Updates DB and emits SSE progress events if long-running.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find all applications in this thread
        applications = db.query(Application).filter(
            Application.gmail_thread_id == thread_id,
            Application.user_id == user.id
        ).all()
        
        if not applications:
            raise HTTPException(status_code=404, detail=f"No applications found for thread {thread_id}")
        
        # Get OAuth token for Gmail client
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
        if not oauth_token:
            raise HTTPException(status_code=400, detail="OAuth tokens not found. Please re-authenticate.")
        
        from app.gmail_client import GmailClient
        gmail_client = GmailClient(user.id, user.email, oauth_token)
        
        # Re-classify each application
        reclassified_count = 0
        for app in applications:
            try:
                # Prepare email data
                email_data = {
                    "message_id": app.gmail_message_id,
                    "thread_id": app.gmail_thread_id,
                    "subject": app.subject,
                    "snippet": app.snippet or "",
                    "sender_email": app.from_email or "",
                    "sender_domain": app.company_domain or "",
                    "received_at": app.received_at.isoformat() if app.received_at else None,
                    "body": ""
                }
                
                # Re-classify
                if isinstance(classifier, HybridClassifier):
                    classifier.db = db
                    classifier.gmail_client = gmail_client
                    result = classifier.classify(
                        email_data=email_data,
                        thread_id=app.gmail_thread_id,
                        company_name=app.company_name,
                        role=app.role
                    )
                    
                    # Update application
                    old_category = app.category
                    app.category = result.status.value
                    app.classification_source = "HYBRID"
                    app.classification_confidence = str(result.confidence)
                    app.classified_at = datetime.now(timezone.utc)
                    app.needs_review = result.confidence < 0.6 if result.confidence else False
                    
                    # Create audit log
                    from app.database import ClassificationAuditLog
                    audit_log = ClassificationAuditLog(
                        application_id=app.id,
                        old_status=old_category,
                        new_status=result.status.value,
                        reason=result.explanation,
                        classification_source="HYBRID",
                        confidence=str(result.confidence)
                    )
                    db.add(audit_log)
                    reclassified_count += 1
            except Exception as e:
                logger.error(f"Error re-classifying application {app.id}: {e}", exc_info=True)
                continue
        
        db.commit()
        
        return {
            "message": f"Re-classified {reclassified_count} applications in thread {thread_id}",
            "thread_id": thread_id,
            "reclassified_count": reclassified_count,
            "total_applications": len(applications)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-classifying thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to re-classify thread: {str(e)}")

@app.post("/applications/reclassify/range")
async def reclassify_range(
    months: Optional[int] = Query(None, description="Time range in months: 3, 6, 12, 16, or None for full"),
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    STEP 10: Re-classify applications within a time range.
    
    Re-runs classifier pipeline on all emails within the specified time range.
    Updates DB and emits SSE progress events if long-running.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Calculate date range
        cutoff_date = None
        if months:
            if months not in [3, 6, 12, 16]:
                raise HTTPException(status_code=400, detail="Invalid months. Must be 3, 6, 12, or 16.")
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=months * 30)
        
        # Query applications
        query = db.query(Application).filter(Application.user_id == user.id)
        if cutoff_date:
            query = query.filter(Application.received_at >= cutoff_date)
        
        applications = query.all()
        
        if not applications:
            return {
                "message": f"No applications found for range",
                "reclassified_count": 0,
                "total_applications": 0
            }
        
        # Get OAuth token for Gmail client
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user.id).first()
        if not oauth_token:
            raise HTTPException(status_code=400, detail="OAuth tokens not found. Please re-authenticate.")
        
        from app.gmail_client import GmailClient
        gmail_client = GmailClient(user.id, user.email, oauth_token)
        
        # Re-classify each application
        reclassified_count = 0
        for app in applications:
            try:
                # Prepare email data
                email_data = {
                    "message_id": app.gmail_message_id,
                    "thread_id": app.gmail_thread_id,
                    "subject": app.subject,
                    "snippet": app.snippet or "",
                    "sender_email": app.from_email or "",
                    "sender_domain": app.company_domain or "",
                    "received_at": app.received_at.isoformat() if app.received_at else None,
                    "body": ""
                }
                
                # Re-classify
                if isinstance(classifier, HybridClassifier):
                    classifier.db = db
                    classifier.gmail_client = gmail_client
                    result = classifier.classify(
                        email_data=email_data,
                        thread_id=app.gmail_thread_id,
                        company_name=app.company_name,
                        role=app.role
                    )
                    
                    # Update application
                    old_category = app.category
                    app.category = result.status.value
                    app.classification_source = "HYBRID"
                    app.classification_confidence = str(result.confidence)
                    app.classified_at = datetime.now(timezone.utc)
                    app.needs_review = result.confidence < 0.6 if result.confidence else False
                    
                    # Create audit log
                    from app.database import ClassificationAuditLog
                    audit_log = ClassificationAuditLog(
                        application_id=app.id,
                        old_status=old_category,
                        new_status=result.status.value,
                        reason=result.explanation,
                        classification_source="HYBRID",
                        confidence=str(result.confidence)
                    )
                    db.add(audit_log)
                    reclassified_count += 1
            except Exception as e:
                logger.error(f"Error re-classifying application {app.id}: {e}", exc_info=True)
                continue
        
        db.commit()
        
        return {
            "message": f"Re-classified {reclassified_count} applications",
            "reclassified_count": reclassified_count,
            "total_applications": len(applications),
            "range_months": months
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-classifying range: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to re-classify range: {str(e)}")

@app.get("/health")
async def health(db: Session = Depends(get_db)):
    # Database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = {"status": "ok"}
    except Exception as e:
        database = {"status": "error", "message": str(e)}

    # Classifier service
    classifier_url = os.getenv("CLASSIFIER_SERVICE_URL", "http://host.docker.internal:8003")
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{classifier_url.rstrip('/')}/health")
        classifier_svc = {"status": "ok" if r.status_code == 200 else "error", "status_code": r.status_code}
    except Exception as e:
        classifier_svc = {"status": "error", "message": str(e)}

    # Count running sync jobs from DB
    try:
        running = db.query(SyncJob).filter(SyncJob.status == SyncJobStatus.RUNNING).count()
        total = db.query(SyncJob).count()
    except Exception:
        running = 0
        total = 0
    
    overall = "ok" if database.get("status") == "ok" else "degraded"

    return {
        "status": overall,
        "service": "gmail-connector",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "uptime_seconds": round(time.time() - _health_start, 2),
        "database": database,
        "classifier_service": classifier_svc,
        "active_sync_jobs": running,
        "total_sync_jobs": total,
    }

@app.get("/health/classifier")
async def health_classifier():
    """
    STEP 10: Health check for ONNX classifier.
    Verifies model session is loaded and runs one tiny inference on a known sample.
    """
    try:
        from app.services.classifier.hf_onnx_classifier import get_classifier
        
        # Check if classifier is initialized
        try:
            clf = get_classifier()
        except RuntimeError as e:
            return {
                "status": "error",
                "message": f"Classifier not initialized: {str(e)}",
                "model_loaded": False
            }
        
        # Run one tiny inference on a known sample
        test_result = clf.classify_one(
            subject="Interview availability",
            snippet="Can you share times for a 30-min call?",
            from_domain="greenhouse.io",
            thread_summary=""
        )
        
        # Verify result structure
        if not test_result or "status" not in test_result or "confidence" not in test_result:
            return {
                "status": "error",
                "message": "Classifier returned invalid result structure",
                "model_loaded": True,
                "inference_test": "failed"
            }
        
        return {
            "status": "ok",
            "model_loaded": True,
            "inference_test": "passed",
            "test_result": {
                "status": test_result.get("status"),
                "confidence": test_result.get("confidence"),
                "label": test_result.get("label")
            },
            "model_name": os.getenv("ONNX_MODEL_NAME", "job_email_classifier_v1"),
            "model_version": os.getenv("ONNX_MODEL_VERSION", "1.0")
        }
    except Exception as e:
        logger.error(f"Classifier health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "model_loaded": False
        }


# ========== PROFILE LINKS ENDPOINTS ==========

class ProfileLinkCreate(BaseModel):
    type: str  # "linkedin", "github", "portfolio", "custom"
    label: Optional[str] = None  # Required for "custom"
    url: str

class ProfileLinkUpdate(BaseModel):
    type: Optional[str] = None
    label: Optional[str] = None
    url: Optional[str] = None

@app.get("/profile/links")
async def get_profile_links(
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get all profile links for the current user.
    Returns list of profile links.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        links = db.query(ProfileLink).filter(
            ProfileLink.user_id == user.id
        ).order_by(ProfileLink.created_at.asc()).all()
        
        links_data = []
        for link in links:
            links_data.append({
                "id": str(link.id),
                "type": link.type.value,
                "label": link.label,
                "url": link.url,
                "created_at": link.created_at.isoformat() if link.created_at else None,
                "updated_at": link.updated_at.isoformat() if link.updated_at else None,
            })
        
        return {"links": links_data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile links: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get profile links: {str(e)}")

@app.post("/profile/links")
async def create_profile_link(
    link_data: ProfileLinkCreate,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Create a new profile link.
    Validates and normalizes URL before saving.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Validate URL
        is_valid, result = validate_url(link_data.url)
        if not is_valid:
            raise HTTPException(status_code=400, detail=result)
        
        normalized_url = result
        
        # Validate type
        try:
            link_type = ProfileLinkType(link_data.type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid link type. Must be one of: linkedin, github, portfolio, custom"
            )
        
        # Validate label requirement for custom type
        if link_type == ProfileLinkType.CUSTOM:
            if not link_data.label or not link_data.label.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Label is required for custom link type"
                )
        else:
            # Auto-detect label for non-custom types if not provided
            link_data.label = link_data.label or None
        
        # Create profile link
        profile_link = ProfileLink(
            user_id=user.id,
            type=link_type,
            label=link_data.label.strip() if link_data.label else None,
            url=normalized_url,
        )
        
        db.add(profile_link)
        db.commit()
        db.refresh(profile_link)
        
        return {
            "id": str(profile_link.id),
            "type": profile_link.type.value,
            "label": profile_link.label,
            "url": profile_link.url,
            "created_at": profile_link.created_at.isoformat() if profile_link.created_at else None,
            "updated_at": profile_link.updated_at.isoformat() if profile_link.updated_at else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating profile link: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create profile link: {str(e)}")

@app.put("/profile/links/{link_id}")
async def update_profile_link(
    link_id: str,
    link_data: ProfileLinkUpdate,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Update an existing profile link.
    Validates and normalizes URL if provided.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        profile_link = db.query(ProfileLink).filter(
            ProfileLink.id == link_id,
            ProfileLink.user_id == user.id
        ).first()
        
        if not profile_link:
            raise HTTPException(status_code=404, detail="Profile link not found")
        
        # Update URL if provided
        if link_data.url is not None:
            is_valid, result = validate_url(link_data.url)
            if not is_valid:
                raise HTTPException(status_code=400, detail=result)
            profile_link.url = result
        
        # Update type if provided
        if link_data.type is not None:
            try:
                link_type = ProfileLinkType(link_data.type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid link type. Must be one of: linkedin, github, portfolio, custom"
                )
            profile_link.type = link_type
            
            # Validate label requirement for custom type
            if link_type == ProfileLinkType.CUSTOM:
                if not link_data.label or not link_data.label.strip():
                    # If type changed to custom but no label provided, keep existing label or require it
                    if not profile_link.label:
                        raise HTTPException(
                            status_code=400,
                            detail="Label is required for custom link type"
                        )
        
        # Update label if provided
        if link_data.label is not None:
            # If type is custom, label is required
            if profile_link.type == ProfileLinkType.CUSTOM:
                if not link_data.label.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Label cannot be empty for custom link type"
                    )
                profile_link.label = link_data.label.strip()
            else:
                profile_link.label = link_data.label.strip() if link_data.label.strip() else None
        
        profile_link.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(profile_link)
        
        return {
            "id": str(profile_link.id),
            "type": profile_link.type.value,
            "label": profile_link.label,
            "url": profile_link.url,
            "created_at": profile_link.created_at.isoformat() if profile_link.created_at else None,
            "updated_at": profile_link.updated_at.isoformat() if profile_link.updated_at else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating profile link: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update profile link: {str(e)}")

@app.delete("/profile/links/{link_id}")
async def delete_profile_link(
    link_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Delete a profile link.
    """
    try:
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        profile_link = db.query(ProfileLink).filter(
            ProfileLink.id == link_id,
            ProfileLink.user_id == user.id
        ).first()
        
        if not profile_link:
            raise HTTPException(status_code=404, detail="Profile link not found")
        
        db.delete(profile_link)
        db.commit()
        
        return {"success": True, "message": "Profile link deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting profile link: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete profile link: {str(e)}")

@app.post("/classify", response_model=ClassificationResult)
def classify(payload: EmailForClassification):
    """
    Classify an email using ONNX model.
    
    This endpoint uses the singleton ONNX classifier initialized at startup.
    """
    try:
        from app.services.classifier.hf_onnx_classifier import get_classifier
        clf = get_classifier()
        out = clf.classify_one(
            subject=payload.subject or "",
            snippet=payload.snippet or "",
            from_domain=payload.from_domain or "",
            thread_summary=payload.thread_summary or "",
        )
        return ClassificationResult(**out)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
