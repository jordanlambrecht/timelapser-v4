"""
Log Cleanup Service for the Logger Service.

This service handles database cleanup, maintenance operations, and log analytics
for the centralized logging system. It integrates with worker cleanup systems
and provides statistics for monitoring.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

from ....database.log_operations import LogOperations, SyncLogOperations
from ....constants import LOG_CLEANUP_BATCH_SIZE, LOG_CLEANUP_INTERVAL_HOURS
from ....utils.time_utils import utc_now
from ..utils.settings_cache import LoggerSettingsCache


class LogCleanupService:
    """
    Service for cleaning up old logs and providing log analytics.

    Features:
    - Automatic cleanup of old log entries
    - Log statistics and analytics
    - Integration with worker cleanup systems
    - Health monitoring and maintenance
    - Configurable retention policies
    """

    def __init__(
        self,
        async_log_ops: LogOperations,
        sync_log_ops: SyncLogOperations,
        settings_cache: Optional[LoggerSettingsCache] = None,
        default_retention_days: int = 30,
        cleanup_batch_size: int = LOG_CLEANUP_BATCH_SIZE,
    ):
        """
        Initialize the log cleanup service.

        Args:
            async_log_ops: Async log operations instance
            sync_log_ops: Sync log operations instance
            settings_cache: Settings cache for dynamic retention configuration
            default_retention_days: Default number of days to retain logs (fallback)
            cleanup_batch_size: Number of logs to delete per batch
        """
        self.async_log_ops = async_log_ops
        self.sync_log_ops = sync_log_ops
        self.settings_cache = settings_cache
        self.default_retention_days = default_retention_days
        self.cleanup_batch_size = cleanup_batch_size

        # Health and statistics tracking
        self._healthy = True
        self._last_cleanup_time = None
        self._total_logs_cleaned = 0
        self._last_cleanup_error = None

    async def _get_retention_days_async(self, override_days: Optional[int] = None) -> int:
        """
        Get retention days from user settings or override.
        
        Args:
            override_days: Explicit override (takes precedence)
            
        Returns:
            Number of days to retain logs
        """
        if override_days is not None:
            return override_days
            
        if self.settings_cache:
            try:
                return await self.settings_cache.get_setting_async("db_log_retention_days")
            except Exception:
                pass
        
        return self.default_retention_days

    def _get_retention_days_sync(self, override_days: Optional[int] = None) -> int:
        """
        Get retention days from user settings or override (sync version).
        
        Args:
            override_days: Explicit override (takes precedence)
            
        Returns:
            Number of days to retain logs
        """
        if override_days is not None:
            return override_days
            
        if self.settings_cache:
            try:
                return self.settings_cache.get_setting_sync("db_log_retention_days")
            except Exception:
                pass
        
        return self.default_retention_days

    async def cleanup_old_logs(
        self,
        days_to_keep: Optional[int] = None,
        source_filter: Optional[str] = None,
        level_filter: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Clean up old log entries from the database.

        Args:
            days_to_keep: Number of days of logs to keep (defaults to default_retention_days)
            source_filter: Optional source filter (currently not supported by underlying method)
            level_filter: Optional level filter (currently not supported by underlying method)
            dry_run: If True, returns count without actually deleting (not supported yet)

        Returns:
            Dictionary containing cleanup results and statistics
        """
        try:
            # Get retention days from user settings or override
            days_to_keep = await self._get_retention_days_async(days_to_keep)

            # Use the existing delete_old_logs method
            deleted_count = await self.async_log_ops.delete_old_logs(days_to_keep)

            # Update statistics
            self._total_logs_cleaned += deleted_count
            self._last_cleanup_time = utc_now()

            return {
                "success": True,
                "logs_deleted": deleted_count,
                "days_to_keep": days_to_keep,
                "cleanup_time": self._last_cleanup_time.isoformat(),
                "note": "Source and level filters not yet supported by underlying database operations",
            }

        except Exception as e:
            self._last_cleanup_error = str(e)
            self._healthy = False

            return {"success": False, "error": str(e), "days_to_keep": days_to_keep}

    async def _count_logs_for_cleanup(
        self,
        cutoff_date: datetime,
        source_filter: Optional[str] = None,
        level_filter: Optional[str] = None,
    ) -> int:
        """
        Count the number of logs that would be deleted.

        NOTE: This is a placeholder implementation since the underlying
        database operations don't support counting with filters.

        Args:
            cutoff_date: Date before which logs should be deleted
            source_filter: Optional source filter (not implemented)
            level_filter: Optional level filter (not implemented)

        Returns:
            Number of logs that would be deleted (always 0 for now)
        """
        # TODO: Implement count_logs_before_date in LogOperations for proper functionality
        return 0

    async def _delete_log_batch(
        self,
        cutoff_date: datetime,
        source_filter: Optional[str] = None,
        level_filter: Optional[str] = None,
    ) -> int:
        """
        Delete a batch of old logs.

        NOTE: This is a placeholder implementation since the underlying
        database operations don't support batch deletion with filters.

        Args:
            cutoff_date: Date before which logs should be deleted
            source_filter: Optional source filter (not implemented)
            level_filter: Optional level filter (not implemented)

        Returns:
            Number of logs deleted in this batch (always 0 for now)
        """
        # TODO: Implement delete_logs_batch in LogOperations for proper functionality
        return 0

    async def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get comprehensive log statistics for monitoring and analysis.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary containing log statistics
        """
        start_time = None
        end_time = None
        try:
            # Calculate time range using timezone-aware timestamps
            end_time = utc_now()
            start_time = end_time - timedelta(hours=hours)

            # Get basic statistics
            stats = {
                "analysis_period": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "hours": hours,
                },
                "total_logs": await self._get_total_log_count(start_time, end_time),
                "logs_by_level": await self._get_logs_by_level(start_time, end_time),
                "logs_by_source": await self._get_logs_by_source(start_time, end_time),
                "logs_by_logger": await self._get_logs_by_logger(start_time, end_time),
                "error_summary": await self._get_error_summary(start_time, end_time),
                "cleanup_statistics": {
                    "last_cleanup_time": (
                        self._last_cleanup_time.isoformat()
                        if self._last_cleanup_time
                        else None
                    ),
                    "total_logs_cleaned": self._total_logs_cleaned,
                    "cleanup_service_healthy": self._healthy,
                    "last_cleanup_error": self._last_cleanup_error,
                },
            }

            return stats

        except Exception as e:
            return {
                "error": str(e),
                "analysis_period": {
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None,
                    "hours": hours,
                },
            }

    async def _get_total_log_count(
        self, start_time: datetime, end_time: datetime
    ) -> int:
        """Get total log count for time period.

        NOTE: Placeholder implementation - LogOperations doesn't have count_logs_in_range.
        """
        # TODO: Implement count_logs_in_range in LogOperations for proper functionality
        return 0

    async def _get_logs_by_level(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, int]:
        """Get log count breakdown by level.

        NOTE: Placeholder implementation - LogOperations doesn't have get_log_level_breakdown.
        """
        # TODO: Implement get_log_level_breakdown in LogOperations for proper functionality
        return {}

    async def _get_logs_by_source(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, int]:
        """Get log count breakdown by source.

        NOTE: Placeholder implementation - LogOperations doesn't have get_log_source_breakdown.
        """
        # TODO: Implement get_log_source_breakdown in LogOperations for proper functionality
        return {}

    async def _get_logs_by_logger(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, int]:
        """Get log count breakdown by logger name.

        NOTE: Placeholder implementation - LogOperations doesn't have get_log_logger_breakdown.
        """
        # TODO: Implement get_log_logger_breakdown in LogOperations for proper functionality
        return {}

    async def _get_error_summary(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get summary of errors and warnings.

        NOTE: Placeholder implementation - LogOperations doesn't have get_error_summary.
        """
        # TODO: Implement get_error_summary in LogOperations for proper functionality
        return {}

    def cleanup_old_logs_sync(
        self,
        days_to_keep: Optional[int] = None,
        source_filter: Optional[str] = None,
        level_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous version of cleanup_old_logs for worker contexts.

        Args:
            days_to_keep: Number of days of logs to keep
            source_filter: Optional source filter
            level_filter: Optional level filter

        Returns:
            Dictionary containing cleanup results
        """
        try:
            # Get retention days from user settings or override
            days_to_keep = self._get_retention_days_sync(days_to_keep)

            # Calculate cutoff date using timezone-aware timestamp
            cutoff_date = utc_now() - timedelta(days=days_to_keep)

            # Use sync operations for cleanup
            deleted_count = self.sync_log_ops.cleanup_old_logs(days_to_keep)

            # Update statistics
            self._total_logs_cleaned += deleted_count
            self._last_cleanup_time = utc_now()

            return {
                "success": True,
                "logs_deleted": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
                "days_to_keep": days_to_keep,
                "cleanup_time": self._last_cleanup_time.isoformat(),
            }

        except Exception as e:
            self._last_cleanup_error = str(e)
            self._healthy = False

            return {"success": False, "error": str(e), "days_to_keep": days_to_keep}

    async def schedule_periodic_cleanup(
        self, interval_hours: int = 24, days_to_keep: Optional[int] = None
    ) -> None:
        """
        Schedule periodic cleanup of old logs.

        Args:
            interval_hours: Hours between cleanup runs
            days_to_keep: Number of days of logs to keep
        """
        try:
            while True:
                # Wait for interval
                await asyncio.sleep(interval_hours * 3600)

                # Perform cleanup
                result = await self.cleanup_old_logs(days_to_keep)

                if result.get("success"):
                    print(
                        f"Periodic log cleanup completed: {result['logs_deleted']} logs deleted"
                    )
                else:
                    print(f"Periodic log cleanup failed: {result.get('error')}")

        except asyncio.CancelledError:
            print("Periodic log cleanup cancelled")
        except Exception as e:
            print(f"Periodic log cleanup error: {e}")

    def get_retention_policies(self) -> Dict[str, Any]:
        """
        Get current retention policies and settings.

        Returns:
            Dictionary containing retention policy information
        """
        return {
            "default_retention_days": self.default_retention_days,
            "cleanup_batch_size": self.cleanup_batch_size,
            "last_cleanup_time": (
                self._last_cleanup_time.isoformat() if self._last_cleanup_time else None
            ),
            "total_logs_cleaned": self._total_logs_cleaned,
            "healthy": self._healthy,
            "last_cleanup_error": self._last_cleanup_error,
        }

    def update_retention_policy(
        self, days_to_keep: int, batch_size: Optional[int] = None
    ) -> None:
        """
        Update retention policy settings.

        Args:
            days_to_keep: New default retention period
            batch_size: New cleanup batch size (optional)
        """
        self.default_retention_days = days_to_keep

        if batch_size is not None:
            self.cleanup_batch_size = batch_size

    def is_healthy(self) -> bool:
        """
        Check if the cleanup service is healthy.

        Returns:
            True if service is healthy
        """
        return self._healthy

    def reset_health(self) -> None:
        """Reset the health status of the service."""
        self._healthy = True
        self._last_cleanup_error = None

    def get_cleanup_stats(self) -> Dict[str, Any]:
        """
        Get cleanup service statistics.

        Returns:
            Dictionary containing cleanup statistics
        """
        return {
            "healthy": self._healthy,
            "total_logs_cleaned": self._total_logs_cleaned,
            "last_cleanup_time": (
                self._last_cleanup_time.isoformat() if self._last_cleanup_time else None
            ),
            "last_cleanup_error": self._last_cleanup_error,
            "default_retention_days": self.default_retention_days,
            "cleanup_batch_size": self.cleanup_batch_size,
        }
