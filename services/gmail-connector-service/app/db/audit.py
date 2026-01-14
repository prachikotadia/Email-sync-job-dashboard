"""
Audit logging for email filtering decisions.

Stores audit records for every email processed, whether stored or rejected.
"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime
import json
from app.db.session import Base


class EmailFilterAudit(Base):
    """Audit log for email filtering decisions."""
    __tablename__ = "email_filter_audit"
    
    id = Column(String(36), primary_key=True)
    message_id = Column(String(255), nullable=False, index=True)  # Gmail message ID
    user_id = Column(String(36), nullable=False, index=True)
    
    # Email metadata
    from_email = Column(String(255))
    subject = Column(String(500))
    
    # Heuristic scoring
    heuristic_score = Column(Integer)
    heuristic_reasons = Column(JSON)  # List of strings
    
    # Classification results
    llm_is_job_application = Column(Boolean)
    llm_confidence = Column(Float)
    llm_category = Column(String(50))  # Applied, Interview, Rejected, etc.
    llm_reason = Column(String(500))
    
    # Decision
    final_decision = Column(String(20))  # stored, rejected
    rejected_reason_code = Column(String(50))  # NEWSLETTER, JOB_ALERT, LOW_CONFIDENCE, etc.
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "from_email": self.from_email,
            "subject": self.subject,
            "heuristic_score": self.heuristic_score,
            "heuristic_reasons": self.heuristic_reasons,
            "llm_is_job_application": self.llm_is_job_application,
            "llm_confidence": self.llm_confidence,
            "llm_category": self.llm_category,
            "llm_reason": self.llm_reason,
            "final_decision": self.final_decision,
            "rejected_reason_code": self.rejected_reason_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
