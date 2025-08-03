# backend/app/services/recovery_service.py
"""
Recovery Service - Coordinates startup recovery operations for all job types.

This service provides centralized recovery operations for system restarts,
handling stuck jobs across all job queues and providing comprehensive
recovery statistics.
"""

from typing import Any, Dict, Optional

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.overlay_job_operations import (
    OverlayJobOperations,
    SyncOverlayJobOperations,
)
from ..database.thumbnail_job_operations import (
    SyncThumbnailJobOperations,
    ThumbnailJobOperations,
)
from ..database.video_operations import SyncVideoOperations, VideoOperations
from ..enums import LogEmoji, LoggerName, LogSource
from ..services.logger.logger_service import LoggerService
from ..utils.startup_cleanup import StartupCleanupService
from ..utils.time_utils import utc_now, utc_timestamp
from .logger import get_service_logger

logger = get_service_logger(LoggerName.SCHEDULING_SERVICE, LogSource.SCHEDULER)


class RecoveryService:
    """
    Async recovery service for coordinating startup recovery operations.

    Handles recovery of stuck jobs across all job types:
    - Thumbnail generation jobs
    - Video generation jobs
    - Overlay generation jobs

    Provides comprehensive recovery statistics and logging.
    """

    def __init__(self, db: AsyncDatabase, sync_db: SyncDatabase) -> None:
        """
        Initialize recovery service with async database instance.

        Args:
            db: AsyncDatabase instance
            sync_db: SyncDatabase instance
        """
        self.db = db
        self.thumbnail_ops = ThumbnailJobOperations(db)
        self.video_ops = VideoOperations(db)
        self.overlay_ops = OverlayJobOperations(db)
        self.log = LoggerService(async_db=db, sync_db=sync_db)

    async def perform_startup_recovery(
        self,
        max_processing_age_minutes: int = 30,
        log_recovery_details: bool = True,
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive startup recovery for all job types.

        This method should be called on application startup to recover any jobs
        that were stuck in 'processing' status when the system went down.

        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing'
                                        before being considered stuck (default: 30 minutes)
            log_recovery_details: Whether to log detailed recovery information

        Returns:
            Dictionary with comprehensive recovery statistics
        """
        recovery_start_time = utc_now()
        logger.info(
            "Starting startup recovery for all job types...", emoji=LogEmoji.STARTUP
        )

        try:
            # Recovery results for each job type
            recovery_results = {}
            total_recovered = 0
            total_failed = 0

            # 1. Recover thumbnail jobs
            if log_recovery_details:
                logger.info(
                    "Recovering stuck thumbnail generation jobs...",
                    emoji=LogEmoji.CAMERA,
                )
            thumbnail_results = await self.thumbnail_ops.recover_stuck_jobs(
                max_processing_age_minutes, sse_broadcaster
            )
            recovery_results["thumbnail_jobs"] = thumbnail_results
            total_recovered += thumbnail_results.get("stuck_jobs_recovered", 0)
            total_failed += thumbnail_results.get("stuck_jobs_failed", 0)

            # 2. Recover video jobs
            if log_recovery_details:
                logger.info(
                    "Recovering stuck video generation jobs...", emoji=LogEmoji.VIDEO
                )
            video_results = await self.video_ops.recover_stuck_jobs(
                max_processing_age_minutes, sse_broadcaster
            )
            recovery_results["video_jobs"] = video_results
            total_recovered += video_results.get("stuck_jobs_recovered", 0)
            total_failed += video_results.get("stuck_jobs_failed", 0)

            # 3. Recover overlay jobs
            if log_recovery_details:
                logger.info(
                    "Recovering stuck overlay generation jobs...",
                    emoji=LogEmoji.OVERLAY,
                )
            overlay_results = await self.overlay_ops.recover_stuck_jobs(
                max_processing_age_minutes, sse_broadcaster
            )
            recovery_results["overlay_jobs"] = overlay_results
            total_recovered += overlay_results.get("stuck_jobs_recovered", 0)
            total_failed += overlay_results.get("stuck_jobs_failed", 0)

            # Calculate recovery duration
            recovery_duration = (utc_now() - recovery_start_time).total_seconds()

            # Compile comprehensive results
            recovery_summary = {
                "recovery_timestamp": recovery_start_time.isoformat(),
                "recovery_duration_seconds": recovery_duration,
                "max_processing_age_minutes": max_processing_age_minutes,
                "total_jobs_recovered": total_recovered,
                "total_jobs_failed_recovery": total_failed,
                "job_type_results": recovery_results,
                "recovery_successful": True,
            }

            # Log summary
            if total_recovered > 0:
                logger.info(
                    f"Startup recovery completed successfully in {recovery_duration:.2f}s - "
                    f"Recovered {total_recovered} stuck jobs across all types",
                    emoji=LogEmoji.SUCCESS,
                )
            else:
                logger.info(
                    f"Startup recovery completed in {recovery_duration:.2f}s - "
                    f"No stuck jobs found",
                    emoji=LogEmoji.SUCCESS,
                )

            if total_failed > 0:
                logger.warning(f"{total_failed} jobs failed to recover during startup")

            return recovery_summary

        except Exception as e:
            recovery_duration = (utc_now() - recovery_start_time).total_seconds()
            logger.error(
                f"Startup recovery failed after {recovery_duration:.2f}s: {e}",
                exception=e,
                extra_context={
                    "operation": "startup_recovery_sync",
                    "duration_seconds": recovery_duration,
                },
            )

            return {
                "recovery_timestamp": recovery_start_time.isoformat(),
                "recovery_duration_seconds": recovery_duration,
                "max_processing_age_minutes": max_processing_age_minutes,
                "total_jobs_recovered": 0,
                "total_jobs_failed_recovery": 0,
                "job_type_results": {},
                "recovery_successful": False,
                "error": str(e),
            }

    async def get_stuck_jobs_summary(
        self, max_processing_age_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Get a summary of stuck jobs without performing recovery.

        Useful for monitoring and health checks.

        Args:
            max_processing_age_minutes: Age threshold for considering jobs stuck

        Returns:
            Summary of stuck jobs across all types
        """
        try:
            summary = {
                "timestamp": utc_timestamp(),
                "max_processing_age_minutes": max_processing_age_minutes,
                "job_types": {},
            }

            # Note: Would need to add get_stuck_jobs_count methods to each operation class
            # For now, return basic structure
            summary["job_types"] = {
                "thumbnail_jobs": {
                    "stuck_count": 0,
                    "details": "Method not implemented",
                },
                "overlay_jobs": {"stuck_count": 0, "details": "Method not implemented"},
            }

            return summary

        except Exception as e:
            logger.error(
                f"Error getting stuck jobs summary: {e}",
                exception=e,
                extra_context={"operation": "get_stuck_jobs_summary_sync"},
            )
            return {"timestamp": utc_timestamp(), "error": str(e)}


class SyncRecoveryService:
    """
    Sync recovery service for coordinating startup recovery operations.

    Provides synchronous versions of recovery operations for use in
    sync contexts like worker initialization.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize sync recovery service with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.thumbnail_ops = SyncThumbnailJobOperations(db)
        self.video_ops = SyncVideoOperations(db)
        self.overlay_ops = SyncOverlayJobOperations(db)
        self.cleanup_service = StartupCleanupService(db)

    def perform_startup_recovery(
        self,
        max_processing_age_minutes: int = 30,
        log_recovery_details: bool = True,
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive startup recovery for all job types (sync version).

        This method should be called on application startup to recover any jobs
        that were stuck in 'processing' status when the system went down.

        Args:
            max_processing_age_minutes: Maximum time a job can be in 'processing'
                                        before being considered stuck (default: 30 minutes)
            log_recovery_details: Whether to log detailed recovery information

        Returns:
            Dictionary with comprehensive recovery statistics
        """
        recovery_start_time = utc_now()
        logger.info(
            "Starting startup recovery for all job types (sync)...",
            emoji=LogEmoji.STARTUP,
        )

        try:
            # Recovery results for each job type
            recovery_results = {}
            total_recovered = 0
            total_failed = 0

            # 1. Recover thumbnail jobs
            if log_recovery_details:
                logger.info(
                    "Recovering stuck thumbnail generation jobs...",
                    emoji=LogEmoji.THUMBNAIL,
                )
            thumbnail_results = self.thumbnail_ops.recover_stuck_jobs(
                max_processing_age_minutes, sse_broadcaster
            )
            recovery_results["thumbnail_jobs"] = thumbnail_results
            total_recovered += thumbnail_results.get("stuck_jobs_recovered", 0)
            total_failed += thumbnail_results.get("stuck_jobs_failed", 0)

            # 2. Recover video jobs
            if log_recovery_details:
                logger.info(
                    "Recovering stuck video generation jobs...", emoji=LogEmoji.VIDEO
                )
            video_results = self.video_ops.recover_stuck_jobs(
                max_processing_age_minutes, sse_broadcaster
            )
            recovery_results["video_jobs"] = video_results
            total_recovered += video_results.get("stuck_jobs_recovered", 0)
            total_failed += video_results.get("stuck_jobs_failed", 0)

            # 3. Recover overlay jobs
            if log_recovery_details:
                logger.info(
                    "Recovering stuck overlay generation jobs...",
                    emoji=LogEmoji.OVERLAY,
                )
            overlay_results = self.overlay_ops.recover_stuck_jobs(
                max_processing_age_minutes, sse_broadcaster
            )
            recovery_results["overlay_jobs"] = overlay_results
            total_recovered += overlay_results.get("stuck_jobs_recovered", 0)
            total_failed += overlay_results.get("stuck_jobs_failed", 0)

            # 4. Perform file cleanup
            if log_recovery_details:
                logger.info(
                    "Performing startup file cleanup...", emoji=LogEmoji.CLEANUP
                )
            cleanup_results = self.cleanup_service.perform_startup_cleanup(
                cleanup_thumbnails=True,
                cleanup_temp_files=True,
                cleanup_orphaned_files=False,  # Conservative by default
                max_age_hours=24,
            )
            recovery_results["file_cleanup"] = cleanup_results

            # Calculate recovery duration
            recovery_duration = (utc_now() - recovery_start_time).total_seconds()

            # Compile comprehensive results
            recovery_summary = {
                "recovery_timestamp": recovery_start_time.isoformat(),
                "recovery_duration_seconds": recovery_duration,
                "max_processing_age_minutes": max_processing_age_minutes,
                "total_jobs_recovered": total_recovered,
                "total_jobs_failed_recovery": total_failed,
                "job_type_results": recovery_results,
                "recovery_successful": True,
            }

            # Log summary
            if total_recovered > 0:
                logger.info(
                    f"Startup recovery completed successfully in {recovery_duration:.2f}s - "
                    f"Recovered {total_recovered} stuck jobs across all types",
                    emoji=LogEmoji.SUCCESS,
                )
            else:
                logger.info(
                    f"Startup recovery completed in {recovery_duration:.2f}s - "
                    f"No stuck jobs found",
                    emoji=LogEmoji.SUCCESS,
                )
            if total_failed > 0:
                logger.warning(f"{total_failed} jobs failed to recover during startup")

            return recovery_summary

        except Exception as e:
            recovery_duration = (utc_now() - recovery_start_time).total_seconds()
            logger.error(
                f"Startup recovery failed after {recovery_duration:.2f}s",
                extra_context={
                    "operation": "startup_recovery_sync",
                    "duration_seconds": recovery_duration,
                },
                exception=e,
            )

            return {
                "recovery_timestamp": recovery_start_time.isoformat(),
                "recovery_duration_seconds": recovery_duration,
                "max_processing_age_minutes": max_processing_age_minutes,
                "total_jobs_recovered": 0,
                "total_jobs_failed_recovery": 0,
                "job_type_results": {},
                "recovery_successful": False,
                "error": str(e),
            }

    def get_stuck_jobs_summary(
        self, max_processing_age_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Get a summary of stuck jobs without performing recovery (sync version).

        Useful for monitoring and health checks.

        Args:
            max_processing_age_minutes: Age threshold for considering jobs stuck

        Returns:
            Summary of stuck jobs across all types
        """
        try:
            summary = {
                "timestamp": utc_timestamp(),
                "max_processing_age_minutes": max_processing_age_minutes,
                "job_types": {},
            }

            # Note: Would need to add get_stuck_jobs_count methods to each operation class
            # For now, return basic structure
            summary["job_types"] = {
                "thumbnail_jobs": {
                    "stuck_count": 0,
                    "details": "Method not implemented",
                },
                "video_jobs": {"stuck_count": 0, "details": "Method not implemented"},
                "overlay_jobs": {"stuck_count": 0, "details": "Method not implemented"},
            }

            return summary

        except Exception as e:
            logger.error(
                "Error getting stuck jobs summary",
                extra_context={"operation": "get_stuck_jobs_summary_sync"},
                exception=e,
            )
            return {"timestamp": utc_timestamp(), "error": str(e)}
