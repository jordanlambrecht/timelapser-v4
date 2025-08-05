# backend/app/database/thumbnail_job_operations.py
"""
Thumbnail Job Operations - Database layer for thumbnail generation job management.

Responsibilities:
- CRUD operations for thumbnail_generation_jobs table
- Priority-based job retrieval with batching
- Status updates and retry scheduling
- Cleanup of completed jobs
"""


from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg

from ..enums import JobStatus
from ..models.shared_models import ThumbnailGenerationJob, ThumbnailGenerationJobCreate
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import ThumbnailOperationError
from .recovery_operations import RecoveryOperations, SyncRecoveryOperations


class ThumbnailJobQueryBuilder:
    """Centralized query builder for thumbnail job operations."""

    @staticmethod
    def get_base_select_fields():
        """Get standard fields for thumbnail job queries."""
        return """
            id, image_id, priority, status, job_type, created_at,
            started_at, completed_at, error_message, processing_time_ms, retry_count
        """

    @staticmethod
    def build_pending_jobs_query():
        """Build optimized query for pending jobs with priority ordering."""
        fields = ThumbnailJobQueryBuilder.get_base_select_fields()
        return f"""
            SELECT {fields}
            FROM thumbnail_generation_jobs
            WHERE status = %s
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END,
                created_at ASC
            LIMIT %s
        """

    @staticmethod
    def build_job_statistics_query():
        """Build optimized statistics query using CTEs for better performance."""
        return """
            WITH job_stats AS (
                SELECT
                    status,
                    COUNT(*) as count,
                    AVG(processing_time_ms) as avg_processing_time_ms
                FROM thumbnail_generation_jobs
                WHERE created_at > %s - INTERVAL '24 hours'
                GROUP BY status
            )
            SELECT
                status,
                count,
                avg_processing_time_ms
            FROM job_stats
        """

    @staticmethod
    def build_active_job_counts_query():
        """Build query for active job counts."""
        return """
            SELECT
                status,
                COUNT(*) as count
            FROM thumbnail_generation_jobs
            WHERE status IN (%s, %s)
            GROUP BY status
        """


class ThumbnailJobOperations:
    """
    Async database operations for thumbnail generation jobs.

    Provides priority-based job queuing, status management, and cleanup operations
    following the established database operations pattern.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db
        self.recovery_ops = RecoveryOperations(db)
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_thumbnail_job_caches(
        self,
        job_id: Optional[int] = None,
        image_id: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Clear caches related to thumbnail jobs using sophisticated cache system."""
        # Clear thumbnail job caches using advanced cache manager
        cache_patterns = [
            "thumbnail_job:get_pending_jobs",
            "thumbnail_job:get_job_statistics",
            "thumbnail_job:get_active_job_counts",
        ]

        if job_id:
            cache_patterns.extend(
                [
                    f"thumbnail_job:get_job_by_id:{job_id}",
                    f"thumbnail_job:metadata:{job_id}",
                ]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(job_id, updated_at)
                await self.cache_invalidation.invalidate_with_etag_validation(
                    f"thumbnail_job:metadata:{job_id}", etag
                )

        if image_id:
            cache_patterns.append(f"thumbnail_job:image:{image_id}")

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    async def create_job(
        self, job_data: ThumbnailGenerationJobCreate
    ) -> Optional[ThumbnailGenerationJob]:
        """
        Create a new thumbnail generation job.

        Args:
            job_data: Job creation data with image_id, priority, etc.

        Returns:
            ThumbnailGenerationJob instance if successful, None otherwise
        """
        try:
            query = """
                INSERT INTO thumbnail_generation_jobs
                (image_id, priority, status, job_type, created_at, retry_count)
                VALUES (%s, %s, %s, %s, %s, 0)
                RETURNING id, image_id, priority, status, job_type, created_at,
                        started_at, completed_at, error_message, processing_time_ms, retry_count
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            job_data.image_id,
                            job_data.priority,
                            job_data.status,
                            job_data.job_type,
                            current_time,
                        ),
                    )
                    result = await cur.fetchone()

            if result:
                job = ThumbnailGenerationJob(**dict(result))
                # Clear related caches after successful creation
                await self._clear_thumbnail_job_caches(
                    job.id, job.image_id, updated_at=utc_now()
                )
                return job
            return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to create thumbnail job: {e}", operation="create_job"
            ) from e

    @cached_response(ttl_seconds=15, key_prefix="thumbnail_job")
    async def get_pending_jobs(
        self, batch_size: int = 5
    ) -> List[ThumbnailGenerationJob]:
        """
        Get pending jobs ordered by priority and creation time using optimized query builder.

        Args:
            batch_size: Maximum number of jobs to retrieve

        Returns:
            List of pending ThumbnailGenerationJob instances
        """
        try:
            # Use optimized query builder for consistent query construction
            query = ThumbnailJobQueryBuilder.build_pending_jobs_query()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (JobStatus.PENDING, batch_size))
                    results = await cur.fetchall()
                    return [ThumbnailGenerationJob(**dict(row)) for row in results]

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to get pending jobs: {e}", operation="get_pending_jobs"
            ) from e

    async def mark_job_started(self, job_id: int) -> bool:
        """
        Mark a job as started (processing).

        Args:
            job_id: ID of the job to mark as started

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, started_at = %s
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            JobStatus.PROCESSING,
                            current_time,
                            job_id,
                            JobStatus.PENDING,
                        ),
                    )
                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful update
                        await self._clear_thumbnail_job_caches(job_id)
                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to mark job as started: {e}", operation="mark_job_started"
            ) from e

    async def mark_job_completed(
        self, job_id: int, processing_time_ms: Optional[int] = None
    ) -> bool:
        """
        Mark a job as completed successfully.

        Args:
            job_id: ID of the job to mark as completed
            processing_time_ms: Optional processing time in milliseconds

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, completed_at = %s, processing_time_ms = %s
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            JobStatus.COMPLETED,
                            current_time,
                            processing_time_ms,
                            job_id,
                            JobStatus.PROCESSING,
                        ),
                    )
                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful completion
                        await self._clear_thumbnail_job_caches(job_id)
                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to mark job as completed: {e}", operation="mark_job_completed"
            ) from e

    async def mark_job_failed(
        self, job_id: int, error_message: str, retry_count: int = 0
    ) -> bool:
        """
        Mark a job as failed with error details.

        Args:
            job_id: ID of the job to mark as failed
            error_message: Error description
            retry_count: Current retry count

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, error_message = %s, retry_count = %s, completed_at = %s
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            JobStatus.FAILED,
                            error_message,
                            retry_count,
                            current_time,
                            job_id,
                            JobStatus.PROCESSING,
                        ),
                    )
                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after failure
                        await self._clear_thumbnail_job_caches(job_id)
                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to mark job as failed: {e}", operation="mark_job_failed"
            ) from e

    async def schedule_retry(
        self, job_id: int, retry_count: int, delay_minutes: int = 1
    ) -> bool:
        """
        Schedule a job for retry after a delay.

        Args:
            job_id: ID of the job to retry
            retry_count: New retry count
            delay_minutes: Delay before retry (for exponential backoff)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Reset to pending status for retry, update retry count and clear error
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, retry_count = %s, error_message = NULL,
                    created_at = %s + %s * INTERVAL '1 minute'
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            JobStatus.PENDING,
                            retry_count,
                            current_time,
                            delay_minutes,
                            job_id,
                            JobStatus.FAILED,
                        ),
                    )
                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after retry scheduling
                        await self._clear_thumbnail_job_caches(job_id)
                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to schedule retry: {e}", operation="schedule_retry"
            ) from e

    async def cancel_jobs_for_image(self, image_id: int) -> int:
        """
        Cancel all pending jobs for a specific image.

        Args:
            image_id: ID of the image whose jobs should be cancelled

        Returns:
            Number of jobs cancelled
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, completed_at = %s
                WHERE image_id = %s AND status = %s
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            JobStatus.CANCELLED,
                            current_time,
                            image_id,
                            JobStatus.PENDING,
                        ),
                    )
                    cancelled_count = cur.rowcount
                    if cancelled_count > 0:
                        # Clear related caches after cancellation
                        await self._clear_thumbnail_job_caches(image_id=image_id)
                    return cancelled_count

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to cancel jobs for image: {e}",
                operation="cancel_jobs_for_image",
            ) from e

    async def cleanup_completed_jobs(self, older_than_hours: int = 24) -> int:
        """
        Clean up completed/failed jobs older than specified hours.

        Args:
            older_than_hours: Remove jobs completed more than this many hours ago

        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_time = utc_now() - timedelta(hours=older_than_hours)

            query = """
                DELETE FROM thumbnail_generation_jobs
                WHERE status IN (%s, %s, %s)
                AND completed_at < %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            JobStatus.COMPLETED,
                            JobStatus.FAILED,
                            JobStatus.CANCELLED,
                            cutoff_time,
                        ),
                    )
                    deleted_count = cur.rowcount
                    if deleted_count > 0:
                        # Clear related caches after cleanup
                        await self._clear_thumbnail_job_caches()
                    return deleted_count

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to cleanup completed jobs: {e}",
                operation="cleanup_completed_jobs",
            ) from e

    @cached_response(ttl_seconds=30, key_prefix="thumbnail_job")
    async def get_active_job_counts(self) -> Dict[str, int]:
        """
        Get counts of active jobs (pending/processing) without time constraints.

        Returns:
            Dictionary with pending_jobs and processing_jobs counts
        """
        try:
            # Use optimized query builder
            query = ThumbnailJobQueryBuilder.build_active_job_counts_query()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (JobStatus.PENDING, JobStatus.PROCESSING),
                    )
                    results = await cur.fetchall()

            counts = {
                "pending_jobs": 0,
                "processing_jobs": 0,
            }

            for row in results:
                status = row["status"]
                count = row["count"]

                if status == JobStatus.PENDING:
                    counts["pending_jobs"] = count
                elif status == JobStatus.PROCESSING:
                    counts["processing_jobs"] = count

            return counts

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to get job counts: {e}", operation="get_job_counts"
            ) from e

    @cached_response(ttl_seconds=60, key_prefix="thumbnail_job")
    async def get_job_statistics(self) -> Dict[str, Any]:
        """
        Get job queue statistics for monitoring.

        Returns:
            Dictionary with job counts by status and other metrics
        """
        try:
            # Use optimized CTE-based query for better performance
            query = ThumbnailJobQueryBuilder.build_job_statistics_query()
            current_time = utc_now()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (current_time,))
                    results = await cur.fetchall()

            stats = {
                "total_jobs_24h": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
                "cancelled_jobs_24h": 0,
                "avg_processing_time_ms": 0,
            }

            for row in results:
                status = row["status"]
                count = row["count"]
                stats["total_jobs_24h"] += count

                if status == JobStatus.PENDING:
                    stats["pending_jobs"] = count
                elif status == JobStatus.PROCESSING:
                    stats["processing_jobs"] = count
                elif status == JobStatus.COMPLETED:
                    stats["completed_jobs_24h"] = count
                    if row["avg_processing_time_ms"]:
                        stats["avg_processing_time_ms"] = int(
                            row["avg_processing_time_ms"]
                        )
                elif status == JobStatus.FAILED:
                    stats["failed_jobs_24h"] = count
                elif status == JobStatus.CANCELLED:
                    stats["cancelled_jobs_24h"] = count

            return stats

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to get job statistics: {e}", operation="get_job_statistics"
            ) from e

    async def get_job_by_id(self, job_id: int) -> Optional[ThumbnailGenerationJob]:
        """
        Get a specific job by ID.

        Args:
            job_id: ID of the job to retrieve

        Returns:
            ThumbnailGenerationJob instance if found, None otherwise
        """
        try:
            query = """
                SELECT id, image_id, priority, status, job_type, created_at,
                        started_at, completed_at, error_message, processing_time_ms, retry_count
                FROM thumbnail_generation_jobs
                WHERE id = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (job_id,))
                    result = await cur.fetchone()

            if result:
                return ThumbnailGenerationJob(**dict(result))
            return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    async def cancel_jobs_by_status(self, status: str) -> int:
        """
        Cancel all jobs with the specified status.

        Args:
            status: Status of jobs to cancel (e.g., "pending")

        Returns:
            Number of jobs cancelled
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = 'cancelled',
                    completed_at = %s,
                    error_message = 'Cancelled by user request'
                WHERE status = %s
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (current_time, status))
                    return cur.rowcount or 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    async def cancel_active_jobs(self) -> int:
        """
        Cancel all jobs that are not in final states (completed, failed, cancelled).
        This includes pending, processing, and any other non-final states.

        Returns:
            Number of jobs cancelled
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = 'cancelled',
                    completed_at = %s,
                    error_message = 'Cancelled by user request'
                WHERE status NOT IN ('completed', 'failed', 'cancelled')
            """

            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (current_time,))
                    return cur.rowcount or 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    async def recover_stuck_jobs(
        self,
        max_processing_age_minutes: int = 30,
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Recover jobs stuck in 'processing' status by resetting them to 'pending'.

        Uses shared RecoveryUtilities for consistent recovery behavior across all job types.

        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing' status
                                        before being considered stuck (default: 30 minutes)
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with comprehensive recovery statistics
        """
        return await self.recovery_ops.recover_stuck_jobs_for_table(
            table_name="thumbnail_generation_jobs",
            max_processing_age_minutes=max_processing_age_minutes,
            job_type_name="thumbnail jobs",
            sse_broadcaster=sse_broadcaster,
        )


class SyncThumbnailJobOperations:
    """
    Synchronous database operations for thumbnail generation job management.

    Provides thread-safe, synchronous database operations for the thumbnail job queue
    system. Designed specifically for background worker environments that require
    blocking database operations.

    Key Features:
    - Priority-based job queuing (high > medium > low)
    - Atomic status transitions with proper concurrency handling
    - Retry scheduling with timestamp-based delays
    - Efficient cleanup of completed jobs
    - Comprehensive statistics for monitoring

    Database Schema:
    - Operates on thumbnail_generation_jobs table
    - Supports CASCADE DELETE through image_id foreign key
    - Includes performance indexes on status, priority, and timestamps

    Thread Safety:
    - All operations use database-level locking and transactions
    - No shared state between method calls
    - Safe for concurrent access from multiple worker threads

    Usage Context:
    - Primary interface for ThumbnailWorker background processing
    - Used by SyncThumbnailJobService for business logic
    - Integrates with capture workflow for automatic job creation
    """

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db
        self.recovery_ops = SyncRecoveryOperations(db)

    def create_job(
        self, job_data: ThumbnailGenerationJobCreate
    ) -> Optional[ThumbnailGenerationJob]:
        """Synchronous version of create_job."""
        try:
            query = """
                INSERT INTO thumbnail_generation_jobs
                (image_id, priority, status, job_type, created_at, retry_count)
                VALUES (%s, %s, %s, %s, %s, 0)
                RETURNING id, image_id, priority, status, job_type, created_at,
                        started_at, completed_at, error_message, processing_time_ms, retry_count
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            job_data.image_id,
                            job_data.priority,
                            job_data.status,
                            job_data.job_type,
                            current_time,
                        ),
                    )
                    result = cur.fetchone()

            if result:
                return ThumbnailGenerationJob(**result)
            return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def get_pending_jobs(self, batch_size: int = 5) -> List[ThumbnailGenerationJob]:
        """Synchronous version of get_pending_jobs."""
        try:
            query = """
                SELECT id, image_id, priority, status, job_type, created_at,
                        started_at, completed_at, error_message, processing_time_ms, retry_count
                FROM thumbnail_generation_jobs
                WHERE status = %s
                ORDER BY
                    CASE priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    created_at ASC
                LIMIT %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (JobStatus.PENDING, batch_size))
                    results = cur.fetchall()
                    return [ThumbnailGenerationJob(**row) for row in results]

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def mark_job_completed(
        self, job_id: int, processing_time_ms: Optional[int] = None
    ) -> bool:
        """Synchronous version of mark_job_completed."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, completed_at = %s, processing_time_ms = %s
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            JobStatus.COMPLETED,
                            current_time,
                            processing_time_ms,
                            job_id,
                            JobStatus.PROCESSING,
                        ),
                    )
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def mark_job_started(self, job_id: int) -> bool:
        """Synchronous version of mark_job_started."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, started_at = %s
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            JobStatus.PROCESSING,
                            current_time,
                            job_id,
                            JobStatus.PENDING,
                        ),
                    )
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def mark_job_failed(
        self, job_id: int, error_message: str, retry_count: int = 0
    ) -> bool:
        """Synchronous version of mark_job_failed."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, error_message = %s, retry_count = %s, completed_at = %s
                WHERE id = %s AND status = %s
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            JobStatus.FAILED,
                            error_message,
                            retry_count,
                            current_time,
                            job_id,
                            JobStatus.PROCESSING,
                        ),
                    )
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def schedule_retry(self, job_id: int, retry_count: int, delay_minutes: int) -> bool:
        """
        Schedule a job for retry with exponential backoff.

        Args:
            job_id: ID of the job to retry
            retry_count: New retry count
            delay_minutes: Delay before retry

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate future timestamp for delayed retry

            retry_time = utc_now() + timedelta(minutes=delay_minutes)

            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, retry_count = %s, error_message = NULL,
                    created_at = %s
                WHERE id = %s AND status = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            JobStatus.PENDING,
                            retry_count,
                            retry_time,
                            job_id,
                            JobStatus.FAILED,
                        ),
                    )
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def cleanup_completed_jobs(self, hours_old: int) -> int:
        """
        Clean up completed and failed jobs older than specified hours.

        Args:
            hours_old: Age threshold in hours

        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_time = utc_now() - timedelta(hours=hours_old)
            query = """
                DELETE FROM thumbnail_generation_jobs
                WHERE status IN (%s, %s)
                AND completed_at < %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            JobStatus.COMPLETED,
                            JobStatus.FAILED,
                            cutoff_time,
                        ),
                    )
                    return cur.rowcount

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def cancel_jobs_by_status(self, status: str) -> int:
        """
        Cancel all jobs with the specified status (sync version).

        Args:
            status: Status of jobs to cancel (e.g., "pending")

        Returns:
            Number of jobs cancelled
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = 'cancelled',
                    completed_at = %s,
                    error_message = 'Cancelled by user request'
                WHERE status = %s
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (current_time, status))
                    return cur.rowcount or 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def get_recovered_jobs(self, max_age_hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get jobs that were recently recovered from stuck processing state.

        Args:
            max_age_hours: Maximum age of jobs to consider

        Returns:
            List of job dictionaries with recovery information
        """
        try:
            query = """
                SELECT id, image_id, error_message, created_at
                FROM thumbnail_generation_jobs
                WHERE status = %(status)s
                    AND error_message LIKE %(message_pattern)s
                    AND created_at > %(current_time)s - %(hours)s * INTERVAL '1 hour'
                ORDER BY created_at DESC
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        {
                            "status": JobStatus.PENDING,
                            "message_pattern": "%recovered from stuck processing state%",
                            "current_time": current_time,
                            "hours": max_age_hours,
                        },
                    )
                    rows = cur.fetchall()
                    return [dict(row) for row in rows] if rows else []

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def cancel_active_jobs(self) -> int:
        """
        Cancel all jobs that are not in final states (completed, failed, cancelled).
        This includes pending, processing, and any other non-final states.

        Returns:
            Number of jobs cancelled
        """
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = 'cancelled',
                    completed_at = %s,
                    error_message = 'Cancelled by user request'
                WHERE status NOT IN ('completed', 'failed', 'cancelled')
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (current_time,))
                    return cur.rowcount or 0

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def get_job_by_id(self, job_id: int) -> Optional[ThumbnailGenerationJob]:
        """
        Get a thumbnail generation job by its ID.

        Args:
            job_id: ID of the job to retrieve

        Returns:
            ThumbnailGenerationJob if found, None otherwise
        """
        try:
            query = """
                SELECT id, image_id, priority, status, job_type, created_at,
                        started_at, completed_at, error_message, processing_time_ms, retry_count
                FROM thumbnail_generation_jobs
                WHERE id = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (job_id,))
                    row = cur.fetchone()

                    if row:
                        return ThumbnailGenerationJob(**dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def get_job_statistics(self) -> dict:
        """
        Get comprehensive job queue statistics.

        Returns:
            Dictionary with job counts and status information
        """
        try:
            query = """
                SELECT
                    status,
                    COUNT(*) as count,
                    MAX(created_at) as latest_created,
                    MIN(CASE WHEN status = 'pending' THEN created_at ELSE NULL END) as oldest_pending,
                    AVG(CASE WHEN status = 'completed' THEN processing_time_ms ELSE NULL END) as avg_processing_time
                FROM thumbnail_generation_jobs
                WHERE created_at > %(current_time)s - INTERVAL '24 hours'
                GROUP BY status
            """

            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, {"current_time": current_time})
                    results = cur.fetchall()

            # Initialize stats with defaults
            stats = {
                "pending_count": 0,
                "processing_count": 0,
                "completed_today": 0,
                "failed_today": 0,
                "avg_processing_time": 0,
                "oldest_pending_age": 0,
            }

            oldest_pending_timestamp = None

            # Process results
            for row in results:
                status = row["status"]
                count = row["count"]

                if status == "pending":
                    stats["pending_count"] = count
                    if row["oldest_pending"] and (
                        oldest_pending_timestamp is None
                        or row["oldest_pending"] < oldest_pending_timestamp
                    ):
                        oldest_pending_timestamp = row["oldest_pending"]
                elif status == "processing":
                    stats["processing_count"] = count
                elif status == "completed":
                    stats["completed_today"] = count
                    if row["avg_processing_time"]:
                        stats["avg_processing_time"] = (
                            row["avg_processing_time"] / 1000 / 60
                        )  # ms to minutes
                elif status == "failed":
                    stats["failed_today"] = count

            if oldest_pending_timestamp:
                stats["oldest_pending_age"] = (
                    utc_now() - oldest_pending_timestamp
                ).total_seconds() / 60  # minutes

            return stats

        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to get queue statistics: {e}", operation="get_queue_statistics"
            ) from e

    def cancel_jobs_by_camera(self, camera_id: int) -> int:
        """Cancel pending thumbnail jobs associated with a specific camera."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs j
                SET status = 'cancelled', completed_at = %s
                FROM images i
                WHERE j.image_id = i.id AND i.camera_id = %s AND j.status = 'pending'
            """
            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (current_time, camera_id))
                    return cur.rowcount or 0
        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def cancel_jobs_by_timelapse(self, timelapse_id: int) -> int:
        """Cancel pending thumbnail jobs associated with a specific timelapse."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs j
                SET status = 'cancelled', completed_at = %s
                FROM images i
                WHERE j.image_id = i.id AND i.timelapse_id = %s AND j.status = 'pending'
            """
            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (current_time, timelapse_id))
                    return cur.rowcount or 0
        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def promote_old_jobs(self, age_threshold_minutes: int) -> int:
        """Promote old pending jobs to a higher priority."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET priority = CASE
                                WHEN priority = 'low' THEN 'medium'
                                WHEN priority = 'medium' THEN 'high'
                                ELSE 'high'
                            END
                WHERE status = 'pending'
                AND created_at < %(current_time)s - %(minutes)s * INTERVAL '1 minute'
                AND priority != 'high'
            """
            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        {
                            "current_time": current_time,
                            "minutes": age_threshold_minutes,
                        },
                    )
                    return cur.rowcount or 0
        except (psycopg.Error, KeyError, ValueError) as e:
            raise ThumbnailOperationError(
                f"Failed to perform operation: {e}", operation="thumbnail_operation"
            ) from e

    def recover_stuck_jobs(
        self,
        max_processing_age_minutes: int = 30,
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Recover jobs stuck in 'processing' status by resetting them to 'pending' (sync version).

        Uses shared RecoveryUtilities for consistent recovery behavior across all job types.

        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing' status
                                        before being considered stuck (default: 30 minutes)
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with comprehensive recovery statistics
        """
        return self.recovery_ops.recover_stuck_jobs_for_table(
            table_name="thumbnail_generation_jobs",
            max_processing_age_minutes=max_processing_age_minutes,
            job_type_name="thumbnail jobs",
            sse_broadcaster=sse_broadcaster,
        )
