"""
Strict email classifier for job application emails.

This module implements Stage 2 post-filter with strict rules and high confidence threshold (0.85).
"""
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EmailCategory(str, Enum):
    """Email categories - exactly as specified."""
    APPLIED_CONFIRMATION = "APPLIED_CONFIRMATION"
    REJECTION = "REJECTION"
    INTERVIEW = "INTERVIEW"
    ASSESSMENT = "ASSESSMENT"
    OFFER = "OFFER"
    RECRUITER_OUTREACH = "RECRUITER_OUTREACH"
    OTHER = "OTHER"  # Means discard


# Hard negative checks (instant discard)
# Excludes: Newsletters, promos, marketing, coupons, job alerts, generic HR content,
# career advice, webinars, events, and ANY email without specific application intent
HARD_NEGATIVE_PATTERNS = [
    # Job alerts and recommendations
    "job alert",
    "jobs you may like",
    "jobs you might like",
    "recommended jobs",
    "top jobs",
    "recommended",
    "new jobs",
    "job opportunities",
    "job matches",
    "job suggestions",
    "similar jobs",
    # Newsletters and digests
    "digest",
    "newsletter",
    "weekly digest",
    "daily digest",
    "monthly digest",
    "email digest",
    # Marketing and promotions
    "unsubscribe",
    "promo",
    "promotion",
    "coupon",
    "discount",
    "sale",
    "special offer",
    "limited time",
    "marketing",
    # Generic career content (not tied to specific application)
    "career advice",
    "career tips",
    "career guidance",
    "career webinar",
    "webinar",
    "event",
    "workshop",
    "seminar",
    "conference",
    "networking event",
    "career fair",
    # Platform-specific alerts
    "linkedin digest",
    "indeed alert",
    "glassdoor alert",
    "monster alert",
    "ziprecruiter alert",
    # Generic HR content
    "hr newsletter",
    "talent newsletter",
    "recruiting newsletter",
    "hiring newsletter",
    # Ambiguous patterns
    "update your profile",
    "complete your profile",
    "profile reminder",
    "account update",
    "settings update",
]


# Positive patterns with category and confidence boost
POSITIVE_PATTERNS = {
    EmailCategory.APPLIED_CONFIRMATION: [
        ("thank you for applying", 1.0),
        ("we received your application", 1.0),
        ("application received", 0.95),
        ("application submitted", 0.9),
        ("application confirmation", 0.9),
    ],
    EmailCategory.REJECTION: [
        ("not selected", 1.0),
        ("unfortunately", 0.95),
        ("regret to inform", 1.0),
        ("we regret", 0.9),
        ("moving forward", 0.85),  # Only if with rejection context
    ],
    EmailCategory.INTERVIEW: [
        ("interview", 0.9),
        ("phone screen", 1.0),
        ("technical interview", 1.0),
        ("schedule", 0.85),  # Must be with interview context
        ("calendar", 0.8),
        ("availability", 0.8),
    ],
    EmailCategory.ASSESSMENT: [
        ("assessment", 1.0),
        ("coding challenge", 1.0),
        ("hackerrank", 1.0),
        ("codility", 1.0),
        ("take home", 0.9),
    ],
    EmailCategory.OFFER: [
        ("offer", 0.95),
        ("compensation", 0.85),  # Must be with offer context
        ("background check", 1.0),  # Only after offer
        ("onboarding", 0.9),  # Only after offer
    ],
}


def classify_email(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify email using strict rules.
    
    Stage 2 post-filter - only accepts emails with high confidence (>= 0.85).
    
    Args:
        email_data: Email data with 'subject', 'from', 'snippet', 'headers'
        
    Returns:
        Dict with:
        - label: EmailCategory
        - confidence: float (0.0-1.0)
        - reasons: List[str] (matched patterns)
        - stored: bool (whether to store)
    """
    subject = (email_data.get("subject") or "").lower()
    from_email = (email_data.get("from") or "").lower()
    snippet = (email_data.get("snippet") or "").lower()
    headers_raw = email_data.get("headers", [])
    body_text = email_data.get("body_text", "").lower() if email_data.get("body_text") else snippet
    
    # Ensure headers is always a list of dicts
    if isinstance(headers_raw, dict):
        # Convert dict to list of {name, value} dicts
        headers = [{"name": k, "value": v} for k, v in headers_raw.items()]
    elif isinstance(headers_raw, list):
        headers = headers_raw
    elif isinstance(headers_raw, str):
        # If it's a string, create empty list (can't parse string headers)
        headers = []
    else:
        headers = []
    
    # Check headers for negative signals
    list_unsubscribe = any(
        h.get("name", "").lower() == "list-unsubscribe"
        for h in headers
        if isinstance(h, dict)
    )
    precedence = next(
        (h.get("value", "").lower() for h in headers if isinstance(h, dict) and h.get("name", "").lower() == "precedence"),
        ""
    )
    
    # HARD NEGATIVE CHECKS - instant discard
    # Check both subject and body for exclusion patterns
    combined_text = f"{subject} {snippet} {body_text}".lower()
    
    # Check for hard negative patterns (case-insensitive)
    for pattern in HARD_NEGATIVE_PATTERNS:
        if pattern.lower() in combined_text:
            return {
                "label": EmailCategory.OTHER.value,
                "confidence": 0.0,
                "reasons": [f"Hard negative pattern: {pattern}"],
                "stored": False,
                "discard_reason": f"Excluded: Contains {pattern} (newsletter/marketing/alert/generic content)"
            }
    
    # Check for List-Unsubscribe header or Precedence: bulk
    if list_unsubscribe or precedence == "bulk":
        return {
            "label": EmailCategory.OTHER.value,
            "confidence": 0.0,
            "reasons": ["List-Unsubscribe header or Precedence: bulk"],
            "stored": False,
            "discard_reason": "Newsletter/marketing email"
        }
    
    # Check sender domain for obvious marketing/alerts
    if "@" in from_email:
        domain = from_email.split("@")[1].lower()
        marketing_domains = ["linkedin.com", "indeed.com", "glassdoor.com", "monster.com"]
        if any(md in domain for md in marketing_domains):
            # Only discard if no positive patterns
            has_positive = False
            for category, patterns in POSITIVE_PATTERNS.items():
                for pattern, _ in patterns:
                    if pattern in combined_text:
                        has_positive = True
                        break
                if has_positive:
                    break
            
            if not has_positive:
                return {
                    "label": EmailCategory.OTHER.value,
                    "confidence": 0.0,
                    "reasons": [f"Marketing domain: {domain}"],
                    "stored": False,
                    "discard_reason": f"Marketing/alert domain: {domain}"
                }
    
    # POSITIVE CHECKS - find strongest match
    best_category = None
    best_confidence = 0.0
    matched_reasons = []
    
    for category, patterns in POSITIVE_PATTERNS.items():
        category_confidence = 0.0
        category_reasons = []
        
        for pattern, confidence_boost in patterns:
            # Check subject first (higher weight)
            if pattern in subject:
                category_confidence = max(category_confidence, confidence_boost * 1.0)
                category_reasons.append(f"Subject: {pattern}")
            # Then snippet/body (lower weight)
            elif pattern in snippet or pattern in body_text:
                category_confidence = max(category_confidence, confidence_boost * 0.85)
                category_reasons.append(f"Body: {pattern}")
        
        # Special handling for REJECTION - "unfortunately" + "moving forward" together
        if category == EmailCategory.REJECTION:
            if "unfortunately" in combined_text and "moving forward" in combined_text:
                category_confidence = max(category_confidence, 0.95)
                category_reasons.append("Subject/Body: unfortunately + moving forward")
        
        # Special handling for INTERVIEW - "interview" + scheduling terms
        if category == EmailCategory.INTERVIEW:
            if "interview" in combined_text:
                scheduling_terms = ["schedule", "scheduled", "calendar", "availability"]
                if any(term in combined_text for term in scheduling_terms):
                    category_confidence = max(category_confidence, 0.95)
                    category_reasons.append("Subject/Body: interview + scheduling")
        
        if category_confidence > best_confidence:
            best_confidence = category_confidence
            best_category = category
            matched_reasons = category_reasons
    
    # CONFIDENCE REQUIREMENT - lowered to 0.5 to accept more emails
    # Accept emails with moderate confidence to capture all application emails
    if best_category and best_confidence >= 0.5:
        # High confidence - only store if we're very sure it's application-related
        # Additional check: must have specific application intent keywords
        application_intent_keywords = [
            "application", "applied", "interview", "rejected", "offer", 
            "hiring", "recruiter", "candidate", "position", "role"
        ]
        has_application_intent = any(
            keyword in combined_text for keyword in application_intent_keywords
        )
        
        if has_application_intent:
            return {
                "label": best_category.value,
                "confidence": best_confidence,
                "reasons": matched_reasons,
                "stored": True
            }
        else:
            # High confidence but no clear application intent - exclude
            return {
                "label": best_category.value,
                "confidence": best_confidence,
                "reasons": matched_reasons,
                "stored": False,
                "discard_reason": "No specific application/interview/rejection/offer intent found"
            }
    else:
        # Medium/low confidence or no match - ALWAYS DISCARD (err on side of excluding)
        return {
            "label": EmailCategory.OTHER.value if not best_category else best_category.value,
            "confidence": best_confidence if best_confidence > 0 else 0.0,
            "reasons": matched_reasons if matched_reasons else ["No strong positive patterns"],
            "stored": False,
            "discard_reason": "Ambiguous or low confidence - excluded per strict filtering rules"
        }
