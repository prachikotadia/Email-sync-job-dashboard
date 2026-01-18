"""
RQ job queue setup
"""
import os
import redis
from rq import Queue
import logging

logger = logging.getLogger(__name__)

# Redis connection with retry logic
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def get_redis_connection():
    """Get Redis connection with error handling"""
    try:
        conn = redis.from_url(REDIS_URL, socket_connect_timeout=5, socket_timeout=5)
        # Test connection
        conn.ping()
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {REDIS_URL}: {e}")
        raise

# Lazy initialization - will be initialized on first use
_redis_conn = None
_sync_queue = None

def _ensure_queue_initialized():
    """Lazy initialization of Redis queue"""
    global _redis_conn, _sync_queue
    if _sync_queue is None:
        try:
            _redis_conn = get_redis_connection()
            _sync_queue = Queue('gmail_sync', connection=_redis_conn)
            logger.info(f"Redis queue initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis queue: {e} - will use fallback mode")
            _redis_conn = None
            _sync_queue = None

# Public accessors
def get_redis_connection_for_worker():
    """Get Redis connection for worker (used by worker.py)"""
    _ensure_queue_initialized()
    return _redis_conn

def get_sync_queue():
    """Get sync queue instance"""
    _ensure_queue_initialized()
    return _sync_queue

def enqueue_sync_job(job_id: str, user_id: str, user_email: str) -> bool:
    """
    Enqueue a Gmail sync job to the worker queue.
    
    Args:
        job_id: UUID of the sync job
        user_id: Database user ID (UUID string)
        user_email: User email for validation
        
    Returns:
        True if enqueued successfully
    """
    _ensure_queue_initialized()
    sync_queue = get_sync_queue()
    
    if sync_queue is None:
        logger.warning("Redis queue not available - cannot enqueue job")
        return False
    
    try:
        # Ensure Redis connection is still alive
        redis_conn = get_redis_connection_for_worker()
        if redis_conn:
            try:
                redis_conn.ping()
            except Exception:
                logger.warning("Redis connection lost, attempting to reconnect...")
                _ensure_queue_initialized()
                redis_conn = get_redis_connection_for_worker()
                sync_queue = get_sync_queue()
                if sync_queue is None:
                    return False
        
        from app.worker import process_sync_job
        job = sync_queue.enqueue(
            process_sync_job,
            job_id,
            user_id,
            user_email,
            job_id=job_id,  # Use sync job ID as RQ job ID
            job_timeout='1h',  # 1 hour timeout for long syncs
            result_ttl=86400  # Keep results for 24 hours
        )
        logger.info(f"Enqueued sync job {job_id} to queue, RQ job ID: {job.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to enqueue sync job {job_id}: {e}", exc_info=True)
        return False
