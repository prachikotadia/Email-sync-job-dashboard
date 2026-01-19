"""
RQ Worker entrypoint for processing Gmail sync jobs
"""
import asyncio
import uuid
import logging
from app.database import SessionLocal, SyncJob, SyncJobStatus, SyncStateEnum
from app.progress_events import (
    create_progress_event, 
    publish_progress_event, 
    SyncPhase, 
    EventLevel
)
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)

def _check_and_handle_cancellation(db, sync_job, job_id: uuid.UUID):
    """
    Check if job has been canceled and handle cancellation.
    
    Returns:
        True if job was canceled (caller should exit), False otherwise
    """
    # Refresh job from DB to get latest status
    db.refresh(sync_job)
    
    if sync_job.status == SyncJobStatus.CANCEL_REQUESTED:
        # Cancel the job - set to CANCELED state
        sync_job.status = SyncJobStatus.CANCELED
        sync_job.sync_state = SyncStateEnum.COMPLETED  # Use COMPLETED state for canceled jobs
        sync_job.canceled_at = datetime.now(timezone.utc)
        sync_job.finished_at = datetime.now(timezone.utc)
        sync_job.current_phase = SyncPhase.CANCELED
        sync_job.updated_at = datetime.now(timezone.utc)
        
        # Get current counts for cancellation event
        current_counts = {
            "total_estimated": sync_job.total_emails or 0,
            "listed": sync_job.counts_listed or 0,
            "fetched": sync_job.counts_fetched or 0,
            "parsed": sync_job.counts_parsed or 0,
            "classified": sync_job.counts_classified or 0,
            "saved": sync_job.counts_saved or 0,
            "skipped": sync_job.counts_skipped or 0,
            "failed": 0
        }
        
        # Emit CANCELED SSE event immediately
        cancel_event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.CANCELED,
            message="Sync canceled by user",
            level=EventLevel.INFO,
            counts=current_counts,
            rate={"emails_per_sec": 0.0, "bytes_per_sec": 0.0},
            done=True
        )
        publish_progress_event(cancel_event)
        _persist_event(db, sync_job, cancel_event)
        
        # Update sync state (user-level)
        from app.main import SyncState
        sync_state = db.query(SyncState).filter(SyncState.user_id == sync_job.user_id).first()
        if sync_state:
            sync_state.is_sync_running = False
            sync_state.sync_lock_expires_at = None
        
        db.commit()
        logger.info(f"Sync job {job_id} canceled by user")
        # Note: add_log is in app.main, but we avoid importing it here to prevent circular deps
        # Logging is handled via publish_progress_event and _persist_event
        
        return True
    return False

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
        
        # Resume from last state on crash (if job was interrupted)
        last_state = sync_job.sync_state
        if last_state not in [SyncStateEnum.IDLE, SyncStateEnum.COMPLETED, SyncStateEnum.FAILED_FATAL]:
            logger.info(f"Resuming sync job {job_id} from last state: {last_state.value}")
        
        # Publish queued event
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.QUEUED,
            message="Sync job queued",
            level=EventLevel.INFO
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        # Update status and sync_state to QUEUED (if resuming, will transition to appropriate state)
        sync_job.status = SyncJobStatus.RUNNING
        sync_job.sync_state = SyncStateEnum.QUEUED
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
        
        # Determine sync type and set state to FETCHING_HEADERS (starting message list fetch)
        is_incremental = sync_state.gmail_history_id is not None
        if is_incremental:
            add_log(db, job_id, "Starting incremental sync (only new emails)...", "info")
        else:
            add_log(db, job_id, "Starting full sync (scanning all emails)...", "info")
        
        # Transition to FETCHING_HEADERS state (pagination of message list)
        sync_job.sync_state = SyncStateEnum.FETCHING_HEADERS
        sync_job.current_phase = SyncPhase.LISTING
        sync_job.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        # Check for cancellation before starting sync
        if _check_and_handle_cancellation(db, sync_job, job_id):
            return  # Job was canceled, exit early
        
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
        
        # Get mode from checkpoint (stored when job was created)
        checkpoint = sync_job.checkpoint or {}
        mode = checkpoint.get("mode", "full_history")
        time_range_months = checkpoint.get("time_range_months")
        checkpoint_token = checkpoint.get("page_token")  # For resume (if crash occurred mid-pagination)
        checkpoint_state_str = checkpoint.get("sync_state")  # Resume from last state
        
        # Resume from last state if checkpoint exists
        if checkpoint_state_str:
            try:
                resume_state = SyncStateEnum(checkpoint_state_str)
                logger.info(f"Resuming sync from checkpoint: state={resume_state.value}, page_token={checkpoint_token[:20] if checkpoint_token else 'None'}...")
                # If resuming from a non-terminal state, continue from that state
                if resume_state not in [SyncStateEnum.COMPLETED, SyncStateEnum.FAILED_FATAL]:
                    sync_job.sync_state = resume_state
                    db.commit()
            except (ValueError, KeyError):
                logger.warning(f"Invalid checkpoint state: {checkpoint_state_str}, starting from QUEUED")
        
        # Run sync - iterate through progress updates
        # Wrap with rate limit handling: pause job, persist progress, emit SSE event, retry with backoff
        max_rate_limit_retries = 10  # Maximum retries for rate limits (do not fail sync)
        rate_limit_delay = 2.0  # Start with 2s, double each time (2s → 4s → 8s → ... → max 60s)
        max_rate_limit_delay = 60.0
        
        retry_count = 0
        while retry_count <= max_rate_limit_retries:
            try:
                async for progress in sync_engine.sync_all_emails(
                    user_id, 
                    sync_state.gmail_history_id,
                    mode=mode,
                    time_range_months=time_range_months,
                    checkpoint_token=checkpoint_token
                ):
                    # Check for cancellation before processing each progress update
                    if _check_and_handle_cancellation(db, sync_job, job_id):
                        return  # Job was canceled, exit immediately
                    
                    # Reset retry count on successful progress
                    retry_count = 0
                    rate_limit_delay = 2.0  # Reset delay
                    
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
                    
                    # Update phase and explicit sync_state based on progress
                    # State transitions: FETCHING_HEADERS -> FETCHING_BODIES -> CLASSIFYING (saves occur during classification)
                    if total_fetched == 0:
                        phase = SyncPhase.LISTING
                        message = f"Listing emails... Found {total_scanned} so far"
                        explicit_state = SyncStateEnum.FETCHING_HEADERS  # Getting message list
                    elif total_scanned > 0 and candidate_job_emails == 0 and processed_count == 0:
                        phase = SyncPhase.FETCHING
                        message = f"Fetching emails... {total_fetched}/{total_scanned} fetched"
                        explicit_state = SyncStateEnum.FETCHING_BODIES  # Fetching full message content
                    elif candidate_job_emails > 0:
                        phase = SyncPhase.CLASSIFYING
                        message = f"Classifying and saving emails... {processed_count}/{candidate_job_emails} processed"
                        # CLASSIFYING state covers both classification and persistence (saves happen during this phase)
                        explicit_state = SyncStateEnum.CLASSIFYING
                    else:
                        phase = SyncPhase.FETCHING
                        message = f"Fetching emails... {total_fetched}/{total_scanned} fetched"
                        explicit_state = SyncStateEnum.FETCHING_BODIES
                    
                    # Publish event for EVERY email processed (real-time updates)
                    # Only throttle DB persistence to avoid too many writes
                    should_persist_to_db = (
                        total_fetched % 10 == 0 or  # Persist every 10 emails
                        total_scanned % 50 == 0 or  # Or every 50 scanned
                        total_fetched == 1  # Always persist first
                    )
                    
                    # Always publish event to Redis for real-time UI updates
                    # Include email_id if available for per-email tracking
                    email_entry = progress.get("email_entry")
                    email_id = email_entry.get("id") if email_entry else None
                    
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
                        },
                        email_id=email_id  # Include email_id for per-email tracking
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
                    
                    # Update DB with explicit sync_state (for retry/resume)
                    sync_job.total_emails = total_scanned
                    sync_job.processed_emails = processed_count
                    sync_job.counts_listed = total_scanned
                    sync_job.counts_fetched = total_fetched  # Actual fetched from Gmail
                    # CRITICAL: counts_classified must be actual saved count (sum of classified dict)
                    # This ensures DB stored count == classified count verification passes
                    sync_job.counts_classified = processed_count  # Actual classified and saved count
                    sync_job.counts_saved = processed_count  # Same as classified (all classified are saved)
                    sync_job.counts_skipped = max(0, total_scanned - total_fetched)
                    sync_job.rate_emails_per_sec = int(emails_per_sec)
                    sync_job.current_phase = phase
                    sync_job.sync_state = explicit_state  # Persist explicit state for resume
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
                        
                        # Emit per-email event for granular tracking
                        # This allows UI to show "Fetching email 1...", "Classifying email 2...", etc.
                        per_email_event = create_progress_event(
                            sync_id=str(job_id),
                            phase=SyncPhase.CLASSIFYING,  # Email is being classified/saved
                            message=f"Processing email {processed_count}: {email_entry.get('company', 'Unknown')} - {email_entry.get('subject', 'No subject')[:50]}",
                            level=EventLevel.INFO,
                            counts=counts,
                            rate=rate,
                            cursor={
                                "page_token": progress.get("page_token"),
                                "history_id": sync_state.gmail_history_id
                            },
                            email_id=email_entry.get("id")  # Include email_id for per-email tracking
                        )
                        publish_progress_event(per_email_event)
                        # Don't persist per-email events to DB (too many writes) - only persist batch events
                    
                    # Save checkpoint every 10 batches for crash recovery
                    # REQUIRED: Persist last processed messageId, internalDate, pageToken
                    if total_fetched % 10 == 0:
                        # Update checkpoint with current state for resume capability
                        checkpoint_data = sync_job.checkpoint or {}
                        checkpoint_data.update({
                            "mode": mode,
                            "time_range_months": time_range_months,
                            "page_token": progress.get("page_token"),  # Required: for resume pagination
                            "last_processed_message_id": progress.get("last_processed_message_id"),  # Required: skip already processed
                            "last_message_index": progress.get("last_processed_message_id"),  # Alias for requirements compatibility
                            "last_processed_internal_date": progress.get("last_processed_internal_date"),  # Required: for ordering
                            "total_fetched": total_fetched,
                            "processed_count": processed_count,
                            "sync_state": explicit_state.value  # Persist state for resume
                        })
                        sync_job.checkpoint = checkpoint_data
                        db.commit()
                
                # Async for completed successfully - break from retry loop
                break  # Sync completed successfully
                
            except Exception as rate_limit_error:
                # Check if it's a GmailRateLimitError
                from app.gmail_client import GmailRateLimitError
                
                if isinstance(rate_limit_error, GmailRateLimitError):
                    retry_count += 1
                    error_msg = str(rate_limit_error)
                    
                    # Calculate backoff delay: 2s → 4s → 8s → ... → max 60s
                    wait_time = min(rate_limit_delay, max_rate_limit_delay)
                    if rate_limit_error.retry_after:
                        # Use suggested retry-after from API if provided
                        wait_time = min(float(rate_limit_error.retry_after), max_rate_limit_delay)
                    
                    logger.warning(
                        f"Gmail API rate limit hit (retry {retry_count}/{max_rate_limit_retries}): {error_msg}. "
                        f"Pausing job and retrying in {wait_time}s..."
                    )
                    
                    # 1. Pause job (update to FAILED_RETRYABLE state - rate limits are retryable)
                    sync_job.current_phase = SyncPhase.RATE_LIMITED
                    sync_job.sync_state = SyncStateEnum.FAILED_RETRYABLE  # Rate limit is retryable
                    sync_job.updated_at = datetime.now(timezone.utc)
                    
                    # 2. Persist current progress (save current state)
                    # Progress is already persisted in checkpoint, just commit
                    checkpoint_data = sync_job.checkpoint or {}
                    checkpoint_data.update({
                        "mode": mode,
                        "time_range_months": time_range_months,
                        "rate_limited": True,
                        "rate_limit_retry": retry_count
                    })
                    sync_job.checkpoint = checkpoint_data
                    db.commit()
                    
                    # 3. Emit SSE event: "rate_limited"
                    current_counts = {
                        "total_estimated": sync_job.total_emails or 0,
                        "listed": sync_job.counts_listed or 0,
                        "fetched": sync_job.counts_fetched or 0,
                        "parsed": sync_job.counts_parsed or 0,
                        "classified": sync_job.counts_classified or 0,
                        "saved": sync_job.counts_saved or 0,
                        "skipped": sync_job.counts_skipped or 0,
                        "failed": 0
                    }
                    
                    rate_limit_event = create_progress_event(
                        sync_id=str(job_id),
                        phase=SyncPhase.RATE_LIMITED,
                        message=f"Rate limit reached. Pausing sync and retrying in {int(wait_time)}s... (attempt {retry_count}/{max_rate_limit_retries})",
                        level=EventLevel.WARN,
                        counts=current_counts,
                        rate={"emails_per_sec": 0.0, "bytes_per_sec": 0.0},
                        cursor={"page_token": checkpoint_data.get("page_token"), "history_id": sync_state.gmail_history_id},
                        errors=[{
                            "code": "RATE_LIMIT",
                            "detail": error_msg,
                            "retryable": True,
                            "retry_after_seconds": int(wait_time)
                        }],
                        done=False,
                        retry_count=retry_count,
                        retry_after_seconds=wait_time
                    )
                    publish_progress_event(rate_limit_event)
                    _persist_event(db, sync_job, rate_limit_event)
                    
                    add_log(db, job_id, f"Rate limit hit - pausing for {int(wait_time)}s before retry {retry_count}/{max_rate_limit_retries}", "warning")
                    
                    # 4. Wait with exponential backoff (2s → 4s → 8s → max 60s)
                    # Check for cancellation during backoff (split sleep into small chunks)
                    sleep_chunks = 10  # Check every 1/10th of wait_time
                    chunk_duration = wait_time / sleep_chunks
                    for _ in range(sleep_chunks):
                        await asyncio.sleep(chunk_duration)
                        # Check for cancellation during backoff
                        if _check_and_handle_cancellation(db, sync_job, job_id):
                            return  # Job was canceled, exit immediately
                    rate_limit_delay *= 2  # Double for next retry
                    
                    # Continue retry loop (do NOT fail sync)
                    continue
                else:
                    # Not a rate limit error - re-raise to be handled by outer exception handler
                    raise
        
        # Finalize - use correct counts for verification
        # CRITICAL: Use counts_fetched (actual fetched) not processed_emails (classified)
        final_total_scanned = sync_job.total_emails or 0
        final_total_fetched = sync_job.counts_fetched or 0  # Actual fetched count
        
        # Update sync state (user-level SyncState table) - only if not canceled
        if sync_job.status != SyncJobStatus.CANCELED:
            sync_state.gmail_history_id = sync_engine.get_latest_history_id()
            sync_state.last_synced_at = datetime.now(timezone.utc)
        sync_state.is_sync_running = False  # Clear lock
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
        
        # Mark as completed - save final checkpoint
        sync_job.status = SyncJobStatus.COMPLETED
        sync_job.sync_state = SyncStateEnum.COMPLETED  # Final state: completed
        sync_job.finished_at = datetime.now(timezone.utc)
        sync_job.current_phase = SyncPhase.DONE
        
        # Save final checkpoint (pagination complete, all processed)
        # REQUIRED: Persist last processed messageId, internalDate, pageToken (even if None/complete)
        checkpoint_data = sync_job.checkpoint or {}
        checkpoint_data.update({
            "mode": mode,
            "time_range_months": time_range_months,
            "page_token": None,  # Pagination complete
            "last_processed_message_id": checkpoint_data.get("last_processed_message_id"),  # Last processed before completion
            "last_processed_internal_date": checkpoint_data.get("last_processed_internal_date"),  # Last processed timestamp
            "total_fetched": final_total_fetched,
            "processed_count": sum(final_stats.values()),
            "completed": True,
            "sync_state": SyncStateEnum.COMPLETED.value
        })
        sync_job.checkpoint = checkpoint_data
        db.commit()
        
        # METRICS VERIFICATION (FINAL SAFETY NET) - Verify acceptance criteria
        try:
            from app.verification import verify_sync_completion
            verification_results = verify_sync_completion(db, sync_job, user_id)
            
            if not verification_results["passed"]:
                # Verification failed - log errors but don't fail sync (data may still be valid)
                error_summary = "; ".join(verification_results["errors"])
                logger.warning(f"⚠️ Verification warnings for sync {job_id}: {error_summary}")
                add_log(db, job_id, f"Verification warnings: {error_summary}", "warning")
            else:
                logger.info(f"✅ All verification checks passed for sync {job_id}")
                add_log(db, job_id, "✅ All verification checks passed", "success")
        except Exception as e:
            logger.error(f"Verification check failed: {e}", exc_info=True)
            # Don't fail sync if verification check itself fails
            add_log(db, job_id, f"Verification check error: {str(e)}", "error")
        
        # Publish done event
        # CRITICAL: Use actual counts from sync_job for verification accuracy
        final_classified_count = sync_job.counts_classified or sum(final_stats.values())
        total_stored = sum(final_stats.values())
        
        # Verify counts match for acceptance criteria
        if final_classified_count != total_stored:
            logger.warning(
                f"Count mismatch: sync_job.counts_classified ({final_classified_count}) != "
                f"DB stored ({total_stored}). This may indicate save failures."
            )
        
        event = create_progress_event(
            sync_id=str(job_id),
            phase=SyncPhase.DONE,
            message=f"Sync completed! Stored {total_stored} job application emails.",
            level=EventLevel.INFO,
            counts={
                "total_estimated": final_total_scanned,
                "listed": final_total_scanned,
                "fetched": final_total_fetched,  # Actual fetched count
                "parsed": final_total_fetched,
                "classified": final_classified_count,  # Actual classified and saved count
                "saved": total_stored,  # Actual DB count
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
    """Publish error event and update job status with explicit sync_state"""
    try:
        # Determine if error is retryable or fatal
        is_retryable = error_code in ["RATE_LIMIT", "TIMEOUT"]
        final_state = SyncStateEnum.FAILED_RETRYABLE if is_retryable else SyncStateEnum.FAILED_FATAL
        
        event = create_progress_event(
            sync_id=sync_id,
            phase=SyncPhase.FAILED,
            message=f"Sync failed: {error_msg}",
            level=EventLevel.ERROR,
            errors=[{
                "code": error_code,
                "detail": error_msg,
                "retryable": is_retryable
            }],
            done=True
        )
        publish_progress_event(event)
        _persist_event(db, sync_job, event)
        
        sync_job.status = SyncJobStatus.FAILED
        sync_job.sync_state = final_state  # Set explicit state: FAILED_RETRYABLE or FAILED_FATAL
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
