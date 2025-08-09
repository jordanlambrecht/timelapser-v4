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
from ..database.timelapse_operations import SyncTimelapseOperations, TimelapseOperations
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

    def __init__(self, db: AsyncDatabase, sync_db: SyncDatabase, scheduler_worker=None, 
                 thumbnail_ops=None, video_ops=None, overlay_ops=None, timelapse_ops=None) -> None:
        """
        Initialize recovery service with injected dependencies.

        Args:
            db: AsyncDatabase instance
            sync_db: SyncDatabase instance
            scheduler_worker: Optional scheduler worker for timelapse recovery
            thumbnail_ops: Optional ThumbnailJobOperations instance
            video_ops: Optional VideoOperations instance
            overlay_ops: Optional OverlayJobOperations instance
            timelapse_ops: Optional TimelapseOperations instance
        """
        self.db = db
        self.sync_db = sync_db
        # Use dependency injection to prevent database connection multiplication
        self.thumbnail_ops = thumbnail_ops or self._get_default_thumbnail_ops()
        self.video_ops = video_ops or self._get_default_video_ops()
        self.overlay_ops = overlay_ops or self._get_default_overlay_ops()
        self.timelapse_ops = timelapse_ops or self._get_default_timelapse_ops()
        self.scheduler_worker = scheduler_worker
        # Use sync LoggerService singleton (constructor is sync context)
        from ..dependencies.sync_services import get_logger_service
        self.log = get_logger_service()
    
    def _get_default_thumbnail_ops(self):
        """Fallback to get ThumbnailJobOperations singleton"""
        # This is a sync method in an async class, use direct instantiation
        from ..database.thumbnail_job_operations import ThumbnailJobOperations
        return ThumbnailJobOperations(self.db)
    
    def _get_default_video_ops(self):
        """Fallback to get VideoOperations singleton"""
        # This is a sync method in an async class, use direct instantiation
        from ..database.video_operations import VideoOperations
        return VideoOperations(self.db)
    
    def _get_default_overlay_ops(self):
        """Fallback to get OverlayJobOperations singleton"""
        # This is a sync method in an async class, use direct instantiation
        from ..database.overlay_job_operations import OverlayJobOperations
        return OverlayJobOperations(self.db)
    
    def _get_default_timelapse_ops(self):
        """Fallback to get TimelapseOperations singleton"""
        # This is a sync method in an async class, use direct instantiation
        from ..database.timelapse_operations import TimelapseOperations
        return TimelapseOperations(self.db)

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

            # 4. Recover timelapse capture jobs
            timelapse_results = {"timelapses_recovered": 0, "timelapses_found": 0}
            if self.scheduler_worker:
                if log_recovery_details:
                    logger.info(
                        "Recovering timelapse capture jobs...",
                        emoji=LogEmoji.CAMERA,
                    )
                try:
                    # Get running timelapses - need to use sync version since scheduler is sync
                    # Using injected SyncTimelapseOperations singleton
                    from ..dependencies.specialized import get_sync_timelapse_operations
                    sync_timelapse_ops = get_sync_timelapse_operations()
                    active_timelapses = sync_timelapse_ops.get_running_and_paused_timelapses()
                    timelapses_found = len(active_timelapses) if active_timelapses else 0
                    
                    if timelapses_found > 0:
                        # Delegate to scheduler worker for timelapse recovery
                        self.scheduler_worker.sync_running_timelapses()
                        timelapse_results = {
                            "timelapses_recovered": timelapses_found,
                            "timelapses_found": timelapses_found
                        }
                        logger.info(
                            f"Restored {timelapses_found} timelapse capture jobs",
                            emoji=LogEmoji.SUCCESS
                        )
                    else:
                        timelapse_results = {"timelapses_recovered": 0, "timelapses_found": 0}
                        
                except Exception as e:
                    logger.error(f"Error recovering timelapse capture jobs: {e}")
                    timelapse_results = {"timelapses_recovered": 0, "timelapses_found": 0, "error": str(e)}
            else:
                if log_recovery_details:
                    logger.debug("Scheduler worker not available - skipping timelapse recovery")
            
            recovery_results["timelapse_capture_jobs"] = timelapse_results

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

    def __init__(self, db: SyncDatabase, scheduler_worker=None, thumbnail_ops=None, 
                 video_ops=None, overlay_ops=None, timelapse_ops=None):
        """
        Initialize sync recovery service with injected dependencies.

        Args:
            db: SyncDatabase instance
            scheduler_worker: Optional scheduler worker for timelapse recovery
            thumbnail_ops: Optional SyncThumbnailJobOperations instance
            video_ops: Optional SyncVideoOperations instance
            overlay_ops: Optional SyncOverlayJobOperations instance
            timelapse_ops: Optional SyncTimelapseOperations instance
        """
        self.db = db
        self.thumbnail_ops = thumbnail_ops or self._get_default_thumbnail_ops()
        self.video_ops = video_ops or self._get_default_video_ops()
        self.overlay_ops = overlay_ops or self._get_default_overlay_ops()
        self.timelapse_ops = timelapse_ops or self._get_default_timelapse_ops()
        self.scheduler_worker = scheduler_worker
        # Use singleton StartupCleanupService to prevent database connection multiplication
        from ..dependencies.sync_services import get_startup_cleanup_service
        self.cleanup_service = get_startup_cleanup_service()
        
    def _get_default_thumbnail_ops(self):
        """Fallback to get SyncThumbnailJobOperations singleton"""
        from ..dependencies.specialized import get_sync_thumbnail_job_operations
        return get_sync_thumbnail_job_operations()
        
    def _get_default_video_ops(self):
        """Fallback to get SyncVideoOperations singleton"""
        from ..dependencies.specialized import get_sync_video_operations
        return get_sync_video_operations()
        
    def _get_default_overlay_ops(self):
        """Fallback to get SyncOverlayJobOperations singleton"""
        from ..dependencies.specialized import get_sync_overlay_job_operations
        return get_sync_overlay_job_operations()
        
    def _get_default_timelapse_ops(self):
        """Fallback to get SyncTimelapseOperations singleton"""
        from ..dependencies.specialized import get_sync_timelapse_operations
        return get_sync_timelapse_operations()

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

            # 4. Recover timelapse capture jobs
            timelapse_results = {"timelapses_recovered": 0, "timelapses_found": 0}
            if self.scheduler_worker:
                if log_recovery_details:
                    logger.info(
                        "Recovering timelapse capture jobs...",
                        emoji=LogEmoji.CAMERA,
                    )
                try:
                    active_timelapses = self.timelapse_ops.get_running_and_paused_timelapses()
                    timelapses_found = len(active_timelapses) if active_timelapses else 0
                    
                    if timelapses_found > 0:
                        # Delegate to scheduler worker for timelapse recovery
                        self.scheduler_worker.sync_running_timelapses()
                        timelapse_results = {
                            "timelapses_recovered": timelapses_found,
                            "timelapses_found": timelapses_found
                        }
                        logger.info(
                            f"Restored {timelapses_found} timelapse capture jobs",
                            emoji=LogEmoji.SUCCESS
                        )
                    else:
                        timelapse_results = {"timelapses_recovered": 0, "timelapses_found": 0}
                        
                except Exception as e:
                    logger.error(f"Error recovering timelapse capture jobs: {e}")
                    timelapse_results = {"timelapses_recovered": 0, "timelapses_found": 0, "error": str(e)}
            else:
                if log_recovery_details:
                    logger.debug("Scheduler worker not available - skipping timelapse recovery")
            
            recovery_results["timelapse_capture_jobs"] = timelapse_results

            # 5. Perform file cleanup
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
