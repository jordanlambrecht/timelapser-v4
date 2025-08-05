# backend/app/workers/standard_job_manager.py
"""
Standard Job Manager

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE: Manages RECURRING SYSTEM JOBS that keep the entire platform operational

┌─ StandardJobManager (this file) ─────────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ HEALTH MONITORING ──────────┐     ┌─ DATA REFRESH ────────────────────────────┐ │
│  │ • Camera health checks       │     │ • Weather data (hourly + catchup)        │ │
│  │ • System status monitoring   │     │ • Weather startup refresh                 │ │
│  │ • Regular health intervals   │     │ • Timezone-aware scheduling              │ │
│  └───────────────────────────────┘     └───────────────────────────────────────────┘ │
│                                                                                      │
│  ┌─ AUTOMATION ──────────────────────┐     ┌─ MAINTENANCE ─────────────────────────┐ │
│  │ • Video automation processing     │     │ • Timelapse synchronization           │ │
│  │ • Milestone/scheduled triggers    │     │ • SSE event cleanup                   │ │
│  │ • Automation evaluation cycles    │     │ • System maintenance tasks            │ │
│  └────────────────────────────────────┘     └───────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                   ┌────────────────────────┼────────────────────────┐
                   ▼                        ▼                        ▼

┌─ USES UTILITIES ──────┐   ┌─ COORDINATES WITH ────┐   ┌─ FUNCTION INJECTION ──┐
│ • SchedulerJobTemplate │   │ • AutomationEvaluator  │   │ • health_check_func    │
│ • SchedulerTimeUtils   │   │ • WeatherService       │   │ • weather_refresh_func │
│ • Consistent patterns │   │ • VideoAutomation      │   │ • video_automation_func│
└────────────────────────┘   └────────────────────────┘   └────────────────────────┘

RELATIONSHIP TO SCHEDULER ECOSYSTEM:
• PARENT: SchedulerWorker creates and injects function references
• SIBLINGS: ImmediateJobManager (on-demand), AutomationEvaluator (triggers)
• CHILDREN: Uses SchedulerJobTemplate for consistent job patterns

SYSTEM JOBS BREAKDOWN (6 total jobs):
1. Health Job → Camera/system health monitoring (configurable interval)
2. Weather Job → Hourly weather data refresh (cron-based)
3. Weather Startup → Immediate weather refresh on system startup
4. Weather Catchup → 15-minute backup for missed hourly refreshes
5. Video Automation → Processing video automation queue (regular interval)
6. Automation Triggers → Evaluating milestone/scheduled video triggers (5 min)
7. Timelapse Sync → Synchronizing scheduler with active timelapses (5 min)
8. SSE Cleanup → Cleaning up old SSE events (6 hours)

DESIGN PATTERN: Function Injection Manager
• SchedulerWorker injects all function references during initialization
• Manager handles all the scheduling setup and configuration
• Template patterns ensure consistent job configuration
• Centralized management of all recurring system operations
"""

import inspect
import asyncio
from typing import Dict, Any, Optional, Callable
from ..services.logger import get_service_logger
from ..enums import LoggerName

from .utils import SchedulerTimeUtils, SchedulerJobTemplate
from ..database.core import SyncDatabase
from ..constants import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    WEATHER_REFRESH_MINUTE,
    VIDEO_AUTOMATION_INTERVAL_SECONDS,
    SCHEDULER_UPDATE_INTERVAL_SECONDS,
)
from .constants import (
    WEATHER_STARTUP_DELAY_SECONDS,
    WEATHER_CATCHUP_INTERVAL_MINUTES,
    AUTOMATION_TRIGGER_INTERVAL_MINUTES,
    # TIMELAPSE_SYNC_INTERVAL_MINUTES,
    SSE_CLEANUP_INTERVAL_HOURS,
    CLEANUP_INTERVAL_HOURS_DEFAULT,
    SECONDS_PER_MINUTE,
    SECONDS_PER_HOUR,
)

logger = get_service_logger(LoggerName.SCHEDULER_WORKER)


class StandardJobManager:
    """Manages setup and lifecycle of standard recurring jobs."""

    def __init__(
        self,
        scheduler,
        job_registry: Dict[str, Any],
        db: SyncDatabase,
        time_utils: SchedulerTimeUtils,
        logger_prefix: str = "StandardJobManager",
    ):
        """Initialize standard job manager."""
        self.scheduler = scheduler
        self.job_registry = job_registry
        self.db = db
        self.time_utils = time_utils
        self.job_template = SchedulerJobTemplate(scheduler, job_registry, time_utils)
        self.logger_prefix = logger_prefix

        # External function references (injected by parent)
        self.health_check_func: Optional[Callable] = None
        self.weather_refresh_func: Optional[Callable] = None
        self.video_automation_func: Optional[Callable] = None
        self.automation_triggers_func: Optional[Callable] = None
        self.sync_timelapses_func: Optional[Callable] = None
        self.sse_cleanup_func: Optional[Callable] = None
        self.database_cleanup_func: Optional[Callable] = None

    def log_info(self, message: str) -> None:
        """Log info message with prefix."""
        logger.info(f"{self.logger_prefix}: {message}")

    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message with prefix."""
        if exception:
            logger.error(f"{self.logger_prefix}: {message}: {exception}")
        else:
            logger.error(f"{self.logger_prefix}: {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message with prefix."""
        logger.warning(f"{self.logger_prefix}: {message}")

    def log_debug(self, message: str) -> None:
        """Log debug message with prefix."""
        logger.debug(f"{self.logger_prefix}: {message}")

    def add_all_standard_jobs(self) -> int:
        """
        Add all standard recurring jobs to the scheduler.

        Returns:
            Number of jobs successfully added
        """
        success_count = 0

        # Add health monitoring job
        if self._add_health_job():
            success_count += 1

        # Add weather jobs
        weather_jobs_added = self._add_weather_jobs()
        success_count += weather_jobs_added

        # Add video automation job
        if self._add_video_automation_job():
            success_count += 1

        # Add automation triggers job
        if self._add_automation_triggers_job():
            success_count += 1

        # Add timelapse sync job
        if self._add_timelapse_sync_job():
            success_count += 1

        # Add SSE cleanup job
        if self._add_sse_cleanup_job():
            success_count += 1

        # Add database cleanup job (CEO compliant replacement for CleanupWorker autonomous run)
        if self._add_database_cleanup_job():
            success_count += 1

        total_jobs = len(
            [
                "health_job",
                "weather_job",
                "weather_startup_job",
                "weather_catchup_job",
                "video_automation_job",
                "automation_triggers_job",
                "timelapse_sync_job",
                "sse_cleanup_job",
                "database_cleanup_job",
            ]
        )
        self.log_info(f"Added {success_count}/{total_jobs} standard jobs")
        return success_count

    def _add_health_job(self) -> bool:
        """Add health monitoring job."""
        if not self.health_check_func:
            self.log_warning(
                "Health check function not configured, skipping health job"
            )
            return False

        return self.job_template.schedule_interval_job(
            job_id="health_job",
            func=self.health_check_func,
            interval_seconds=HEALTH_CHECK_INTERVAL_SECONDS,
        )

    def _add_weather_jobs(self) -> int:
        """Add weather-related jobs. Returns number of jobs added."""
        if not self.weather_refresh_func:
            self.log_warning(
                "Weather refresh function not configured, skipping weather jobs"
            )
            return 0

        jobs_added = 0

        # Main weather refresh job (hourly)
        if self.job_template.schedule_cron_job(
            job_id="weather_job",
            func=self.weather_refresh_func,
            minute=WEATHER_REFRESH_MINUTE,
        ):
            jobs_added += 1

        # Weather startup job (immediate refresh on startup)
        startup_wrapper = self._create_weather_startup_wrapper()
        if self.job_template.schedule_immediate_job(
            job_id="weather_startup_job",
            wrapper_func=startup_wrapper,
            delay_seconds=WEATHER_STARTUP_DELAY_SECONDS,
        ):
            jobs_added += 1

        # Weather catchup job (every 15 minutes to catch missed schedules)
        catchup_wrapper = self._create_weather_catchup_wrapper()
        if self.job_template.schedule_interval_job(
            job_id="weather_catchup_job",
            func=catchup_wrapper,
            interval_seconds=WEATHER_CATCHUP_INTERVAL_MINUTES
            * SECONDS_PER_MINUTE,  # 15 minutes
        ):
            jobs_added += 1

        return jobs_added

    def _create_weather_startup_wrapper(self):
        """Create weather startup wrapper function."""

        async def weather_startup_func() -> None:
            """Wrapper to force weather refresh on startup"""
            if self.weather_refresh_func is not None and hasattr(
                self.weather_refresh_func, "__call__"
            ):
                # Check if weather_func accepts force_refresh parameter

                sig = inspect.signature(self.weather_refresh_func)
                if "force_refresh" in sig.parameters:
                    await self.weather_refresh_func(force_refresh=True)
                else:
                    await self.weather_refresh_func()

        return weather_startup_func

    def _create_weather_catchup_wrapper(self):
        """Create weather catchup wrapper function."""

        def weather_catchup_wrapper():
            """Check if we missed the hourly weather schedule and refresh if needed"""
            try:
                current_time = self.time_utils.get_current_time()
                # If we're within 5 minutes after the scheduled minute, refresh weather
                if (
                    current_time.minute >= WEATHER_REFRESH_MINUTE
                    and current_time.minute <= WEATHER_REFRESH_MINUTE + 5
                ):
                    if self.weather_refresh_func is not None:
                        asyncio.create_task(self.weather_refresh_func())
            except Exception as e:
                self.log_error(f"Error in weather catchup: {e}")

        return weather_catchup_wrapper

    def _add_video_automation_job(self) -> bool:
        """Add video automation processing job."""
        if not self.video_automation_func:
            self.log_warning(
                "Video automation function not configured, skipping video automation job"
            )
            return False

        return self.job_template.schedule_interval_job(
            job_id="video_automation_job",
            func=self.video_automation_func,
            interval_seconds=VIDEO_AUTOMATION_INTERVAL_SECONDS,
        )

    def _add_automation_triggers_job(self) -> bool:
        """Add automation triggers evaluation job."""
        if not self.automation_triggers_func:
            self.log_warning(
                "Automation triggers function not configured, skipping automation triggers job"
            )
            return False

        return self.job_template.schedule_interval_job(
            job_id="automation_triggers_job",
            func=self.automation_triggers_func,
            interval_seconds=AUTOMATION_TRIGGER_INTERVAL_MINUTES
            * SECONDS_PER_MINUTE,  # 5 minutes
        )

    def _add_timelapse_sync_job(self) -> bool:
        """Add timelapse synchronization job."""
        if not self.sync_timelapses_func:
            self.log_warning(
                "Sync timelapses function not configured, skipping timelapse sync job"
            )
            return False

        return self.job_template.schedule_interval_job(
            job_id="timelapse_sync_job",
            func=self.sync_timelapses_func,
            interval_seconds=SCHEDULER_UPDATE_INTERVAL_SECONDS,
        )

    def _add_sse_cleanup_job(self) -> bool:
        """Add SSE cleanup job."""
        if not self.sse_cleanup_func:
            self.log_debug(
                "SSE cleanup function not configured, skipping SSE cleanup job"
            )
            return False

        return self.job_template.schedule_interval_job(
            job_id="sse_cleanup_job",
            func=self.sse_cleanup_func,
            interval_seconds=SSE_CLEANUP_INTERVAL_HOURS * SECONDS_PER_HOUR,  # 6 hours
        )

    def _add_database_cleanup_job(self) -> bool:
        """Add database cleanup job (CEO compliant - replaces CleanupWorker autonomous run)."""
        if not self.database_cleanup_func:
            self.log_debug(
                "Database cleanup function not configured, skipping database cleanup job"
            )
            return False

        return self.job_template.schedule_interval_job(
            job_id="database_cleanup_job",
            func=self.database_cleanup_func,
            interval_seconds=CLEANUP_INTERVAL_HOURS_DEFAULT
            * SECONDS_PER_HOUR,  # 6 hours
        )

    def remove_all_standard_jobs(self) -> None:
        """Remove all standard jobs from the scheduler."""
        standard_job_ids = [
            "health_job",
            "weather_job",
            "weather_startup_job",
            "weather_catchup_job",
            "video_automation_job",
            "automation_triggers_job",
            "timelapse_sync_job",
            "sse_cleanup_job",
            "database_cleanup_job",
        ]

        for job_id in standard_job_ids:
            if job_id in self.job_registry:
                try:
                    self.scheduler.remove_job(job_id)
                    del self.job_registry[job_id]
                    self.log_debug(f"Removed standard job {job_id}")
                except Exception as e:
                    self.log_warning(f"Error removing standard job {job_id}: {e}")
