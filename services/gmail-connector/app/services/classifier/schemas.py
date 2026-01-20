"""
Pydantic schemas for classification requests and responses.
"""

from pydantic import BaseModel
from typing import Optional, List


class EmailForClassification(BaseModel):
    """Request schema for email classification."""
    
    subject: Optional[str] = ""
    snippet: Optional[str] = ""
    from_domain: Optional[str] = ""
    thread_summary: Optional[str] = ""


class ClassificationResult(BaseModel):
    """Response schema for email classification."""
    
    label: str                 # raw HF label (e.g., "confirmation", "interview")
    status: str                # mapped to your app status (e.g., "ACTIVE", "INTERVIEW")
    confidence: float
    reason: str
