# backend/app/database/overlay_job_operations.py
"""
Overlay Job Operations - Database layer for overlay generation job management.

Responsibilities:
- CRUD operations for overlay_generation_jobs table
- Priority-based job retrieval with batching
- Status updates and retry scheduling
- Cleanup of completed jobs
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from loguru import logger
import psycopg

from .core import AsyncDatabase, SyncDatabase
from ..models.overlay_model import (
    OverlayGenerationJob,
    OverlayGenerationJobCreate,
    OverlayJobStatistics,
)
from ..enums import JobStatus
from .recovery_operations import RecoveryOperations, SyncRecoveryOperations
from ..constants import (
    DEFAULT_OVERLAY_JOB_BATCH_SIZE,
    DEFAULT_OVERLAY_MAX_RETRIES,
    OVERLAY_JOB_RETRY_DELAYS,
)
from ..utils.time_utils import utc_now


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

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance."""
        self.db = db
        self.recovery_ops = RecoveryOperations(db)

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
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, image_id, priority, status, job_type, retry_count, 
                                 error_message, created_at, started_at, completed_at
                        """,
                        (
                            job_data.image_id,
                            job_data.priority,
                            job_data.status,
                            job_data.job_type,
                        ),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to create overlay generation job: {e}")
            return None

    async def get_job_by_id(self, job_id: int) -> Optional[OverlayGenerationJob]:
        """Get overlay generation job by ID"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        FROM overlay_generation_jobs
                        WHERE id = %s
                        """,
                        (job_id,),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to get overlay generation job {job_id}: {e}")
            return None

    async def get_pending_jobs(
        self, limit: int = DEFAULT_OVERLAY_JOB_BATCH_SIZE
    ) -> List[OverlayGenerationJob]:
        """
        Get pending overlay generation jobs ordered by priority and creation time.

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of pending jobs ordered by priority (high->medium->low) then by created_at
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        FROM overlay_generation_jobs
                        WHERE status = %s
                        ORDER BY
                            CASE priority
                                WHEN 'high' THEN 1
                                WHEN 'medium' THEN 2
                                WHEN 'low' THEN 3
                            END,
                            created_at ASC
                        LIMIT %s
                        """,
                        (JobStatus.PENDING, limit),
                    )

                    rows = await cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to get pending overlay generation jobs: {e}")
            return []

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
                    update_fields = ["status = %s"]
                    params: List[Union[str, datetime, int]] = [status]

                    if error_message is not None:
                        update_fields.append("error_message = %s")
                        params.append(error_message)

                    if started_at is not None:
                        update_fields.append("started_at = %s")
                        params.append(started_at)

                    if completed_at is not None:
                        update_fields.append("completed_at = %s")
                        params.append(completed_at)

                    params.append(job_id)

                    await cur.execute(
                        f"""
                        UPDATE overlay_generation_jobs
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        """,
                        params,
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Failed to update overlay generation job {job_id} status: {e}"
            )
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
                            status = %s,
                            error_message = NULL,
                            started_at = NULL,
                            completed_at = NULL
                        WHERE id = %s AND retry_count < %s
                        """,
                        (
                            JobStatus.PENDING,
                            job_id,
                            DEFAULT_OVERLAY_MAX_RETRIES,
                        ),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to increment retry count for job {job_id}: {e}")
            return False

    async def get_jobs_for_retry(self) -> List[OverlayGenerationJob]:
        """
        Get failed jobs that are eligible for retry based on retry delays.

        Returns:
            List of jobs eligible for retry
        """
        try:
            # Calculate retry thresholds based on retry count
            retry_conditions = []
            for i, delay_minutes in enumerate(OVERLAY_JOB_RETRY_DELAYS):
                retry_conditions.append(
                    f"(retry_count = {i} AND completed_at < NOW() - "
                    f"INTERVAL '{delay_minutes} minutes')"
                )

            retry_condition = " OR ".join(retry_conditions)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"""
                        SELECT id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        FROM overlay_generation_jobs
                        WHERE status = %s
                            AND retry_count < %s
                            AND ({retry_condition})
                        ORDER BY priority DESC, completed_at ASC
                        """,
                        (JobStatus.FAILED, DEFAULT_OVERLAY_MAX_RETRIES),
                    )

                    rows = await cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to get jobs for retry: {e}")
            return []

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
                        WHERE status IN (%s, %s, %s)
                            AND completed_at < NOW() - INTERVAL '%s hours'
                        """,
                        (
                            JobStatus.COMPLETED,
                            JobStatus.FAILED,
                            JobStatus.CANCELLED,
                            hours,
                        ),
                    )

                    return cur.rowcount

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to cleanup completed overlay jobs: {e}")
            return 0

    async def get_job_statistics(self) -> OverlayJobStatistics:
        """Get overlay job queue statistics for monitoring"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Get job counts by status
                    await cur.execute(
                        """
                        SELECT
                            COUNT(*) FILTER (
                                WHERE created_at > NOW() - INTERVAL '24 hours'
                            ) as total_jobs_24h,
                            COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
                            COUNT(*) FILTER (WHERE status = 'processing') as processing_jobs,
                            COUNT(*) FILTER (
                                WHERE status = 'completed' AND 
                                completed_at > NOW() - INTERVAL '24 hours'
                            ) as completed_jobs_24h,
                            COUNT(*) FILTER (
                                WHERE status = 'failed' AND 
                                completed_at > NOW() - INTERVAL '24 hours'
                            ) as failed_jobs_24h,
                            COUNT(*) FILTER (
                                WHERE status = 'cancelled' AND 
                                completed_at > NOW() - INTERVAL '24 hours'
                            ) as cancelled_jobs_24h,
                            COALESCE(
                                AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) 
                                FILTER (
                                    WHERE status = 'completed' AND 
                                    completed_at > NOW() - INTERVAL '24 hours'
                                ), 0
                            ) as avg_processing_time_ms
                        FROM overlay_generation_jobs
                        """
                    )

                    row = await cur.fetchone()
                    if row:
                        stats_dict = dict(row)
                        return OverlayJobStatistics(
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

            return OverlayJobStatistics()

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to get overlay job statistics: {e}")
            return OverlayJobStatistics()

    async def get_jobs_by_image_id(self, image_id: int) -> List[OverlayGenerationJob]:
        """Get all overlay generation jobs for a specific image"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        FROM overlay_generation_jobs
                        WHERE image_id = %s
                        ORDER BY created_at DESC
                        """,
                        (image_id,),
                    )

                    rows = await cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Failed to get overlay generation jobs for image {image_id}: {e}"
            )
            return []

    async def cancel_pending_jobs_for_image(self, image_id: int) -> int:
        """Cancel all pending overlay generation jobs for a specific image"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %s, completed_at = NOW()
                        WHERE image_id = %s AND status = %s
                        """,
                        (
                            JobStatus.CANCELLED,
                            image_id,
                            JobStatus.PENDING,
                        ),
                    )

                    return cur.rowcount

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to cancel pending jobs for image {image_id}: {e}")
            return 0

    async def recover_stuck_jobs(
        self, 
        max_processing_age_minutes: int = 30,
        sse_broadcaster: Optional[Any] = None
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
            sse_broadcaster=sse_broadcaster
        )


class SyncOverlayJobOperations:
    """
    Sync database operations for overlay generation jobs.

    Provides synchronous versions of overlay job database operations
    for use in worker processes and synchronous contexts.
    """

    def __init__(self, db: SyncDatabase):
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
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        """,
                        (
                            job_data.image_id,
                            job_data.priority,
                            job_data.status,
                            job_data.job_type,
                        ),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to create overlay generation job (sync): {e}")
            return None

    def get_pending_jobs(
        self, limit: int = DEFAULT_OVERLAY_JOB_BATCH_SIZE
    ) -> List[OverlayGenerationJob]:
        """Get pending overlay generation jobs (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, image_id, priority, status, job_type, retry_count,
                                error_message, created_at, started_at, completed_at
                        FROM overlay_generation_jobs
                        WHERE status = %s
                        ORDER BY
                            CASE priority
                                WHEN 'high' THEN 1
                                WHEN 'medium' THEN 2
                                WHEN 'low' THEN 3
                            END,
                            created_at ASC
                        LIMIT %s
                        """,
                        (JobStatus.PENDING, limit),
                    )

                    rows = cur.fetchall()
                    return [_row_to_overlay_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to get pending overlay generation jobs (sync): {e}")
            return []

    def mark_job_processing(self, job_id: int) -> bool:
        """Mark job as processing (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %s, started_at = NOW()
                        WHERE id = %s
                        """,
                        (JobStatus.PROCESSING, job_id),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Failed to mark overlay job {job_id} as processing (sync): {e}"
            )
            return False

    def mark_job_completed(self, job_id: int) -> bool:
        """Mark job as completed (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %s, completed_at = NOW()
                        WHERE id = %s
                        """,
                        (JobStatus.COMPLETED, job_id),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Failed to mark overlay job {job_id} as completed (sync): {e}"
            )
            return False

    def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """Mark job as failed (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE overlay_generation_jobs
                        SET status = %s, error_message = %s, completed_at = NOW()
                        WHERE id = %s
                        """,
                        (JobStatus.FAILED, error_message, job_id),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to mark overlay job {job_id} as failed (sync): {e}")
            return False

    def recover_stuck_jobs(
        self, 
        max_processing_age_minutes: int = 30,
        sse_broadcaster: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Recover overlay generation jobs stuck in 'processing' status by resetting them to 'pending' (sync version).
        
        Uses shared RecoveryUtilities for consistent recovery behavior across all job types.
        
        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing' status
                                       before being considered stuck (default: 30 minutes)
            sse_broadcaster: Optional SSE broadcaster for real-time updates
        
        Returns:
            Dictionary with comprehensive recovery statistics
        """
        return self.recovery_ops.recover_stuck_jobs_for_table(
            table_name="overlay_generation_jobs",
            max_processing_age_minutes=max_processing_age_minutes,
            job_type_name="overlay generation jobs",
            sse_broadcaster=sse_broadcaster
        )
