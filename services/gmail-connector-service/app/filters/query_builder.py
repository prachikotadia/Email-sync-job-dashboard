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


def build_job_gmail_query(days: int = None, last_synced_date: str = None) -> str:
    """
    Build Gmail query - NO FILTERING at query level (RULE 2).
    
    RULE 2: Fetch latest emails WITHOUT filtering.
    Filtering happens AFTER fetching, NOT at Gmail query level.
    
    Args:
        days: Number of days to look back (defaults to 180)
        last_synced_date: ISO format date string - if provided, only fetch emails newer than this
        
    Returns:
        Gmail search query string (time-based only, NO keyword filtering)
    """
    if days is None:
        days = getattr(settings, 'GMAIL_QUERY_DAYS', 180)
    
    # RULE 2: NO keyword filtering at Gmail query level
    # Only time-based filtering for incremental sync
    if last_synced_date:
        # Fetch only emails newer than last sync (incremental sync)
        try:
            # Extract date part from ISO format
            date_part = last_synced_date.split('T')[0]
            time_filter = f'after:{date_part}'
            logger.info(f"[INCREMENTAL] Using incremental sync filter: after {date_part}")
            query = f'in:anywhere {time_filter}'
        except:
            query = f'in:anywhere newer_than:{days}d'
    else:
        query = f'in:anywhere newer_than:{days}d'
    
    logger.info(f"[GMAIL QUERY] Built query (NO keyword filtering): {query}")
    logger.info(f"[GMAIL QUERY] Filtering will happen AFTER fetching full email content")
    
    return query
