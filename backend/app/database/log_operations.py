# backend/app/database/log_operations.py

"""
Log database operations module - Composition Pattern.

This module handles all log-related database operations including:
- Log retrieval and filtering
- Log management operations
- Analytics and reporting
"""


import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

import psycopg

from ..constants import DEFAULT_CORRUPTION_HISTORY_HOURS, DEFAULT_LOG_RETENTION_DAYS
from ..models.log_model import Log, LogCreate
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import LogOperationError


class PaginationInfo(TypedDict):
    """Pagination metadata structure."""

    current_page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next: bool
    has_prev: bool


class LogsWithPagination(TypedDict):
    """Type definition for paginated logs response."""

    logs: List[Log]
    pagination: PaginationInfo


class LogQueryBuilder:
    """Centralized query builder for log operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_logs_timestamp ON logs(timestamp DESC);
    - CREATE INDEX idx_logs_camera_id ON logs(camera_id) WHERE camera_id IS NOT NULL;
    - CREATE INDEX idx_logs_level ON logs(level);
    - CREATE INDEX idx_logs_source ON logs(source);
    - CREATE INDEX idx_logs_composite ON logs(camera_id, timestamp DESC);
    - CREATE INDEX idx_logs_message_gin ON logs USING gin(to_tsvector('english', message));
    """

    @staticmethod
    def build_filtered_logs_query(
        where_conditions: List[str], with_count: bool = False
    ):
        """Build optimized query for filtered logs with optional count."""
        where_clause = (
            "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        )

        if with_count:
            # Combined query for both data and count
            return f"""
                WITH filtered_logs AS (
                    SELECT
                        l.*,
                        c.name as camera_name
                    FROM logs l
                    LEFT JOIN cameras c ON l.camera_id = c.id
                    {where_clause}
                ),
                log_count AS (
                    SELECT COUNT(*) as total_count
                    FROM filtered_logs
                )
                SELECT
                    fl.*,
                    lc.total_count,
                    ROW_NUMBER() OVER (ORDER BY fl.timestamp DESC) as row_num
                FROM filtered_logs fl
                CROSS JOIN log_count lc
                ORDER BY fl.timestamp DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """
        else:
            # Simple data query without count
            return f"""
                SELECT
                    l.*,
                    c.name as camera_name
                FROM logs l
                LEFT JOIN cameras c ON l.camera_id = c.id
                {where_clause}
                ORDER BY l.timestamp DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """

    @staticmethod
    def build_camera_logs_query():
        """Build optimized query for camera-specific logs."""
        return """
            SELECT l.*, c.name as camera_name
            FROM logs l
            LEFT JOIN cameras c ON l.camera_id = c.id
            WHERE (l.camera_id = %(camera_id)s OR l.source = %(camera_source)s)
                AND l.timestamp > %(now)s - INTERVAL '%(hours)s hours'
            ORDER BY l.timestamp DESC
        """

    @staticmethod
    def build_bulk_insert_query(batch_size: int):
        """Build bulk insert query for log entries."""
        values_placeholders = ", ".join(
            [
                f"(%(level_{i})s, %(message_{i})s, %(logger_name_{i})s, %(source_{i})s, %(camera_id_{i})s, %(extra_data_{i})s, %(timestamp_{i})s)"
                for i in range(batch_size)
            ]
        )

        return f"""
            INSERT INTO logs (level, message, logger_name, source, camera_id, extra_data, timestamp)
            VALUES {values_placeholders}
            RETURNING *
        """


class LogOperations:
    """Async log database operations."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_log_caches(
        self, log_id: Optional[int] = None, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to logs using sophisticated cache system."""
        # Clear log-related caches using advanced cache manager
        cache_patterns = [
            "log:get_logs",
            "log:get_camera_logs",
        ]

        if log_id:
            cache_patterns.extend(
                [f"log:get_log_by_id:{log_id}", f"log:metadata:{log_id}"]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(log_id, updated_at)
                await self.cache_invalidation.invalidate_with_etag_validation(
                    f"log:metadata:{log_id}", etag
                )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    @cached_response(ttl_seconds=10, key_prefix="log")
    async def get_logs(
        self,
        camera_id: Optional[int] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        search_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> LogsWithPagination:
        """
        Get logs with pagination and filtering.

        Uses 10s caching for brief caching to help with rapid pagination.

        Args:
            camera_id: Filter by camera ID
            level: Filter by log level
            source: Filter by source
            search_query: Search in message content
            start_date: Filter by start date
            end_date: Filter by end date
            page: Page number (1-based)
            page_size: Number of logs per page

        Returns:
            Dictionary with logs, pagination info, and metadata
        """
        # Validate inputs
        page = max(1, page)
        page_size = max(1, min(100, page_size))  # Cap at 100

        offset = (page - 1) * page_size

        # Build where conditions
        where_conditions = []
        params = {}

        if level:
            where_conditions.append("l.level = %(level)s")
            params["level"] = level.upper()

        if source:
            where_conditions.append("l.source = %(source)s")
            params["source"] = source

        if camera_id:
            where_conditions.append(
                "(l.camera_id = %(camera_id)s OR l.source = %(camera_source)s)"
            )
            params["camera_id"] = camera_id
            params["camera_source"] = f"camera_{camera_id}"

        if start_date:
            where_conditions.append("l.timestamp >= %(start_date)s")
            params["start_date"] = start_date

        if end_date:
            where_conditions.append("l.timestamp <= %(end_date)s")
            params["end_date"] = end_date

        if search_query:
            # Use full-text search for better performance on large datasets
            where_conditions.append(
                "to_tsvector('english', l.message) @@ plainto_tsquery('english', %(search)s)"
            )
            params["search"] = search_query

        # Remove manual caching - now handled by @cached_response decorator

        params.update({"limit": page_size, "offset": offset})

        # Use optimized query builder that combines count and data in single query
        query = LogQueryBuilder.build_filtered_logs_query(
            where_conditions, with_count=True
        )

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    results = await cur.fetchall()

                    if not results:
                        # Return empty result set
                        result = {
                            "logs": [],
                            "pagination": {
                                "current_page": page,
                                "page_size": page_size,
                                "total_count": 0,
                                "total_pages": 0,
                                "has_next": False,
                                "has_prev": page > 1,
                            },
                        }
                    else:
                        # Extract total count from first row (all rows have same total_count)
                        total_count = results[0]["total_count"]
                        logs = [self._row_to_log_with_count(row) for row in results]
                        total_pages = (total_count + page_size - 1) // page_size

                        result = {
                            "logs": logs,
                            "pagination": {
                                "current_page": page,
                                "page_size": page_size,
                                "total_count": total_count,
                                "total_pages": total_pages,
                                "has_next": page < total_pages,
                                "has_prev": page > 1,
                            },
                        }

                    return cast(LogsWithPagination, result)
        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError):
            raise LogOperationError(
                "Failed to retrieve logs",
                operation="get_logs",
            )

    async def add_log_entry(
        self,
        level: str,
        message: str,
        logger_name: str = "system",
        source: str = "system",
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Log:
        """
        Add a log entry to the database.

        Args:
            level: Log level
            message: Log message
            logger_name: Logger name
            source: Log source
            camera_id: Optional camera ID
            extra_data: Optional extra data

        Returns:
            Created Log model
        """
        query = """
            INSERT INTO logs (level, message, logger_name, source, camera_id, extra_data, timestamp)
            VALUES (%(level)s, %(message)s, %(logger_name)s, %(source)s, %(camera_id)s, %(extra_data)s, %(timestamp)s)
            RETURNING *
        """

        params = {
            "level": level.upper(),
            "message": message,
            "logger_name": logger_name,
            "source": source,
            "camera_id": camera_id,
            "extra_data": json.dumps(extra_data) if extra_data else None,
            "timestamp": utc_now(),
        }

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    result = await cur.fetchone()
                    log = self._row_to_log(result)

                    # Clear related caches after successful creation
                    await self._clear_log_caches()

                    return log
        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError):
            raise LogOperationError(
                "Failed to add log entry", operation="add_log_entry"
            )

    async def create_log(self, log_entry: LogCreate) -> Log:
        """
        Create a single log entry from LogCreate model.

        Args:
            log_entry: LogCreate model instance

        Returns:
            Created Log model
        """
        return await self.add_log_entry(
            level=log_entry.level,
            message=log_entry.message,
            logger_name=log_entry.logger_name or "system",
            source=log_entry.source or "system",
            camera_id=log_entry.camera_id,
            extra_data=log_entry.extra_data,
        )

    async def bulk_create_logs(self, log_entries: List[LogCreate]) -> List[Log]:
        """
        Bulk create multiple log entries for efficient batching.

        Args:
            log_entries: List of LogCreate model instances

        Returns:
            List of created Log model instances
        """
        if not log_entries:
            return []

        # Use optimized query builder for bulk inserts with centralized time
        batch_size = len(log_entries)
        now = utc_now()
        query = LogQueryBuilder.build_bulk_insert_query(batch_size)

        # Build parameters for bulk insert
        params = {}
        for i, log_entry in enumerate(log_entries):
            params.update(
                {
                    f"level_{i}": log_entry.level.upper(),
                    f"message_{i}": log_entry.message,
                    f"logger_name_{i}": log_entry.logger_name or "system",
                    f"source_{i}": log_entry.source or "system",
                    f"camera_id_{i}": log_entry.camera_id,
                    f"extra_data_{i}": (
                        json.dumps(log_entry.extra_data)
                        if log_entry.extra_data
                        else None
                    ),
                    f"timestamp_{i}": now,
                }
            )

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    results = await cur.fetchall()
                    logs = [self._row_to_log(row) for row in results]

                    # Clear related caches after successful bulk creation
                    await self._clear_log_caches()

                    return logs
        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError):
            raise LogOperationError(
                "Failed to bulk create log entries", operation="bulk_create_logs"
            )

    @cached_response(ttl_seconds=30, key_prefix="log")
    async def get_camera_logs(
        self, camera_id: int, hours: int = DEFAULT_CORRUPTION_HISTORY_HOURS
    ) -> List[Log]:
        """
        Get logs for a specific camera with 30s caching.

        Args:
            camera_id: Camera ID
            hours: Hours to look back

        Returns:
            List of Log models
        """

        # Use optimized query builder with centralized time
        query = LogQueryBuilder.build_camera_logs_query()
        now = utc_now()
        params = {
            "camera_id": camera_id,
            "camera_source": f"camera_{camera_id}",
            "hours": hours,
            "now": now,
        }

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    results = await cur.fetchall()
                    return [self._row_to_log(row) for row in results]
        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError):
            raise LogOperationError(
                "Failed to retrieve camera logs", operation="get_camera_logs"
            )

    async def delete_old_logs(
        self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS
    ) -> int:
        """
        Delete old log entries.

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of logs deleted
        """
        try:
            if days_to_keep == 0:
                query = "DELETE FROM logs"
                params = None
            else:
                query = """
                    DELETE FROM logs
                    WHERE timestamp < %(now)s - INTERVAL '%(days)s days'
                """
                params = {"now": utc_now(), "days": days_to_keep}

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    if params:
                        await cur.execute(query, params)
                    else:
                        await cur.execute(query)
                    deleted_count = cur.rowcount or 0

                    # Clear related caches after successful deletion
                    if deleted_count > 0:
                        await self._clear_log_caches()

                    return deleted_count
        except (psycopg.Error, KeyError, ValueError) as e:
            raise LogOperationError(
                f"Failed to delete old logs (keeping {days_to_keep} days)",
                details={
                    "operation": "delete_old_logs",
                    "days_to_keep": days_to_keep,
                    "error": str(e),
                },
            )

    def _row_to_log(self, row: Dict[str, Any]) -> Log:
        """Convert database row to Log model."""
        return Log(
            id=row["id"],
            level=row["level"],
            message=row["message"],
            timestamp=row["timestamp"],
            camera_id=row["camera_id"],
            source=row["source"],
            logger_name=row["logger_name"],
            extra_data=row["extra_data"] if row["extra_data"] else None,
            camera_name=row.get("camera_name"),
        )

    def _row_to_log_with_count(self, row: Dict[str, Any]) -> Log:
        """Convert database row with count data to Log model."""
        return Log(
            id=row["id"],
            level=row["level"],
            message=row["message"],
            timestamp=row["timestamp"],
            camera_id=row["camera_id"],
            source=row["source"],
            logger_name=row["logger_name"],
            extra_data=row["extra_data"] if row["extra_data"] else None,
            camera_name=row["camera_name"],
        )


class SyncLogOperations:
    """Sync log database operations."""

    def __init__(self, db: SyncDatabase) -> None:
        self.db = db

    def write_log_entry(
        self,
        level: str,
        message: str,
        source: str = "system",
        camera_id: Optional[int] = None,
        logger_name: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Log:
        """
        Write a log entry to the database.

        Args:
            level: Log level
            message: Log message
            source: Log source
            camera_id: Optional camera ID
            logger_name: Optional logger name
            extra_data: Optional extra data

        Returns:
            Created Log model
        """
        try:
            query = """
                INSERT INTO logs (level, message, camera_id, source, logger_name, extra_data, timestamp)
                VALUES (%(level)s, %(message)s, %(camera_id)s, %(source)s, %(logger_name)s, %(extra_data)s, %s)
                RETURNING *
            """

            params = {
                "level": level.upper(),
                "message": message,
                "camera_id": camera_id,
                "source": source,
                "logger_name": logger_name,
                "extra_data": json.dumps(extra_data) if extra_data else None,
            }

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, list(params.values()) + [utc_now()])
                    result = cur.fetchone()
                    return self._row_to_log(result)
        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError):
            raise LogOperationError(
                f"Failed to write log entry (level: {level})",
                details={
                    "operation": "write_log_entry",
                    "level": level,
                    "message": message[:100] + "..." if len(message) > 100 else message,
                    "camera_id": camera_id,
                },
            )

    def create_log(self, log_entry: LogCreate) -> Log:
        """
        Create a single log entry from LogCreate model.

        Args:
            log_entry: LogCreate model instance

        Returns:
            Created Log model
        """
        return self.write_log_entry(
            level=log_entry.level,
            message=log_entry.message,
            logger_name=log_entry.logger_name or "system",
            source=log_entry.source or "system",
            camera_id=log_entry.camera_id,
            extra_data=log_entry.extra_data,
        )

    def bulk_create_logs(self, log_entries: List[LogCreate]) -> List[Log]:
        """
        Bulk create multiple log entries for efficient batching.

        Args:
            log_entries: List of LogCreate model instances

        Returns:
            List of created Log model instances
        """
        try:
            if not log_entries:
                return []

            # Use centralized query builder
            batch_size = len(log_entries)
            now = utc_now()
            query = LogQueryBuilder.build_bulk_insert_query(batch_size)

            # Build parameters for bulk insert
            params = {}
            for i, log_entry in enumerate(log_entries):
                params.update(
                    {
                        f"level_{i}": log_entry.level.upper(),
                        f"message_{i}": log_entry.message,
                        f"logger_name_{i}": log_entry.logger_name or "system",
                        f"source_{i}": log_entry.source or "system",
                        f"camera_id_{i}": log_entry.camera_id,
                        f"extra_data_{i}": (
                            json.dumps(log_entry.extra_data)
                            if log_entry.extra_data
                            else None
                        ),
                        f"timestamp_{i}": now,
                    }
                )

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    results = cur.fetchall()
                    return [self._row_to_log(row) for row in results]
        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError):
            raise LogOperationError(
                f"Failed to bulk create {len(log_entries)} log entries",
                details={
                    "operation": "bulk_create_logs",
                    "batch_size": len(log_entries),
                    "error": "An error occurred",
                },
            )

    def cleanup_old_logs(self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS) -> int:
        """
        Clean up old log entries.

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of logs deleted
        """
        try:
            if days_to_keep == 0:
                query = "DELETE FROM logs"
                params = ()
            else:
                query = """
                    DELETE FROM logs
                    WHERE timestamp < %(now)s - INTERVAL %(days)s * INTERVAL '1 day'
                """
                params = {"now": utc_now(), "days": days_to_keep}

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    affected = cur.rowcount or 0

                    if affected > 0:
                        pass
                        # if days_to_keep == 0:
                        #     logger.info(
                        #         f"Cleaned up ALL {affected} log entries",
                        #         emoji=LogEmoji.CLEANUP,
                        #     )
                        # else:
                        #     logger.info(
                        #         f"Cleaned up {affected} old log entries",
                        #         emoji=LogEmoji.CLEANUP,
                        #     )

                    return affected
        except (psycopg.Error, KeyError, ValueError) as e:
            raise LogOperationError(
                f"Failed to cleanup old logs (keeping {days_to_keep} days)",
                details={
                    "operation": "cleanup_old_logs",
                    "days_to_keep": days_to_keep,
                    "error": str(e),
                },
            )

    def _row_to_log(self, row: Dict[str, Any]) -> Log:
        """Convert database row to Log model."""
        return Log(
            id=row["id"],
            level=row["level"],
            message=row["message"],
            timestamp=row["timestamp"],
            camera_id=row["camera_id"],
            source=row["source"],
            logger_name=row["logger_name"],
            extra_data=row["extra_data"] if row["extra_data"] else None,
            camera_name=row.get("camera_name"),
        )
