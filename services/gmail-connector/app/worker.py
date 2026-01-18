"""
RQ Worker entrypoint for processing Gmail sync jobs
"""
import asyncio
import uuid
import logging
from app.database import SessionLocal, SyncJob, SyncJobStatus
from app.progress_events import (
    create_progress_event, 
    publish_progress_event, 
    SyncPhase, 
    EventLevel
)
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)

def process_sync_job(job_id_str: str, user_id_str: str, user_email: str):
    """
    RQ worker function to process a Gmail sync job.
    This is a synchronous wrapper around the async run_sync function.
    
    Args:
        job_id_str: UUID string of the sync job
        user_id_str: Database user ID (UUID string)
        user_email: User email for validation
    """
    job_id = uuid.UUID(job_id_str)
    user_id = uuid.UUID(user_id_str)
    
    # Run the async sync function
    asyncio.run(run_sync_with_progress(job_id, user_id, user_email))

async def run_sync_with_progress(job_id: uuid.UUID, user_id: uuid.UUID, user_email: str):
    """
    Run Gmail sync with progress event publishing.
    This is a refactored version of run_sync that publishes progress events.
    """
    from app.main import (
        GmailClient, SyncEngine, OAuthToken, SyncState,
        classifier, company_extractor, calculate_stats, add_log
    )
    
    db = SessionLocal()
    sync_job = None
    start_time = datetime.now(timezone.utc)
    last_event_time = start_time
    event_throttle_seconds = 1.0  # Publish events at most once per second
    
    try:
        # Get SyncJob from DB
        sync_job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not sync_job:
            logger.error(f"SyncJob {job_id} not found in DB")
            return
        
        # Publish queued event
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.QUEUED,
            message="Sync job queued",
            level=EventLevel.INFO
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        # Update status to RUNNING
        sync_job.status = SyncJobStatus.RUNNING
        sync_job.started_at = datetime.now(timezone.utc)
        sync_job.updated_at = datetime.now(timezone.utc)
        sync_job.current_phase = SyncPhase.STARTING
        db.commit()
        
        # Publish starting event with initial counts
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.STARTING,
            message="Starting Gmail sync...",
            level=EventLevel.INFO,
            counts={
                "total_estimated": 0,
                "listed": 0,
                "fetched": 0,
                "parsed": 0,
                "classified": 0,
                "saved": 0,
                "skipped": 0,
                "failed": 0
            }
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        add_log(db, job_id, "Starting Gmail sync...", "info")
        logger.info(f"Starting sync for user {user_id} (job {job_id})")
        
        # Get user's OAuth tokens
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
        if not oauth_token:
            error_msg = f"No OAuth tokens found for user {user_email}. Please re-authenticate."
            add_log(db, job_id, f"ERROR: {error_msg}", "error")
            _publish_error_event(str(job_id), error_msg, "REAUTH_REQUIRED", db, sync_job)
            raise Exception(f"REAUTH_REQUIRED: {error_msg}")
        
        # Check token expiration
        if oauth_token.expires_at:
            expires_at = oauth_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                if not oauth_token.refresh_token:
                    error_msg = "Access token expired and no refresh token available. Please re-authenticate."
                    add_log(db, job_id, f"ERROR: {error_msg}", "error")
                    _publish_error_event(str(job_id), error_msg, "REAUTH_REQUIRED", db, sync_job)
                    raise Exception(f"REAUTH_REQUIRED: {error_msg}")
        
        # Initialize Gmail client
        add_log(db, job_id, "Initializing Gmail client...", "info")
        try:
            gmail_client = GmailClient(user_id, user_email, oauth_token)
            try:
                gmail_client._refresh_token_if_needed()
                db.refresh(oauth_token)
                db.commit()
            except Exception as refresh_err:
                if "REAUTH_REQUIRED" in str(refresh_err):
                    raise
                logger.warning(f"Token refresh attempt failed (non-fatal): {refresh_err}")
            add_log(db, job_id, "Gmail client initialized successfully", "success")
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
            _publish_error_event(str(job_id), error_msg, "VALIDATION_ERROR", db, sync_job)
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
        
        # Determine sync type
        is_incremental = sync_state.gmail_history_id is not None
        if is_incremental:
            add_log(db, job_id, "Starting incremental sync (only new emails)...", "info")
            sync_job.current_phase = SyncPhase.LISTING
        else:
            add_log(db, job_id, "Starting full sync (scanning all emails)...", "info")
            sync_job.current_phase = SyncPhase.LISTING
        
        # Publish listing phase event
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.LISTING,
            message="Listing emails from Gmail...",
            level=EventLevel.INFO
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        db.commit()
        
        # Track progress for rate calculation
        last_count_update = {
            "listed": 0,
            "fetched": 0,
            "parsed": 0,
            "classified": 0,
            "saved": 0
        }
        last_rate_calc_time = datetime.now(timezone.utc)
        
        # Run sync - iterate through progress updates
        async for progress in sync_engine.sync_all_emails(user_id, sync_state.gmail_history_id):
            total_scanned = progress.get("total_scanned", 0)
            total_fetched = progress.get("total_fetched", 0)
            candidate_job_emails = progress.get("candidate_job_emails", 0)
            processed_count = progress.get("processed_emails", total_fetched)
            
            # Update counts
            counts = {
                "total_estimated": total_scanned,
                "listed": total_scanned,
                "fetched": total_fetched,
                "parsed": total_fetched,
                "classified": candidate_job_emails,
                "saved": processed_count,
                "skipped": max(0, total_scanned - total_fetched),
                "failed": 0
            }
            
            # Calculate rate
            now = datetime.now(timezone.utc)
            elapsed = (now - last_rate_calc_time).total_seconds()
            if elapsed > 0:
                emails_per_sec = (total_fetched - last_count_update["fetched"]) / elapsed
            else:
                emails_per_sec = 0.0
            
            rate = {
                "emails_per_sec": emails_per_sec,
                "bytes_per_sec": 0.0  # Could calculate if needed
            }
            
            # Update phase based on progress
            if total_fetched == 0:
                phase = SyncPhase.LISTING
                message = f"Listing emails... Found {total_scanned} so far"
            elif candidate_job_emails > 0 and processed_count < candidate_job_emails:
                phase = SyncPhase.CLASSIFYING
                message = f"Classifying emails... {processed_count}/{candidate_job_emails} processed"
            else:
                phase = SyncPhase.FETCHING
                message = f"Fetching emails... {total_fetched}/{total_scanned} fetched"
            
            # Publish event for EVERY email processed (real-time updates)
            # Only throttle DB persistence to avoid too many writes
            should_persist_to_db = (
                total_fetched % 10 == 0 or  # Persist every 10 emails
                total_scanned % 50 == 0 or  # Or every 50 scanned
                total_fetched == 1  # Always persist first
            )
            
            # Always publish event to Redis for real-time UI updates
            event = create_progress_event(
                sync_id=str(job_id),
                phase=phase,
                message=message,
                level=EventLevel.INFO,
                counts=counts,
                rate=rate,
                cursor={
                    "page_token": progress.get("page_token"),
                    "history_id": sync_state.gmail_history_id
                }
            )
            publish_progress_event(event)
            
            # Only persist to DB periodically to avoid too many writes
            if should_persist_to_db:
                _persist_event(db, sync_job, event)
                last_event_time = now
                last_rate_calc_time = now
                last_count_update = counts.copy()
            else:
                # Still update rate calculation time for accurate rate
                last_rate_calc_time = now
            
            # Update DB
            sync_job.total_emails = total_scanned
            sync_job.processed_emails = processed_count
            sync_job.counts_listed = total_scanned
            sync_job.counts_fetched = total_fetched
            sync_job.counts_classified = candidate_job_emails
            sync_job.counts_saved = processed_count
            sync_job.counts_skipped = max(0, total_scanned - total_fetched)
            sync_job.rate_emails_per_sec = int(emails_per_sec)
            sync_job.current_phase = phase
            sync_job.updated_at = now
            sync_job.last_heartbeat_at = now
            
            # Add email entry if present
            email_entry = progress.get("email_entry")
            if email_entry:
                email_entries = sync_job.email_entries or []
                email_entries.append(email_entry)
                if len(email_entries) > 100:
                    email_entries = email_entries[-100:]
                sync_job.email_entries = email_entries
            
            # Commit every 10 batches
            if total_fetched % 10 == 0:
                db.commit()
        
        # Finalize
        final_total_scanned = sync_job.total_emails
        final_total_fetched = sync_job.processed_emails
        
        # Update sync state
        sync_state.gmail_history_id = sync_engine.get_latest_history_id()
        sync_state.last_synced_at = datetime.now(timezone.utc)
        sync_state.is_sync_running = False
        sync_state.sync_lock_expires_at = None
        
        # Get final stats
        final_stats = calculate_stats(db, user_id)
        db.commit()
        
        # Publish finalizing event
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.FINALIZING,
            message="Finalizing sync...",
            level=EventLevel.INFO,
            counts={
                "total_estimated": final_total_scanned,
                "listed": final_total_scanned,
                "fetched": final_total_fetched,
                "parsed": final_total_fetched,
                "classified": sum(final_stats.values()),
                "saved": sum(final_stats.values()),
                "skipped": max(0, final_total_scanned - final_total_fetched),
                "failed": 0
            }
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        # Mark as completed
        sync_job.status = SyncJobStatus.COMPLETED
        sync_job.finished_at = datetime.now(timezone.utc)
        sync_job.current_phase = SyncPhase.DONE
        db.commit()
        
        # Publish done event
        total_stored = sum(final_stats.values())
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.DONE,
            message=f"Sync completed! Stored {total_stored} job application emails.",
            level=EventLevel.INFO,
            counts={
                "total_estimated": final_total_scanned,
                "listed": final_total_scanned,
                "fetched": final_total_fetched,
                "parsed": final_total_fetched,
                "classified": total_stored,
                "saved": total_stored,
                "skipped": max(0, final_total_scanned - final_total_fetched),
                "failed": 0
            },
            done=True
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        error_code = None
        
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
        _publish_error_event(str(job_id), error_msg, error_code, db, sync_job)
        
    finally:
        try:
            db.close()
        except Exception:
            pass

def _persist_event(db, sync_job, event):
    """Persist progress event to DB for reconnection"""
    try:
        sync_job.last_event_json = event
        sync_job.last_heartbeat_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist event: {e}")
        db.rollback()

def _publish_error_event(sync_id: str, error_msg: str, error_code: str, db, sync_job):
    """Publish error event and update job status"""
    try:
        event = create_progress_event(
            sync_id=sync_id,
            phase=SyncPhase.FAILED,
            message=f"Sync failed: {error_msg}",
            level=EventLevel.ERROR,
            errors=[{
                "code": error_code,
                "detail": error_msg,
                "retryable": error_code in ["RATE_LIMIT", "TIMEOUT"]
            }],
            done=True
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        sync_job.status = SyncJobStatus.FAILED
        sync_job.finished_at = datetime.now(timezone.utc)
        sync_job.error_message = error_msg
        sync_job.error_code = error_code
        sync_job.error_json = {"code": error_code, "detail": error_msg}
        sync_job.current_phase = SyncPhase.FAILED
        db.commit()
    except Exception as e:
        logger.error(f"Failed to publish error event: {e}")
        db.rollback()

if __name__ == "__main__":
    # RQ worker entrypoint
    from rq import Worker, Queue, Connection
    from app.queue import get_redis_connection_for_worker
    
    logging.basicConfig(level=logging.INFO)
    
    redis_conn = get_redis_connection_for_worker()
    if redis_conn is None:
        logger.error("Cannot start worker: Redis connection not available")
        exit(1)
    
    with Connection(redis_conn):
        worker = Worker(['gmail_sync'])
        worker.work()
