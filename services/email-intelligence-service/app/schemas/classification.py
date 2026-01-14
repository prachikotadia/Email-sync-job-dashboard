"""
Schemas for email classification.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class ClassificationRequest(BaseModel):
    """Request to classify an email."""
    email_data: Dict[str, Any] = Field(..., description="Email data from Gmail API (format='full')")
    

class KeywordMatch(BaseModel):
    """Matched keyword information."""
    keyword: str
    weight: float
    type: str
    location: str  # "subject" or "body"
    matches: int  # Number of matches found


class ClassificationResponse(BaseModel):
    """Response from email classification."""
    predicted_status: str = Field(..., description="Predicted status: Applied, Interview, Rejected, Ghosted, Accepted/Offer")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    matched_keywords: List[KeywordMatch] = Field(default_factory=list, description="List of matched keywords")
    category_scores: Dict[str, float] = Field(default_factory=dict, description="Score for each category")
    explanation: str = Field(..., description="Human-readable explanation")
    rule_based: bool = Field(default=True, description="Whether this is rule-based classification")


class BatchClassificationRequest(BaseModel):
    """Request to classify multiple emails."""
    emails: List[Dict[str, Any]] = Field(..., description="List of email data from Gmail API")


class BatchClassificationResponse(BaseModel):
    """Response from batch classification."""
    classifications: List[ClassificationResponse] = Field(..., description="Classification results for each email")
    total: int = Field(..., description="Total number of emails processed")
    errors: int = Field(default=0, description="Number of errors encountered")
