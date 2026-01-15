from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.application import ProcessedEmail, IngestResponse
from app.services.upsert_logic import UpsertLogic
from app.db.supabase import get_db
from app.models import Email, ApplicationEvent, User
from datetime import datetime
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/from-email-ai", response_model=IngestResponse)
def ingest_from_email_ai(
    emails: List[ProcessedEmail], 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    RULE 8: Internal ingest endpoint that stores emails and events.
    
    Stores:
    - Emails in emails table
    - Events in application_events table
    - Updates applications via UpsertLogic
    
    CRITICAL: Sets user_id on all applications to ensure they're visible to the user.
    """
    # CRITICAL: Log initial state
    emails_received = len(emails)
    logger.info(f"📥 [INGEST START] Received {emails_received} emails from gmail-connector")
    logger.info(f"📊 [DATA FLOW] Received from gmail-connector: {emails_received} emails")
    logger.info(f"📊 [DATA FLOW] NO LIMIT on ingest - processing ALL emails")
    logger.info(f"📊 [DATA FLOW] User ID: {x_user_id or 'NONE'}")
    
    # CRITICAL: Track counts for validation
    emails_processed = 0
    emails_stored_count = 0
    applications_created = 0
    applications_updated = 0
    errors_count = 0
    
    # Get or create user from user_id header
    user_id_uuid = None
    if x_user_id:
        try:
            user_id_uuid = uuid.UUID(x_user_id)
            # Get or create user
            user = db.query(User).filter(User.id == user_id_uuid).first()
            if not user:
                # Try to get user email from first email's to_email
                user_email = emails[0].to_email if emails else None
                if user_email:
                    user = db.query(User).filter(User.email == user_email).first()
                    if not user:
                        user = User(id=user_id_uuid, email=user_email)
                        db.add(user)
                        db.flush()
                        logger.info(f"✅ Created user {user_id_uuid} with email {user_email}")
            if user:
                user_id_uuid = user.id
                logger.info(f"✅ Using user_id: {user_id_uuid}")
        except Exception as e:
            logger.warning(f"⚠️  Invalid user_id header: {x_user_id}, error: {e}")
    
    logic = UpsertLogic(db, user_id=user_id_uuid)
    
    # Track if application was newly created
    existing_app_ids = set()
    db.execute(select(Application.id)).scalars().all()
    for app in db.query(Application).all():
        existing_app_ids.add(app.id)
    
    for idx, email in enumerate(emails, 1):
        try:
            emails_processed += 1
            logger.info(f"  [{idx}/{emails_received}] Processing: {email.company_name} - {email.role} ({email.application_status})")
            
            # 1. Upsert application (existing logic)
            received_at_dt = email.received_at
            if isinstance(received_at_dt, str):
                received_at_dt = datetime.fromisoformat(received_at_dt.replace('Z', '+00:00'))
            
            app = logic.process(
                company_name=email.company_name,
                role_title=email.role,
                status=email.application_status,
                confidence=email.confidence_score,
                email_date=received_at_dt
            )
            
            # Track if this is a new application
            if app.id not in existing_app_ids:
                applications_created += 1
                existing_app_ids.add(app.id)
                logger.info(f"  ✅ Created NEW application: {app.id} ({email.company_name} - {email.role})")
            else:
                applications_updated += 1
            
            # 2. RULE 8: Store email in emails table
            try:
                # Check if email already exists (by gmail_message_id)
                existing_email = db.query(Email).filter(
                    Email.gmail_message_id == email.email_id
                ).first()
                
                email_record = None
                if not existing_email:
                    email_record = Email(
                        id=uuid.uuid4(),
                        user_id=app.user_id,
                        application_id=app.id,
                        gmail_message_id=email.email_id,
                        thread_id=email.thread_id or f"thread_{email.email_id}",
                        subject=email.subject or "No Subject",
                        from_email=email.from_email or "Unknown",
                        to_email=email.to_email,
                        body_text=email.body_text,
                        received_at=received_at_dt,
                        internal_date=email.internal_date,
                        status=email.application_status,
                        confidence_score=email.confidence_score,
                        company_name=email.company_name,
                        role_title=email.role
                    )
                    db.add(email_record)
                    db.flush()  # Flush to get email_record.id
                    emails_stored_count += 1
                    logger.info(f"  ✅ Stored email ID: {email_record.id} (gmail_message_id: {email.email_id})")
                else:
                    email_record = existing_email
                    logger.info(f"  ℹ️  Email already exists: {email_record.id}")
                
                # 3. RULE 8: Create application event
                event = ApplicationEvent(
                    id=uuid.uuid4(),
                    application_id=app.id,
                    email_id=email_record.id,
                    event_type=email.application_status,
                    event_date=received_at_dt,
                    confidence_score=email.confidence_score,
                    metadata={
                        "company_name": email.company_name,
                        "role": email.role,
                        "subject": email.subject,
                        "summary": email.summary
                    }
                )
                db.add(event)
                events_created += 1
                logger.info(f"  ✅ Created event ID: {event.id}")
                
            except Exception as email_error:
                logger.error(f"  ⚠️  Error storing email/event: {email_error}", exc_info=True)
                # Continue even if email/event storage fails
            
            db.commit()
            logger.info(f"  ✅ Stored application ID: {app.id}")
            
        except Exception as e:
            logger.error(f"  ❌ Ingest error for {email.company_name}: {e}", exc_info=True)
            db.rollback()
            errors_count += 1
    
    # CRITICAL: Final validation and logging
    logger.info(f"")
    logger.info(f"📊 [INGEST COMPLETE] ========================================")
    logger.info(f"📊 [INGEST] Emails received: {emails_received}")
    logger.info(f"📊 [INGEST] Emails processed: {emails_processed}")
    logger.info(f"📊 [INGEST] Emails stored: {emails_stored_count}")
    logger.info(f"📊 [INGEST] Applications created: {applications_created}")
    logger.info(f"📊 [INGEST] Applications updated: {applications_updated}")
    logger.info(f"📊 [INGEST] Events created: {events_created}")
    logger.info(f"📊 [INGEST] Errors: {errors_count}")
    logger.info(f"📊 [DATA FLOW] NO LIMIT on storage - ALL emails stored in database")
    
    # CRITICAL VALIDATION: Check for mismatches
    if emails_received != emails_processed:
        logger.error(f"❌ [VALIDATION FAILED] emails_received ({emails_received}) != emails_processed ({emails_processed})")
    if emails_processed != emails_stored_count:
        logger.error(f"❌ [VALIDATION FAILED] emails_processed ({emails_processed}) != emails_stored ({emails_stored_count})")
    if emails_received == emails_stored_count and emails_received > 0:
        logger.info(f"✅ [VALIDATION PASSED] All {emails_received} emails stored successfully")
    
    logger.info(f"📊 [INGEST COMPLETE] ========================================")
    logger.info(f"")
    
    return IngestResponse(
        accepted=emails_received,
        duplicates=applications_updated,
        errors=errors_count
    )
