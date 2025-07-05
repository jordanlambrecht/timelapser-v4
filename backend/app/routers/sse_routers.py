# backend/app/routers/sse_routers.py
"""
Server-Sent Events (SSE) HTTP endpoints using simple polling.

Role: Real-time event streaming endpoints
Responsibilities: Database-driven SSE streaming, event delivery, connection management
Interactions: Uses SSEEventsOperations for database access, streams events to clients
"""

import json
import asyncio
from typing import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from loguru import logger

from ..dependencies import AsyncDatabaseDep
from ..database.sse_events_operations import SSEEventsOperations
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter
from ..utils.cache_invalidation import CacheInvalidationService

router = APIRouter(tags=["sse"])


@router.get("/events")
@handle_exceptions("SSE event stream")
async def sse_event_stream(db: AsyncDatabaseDep):
    """
    Server-Sent Events endpoint for real-time event streaming using database polling.
    
    This endpoint polls the database every 3 seconds for new events, providing
    reliable real-time updates with industry-standard polling approach.
    
    Returns:
        StreamingResponse: SSE-formatted event stream
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Generate SSE-formatted events using database polling.
        
        Yields:
            SSE-formatted event strings
        """
        sse_ops = SSEEventsOperations(db)
        last_heartbeat = datetime.utcnow()
        
        logger.info("SSE client connected, starting event stream (polling mode)")
        
        try:
            # Process any existing events first
            existing_events = await sse_ops.get_pending_events(limit=50)
            if existing_events:
                for event in existing_events:
                    # Format as SSE event
                    event_data = {
                        "type": event["type"],
                        "data": event["data"],
                        "timestamp": event["timestamp"]
                    }
                    
                    # Trigger cache invalidation for this event
                    try:
                        await CacheInvalidationService.handle_sse_event(
                            event["type"], event["data"]
                        )
                    except Exception as cache_error:
                        logger.warning(f"Cache invalidation failed for {event['type']}: {cache_error}")
                    
                    # Yield SSE-formatted data
                    yield f"data: {json.dumps(event_data)}\n\n"
                
                # Mark events as processed
                event_ids = [event["id"] for event in existing_events]
                await sse_ops.mark_events_processed(event_ids)
                logger.debug(f"Streamed {len(existing_events)} existing SSE events to client")

            # Main polling loop
            while True:
                try:
                    # Poll for new events every 3 seconds
                    events = await sse_ops.get_pending_events(limit=10)
                    
                    if events:
                        # Stream each event to client
                        event_ids = []
                        for event in events:
                            # Format as SSE event
                            event_data = {
                                "type": event["type"],
                                "data": event["data"],
                                "timestamp": event["timestamp"]
                            }
                            
                            # Trigger cache invalidation for this event
                            try:
                                await CacheInvalidationService.handle_sse_event(
                                    event["type"], event["data"]
                                )
                            except Exception as cache_error:
                                logger.warning(f"Cache invalidation failed for {event['type']}: {cache_error}")
                            
                            # Yield SSE-formatted data
                            yield f"data: {json.dumps(event_data)}\n\n"
                            event_ids.append(event["id"])
                        
                        # Mark events as processed
                        await sse_ops.mark_events_processed(event_ids)
                        logger.debug(f"Streamed {len(events)} SSE events to client")
                    
                    # Send heartbeat every 30 seconds
                    now = datetime.utcnow()
                    if (now - last_heartbeat).total_seconds() > 30:
                        heartbeat_event = {
                            "type": "heartbeat",
                            "data": {"timestamp": now.isoformat()},
                            "timestamp": now.isoformat()
                        }
                        yield f"data: {json.dumps(heartbeat_event)}\n\n"
                        last_heartbeat = now
                        logger.debug("Sent SSE heartbeat")
                    
                    # Wait 3 seconds before next poll (industry standard)
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error in SSE event generation: {e}")
                    # Send error event to client
                    error_event = {
                        "type": "error",
                        "data": {"message": "Event stream error occurred"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    await asyncio.sleep(5)  # Wait longer on error
                    
        except asyncio.CancelledError:
            logger.info("SSE client disconnected")
            raise
        except Exception as e:
            logger.error(f"Fatal error in SSE stream: {e}")
            raise

    # Return streaming response with proper SSE headers
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/events/stats")
@handle_exceptions("get SSE event statistics")
async def get_sse_stats(db: AsyncDatabaseDep):
    """
    Get SSE event statistics for monitoring and debugging.
    
    Returns:
        Dictionary with event statistics
    """
    sse_ops = SSEEventsOperations(db)
    stats = await sse_ops.get_event_stats()
    
    return ResponseFormatter.success(
        "SSE event statistics retrieved successfully",
        data=stats
    )


@router.post("/events/cleanup")
@handle_exceptions("cleanup old SSE events")
async def cleanup_old_events(
    max_age_hours: int = 24,
    db: AsyncDatabaseDep = None
):
    """
    Clean up old processed SSE events to prevent database bloat.
    
    Args:
        max_age_hours: Maximum age of processed events to keep (default 24 hours)
    
    Returns:
        Number of events cleaned up
    """
    sse_ops = SSEEventsOperations(db)
    deleted_count = await sse_ops.cleanup_old_events(max_age_hours)
    
    return ResponseFormatter.success(
        f"Cleaned up {deleted_count} old SSE events",
        data={"deleted_count": deleted_count, "max_age_hours": max_age_hours}
    )