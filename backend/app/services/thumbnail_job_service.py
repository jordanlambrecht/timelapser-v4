# backend/app/services/thumbnail_job_service.py
"""
Thumbnail Job Service - Simple service layer for job queue operations.

This provides a clean service interface for thumbnail job management,
following the architecture pattern of service -> operations -> database.
"""

from typing import List, Optional
from loguru import logger

from ..database.thumbnail_job_operations import SyncThumbnailJobOperations
from ..models.shared_models import ThumbnailGenerationJob, ThumbnailGenerationJobCreate
from ..constants import (
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_TYPE_SINGLE,
    DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
)


class SyncThumbnailJobService:
    """
    Synchronous service for thumbnail job queue management.

    Provides a clean service layer interface for thumbnail generation job operations,
    following the established architecture pattern: Service → Operations → Database.

    Responsibilities:
    - Job creation and queuing with proper priority assignment
    - Job status management throughout the lifecycle
    - Retry scheduling with exponential backoff logic
    - Job queue statistics and monitoring
    - Cleanup of completed/failed jobs

    Integration Points:
    - Used by ThumbnailWorker for background job processing
    - Integrates with CaptureWorker for automatic job queuing
    - Coordinates with SettingsService for configuration management

    Thread Safety:
    - Designed for synchronous worker environments
    - Database operations are thread-safe through connection pooling
    - No shared state between instances
    """

    def __init__(self, sync_db, settings_service=None):
        """
        Initialize thumbnail job service with database and optional settings.

        Args:
            sync_db: Synchronous database connection for worker operations
            settings_service: Optional SettingsService for configuration access
                             Required for thumbnail generation settings validation

        Note:
            The sync_db is exposed as self.sync_db to allow worker classes
            direct access for performance-critical database operations.
        """
        self.sync_db = sync_db  # Expose for worker access
        self.thumbnail_job_ops = SyncThumbnailJobOperations(sync_db)
        self.settings_service = settings_service

    def queue_job(
        self, image_id: int, priority: str = THUMBNAIL_JOB_PRIORITY_MEDIUM
    ) -> Optional[ThumbnailGenerationJob]:
        """
        Queue a thumbnail generation job for an image.

        Args:
            image_id: ID of the image to generate thumbnails for
            priority: Job priority (high/medium/low)

        Returns:
            Created job or None if failed
        """
        try:
            job_create = ThumbnailGenerationJobCreate(
                image_id=image_id,
                priority=priority,
                status=THUMBNAIL_JOB_STATUS_PENDING,
                job_type=THUMBNAIL_JOB_TYPE_SINGLE,
            )

            job = self.thumbnail_job_ops.create_job(job_create)
            return job

        except Exception as e:
            logger.error(f"Failed to queue thumbnail job for image {image_id}: {e}")
            return None

    def get_pending_jobs(
        self, batch_size: int = DEFAULT_THUMBNAIL_JOB_BATCH_SIZE
    ) -> List[ThumbnailGenerationJob]:
        """Get pending jobs for processing."""
        try:
            return self.thumbnail_job_ops.get_pending_jobs(batch_size)
        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}")
            return []

    def mark_job_started(self, job_id: int) -> bool:
        """Mark a job as started."""
        try:
            return self.thumbnail_job_ops.mark_job_started(job_id)
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as started: {e}")
            return False

    def mark_job_completed(
        self, job_id: int, processing_time_ms: Optional[int] = None
    ) -> bool:
        """Mark a job as completed."""
        try:
            return self.thumbnail_job_ops.mark_job_completed(job_id, processing_time_ms)
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as completed: {e}")
            return False

    def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """Mark a job as failed."""
        try:
            return self.thumbnail_job_ops.mark_job_failed(job_id, error_message)
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")
            return False

    def schedule_retry(self, job_id: int, retry_count: int, delay_minutes: int) -> bool:
        """
        Schedule a failed job for retry with exponential backoff delay.

        Args:
            job_id: ID of the job to retry
            retry_count: Current retry attempt number (1-based)
            delay_minutes: Minutes to delay before making the job available again

        Returns:
            True if retry was successfully scheduled, False otherwise

        Note:
            This resets the job status to PENDING and updates the created_at
            timestamp to implement the delay. The retry_count is incremented
            to track total retry attempts.
        """
        try:
            return self.thumbnail_job_ops.schedule_retry(
                job_id, retry_count, delay_minutes
            )
        except Exception as e:
            logger.error(f"Failed to schedule retry for job {job_id}: {e}")
            return False

    def cleanup_completed_jobs(self, hours_old: int) -> int:
        """
        Remove completed and failed jobs older than the specified threshold.

        Args:
            hours_old: Age threshold in hours - jobs older than this are deleted

        Returns:
            Number of jobs cleaned up

        Note:
            Only jobs with status COMPLETED, FAILED, or CANCELLED are eligible
            for cleanup. PENDING and PROCESSING jobs are never removed to
            prevent data loss during active operations.
        """
        try:
            return self.thumbnail_job_ops.cleanup_completed_jobs(hours_old)
        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")
            return 0

    def get_job_statistics(self) -> dict:
        """
        Get comprehensive job queue statistics for monitoring and performance tuning.

        Returns:
            Dictionary containing:
            - pending_jobs: Current number of jobs waiting for processing
            - processing_jobs: Jobs currently being processed by workers
            - completed_jobs_24h: Successfully completed jobs in last 24 hours
            - failed_jobs_24h: Failed jobs in last 24 hours
            - total_active: Sum of pending and processing jobs

        Note:
            Statistics are calculated from jobs created within the last 24 hours
            to provide relevant recent activity metrics. Returns safe defaults
            (all zeros) if database query fails.
        """
        try:
            return self.thumbnail_job_ops.get_job_statistics()
        except Exception as e:
            logger.error(f"Failed to get job statistics: {e}")
            return {
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
            }

    async def cancel_pending_jobs(self) -> int:
        """
        Cancel all active thumbnail generation jobs (pending, processing, and any other non-final states).

        Returns:
            Number of jobs cancelled
        """
        try:
            logger.info("Cancelling all active thumbnail jobs")
            # Run sync method in executor for async compatibility
            import asyncio

            loop = asyncio.get_event_loop()
            
            # Cancel all jobs that are not in final states (completed, failed, cancelled)
            # This ensures we catch any jobs in pending, processing, or any other active states
            if hasattr(self.thumbnail_job_ops, 'cancel_active_jobs'):
                cancelled_count = await loop.run_in_executor(
                    None, self.thumbnail_job_ops.cancel_active_jobs
                )
            else:
                # Fallback to individual status cancellation
                pending_cancelled = await loop.run_in_executor(
                    None, self.thumbnail_job_ops.cancel_jobs_by_status, "pending"
                )
                processing_cancelled = await loop.run_in_executor(
                    None, self.thumbnail_job_ops.cancel_jobs_by_status, "processing"
                )
                cancelled_count = pending_cancelled + processing_cancelled
            
            logger.info(f"Cancelled {cancelled_count} active thumbnail jobs")
            return cancelled_count
        except Exception as e:
            logger.error(f"Failed to cancel jobs: {e}")
            return 0
