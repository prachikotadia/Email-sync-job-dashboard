"""
Heuristic scoring system for job email filtering.

This module implements fast heuristic scoring to filter out non-job emails
before sending them to the classification service.
"""

import re
import logging
from typing import Dict, Any, List, Tuple
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ATS domains that indicate job-related emails
ATS_DOMAINS = [
    'greenhouse.io',
    'lever.co',
    'workday.com',
    'icims.com',
    'successfactors.com',
    'myworkday.com',
    'smartrecruiters.com',
    'ashbyhq.com',
    'bamboohr.com',
    'jobvite.com',
    'talemetry.com',
]

# Known job alert/newsletter senders (negative)
NEWSLETTER_DOMAINS = [
    'linkedin.com',
    'indeed.com',
    'glassdoor.com',
    'monster.com',
    'ziprecruiter.com',
    'dice.com',
    'simplyhired.com',
]

# Positive phrases (score +2 to +5 each)
POSITIVE_PHRASES = [
    ('thank you for applying', 5),
    ('application received', 5),
    ('application submitted', 4),
    ('we received your application', 5),
    ('your application', 3),
    ('application update', 4),
    ('application status', 4),
    ('next steps', 4),
    ('interview', 5),
    ('schedule', 3),
    ('assessment', 4),
    ('coding challenge', 4),
    ('online assessment', 4),
    ('take home', 3),
    ('offer', 5),
    ('rejection', 4),
    ('unfortunately', 3),
    ('regret to inform', 4),
    ('background check', 4),
    ('schedule a call', 4),
    ('select a time', 3),
]

# Negative phrases (score -3 to -10 each)
NEGATIVE_PHRASES = [
    ('jobs you may like', -10),
    ('job alert', -8),
    ('recommended jobs', -8),
    ('digest', -5),
    ('newsletter', -8),
    ('subscription', -5),
    ('promotions', -5),
    ('weekly', -3),
    ('daily', -3),
    ('career advice', -5),
    ('salary', -3),
    ('course', -5),
    ('bootcamp', -5),
    ('webinar', -5),
    ('event', -3),
    ('hiring newsletter', -8),
]


def heuristic_job_score(email_data: Dict[str, Any]) -> Tuple[int, List[str]]:
    """
    Calculate heuristic score for an email to determine if it's job-related.
    
    Args:
        email_data: Email data with 'subject', 'from', 'snippet', 'headers'
        
    Returns:
        Tuple of (score, reasons) where:
        - score: Integer score (higher = more likely job-related)
        - reasons: List of strings explaining why score was given
    """
    score = 0
    reasons = []
    
    # Extract fields
    subject = (email_data.get('subject') or '').lower()
    from_addr = (email_data.get('from') or '').lower()
    snippet = (email_data.get('snippet') or '').lower()
    headers = email_data.get('headers', [])
    
    combined_text = f"{subject} {snippet}".lower()
    
    # Check for positive phrases in subject
    for phrase, points in POSITIVE_PHRASES:
        if phrase in subject:
            score += points
            reasons.append(f"+{points}: subject contains '{phrase}'")
    
    # Check for positive phrases in snippet
    for phrase, points in POSITIVE_PHRASES:
        if phrase in snippet and phrase not in subject:
            score += max(points - 1, 1)  # Slightly lower weight for snippet
            reasons.append(f"+{max(points - 1, 1)}: snippet contains '{phrase}'")
    
    # Check for ATS domains
    for domain in ATS_DOMAINS:
        if domain in from_addr:
            score += 5
            reasons.append(f"+5: from ATS domain ({domain})")
            break
    
    # Check for negative phrases
    for phrase, penalty in NEGATIVE_PHRASES:
        if phrase in combined_text:
            score += penalty
            reasons.append(f"{penalty}: contains '{phrase}'")
    
    # Check for newsletter domains
    for domain in NEWSLETTER_DOMAINS:
        if domain in from_addr:
            score -= 8
            reasons.append(f"-8: from newsletter domain ({domain})")
            break
    
    # Check for List-Unsubscribe header (newsletters often have this)
    list_unsubscribe = any(
        h.get('name', '').lower() == 'list-unsubscribe'
        for h in headers
        if isinstance(h, dict)
    )
    if list_unsubscribe:
        score -= 3
        reasons.append("-3: has List-Unsubscribe header (likely newsletter)")
    
    # Boost if contains both subject and snippet positive phrases
    subject_positive = any(phrase in subject for phrase, _ in POSITIVE_PHRASES)
    snippet_positive = any(phrase in snippet for phrase, _ in POSITIVE_PHRASES)
    if subject_positive and snippet_positive:
        score += 2
        reasons.append("+2: multiple positive signals")
    
    return score, reasons


def should_process_email(score: int) -> Tuple[bool, str]:
    """
    Determine if email should be processed based on heuristic score.
    
    Args:
        score: Heuristic score from heuristic_job_score()
        
    Returns:
        Tuple of (should_process, reason)
    """
    accept_threshold = getattr(settings, 'HEURISTIC_ACCEPT', 6)
    reject_threshold = getattr(settings, 'HEURISTIC_REJECT', 0)
    
    if score >= accept_threshold:
        return True, "accepted"
    elif score <= reject_threshold:
        return False, "rejected"
    else:
        return True, "low_confidence"
