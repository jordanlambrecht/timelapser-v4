# backend/app/workers/utils/scheduler_helpers.py
"""
Scheduler Helper Utilities

Extracted common patterns and utilities for scheduler operations.
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

from ...constants import DEFAULT_TIMEZONE
from ...enums import LoggerName, LogSource
from ...services.logger import get_service_logger
from ...services.settings_service import SyncSettingsService
from ...utils.time_utils import (
    get_timezone_aware_timestamp_sync,
    get_timezone_from_cache_sync,
)
from ..constants import (
    MILLISECONDS_PER_SECOND,
    SCHEDULER_CACHE_TTL_SECONDS,
    SCHEDULER_IMMEDIATE_JOB_DELAY_SECONDS,
    SCHEDULER_MISFIRE_GRACE_TIME_SECONDS,
)

logger = get_service_logger(LoggerName.SCHEDULER_WORKER, LogSource.SCHEDULER)


class SchedulerTimeUtils:
    """
    Utility class for timezone and time-related scheduler operations.

    Uses modern zoneinfo and aligns with codebase timezone-aware patterns.
    """

    def __init__(self, settings_service: SyncSettingsService):
        """Initialize with settings service for timezone retrieval."""
        self.settings_service = settings_service
        self._cached_timezone: Optional[ZoneInfo] = None
        self._cache_timestamp = 0
        self._cache_ttl = SCHEDULER_CACHE_TTL_SECONDS  # 5 minutes

    def get_timezone(self) -> ZoneInfo:
        """
        Get timezone using codebase-standard timezone handling with caching.

        Returns:
            ZoneInfo timezone object
        """
        current_time = time.time()

        # Check if cache is still valid
        if (
            self._cached_timezone
            and (current_time - self._cache_timestamp) < self._cache_ttl
        ):
            return self._cached_timezone

        try:
            # Use codebase-standard timezone retrieval
            timezone_str = get_timezone_from_cache_sync(self.settings_service)
            self._cached_timezone = ZoneInfo(timezone_str)
            self._cache_timestamp = current_time
            logger.debug(f"Updated timezone cache: {timezone_str}")
        except Exception as e:
            logger.warning(f"Failed to get timezone from settings, using UTC: {e}")
            self._cached_timezone = ZoneInfo(DEFAULT_TIMEZONE)
            self._cache_timestamp = current_time

        return self._cached_timezone

    def get_immediate_run_time(
        self, delay_seconds: int = SCHEDULER_IMMEDIATE_JOB_DELAY_SECONDS
    ) -> datetime:
        """
        Get timezone-aware datetime for immediate job scheduling.

        Uses codebase-standard timezone-aware timestamp generation.

        Args:
            delay_seconds: Seconds to delay execution (default: SCHEDULER_IMMEDIATE_JOB_DELAY_SECONDS)

        Returns:
            Timezone-aware datetime for job scheduling
        """
        current_time = get_timezone_aware_timestamp_sync(self.settings_service)
        return current_time + timedelta(seconds=delay_seconds)

    def get_current_time(self) -> datetime:
        """
        Get current timezone-aware datetime using codebase standards.

        Returns:
            Current timezone-aware datetime from database settings
        """
        return get_timezone_aware_timestamp_sync(self.settings_service)

    def invalidate_cache(self) -> None:
        """Manually invalidate the timezone cache."""
        self._cached_timezone = None
        self._cache_timestamp = 0


class JobIdGenerator:
    """Utility for generating unique job IDs."""

    @staticmethod
    def immediate_capture(camera_id: int, timelapse_id: int) -> str:
        """Generate job ID for immediate capture."""
        timestamp = int(time.time() * MILLISECONDS_PER_SECOND)
        return f"immediate_capture_{camera_id}_{timelapse_id}_{timestamp}"

    @staticmethod
    def immediate_video(timelapse_id: int) -> str:
        """Generate job ID for immediate video generation."""
        timestamp = int(time.time() * MILLISECONDS_PER_SECOND)
        return f"immediate_video_{timelapse_id}_{timestamp}"

    @staticmethod
    def immediate_overlay(image_id: int) -> str:
        """Generate job ID for immediate overlay generation."""
        timestamp = int(time.time() * MILLISECONDS_PER_SECOND)
        return f"immediate_overlay_{image_id}_{timestamp}"

    @staticmethod
    def immediate_thumbnail(image_id: int) -> str:
        """Generate job ID for immediate thumbnail generation."""
        timestamp = int(time.time() * MILLISECONDS_PER_SECOND)
        return f"immediate_thumbnail_{image_id}_{timestamp}"

    @staticmethod
    def timelapse_capture(timelapse_id: int) -> str:
        """Generate job ID for timelapse capture scheduling."""
        return f"timelapse_capture_{timelapse_id}"


class SchedulerJobTemplate:
    """Template for creating scheduler jobs with common patterns."""

    def __init__(
        self, scheduler, job_registry: Dict[str, Any], time_utils: SchedulerTimeUtils
    ):
        """Initialize with scheduler dependencies."""
        self.scheduler = scheduler
        self.job_registry = job_registry
        self.time_utils = time_utils

    def schedule_immediate_job(
        self,
        job_id: str,
        wrapper_func,
        delay_seconds: int = SCHEDULER_IMMEDIATE_JOB_DELAY_SECONDS,
        max_instances: int = 1,
    ) -> bool:
        """
        Template for scheduling immediate one-time jobs.

        Args:
            job_id: Unique job identifier
            wrapper_func: Async function to execute
            delay_seconds: Delay before execution
            max_instances: Maximum concurrent instances

        Returns:
            True if job was scheduled successfully
        """
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                self._remove_job(job_id)

            # Schedule for immediate execution
            run_time = self.time_utils.get_immediate_run_time(delay_seconds)

            job = self.scheduler.add_job(
                func=wrapper_func,
                trigger="date",
                run_date=run_time,
                id=job_id,
                max_instances=max_instances,
                coalesce=True,
                misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME_SECONDS,
            )

            if job:
                self.job_registry[job_id] = job
                logger.debug(f"Scheduled immediate job {job_id} for {run_time}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to schedule immediate job {job_id}: {e}")
            return False

    def schedule_interval_job(
        self, job_id: str, func, interval_seconds: int, max_instances: int = 1
    ) -> bool:
        """
        Template for scheduling interval jobs.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            interval_seconds: Interval between executions
            max_instances: Maximum concurrent instances

        Returns:
            True if job was scheduled successfully
        """
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                self._remove_job(job_id)

            job = self.scheduler.add_job(
                func=func,
                trigger="interval",
                seconds=interval_seconds,
                id=job_id,
                max_instances=max_instances,
                coalesce=True,
                misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME_SECONDS,
            )

            if job:
                self.job_registry[job_id] = job
                logger.debug(
                    f"Scheduled interval job {job_id} every {interval_seconds}s"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to schedule interval job {job_id}: {e}")
            return False

    def schedule_cron_job(
        self,
        job_id: str,
        func,
        minute: Optional[Union[int, str]] = None,
        hour: Optional[Union[int, str]] = None,
        max_instances: int = 1,
    ) -> bool:
        """
        Template for scheduling cron jobs.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            minute: Cron minute specification
            hour: Cron hour specification
            max_instances: Maximum concurrent instances

        Returns:
            True if job was scheduled successfully
        """
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                self._remove_job(job_id)

            tz = self.time_utils.get_timezone()

            job = self.scheduler.add_job(
                func=func,
                trigger="cron",
                minute=minute,
                hour=hour,
                timezone=tz,
                id=job_id,
                max_instances=max_instances,
                coalesce=True,
                misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME_SECONDS,
            )

            if job:
                self.job_registry[job_id] = job
                logger.debug(f"Scheduled cron job {job_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to schedule cron job {job_id}: {e}")
            return False

    def _remove_job(self, job_id: str) -> None:
        """Remove job from scheduler and registry."""
        try:
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                del self.job_registry[job_id]
                logger.debug(f"Removed job {job_id}")
        except Exception as e:
            logger.warning(f"Error removing job {job_id}: {e}")
