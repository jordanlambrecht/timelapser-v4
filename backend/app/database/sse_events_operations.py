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
import psycopg

from .core import AsyncDatabase, SyncDatabase
from ..enums import SSEPriority
from ..utils.time_utils import utc_now
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.cache_invalidation import CacheInvalidationService


class SSEEventQueryBuilder:
    """Centralized query builder for SSE events operations."""

    @staticmethod
    def get_base_select_fields():
        """Get standard fields for SSE event queries."""
        return "id, event_type, event_data, created_at, priority, source"

    @staticmethod
    def build_pending_events_query():
        """Build optimized query for pending events with priority ordering."""
        fields = SSEEventQueryBuilder.get_base_select_fields()
        return f"""
            SELECT {fields}
            FROM sse_events
            WHERE processed_at IS NULL
                AND created_at > %s
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'normal' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at ASC
            LIMIT %s
        """

    @staticmethod
    def build_event_stats_query():
        """Build optimized statistics query using CTEs for better performance."""
        return """
            WITH event_counts AS (
                SELECT
                    COUNT(*) as total_events,
                    COUNT(*) FILTER (WHERE processed_at IS NULL) as pending_events,
                    COUNT(*) FILTER (WHERE processed_at IS NOT NULL) as processed_events,
                    COUNT(*) FILTER (
                        WHERE created_at > NOW() - INTERVAL '1 hour'
                    ) as recent_events,
                    COUNT(DISTINCT event_type) as unique_event_types
                FROM sse_events
            )
            SELECT * FROM event_counts
        """


class SSEEventsOperations:
    """
    Async SSE events database operations using composition pattern.

    This class handles creating, retrieving, and managing SSE events
    stored in the database for reliable real-time event streaming.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """
        Initialize SSEEventsOperations with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_sse_event_caches(
        self,
        event_id: Optional[int] = None,
        event_type: Optional[str] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Clear caches related to SSE events using sophisticated cache system."""
        # Clear SSE event caches using advanced cache manager
        cache_patterns = [
            "sse_events:get_pending_events",
            "sse_events:get_event_stats",
        ]

        if event_id:
            cache_patterns.extend(
                [
                    f"sse_events:event_by_id:{event_id}",
                    f"sse_events:metadata:{event_id}",
                ]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(event_id, updated_at)
                await self.cache_invalidation.invalidate_with_etag_validation(
                    f"sse_events:metadata:{event_id}", etag
                )

        if event_type:
            cache_patterns.append(f"sse_events:by_type:{event_type}")

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    async def create_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: str = SSEPriority.NORMAL,
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

                        # Clear related caches after successful creation
                        await self._clear_sse_event_caches(
                            event_id, event_type, updated_at=utc_now()
                        )

                        return event_id
                    else:
                        raise psycopg.DatabaseError("Failed to create SSE event")

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create SSE event {event_type}: {e}")
            raise

    async def create_events_batch(self, events: List[Dict[str, Any]]) -> List[int]:
        """
        Create multiple SSE events in a single transaction for optimal performance.

        Args:
            events: List of event dictionaries with keys: event_type, event_data, priority, source

        Returns:
            List of created event IDs

        Raises:
            Exception: If batch creation fails
        """
        if not events:
            return []

        try:
            query = """
                INSERT INTO sse_events (event_type, event_data, priority, source, retry_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """

            # Prepare parameters for batch execution
            params = []
            for event in events:
                params.append(
                    (
                        event["event_type"],
                        json.dumps(event["event_data"]),
                        event.get("priority", SSEPriority.NORMAL),
                        event.get("source", "system"),
                        0,
                    )
                )

            event_ids = []

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use executemany with returning=True for efficient batch insert
                    await cur.executemany(query, params, returning=True)

                    # Collect all returned IDs
                    for result in cur.results():
                        row = await result.fetchone()
                        if row:
                            event_id = row["id"] if isinstance(row, dict) else row[0]
                            event_ids.append(event_id)

                    if event_ids:
                        # Clear related caches after successful batch creation
                        await self._clear_sse_event_caches()
                        logger.debug(f"Created {len(event_ids)} SSE events in batch")

                    return event_ids

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create SSE events batch: {e}")
            raise

    @cached_response(ttl_seconds=15, key_prefix="sse_events")
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
            # Use optimized query builder for consistent query construction
            query = SSEEventQueryBuilder.build_pending_events_query()
            cutoff_time = utc_now() - timedelta(minutes=max_age_minutes)

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

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
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

                    if updated_count > 0:
                        # Clear related caches after successful processing
                        await self._clear_sse_event_caches()

                    logger.debug(f"Marked {updated_count} SSE events as processed")
                    return updated_count

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to mark SSE events as processed: {e}")
            raise

    async def cleanup_old_events(self, max_age_hours: int = 24) -> int:
        """
        Clean up old SSE events to prevent table bloat.

        FIXED: Now cleans up events by created_at age instead of only processed events.
        This ensures all old events are cleaned up, not just processed ones.

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

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (max_age_hours,))
                    deleted_count = cur.rowcount

                    if deleted_count > 0:
                        # Clear related caches after successful cleanup
                        await self._clear_sse_event_caches()
                        logger.info(
                            f"Cleaned up {deleted_count} old SSE events (older than {max_age_hours}h)"
                        )
                    else:
                        logger.debug(
                            f"No old SSE events found for cleanup (older than {max_age_hours}h)"
                        )

                    return deleted_count

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to cleanup old SSE events: {e}")
            raise

    @cached_response(ttl_seconds=60, key_prefix="sse_events")
    async def get_event_stats(self) -> Dict[str, Any]:
        """
        Get statistics about SSE events for monitoring.

        Returns:
            Dictionary with event statistics

        Raises:
            Exception: If stats retrieval fails
        """
        try:
            # Use optimized CTE-based query for better performance
            query = SSEEventQueryBuilder.build_event_stats_query()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    row = await cur.fetchone()

                    if row:
                        stats = {
                            "total_events": row["total_events"],
                            "pending_events": row["pending_events"],
                            "processed_events": row["processed_events"],
                            "recent_events": row["recent_events"],
                            "unique_event_types": row["unique_event_types"],
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

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get SSE event stats: {e}")
            raise


class SyncSSEEventsOperations:
    """
    Sync SSE events database operations for worker processes.

    This class provides synchronous database operations for SSE events,
    used by worker processes that need to create events.
    """

    def __init__(self, db: SyncDatabase) -> None:
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
        priority: str = SSEPriority.NORMAL,
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
                        raise psycopg.DatabaseError("Failed to create SSE event")

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create SSE event {event_type}: {e}")
            raise

    # Removed business logic helper methods:
    # - create_image_captured_event()
    # - create_camera_status_event()
    # - create_timelapse_status_event()
    # These should be in service layer, not database layer

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

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to cleanup old SSE events: {e}")
            return 0
