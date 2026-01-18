from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import uuid
import json
import logging
from app.database import GmailSyncJob, GmailSyncJobLog, User, OAuthToken

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(self, user_id: uuid.UUID, user_email: str) -> GmailSyncJob:
        """Create a new sync job. Returns existing job if one is running."""
        # Check for existing running job
        existing_job = self.db.query(GmailSyncJob).filter(
            GmailSyncJob.user_id == user_id,
            GmailSyncJob.status.in_(["QUEUED", "RUNNING"])
        ).first()
        
        if existing_job:
            # Check if lock expired
            if existing_job.lock_expires_at and existing_job.lock_expires_at < datetime.now(timezone.utc):
                logger.warning(f"Existing job {existing_job.id} lock expired, marking as failed")
                existing_job.status = "FAILED"
                existing_job.error_message = "Job lock expired (process may have crashed)"
                self.db.commit()
            else:
                # Return existing job
                return existing_job
        
        # Create new job
        job = GmailSyncJob(
            user_id=user_id,
            gmail_account_email=user_email,
            status="QUEUED",
            lock_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            heartbeat_at=datetime.now(timezone.utc)
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        self.log(job.id, "INFO", f"Sync job created for {user_email}")
        return job
    
    def start_job(self, job_id: uuid.UUID) -> None:
        """Mark job as RUNNING and set lock."""
        job = self.db.query(GmailSyncJob).filter(GmailSyncJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.status = "RUNNING"
        job.phase = "FETCHING"
        job.started_at = datetime.now(timezone.utc)
        job.lock_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        job.heartbeat_at = datetime.now(timezone.utc)
        self.db.commit()
        
        self.log(job_id, "INFO", "Sync job started")
    
    def update_progress(
        self,
        job_id: uuid.UUID,
        emails_fetched: Optional[int] = None,
        emails_classified: Optional[int] = None,
        applications_stored: Optional[int] = None,
        skipped: Optional[int] = None,
        category_counts: Optional[Dict[str, int]] = None,
        total_estimated: Optional[int] = None,
        phase: Optional[str] = None
    ) -> None:
        """Update job progress counters."""
        job = self.db.query(GmailSyncJob).filter(GmailSyncJob.id == job_id).first()
        if not job:
            return
        
        if emails_fetched is not None:
            job.emails_fetched = emails_fetched
        if emails_classified is not None:
            job.emails_classified = emails_classified
        if applications_stored is not None:
            job.applications_stored = applications_stored
        if skipped is not None:
            job.skipped_messages = skipped
        if category_counts is not None:
            job.category_counts = json.dumps(category_counts)
        if total_estimated is not None:
            job.total_messages_estimated = total_estimated
        if phase is not None:
            job.phase = phase
        
        # Update ETA
        self._update_eta(job)
        
        # Update heartbeat
        job.heartbeat_at = datetime.now(timezone.utc)
        job.lock_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        job.updated_at = datetime.now(timezone.utc)
        self.db.commit()
    
    def _update_eta(self, job: GmailSyncJob) -> None:
        """Calculate ETA based on processing rate."""
        if not job.started_at:
            return
        
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        if elapsed < 5:  # Need at least 5 seconds of data
            return
        
        if job.emails_fetched > 0:
            rate = job.emails_fetched / elapsed
            job.rate_per_sec = rate
            
            if job.total_messages_estimated and job.total_messages_estimated > job.emails_fetched:
                remaining = job.total_messages_estimated - job.emails_fetched
                job.eta_seconds = int(remaining / rate) if rate > 0 else None
    
    def complete_job(self, job_id: uuid.UUID) -> None:
        """Mark job as COMPLETED."""
        job = self.db.query(GmailSyncJob).filter(GmailSyncJob.id == job_id).first()
        if not job:
            return
        
        job.status = "COMPLETED"
        job.phase = "FINALIZING"
        job.finished_at = datetime.now(timezone.utc)
        job.lock_expires_at = None
        job.eta_seconds = None
        self.db.commit()
        
        self.log(job_id, "INFO", "Sync job completed successfully")
    
    def fail_job(self, job_id: uuid.UUID, error_message: str) -> None:
        """Mark job as FAILED."""
        job = self.db.query(GmailSyncJob).filter(GmailSyncJob.id == job_id).first()
        if not job:
            return
        
        job.status = "FAILED"
        job.error_message = error_message
        job.finished_at = datetime.now(timezone.utc)
        job.lock_expires_at = None
        self.db.commit()
        
        self.log(job_id, "ERROR", f"Sync job failed: {error_message}")
    
    def log(self, job_id: uuid.UUID, level: str, message: str) -> None:
        """Add a log entry to the job."""
        job = self.db.query(GmailSyncJob).filter(GmailSyncJob.id == job_id).first()
        if not job:
            return
        
        job.last_log_seq += 1
        log_entry = GmailSyncJobLog(
            job_id=job_id,
            seq=job.last_log_seq,
            level=level,
            message=message
        )
        self.db.add(log_entry)
        self.db.commit()
        
        # Also log to application logger
        if level == "ERROR":
            logger.error(f"Job {job_id}: {message}")
        elif level == "WARN":
            logger.warning(f"Job {job_id}: {message}")
        else:
            logger.info(f"Job {job_id}: {message}")
