#!/usr/bin/env python3
# backend/app/workers/cleanup_worker.py
"""
Cleanup Worker for Timelapser v4.

Handles scheduled cleanup operations for maintaining database health and storage management.
Integrates with user settings for configurable retention policies.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..database.core import AsyncDatabase

from .base_worker import BaseWorker
from ..database import SyncDatabase
from ..services.settings_service import SyncSettingsService
from ..services.log_service import SyncLogService

# from ..services.corruption_service import SyncCorruptionService  # Replaced by corruption_pipeline
from ..database.corruption_operations import SyncCorruptionOperations
from ..services.video_pipeline import create_video_pipeline
from ..services.timelapse_service import SyncTimelapseService
from ..database.image_operations import SyncImageOperations
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..database.statistics_operations import SyncStatisticsOperations
from ..constants import (
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_IMAGE_RETENTION_DAYS,
    DEFAULT_VIDEO_CLEANUP_DAYS,
    DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
    DEFAULT_STATISTICS_RETENTION_DAYS,
)
from ..utils.temp_file_manager import cleanup_temporary_files


class CleanupWorker(BaseWorker):
    """
    Worker responsible for scheduled cleanup operations.

    Responsibilities:
    - Database log cleanup based on retention settings
    - Image file and record cleanup
    - Video generation job cleanup
    - Corruption detection log cleanup
    - SSE events cleanup
    - Statistics cleanup
    - Rate limiter data cleanup
    """

    def __init__(
        self,
        sync_db: SyncDatabase,
        async_db: "AsyncDatabase",
        settings_service: SyncSettingsService,
        cleanup_interval_hours: int = 6,  # Run every 6 hours by default
    ):
        """
        Initialize cleanup worker.

        Args:
            sync_db: Synchronous database connection
            async_db: Asynchronous database connection
            settings_service: Settings service for configuration
            cleanup_interval_hours: How often to run cleanup (in hours)
        """
        super().__init__("Cleanup")
        self.sync_db = sync_db
        self.async_db = async_db
        self.settings_service = settings_service
        self.cleanup_interval_hours = cleanup_interval_hours

        # Initialize service dependencies
        self.log_service: Optional[SyncLogService] = None
        # self.corruption_service: Optional[SyncCorruptionService] = None  # Replaced by corruption_pipeline
        self.corruption_ops: Optional[SyncCorruptionOperations] = None
        self.video_pipeline = None
        self.timelapse_service: Optional[SyncTimelapseService] = None
        self.image_ops: Optional[SyncImageOperations] = None
        self.statistics_ops: Optional[SyncStatisticsOperations] = None

        # Track cleanup stats
        self.last_cleanup_time: Optional[datetime] = None
        self.cleanup_stats: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize worker dependencies."""
        try:
            # Initialize service layer dependencies
            self.log_service = SyncLogService(self.sync_db)
            # self.corruption_service = SyncCorruptionService(self.sync_db)  # Replaced by corruption_pipeline
            self.corruption_ops = SyncCorruptionOperations(self.sync_db)
            self.video_pipeline = create_video_pipeline(self.sync_db)
            self.timelapse_service = SyncTimelapseService(self.sync_db)

            # Initialize database operations
            self.image_ops = SyncImageOperations(self.sync_db)
            self.statistics_ops = SyncStatisticsOperations(self.sync_db)

            self.log_info("🧹 Cleanup worker initialized successfully")

        except Exception as e:
            self.log_error(f"Failed to initialize cleanup worker: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup worker resources."""
        self.log_info("🧹 Cleanup worker stopped")

    async def run(self) -> None:
        """Main worker loop - runs cleanup operations on schedule."""
        self.log_info(
            f"🧹 Cleanup worker started (interval: {self.cleanup_interval_hours}h)"
        )

        while self.running:
            try:
                # Run cleanup operations
                await self._run_cleanup_cycle()

                # Wait for next cycle
                await asyncio.sleep(
                    self.cleanup_interval_hours * 3600
                )  # Convert hours to seconds

            except asyncio.CancelledError:
                self.log_info("🧹 Cleanup worker cancelled")
                break
            except Exception as e:
                self.log_error(f"🧹 Error in cleanup worker cycle: {e}")
                # Wait a bit before retrying to avoid rapid error loops
                await asyncio.sleep(300)  # 5 minutes

    async def _run_cleanup_cycle(self) -> None:
        """Run a complete cleanup cycle for all data types."""
        start_time = datetime.now()
        self.log_info("🧹 Starting cleanup cycle...")

        # Get retention settings from user configuration
        retention_settings = await self._get_retention_settings()

        cleanup_results = {}

        try:
            # 1. Clean up logs
            if retention_settings.get("log_retention_days"):
                logs_deleted = await self._cleanup_logs(
                    retention_settings["log_retention_days"]
                )
                cleanup_results["logs"] = logs_deleted

            # 2. Clean up images
            if retention_settings.get("image_retention_days"):
                images_deleted = await self._cleanup_images(
                    retention_settings["image_retention_days"]
                )
                cleanup_results["images"] = images_deleted

            # 3. Clean up video generation jobs
            if retention_settings.get("video_cleanup_days"):
                video_jobs_deleted = await self._cleanup_video_jobs(
                    retention_settings["video_cleanup_days"]
                )
                cleanup_results["video_jobs"] = video_jobs_deleted

            # 4. Clean up completed timelapses
            if retention_settings.get("timelapse_retention_days"):
                timelapses_deleted = await self._cleanup_timelapses(
                    retention_settings["timelapse_retention_days"]
                )
                cleanup_results["timelapses"] = timelapses_deleted

            # 5. Clean up corruption detection logs
            if retention_settings.get("corruption_logs_retention_days"):
                corruption_logs_deleted = await self._cleanup_corruption_logs(
                    retention_settings["corruption_logs_retention_days"]
                )
                cleanup_results["corruption_logs"] = corruption_logs_deleted

            # 6. Clean up SSE events
            sse_events_deleted = self._cleanup_sse_events(
                24
            )  # Keep 24 hours of SSE events
            cleanup_results["sse_events"] = sse_events_deleted

            # 7. Clean up statistics
            if retention_settings.get("statistics_retention_days"):
                stats_deleted = await self._cleanup_statistics(
                    retention_settings["statistics_retention_days"]
                )
                cleanup_results["statistics"] = stats_deleted

            # 8. Clean up rate limiter data
            rate_limiter_cleaned = await self._cleanup_rate_limiter_data()
            cleanup_results["rate_limiter"] = rate_limiter_cleaned

            # 9. Clean up temporary files (preview images, test captures)
            temp_files_cleaned = await self._cleanup_temporary_files()
            cleanup_results["temp_files"] = temp_files_cleaned

            # Update stats
            self.last_cleanup_time = start_time
            self.cleanup_stats = {
                "last_run": start_time.isoformat(),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "results": cleanup_results,
                "total_items_cleaned": sum(cleanup_results.values()),
            }

            # Log summary
            total_cleaned = sum(cleanup_results.values())
            duration = (datetime.now() - start_time).total_seconds()

            self.log_info(
                f"🧹 Cleanup cycle completed in {duration:.1f}s - "
                f"Total items cleaned: {total_cleaned} "
                f"(logs: {cleanup_results.get('logs', 0)}, "
                f"images: {cleanup_results.get('images', 0)}, "
                f"video_jobs: {cleanup_results.get('video_jobs', 0)}, "
                f"timelapses: {cleanup_results.get('timelapses', 0)}, "
                f"corruption_logs: {cleanup_results.get('corruption_logs', 0)}, "
                f"sse_events: {cleanup_results.get('sse_events', 0)}, "
                f"statistics: {cleanup_results.get('statistics', 0)}, "
                f"rate_limiter: {cleanup_results.get('rate_limiter', 0)})"
            )

            # Note: SyncDatabase doesn't support broadcast_event (async only feature)
            # Frontend will need to poll for cleanup status or use async endpoints

        except Exception as e:
            self.log_error(f"🧹 Error during cleanup cycle: {e}")
            raise

    async def _get_retention_settings(self) -> Dict[str, int]:
        """Get retention settings from user configuration."""
        try:
            # Get settings with fallback to defaults
            def get_int_setting(key: str, default: int) -> int:
                """Helper to get integer setting with proper type conversion."""
                value = self.settings_service.get_setting(key, str(default))
                if value is None:
                    return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    self.log_warning(
                        f"Invalid {key} setting '{value}', using default: {default}"
                    )
                    return default

            return {
                "log_retention_days": get_int_setting(
                    "log_retention_days", DEFAULT_LOG_RETENTION_DAYS
                ),
                "image_retention_days": get_int_setting(
                    "image_retention_days", DEFAULT_IMAGE_RETENTION_DAYS
                ),
                "video_cleanup_days": get_int_setting(
                    "video_cleanup_days", DEFAULT_VIDEO_CLEANUP_DAYS
                ),
                "timelapse_retention_days": get_int_setting(
                    "timelapse_retention_days", 90
                ),
                "corruption_logs_retention_days": get_int_setting(
                    "corruption_logs_retention_days",
                    DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
                ),
                "statistics_retention_days": get_int_setting(
                    "statistics_retention_days", DEFAULT_STATISTICS_RETENTION_DAYS
                ),
            }
        except Exception as e:
            self.log_warning(f"Failed to get retention settings, using defaults: {e}")
            return {
                "log_retention_days": DEFAULT_LOG_RETENTION_DAYS,
                "image_retention_days": DEFAULT_IMAGE_RETENTION_DAYS,
                "video_cleanup_days": DEFAULT_VIDEO_CLEANUP_DAYS,
                "timelapse_retention_days": 90,
                "corruption_logs_retention_days": DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
                "statistics_retention_days": DEFAULT_STATISTICS_RETENTION_DAYS,
            }

    async def _cleanup_logs(self, days_to_keep: int) -> int:
        """Clean up old log entries."""
        try:
            if self.log_service:
                # Use cleanup_old_logs method which exists on SyncLogService
                return self.log_service.cleanup_old_logs(days_to_keep)
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup logs: {e}")
            return 0

    async def _cleanup_images(self, days_to_keep: int) -> int:
        """Clean up old image records."""
        try:
            if self.image_ops:
                return self.image_ops.cleanup_old_images(days_to_keep)
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup images: {e}")
            return 0

    async def _cleanup_video_jobs(self, days_to_keep: int) -> int:
        """Clean up old video generation jobs."""
        try:
            if self.video_pipeline:
                return self.video_pipeline.job_service.cleanup_old_jobs(days_to_keep)
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup video jobs: {e}")
            return 0

    async def _cleanup_timelapses(self, retention_days: int) -> int:
        """Clean up old completed timelapses."""
        try:
            if self.timelapse_service:
                return self.timelapse_service.cleanup_completed_timelapses(
                    retention_days
                )
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup timelapses: {e}")
            return 0

    async def _cleanup_corruption_logs(self, days_to_keep: int) -> int:
        """Clean up old corruption detection logs."""
        try:
            if self.corruption_ops:
                return self.corruption_ops.cleanup_old_corruption_logs(days_to_keep)
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup corruption logs: {e}")
            return 0

    def _cleanup_sse_events(self, max_age_hours: int) -> int:
        """Clean up old SSE events."""
        try:
            # Use sync database for SSE events in worker
            sse_ops = SyncSSEEventsOperations(self.sync_db)
            return sse_ops.cleanup_old_events(max_age_hours)
        except Exception as e:
            self.log_error(f"Failed to cleanup SSE events: {e}")
            return 0

    async def _cleanup_statistics(self, days_to_keep: int) -> int:
        """Clean up old statistical data."""
        try:
            if self.statistics_ops:
                return self.statistics_ops.cleanup_old_statistics(days_to_keep)
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup statistics: {e}")
            return 0

    async def _cleanup_rate_limiter_data(self) -> int:
        """Clean up old rate limiter tracking data."""
        try:
            # This would need to be implemented if we have a global rate limiter instance
            # For now, just return 0 as rate limiter cleanup happens automatically
            return 0
        except Exception as e:
            self.log_error(f"Failed to cleanup rate limiter data: {e}")
            return 0

    async def _cleanup_temporary_files(self) -> int:
        """Clean up old temporary files (preview images, test captures)."""
        try:
            # Clean up temporary files older than 2 hours
            cleaned_count = cleanup_temporary_files(max_age_hours=2)

            if cleaned_count > 0:
                self.log_info(f"🧹 Cleaned up {cleaned_count} temporary files")
            else:
                self.log_debug("🧹 No temporary files to clean up")

            return cleaned_count
        except Exception as e:
            self.log_error(f"Error cleaning up temporary files: {e}")
            return 0

    def get_status(self) -> Dict[str, Any]:
        """Get current cleanup worker status (STANDARDIZED METHOD NAME)."""
        # Get base status from BaseWorker
        base_status = super().get_status()

        # Add cleanup-specific status information
        base_status.update(
            {
                "worker_type": "CleanupWorker",
                "last_cleanup_time": (
                    self.last_cleanup_time.isoformat()
                    if self.last_cleanup_time
                    else None
                ),
                "cleanup_interval_hours": self.cleanup_interval_hours,
                "cleanup_stats": self.cleanup_stats,
                "total_items_cleaned": self.cleanup_stats.get("total_items_cleaned", 0),
                "last_duration_seconds": self.cleanup_stats.get("duration_seconds", 0),
                # Service health status
                "log_service_status": "healthy" if self.log_service else "unavailable",
                "corruption_ops_status": (
                    "healthy" if self.corruption_ops else "unavailable"
                ),
                "video_pipeline_status": (
                    "healthy" if self.video_pipeline else "unavailable"
                ),
                "timelapse_service_status": (
                    "healthy" if self.timelapse_service else "unavailable"
                ),
                "image_ops_status": "healthy" if self.image_ops else "unavailable",
                "statistics_ops_status": (
                    "healthy" if self.statistics_ops else "unavailable"
                ),
            }
        )

        return base_status

    def get_cleanup_stats(self) -> Dict[str, Any]:
        """Get current cleanup statistics (DEPRECATED - use get_status())."""
        # Keep for backward compatibility, but delegate to get_status()
        status = self.get_status()
        return {
            "last_cleanup_time": status["last_cleanup_time"],
            "cleanup_interval_hours": status["cleanup_interval_hours"],
            "running": status["running"],
            **status["cleanup_stats"],
        }

    async def trigger_immediate_cleanup(
        self, cleanup_types: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Trigger an immediate cleanup cycle.

        Args:
            cleanup_types: Optional list of specific cleanup types to run

        Returns:
            Cleanup results
        """
        self.log_info("🧹 Triggering immediate cleanup cycle...")

        if cleanup_types is None:
            # Run full cleanup cycle
            await self._run_cleanup_cycle()
        else:
            # Run specific cleanup types
            retention_settings = await self._get_retention_settings()
            cleanup_results = {}

            for cleanup_type in cleanup_types:
                if cleanup_type == "logs" and retention_settings.get(
                    "log_retention_days"
                ):
                    cleanup_results["logs"] = await self._cleanup_logs(
                        retention_settings["log_retention_days"]
                    )
                elif cleanup_type == "images" and retention_settings.get(
                    "image_retention_days"
                ):
                    cleanup_results["images"] = await self._cleanup_images(
                        retention_settings["image_retention_days"]
                    )
                elif cleanup_type == "video_jobs" and retention_settings.get(
                    "video_cleanup_days"
                ):
                    cleanup_results["video_jobs"] = await self._cleanup_video_jobs(
                        retention_settings["video_cleanup_days"]
                    )
                elif cleanup_type == "timelapses" and retention_settings.get(
                    "timelapse_retention_days"
                ):
                    cleanup_results["timelapses"] = await self._cleanup_timelapses(
                        retention_settings["timelapse_retention_days"]
                    )
                elif cleanup_type == "corruption_logs" and retention_settings.get(
                    "corruption_logs_retention_days"
                ):
                    cleanup_results["corruption_logs"] = (
                        await self._cleanup_corruption_logs(
                            retention_settings["corruption_logs_retention_days"]
                        )
                    )
                elif cleanup_type == "sse_events":
                    cleanup_results["sse_events"] = self._cleanup_sse_events(24)
                elif cleanup_type == "statistics" and retention_settings.get(
                    "statistics_retention_days"
                ):
                    cleanup_results["statistics"] = await self._cleanup_statistics(
                        retention_settings["statistics_retention_days"]
                    )
                elif cleanup_type == "rate_limiter":
                    cleanup_results["rate_limiter"] = (
                        await self._cleanup_rate_limiter_data()
                    )

            self.cleanup_stats["results"] = cleanup_results

        return self.cleanup_stats
