"""
Email classification API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.classification import (
    ClassificationRequest,
    ClassificationResponse,
    BatchClassificationRequest,
    BatchClassificationResponse,
    KeywordMatch,
)
from app.classifiers.rule_based import RuleBasedClassifier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/classification", tags=["classification"])

# Initialize classifier (singleton)
classifier = RuleBasedClassifier(ghosted_threshold_days=14)


@router.post("/classify", response_model=ClassificationResponse)
async def classify_email(request: ClassificationRequest):
    """
    Classify a single email into job application status.
    
    Phase 1: Rule-based keyword matching.
    
    Exclusion Rules (HARD EXCLUDE):
    - Newsletters, promos, marketing, coupons
    - Job alerts (LinkedIn, Indeed, Glassdoor, etc.)
    - Generic career advice, webinars, events
    - Random HR content not tied to an application
    - ANY email without specific application/interview/rejection/offer intent
    - Ambiguous emails → DO NOT STORE (err on side of excluding)
    
    Returns:
        Classification result with predicted status, confidence, and explanation.
        Status "Unknown" means the email was excluded and should NOT be stored.
    """
    try:
        result = classifier.classify(request.email_data)
        
        # Log excluded emails for monitoring
        if result.get("predicted_status") == "Unknown" or result.get("excluded"):
            logger.info(f"Email excluded: {result.get('explanation', 'No explanation')}")
        
        # Convert matched_keywords to KeywordMatch objects
        matched_keywords = [
            KeywordMatch(
                keyword=kw.get("keyword", ""),
                weight=kw.get("weight", 0.0),
                type=kw.get("type", "partial"),
                location=kw.get("location", "body"),
                matches=len(kw.get("matches", [])) if isinstance(kw.get("matches"), list) else kw.get("matches", 0),
            )
            for kw in result.get("matched_keywords", [])
        ]
        
        return ClassificationResponse(
            predicted_status=result["predicted_status"],
            confidence_score=result["confidence_score"],
            matched_keywords=matched_keywords,
            category_scores=result.get("category_scores", {}),
            explanation=result["explanation"],
            rule_based=result.get("rule_based", True),
        )
        
    except Exception as e:
        logger.error(f"Error classifying email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.post("/classify/batch", response_model=BatchClassificationResponse)
async def classify_emails_batch(request: BatchClassificationRequest):
    """
    Classify multiple emails in batch.
    
    Useful for processing multiple emails at once.
    
    Exclusion Rules (HARD EXCLUDE):
    - Newsletters, promos, marketing, coupons
    - Job alerts (LinkedIn, Indeed, Glassdoor, etc.)
    - Generic career advice, webinars, events
    - Random HR content not tied to an application
    - ANY email without specific application/interview/rejection/offer intent
    - Ambiguous emails → DO NOT STORE (err on side of excluding)
    
    Emails with status "Unknown" are excluded and should NOT be stored.
    """
    classifications = []
    errors = 0
    
    for email_data in request.emails:
        try:
            result = classifier.classify(email_data)
            
            # Convert matched_keywords to KeywordMatch objects
            matched_keywords = [
                KeywordMatch(
                    keyword=kw.get("keyword", ""),
                    weight=kw.get("weight", 0.0),
                    type=kw.get("type", "partial"),
                    location=kw.get("location", "body"),
                    matches=len(kw.get("matches", [])) if isinstance(kw.get("matches"), list) else kw.get("matches", 0),
                )
                for kw in result.get("matched_keywords", [])
            ]
            
            classifications.append(
                ClassificationResponse(
                    predicted_status=result["predicted_status"],
                    confidence_score=result["confidence_score"],
                    matched_keywords=matched_keywords,
                    category_scores=result.get("category_scores", {}),
                    explanation=result["explanation"],
                    rule_based=result.get("rule_based", True),
                )
            )
        except Exception as e:
            logger.error(f"Error classifying email in batch: {e}", exc_info=True)
            errors += 1
    
    return BatchClassificationResponse(
        classifications=classifications,
        total=len(request.emails),
        errors=errors,
    )
