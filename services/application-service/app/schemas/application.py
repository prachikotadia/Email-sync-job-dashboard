from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

# --- Shared Specs ---
class ProcessedEmail(BaseModel):
    """RULE 8: Processed email with all required fields for storage"""
    email_id: str  # Gmail message ID
    thread_id: str  # Gmail thread ID
    company_name: str
    role: str = "Unknown Role"
    application_status: str
    confidence_score: float
    received_at: datetime
    summary: Optional[str] = None
    # Additional fields for RULE 8
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    body_text: Optional[str] = None
    internal_date: Optional[int] = None  # Gmail internal date (milliseconds)
    subject: Optional[str] = None

# --- Application Schemas ---
class ApplicationResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    role_title: str
    status: str
    applied_count: int
    last_email_date: Optional[datetime]
    ghosted: bool
    resume_url: Optional[str]
    
    class Config:
        from_attributes = True

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    ghosted: Optional[bool] = None
    resume_id: Optional[uuid.UUID] = None

# --- Ingest Schemas ---
class IngestResponse(BaseModel):
    accepted: int
    duplicates: int # or updated
    errors: int
