# backend/app/database/recovery_operations.py
"""
Recovery Operations - Database operations for job recovery across all job types.

This module provides database operations for recovering stuck jobs, following the
standard operations layer pattern. Handles both async and sync database operations
for consistent recovery behavior across all job systems.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import psycopg

from ..enums import JobStatus, SSEEvent, SSEEventSource
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_timestamp_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import RecoveryOperationError


class RecoveryQueryBuilder:
    """Centralized query builder for recovery operations.

    IMPORTANT: For optimal performance, ensure these indexes exist for ALL job tables:
    - CREATE INDEX idx_{table}_status_updated ON {table}(status, updated_at) WHERE status = 'processing';
    - CREATE INDEX idx_{table}_status ON {table}(status);
    - CREATE INDEX idx_{table}_updated_at ON {table}(updated_at DESC);
    - CREATE INDEX idx_{table}_created_updated ON {table}(created_at, updated_at);
    - CREATE INDEX idx_{table}_processing_age ON {table}(updated_at) WHERE status = 'processing';

    Example for specific tables:
    - CREATE INDEX idx_overlay_generation_jobs_status_updated ON overlay_generation_jobs(status, updated_at) WHERE status = 'processing';
    - CREATE INDEX idx_thumbnail_generation_jobs_status_updated ON thumbnail_generation_jobs(status, updated_at) WHERE status = 'processing';
    - CREATE INDEX idx_scheduled_jobs_status_updated ON scheduled_jobs(status, updated_at) WHERE status = 'processing';
    """

    # Allowed job table names for SQL injection prevention
    ALLOWED_JOB_TABLES = {
        "overlay_generation_jobs",
        "thumbnail_generation_jobs",
        "scheduled_jobs",
        "video_generation_jobs",
        "image_processing_jobs",
    }

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        """Validate table name to prevent SQL injection."""
        if table_name not in RecoveryQueryBuilder.ALLOWED_JOB_TABLES:
            raise ValueError(
                f"Invalid table name: {table_name}. Must be one of: {RecoveryQueryBuilder.ALLOWED_JOB_TABLES}"
            )
        return table_name

    @staticmethod
    def build_find_stuck_jobs_query(table_name: str):
        """Build query to find stuck jobs in processing status using named parameters."""
        # Validate table name to prevent SQL injection
        validated_table = RecoveryQueryBuilder._validate_table_name(table_name)
        return f"""
            SELECT id, created_at, started_at
            FROM {validated_table}
            WHERE status = %(status)s
                AND started_at IS NOT NULL
                AND started_at < %(cutoff_time)s
            ORDER BY started_at ASC
        """

    @staticmethod
    def build_update_stuck_jobs_query(table_name: str):
        """Build query to update stuck jobs back to pending status using named parameters."""
        # Validate table name to prevent SQL injection
        validated_table = RecoveryQueryBuilder._validate_table_name(table_name)
        return f"""
            UPDATE {validated_table}
            SET status = %(new_status)s,
                error_message = %(error_message)s,
                started_at = NULL
            WHERE status = %(current_status)s
                AND started_at IS NOT NULL
                AND started_at < %(cutoff_time)s
        """

    @staticmethod
    def build_recovery_stats_query(table_name: str):
        """Build query to get comprehensive recovery statistics using named parameters."""
        # Validate table name to prevent SQL injection
        validated_table = RecoveryQueryBuilder._validate_table_name(table_name)
        return f"""
            WITH job_stats AS (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_count,
                    COUNT(*) FILTER (
                        WHERE status = 'processing'
                        AND started_at IS NOT NULL
                        AND started_at < %(cutoff_time)s
                    ) as stuck_count,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, started_at, created_at) - created_at))) FILTER (
                        WHERE status = 'processing'
                    ) as avg_processing_time_seconds
                FROM {validated_table}
            )
            SELECT * FROM job_stats
        """


class RecoveryOperations:
    """
    Async database operations for job recovery across all job types.

    Provides generic recovery methods that work with any job table following
    the standard pattern with 'status', 'created_at', and 'updated_at' columns.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db
        # CacheInvalidationService is now used as static class methods

    async def _clear_recovery_caches(
        self, table_name: str, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to recovery operations using sophisticated cache system."""
        # Clear recovery-related caches using advanced cache manager
        cache_patterns = [
            f"recovery:get_recovery_statistics:{table_name}",
            "recovery:recovery_stats",
        ]

        # Also clear related job caches based on table type
        if "overlay" in table_name:
            cache_patterns.extend(
                [
                    "overlay_job:get_pending_jobs",
                    "overlay_job:get_retry_eligible_jobs",
                    "overlay_job:get_job_statistics",
                ]
            )
        elif "thumbnail" in table_name:
            cache_patterns.extend(
                [
                    "thumbnail_job:get_pending_jobs",
                    "thumbnail_job:get_retry_eligible_jobs",
                    "thumbnail_job:get_job_statistics",
                ]
            )
        elif "scheduled" in table_name:
            cache_patterns.extend(
                ["scheduled_job:get_active_jobs", "scheduled_job:get_job_statistics"]
            )

        # Use ETag-aware invalidation if timestamp provided
        if updated_at:
            etag = generate_timestamp_etag(updated_at)
            await CacheInvalidationService.invalidate_with_etag_validation(
                f"recovery:metadata:{table_name}", etag
            )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    @cached_response(ttl_seconds=15, key_prefix="recovery")
    async def get_recovery_statistics(
        self,
        table_name: str,
        max_processing_age_minutes: int = 30,
    ) -> Dict[str, Any]:
        """
        Get comprehensive recovery statistics for a job table with 15s caching.

        Args:
            table_name: Name of the job table
            max_processing_age_minutes: Threshold for considering jobs stuck

        Returns:
            Dictionary with recovery statistics
        """
        try:
            cutoff_time = utc_now() - timedelta(minutes=max_processing_age_minutes)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized stats query with named parameters
                    query = RecoveryQueryBuilder.build_recovery_stats_query(table_name)
                    await cur.execute(query, {"cutoff_time": cutoff_time})

                    row = await cur.fetchone()
                    if row:
                        stats = dict(row)
                        result = {
                            "processing_count": int(stats.get("processing_count", 0)),
                            "stuck_count": int(stats.get("stuck_count", 0)),
                            "pending_count": int(stats.get("pending_count", 0)),
                            "failed_count": int(stats.get("failed_count", 0)),
                            "avg_processing_time_seconds": float(
                                stats.get("avg_processing_time_seconds", 0) or 0
                            ),
                            "cutoff_time": cutoff_time.isoformat(),
                            "table_name": table_name,
                        }
                        return result

            # Return empty stats if no data
            return {
                "processing_count": 0,
                "stuck_count": 0,
                "pending_count": 0,
                "failed_count": 0,
                "avg_processing_time_seconds": 0.0,
                "cutoff_time": cutoff_time.isoformat(),
                "table_name": table_name,
            }

        except (psycopg.Error, KeyError, ValueError) as e:
            raise RecoveryOperationError(
                f"Failed to get recovery statistics for {table_name}",
                details={
                    "operation": "get_recovery_statistics",
                    "table_name": table_name,
                    "max_processing_age_minutes": max_processing_age_minutes,
                    "error": "An error occurred",
                },
            ) from e

    async def recover_stuck_jobs_for_table(
        self,
        table_name: str,
        max_processing_age_minutes: int = 30,
        job_type_name: str = "jobs",
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generic recovery method for any job table (async version).

        Finds jobs stuck in 'processing' status for longer than the specified
        time and resets them to 'pending' status for retry.

        Args:
            table_name: Name of the job table (e.g., 'thumbnail_generation_jobs')
            max_processing_age_minutes: Maximum time a job can be in processing
            job_type_name: Human-readable job type for logging (e.g., 'thumbnail jobs')
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with recovery statistics
        """
        recovery_start_time = utc_now()

        try:
            # Calculate cutoff time for stuck jobs
            cutoff_time = recovery_start_time - timedelta(
                minutes=max_processing_age_minutes
            )

            # Find stuck jobs using optimized query builder
            find_query = RecoveryQueryBuilder.build_find_stuck_jobs_query(table_name)

            stuck_jobs = []
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        find_query,
                        {
                            "status": JobStatus.PROCESSING.value,
                            "cutoff_time": cutoff_time,
                        },
                    )
                    stuck_jobs = await cur.fetchall()

            if not stuck_jobs:
                return {
                    "stuck_jobs_found": 0,
                    "stuck_jobs_recovered": 0,
                    "stuck_jobs_failed": 0,
                    "recovery_duration_seconds": 0.0,
                    "cutoff_time": cutoff_time.isoformat(),
                    "recovery_successful": True,
                }

            # Broadcast recovery start event
            if sse_broadcaster:
                try:
                    await sse_broadcaster.broadcast_event(
                        event_type=SSEEvent.SYSTEM_WARNING,
                        data={
                            "message": f"Starting recovery of {len(stuck_jobs)} stuck {job_type_name}",
                            "job_type": job_type_name,
                            "stuck_count": len(stuck_jobs),
                            "table_name": table_name,
                        },
                        source=SSEEventSource.SYSTEM,
                    )
                except Exception:
                    # Ignore broadcast failures - not critical
                    pass

            # Reset stuck jobs to pending using optimized query builder
            update_query = RecoveryQueryBuilder.build_update_stuck_jobs_query(
                table_name
            )

            current_time = utc_now()
            error_message = f"Job recovered from stuck processing state on {current_time.isoformat()} - reset to pending for retry"

            recovered_count = 0
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        update_query,
                        {
                            "new_status": JobStatus.PENDING.value,
                            "error_message": error_message,
                            "current_status": JobStatus.PROCESSING.value,
                            "cutoff_time": cutoff_time,
                        },
                    )
                    recovered_count = cur.rowcount

                    # Clear related caches after successful recovery
                    if recovered_count > 0:
                        await self._clear_recovery_caches(
                            table_name, updated_at=current_time
                        )

            # Calculate recovery statistics
            recovery_end_time = utc_now()
            recovery_duration = (
                recovery_end_time - recovery_start_time
            ).total_seconds()

            # Broadcast recovery completion event
            if sse_broadcaster:
                try:
                    await sse_broadcaster.broadcast_event(
                        event_type=SSEEvent.SYSTEM_INFO,
                        data={
                            "message": f"Recovery completed: {recovered_count}/{len(stuck_jobs)} {job_type_name} recovered",
                            "job_type": job_type_name,
                            "recovered_count": recovered_count,
                            "total_stuck": len(stuck_jobs),
                            "table_name": table_name,
                            "recovery_duration": recovery_duration,
                        },
                        source=SSEEventSource.SYSTEM,
                    )
                except Exception:
                    # Ignore broadcast failures - not critical
                    pass

            result = {
                "stuck_jobs_found": len(stuck_jobs),
                "stuck_jobs_recovered": recovered_count,
                "stuck_jobs_failed": len(stuck_jobs) - recovered_count,
                "recovery_duration_seconds": recovery_duration,
                "cutoff_time": cutoff_time.isoformat(),
                "recovery_successful": True,
            }

            return result

        except (psycopg.Error, KeyError, ValueError):
            raise RecoveryOperationError(
                "Recovery failed",
                details={"operation": "recover_stuck_jobs_for_table"},
            )

    async def _broadcast_recovery_event(
        self,
        sse_broadcaster: Optional[Any],
        event_type: SSEEvent,
        message: str,
        **extra_data,
    ) -> None:
        """Shared utility method for broadcasting recovery events (async)."""
        if sse_broadcaster:
            try:
                await sse_broadcaster.broadcast_event(
                    event_type=event_type,
                    data={"message": message, **extra_data},
                    source=SSEEventSource.SYSTEM,
                )
            except Exception:
                # Ignore broadcast failures - not critical
                pass


class SyncRecoveryOperations:
    """
    Sync database operations for job recovery across all job types.

    Provides sync versions of recovery operations for use in worker processes
    and other sync contexts.
    """

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def recover_stuck_jobs_for_table(
        self,
        table_name: str,
        max_processing_age_minutes: int = 30,
        job_type_name: str = "jobs",
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generic recovery method for any job table (sync version).

        Finds jobs stuck in 'processing' status for longer than the specified
        time and resets them to 'pending' status for retry.

        Args:
            table_name: Name of the job table (e.g., 'thumbnail_generation_jobs')
            max_processing_age_minutes: Maximum time a job can be in processing
            job_type_name: Human-readable job type for logging (e.g., 'thumbnail jobs')
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with recovery statistics
        """
        recovery_start_time = utc_now()

        try:
            # Calculate cutoff time for stuck jobs
            cutoff_time = recovery_start_time - timedelta(
                minutes=max_processing_age_minutes
            )

            # Find stuck jobs using optimized query builder
            find_query = RecoveryQueryBuilder.build_find_stuck_jobs_query(table_name)

            stuck_jobs = []
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        find_query,
                        {
                            "status": JobStatus.PROCESSING.value,
                            "cutoff_time": cutoff_time,
                        },
                    )
                    stuck_jobs = cur.fetchall()

            if not stuck_jobs:
                return {
                    "stuck_jobs_found": 0,
                    "stuck_jobs_recovered": 0,
                    "stuck_jobs_failed": 0,
                    "recovery_duration_seconds": 0.0,
                    "cutoff_time": cutoff_time.isoformat(),
                    "recovery_successful": True,
                }

            # Broadcast recovery start event
            self._broadcast_recovery_event(
                sse_broadcaster,
                SSEEvent.SYSTEM_WARNING,
                f"Starting recovery of {len(stuck_jobs)} stuck {job_type_name}",
                job_type=job_type_name,
                stuck_count=len(stuck_jobs),
                table_name=table_name,
            )

            # Reset stuck jobs to pending using optimized query builder
            update_query = RecoveryQueryBuilder.build_update_stuck_jobs_query(
                table_name
            )

            current_time = utc_now()
            error_message = f"Job recovered from stuck processing state on {current_time.isoformat()} - reset to pending for retry"

            recovered_count = 0
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        update_query,
                        {
                            "new_status": JobStatus.PENDING.value,
                            "error_message": error_message,
                            "current_status": JobStatus.PROCESSING.value,
                            "cutoff_time": cutoff_time,
                        },
                    )
                    recovered_count = cur.rowcount

            # Calculate recovery statistics
            recovery_end_time = utc_now()
            recovery_duration = (
                recovery_end_time - recovery_start_time
            ).total_seconds()

            # Broadcast recovery completion event
            self._broadcast_recovery_event(
                sse_broadcaster,
                SSEEvent.SYSTEM_INFO,
                f"Recovery completed: {recovered_count}/{len(stuck_jobs)} {job_type_name} recovered",
                job_type=job_type_name,
                recovered_count=recovered_count,
                total_stuck=len(stuck_jobs),
                table_name=table_name,
                recovery_duration=recovery_duration,
            )

            result = {
                "stuck_jobs_found": len(stuck_jobs),
                "stuck_jobs_recovered": recovered_count,
                "stuck_jobs_failed": len(stuck_jobs) - recovered_count,
                "recovery_duration_seconds": recovery_duration,
                "cutoff_time": cutoff_time.isoformat(),
                "recovery_successful": True,
            }

            return result

        except (psycopg.Error, KeyError, ValueError) as e:
            raise RecoveryOperationError(
                "Recovery failed",
                details={"operation": "recover_stuck_jobs_for_table_sync"},
            ) from e

    def _broadcast_recovery_event(
        self,
        sse_broadcaster: Optional[Any],
        event_type: SSEEvent,
        message: str,
        **extra_data,
    ) -> None:
        """Shared utility method for broadcasting recovery events (sync)."""
        if sse_broadcaster:
            try:
                sse_broadcaster.broadcast_event(
                    event_type=event_type,
                    data={"message": message, **extra_data},
                    source=SSEEventSource.SYSTEM,
                )
            except Exception:
                # Ignore broadcast failures - not critical
                pass
