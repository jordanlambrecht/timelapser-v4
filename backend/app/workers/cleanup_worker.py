#!/usr/bin/env python3
# backend/app/workers/cleanup_worker.py
"""
Cleanup Worker for Timelapser v4.

Handles scheduled cleanup operations for maintaining database health and storage management.
Integrates with user settings for configurable retention policies.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

if TYPE_CHECKING:
    from ..database.core import AsyncDatabase

from ..constants import (
    DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
    DEFAULT_IMAGE_RETENTION_DAYS,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_OVERLAY_CLEANUP_HOURS,
    DEFAULT_STATISTICS_RETENTION_DAYS,
    DEFAULT_VIDEO_CLEANUP_DAYS,
    UNKNOWN_ERROR_MESSAGE,
)
from ..database import SyncDatabase

# from ..services.corruption_service import SyncCorruptionService  # Replaced by corruption_pipeline
from ..database.corruption_operations import SyncCorruptionOperations
from ..database.image_operations import SyncImageOperations
from ..database.log_operations import LogOperations, SyncLogOperations
from ..database.overlay_job_operations import SyncOverlayJobOperations
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..database.statistics_operations import SyncStatisticsOperations
from ..enums import LogEmoji, LoggerName, LogSource, WorkerType
from ..services.cleanup_workflow_service import CleanupWorkflowService
from ..services.logger import get_service_logger
from ..services.logger.services.cleanup_service import LogCleanupService
from ..services.settings_service import SyncSettingsService

# Defer video pipeline import to avoid circular dependency
# from ..services.video_pipeline import create_video_pipeline
from ..services.timelapse_service import SyncTimelapseService
from ..utils.temp_file_manager import cleanup_temporary_files
from ..utils.time_utils import utc_now
from .base_worker import BaseWorker
from .constants import (
    CLEANUP_INTERVAL_HOURS_DEFAULT,
    WEATHER_SSE_CLEANUP_HOURS,
)
from .exceptions import (
    CleanupServiceError,
    RetentionConfigurationError,
    ServiceUnavailableError,
    WorkerInitializationError,
)
from .mixins.settings_helper_mixin import SettingsHelperMixin
from .models.cleanup_responses import (
    CleanupResults,
    CleanupStats,
    CleanupWorkerStatus,
    LogCleanupResult,
    RetentionSettings,
)
from .utils.worker_status_builder import WorkerStatusBuilder

# from ..models.health_model import HealthStatus  # Unused


cleanup_logger = get_service_logger(LoggerName.CLEANUP_WORKER, LogSource.WORKER)


class CleanupWorker(SettingsHelperMixin, BaseWorker):
    """
    Worker responsible for scheduled cleanup operations.

    Follows standardized worker patterns with:
    - Dependency injection for all services
    - Proper error handling with structured logging
    - Configurable retention policies from settings
    - Comprehensive cleanup coverage for all data types

    Responsibilities:
    - Database log cleanup based on retention settings
    - Image file and record cleanup
    - Video generation job cleanup
    - Corruption detection log cleanup
    - SSE events cleanup
    - Statistics cleanup
    - Rate limiter data cleanup
    - Temporary file cleanup
    """

    def __init__(
        self,
        sync_db: SyncDatabase,
        async_db: "AsyncDatabase",
        settings_service: SyncSettingsService,
        cleanup_interval_hours: int = CLEANUP_INTERVAL_HOURS_DEFAULT,  # Run every 6 hours by default
    ):
        """
        Initialize cleanup worker.

        Args:
            sync_db: Synchronous database connection
            async_db: Asynchronous database connection
            settings_service: Settings service for configuration
            cleanup_interval_hours: How often to run cleanup (in hours)

        Raises:
            WorkerInitializationError: If required dependencies are missing
        """
        # Validate required dependencies
        if not sync_db:
            raise WorkerInitializationError("SyncDatabase is required")
        if not async_db:
            raise WorkerInitializationError("AsyncDatabase is required")
        if not settings_service:
            raise WorkerInitializationError("SyncSettingsService is required")
        if cleanup_interval_hours <= 0:
            raise WorkerInitializationError("cleanup_interval_hours must be positive")

        super().__init__("Cleanup")
        self.sync_db = sync_db
        self.async_db = async_db
        self.settings_service = settings_service
        self.cleanup_interval_hours = cleanup_interval_hours

        # Initialize service dependencies
        self.log_service: Optional[LogCleanupService] = None
        # self.corruption_service: Optional[SyncCorruptionService] = None  # Replaced by corruption_pipeline
        self.corruption_ops: Optional[SyncCorruptionOperations] = None
        self.video_pipeline = None
        self.timelapse_service: Optional[SyncTimelapseService] = None
        self.image_ops: Optional[SyncImageOperations] = None
        self.statistics_ops: Optional[SyncStatisticsOperations] = None
        self.overlay_job_ops: Optional[SyncOverlayJobOperations] = None

        # Track cleanup stats
        self.last_cleanup_time: Optional[datetime] = None
        self.cleanup_stats: CleanupStats = CleanupStats()

        # Initialize workflow service for Service Layer Boundary Pattern
        self.cleanup_service = CleanupWorkflowService()

    async def initialize(self) -> None:
        """Initialize worker dependencies."""
        try:
            # Initialize service layer dependencies
            # Initialize log operations
            if self.async_db:
                async_log_ops = LogOperations(self.async_db)
                sync_log_ops = SyncLogOperations(self.sync_db)
                self.log_service = LogCleanupService(
                    async_log_ops=async_log_ops, sync_log_ops=sync_log_ops
                )
            else:
                # Log service requires async_db - worker functionality limited
                cleanup_logger.warning(
                    "Log cleanup service unavailable - async_db not provided"
                )
                self.log_service = None
            # self.corruption_service = SyncCorruptionService(self.sync_db)  # Replaced by corruption_pipeline
            self.corruption_ops = SyncCorruptionOperations(self.sync_db)

            # Import here to avoid circular dependency
            from ..services.video_pipeline import create_video_pipeline

            self.video_pipeline = create_video_pipeline(self.sync_db)

            self.timelapse_service = SyncTimelapseService(self.sync_db)

            # Initialize database operations
            self.image_ops = SyncImageOperations(self.sync_db)
            self.statistics_ops = SyncStatisticsOperations(self.sync_db)
            self.overlay_job_ops = SyncOverlayJobOperations(self.sync_db)

            cleanup_logger.info(
                "Cleanup worker initialized successfully",
                emoji=LogEmoji.SUCCESS,
                store_in_db=False,
            )

        except Exception as e:
            cleanup_logger.error(
                f"Error cleaning temporary files: {e}", store_in_db=False
            )
            raise

    async def cleanup(self) -> None:
        """Cleanup worker resources."""
        cleanup_logger.info(
            "Cleanup worker stopped", emoji=LogEmoji.CLEANUP, store_in_db=False
        )

    # REMOVED: Autonomous run() method - CleanupWorker now follows CEO architecture
    # Cleanup operations are now scheduled and controlled by SchedulerWorker
    # via the execute_cleanup() method, eliminating autonomous timing decisions

    async def execute_cleanup(self) -> None:
        """
        Execute cleanup operations - can be called by scheduler or autonomous loop.

        This method contains the core cleanup logic and can be invoked either:
        1. By the autonomous run() loop at scheduled intervals
        2. By external scheduler for immediate cleanup operations
        """
        start_time = utc_now()
        cleanup_logger.info(
            "Starting cleanup cycle...", emoji=LogEmoji.CLEANUP, store_in_db=False
        )

        try:
            # Get retention settings from user configuration
            retention_settings_dict = await self._get_retention_settings()
            retention_settings = RetentionSettings.from_dict(retention_settings_dict)

            cleanup_results = CleanupResults()

            # 1. Clean up logs
            if retention_settings.log_retention_days > 0:
                cleanup_results.logs = await self._cleanup_logs(
                    retention_settings.log_retention_days
                )

            # 2. Clean up images
            if retention_settings.image_retention_days > 0:
                cleanup_results.images = await self._cleanup_images(
                    retention_settings.image_retention_days
                )

            # 3. Clean up video generation jobs
            if retention_settings.video_cleanup_days > 0:
                cleanup_results.video_jobs = await self._cleanup_video_jobs(
                    retention_settings.video_cleanup_days
                )

            # 4. Clean up completed timelapses
            if retention_settings.timelapse_retention_days > 0:
                cleanup_results.timelapses = await self._cleanup_timelapses(
                    retention_settings.timelapse_retention_days
                )

            # 5. Clean up corruption detection logs
            if retention_settings.corruption_logs_retention_days > 0:
                cleanup_results.corruption_logs = await self._cleanup_corruption_logs(
                    retention_settings.corruption_logs_retention_days
                )

            # 6. Clean up SSE events
            cleanup_results.sse_events = self._cleanup_sse_events(
                WEATHER_SSE_CLEANUP_HOURS
            )  # Keep 24 hours of SSE events

            # 7. Clean up statistics
            if retention_settings.statistics_retention_days > 0:
                cleanup_results.statistics = await self._cleanup_statistics(
                    retention_settings.statistics_retention_days
                )

            # 8. Clean up overlay generation jobs
            if retention_settings.overlay_cleanup_hours > 0:
                cleanup_results.overlay_jobs = await self._cleanup_overlay_jobs(
                    retention_settings.overlay_cleanup_hours
                )

            # 9. Clean up rate limiter data
            cleanup_results.rate_limiter = await self._cleanup_rate_limiter_data()

            # 10. Clean up temporary files (preview images, test captures)
            cleanup_results.temp_files = await self._cleanup_temporary_files()

            # Update stats
            self.last_cleanup_time = start_time
            duration_seconds = (utc_now() - start_time).total_seconds()

            self.cleanup_stats = CleanupStats(
                last_run=start_time.isoformat(),
                duration_seconds=duration_seconds,
                results=cleanup_results,
                total_items_cleaned=cleanup_results.total_cleaned,
            )

            # Log summary
            cleanup_logger.info(
                f"Cleanup cycle completed in {duration_seconds:.1f}s - "
                f"Total items cleaned: {cleanup_results.total_cleaned} "
                f"(logs: {cleanup_results.logs}, "
                f"images: {cleanup_results.images}, "
                f"video_jobs: {cleanup_results.video_jobs}, "
                f"timelapses: {cleanup_results.timelapses}, "
                f"corruption_logs: {cleanup_results.corruption_logs}, "
                f"overlay_jobs: {cleanup_results.overlay_jobs}, "
                f"sse_events: {cleanup_results.sse_events}, "
                f"statistics: {cleanup_results.statistics}, "
                f"rate_limiter: {cleanup_results.rate_limiter})",
                emoji=LogEmoji.SUCCESS,
            )

            # Note: SyncDatabase doesn't support broadcast_event (async only feature)
            # Frontend will need to poll for cleanup status or use async endpoints

        except RetentionConfigurationError as e:
            cleanup_logger.error(
                f"Retention configuration error during cleanup cycle: {e}"
            )
            raise
        except CleanupServiceError as e:
            cleanup_logger.error(f"Cleanup service error during cleanup cycle: {e}")
            raise
        except ServiceUnavailableError as e:
            cleanup_logger.error(
                f"Required service unavailable during cleanup cycle: {e}"
            )
            raise
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during cleanup cycle: {e}")
            raise

    async def _get_retention_settings(self) -> Dict[str, int]:
        """Get retention settings from user configuration using SettingsHelperMixin."""
        # Use SettingsHelperMixin for standardized retention settings handling
        return self.get_retention_settings(
            settings_service=self.settings_service,
            setting_keys_and_defaults={
                "log_retention_days": DEFAULT_LOG_RETENTION_DAYS,
                "image_retention_days": DEFAULT_IMAGE_RETENTION_DAYS,
                "video_cleanup_days": DEFAULT_VIDEO_CLEANUP_DAYS,
                "timelapse_retention_days": 90,
                "corruption_logs_retention_days": DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
                "statistics_retention_days": DEFAULT_STATISTICS_RETENTION_DAYS,
                "overlay_cleanup_hours": DEFAULT_OVERLAY_CLEANUP_HOURS,
            },
            logger=cleanup_logger,
        )

    async def _cleanup_logs(self, days_to_keep: int) -> int:
        """Clean up old log entries using the enhanced logger service."""
        try:
            if not self.log_service:
                cleanup_logger.warning("Log cleanup service not available")
                return 0

            # Use sync cleanup method for worker context
            result_dict = self.log_service.cleanup_old_logs_sync(days_to_keep)
            result = LogCleanupResult.from_dict(result_dict)

            if result.is_successful:
                return result.logs_deleted
            else:
                cleanup_logger.error(
                    f"Logger cleanup failed: {result.error or 'Unknown error'}"
                )
                return 0

        except CleanupServiceError as e:
            cleanup_logger.error(f"Cleanup service error during log cleanup: {e}")
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(
                f"Service unavailable during log cleanup: {e}", store_in_db=False
            )
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during log cleanup: {e}")
            return 0

    async def _cleanup_images(self, days_to_keep: int) -> int:
        """Clean up old image records."""
        try:
            if self.image_ops:
                return self.image_ops.cleanup_old_images(days_to_keep)
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(f"Cleanup service error during image cleanup: {e}")
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(f"Service unavailable during image cleanup: {e}")
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during image cleanup: {e}")
            return 0

    async def _cleanup_video_jobs(self, days_to_keep: int) -> int:
        """Clean up old video generation jobs."""
        try:
            if self.video_pipeline:
                return self.video_pipeline.job_service.cleanup_old_jobs(days_to_keep)
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(f"Cleanup service error during video job cleanup: {e}")
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(f"Service unavailable during video job cleanup: {e}")
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during video job cleanup: {e}")
            return 0

    async def _cleanup_timelapses(self, retention_days: int) -> int:
        """Clean up old completed timelapses."""
        try:
            if self.timelapse_service:
                return self.timelapse_service.cleanup_completed_timelapses(
                    retention_days
                )
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(f"Cleanup service error during timelapse cleanup: {e}")
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(f"Service unavailable during timelapse cleanup: {e}")
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during timelapse cleanup: {e}")
            return 0

    async def _cleanup_corruption_logs(self, days_to_keep: int) -> int:
        """Clean up old corruption detection logs."""
        try:
            if self.corruption_ops:
                return self.corruption_ops.cleanup_old_corruption_logs(days_to_keep)
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(
                f"Cleanup service error during corruption log cleanup: {e}"
            )
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(
                f"Service unavailable during corruption log cleanup: {e}"
            )
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during corruption log cleanup: {e}")
            return 0

    def _cleanup_sse_events(self, max_age_hours: int) -> int:
        """Clean up old SSE events."""
        try:
            # Use sync database for SSE events in worker
            sse_ops = SyncSSEEventsOperations(self.sync_db)
            return sse_ops.cleanup_old_events(max_age_hours)
        except CleanupServiceError as e:
            cleanup_logger.error(f"Cleanup service error during SSE event cleanup: {e}")
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(f"Service unavailable during SSE event cleanup: {e}")
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during SSE event cleanup: {e}")
            return 0

    async def _cleanup_statistics(self, days_to_keep: int) -> int:
        """Clean up old statistical data."""
        try:
            if self.statistics_ops:
                return self.statistics_ops.cleanup_old_statistics(days_to_keep)
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(
                f"Cleanup service error during statistics cleanup: {e}"
            )
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(f"Service unavailable during statistics cleanup: {e}")
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during statistics cleanup: {e}")
            return 0

    async def _cleanup_overlay_jobs(self, hours_to_keep: int) -> int:
        """Clean up old overlay generation jobs."""
        try:
            if self.overlay_job_ops:
                return self.overlay_job_ops.cleanup_completed_jobs(hours_to_keep)
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(
                f"Cleanup service error during overlay job cleanup: {e}"
            )
            return 0
        except ServiceUnavailableError as e:
            cleanup_logger.error(f"Service unavailable during overlay job cleanup: {e}")
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during overlay job cleanup: {e}")
            return 0

    async def _cleanup_rate_limiter_data(self) -> int:
        """Clean up old rate limiter tracking data."""
        try:
            # This would need to be implemented if we have a global rate limiter instance
            # For now, just return 0 as rate limiter cleanup happens automatically
            return 0
        except CleanupServiceError as e:
            cleanup_logger.error(
                f"Cleanup service error during rate limiter cleanup: {e}"
            )
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during rate limiter cleanup: {e}")
            return 0

    async def _cleanup_temporary_files(self) -> int:
        """Clean up old temporary files (preview images, test captures)."""
        try:
            # Clean up temporary files older than 2 hours
            cleaned_count = cleanup_temporary_files(max_age_hours=2)

            if cleaned_count > 0:
                cleanup_logger.info(
                    f"Cleaned up {cleaned_count} temporary files",
                    emoji=LogEmoji.SUCCESS,
                )
            else:
                cleanup_logger.debug("No temporary files to clean up")

            return cleaned_count
        except CleanupServiceError as e:
            cleanup_logger.error(
                f"Cleanup service error during temporary file cleanup: {e}"
            )
            return 0
        except Exception as e:
            cleanup_logger.error(f"Unexpected error during temporary file cleanup: {e}")
            return 0

    def get_status(self) -> Dict[str, Any]:
        """Get current cleanup worker status using explicit status pattern."""
        try:
            # Build explicit base status - no super() calls
            base_status = WorkerStatusBuilder.build_base_status(
                name=self.name,
                running=self.running,
                worker_type=WorkerType.CLEANUP_WORKER.value,
            )

            # Get service-specific status
            service_status = self.cleanup_service.get_worker_status(
                log_service=self.log_service,
                corruption_ops=self.corruption_ops,
                video_pipeline=self.video_pipeline,
                timelapse_service=self.timelapse_service,
                image_ops=self.image_ops,
                statistics_ops=self.statistics_ops,
                overlay_job_ops=self.overlay_job_ops,
                last_cleanup_time=self.last_cleanup_time,
                cleanup_interval_hours=self.cleanup_interval_hours,
                cleanup_stats=self.cleanup_stats,
            )

            # Convert to CleanupWorkerStatus model for validation and consistency
            merged_status = WorkerStatusBuilder.merge_service_status(
                base_status, service_status
            )
            cleanup_worker_status = CleanupWorkerStatus.from_dict(merged_status)

            # Return as dict for compatibility
            return cleanup_worker_status.__dict__

        except Exception as e:
            # Return standardized error status
            error_status = WorkerStatusBuilder.build_error_status(
                name=self.name,
                worker_type=WorkerType.CLEANUP_WORKER.value,
                error_type="unexpected",
                error_message=str(e) or UNKNOWN_ERROR_MESSAGE,
            )
            return error_status

    async def trigger_immediate_cleanup(
        self, cleanup_types: Optional[list] = None
    ) -> Union[Dict[str, Any], CleanupStats]:
        """
        Trigger an immediate cleanup cycle.

        Args:
            cleanup_types: Optional list of specific cleanup types to run

        Returns:
            Cleanup results
        """
        cleanup_logger.info(
            "Triggering immediate cleanup cycle...", emoji=LogEmoji.CLEANUP
        )

        if cleanup_types is None:
            # Run full cleanup cycle
            await self.execute_cleanup()
        else:
            # Run specific cleanup types
            retention_settings_dict = await self._get_retention_settings()
            retention_settings = RetentionSettings.from_dict(retention_settings_dict)
            cleanup_results = CleanupResults()

            for cleanup_type in cleanup_types:
                if cleanup_type == "logs" and retention_settings.log_retention_days > 0:
                    cleanup_results.logs = await self._cleanup_logs(
                        retention_settings.log_retention_days
                    )
                elif (
                    cleanup_type == "images"
                    and retention_settings.image_retention_days > 0
                ):
                    cleanup_results.images = await self._cleanup_images(
                        retention_settings.image_retention_days
                    )
                elif (
                    cleanup_type == "video_jobs"
                    and retention_settings.video_cleanup_days > 0
                ):
                    cleanup_results.video_jobs = await self._cleanup_video_jobs(
                        retention_settings.video_cleanup_days
                    )
                elif (
                    cleanup_type == "timelapses"
                    and retention_settings.timelapse_retention_days > 0
                ):
                    cleanup_results.timelapses = await self._cleanup_timelapses(
                        retention_settings.timelapse_retention_days
                    )
                elif (
                    cleanup_type == "corruption_logs"
                    and retention_settings.corruption_logs_retention_days > 0
                ):
                    cleanup_results.corruption_logs = (
                        await self._cleanup_corruption_logs(
                            retention_settings.corruption_logs_retention_days
                        )
                    )
                elif cleanup_type == "sse_events":
                    cleanup_results.sse_events = self._cleanup_sse_events(
                        WEATHER_SSE_CLEANUP_HOURS
                    )
                elif (
                    cleanup_type == "statistics"
                    and retention_settings.statistics_retention_days > 0
                ):
                    cleanup_results.statistics = await self._cleanup_statistics(
                        retention_settings.statistics_retention_days
                    )
                elif (
                    cleanup_type == "overlay_jobs"
                    and retention_settings.overlay_cleanup_hours > 0
                ):
                    cleanup_results.overlay_jobs = await self._cleanup_overlay_jobs(
                        retention_settings.overlay_cleanup_hours
                    )
                elif cleanup_type == "rate_limiter":
                    cleanup_results.rate_limiter = (
                        await self._cleanup_rate_limiter_data()
                    )

            # Update cleanup stats (typed results only)
            self.cleanup_stats.results = cleanup_results
            self.cleanup_stats.total_items_cleaned = cleanup_results.total_cleaned

        return self.cleanup_stats

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status for worker management system compatibility.

        This method provides simple binary health information separate
        from the detailed status reporting in get_status().
        """
        return WorkerStatusBuilder.build_simple_health_status(
            running=self.running,
            worker_type=WorkerType.CLEANUP_WORKER.value,
            additional_checks={
                "cleanup_service_available": self.cleanup_service is not None,
                "log_service_available": self.log_service is not None,
                "corruption_ops_available": self.corruption_ops is not None,
                "video_pipeline_available": self.video_pipeline is not None,
            },
        )
