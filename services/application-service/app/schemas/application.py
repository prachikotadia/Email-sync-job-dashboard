from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

# --- Shared Specs ---
class ProcessedEmail(BaseModel):
    """Matches contract from Email Intelligence Service"""
    email_id: str
    company_name: str
    role: str = "Unknown Role"
    application_status: str
    confidence_score: float
    received_at: datetime
    summary: Optional[str] = None

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
