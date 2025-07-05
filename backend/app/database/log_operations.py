# backend/app/database/log_operations.py

"""
Log database operations module - Composition Pattern.

This module handles all log-related database operations including:
- Log retrieval and filtering
- Log management operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

# Import database core for composition
from .core import AsyncDatabase, SyncDatabase
from ..models.log_model import Log
from ..models.log_summary_model import (
    LogSourceModel,
    LogSummaryModel,
    ErrorCountBySourceModel,
)
from ..constants import (
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_CORRUPTION_HISTORY_HOURS,
    DEFAULT_DASHBOARD_QUALITY_TREND_DAYS,
)


def _row_to_log_shared(row: Dict[str, Any]) -> Log:
    """
    Shared helper function for converting database row to Log model.
    
    This eliminates duplicate logic between async and sync classes.
    Filters fields that belong to Log model and creates proper instance.
    
    Args:
        row: Database row data as dictionary
        
    Returns:
        Log model instance
    """
    # Filter fields that belong to Log model
    log_fields = {k: v for k, v in row.items() if k in Log.model_fields}
    return Log(**log_fields)


class LogOperations:
    """Log database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db

    def _row_to_log(self, row: Dict[str, Any]) -> Log:
        """Convert database row to Log model."""
        return _row_to_log_shared(row)

    async def get_logs(
        self,
        camera_id: Optional[int] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        search_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Retrieve logs with comprehensive filtering and pagination.

        Args:
            camera_id: Optional camera ID to filter by
            level: Optional log level to filter by
            source: Optional source to filter by
            search_query: Optional text search in log messages
            start_date: Optional start date for date range filtering
            end_date: Optional end date for date range filtering
            page: Page number (1-based)
            page_size: Number of logs per page

        Returns:
            Dictionary containing Log models and pagination metadata
        """
        offset = (page - 1) * page_size

        # Build WHERE clause based on filters
        where_conditions = []
        params = []

        if camera_id:
            where_conditions.append("(camera_id = %s OR source = %s)")
            params.extend([camera_id, f"camera_{camera_id}"])

        if level:
            where_conditions.append("level = %s")
            params.append(level.upper())

        if source:
            where_conditions.append("source = %s")
            params.append(source)

        if search_query:
            where_conditions.append("(message ILIKE %s OR logger_name ILIKE %s)")
            search_pattern = f"%{search_query}%"
            params.extend([search_pattern, search_pattern])

        if start_date:
            where_conditions.append("timestamp >= %s")
            params.append(start_date)

        if end_date:
            where_conditions.append("timestamp <= %s")
            params.append(end_date)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get total count
                count_query = f"""
                SELECT COUNT(*) as total_count
                FROM logs
                WHERE {where_clause}
                """
                await cur.execute(count_query, params)
                count_results = await cur.fetchall()
                total_count = count_results[0]["total_count"] if count_results else 0

                # Get logs with pagination
                logs_query = f"""
                SELECT 
                    l.*,
                    c.name as camera_name
                FROM logs l
                LEFT JOIN cameras c ON l.camera_id = c.id
                WHERE {where_clause}
                ORDER BY l.timestamp DESC
                LIMIT %s OFFSET %s
                """

                logs_params = params + [page_size, offset]
                await cur.execute(logs_query, logs_params)
                log_rows = await cur.fetchall()
                logs = [self._row_to_log(row) for row in log_rows]

                return {
                    "logs": logs,  # List[Log]
                    "total_count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "filters": {
                        "camera_id": camera_id,
                        "level": level,
                        "source": source,
                        "search_query": search_query,
                        "start_date": start_date.isoformat() if start_date else None,
                        "end_date": end_date.isoformat() if end_date else None,
                    },
                }

    async def get_log_sources(self) -> List[LogSourceModel]:
        """
        Get all available log sources.

        Returns:
            List of log source models with counts
        """
        query = """
        SELECT 
            source,
            COUNT(*) as log_count,
            MAX(timestamp) as last_log_at,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) as error_count,
            COUNT(CASE WHEN level = 'WARNING' THEN 1 END) as warning_count
        FROM logs
        WHERE timestamp > NOW() - INTERVAL '{DEFAULT_DASHBOARD_QUALITY_TREND_DAYS} days'
        GROUP BY source
        ORDER BY source 
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
                return [LogSourceModel(**row) for row in rows]

    # DEPRECATED: get_log_levels() method removed - use static LOG_LEVELS constant from constants.py
    # Log levels are hardcoded constants and don't require database queries

    async def get_log_summary(self, hours: int = DEFAULT_CORRUPTION_HISTORY_HOURS) -> LogSummaryModel:
        """
        Get log summary statistics for a time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Log summary model with statistics
        """
        query = """
        SELECT 
            COUNT(*) as total_logs,
            COUNT(CASE WHEN level = 'CRITICAL' THEN 1 END) as critical_count,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) as error_count,
            COUNT(CASE WHEN level = 'WARNING' THEN 1 END) as warning_count,
            COUNT(CASE WHEN level = 'INFO' THEN 1 END) as info_count,
            COUNT(CASE WHEN level = 'DEBUG' THEN 1 END) as debug_count,
            COUNT(DISTINCT source) as unique_sources,
            COUNT(DISTINCT camera_id) as unique_cameras,
            MIN(timestamp) as first_log_at,
            MAX(timestamp) as last_log_at
        FROM logs
        WHERE timestamp > NOW() - INTERVAL '%s hours'
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (hours,))
                results = await cur.fetchall()
                if results:
                    return LogSummaryModel(**results[0])
                return LogSummaryModel(
                    total_logs=0,
                    critical_count=0,
                    error_count=0,
                    warning_count=0,
                    info_count=0,
                    debug_count=0,
                    unique_sources=0,
                    unique_cameras=0,
                    first_log_at=None,
                    last_log_at=None,
                )

    async def delete_old_logs(self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS) -> int:
        """
        Delete old logs based on retention policy.

        Args:
            days_to_keep: Number of days to keep logs (default: from constants)

        Returns:
            Number of logs deleted
        """
        query = """
        DELETE FROM logs 
        WHERE timestamp < NOW() - INTERVAL '%s days'
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (days_to_keep,))
                affected = cur.rowcount

                return affected or 0

    async def add_log_entry(
        self,
        level: str,
        message: str,
        logger_name: str,
        source: str = "system",
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Log:
        """
        Add a log entry to the database (async version).

        Args:
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            message: Log message
            logger_name: Name of the logger
            source: Source of the log (e.g., 'system', 'camera_1', 'worker')
            camera_id: Optional camera ID if log is camera-specific
            extra_data: Optional additional data as JSON

        Returns:
            Created Log model instance
        """
        query = """
        INSERT INTO logs (
            level, message, logger_name, source, camera_id, extra_data, timestamp
        ) VALUES (
            %s, %s, %s, %s, %s, %s, NOW()
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (
                        level.upper(),
                        message,
                        logger_name,
                        source,
                        camera_id,
                        extra_data,
                    ),
                )
                results = await cur.fetchall()

                if results:
                    log_entry_row = results[0]
                    log_entry = self._row_to_log(log_entry_row)

                    return log_entry

                raise Exception("Failed to write log entry")


class SyncLogOperations:
    """Sync log database operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def _row_to_log(self, row: Dict[str, Any]) -> Log:
        """Convert database row to Log model."""
        return _row_to_log_shared(row)

    def add_log_entry(
        self,
        level: str,
        message: str,
        source: str = "system",
        camera_id: Optional[int] = None,
        **kwargs,  # Accept additional args for compatibility
    ) -> Log:
        """Alias for write_log_entry for compatibility."""
        return self.write_log_entry(
            level=level, message=message, source=source, camera_id=camera_id
        )

    def write_log_entry(
        self,
        level: str,
        message: str,
        source: str = "system",
        camera_id: Optional[int] = None,
    ) -> Log:
        """
        Write a log entry to the database using the actual table schema.

        Args:
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            message: Log message
            source: Source of the log (e.g., 'system', 'camera_1', 'worker')
            camera_id: Optional camera ID if log is camera-specific

        Returns:
            Created Log model instance
        """
        # Use the actual logs table schema: id, level, message, camera_id, timestamp
        query = """
        INSERT INTO logs (level, message, camera_id, timestamp) 
        VALUES (%s, %s, %s, NOW())
        RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        level.upper(),
                        message,
                        camera_id,
                    ),
                )
                results = cur.fetchall()

                if results:
                    log_entry_row = results[0]
                    log_entry = self._row_to_log(log_entry_row)

                    return log_entry

                raise Exception("Failed to write log entry")

    def get_camera_logs(self, camera_id: int, hours: int = DEFAULT_CORRUPTION_HISTORY_HOURS) -> List[Log]:
        """
        Get logs for a specific camera.

        Args:
            camera_id: ID of the camera
            hours: Number of hours to look back

        Returns:
            List of camera Log models
        """
        query = """
        SELECT * FROM logs
        WHERE (camera_id = %s OR source = %s)
        AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp DESC
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id, f"camera_{camera_id}", hours))
                results = cur.fetchall()
                return [self._row_to_log(row) for row in results]

    def cleanup_old_logs(self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS) -> int:
        """
        Clean up old log entries.

        Args:
            days_to_keep: Number of days to keep logs (default: from constants)

        Returns:
            Number of logs deleted
        """
        query = """
        DELETE FROM logs
        WHERE timestamp < NOW() - INTERVAL '%s days'
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (days_to_keep,))
                affected = cur.rowcount

                if affected and affected > 0:
                    logger.info(f"Cleaned up {affected} old log entries")

                return affected or 0

    def get_error_count_by_source(
        self, hours: int = DEFAULT_CORRUPTION_HISTORY_HOURS
    ) -> List[ErrorCountBySourceModel]:
        """
        Get error count by source for monitoring.

        Args:
            hours: Number of hours to analyze

        Returns:
            List of source error count models
        """
        query = """
        SELECT
            source,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) as error_count,
            COUNT(CASE WHEN level = 'CRITICAL' THEN 1 END) as critical_count,
            COUNT(*) as total_count,
            MAX(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN timestamp END) as last_error_at
        FROM logs
        WHERE timestamp > NOW() - INTERVAL '%s hours'
        GROUP BY source
        HAVING COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 END) > 0
        ORDER BY error_count + critical_count DESC
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (hours,))
                rows = cur.fetchall()
                return [ErrorCountBySourceModel(**row) for row in rows]
