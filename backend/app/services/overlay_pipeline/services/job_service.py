# backend/app/services/overlay_pipeline/services/job_service.py
"""
Overlay Job Service - Service layer for overlay generation job queue operations.

This provides a clean service interface for overlay job management,
following the architecture pattern of service -> operations -> database.
"""

from typing import List, Optional

from ....constants import (
    DEFAULT_OVERLAY_JOB_BATCH_SIZE,
)
from ....database.core import AsyncDatabase, SyncDatabase
from ....database.overlay_job_operations import OverlayJobOperations
from ....enums import (
    LogEmoji,
    LoggerName,
    LogSource,
    OverlayJobPriority,
    OverlayJobStatus,
    OverlayJobType,
)
from ....models.health_model import HealthStatus
from ....models.overlay_model import (
    OverlayGenerationJob,
    OverlayGenerationJobCreate,
)
from ....services.logger import get_service_logger
from ....utils.time_utils import utc_timestamp

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


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

    def __init__(self, db: SyncDatabase, settings_service=None, overlay_job_ops=None):
        """
        Initialize overlay job service with injected dependencies.

        Args:
            db: Synchronous database connection for worker operations
            settings_service: Optional SettingsService for configuration access
            overlay_job_ops: Optional SyncOverlayJobOperations instance

        Note:
            The db is exposed as self.sync_db to allow worker classes
            direct access for performance-critical database operations.
        """
        self.sync_db = db  # Expose for worker access
        self.overlay_job_ops = overlay_job_ops or self._get_default_overlay_job_ops()
        self.settings_service = settings_service

    def _get_default_overlay_job_ops(self):
        """Fallback to create SyncOverlayJobOperations directly if not injected"""
        # Using injected SyncOverlayJobOperations singleton
        from ....dependencies.specialized import get_sync_overlay_job_operations

        return get_sync_overlay_job_operations()

    def queue_job(
        self, image_id: int, priority: OverlayJobPriority = OverlayJobPriority.MEDIUM
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
            logger.error(
                f"Failed to queue overlay job for image {image_id}", exception=e
            )
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
            logger.error("Failed to get pending overlay jobs", exception=e)
            return []

    def mark_job_processing(self, job_id: int) -> bool:
        """Mark a job as processing."""
        try:
            return self.overlay_job_ops.mark_job_processing(job_id)
        except Exception as e:
            logger.error(
                f"Failed to mark overlay job {job_id} as processing", exception=e
            )
            return False

    def mark_job_completed(self, job_id: int) -> bool:
        """Mark a job as completed."""
        try:
            return self.overlay_job_ops.mark_job_completed(job_id)
        except Exception as e:
            logger.error(
                f"Failed to mark overlay job {job_id} as completed", exception=e
            )
            return False

    def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """Mark a job as failed."""
        try:
            return self.overlay_job_ops.mark_job_failed(job_id, error_message)
        except Exception as e:
            logger.error(f"Failed to mark overlay job {job_id} as failed", exception=e)
            return False

    def schedule_retry(self, job_id: int, retry_count: int, delay_minutes: int) -> bool:
        """Schedule job retry with delay."""
        try:
            return self.overlay_job_ops.schedule_retry(
                job_id, retry_count, delay_minutes
            )
        except Exception as e:
            logger.error(f"Failed to schedule retry for job {job_id}", exception=e)
            return False

    def recover_stuck_jobs(self, max_processing_age_minutes: int = 30) -> dict:
        """
        Recover jobs stuck in processing status.

        Args:
            max_processing_age_minutes: Maximum time a job can be in processing status

        Returns:
            Recovery statistics dictionary
        """
        try:
            return self.overlay_job_ops.recover_stuck_jobs(max_processing_age_minutes)
        except Exception as e:
            logger.error("Failed to recover stuck overlay jobs", exception=e)
            return {"recovered_count": 0, "error": str(e)}

    def get_service_health(self) -> dict:
        """
        Get comprehensive health status of overlay job service.

        Returns:
            Dict containing detailed health metrics for monitoring
        """
        try:
            logger.debug("Checking overlay job service health")

            # Check database connectivity
            db_healthy = False
            db_error = None
            try:
                # Test database connection by getting pending jobs
                test_jobs = self.overlay_job_ops.get_pending_jobs(limit=1)
                db_healthy = isinstance(test_jobs, list)
                logger.debug(
                    f"Database connectivity: {'✅ healthy' if db_healthy else '❌ unhealthy'}",
                    emoji=LogEmoji.DATABASE,
                )
            except Exception as e:
                db_error = str(e)
                logger.error(
                    "Database connectivity failed", exception=e, emoji=LogEmoji.DATABASE
                )

            # Basic queue health check
            queue_healthy = db_healthy
            logger.debug(
                f"Job queue: {'✅ healthy' if queue_healthy else '⚠️ degraded'}",
                emoji=LogEmoji.QUEUE,
            )

            # Check settings service if provided
            settings_healthy = True
            settings_error = None
            if self.settings_service:
                try:
                    # Test basic settings access
                    test_setting = self.settings_service.get_setting(
                        "data_directory", None
                    )
                    settings_healthy = test_setting is not None
                    logger.debug(
                        f"Settings service: {'✅ healthy' if settings_healthy else '❌ unhealthy'}",
                        emoji=LogEmoji.SYSTEM,
                    )
                except Exception as e:
                    settings_healthy = False
                    settings_error = str(e)
                    logger.error(
                        "Settings service failed", exception=e, emoji=LogEmoji.SYSTEM
                    )
            else:
                logger.debug(
                    "Settings service: ⚪ not configured", emoji=LogEmoji.SYSTEM
                )

            # Determine overall health
            # Core requirement: database connectivity
            # Queue stats and settings are great but not critical
            overall_healthy = db_healthy
            if overall_healthy and queue_healthy and settings_healthy:
                overall_status = HealthStatus.HEALTHY
            elif overall_healthy:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.UNREACHABLE

            health_data = {
                "service": "overlay_job_service",
                "status": overall_status,
                "database": {
                    "status": (
                        HealthStatus.HEALTHY if db_healthy else HealthStatus.UNREACHABLE
                    ),
                    "error": db_error,
                },
                "job_queue": {
                    "status": (
                        HealthStatus.HEALTHY if queue_healthy else HealthStatus.DEGRADED
                    ),
                },
                "settings_service": {
                    "status": (
                        HealthStatus.HEALTHY
                        if settings_healthy
                        else (
                            HealthStatus.UNREACHABLE
                            if self.settings_service
                            else HealthStatus.UNKNOWN
                        )
                    ),
                    "error": settings_error,
                },
                "timestamp": utc_timestamp(),
            }

            logger.debug(
                f"Overlay job service health: {overall_status}", emoji=LogEmoji.HEALTH
            )
            return health_data

        except Exception as e:
            logger.error("Failed to get overlay job service health", exception=e)

            return {
                "service": "overlay_job_service",
                "status": HealthStatus.UNREACHABLE,
                "error": str(e),
                "timestamp": utc_timestamp(),
            }

    def cleanup_completed_jobs(self, hours_to_keep: int) -> int:
        """
        Clean up completed overlay jobs older than specified hours.

        Args:
            hours_to_keep: Number of hours of completed jobs to keep

        Returns:
            Number of jobs cleaned up
        """
        try:
            return self.overlay_job_ops.cleanup_completed_jobs(hours_to_keep)
        except Exception as e:
            logger.error("Failed to cleanup completed overlay jobs", exception=e)
            return 0

    def get_job_statistics(self):
        """Get comprehensive job queue statistics for monitoring (sync)."""
        try:
            return self.overlay_job_ops.get_job_statistics()
        except Exception as e:
            logger.error("Failed to get overlay job statistics", exception=e)
            return None


class AsyncOverlayJobService:
    """
    Asynchronous service for overlay job queue management.

    Provides async versions of overlay job operations for use in FastAPI
    endpoints and other async contexts.
    """

    def __init__(self, db: AsyncDatabase, settings_service=None, overlay_job_ops=None):
        """
        Initialize async overlay job service with injected dependencies.

        Args:
            db: Asynchronous database connection for API operations
            settings_service: Optional SettingsService for configuration access
            overlay_job_ops: Optional OverlayJobOperations instance
        """
        self.async_db = db
        self.overlay_job_ops = overlay_job_ops or self._get_default_overlay_job_ops()
        self.settings_service = settings_service

    def _get_default_overlay_job_ops(self):
        """Fallback to create OverlayJobOperations directly if not injected"""
        return OverlayJobOperations(self.async_db)

    async def queue_job(
        self, image_id: int, priority: OverlayJobPriority = OverlayJobPriority.MEDIUM
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
            logger.error(
                f"Failed to queue overlay job for image {image_id}", exception=e
            )
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
            logger.error("Failed to get pending overlay jobs", exception=e)
            return []

    async def get_job_statistics(self):
        """Get comprehensive job queue statistics for monitoring (async)."""
        try:
            return await self.overlay_job_ops.get_job_statistics()
        except Exception as e:
            logger.error("Failed to get overlay job statistics", exception=e)
            return None

    async def get_jobs_by_image_id(self, image_id: int) -> List[OverlayGenerationJob]:
        """Get all overlay generation jobs for a specific image (async)."""
        try:
            return await self.overlay_job_ops.get_jobs_by_image_id(image_id)
        except Exception as e:
            logger.error(
                f"Failed to get overlay jobs for image {image_id}", exception=e
            )
            return []

    async def cancel_pending_jobs_for_image(self, image_id: int) -> int:
        """Cancel all pending overlay generation jobs for a specific image (async)."""
        try:
            return await self.overlay_job_ops.cancel_pending_jobs_for_image(image_id)
        except Exception as e:
            logger.error(
                f"Failed to cancel pending overlay jobs for image {image_id}",
                exception=e,
            )
            return 0
