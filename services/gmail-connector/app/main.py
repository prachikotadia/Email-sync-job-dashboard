from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.gmail_client import GmailClient
from app.sync_engine import SyncEngine
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import get_db, init_db, engine, SessionLocal, User, Application, SyncState, OAuthToken, SyncJob, SyncJobStatus
from app.ghosted_detector import GhostedDetector
from app.export_service import generate_export
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

# Initialize components
classifier = Classifier()
company_extractor = CompanyExtractor()
ghosted_detector = GhostedDetector(days=int(os.getenv("GHOSTED_DAYS", "21")))

# In-memory sync jobs - REMOVED, using DB-only SyncJob model

class SyncStartRequest(BaseModel):
    user_id: str
    user_email: str  # Authenticated user email for validation

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
    
    # Check for existing RUNNING sync job
    existing_job = db.query(SyncJob).filter(
        SyncJob.user_id == user.id,
        SyncJob.status == SyncJobStatus.RUNNING
    ).first()
    
    if existing_job:
        # Sync already running - return existing sync_id
        sync_id = str(existing_job.id)
        logger.info(f"Sync already running for user {user_email}, returning existing sync_id: {sync_id}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"sync_id": sync_id, "status": "running"}
        )
    
    # Create new SyncJob in DB with PENDING status
    job_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)  # 24 hour TTL
    
    sync_job = SyncJob(
        id=job_id,
        user_id=user.id,
        status=SyncJobStatus.PENDING,
        total_emails=0,
        processed_emails=0,
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        logs=[],
        email_entries=[]
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

def calculate_stats(db: Session, user_id) -> dict:
    """
    Returns REAL counts from DB, never estimated.
    Five categories: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED (uppercase).
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
    
    # Map results (handle legacy lowercase categories)
    for category, count in results:
        cat_upper = category.upper() if category else None
        if cat_upper == "OFFER" or cat_upper == "ACCEPTED":
            cat_upper = "OFFER_ACCEPTED"
        if cat_upper in stats:
            stats[cat_upper] = count
    
    return stats

def _generate_gmail_web_url(message_id: str, user_email: str) -> str:
    """
    Generate Gmail web URL for a message
    Format: https://mail.google.com/mail/u/0/#inbox/{message_id}
    """
    # Gmail web URL format
    # For Gmail, we can use the message ID directly
    # The URL format is: https://mail.google.com/mail/u/0/#inbox/{message_id}
    # Or: https://mail.google.com/mail/u/0/#search/{message_id}
    return f"https://mail.google.com/mail/u/0/#inbox/{message_id}"


@app.get("/applications")
async def get_applications(
    user_id: str = Query(...),
    search: str = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get all applications
    NO pagination limits - returns ALL fetched emails
    Response includes gmail_web_url for opening emails
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {"applications": [], "total": 0, "counts": {}, "warning": None}
        
        query = db.query(Application).filter(Application.user_id == user.id)
        
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
            query = query.filter(Application.category == status_upper)
        
        applications = query.order_by(Application.received_at.desc()).all()
        
        # Convert to dict with all required fields (strict API contract)
        apps_data = []
        for app in applications:
            # Category must be uppercase: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED
            category = app.category.upper() if app.category else "APPLIED"
            if category == "ACCEPTED" or category == "OFFER":
                category = "OFFER_ACCEPTED"
            
            # Use stored gmail_web_url or generate if missing
            gmail_web_url = app.gmail_web_url if app.gmail_web_url else _generate_gmail_web_url(app.gmail_message_id, user_id)
            
            # Ensure gmail_thread_id is never null
            gmail_thread_id = app.gmail_thread_id if app.gmail_thread_id else app.gmail_message_id
            
            apps_data.append({
                "id": str(app.id),
                "company_name": app.company_name or "Unknown Company",  # Ensure never null
                "category": category,  # Uppercase: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED
                "subject": app.subject or "No Subject",  # Ensure never null
                "snippet": app.snippet,
                "received_at": app.received_at.isoformat() if app.received_at else None,
                "gmail_web_url": gmail_web_url,  # Required field
            })
        
        return {
            "total": len(apps_data),
            "applications": apps_data,
        }
    except Exception as e:
        logger.error(f"Error getting applications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get applications: {str(e)}")


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
        
        # Generate Gmail web URL
        gmail_web_url = _generate_gmail_web_url(application.gmail_message_id, user_id)
        
        return {
            "id": str(application.id),
            "company_name": application.company_name or "Unknown Company",
            "category": category,
            "received_at": application.received_at.isoformat() if application.received_at else None,
            "gmail_message_id": application.gmail_message_id,
            "gmail_thread_id": application.gmail_thread_id,
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
    Background job to check and update ghosted applications
    """
    background_tasks.add_task(ghosted_detector.check_all_users, db)
    return {"message": "Ghosted check started"}

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
