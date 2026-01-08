from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.schemas.application import ProcessedEmail, IngestResponse
from app.services.upsert_logic import UpsertLogic
# from app.utils.db_session import get_db # OLD
from app.db.supabase import get_db # NEW

router = APIRouter()

@router.post("/from-email-ai", response_model=IngestResponse)
def ingest_from_email_ai(emails: List[ProcessedEmail], db: Session = Depends(get_db)):
    """
    Internal ingest endpoint called by valid sources (e.g. email-intelligence).
    """
    logic = UpsertLogic(db)
    
    updated_count = 0
    errors = 0
    
    for email in emails:
        try:
            logic.process(
                company_name=email.company_name,
                role_title=email.role,
                status=email.application_status,
                confidence=email.confidence_score,
                email_date=email.received_at
            )
            updated_count += 1
        except Exception as e:
            print(f"Ingest error: {e}")
            errors += 1
            
    return IngestResponse(
        accepted=len(emails),
        duplicates=updated_count,
        errors=errors
    )
