from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.gmail_client import GmailClient
from app.sync_engine import SyncEngine
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import get_db, init_db, User, Application, SyncState
from app.ghosted_detector import GhostedDetector
from datetime import datetime, timedelta
import os
import uuid
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# In-memory sync jobs (for progress tracking)
sync_jobs: dict = {}

class SyncStartRequest(BaseModel):
    user_id: str
    user_email: str  # Authenticated user email for validation

class ClearRequest(BaseModel):
    user_id: str

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
            if sync_state.sync_lock_expires_at and sync_state.sync_lock_expires_at > datetime.utcnow():
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
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@app.post("/sync/start")
async def start_sync(
    request: SyncStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start Gmail sync
    NO sync skipping unless explicitly locked
    """
    user_email = request.user_email
    
    # Validate user_id matches email (user_id is email in JWT)
    if request.user_id != user_email:
        raise HTTPException(status_code=403, detail="User ID does not match authenticated email")
    
    # Get or create user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(email=user_email)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Check for existing lock
    sync_state = db.query(SyncState).filter(SyncState.user_id == user.id).first()
    if sync_state and sync_state.is_sync_running:
        if sync_state.sync_lock_expires_at and sync_state.sync_lock_expires_at > datetime.utcnow():
            raise HTTPException(
                status_code=409,
                detail=f"Sync already running: {sync_state.lock_job_id}"
            )
        else:
            # Lock expired, clear it
            sync_state.is_sync_running = False
            sync_state.sync_lock_expires_at = None
    
    # Create new job
    job_id = str(uuid.uuid4())
    
    # Set lock with TTL (10 minutes)
    if not sync_state:
        sync_state = SyncState(user_id=user.id)
        db.add(sync_state)
    
    sync_state.is_sync_running = True
    sync_state.sync_lock_expires_at = datetime.utcnow() + timedelta(minutes=10)
    sync_state.lock_job_id = job_id
    db.commit()
    
    # Initialize sync job (store both email and DB ID for lookup)
    sync_jobs[job_id] = {
        "user_id": user.id,  # Database ID
        "user_email": user_email,  # Email for validation
        "status": "running",
        "total_scanned": 0,
        "total_fetched": 0,
        "candidate_job_emails": 0,
        "classified": {},
        "skipped": 0,
    }
    
    # Start sync in background
    background_tasks.add_task(run_sync, job_id, user.id, user_email, db)
    
    return {"job_id": job_id, "status": "started"}

async def run_sync(job_id: str, user_id: int, user_email: str, db: Session):
    """
    Run Gmail sync - fetches ALL emails, no limits. user_id=DB id, user_email for validation.
    """
    try:
        sync_jobs[job_id]["status"] = "running"
        logger.info(f"Starting sync for user {user_id} (job {job_id})")
        
        # Get user's OAuth tokens (in production, fetch from secure storage)
        # For now, this is a placeholder
        
        # Initialize Gmail client
        gmail_client = GmailClient(user_id, user_email)
        
        # Validate email ownership
        gmail_email = await gmail_client.get_user_email()
        if gmail_email.lower() != user_email.lower():
            logger.error(f"Email mismatch: {user_email} != {gmail_email}")
            raise Exception(f"Gmail email ({gmail_email}) does not match authenticated user ({user_email})")
        
        # Initialize sync engine
        sync_engine = SyncEngine(gmail_client, classifier, company_extractor, db)
        
        # Get sync state
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if not sync_state:
            sync_state = SyncState(user_id=user_id)
            db.add(sync_state)
            db.commit()
        
        # Run sync - fetches ALL emails
        is_incremental = sync_state.gmail_history_id is not None
        
        async for progress in sync_engine.sync_all_emails(user_id, sync_state.gmail_history_id):
            sync_jobs[job_id].update({
                "total_scanned": progress.get("total_scanned", 0),
                "total_fetched": progress.get("total_fetched", 0),
                "candidate_job_emails": progress.get("candidate_job_emails", 0),
                "classified": progress.get("classified", {}),
                "skipped": progress.get("skipped", 0),
            })
        
        # Update sync state
        final_progress = sync_jobs[job_id]
        sync_state.gmail_history_id = sync_engine.get_latest_history_id()
        sync_state.last_synced_at = datetime.utcnow()
        sync_state.is_sync_running = False
        sync_state.sync_lock_expires_at = None
        db.commit()
        
        # Mark as completed
        sync_jobs[job_id]["status"] = "completed"
        
        cl = final_progress.get("classified", {})
        logger.info(
            f"Fetched: {final_progress['total_fetched']} emails. "
            f"Job-related candidates: {final_progress.get('candidate_job_emails', 0)}. "
            f"Applied: {cl.get('applied', 0)}, Rejected: {cl.get('rejected', 0)}, "
            f"Interview: {cl.get('interview', 0)}, Offer: {cl.get('offer', 0)}, "
            f"Ghosted: {cl.get('ghosted', 0)}. Skipped: {final_progress.get('skipped', 0)}."
        )
        
    except Exception as e:
        logger.error(f"Sync error for job {job_id}: {e}", exc_info=True)
        sync_jobs[job_id]["status"] = "failed"
        sync_jobs[job_id]["error"] = str(e)
        
        # Release lock
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if sync_state:
            sync_state.is_sync_running = False
            sync_state.sync_lock_expires_at = None
            db.commit()

@app.get("/sync/progress/{job_id}")
async def get_sync_progress(job_id: str, user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Get sync progress (for polling)
    Returns real-time counts from backend
    """
    if job_id not in sync_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = sync_jobs[job_id]
    
    # Validate user (user_id is email from JWT)
    if job.get("user_email") != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Get applications count from DB
    applications_count = db.query(Application).filter(Application.user_id == job["user_id"]).count()
    
    return {
        "status": job["status"],
        "total_scanned": job["total_scanned"],
        "total_fetched": job["total_fetched"],
        "candidate_job_emails": job.get("candidate_job_emails", 0),
        "classified": job["classified"],
        "skipped": job.get("skipped", 0),
        "applications_count": applications_count,
        "stats": calculate_stats(db, job["user_id"]),
    }

def calculate_stats(db: Session, user_id: int) -> dict:
    """
    Returns REAL counts from DB, never estimated.
    Five categories: applied, rejected, interview, offer (includes legacy "accepted"), ghosted.
    """
    stats = {
        "total": db.query(Application).filter(Application.user_id == user_id).count(),
        "applied": db.query(Application).filter(
            Application.user_id == user_id, Application.category == "applied"
        ).count(),
        "rejected": db.query(Application).filter(
            Application.user_id == user_id, Application.category == "rejected"
        ).count(),
        "interview": db.query(Application).filter(
            Application.user_id == user_id, Application.category == "interview"
        ).count(),
        "offer": db.query(Application).filter(
            Application.user_id == user_id,
            Application.category.in_(["offer", "accepted"])
        ).count(),
        "ghosted": db.query(Application).filter(
            Application.user_id == user_id, Application.category == "ghosted"
        ).count(),
    }
    return stats

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
            query = query.filter(Application.category == status.lower())
        
        applications = query.order_by(Application.received_at.desc()).all()
        
        # Convert to dict
        apps_data = [
            {
                "id": app.id,
                "company": app.company_name,
                "role": app.role,
                "status": app.category,
                "subject": app.subject,
                "from": app.from_email,
                "date": app.received_at.isoformat() if app.received_at else None,
                "snippet": app.snippet,
            }
            for app in applications
        ]
        
        # Calculate real counts
        counts = {}
        for app in applications:
            counts[app.category] = counts.get(app.category, 0) + 1
        
        return {
            "applications": apps_data,
            "total": len(apps_data),
            "counts": counts,
            "warning": None,
        }
    except Exception as e:
        logger.error(f"Error getting applications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get applications: {str(e)}")

@app.get("/stats")
async def get_stats(user_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Get dashboard statistics
    Returns REAL counts from backend, never estimated
    """
    try:
        # user_id is email, get database user
        user = db.query(User).filter(User.email == user_id).first()
        if not user:
            return {"total": 0, "applied": 0, "rejected": 0, "interview": 0, "offer": 0, "ghosted": 0}
        return calculate_stats(db, user.id)
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
        
        # Clear sync state
        sync_state = db.query(SyncState).filter(SyncState.user_id == user_id).first()
        if sync_state:
            sync_state.gmail_history_id = None
            sync_state.last_synced_at = None
            sync_state.is_sync_running = False
            sync_state.sync_lock_expires_at = None
            sync_state.lock_job_id = None
        
        db.commit()
        
        # Clear sync jobs for this user
        jobs_to_remove = [
            job_id for job_id, job in sync_jobs.items()
            if job.get("user_id") == user_id
        ]
        for job_id in jobs_to_remove:
            del sync_jobs[job_id]
        
        logger.info(f"Cleared all data for user {user_id}")
        return {"message": "User data cleared"}
    except Exception as e:
        logger.error(f"Error clearing data: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

@app.post("/ghosted/check")
async def check_ghosted(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Background job to check and update ghosted applications
    """
    background_tasks.add_task(ghosted_detector.check_all_users, db)
    return {"message": "Ghosted check started"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "gmail-connector"}
