from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.gmail_client import GmailClient
from app.sync_engine import SyncEngine
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import get_db, init_db, engine, User, Application, SyncState, OAuthToken
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

# In-memory sync jobs (for progress tracking)
sync_jobs: dict = {}

class SyncStartRequest(BaseModel):
    user_id: str
    user_email: str  # Authenticated user email for validation

class ClearRequest(BaseModel):
    user_id: str

<<<<<<< HEAD
class OAuthTokenStoreRequest(BaseModel):
    user_email: str
    access_token: str
    refresh_token: Optional[str] = None
    token_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: Optional[list] = None
    expires_at: Optional[str] = None
=======
class ExportRequest(BaseModel):
    format: str  # csv, xlsx, json, pdf
    category: str  # ALL, APPLIED, REJECTED, INTERVIEW, OFFER, GHOSTED
    dateRange: dict  # { "from": "YYYY-MM-DD" | null, "to": "YYYY-MM-DD" | null }
    fields: List[str]  # List of field names to include
>>>>>>> 374683f21e722a664dcbf5bdb1c3f2b13a84a73c

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
        
        # Get user's OAuth tokens from database
        oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
        if not oauth_token:
            raise Exception(f"No OAuth tokens found for user {user_email}. Please re-authenticate.")
        
        # Check if token is expired and refresh if needed
        if oauth_token.expires_at and oauth_token.expires_at < datetime.utcnow():
            if not oauth_token.refresh_token:
                raise Exception("Access token expired and no refresh token available. Please re-authenticate.")
            # TODO: Implement token refresh logic here
            logger.warning(f"Access token expired for user {user_email}, but refresh not yet implemented")
        
        # Initialize Gmail client with OAuth tokens
        gmail_client = GmailClient(user_id, user_email, oauth_token)
        
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
            except:
                expires_at = datetime.utcnow() + timedelta(hours=1)
        
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
            oauth_token.updated_at = datetime.utcnow()
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
async def health():
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

    running = sum(1 for j in sync_jobs.values() if j.get("status") == "running")
    overall = "ok" if database.get("status") == "ok" else "degraded"

    return {
        "status": overall,
        "service": "gmail-connector",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "uptime_seconds": round(time.time() - _health_start, 2),
        "database": database,
        "classifier_service": classifier_svc,
        "active_sync_jobs": running,
        "total_sync_jobs": len(sync_jobs),
    }
