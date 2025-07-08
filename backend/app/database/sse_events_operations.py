# backend/app/database/sse_events_operations.py
"""
SSE Events Operations - Composition-based architecture.

This module handles database operations for Server-Sent Events (SSE) using
dependency injection for database operations, providing type-safe interfaces.
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from .core import AsyncDatabase, SyncDatabase


class SSEEventsOperations:
    """
    Async SSE events database operations using composition pattern.

    This class handles creating, retrieving, and managing SSE events
    stored in the database for reliable real-time event streaming.
    """

    def __init__(self, db: AsyncDatabase):
        """
        Initialize SSEEventsOperations with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db

    async def create_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: str = "normal",
        source: str = "system",
    ) -> int:
        """
        Create a new SSE event in the database.

        Args:
            event_type: Type of event (e.g., 'image_captured', 'camera_status_changed')
            event_data: Event payload data
            priority: Event priority ('low', 'normal', 'high', 'critical')
            source: Source of the event (e.g., 'worker', 'api', 'system')

        Returns:
            ID of the created event

        Raises:
            Exception: If event creation fails
        """
        try:
            query = """
                INSERT INTO sse_events (event_type, event_data, priority, source, retry_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (event_type, json.dumps(event_data), priority, source, 0),
                    )
                    result = await cur.fetchone()
                    if result:
                        event_id = (
                            result["id"] if isinstance(result, dict) else result[0]
                        )
                        logger.debug(
                            f"Created SSE event: {event_type} with ID {event_id}"
                        )
                        return event_id
                    else:
                        raise Exception("Failed to create SSE event")

        except Exception as e:
            logger.error(f"Failed to create SSE event {event_type}: {e}")
            raise

    async def get_pending_events(
        self, limit: int = 100, max_age_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get pending (unprocessed) SSE events for streaming.

        Args:
            limit: Maximum number of events to return
            max_age_minutes: Maximum age of events to return (prevents old events)

        Returns:
            List of event dictionaries with formatted data

        Raises:
            Exception: If retrieval fails
        """
        try:
            query = """
                SELECT id, event_type, event_data, created_at, priority, source
                FROM sse_events
                WHERE processed_at IS NULL
                  AND created_at > %s
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
            """

            cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (cutoff_time, limit))
                    rows = await cur.fetchall()

                    events = []
                    for row in rows:
                        event = {
                            "id": row["id"],
                            "type": row["event_type"],
                            "data": row["event_data"] if row["event_data"] else {},
                            "timestamp": (
                                row["created_at"].isoformat()
                                if row["created_at"]
                                else None
                            ),
                            "priority": row["priority"],
                            "source": row["source"],
                        }
                        events.append(event)

                    if events:
                        logger.debug(f"Retrieved {len(events)} pending SSE events")
                    return events

        except Exception as e:
            logger.error(f"Failed to get pending SSE events: {e}")
            raise

    async def mark_events_processed(self, event_ids: List[int]) -> int:
        """
        Mark SSE events as processed (delivered to clients).

        Args:
            event_ids: List of event IDs to mark as processed

        Returns:
            Number of events marked as processed

        Raises:
            Exception: If marking fails
        """
        if not event_ids:
            return 0

        try:
            query = """
                UPDATE sse_events
                SET processed_at = NOW()
                WHERE id = ANY(%s) AND processed_at IS NULL
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (event_ids,))
                    updated_count = cur.rowcount
                    logger.debug(f"Marked {updated_count} SSE events as processed")
                    return updated_count

        except Exception as e:
            logger.error(f"Failed to mark SSE events as processed: {e}")
            raise

    async def cleanup_old_events(self, max_age_hours: int = 24) -> int:
        """
        Clean up old processed SSE events to prevent table bloat.

        Args:
            max_age_hours: Maximum age of processed events to keep

        Returns:
            Number of events deleted

        Raises:
            Exception: If cleanup fails
        """
        try:
            query = """
                DELETE FROM sse_events
                WHERE processed_at IS NOT NULL
                    AND processed_at < %s
            """

            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (cutoff_time,))
                    deleted_count = cur.rowcount
                    logger.info(f"Cleaned up {deleted_count} old SSE events")
                    return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old SSE events: {e}")
            raise

    async def get_event_stats(self) -> Dict[str, Any]:
        """
        Get statistics about SSE events for monitoring.

        Returns:
            Dictionary with event statistics

        Raises:
            Exception: If stats retrieval fails
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_events,
                    COUNT(*) FILTER (WHERE processed_at IS NULL) as pending_events,
                    COUNT(*) FILTER (WHERE processed_at IS NOT NULL) as processed_events,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as recent_events,
                    COUNT(DISTINCT event_type) as unique_event_types
                FROM sse_events
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    row = await cur.fetchone()

                    if row:
                        stats = {
                            "total_events": row[0],
                            "pending_events": row[1],
                            "processed_events": row[2],
                            "recent_events": row[3],
                            "unique_event_types": row[4],
                        }
                        return stats
                    else:
                        return {
                            "total_events": 0,
                            "pending_events": 0,
                            "processed_events": 0,
                            "recent_events": 0,
                            "unique_event_types": 0,
                        }

        except Exception as e:
            logger.error(f"Failed to get SSE event stats: {e}")
            raise


class SyncSSEEventsOperations:
    """
    Sync SSE events database operations for worker processes.

    This class provides synchronous database operations for SSE events,
    used by worker processes that need to create events.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncSSEEventsOperations with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db

    def create_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: str = "normal",
        source: str = "worker",
    ) -> int:
        """
        Create a new SSE event in the database (sync version).

        Args:
            event_type: Type of event (e.g., 'image_captured', 'camera_status_changed')
            event_data: Event payload data
            priority: Event priority ('low', 'normal', 'high', 'critical')
            source: Source of the event (e.g., 'worker', 'api', 'system')

        Returns:
            ID of the created event

        Raises:
            Exception: If event creation fails
        """
        try:
            query = """
                INSERT INTO sse_events (event_type, event_data, priority, source, retry_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (event_type, json.dumps(event_data), priority, source, 0),
                    )
                    result = cur.fetchone()
                    if result:
                        event_id = result["id"]
                        logger.debug(
                            f"Created SSE event: {event_type} with ID {event_id}"
                        )
                        return event_id
                    else:
                        raise Exception("Failed to create SSE event")

        except Exception as e:
            logger.error(f"Failed to create SSE event {event_type}: {e}")
            raise

    def create_image_captured_event(
        self,
        camera_id: int,
        timelapse_id: int,
        image_count: int,
        day_number: int,
    ) -> int:
        """
        Helper method to create an image captured event.

        Args:
            camera_id: ID of the camera
            timelapse_id: ID of the timelapse
            image_count: Current image count
            day_number: Day number of the capture

        Returns:
            ID of the created event
        """
        event_data = {
            "camera_id": camera_id,
            "timelapse_id": timelapse_id,
            "image_count": image_count,
            "day_number": day_number,
        }

        return self.create_event(
            event_type="image_captured",
            event_data=event_data,
            priority="normal",
            source="worker",
        )

    def create_camera_status_event(
        self,
        camera_id: int,
        status: str,
        health_status: Optional[str] = None,
    ) -> int:
        """
        Helper method to create a camera status changed event.

        Args:
            camera_id: ID of the camera
            status: New camera status
            health_status: Optional health status

        Returns:
            ID of the created event
        """
        event_data = {
            "camera_id": camera_id,
            "status": status,
        }

        if health_status:
            event_data["health_status"] = health_status

        return self.create_event(
            event_type="camera_status_changed",
            event_data=event_data,
            priority="high",
            source="worker",
        )

    def create_timelapse_status_event(
        self,
        camera_id: int,
        timelapse_id: int,
        status: str,
    ) -> int:
        """
        Helper method to create a timelapse status changed event.

        Args:
            camera_id: ID of the camera
            timelapse_id: ID of the timelapse
            status: New timelapse status

        Returns:
            ID of the created event
        """
        event_data = {
            "camera_id": camera_id,
            "timelapse_id": timelapse_id,
            "status": status,
        }

        return self.create_event(
            event_type="timelapse_status_changed",
            event_data=event_data,
            priority="high",
            source="worker",
        )

    def cleanup_old_events(self, max_age_hours: int = 24) -> int:
        """
        Clean up old SSE events (sync version).

        Args:
            max_age_hours: Maximum age of events to keep in hours

        Returns:
            Number of events deleted

        Raises:
            Exception: If cleanup fails
        """
        try:
            query = """
                DELETE FROM sse_events
                WHERE created_at < NOW() - INTERVAL '%s hours'
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (max_age_hours,))
                    affected = cur.rowcount

                    if affected and affected > 0:
                        logger.info(f"Cleaned up {affected} old SSE events")

                    return affected or 0

        except Exception as e:
            logger.error(f"Failed to cleanup old SSE events: {e}")
            return 0
