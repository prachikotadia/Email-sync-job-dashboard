"""
Progress event schema and Redis publisher for SSE streaming
"""
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import json
import redis
import os
import logging

logger = logging.getLogger(__name__)

# Redis connection with error handling
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def get_redis_client():
    """Get Redis client with error handling"""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
        client.ping()
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None

redis_client = get_redis_client()

# Progress event phases
class SyncPhase:
    QUEUED = "queued"
    STARTING = "starting"
    LISTING = "listing"
    FETCHING = "fetching"
    PARSING = "parsing"
    CLASSIFYING = "classifying"
    SAVING = "saving"
    FINALIZING = "finalizing"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"
    RATE_LIMITED = "rate_limited"  # Job paused due to Gmail API rate limits

# Event levels
class EventLevel:
    INFO = "info"
    WARN = "warn"
    ERROR = "error"

def create_progress_event(
    sync_id: str,
    phase: str,
    message: str,
    level: str = EventLevel.INFO,
    counts: Optional[Dict[str, int]] = None,
    rate: Optional[Dict[str, float]] = None,
    cursor: Optional[Dict[str, Optional[str]]] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    done: bool = False,
    email_id: Optional[str] = None,  # Gmail message ID for per-email tracking
    retry_count: Optional[int] = None,  # Retry attempt number
    retry_after_seconds: Optional[float] = None  # Backoff delay in seconds
) -> Dict[str, Any]:
    """
    Create a canonical progress event following the strict schema.
    
    Args:
        sync_id: UUID of the sync job
        phase: Current phase (queued|starting|listing|fetching|parsing|classifying|saving|finalizing|done|failed|canceled)
        message: Human readable message
        level: Event level (info|warn|error)
        counts: Dictionary with count fields
        rate: Dictionary with rate fields
        cursor: Dictionary with cursor fields (page_token, history_id)
        errors: List of error dictionaries
        done: Whether the sync is complete
        
    Returns:
        Progress event dictionary
    """
    event = {
        "sync_id": sync_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "phase": phase,
        "message": message,
        "counts": counts or {
            "total_estimated": 0,
            "listed": 0,
            "fetched": 0,
            "parsed": 0,
            "classified": 0,
            "saved": 0,
            "skipped": 0,
            "failed": 0
        },
        "rate": rate or {
            "emails_per_sec": 0.0,
            "bytes_per_sec": 0.0
        },
        "cursor": cursor or {
            "page_token": None,
            "history_id": None
        },
        "errors": errors or [],
        "done": done,
        "email_id": email_id,  # Gmail message ID for per-email tracking
        "retry_count": retry_count,  # Retry attempt number
        "retry_after_seconds": retry_after_seconds  # Backoff delay in seconds
    }
    return event

def publish_progress_event(event: Dict[str, Any]) -> bool:
    """
    Publish progress event to Redis pub/sub channel.
    
    Channel name: gmail_sync:{sync_id}
    
    Args:
        event: Progress event dictionary
        
    Returns:
        True if published successfully, False otherwise
    """
    global redis_client
    
    if redis_client is None:
        redis_client = get_redis_client()
        if redis_client is None:
            logger.warning("Redis not available, skipping event publish")
            return False
    
    try:
        sync_id = event["sync_id"]
        channel = f"gmail_sync:{sync_id}"
        
        # Test connection
        try:
            redis_client.ping()
        except Exception:
            logger.warning("Redis connection lost, reconnecting...")
            redis_client = get_redis_client()
            if redis_client is None:
                return False
        
        # Publish to Redis pub/sub
        redis_client.publish(channel, json.dumps(event))
        
        logger.debug(f"Published progress event to {channel}: {event.get('phase')} - {event.get('message')}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish progress event: {e}", exc_info=True)
        return False

def get_redis_subscriber(sync_id: str):
    """
    Get a Redis subscriber for a specific sync_id channel.
    
    Args:
        sync_id: UUID of the sync job
        
    Returns:
        Redis pubsub subscriber or None if Redis unavailable
    """
    global redis_client
    if redis_client is None:
        redis_client = get_redis_client()
        if redis_client is None:
            return None
    
    pubsub = redis_client.pubsub()
    channel = f"gmail_sync:{sync_id}"
    pubsub.subscribe(channel)
    return pubsub
