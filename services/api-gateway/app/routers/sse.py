"""
SSE endpoint for streaming Gmail sync progress events
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.middleware.auth_middleware import verify_token
import redis
import json
import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

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

# Gmail service URL for fetching persisted state
GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")

async def get_last_event_from_db(sync_id: str, user_id: str) -> dict:
    """
    Fetch the last persisted event from the Gmail connector service.
    This allows clients to reconnect and see the latest state immediately.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/sync/status",
                params={"sync_id": sync_id, "user_id": user_id}
            )
            if response.status_code == 200:
                data = response.json()
                # Convert status response to progress event format
                if data.get("status") in ["running", "completed", "failed"]:
                    phase_map = {
                        "running": "fetching",
                        "completed": "done",
                        "failed": "failed"
                    }
                    phase = phase_map.get(data.get("status"), "fetching")
                    
                    return {
                        "sync_id": sync_id,
                        "ts": data.get("updated_at") or datetime.utcnow().isoformat(),
                        "level": "error" if phase == "failed" else "info",
                        "phase": phase,
                        "message": data.get("error_message") or f"Sync {data.get('status')}",
                        "counts": {
                            "total_estimated": data.get("total_emails", 0),
                            "listed": data.get("total_emails", 0),
                            "fetched": data.get("processed_emails", 0),
                            "parsed": data.get("processed_emails", 0),
                            "classified": data.get("applications_found", 0),
                            "saved": data.get("applications_found", 0),
                            "skipped": data.get("skipped", 0),
                            "failed": data.get("processed_failed", 0)
                        },
                        "rate": {
                            "emails_per_sec": 0.0,
                            "bytes_per_sec": 0.0
                        },
                        "cursor": {
                            "page_token": None,
                            "history_id": None
                        },
                        "errors": [{"code": data.get("error_code"), "detail": data.get("error_message")}] if data.get("error_code") else [],
                        "done": phase in ["done", "failed"]
                    }
    except Exception as e:
        logger.warning(f"Failed to fetch last event from DB: {e}")
    return None

async def stream_sync_progress(sync_id: str, user_id: str):
    """
    Stream progress events via SSE.
    
    Flow:
    1. Send last persisted event immediately (if exists)
    2. Subscribe to Redis pub/sub channel
    3. Stream new events as they arrive
    4. Send keep-alive comments every 15s
    5. Handle client disconnection cleanly
    """
    global redis_client
    
    if redis_client is None:
        redis_client = get_redis_client()
        if redis_client is None:
            error_event = {
                "sync_id": sync_id,
                "ts": datetime.utcnow().isoformat(),
                "level": "error",
                "phase": "failed",
                "message": "Redis not available - cannot stream progress",
                "errors": [{"code": "REDIS_UNAVAILABLE", "detail": "Redis service not available", "retryable": True}],
                "done": False
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            return
    
    channel = f"gmail_sync:{sync_id}"
    pubsub = redis_client.pubsub()
    
    try:
        # Subscribe to Redis channel
        pubsub.subscribe(channel)
        logger.info(f"Subscribed to Redis channel: {channel}")
        
        # Send last persisted event first (if exists)
        last_event = await get_last_event_from_db(sync_id, user_id)
        if last_event:
            logger.info(f"Sending last persisted event for sync {sync_id}")
            yield f"data: {json.dumps(last_event)}\n\n"
        else:
            # Send initial event to confirm connection
            initial_event = {
                "sync_id": sync_id,
                "ts": datetime.utcnow().isoformat(),
                "level": "info",
                "phase": "starting",
                "message": "Connected to progress stream",
                "counts": {},
                "rate": {},
                "cursor": {},
                "errors": [],
                "done": False
            }
            yield f"data: {json.dumps(initial_event)}\n\n"
        
        # Start streaming new events
        last_keepalive = datetime.now()
        keepalive_interval = 15  # seconds
        message_count = 0
        
        while True:
            # Check for new messages (run blocking call in thread pool)
            try:
                # Use asyncio.to_thread for Python 3.9+, or run_in_executor for older versions
                try:
                    message = await asyncio.to_thread(
                        pubsub.get_message, 
                        timeout=1.0, 
                        ignore_subscribe_messages=True
                    )
                except AttributeError:
                    # Fallback for Python < 3.9
                    loop = asyncio.get_event_loop()
                    message = await loop.run_in_executor(
                        None,
                        lambda: pubsub.get_message(timeout=1.0, ignore_subscribe_messages=True)
                    )
                
                if message and message.get('type') == 'message':
                    try:
                        event_data = json.loads(message['data'])
                        # Verify sync_id matches
                        if event_data.get("sync_id") == sync_id:
                            message_count += 1
                            logger.debug(f"Received event #{message_count} for sync {sync_id}: {event_data.get('phase')}")
                            yield f"data: {json.dumps(event_data)}\n\n"
                            
                            # If done, close connection
                            if event_data.get("done"):
                                logger.info(f"Sync {sync_id} completed, closing SSE stream")
                                break
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in Redis message: {message.get('data')} - {e}")
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}", exc_info=True)
                elif message and message.get('type') == 'subscribe':
                    # This is the subscription confirmation, ignore it
                    logger.debug(f"Subscribed to channel {channel}")
                    continue
                
            except Exception as e:
                logger.error(f"Error getting Redis message: {e}", exc_info=True)
                # Continue loop, don't break on single message error
            
            # Send keep-alive comment every 15 seconds
            now = datetime.now()
            if (now - last_keepalive).total_seconds() >= keepalive_interval:
                yield ": keepalive\n\n"
                last_keepalive = now
            
            # Small sleep to prevent busy waiting
            await asyncio.sleep(0.1)
            
    except GeneratorExit:
        # Client disconnected - this is normal, don't log as error
        logger.debug(f"Client disconnected from SSE stream for sync {sync_id}")
        raise  # Re-raise to properly close the generator
    except asyncio.CancelledError:
        # Task was cancelled - normal shutdown
        logger.debug(f"SSE stream cancelled for sync {sync_id}")
        raise
    except Exception as e:
        logger.error(f"Error in SSE stream: {e}", exc_info=True)
        error_event = {
            "sync_id": sync_id,
            "ts": datetime.utcnow().isoformat(),
            "level": "error",
            "phase": "failed",
            "message": f"Stream error: {str(e)}",
            "errors": [{"code": "STREAM_ERROR", "detail": str(e), "retryable": True}],
            "done": False
        }
        yield f"data: {json.dumps(error_event)}\n\n"
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
            logger.info(f"Cleaned up Redis pubsub for sync {sync_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up pubsub: {e}")

@router.get("/sync/stream")
async def get_sync_stream(
    sync_id: str = Query(..., alias="sync_id"),
    token_data: dict = Depends(verify_token)
):
    """
    SSE endpoint for streaming Gmail sync progress events.
    
    Returns:
        text/event-stream with progress events
        
    Events:
        - First event: Last persisted state (if exists)
        - Subsequent events: Real-time progress updates
        - Keep-alive comments every 15s
    """
    user_id = token_data.get("sub")
    
    # Verify user owns this sync_id (basic check - could be enhanced)
    # For now, we'll rely on the Gmail service to verify ownership
    
    return StreamingResponse(
        stream_sync_progress(sync_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
