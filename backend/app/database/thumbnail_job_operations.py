# backend/app/database/thumbnail_job_operations.py
"""
Thumbnail Job Operations - Database layer for thumbnail generation job management.

Responsibilities:
- CRUD operations for thumbnail_generation_jobs table
- Priority-based job retrieval with batching
- Status updates and retry scheduling
- Cleanup of completed jobs
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from .core import AsyncDatabase, SyncDatabase
from ..models.shared_models import ThumbnailGenerationJob, ThumbnailGenerationJobCreate
from ..constants import (
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_STATUS_PROCESSING,
    THUMBNAIL_JOB_STATUS_COMPLETED,
    THUMBNAIL_JOB_STATUS_FAILED,
    THUMBNAIL_JOB_STATUS_CANCELLED,
    THUMBNAIL_JOB_PRIORITY_HIGH,
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_PRIORITY_LOW,
)

from ..utils.timezone_utils import utc_now


class ThumbnailJobOperations:
    """
    Async database operations for thumbnail generation jobs.

    Provides priority-based job queuing, status management, and cleanup operations
    following the established database operations pattern.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance."""
        self.db = db

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
                VALUES ($1, $2, $3, $4, NOW(), 0)
                RETURNING id, image_id, priority, status, job_type, created_at, 
                         started_at, completed_at, error_message, processing_time_ms, retry_count
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query.replace("$1", "%s")
                        .replace("$2", "%s")
                        .replace("$3", "%s")
                        .replace("$4", "%s"),
                        (
                            job_data.image_id,
                            job_data.priority,
                            job_data.status,
                            job_data.job_type,
                        ),
                    )
                    result = await cur.fetchone()

            if result:
                return ThumbnailGenerationJob(**dict(result))
            return None

        except Exception as e:
            logger.error(f"Error creating thumbnail job: {e}")
            return None

    async def get_pending_jobs(
        self, batch_size: int = 5
    ) -> List[ThumbnailGenerationJob]:
        """
        Get pending jobs ordered by priority and creation time.

        Args:
            batch_size: Maximum number of jobs to retrieve

        Returns:
            List of pending ThumbnailGenerationJob instances
        """
        try:
            # Priority order: high, medium, low
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

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (THUMBNAIL_JOB_STATUS_PENDING, batch_size))
                    results = await cur.fetchall()
                    return [ThumbnailGenerationJob(**dict(row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting pending jobs: {e}")
            return []

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
                SET status = %s, started_at = NOW()
                WHERE id = %s AND status = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_PROCESSING,
                            job_id,
                            THUMBNAIL_JOB_STATUS_PENDING,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking job {job_id} as started: {e}")
            return False

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
                SET status = %s, completed_at = NOW(), processing_time_ms = %s
                WHERE id = %s AND status = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_COMPLETED,
                            processing_time_ms,
                            job_id,
                            THUMBNAIL_JOB_STATUS_PROCESSING,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking job {job_id} as completed: {e}")
            return False

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
                SET status = %s, error_message = %s, retry_count = %s, completed_at = NOW()
                WHERE id = %s AND status = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_FAILED,
                            error_message,
                            retry_count,
                            job_id,
                            THUMBNAIL_JOB_STATUS_PROCESSING,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking job {job_id} as failed: {e}")
            return False

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
                    created_at = NOW() + INTERVAL %s MINUTE
                WHERE id = %s AND status = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_PENDING,
                            retry_count,
                            delay_minutes,
                            job_id,
                            THUMBNAIL_JOB_STATUS_FAILED,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error scheduling retry for job {job_id}: {e}")
            return False

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
                SET status = $1, completed_at = NOW()
                WHERE image_id = $2 AND status = $3
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query.replace("$1", "%s")
                        .replace("$2", "%s")
                        .replace("$3", "%s"),
                        (
                            THUMBNAIL_JOB_STATUS_CANCELLED,
                            image_id,
                            THUMBNAIL_JOB_STATUS_PENDING,
                        ),
                    )
                    return cur.rowcount

        except Exception as e:
            logger.error(f"Error cancelling jobs for image {image_id}: {e}")
            return 0

    async def cleanup_completed_jobs(self, older_than_hours: int = 24) -> int:
        """
        Clean up completed/failed jobs older than specified hours.

        Args:
            older_than_hours: Remove jobs completed more than this many hours ago

        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

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
                            THUMBNAIL_JOB_STATUS_COMPLETED,
                            THUMBNAIL_JOB_STATUS_FAILED,
                            THUMBNAIL_JOB_STATUS_CANCELLED,
                            cutoff_time,
                        ),
                    )
                    return cur.rowcount

        except Exception as e:
            logger.error(f"Error cleaning up completed jobs: {e}")
            return 0

    async def get_job_statistics(self) -> Dict[str, Any]:
        """
        Get job queue statistics for monitoring.

        Returns:
            Dictionary with job counts by status and other metrics
        """
        try:
            query = """
                SELECT 
                    status,
                    COUNT(*) as count,
                    AVG(processing_time_ms) as avg_processing_time_ms
                FROM thumbnail_generation_jobs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY status
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
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

                if status == THUMBNAIL_JOB_STATUS_PENDING:
                    stats["pending_jobs"] = count
                elif status == THUMBNAIL_JOB_STATUS_PROCESSING:
                    stats["processing_jobs"] = count
                elif status == THUMBNAIL_JOB_STATUS_COMPLETED:
                    stats["completed_jobs_24h"] = count
                    if row["avg_processing_time_ms"]:
                        stats["avg_processing_time_ms"] = int(
                            row["avg_processing_time_ms"]
                        )
                elif status == THUMBNAIL_JOB_STATUS_FAILED:
                    stats["failed_jobs_24h"] = count
                elif status == THUMBNAIL_JOB_STATUS_CANCELLED:
                    stats["cancelled_jobs_24h"] = count

            return stats

        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Error getting job statistics: {error_msg}")
            return {}

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
                WHERE id = $1
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query.replace("$1", "%s"), (job_id,))
                    result = await cur.fetchone()

            if result:
                return ThumbnailGenerationJob(**dict(result))
            return None

        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

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
                    completed_at = NOW(),
                    error_message = 'Cancelled by user request'
                WHERE status = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (status,))
                    return cur.rowcount or 0

        except Exception as e:
            logger.error(f"Error cancelling jobs with status {status}: {e}")
            return 0

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
                    completed_at = NOW(),
                    error_message = 'Cancelled by user request'
                WHERE status NOT IN ('completed', 'failed', 'cancelled')
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    return cur.rowcount or 0

        except Exception as e:
            logger.error(f"Error cancelling active jobs: {e}")
            return 0


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

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance."""
        self.db = db

    def create_job(
        self, job_data: ThumbnailGenerationJobCreate
    ) -> Optional[ThumbnailGenerationJob]:
        """Synchronous version of create_job."""
        try:
            query = """
                INSERT INTO thumbnail_generation_jobs 
                (image_id, priority, status, job_type, created_at, retry_count)
                VALUES (%s, %s, %s, %s, NOW(), 0)
                RETURNING id, image_id, priority, status, job_type, created_at, 
                         started_at, completed_at, error_message, processing_time_ms, retry_count
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            job_data.image_id,
                            job_data.priority,
                            job_data.status,
                            job_data.job_type,
                        ),
                    )
                    result = cur.fetchone()

            if result:
                return ThumbnailGenerationJob(**result)
            return None

        except Exception as e:
            logger.error(f"Error creating thumbnail job (sync): {e}")
            return None

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
                    cur.execute(query, (THUMBNAIL_JOB_STATUS_PENDING, batch_size))
                    results = cur.fetchall()
                    return [ThumbnailGenerationJob(**row) for row in results]

        except Exception as e:
            logger.error(f"Error getting pending jobs (sync): {e}")
            return []

    def mark_job_completed(
        self, job_id: int, processing_time_ms: Optional[int] = None
    ) -> bool:
        """Synchronous version of mark_job_completed."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, completed_at = NOW(), processing_time_ms = %s
                WHERE id = %s AND status = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_COMPLETED,
                            processing_time_ms,
                            job_id,
                            THUMBNAIL_JOB_STATUS_PROCESSING,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking job {job_id} as completed (sync): {e}")
            return False

    def mark_job_started(self, job_id: int) -> bool:
        """Synchronous version of mark_job_started."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, started_at = NOW()
                WHERE id = %s AND status = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_PROCESSING,
                            job_id,
                            THUMBNAIL_JOB_STATUS_PENDING,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking job {job_id} as started (sync): {e}")
            return False

    def mark_job_failed(
        self, job_id: int, error_message: str, retry_count: int = 0
    ) -> bool:
        """Synchronous version of mark_job_failed."""
        try:
            query = """
                UPDATE thumbnail_generation_jobs
                SET status = %s, error_message = %s, retry_count = %s, completed_at = NOW()
                WHERE id = %s AND status = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_FAILED,
                            error_message,
                            retry_count,
                            job_id,
                            THUMBNAIL_JOB_STATUS_PROCESSING,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error marking job {job_id} as failed (sync): {e}")
            return False

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
                            THUMBNAIL_JOB_STATUS_PENDING,
                            retry_count,
                            retry_time,
                            job_id,
                            THUMBNAIL_JOB_STATUS_FAILED,
                        ),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(f"Error scheduling retry for job {job_id}: {e}")
            return False

    def cleanup_completed_jobs(self, hours_old: int) -> int:
        """
        Clean up completed and failed jobs older than specified hours.

        Args:
            hours_old: Age threshold in hours

        Returns:
            Number of jobs cleaned up
        """
        try:
            query = """
                DELETE FROM thumbnail_generation_jobs
                WHERE status IN (%s, %s) 
                AND completed_at < NOW() - INTERVAL %s HOUR
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            THUMBNAIL_JOB_STATUS_COMPLETED,
                            THUMBNAIL_JOB_STATUS_FAILED,
                            hours_old,
                        ),
                    )
                    return cur.rowcount

        except Exception as e:
            logger.error(f"Error cleaning up completed jobs: {e}")
            return 0

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
                    completed_at = NOW(),
                    error_message = 'Cancelled by user request'
                WHERE status = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (status,))
                    return cur.rowcount or 0

        except Exception as e:
            logger.error(f"Error cancelling jobs with status {status}: {e}")
            return 0

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
                    completed_at = NOW(),
                    error_message = 'Cancelled by user request'
                WHERE status NOT IN ('completed', 'failed', 'cancelled')
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return cur.rowcount or 0

        except Exception as e:
            logger.error(f"Error cancelling active jobs: {e}")
            return 0

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
                SELECT id, camera_id, status, error_message, retry_count,
                       created_at, started_at, completed_at, processing_time_ms
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

        except Exception as e:
            logger.error(f"Error getting job by ID {job_id}: {e}")
            return None

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
                    MAX(created_at) as latest_created
                FROM thumbnail_generation_jobs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY status
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()

            # Initialize stats with defaults
            stats = {
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
                "total_active": 0,
            }

            # Process results
            for row in results:
                status = row[0]
                count = row[1]

                if status == THUMBNAIL_JOB_STATUS_PENDING:
                    stats["pending_jobs"] = count
                elif status == THUMBNAIL_JOB_STATUS_PROCESSING:
                    stats["processing_jobs"] = count
                elif status == THUMBNAIL_JOB_STATUS_COMPLETED:
                    stats["completed_jobs_24h"] = count
                elif status == THUMBNAIL_JOB_STATUS_FAILED:
                    stats["failed_jobs_24h"] = count

            stats["total_active"] = stats["pending_jobs"] + stats["processing_jobs"]

            return stats

        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Error getting job statistics: {error_msg}")
            return {
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
                "total_active": 0,
            }
