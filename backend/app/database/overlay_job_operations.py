# backend/app/database/overlay_job_operations.py
"""
Overlay Job Operations - Database layer for overlay generation job management.

Responsibilities:
- CRUD operations for overlay_generation_jobs table
- Priority-based job retrieval with batching
- Status updates and retry scheduling
- Cleanup of completed jobs
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg

from ..constants import (
    DEFAULT_OVERLAY_JOB_BATCH_SIZE,
    DEFAULT_OVERLAY_MAX_RETRIES,
    OVERLAY_JOB_RETRY_DELAYS,
)
from ..enums import JobStatus
from ..models.overlay_model import (
    OverlayGenerationJob,
    OverlayGenerationJobCreate,
    OverlayJobStatistics,
)
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import OverlayOperationError
from .recovery_operations import RecoveryOperations, SyncRecoveryOperations


class OverlayJobQueryBuilder:
    """Centralized query builder for overlay job operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_overlay_jobs_status ON overlay_generation_jobs(status);
    - CREATE INDEX idx_overlay_jobs_priority_created ON overlay_generation_jobs(priority, created_at);
    - CREATE INDEX idx_overlay_jobs_status_retry ON overlay_generation_jobs(status, retry_count) WHERE status = 'failed';
    - CREATE INDEX idx_overlay_jobs_image_id ON overlay_generation_jobs(image_id);
    - CREATE INDEX idx_overlay_jobs_completed_at ON overlay_generation_jobs(completed_at DESC) WHERE status IN ('completed', 'failed', 'cancelled');
    - CREATE INDEX idx_overlay_jobs_processing_started ON overlay_generation_jobs(started_at) WHERE status = 'processing';
    - CREATE INDEX idx_overlay_jobs_created_24h ON overlay_generation_jobs(created_at DESC) WHERE created_at > NOW() - INTERVAL '24 hours';
    """

    @staticmethod
    def get_base_select_fields():
        """Get standard fields for overlay job queries."""
        return """
            id, image_id, priority, status, job_type, retry_count,
            error_message, created_at, started_at, completed_at
        """

    @staticmethod
    def build_pending_jobs_query():
        """Build optimized query for pending jobs with priority ordering using named parameters."""
        fields = OverlayJobQueryBuilder.get_base_select_fields()
        return f"""
            SELECT {fields}
            FROM overlay_generation_jobs
            WHERE status = %(status)s
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                created_at ASC
            LIMIT %(limit)s
        """

    @staticmethod
    def build_retry_eligible_query():
        """Build safe query for jobs eligible for retry using named parameters."""
        fields = OverlayJobQueryBuilder.get_base_select_fields()
        return f"""
            SELECT {fields}
            FROM overlay_generation_jobs
            WHERE status = %(status)s
                AND retry_count < %(max_retries)s
                AND (
                    (retry_count = 0 AND completed_at < %(now)s - INTERVAL '%(delay_0)s minutes') OR
                    (retry_count = 1 AND completed_at < %(now)s - INTERVAL '%(delay_1)s minutes') OR
                    (retry_count = 2 AND completed_at < %(now)s - INTERVAL '%(delay_2)s minutes')
                )
            ORDER BY priority DESC, completed_at ASC
        """

    @staticmethod
    def build_statistics_query():
        """Build optimized statistics query using CTEs with named parameters."""
        return """
            WITH job_counts AS (
                SELECT
                    COUNT(*) FILTER (
                        WHERE created_at > %(now)s - INTERVAL '24 hours'
                    ) as total_jobs_24h,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_jobs,
                    COUNT(*) FILTER (
                        WHERE status = 'completed' AND
                        completed_at > %(now)s - INTERVAL '24 hours'
                    ) as completed_jobs_24h,
                    COUNT(*) FILTER (
                        WHERE status = 'failed' AND
                        completed_at > %(now)s - INTERVAL '24 hours'
                    ) as failed_jobs_24h,
                    COUNT(*) FILTER (
                        WHERE status = 'cancelled' AND
                        completed_at > %(now)s - INTERVAL '24 hours'
                    ) as cancelled_jobs_24h
                FROM overlay_generation_jobs
            ),
            processing_stats AS (
                SELECT
                    COALESCE(
                        AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000),
                        0
                    ) as avg_processing_time_ms
                FROM overlay_generation_jobs
                WHERE status = 'completed'
                    AND completed_at > %(now)s - INTERVAL '24 hours'
                    AND started_at IS NOT NULL
            )
            SELECT
                jc.*,
                ps.avg_processing_time_ms
            FROM job_counts jc
            CROSS JOIN processing_stats ps
        """

    @staticmethod
    def build_image_jobs_query():
        """Build query for jobs by image ID using named parameters."""
        fields = OverlayJobQueryBuilder.get_base_select_fields()
        return f"""
            SELECT {fields}
            FROM overlay_generation_jobs
            WHERE image_id = %(image_id)s
            ORDER BY created_at DESC
        """


def _row_to_overlay_job(row: Dict[str, Any]) -> OverlayGenerationJob:
    """Convert database row to OverlayGenerationJob model"""
    return OverlayGenerationJob(
        id=row["id"],
        image_id=row["image_id"],
        priority=row["priority"],
        status=row["status"],
        job_type=row["job_type"],
        retry_count=row["retry_count"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


class OverlayJobOperations:
    """
    Async database operations for overlay generation jobs.

    Provides priority-based job queuing, status management, and cleanup operations
    following the established database operations pattern.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db
        self.recovery_ops = RecoveryOperations(db)
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_overlay_job_caches(
        self,
        job_id: Optional[int] = None,
        image_id: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Clear caches related to overlay jobs using sophisticated cache system."""
        # Clear overlay job caches using advanced cache manager
        job_patterns = [
            "overlay_job:get_pending_jobs",
            "overlay_job:get_retry_eligible_jobs",
            "overlay_job:get_job_statistics",
        ]

        if job_id:
            job_patterns.extend(
                [
                    f"overlay_job:get_job_by_id:{job_id}",
                    f"overlay_job:metadata:{job_id}",
                ]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(job_id, updated_at)
                await self.cache_invalidation.invalidate_with_etag_validation(
                    f"overlay_job:metadata:{job_id}", etag
                )

        if image_id:
            job_patterns.append(f"overlay_job:image:{image_id}")

        # Clear cache patterns using advanced cache manager
        for pattern in job_patterns:
            await cache.delete(pattern)

    async def create_job(
        self, job_data: OverlayGenerationJobCreate
    ) -> Optional[OverlayGenerationJob]:
        """
        Create a new overlay generation job.

        Args:
            job_data: Job creation data

        Returns:
            Created job or None if creation failed
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO overlay_generation_jobs (image_id, priority, status, job_type)
                        VALUES (%(image_id)s, %(priority)s, %(status)s, %(job_type)s)
                        RETURNING id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        """,
                        {
                            "image_id": job_data.image_id,
                            "priority": job_data.priority,
                            "status": job_data.status,
                            "job_type": job_data.job_type,
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        job = _row_to_overlay_job(dict(row))
                        # Clear related caches after successful creation
                        await self._clear_overlay_job_caches(job.id, job.image_id)
                        return job
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to create overlay generation job: {e}", operation="create_job"
            ) from e

    @cached_response(ttl_seconds=300, key_prefix="overlay_job")
    async def get_job_by_id(self, job_id: int) -> Optional[OverlayGenerationJob]:
        """Get overlay generation job by ID with 5-minute caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        FROM overlay_generation_jobs
                        WHERE id = %(job_id)s
                        """,
                        {"job_id": job_id},
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    @cached_response(ttl_seconds=15, key_prefix="overlay_job")
    async def get_pending_jobs(
        self, limit: int = DEFAULT_OVERLAY_JOB_BATCH_SIZE
    ) -> List[OverlayGenerationJob]:
        """
        Get pending overlay generation jobs ordered by priority and creation time.

        Uses sophisticated caching with 15s TTL for high-frequency access.

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of pending jobs ordered by priority (high->medium->low) then by created_at
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayJobQueryBuilder.build_pending_jobs_query()
                    await cur.execute(
                        query, {"status": JobStatus.PENDING, "limit": limit}
                    )

                    rows = await cur.fetchall()
                    jobs = [_row_to_overlay_job(dict(row)) for row in rows]

                    return jobs

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    async def update_job_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        """
        Update job status and related timestamps.

        Args:
            job_id: ID of the job to update
            status: New status
            error_message: Error message if status is failed
            started_at: Timestamp when processing started
            completed_at: Timestamp when processing completed

        Returns:
            True if update was successful
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Build update query safely with named parameters
                    update_fields = ["status = %(status)s"]
                    params = {"status": status, "job_id": job_id}

                    if error_message is not None:
                        update_fields.append("error_message = %(error_message)s")
                        params["error_message"] = error_message

                    if started_at is not None:
                        update_fields.append("started_at = %(started_at)s")
                        params["started_at"] = started_at

                    if completed_at is not None:
                        update_fields.append("completed_at = %(completed_at)s")
                        params["completed_at"] = completed_at

                    # Safe query construction - join is not user input
                    query = f"""
                        UPDATE overlay_generation_jobs
                        SET {', '.join(update_fields)}
                        WHERE id = %(job_id)s
                    """

                    await cur.execute(query, params)

                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful update
                        await self._clear_overlay_job_caches(job_id)

                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

            return False

    async def mark_job_processing(self, job_id: int) -> bool:
        """Mark job as processing with current timestamp"""
        return await self.update_job_status(
            job_id, JobStatus.PROCESSING, started_at=utc_now()
        )

    async def mark_job_completed(self, job_id: int) -> bool:
        """Mark job as completed with current timestamp"""
        return await self.update_job_status(
            job_id, JobStatus.COMPLETED, completed_at=utc_now()
        )

    async def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """Mark job as failed with error message and timestamp"""
        return await self.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=error_message,
            completed_at=utc_now(),
        )

    async def increment_retry_count(self, job_id: int) -> bool:
        """Increment job retry count and reset to pending status"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET retry_count = retry_count + 1,
                            status = %(status)s,
                            error_message = NULL,
                            started_at = NULL,
                            completed_at = NULL
                        WHERE id = %(job_id)s AND retry_count < %(max_retries)s
                        """,
                        {
                            "status": JobStatus.PENDING,
                            "job_id": job_id,
                            "max_retries": DEFAULT_OVERLAY_MAX_RETRIES,
                        },
                    )

                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful retry increment
                        await self._clear_overlay_job_caches(job_id)

                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

            return False

    @cached_response(ttl_seconds=30, key_prefix="overlay_job")
    async def get_jobs_for_retry(self) -> List[OverlayGenerationJob]:
        """
        Get failed jobs that are eligible for retry based on retry delays.

        Uses 30s caching since retry eligibility changes slowly.

        Returns:
            List of jobs eligible for retry
        """

        try:
            # Use safe query builder with named parameters
            now = utc_now()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use safe query builder
                    query = OverlayJobQueryBuilder.build_retry_eligible_query()

                    # Build parameters safely based on configured retry delays
                    params = {
                        "status": JobStatus.FAILED,
                        "max_retries": DEFAULT_OVERLAY_MAX_RETRIES,
                        "now": now,
                        "delay_0": (
                            str(OVERLAY_JOB_RETRY_DELAYS[0])
                            if len(OVERLAY_JOB_RETRY_DELAYS) > 0
                            else "5"
                        ),
                        "delay_1": (
                            str(OVERLAY_JOB_RETRY_DELAYS[1])
                            if len(OVERLAY_JOB_RETRY_DELAYS) > 1
                            else "15"
                        ),
                        "delay_2": (
                            str(OVERLAY_JOB_RETRY_DELAYS[2])
                            if len(OVERLAY_JOB_RETRY_DELAYS) > 2
                            else "60"
                        ),
                    }

                    await cur.execute(query, params)

                    rows = await cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    async def cleanup_completed_jobs(self, hours: int = 24) -> int:
        """
        Clean up completed/failed jobs older than specified hours.

        Args:
            hours: Age threshold in hours for job cleanup

        Returns:
            Number of jobs cleaned up
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        DELETE FROM overlay_generation_jobs
                        WHERE status IN (%(completed)s, %(failed)s, %(cancelled)s)
                            AND completed_at < %(now)s - INTERVAL %(hours)s * INTERVAL '1 hour'
                        """,
                        {
                            "completed": JobStatus.COMPLETED,
                            "failed": JobStatus.FAILED,
                            "cancelled": JobStatus.CANCELLED,
                            "now": utc_now(),
                            "hours": hours,
                        },
                    )

                    deleted_count = cur.rowcount
                    if deleted_count > 0:
                        # Clear related caches after successful cleanup
                        await self._clear_overlay_job_caches()

                    return deleted_count

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    @cached_response(ttl_seconds=60, key_prefix="overlay_job")
    async def get_job_statistics(self) -> OverlayJobStatistics:
        """Get overlay job queue statistics for monitoring with 60s caching."""

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized CTE-based query with named parameters
                    query = OverlayJobQueryBuilder.build_statistics_query()
                    now = utc_now()
                    await cur.execute(query, {"now": now})

                    row = await cur.fetchone()
                    if row:
                        stats_dict = dict(row)
                        result = OverlayJobStatistics(
                            total_jobs_24h=int(stats_dict["total_jobs_24h"] or 0),
                            pending_jobs=int(stats_dict["pending_jobs"] or 0),
                            processing_jobs=int(stats_dict["processing_jobs"] or 0),
                            completed_jobs_24h=int(
                                stats_dict["completed_jobs_24h"] or 0
                            ),
                            failed_jobs_24h=int(stats_dict["failed_jobs_24h"] or 0),
                            cancelled_jobs_24h=int(
                                stats_dict["cancelled_jobs_24h"] or 0
                            ),
                            avg_processing_time_ms=int(
                                stats_dict["avg_processing_time_ms"] or 0
                            ),
                            last_updated=utc_now(),
                        )
                        return result

            return OverlayJobStatistics()

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to get overlay job statistics: {e}",
                operation="get_job_statistics",
            ) from e

    @cached_response(ttl_seconds=60, key_prefix="overlay_job")
    async def get_jobs_by_image_id(self, image_id: int) -> List[OverlayGenerationJob]:
        """Get all overlay generation jobs for a specific image with 60s caching."""

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayJobQueryBuilder.build_image_jobs_query()
                    await cur.execute(query, {"image_id": image_id})

                    rows = await cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    async def cancel_pending_jobs_for_image(self, image_id: int) -> int:
        """Cancel all pending overlay generation jobs for a specific image"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %(new_status)s, completed_at = %(completed_at)s
                        WHERE image_id = %(image_id)s AND status = %(current_status)s
                        """,
                        {
                            "new_status": JobStatus.CANCELLED,
                            "completed_at": utc_now(),
                            "image_id": image_id,
                            "current_status": JobStatus.PENDING,
                        },
                    )

                    cancelled_count = cur.rowcount
                    if cancelled_count > 0:
                        # Clear related caches after successful cancellation
                        await self._clear_overlay_job_caches(image_id=image_id)

                    return cancelled_count

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    async def recover_stuck_jobs(
        self,
        max_processing_age_minutes: int = 30,
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Recover overlay generation jobs stuck in 'processing' status by resetting them to 'pending'.

        Uses shared RecoveryUtilities for consistent recovery behavior across all job types.

        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing' status
                                        before being considered stuck (default: 30 minutes)
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with comprehensive recovery statistics
        """
        return await self.recovery_ops.recover_stuck_jobs_for_table(
            table_name="overlay_generation_jobs",
            max_processing_age_minutes=max_processing_age_minutes,
            job_type_name="overlay generation jobs",
            sse_broadcaster=sse_broadcaster,
        )


class SyncOverlayJobOperations:
    """
    Sync database operations for overlay generation jobs.

    Provides synchronous versions of overlay job database operations
    for use in worker processes and synchronous contexts.
    """

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db
        self.recovery_ops = SyncRecoveryOperations(db)

    def create_job(
        self, job_data: OverlayGenerationJobCreate
    ) -> Optional[OverlayGenerationJob]:
        """Create a new overlay generation job (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO overlay_generation_jobs (image_id, priority, status, job_type)
                        VALUES (%(image_id)s, %(priority)s, %(status)s, %(job_type)s)
                        RETURNING id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        """,
                        {
                            "image_id": job_data.image_id,
                            "priority": job_data.priority,
                            "status": job_data.status,
                            "job_type": job_data.job_type,
                        },
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    def get_pending_jobs(
        self, limit: int = DEFAULT_OVERLAY_JOB_BATCH_SIZE
    ) -> List[OverlayGenerationJob]:
        """Get pending overlay generation jobs (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use optimized query builder for consistency
                    query = OverlayJobQueryBuilder.build_pending_jobs_query()
                    cur.execute(query, {"status": JobStatus.PENDING, "limit": limit})

                    rows = cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    def mark_job_processing(self, job_id: int) -> bool:
        """Mark job as processing (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %(status)s, started_at = %(started_at)s
                        WHERE id = %(job_id)s
                        """,
                        {
                            "status": JobStatus.PROCESSING,
                            "started_at": utc_now(),
                            "job_id": job_id,
                        },
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    def mark_job_completed(self, job_id: int) -> bool:
        """Mark job as completed (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %(status)s, completed_at = %(completed_at)s
                        WHERE id = %(job_id)s
                        """,
                        {
                            "status": JobStatus.COMPLETED,
                            "completed_at": utc_now(),
                            "job_id": job_id,
                        },
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """Mark job as failed (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %(status)s, error_message = %(error_message)s, completed_at = %(completed_at)s
                        WHERE id = %(job_id)s
                        """,
                        {
                            "status": JobStatus.FAILED,
                            "error_message": error_message,
                            "completed_at": utc_now(),
                            "job_id": job_id,
                        },
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to perform operation: {e}", operation="overlay_operation"
            ) from e

    def recover_stuck_jobs(
        self,
        max_processing_age_minutes: int = 30,
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Recover overlay generation jobs stuck in 'processing' status by resetting them to 'pending' (sync version).

        Uses shared RecoveryUtilities for consistent recovery behavior across all job types.

        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing' status before being considered stuck (default: 30 minutes)

            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with comprehensive recovery statistics
        """
        return self.recovery_ops.recover_stuck_jobs_for_table(
            table_name="overlay_generation_jobs",
            max_processing_age_minutes=max_processing_age_minutes,
            job_type_name="overlay generation jobs",
            sse_broadcaster=sse_broadcaster,
        )

    def get_job_statistics(self) -> OverlayJobStatistics:
        """Get overlay job queue statistics for monitoring (sync version)."""

        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use optimized CTE-based query with named parameters
                    query = OverlayJobQueryBuilder.build_statistics_query()
                    now = utc_now()
                    cur.execute(query, {"now": now})

                    row = cur.fetchone()
                    if row:
                        stats_dict = dict(row)
                        result = OverlayJobStatistics(
                            total_jobs_24h=int(stats_dict["total_jobs_24h"] or 0),
                            pending_jobs=int(stats_dict["pending_jobs"] or 0),
                            processing_jobs=int(stats_dict["processing_jobs"] or 0),
                            completed_jobs_24h=int(
                                stats_dict["completed_jobs_24h"] or 0
                            ),
                            failed_jobs_24h=int(stats_dict["failed_jobs_24h"] or 0),
                            cancelled_jobs_24h=int(
                                stats_dict["cancelled_jobs_24h"] or 0
                            ),
                            avg_processing_time_ms=int(
                                stats_dict["avg_processing_time_ms"] or 0
                            ),
                            last_updated=utc_now(),
                        )
                        return result

            return OverlayJobStatistics()

        except (psycopg.Error, KeyError, ValueError) as e:
            raise OverlayOperationError(
                f"Failed to get overlay job statistics: {e}",
                operation="get_job_statistics",
            ) from e
