from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas.application import ProcessedEmail, IngestResponse
from app.services.dedupe import DedupeService
from app.db.repository import ApplicationRepository
from app.utils.db_session import get_db

router = APIRouter()

@router.post("/processed-emails", response_model=IngestResponse)
def ingest_processed_emails(emails: List[ProcessedEmail], db: Session = Depends(get_db)):
    """
    Ingests processed emails from the Email Intelligence Service.
    Deduplicates and updates application statuses.
    """
    dedupe_service = DedupeService(db)
    repo = ApplicationRepository(db)
    
    updated_count = 0
    errors = 0
    
    for email in emails:
        try:
            # Upsert Application
            app = dedupe_service.process_application(
                company_name=email.company_name,
                role_title=email.role,
                status=email.application_status,
                confidence=email.confidence_score,
                email_date=email.received_at
            )
            
            # Log Audit Event
            repo.log_event(
                app_id=app.id,
                event_type="email_ingested",
                payload=email.model_dump(mode='json')
            )
            
            updated_count += 1
        except Exception as e:
            print(f"Error ingestng email {email.email_id}: {e}")
            errors += 1
            
    return IngestResponse(
        accepted=len(emails),
        duplicates=updated_count, # Logic treats updates as success
        errors=errors
    )
