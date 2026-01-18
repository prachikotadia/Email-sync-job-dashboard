# Cursor Prompt — Real-time Gmail Sync with Live Progress Modal + ETA

## 🎯 MISSION
Implement a production-grade, real-time Gmail sync system that processes 4,000–44,000+ emails reliably. User clicks "Sync" → backend runs a long-running background job → frontend shows a professional modal with live progress, logs, and ETA. Must be Docker-first, cross-platform (Mac + Windows), and handle edge cases gracefully.

---

## 0. NON-NEGOTIABLE REQUIREMENTS

### 0.1 Core Rules
- ✅ **Docker-only**: No OS-specific scripts. Everything runs via `docker-compose`.
- ✅ **Background job**: Sync runs independently of HTTP request lifecycle. Request returns immediately with `jobId`.
- ✅ **Real-time updates**: Frontend shows live progress, logs, and ETA that update every 1-2 seconds.
- ✅ **Survives refresh**: If user refreshes page, frontend reattaches to running job via `GET /gmail/sync/status`.
- ✅ **No deadlocks**: TTL-based locking prevents "sync already running" from blocking forever.
- ✅ **Scalable**: Handles 4,000–44,000+ emails with pagination, batching, and incremental updates.
- ✅ **Error visibility**: All errors shown in log panel with clear messages.

### 0.2 What Must NOT Happen
- ❌ Frontend polling `/gmail/sync/progress/undefined`
- ❌ 503 "Service Unavailable" without clear error message
- ❌ "Sync already running" that never clears
- ❌ Fake progress bars or estimated numbers
- ❌ Sync stopping if user closes modal or navigates away
- ❌ Memory leaks from polling intervals

---

## 1. BACKEND: DATABASE SCHEMA (REQUIRED)

### 1.1 Create `gmail_sync_jobs` Table
**File**: `services/gmail-connector/app/database.py`

Add to database models:

```python
class GmailSyncJob(Base):
    __tablename__ = "gmail_sync_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_account_email = Column(String, nullable=False, index=True)  # Validated email
    
    # Status tracking
    status = Column(String, nullable=False, index=True)  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    phase = Column(String)  # FETCHING, CLASSIFYING, STORING, FINALIZING
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Progress counters
    total_messages_estimated = Column(Integer, nullable=True)  # Null until discovered
    emails_fetched = Column(Integer, default=0, nullable=False)
    emails_classified = Column(Integer, default=0, nullable=False)
    applications_stored = Column(Integer, default=0, nullable=False)
    skipped_messages = Column(Integer, default=0, nullable=False)
    
    # Category breakdown (JSON)
    category_counts = Column(Text)  # JSON: {"applied": 10, "rejected": 5, ...}
    
    # Performance metrics
    rate_per_sec = Column(Float, nullable=True)  # Rolling average processing rate
    eta_seconds = Column(Integer, nullable=True)  # Estimated time remaining
    
    # Logging
    last_log_seq = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Locking (prevent concurrent syncs)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sync_jobs")
    logs = relationship("GmailSyncJobLog", back_populates="job", cascade="all, delete-orphan", order_by="GmailSyncJobLog.seq")
```

### 1.2 Create `gmail_sync_job_logs` Table
**File**: `services/gmail-connector/app/database.py`

```python
class GmailSyncJobLog(Base):
    __tablename__ = "gmail_sync_job_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("gmail_sync_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    seq = Column(Integer, nullable=False, index=True)  # Incrementing sequence number
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    level = Column(String, nullable=False)  # INFO, WARN, ERROR
    message = Column(Text, nullable=False)
    
    # Relationships
    job = relationship("GmailSyncJob", back_populates="logs")
    
    # Composite index for efficient querying
    __table_args__ = (
        Index('idx_job_seq', 'job_id', 'seq'),
    )
```

### 1.3 Update User Model
**File**: `services/gmail-connector/app/database.py`

Add relationship to `User` class:
```python
sync_jobs = relationship("GmailSyncJob", back_populates="user", cascade="all, delete-orphan")
```

### 1.4 Migration
**File**: `services/gmail-connector/app/database.py`

Update `init_db()` to create these tables:
```python
def init_db():
    """Initialize database tables"""
    # ... existing schema check logic ...
    Base.metadata.create_all(bind=engine)
```

---

## 2. BACKEND: JOB WORKER IMPLEMENTATION

### 2.1 Create Job Manager
**File**: `services/gmail-connector/app/job_manager.py` (NEW)

```python
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import uuid
import json
import logging
from app.database import GmailSyncJob, GmailSyncJobLog, User, OAuthToken
from app.sync_engine import SyncEngine
from app.gmail_client import GmailClient
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor

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
```

### 2.2 Update Sync Engine to Use Job Manager
**File**: `services/gmail-connector/app/sync_engine.py`

Modify `sync_all_emails` to accept `job_manager` and `job_id`:

```python
async def sync_all_emails(
    self,
    user_id: uuid.UUID,
    existing_history_id: str = None,
    job_manager: Optional[JobManager] = None,
    job_id: Optional[uuid.UUID] = None
) -> AsyncIterator[Dict]:
    """Sync all emails with job tracking."""
    # ... existing code ...
    
    # Update job progress as we go
    if job_manager and job_id:
        job_manager.log(job_id, "INFO", f"Starting sync: Estimated {total_estimated} emails")
        job_manager.update_progress(job_id, total_estimated=total_estimated, phase="FETCHING")
    
    # ... fetch messages ...
    
    for message in messages:
        # ... process message ...
        if job_manager and job_id:
            job_manager.update_progress(
                job_id,
                emails_fetched=len(processed_messages),
                phase="CLASSIFYING"
            )
            job_manager.log(job_id, "INFO", f"Fetched {len(processed_messages)} emails")
    
    # ... classification ...
    if job_manager and job_id:
        job_manager.update_progress(
            job_id,
            emails_classified=classified_count,
            applications_stored=stored_count,
            skipped=skipped_count,
            category_counts=category_counts,
            phase="STORING"
        )
```

### 2.3 Background Worker Function
**File**: `services/gmail-connector/app/main.py`

Add async worker function:

```python
async def run_sync_job(job_id: uuid.UUID, user_id: uuid.UUID, user_email: str, db: Session):
    """Background worker that runs the sync job."""
    job_manager = JobManager(db)
    
    try:
        # Start job
        job_manager.start_job(job_id)
        
        # Get OAuth tokens
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
        if not oauth_token:
            raise Exception("No OAuth tokens found. Please re-authenticate.")
        
        # Initialize Gmail client
        gmail_client = GmailClient(user_id, user_email, oauth_token)
        
        # Validate email
        gmail_email = await gmail_client.get_user_email()
        if gmail_email.lower() != user_email.lower():
            raise Exception(f"Gmail email mismatch: {gmail_email} != {user_email}")
        
        # Get sync state
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if not sync_state:
            sync_state = SyncState(user_id=user_id)
            db.add(sync_state)
            db.commit()
        
        # Initialize sync engine
        classifier = Classifier()
        company_extractor = CompanyExtractor()
        sync_engine = SyncEngine(gmail_client, classifier, company_extractor, db)
        
        # Run sync with job tracking
        job_manager.log(job_id, "INFO", "Starting Gmail sync...")
        
        async for progress in sync_engine.sync_all_emails(
            user_id,
            sync_state.gmail_history_id,
            job_manager=job_manager,
            job_id=job_id
        ):
            # Progress updates are handled by sync_engine via job_manager
            pass
        
        # Update sync state
        sync_state.gmail_history_id = sync_engine.get_latest_history_id()
        sync_state.last_synced_at = datetime.now(timezone.utc)
        sync_state.is_sync_running = False
        sync_state.sync_lock_expires_at = None
        db.commit()
        
        # Complete job
        job_manager.complete_job(job_id)
        job_manager.log(job_id, "INFO", "Sync completed successfully")
        
    except Exception as e:
        logger.error(f"Sync job {job_id} failed: {e}", exc_info=True)
        job_manager.fail_job(job_id, str(e))
        
        # Release sync lock
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if sync_state:
            sync_state.is_sync_running = False
            sync_state.sync_lock_expires_at = None
            db.commit()
```

---

## 3. BACKEND: API ENDPOINTS

### 3.1 POST /gmail/sync/start
**File**: `services/gmail-connector/app/main.py`

```python
@app.post("/gmail/sync/start")
async def start_sync(
    request: SyncStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a new sync job or return existing running job."""
    user_email = request.user_email
    
    # Get or create user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(email=user_email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create or get existing job
    job_manager = JobManager(db)
    job = job_manager.create_job(user.id, user_email)
    
    # If job is already running, return it
    if job.status == "RUNNING":
        return {
            "jobId": str(job.id),
            "status": job.status,
            "startedAt": job.started_at.isoformat() if job.started_at else None
        }
    
    # Start background task
    background_tasks.add_task(run_sync_job, job.id, user.id, user_email, db)
    
    return {
        "jobId": str(job.id),
        "status": "QUEUED",
        "startedAt": job.started_at.isoformat() if job.started_at else None
    }
```

### 3.2 GET /gmail/sync/status
**File**: `services/gmail-connector/app/main.py`

```python
@app.get("/gmail/sync/status")
async def get_sync_status(
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get current sync job status for user."""
    user = db.query(User).filter(User.email == user_id).first()
    if not user:
        return {"jobId": None, "status": None}
    
    job = db.query(GmailSyncJob).filter(
        GmailSyncJob.user_id == user.id,
        GmailSyncJob.status.in_(["QUEUED", "RUNNING"])
    ).order_by(GmailSyncJob.started_at.desc()).first()
    
    if not job:
        return {"jobId": None, "status": None}
    
    # Parse category counts
    category_counts = {}
    if job.category_counts:
        try:
            category_counts = json.loads(job.category_counts)
        except:
            pass
    
    # Calculate percent
    percent = 0
    if job.total_messages_estimated and job.total_messages_estimated > 0:
        percent = (job.emails_fetched / job.total_messages_estimated) * 100
    
    return {
        "jobId": str(job.id),
        "status": job.status,
        "phase": job.phase,
        "totalEmailsEstimated": job.total_messages_estimated,
        "emailsFetched": job.emails_fetched,
        "emailsClassified": job.emails_classified,
        "applicationsStored": job.applications_stored,
        "skipped": job.skipped_messages,
        "categoryCounts": category_counts,
        "percent": round(percent, 2),
        "etaSeconds": job.eta_seconds,
        "ratePerSec": job.rate_per_sec,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "updatedAt": job.updated_at.isoformat() if job.updated_at else None
    }
```

### 3.3 GET /gmail/sync/progress/{job_id}
**File**: `services/gmail-connector/app/main.py`

```python
@app.get("/gmail/sync/progress/{job_id}")
async def get_sync_progress(
    job_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get progress for a specific job."""
    # Validate job_id
    if not job_id or job_id in ['undefined', 'null', '']:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    
    try:
        job_uuid = uuid.UUID(job_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid job_id format")
    
    job = db.query(GmailSyncJob).filter(GmailSyncJob.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Validate user
    user = db.query(User).filter(User.email == user_id).first()
    if not user or job.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Parse category counts
    category_counts = {}
    if job.category_counts:
        try:
            category_counts = json.loads(job.category_counts)
        except:
            pass
    
    # Calculate percent
    percent = 0
    if job.total_messages_estimated and job.total_messages_estimated > 0:
        percent = (job.emails_fetched / job.total_messages_estimated) * 100
    
    # Get last log message
    last_log = db.query(GmailSyncJobLog).filter(
        GmailSyncJobLog.job_id == job_uuid
    ).order_by(GmailSyncJobLog.seq.desc()).first()
    
    last_message = last_log.message if last_log else None
    
    return {
        "jobId": str(job.id),
        "state": job.status,
        "phase": job.phase,
        "totalEmailsEstimated": job.total_messages_estimated,
        "emailsFetched": job.emails_fetched,
        "emailsClassified": job.emails_classified,
        "applicationsCreatedOrUpdated": job.applications_stored,
        "skipped": job.skipped_messages,
        "categoryCounts": category_counts,
        "percent": round(percent, 2),
        "etaSeconds": job.eta_seconds,
        "ratePerSec": job.rate_per_sec,
        "lastMessage": last_message,
        "updatedAt": job.updated_at.isoformat() if job.updated_at else None,
        "errorMessage": job.error_message
    }
```

### 3.4 GET /gmail/sync/logs/{job_id}
**File**: `services/gmail-connector/app/main.py`

```python
@app.get("/gmail/sync/logs/{job_id}")
async def get_sync_logs(
    job_id: str,
    after_seq: int = Query(0),
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get logs for a job after a specific sequence number."""
    # Validate job_id
    if not job_id or job_id in ['undefined', 'null', '']:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    
    try:
        job_uuid = uuid.UUID(job_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid job_id format")
    
    job = db.query(GmailSyncJob).filter(GmailSyncJob.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Validate user
    user = db.query(User).filter(User.email == user_id).first()
    if not user or job.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Get logs
    logs = db.query(GmailSyncJobLog).filter(
        GmailSyncJobLog.job_id == job_uuid,
        GmailSyncJobLog.seq > after_seq
    ).order_by(GmailSyncJobLog.seq.asc()).limit(1000).all()
    
    return {
        "jobId": str(job.id),
        "logs": [
            {
                "seq": log.seq,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message
            }
            for log in logs
        ],
        "lastSeq": logs[-1].seq if logs else after_seq
    }
```

### 3.5 POST /gmail/sync/cancel/{job_id} (Optional)
**File**: `services/gmail-connector/app/main.py`

```python
@app.post("/gmail/sync/cancel/{job_id}")
async def cancel_sync(
    job_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Cancel a running sync job."""
    # Validate and get job (similar to get_sync_progress)
    # Mark job as CANCELLED
    # Release locks
    # Return success
```

---

## 4. API GATEWAY ROUTES

### 4.1 Update API Gateway Routes
**File**: `services/api-gateway/app/routers/gmail.py`

Add/update routes:

```python
@router.post("/sync/start")
async def start_sync(token_data: dict = Depends(verify_token)):
    """Start Gmail sync job."""
    user_id = token_data.get("sub")
    user_email = token_data.get("email")
    
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/gmail/sync/start",
                json={"user_id": user_id, "user_email": user_email}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/sync/status")
async def get_sync_status(token_data: dict = Depends(verify_token)):
    """Get current sync status for user."""
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/gmail/sync/status",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/sync/progress/{job_id}")
async def get_sync_progress(job_id: str, token_data: dict = Depends(verify_token)):
    """Get sync progress for a job."""
    # Validate job_id
    if not job_id or job_id in ['undefined', 'null', '']:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    
    user_id = token_data.get("sub")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/gmail/sync/progress/{job_id}",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")

@router.get("/sync/logs/{job_id}")
async def get_sync_logs(
    job_id: str,
    after_seq: int = Query(0),
    token_data: dict = Depends(verify_token)
):
    """Get sync logs for a job."""
    # Similar implementation
```

---

## 5. FRONTEND: SYNC PROGRESS MODAL

### 5.1 Create SyncProgressModal Component
**File**: `frontend/src/components/SyncProgressModal.jsx` (NEW)

```javascript
import { useEffect, useRef, useState } from 'react'
import { gmailService } from '../services/gmailService'
import { IconRefresh, IconCheck, IconX, IconAlertCircle } from './icons'
import '../styles/SyncProgressModal.css'

export default function SyncProgressModal({ jobId, onClose, onComplete }) {
  const [progress, setProgress] = useState(null)
  const [logs, setLogs] = useState([])
  const [lastLogSeq, setLastLogSeq] = useState(0)
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef(null)
  const pollIntervalRef = useRef(null)
  const logPollIntervalRef = useRef(null)

  // Poll progress every 1-2 seconds
  useEffect(() => {
    if (!jobId) return

    const pollProgress = async () => {
      try {
        const data = await gmailService.getSyncProgress(jobId)
        setProgress(data)
        
        // If completed or failed, stop polling
        if (data.state === 'COMPLETED' || data.state === 'FAILED' || data.state === 'CANCELLED') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
          if (logPollIntervalRef.current) {
            clearInterval(logPollIntervalRef.current)
            logPollIntervalRef.current = null
          }
          if (data.state === 'COMPLETED' && onComplete) {
            onComplete(data)
          }
        }
      } catch (error) {
        console.error('Failed to poll progress:', error)
      }
    }

    pollProgress() // Initial poll
    pollIntervalRef.current = setInterval(pollProgress, 2000) // Poll every 2 seconds

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [jobId, onComplete])

  // Poll logs every 1 second
  useEffect(() => {
    if (!jobId) return

    const pollLogs = async () => {
      try {
        const data = await gmailService.getSyncLogs(jobId, lastLogSeq)
        if (data.logs && data.logs.length > 0) {
          setLogs(prev => [...prev, ...data.logs])
          setLastLogSeq(data.lastSeq)
        }
      } catch (error) {
        console.error('Failed to poll logs:', error)
      }
    }

    pollLogs() // Initial poll
    logPollIntervalRef.current = setInterval(pollLogs, 1000) // Poll every 1 second

    return () => {
      if (logPollIntervalRef.current) {
        clearInterval(logPollIntervalRef.current)
      }
    }
  }, [jobId, lastLogSeq])

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const formatTime = (seconds) => {
    if (!seconds) return 'Calculating...'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  if (!progress) {
    return (
      <div className="sync-progress-modal-overlay">
        <div className="sync-progress-modal">
          <div className="sync-progress-header">
            <IconRefresh className="sync-progress-spinning" />
            <h3>Starting sync...</h3>
          </div>
        </div>
      </div>
    )
  }

  const isComplete = progress.state === 'COMPLETED'
  const isFailed = progress.state === 'FAILED'
  const isRunning = progress.state === 'RUNNING' || progress.state === 'QUEUED'

  return (
    <div className="sync-progress-modal-overlay" onClick={onClose}>
      <div className="sync-progress-modal neo-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="sync-progress-header">
          <div className="sync-progress-title">
            {isRunning && <IconRefresh className="sync-progress-spinning" />}
            {isComplete && <IconCheck className="sync-progress-success" />}
            {isFailed && <IconAlertCircle className="sync-progress-error" />}
            <h3>
              {isRunning && 'Syncing your Gmail...'}
              {isComplete && 'Sync Complete'}
              {isFailed && 'Sync Failed'}
            </h3>
          </div>
          <button className="sync-progress-close" onClick={onClose}>
            <IconX />
          </button>
        </div>

        {/* Subtitle */}
        <p className="sync-progress-subtitle">
          {isRunning && 'Please wait while we sync your data.'}
          {isComplete && 'Your Gmail has been successfully synced.'}
          {isFailed && progress.errorMessage}
        </p>

        {/* Progress Bar */}
        {isRunning && (
          <div className="sync-progress-bar-container">
            <div className="sync-progress-bar">
              <div
                className="sync-progress-bar-fill"
                style={{ width: `${Math.min(progress.percent || 0, 100)}%` }}
              />
            </div>
            <div className="sync-progress-bar-text">
              {progress.totalEmailsEstimated
                ? `Emails processed: ${progress.emailsFetched.toLocaleString()} / ${progress.totalEmailsEstimated.toLocaleString()}`
                : `Processing: ${progress.emailsFetched.toLocaleString()} emails...`}
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="sync-progress-stats">
          <div className="sync-progress-stat">
            <span className="stat-label">Total Emails</span>
            <span className="stat-value">{progress.totalEmailsEstimated?.toLocaleString() || '—'}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Fetched</span>
            <span className="stat-value">{progress.emailsFetched.toLocaleString()}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Classified</span>
            <span className="stat-value">{progress.emailsClassified.toLocaleString()}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Stored</span>
            <span className="stat-value">{progress.applicationsCreatedOrUpdated.toLocaleString()}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Skipped</span>
            <span className="stat-value">{progress.skipped.toLocaleString()}</span>
          </div>
          {isRunning && progress.etaSeconds && (
            <div className="sync-progress-stat">
              <span className="stat-label">ETA</span>
              <span className="stat-value">{formatTime(progress.etaSeconds)}</span>
            </div>
          )}
        </div>

        {/* Category Breakdown */}
        {progress.categoryCounts && Object.keys(progress.categoryCounts).length > 0 && (
          <div className="sync-progress-categories">
            <h4>Applications by Category</h4>
            <div className="sync-progress-category-badges">
              {Object.entries(progress.categoryCounts).map(([category, count]) => (
                <span key={category} className="category-badge">
                  {category}: {count}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Logs Panel */}
        <div className="sync-progress-logs-section">
          <div className="sync-progress-logs-header">
            <h4>Sync Logs</h4>
            <label className="auto-scroll-toggle">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              Auto-scroll
            </label>
          </div>
          <div
            className="sync-progress-logs"
            ref={logContainerRef}
            onScroll={() => {
              // Stop auto-scroll if user scrolls up
              if (logContainerRef.current) {
                const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
                if (scrollTop + clientHeight < scrollHeight - 50) {
                  setAutoScroll(false)
                }
              }
            }}
          >
            {logs.length === 0 ? (
              <div className="log-entry">Waiting for logs...</div>
            ) : (
              logs.map((log, index) => (
                <div key={`${log.seq}-${index}`} className={`log-entry log-${log.level.toLowerCase()}`}>
                  <span className="log-time">[{formatTimestamp(log.timestamp)}]</span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="sync-progress-actions">
          <button className="btn-secondary" onClick={onClose}>
            {isRunning ? 'Close (sync continues)' : 'Close'}
          </button>
          {isFailed && (
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Retry Sync
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
```

### 5.2 Update gmailService
**File**: `frontend/src/services/gmailService.js`

Add new methods:

```javascript
async startSync() {
  try {
    const response = await apiClient.post('/gmail/sync/start')
    const data = response.data
    
    // Validate jobId
    if (!data.jobId) {
      throw new Error('Backend did not return jobId')
    }
    
    return data
  } catch (error) {
    if (error.response?.status === 409) {
      const message = error.response.data?.detail || 'Sync is already running'
      throw new Error(message)
    }
    throw error
  }
},

async getSyncStatus() {
  try {
    const response = await apiClient.get('/gmail/sync/status')
    return response.data
  } catch (error) {
    throw error
  }
},

async getSyncProgress(jobId) {
  // STRICT GUARD
  if (!jobId || jobId === 'undefined' || jobId === 'null') {
    throw new Error('Cannot get sync progress: jobId is invalid')
  }
  
  try {
    const response = await apiClient.get(`/gmail/sync/progress/${jobId}`)
    return response.data
  } catch (error) {
    throw error
  }
},

async getSyncLogs(jobId, afterSeq = 0) {
  // STRICT GUARD
  if (!jobId || jobId === 'undefined' || jobId === 'null') {
    throw new Error('Cannot get sync logs: jobId is invalid')
  }
  
  try {
    const response = await apiClient.get(`/gmail/sync/logs/${jobId}`, {
      params: { after_seq: afterSeq }
    })
    return response.data
  } catch (error) {
    throw error
  }
}
```

### 5.3 Update Dashboard
**File**: `frontend/src/pages/Dashboard.jsx`

Update sync button handler:

```javascript
const [syncJobId, setSyncJobId] = useState(null)
const [showSyncModal, setShowSyncModal] = useState(false)

const handleStartSync = async () => {
  if (syncCheckRef.current) return
  syncCheckRef.current = true

  try {
    setError(null)
    
    // Check for existing job first
    const status = await gmailService.getSyncStatus()
    if (status.jobId && (status.status === 'RUNNING' || status.status === 'QUEUED')) {
      // Attach to existing job
      setSyncJobId(status.jobId)
      setShowSyncModal(true)
      return
    }
    
    // Start new sync
    const result = await gmailService.startSync()
    
    if (!result.jobId) {
      throw new Error('Sync started but no jobId returned')
    }
    
    setSyncJobId(result.jobId)
    setShowSyncModal(true)
  } catch (err) {
    setError(err.message || 'Failed to start sync')
  } finally {
    syncCheckRef.current = false
  }
}

// On page load, check for running job
useEffect(() => {
  if (isGuest) return
  
  const checkRunningJob = async () => {
    try {
      const status = await gmailService.getSyncStatus()
      if (status.jobId && (status.status === 'RUNNING' || status.status === 'QUEUED')) {
        setSyncJobId(status.jobId)
        setShowSyncModal(true)
      }
    } catch (err) {
      // Ignore errors on status check
    }
  }
  
  checkRunningJob()
}, [isGuest])

// Render modal
{showSyncModal && syncJobId && (
  <SyncProgressModal
    jobId={syncJobId}
    onClose={() => setShowSyncModal(false)}
    onComplete={(progress) => {
      setShowSyncModal(false)
      loadInitialData() // Refresh dashboard
    }}
  />
)}
```

### 5.4 Create CSS
**File**: `frontend/src/styles/SyncProgressModal.css` (NEW)

```css
.sync-progress-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.2s ease-out;
}

.sync-progress-modal {
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.3s ease-out;
  overflow: hidden;
}

.sync-progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border-bottom: 1px solid var(--border-color);
}

.sync-progress-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sync-progress-title h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
}

.sync-progress-spinning {
  animation: spin 1s linear infinite;
  color: var(--accent-primary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.sync-progress-success {
  color: #16a34a;
}

.sync-progress-error {
  color: #dc2626;
}

.sync-progress-subtitle {
  padding: 16px 24px;
  margin: 0;
  color: var(--text-secondary);
}

.sync-progress-bar-container {
  padding: 20px 24px;
}

.sync-progress-bar {
  width: 100%;
  height: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.sync-progress-bar-fill {
  height: 100%;
  background: var(--accent-primary);
  transition: width 0.3s ease;
}

.sync-progress-bar-text {
  font-size: 0.875rem;
  color: var(--text-secondary);
  text-align: center;
}

.sync-progress-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
  padding: 20px 24px;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.sync-progress-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.sync-progress-categories {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
}

.sync-progress-categories h4 {
  margin: 0 0 12px 0;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sync-progress-category-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.category-badge {
  padding: 4px 12px;
  background: var(--bg-secondary);
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 600;
}

.sync-progress-logs-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px 24px;
  overflow: hidden;
}

.sync-progress-logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sync-progress-logs-header h4 {
  margin: 0;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.auto-scroll-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.sync-progress-logs {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  max-height: 300px;
}

.log-entry {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  word-break: break-word;
}

.log-time {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.log-message {
  color: var(--text-primary);
  flex: 1;
}

.log-entry.log-info .log-message {
  color: var(--text-primary);
}

.log-entry.log-warn .log-message {
  color: #f59e0b;
}

.log-entry.log-error .log-message {
  color: #dc2626;
}

.sync-progress-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid var(--border-color);
}

.btn-primary, .btn-secondary {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--accent-primary);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-tertiary);
}
```

---

## 6. TESTING CHECKLIST

### 6.1 Manual Testing Steps

1. **Start Services**
   ```bash
   docker-compose up --build
   ```

2. **Open Frontend**
   - Navigate to `http://localhost:3000`
   - Login with Google OAuth

3. **Start Sync**
   - Click "Sync Emails" button
   - Modal should open immediately
   - Progress should start updating within 2 seconds

4. **Test Real-time Updates**
   - Watch progress bar increment
   - Watch stats update
   - Watch logs stream in
   - Verify ETA appears after totals are known

5. **Test Refresh Recovery**
   - While sync is running, refresh the page
   - Modal should reopen and attach to running job
   - Progress should continue from where it left off

6. **Test Modal Close**
   - Close modal while sync is running
   - Sync should continue in background
   - Reopen modal → should show current progress

7. **Test Completion**
   - Wait for sync to complete
   - Modal should show "Complete" status
   - Final counts should be displayed
   - Logs should be fully visible

8. **Test Error Handling**
   - Simulate backend error (stop gmail-connector service)
   - Modal should show error message
   - Retry button should be available

### 6.2 Verification Points

- ✅ No requests to `/gmail/sync/progress/undefined`
- ✅ Progress updates every 1-2 seconds
- ✅ ETA calculates correctly and updates
- ✅ Logs stream in real-time
- ✅ Modal survives page refresh
- ✅ Sync continues if modal is closed
- ✅ Large mailboxes (4k+) process correctly
- ✅ No memory leaks from polling
- ✅ Lock TTL prevents deadlocks

---

## 7. FILES TO CREATE/MODIFY

### Backend Files
- `services/gmail-connector/app/database.py` - Add job models
- `services/gmail-connector/app/job_manager.py` - NEW
- `services/gmail-connector/app/main.py` - Add endpoints
- `services/gmail-connector/app/sync_engine.py` - Integrate job tracking
- `services/api-gateway/app/routers/gmail.py` - Add routes

### Frontend Files
- `frontend/src/components/SyncProgressModal.jsx` - NEW
- `frontend/src/styles/SyncProgressModal.css` - NEW
- `frontend/src/services/gmailService.js` - Add methods
- `frontend/src/pages/Dashboard.jsx` - Update sync flow

---

## 8. MANUAL STEPS AFTER IMPLEMENTATION

1. **Rebuild Docker containers:**
   ```bash
   docker-compose down
   docker-compose up --build
   ```

2. **Verify services are running:**
   ```bash
   docker-compose ps
   ```
   All services should show "healthy" or "running"

3. **Clear browser cache** (if needed):
   - Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

4. **Test with real Gmail account:**
   - Connect Gmail via OAuth
   - Click "Sync Emails"
   - Verify modal appears and updates

---

## 9. ACCEPTANCE CRITERIA

- [ ] Modal opens immediately when sync starts
- [ ] Progress bar updates in real-time
- [ ] Stats counters update continuously
- [ ] Logs stream in real-time with timestamps
- [ ] ETA appears and updates correctly
- [ ] Modal survives page refresh
- [ ] Sync continues if modal is closed
- [ ] No undefined jobId errors
- [ ] Handles 4,000+ emails without issues
- [ ] Error messages are clear and actionable
- [ ] Works on both Mac and Windows via Docker

---

**END OF PROMPT**
