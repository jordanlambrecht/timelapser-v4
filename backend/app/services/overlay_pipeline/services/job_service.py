# backend/app/services/overlay_pipeline/services/job_service.py
"""
Overlay Job Service - Service layer for overlay generation job queue operations.

This provides a clean service interface for overlay job management,
following the architecture pattern of service -> operations -> database.
"""

from typing import List, Optional
from loguru import logger

from ....database.overlay_job_operations import SyncOverlayJobOperations, OverlayJobOperations
from ....models.overlay_model import OverlayGenerationJob, OverlayGenerationJobCreate, OverlayJobStatistics
from ....enums import (
    OverlayJobPriority,
    OverlayJobStatus,
    OverlayJobType,
)
from ....constants import (
    DEFAULT_OVERLAY_JOB_BATCH_SIZE,
    DEFAULT_OVERLAY_MAX_RETRIES,
    OVERLAY_JOB_RETRY_DELAYS,
)


class SyncOverlayJobService:
    """
    Synchronous service for overlay job queue management.

    Provides a clean service layer interface for overlay generation job operations,
    following the established architecture pattern: Service → Operations → Database.

    Responsibilities:
    - Job creation and queuing with proper priority assignment
    - Job status management throughout the lifecycle
    - Retry scheduling with exponential backoff logic
    - Job queue statistics and monitoring
    - Cleanup of completed/failed jobs

    Integration Points:
    - Used by OverlayWorker for background job processing
    - Integrates with CaptureWorker for automatic job queuing
    - Coordinates with SettingsService for configuration management

    Thread Safety:
    - Designed for synchronous worker environments
    - Database operations are thread-safe through connection pooling
    - No shared state between instances
    """

    def __init__(self, db: 'SyncDatabase', settings_service=None):
        """
        Initialize overlay job service with database and optional settings.

        Args:
            db: Synchronous database connection for worker operations
            settings_service: Optional SettingsService for configuration access
                             Required for overlay generation settings validation

        Note:
            The db is exposed as self.sync_db to allow worker classes
            direct access for performance-critical database operations.
        """
        self.sync_db = db  # Expose for worker access
        self.overlay_job_ops = SyncOverlayJobOperations(db)
        self.settings_service = settings_service

    def queue_job(
        self, image_id: int, priority: str = OverlayJobPriority.MEDIUM
    ) -> Optional[OverlayGenerationJob]:
        """
        Queue an overlay generation job for an image.

        Args:
            image_id: ID of the image to generate overlays for
            priority: Job priority (high/medium/low)

        Returns:
            Created job or None if failed
        """
        try:
            job_create = OverlayGenerationJobCreate(
                image_id=image_id,
                priority=priority,
                status=OverlayJobStatus.PENDING,
                job_type=OverlayJobType.SINGLE,
            )

            job = self.overlay_job_ops.create_job(job_create)
            return job

        except Exception as e:
            logger.error(f"Failed to queue overlay job for image {image_id}: {e}")
            return None

    def queue_priority_job(self, image_id: int) -> Optional[OverlayGenerationJob]:
        """Queue a high-priority overlay job (for manual preview requests)"""
        return self.queue_job(image_id, OverlayJobPriority.HIGH)

    def get_pending_jobs(
        self, batch_size: int = DEFAULT_OVERLAY_JOB_BATCH_SIZE
    ) -> List[OverlayGenerationJob]:
        """Get pending jobs for processing."""
        try:
            return self.overlay_job_ops.get_pending_jobs(batch_size)
        except Exception as e:
            logger.error(f"Failed to get pending overlay jobs: {e}")
            return []

    def mark_job_processing(self, job_id: int) -> bool:
        """Mark a job as processing."""
        try:
            return self.overlay_job_ops.mark_job_processing(job_id)
        except Exception as e:
            logger.error(f"Failed to mark overlay job {job_id} as processing: {e}")
            return False

    def mark_job_completed(self, job_id: int) -> bool:
        """Mark a job as completed."""
        try:
            return self.overlay_job_ops.mark_job_completed(job_id)
        except Exception as e:
            logger.error(f"Failed to mark overlay job {job_id} as completed: {e}")
            return False

    def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """Mark a job as failed."""
        try:
            return self.overlay_job_ops.mark_job_failed(job_id, error_message)
        except Exception as e:
            logger.error(f"Failed to mark overlay job {job_id} as failed: {e}")
            return False

    def schedule_retry(self, job_id: int) -> bool:
        """
        Schedule a failed job for retry with exponential backoff delay.

        Args:
            job_id: ID of the job to retry

        Returns:
            True if retry was successfully scheduled, False otherwise

        Note:
            This increments the retry count and resets the job to PENDING status.
            Jobs that exceed the maximum retry count will not be retried.
        """
        try:
            return self.overlay_job_ops.increment_retry_count(job_id)
        except Exception as e:
            logger.error(f"Failed to schedule retry for overlay job {job_id}: {e}")
            return False

    def get_jobs_for_retry(self) -> List[OverlayGenerationJob]:
        """Get failed jobs that are eligible for retry based on retry delays."""
        try:
            return self.overlay_job_ops.get_jobs_for_retry()
        except Exception as e:
            logger.error(f"Failed to get overlay jobs for retry: {e}")
            return []

    def cleanup_completed_jobs(self, hours_old: int = 24) -> int:
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
            return self.overlay_job_ops.cleanup_completed_jobs(hours_old)
        except Exception as e:
            logger.error(f"Failed to cleanup completed overlay jobs: {e}")
            return 0

    def get_job_statistics(self) -> OverlayJobStatistics:
        """
        Get comprehensive job queue statistics for monitoring.

        Returns:
            OverlayJobStatistics with current queue status and performance metrics
        """
        try:
            return self.overlay_job_ops.get_job_statistics()
        except Exception as e:
            logger.error(f"Failed to get overlay job statistics: {e}")
            return OverlayJobStatistics()

    def get_jobs_by_image_id(self, image_id: int) -> List[OverlayGenerationJob]:
        """Get all overlay generation jobs for a specific image."""
        try:
            return self.overlay_job_ops.get_jobs_by_image_id(image_id)
        except Exception as e:
            logger.error(f"Failed to get overlay jobs for image {image_id}: {e}")
            return []

    def cancel_pending_jobs_for_image(self, image_id: int) -> int:
        """Cancel all pending overlay generation jobs for a specific image."""
        try:
            return self.overlay_job_ops.cancel_pending_jobs_for_image(image_id)
        except Exception as e:
            logger.error(f"Failed to cancel pending overlay jobs for image {image_id}: {e}")
            return 0

    def get_service_health(self) -> dict:
        """
        Get comprehensive health status of overlay job service.
        
        Returns:
            Dict containing detailed health metrics for monitoring
        """
        try:
            logger.debug("🩺 Checking overlay job service health")
            
            # Check database connectivity
            db_healthy = False
            db_error = None
            try:
                # Test database connection by getting job statistics
                stats = self.overlay_job_ops.get_job_statistics()
                db_healthy = stats is not None
                logger.debug(f"🗄️ Database connectivity: {'✅ healthy' if db_healthy else '❌ unhealthy'}")
            except Exception as e:
                db_error = str(e)
                logger.error(f"🗄️ Database connectivity failed: {e}")
            
            # Get queue metrics if database is healthy
            queue_stats = None
            queue_healthy = False
            if db_healthy:
                try:
                    queue_stats = self.get_job_statistics()
                    # Consider queue healthy if we can get statistics
                    queue_healthy = queue_stats is not None
                    logger.debug(f"📋 Job queue: {'✅ healthy' if queue_healthy else '⚠️ degraded'}")
                except Exception as e:
                    logger.warning(f"📋 Job queue degraded: {e}")
            
            # Check settings service if provided
            settings_healthy = True
            settings_error = None
            if self.settings_service:
                try:
                    # Test basic settings access
                    test_setting = self.settings_service.get_setting("data_directory", None)
                    settings_healthy = test_setting is not None
                    logger.debug(f"⚙️ Settings service: {'✅ healthy' if settings_healthy else '❌ unhealthy'}")
                except Exception as e:
                    settings_healthy = False
                    settings_error = str(e)
                    logger.error(f"⚙️ Settings service failed: {e}")
            else:
                logger.debug("⚙️ Settings service: ⚪ not configured")
            
            # Determine overall health
            # Core requirement: database connectivity
            # Queue stats and settings are important but not critical
            overall_healthy = db_healthy
            if overall_healthy and queue_healthy and settings_healthy:
                overall_status = "healthy"
            elif overall_healthy:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"
            
            from ....utils.time_utils import utc_now
            
            health_data = {
                "service": "overlay_job_service",
                "status": overall_status,
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "error": db_error
                },
                "job_queue": {
                    "status": "healthy" if queue_healthy else "degraded",
                    "statistics": queue_stats.model_dump() if queue_stats else None
                },
                "settings_service": {
                    "status": "healthy" if settings_healthy else ("unhealthy" if self.settings_service else "not_configured"),
                    "error": settings_error
                },
                "timestamp": utc_now().isoformat()
            }
            
            logger.debug(f"🩺 Overlay job service health: {overall_status}")
            return health_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get overlay job service health: {e}")
            from ....utils.time_utils import utc_now
            return {
                "service": "overlay_job_service",
                "status": "unhealthy", 
                "error": str(e),
                "timestamp": utc_now().isoformat()
            }


class AsyncOverlayJobService:
    """
    Asynchronous service for overlay job queue management.

    Provides async versions of overlay job operations for use in FastAPI
    endpoints and other async contexts.
    """

    def __init__(self, db: 'AsyncDatabase', settings_service=None):
        """
        Initialize async overlay job service with database and optional settings.

        Args:
            db: Asynchronous database connection for API operations
            settings_service: Optional SettingsService for configuration access
        """
        self.async_db = db
        self.overlay_job_ops = OverlayJobOperations(db)
        self.settings_service = settings_service

    async def queue_job(
        self, image_id: int, priority: str = OverlayJobPriority.MEDIUM
    ) -> Optional[OverlayGenerationJob]:
        """Queue an overlay generation job for an image (async)."""
        try:
            job_create = OverlayGenerationJobCreate(
                image_id=image_id,
                priority=priority,
                status=OverlayJobStatus.PENDING,
                job_type=OverlayJobType.SINGLE,
            )

            job = await self.overlay_job_ops.create_job(job_create)
            return job

        except Exception as e:
            logger.error(f"Failed to queue overlay job for image {image_id}: {e}")
            return None

    async def queue_priority_job(self, image_id: int) -> Optional[OverlayGenerationJob]:
        """Queue a high-priority overlay job (async)"""
        return await self.queue_job(image_id, OverlayJobPriority.HIGH)

    async def get_pending_jobs(
        self, batch_size: int = DEFAULT_OVERLAY_JOB_BATCH_SIZE
    ) -> List[OverlayGenerationJob]:
        """Get pending jobs for processing (async)."""
        try:
            return await self.overlay_job_ops.get_pending_jobs(batch_size)
        except Exception as e:
            logger.error(f"Failed to get pending overlay jobs: {e}")
            return []

    async def get_job_statistics(self) -> OverlayJobStatistics:
        """Get comprehensive job queue statistics for monitoring (async)."""
        try:
            return await self.overlay_job_ops.get_job_statistics()
        except Exception as e:
            logger.error(f"Failed to get overlay job statistics: {e}")
            return OverlayJobStatistics()

    async def get_jobs_by_image_id(self, image_id: int) -> List[OverlayGenerationJob]:
        """Get all overlay generation jobs for a specific image (async)."""
        try:
            return await self.overlay_job_ops.get_jobs_by_image_id(image_id)
        except Exception as e:
            logger.error(f"Failed to get overlay jobs for image {image_id}: {e}")
            return []

    async def cancel_pending_jobs_for_image(self, image_id: int) -> int:
        """Cancel all pending overlay generation jobs for a specific image (async)."""
        try:
            return await self.overlay_job_ops.cancel_pending_jobs_for_image(image_id)
        except Exception as e:
            logger.error(f"Failed to cancel pending overlay jobs for image {image_id}: {e}")
            return 0