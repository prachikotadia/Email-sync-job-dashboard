"""
Gmail search query builder for strict job-email-only filtering.

This module builds Gmail API search queries that filter emails at the source
to only fetch job application lifecycle emails.
"""

import logging
from datetime import datetime, timedelta
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def build_job_gmail_query(days: int = None) -> str:
    """
    Build EXTREMELY STRICT Gmail search query for job application emails only.
    
    Stage 1 pre-filter - only fetches likely job-related emails.
    Uses only strong phrases - NOT broad keywords.
    
    Args:
        days: Number of days to look back (defaults to GMAIL_QUERY_DAYS from config)
        
    Returns:
        Gmail search query string
    """
    if days is None:
        days = getattr(settings, 'GMAIL_QUERY_DAYS', 180)
    
    # STRICT positive phrases - must include at least one strong phrase
    positive_phrases = (
        '"thank you for applying" OR "application received" OR "application submitted" OR '
        '"we received your application" OR "your application" OR "application status" OR '
        '"not selected" OR "unfortunately" OR "we regret" OR "moving forward" OR "next steps" OR '
        'interview OR "phone screen" OR "technical interview" OR schedule OR '
        'assessment OR "coding challenge" OR offer OR "background check"'
    )
    
    # Hard exclusions - exclude obvious noise
    negative_exclusions = (
        '-("job alert" OR "jobs you may like" OR "recommended jobs" OR newsletter OR unsubscribe OR '
        '"career advice" OR webinar OR digest OR promotion OR sale OR coupon)'
    )
    
    # Build strict query
    query = (
        f'in:inbox newer_than:{days}d '
        f'(category:primary OR category:updates) '
        f'({positive_phrases}) '
        f'{negative_exclusions} '
        f'-category:social -category:promotions'
    )
    
    logger.info(f"Built strict Gmail query (days={days}): {query[:200]}...")
    
    return query
