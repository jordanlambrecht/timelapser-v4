# backend/app/database/log_operations.py

"""
Log database operations module - Composition Pattern.

This module handles all log-related database operations including:
- Log retrieval and filtering
- Log management operations
- Analytics and reporting
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json
from loguru import logger

from .core import AsyncDatabase, SyncDatabase
from ..models.log_model import Log, LogCreate
from ..constants import (
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_CORRUPTION_HISTORY_HOURS,
    DEFAULT_DASHBOARD_QUALITY_TREND_DAYS,
)


class LogOperations:
    """Async log database operations."""

    def __init__(self, db: AsyncDatabase):
        self.db = db

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
    ) -> Dict[str, Any]:
        """
        Get logs with pagination and filtering.

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
            where_conditions.append("l.message ILIKE %(search)s")
            params["search"] = f"%{search_query}%"

        where_clause = (
            "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        )

        # Count query
        count_query = f"""
            SELECT COUNT(*)
            FROM logs l
            LEFT JOIN cameras c ON l.camera_id = c.id
            {where_clause}
        """

        # Data query
        data_query = f"""
            SELECT
                l.*,
                c.name as camera_name
            FROM logs l
            LEFT JOIN cameras c ON l.camera_id = c.id
            {where_clause}
            ORDER BY l.timestamp DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """

        params.update({"limit": page_size, "offset": offset})

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get total count
                await cur.execute(count_query, params)
                total_count = (await cur.fetchone())[0]

                # Get logs
                await cur.execute(data_query, params)
                results = await cur.fetchall()
                logs = [self._row_to_log(row) for row in results]

                total_pages = (total_count + page_size - 1) // page_size

                return {
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
            VALUES (%(level)s, %(message)s, %(logger_name)s, %(source)s, %(camera_id)s, %(extra_data)s, NOW())
            RETURNING *
        """

        params = {
            "level": level.upper(),
            "message": message,
            "logger_name": logger_name,
            "source": source,
            "camera_id": camera_id,
            "extra_data": json.dumps(extra_data) if extra_data else None,
        }

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return self._row_to_log(result)

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

        # Build bulk insert query
        values_clauses = []
        params = {}

        for i, log_entry in enumerate(log_entries):
            values_clauses.append(
                f"(%(level_{i})s, %(message_{i})s, %(logger_name_{i})s, %(source_{i})s, %(camera_id_{i})s, %(extra_data_{i})s, NOW())"
            )
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
                }
            )

        values_sql = ", ".join(values_clauses)
        query = f"""
            INSERT INTO logs (level, message, logger_name, source, camera_id, extra_data, timestamp)
            VALUES {values_sql}
            RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_log(row) for row in results]

    async def get_camera_logs(
        self, camera_id: int, hours: int = DEFAULT_CORRUPTION_HISTORY_HOURS
    ) -> List[Log]:
        """
        Get logs for a specific camera.

        Args:
            camera_id: Camera ID
            hours: Hours to look back

        Returns:
            List of Log models
        """
        query = """
            SELECT * FROM logs
            WHERE (camera_id = %(camera_id)s OR source = %(camera_source)s)
              AND timestamp > NOW() - INTERVAL '%(hours)s hours'
            ORDER BY timestamp DESC
        """

        params = {
            "camera_id": camera_id,
            "camera_source": f"camera_{camera_id}",
            "hours": hours,
        }

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_log(row) for row in results]

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
        if days_to_keep == 0:
            query = "DELETE FROM logs"
            params = {}
        else:
            query = """
                DELETE FROM logs
                WHERE timestamp < NOW() - INTERVAL '%(days)s days'
            """
            params = {"days": days_to_keep}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount or 0

    def _row_to_log(self, row: Tuple) -> Log:
        """Convert database row to Log model."""
        return Log(
            id=row[0],
            level=row[1],
            message=row[2],
            timestamp=row[3],
            camera_id=row[4],
            source=row[5],
            logger_name=row[6],
            extra_data=json.loads(row[7]) if row[7] else None,
            camera_name=row[8] if len(row) > 8 else None,
        )


class SyncLogOperations:
    """Sync log database operations."""

    def __init__(self, db: SyncDatabase):
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
        query = """
            INSERT INTO logs (level, message, camera_id, source, logger_name, extra_data, timestamp)
            VALUES (%(level)s, %(message)s, %(camera_id)s, %(source)s, %(logger_name)s, %(extra_data)s, NOW())
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
                cur.execute(query, params)
                result = cur.fetchone()
                return self._row_to_log(result)

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
        if not log_entries:
            return []

        # Build bulk insert query
        values_clauses = []
        params = []

        for log_entry in log_entries:
            values_clauses.append("(%s, %s, %s, %s, %s, %s, NOW())")
            params.extend(
                [
                    log_entry.level.upper(),
                    log_entry.message,
                    log_entry.camera_id,
                    log_entry.source or "system",
                    log_entry.logger_name or "system",
                    json.dumps(log_entry.extra_data) if log_entry.extra_data else None,
                ]
            )

        values_sql = ", ".join(values_clauses)
        query = f"""
            INSERT INTO logs (level, message, camera_id, source, logger_name, extra_data, timestamp)
            VALUES {values_sql}
            RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [self._row_to_log(row) for row in results]

    def cleanup_old_logs(self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS) -> int:
        """
        Clean up old log entries.

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of logs deleted
        """
        if days_to_keep == 0:
            query = "DELETE FROM logs"
            params = ()
        else:
            query = """
                DELETE FROM logs
                WHERE timestamp < NOW() - INTERVAL '%s days'
            """
            params = (days_to_keep,)

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount or 0

                if affected > 0:
                    if days_to_keep == 0:
                        logger.info(f"Cleaned up ALL {affected} log entries")
                    else:
                        logger.info(f"Cleaned up {affected} old log entries")

                return affected

    def _row_to_log(self, row: Tuple) -> Log:
        """Convert database row to Log model."""
        return Log(
            id=row[0],
            level=row[1],
            message=row[2],
            timestamp=row[3],
            camera_id=row[4],
            source=row[5],
            logger_name=row[6],
            extra_data=json.loads(row[7]) if row[7] else None,
            camera_name=row[8] if len(row) > 8 else None,
        )
