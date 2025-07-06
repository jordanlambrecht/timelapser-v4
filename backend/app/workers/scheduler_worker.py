"""
Scheduler worker for Timelapser v4.

Handles job scheduling and interval management for all worker operations.
"""

import asyncio
from datetime import timedelta
from typing import Dict, Any, Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job

from .base_worker import BaseWorker
from ..services.settings_service import SyncSettingsService
from ..utils.timezone_utils import utc_now, get_timezone_from_settings, create_timezone_aware_datetime
from ..constants import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    SCHEDULER_MAX_INSTANCES,
    HEALTH_CHECK_INTERVAL_SECONDS,
    WEATHER_REFRESH_MINUTE,
    VIDEO_AUTOMATION_INTERVAL_SECONDS,
    SCHEDULER_UPDATE_INTERVAL_SECONDS,
    STANDARD_JOBS_COUNT,
)


class SchedulerWorker(BaseWorker):
    """
    Worker responsible for job scheduling and interval management.

    Handles:
    - APScheduler instance management
    - Job registration and lifecycle
    - Interval updates based on settings changes
    - Scheduler health monitoring
    """

    def __init__(self, settings_service: SyncSettingsService):
        """
        Initialize scheduler worker with injected dependencies.

        Args:
            settings_service: Settings operations service
        """
        super().__init__("SchedulerWorker")
        self.settings_service = settings_service
        self.scheduler = AsyncIOScheduler()
        self.current_capture_interval = DEFAULT_CAPTURE_INTERVAL_SECONDS
        self.job_registry: Dict[str, Job] = {}

    async def initialize(self) -> None:
        """Initialize scheduler worker resources."""
        self.log_info("Initialized scheduler worker")

        # Load current capture interval from settings
        try:
            self.current_capture_interval = await self.run_in_executor(
                self.settings_service.get_capture_interval_setting
            )
            self.log_info(f"Loaded capture interval: {self.current_capture_interval}s")
        except Exception as e:
            self.log_warning(f"Failed to load capture interval, using default: {e}")

    async def cleanup(self) -> None:
        """Cleanup scheduler worker resources."""
        self.log_info("Cleaning up scheduler worker")

        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                self.log_info("Scheduler shut down")
        except Exception as e:
            self.log_error("Error shutting down scheduler", e)

    def start_scheduler(self) -> None:
        """Start the APScheduler instance."""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.log_info("Scheduler started successfully")
            else:
                self.log_debug("Scheduler already running")
        except Exception as e:
            self.log_error("Failed to start scheduler", e)
            raise

    def stop_scheduler(self) -> None:
        """Stop the APScheduler instance."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                self.log_info("Scheduler stopped")
            else:
                self.log_debug("Scheduler already stopped")
        except Exception as e:
            self.log_error("Error stopping scheduler", e)

    def add_job(
        self,
        job_id: str,
        func: Callable,
        trigger: str,
        name: Optional[str] = None,
        **trigger_kwargs,
    ) -> bool:
        """
        Add a job to the scheduler.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            trigger: Trigger type (interval, cron, date)
            name: Human-readable job name
            **trigger_kwargs: Trigger-specific arguments

        Returns:
            bool: True if job was added successfully
        """
        try:
            # Remove existing job if it exists
            if job_id in self.job_registry:
                self.remove_job(job_id)

            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                max_instances=SCHEDULER_MAX_INSTANCES,
                **trigger_kwargs,
            )

            self.job_registry[job_id] = job
            self.log_info(f"Added job '{job_id}' with trigger '{trigger}'")
            return True

        except Exception as e:
            self.log_error(f"Failed to add job '{job_id}'", e)
            return False

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a job from the scheduler.

        Args:
            job_id: Job identifier to remove

        Returns:
            bool: True if job was removed successfully
        """
        try:
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                del self.job_registry[job_id]
                self.log_info(f"Removed job '{job_id}'")
                return True
            else:
                self.log_warning(f"Job '{job_id}' not found in registry")
                return False

        except Exception as e:
            self.log_error(f"Failed to remove job '{job_id}'", e)
            return False

    def modify_job(self, job_id: str, **changes) -> bool:
        """
        Modify an existing job's parameters.

        Args:
            job_id: Job identifier to modify
            **changes: Parameters to change

        Returns:
            bool: True if job was modified successfully
        """
        try:
            if job_id in self.job_registry:
                self.scheduler.modify_job(job_id, **changes)
                self.log_info(f"Modified job '{job_id}': {changes}")
                return True
            else:
                self.log_warning(f"Job '{job_id}' not found for modification")
                return False

        except Exception as e:
            self.log_error(f"Failed to modify job '{job_id}'", e)
            return False

    async def update_capture_interval(self) -> bool:
        """
        Update capture interval if settings have changed.

        Returns:
            bool: True if interval was updated
        """
        try:
            new_interval = await self.run_in_executor(
                self.settings_service.get_capture_interval_setting
            )

            if new_interval != self.current_capture_interval:
                self.log_info(
                    f"Updating capture interval: {self.current_capture_interval}s -> {new_interval}s"
                )

                # Update the capture job if it exists
                if "capture_job" in self.job_registry:
                    success = self.modify_job("capture_job", seconds=new_interval)
                    if success:
                        self.current_capture_interval = new_interval
                        return True
                else:
                    # No capture job registered yet, just update the stored value
                    self.current_capture_interval = new_interval
                    return True

            return False  # No change needed

        except Exception as e:
            self.log_error("Error updating capture interval", e)
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            Optional[Dict[str, Any]]: Job status or None if not found
        """
        try:
            if job_id in self.job_registry:
                job = self.job_registry[job_id]
                return {
                    "id": job.id,
                    "name": job.name,
                    "trigger": str(job.trigger),
                    "next_run_time": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "max_instances": job.max_instances,
                    "pending": job.pending,
                }
            else:
                return None

        except Exception as e:
            self.log_error(f"Error getting job status for '{job_id}'", e)
            return None

    def get_all_jobs_status(self) -> Dict[str, Any]:
        """
        Get status information for all registered jobs.

        Returns:
            Dict[str, Any]: Status information for all jobs
        """
        try:
            jobs_status = {}

            for job_id in self.job_registry:
                status = self.get_job_status(job_id)
                if status:
                    jobs_status[job_id] = status

            return {
                "total_jobs": len(self.job_registry),
                "scheduler_running": self.scheduler.running,
                "jobs": jobs_status,
            }

        except Exception as e:
            self.log_error("Error getting all jobs status", e)
            return {
                "total_jobs": 0,
                "scheduler_running": False,
                "jobs": {},
                "error": str(e),
            }

    def add_standard_jobs(
        self,
        capture_func: Callable,
        health_func: Callable,
        weather_func: Callable,
        video_func: Callable,
        sse_cleanup_func: Optional[Callable] = None,
    ) -> bool:
        """
        Add standard worker jobs to the scheduler.

        Args:
            capture_func: Camera capture function
            health_func: Health monitoring function
            weather_func: Weather refresh function
            video_func: Video automation function
            sse_cleanup_func: SSE events cleanup function (optional)

        Returns:
            bool: True if all jobs were added successfully
        """
        try:
            success_count = 0

            # Get timezone for timezone-aware scheduling
            try:
                settings_dict = self.settings_service.get_all_settings()
                timezone_str = get_timezone_from_settings(settings_dict)
            except Exception as e:
                self.log_warning(f"Failed to get timezone, using UTC: {e}")
                timezone_str = "UTC"

            # Schedule image capture job
            if self.add_job(
                job_id="capture_job",
                func=capture_func,
                trigger="interval",
                name="Capture Images from Running Cameras",
                seconds=self.current_capture_interval,
            ):
                success_count += 1

            # Schedule health monitoring job (every minute)
            if self.add_job(
                job_id="health_job",
                func=health_func,
                trigger="interval",
                name="Monitor Camera Connectivity",
                seconds=HEALTH_CHECK_INTERVAL_SECONDS,
            ):
                success_count += 1

            # Schedule weather data refresh job (hourly) - timezone aware
            if self.add_job(
                job_id="weather_job",
                func=weather_func,
                trigger="cron",
                name="Refresh Weather Data",
                minute=WEATHER_REFRESH_MINUTE,
                timezone=timezone_str,
            ):
                success_count += 1
                self.log_info(f"Scheduled hourly weather refresh at minute {WEATHER_REFRESH_MINUTE} in timezone {timezone_str}")

            # Run weather refresh immediately on startup (add 2 seconds delay to ensure everything is initialized)
            startup_time = create_timezone_aware_datetime(timezone_str) + timedelta(seconds=2)
            if self.add_job(
                job_id="weather_startup_job",
                func=weather_func,
                trigger="date",
                name="Initial Weather Data Refresh",
                run_date=startup_time,
            ):
                success_count += 1
                self.log_info(f"Scheduled weather startup refresh for {startup_time.isoformat()}")

            # Add weather catch-up job that runs every 15 minutes to check if we missed the hourly schedule
            if self.add_job(
                job_id="weather_catchup_job",
                func=self._create_weather_catchup_wrapper(weather_func),
                trigger="interval",
                name="Weather Schedule Recovery",
                minutes=15,
            ):
                success_count += 1

            # Schedule video automation processing (every 2 minutes)
            if self.add_job(
                job_id="video_automation_job",
                func=video_func,
                trigger="interval",
                name="Process Video Automation",
                seconds=VIDEO_AUTOMATION_INTERVAL_SECONDS,
            ):
                success_count += 1

            # Schedule interval update check (every 5 minutes)
            if self.add_job(
                job_id="interval_job",
                func=self.update_capture_interval,
                trigger="interval",
                name="Update Scheduler Interval",
                seconds=SCHEDULER_UPDATE_INTERVAL_SECONDS,
            ):
                success_count += 1

            # Add SSE cleanup job (every 6 hours) if function provided
            if sse_cleanup_func:
                if self.add_job(
                    job_id="sse_cleanup_job",
                    func=sse_cleanup_func,
                    trigger="interval",
                    name="SSE Events Cleanup",
                    hours=6,
                ):
                    success_count += 1

            # Calculate expected job count
            expected_jobs = STANDARD_JOBS_COUNT + 1  # Added weather_catchup_job
            if sse_cleanup_func:
                expected_jobs += 1  # Added sse_cleanup_job
                
            self.log_info(f"Added {success_count}/{expected_jobs} standard jobs successfully")
            return success_count == expected_jobs

        except Exception as e:
            self.log_error("Error adding standard jobs", e)
            return False

    def _create_weather_catchup_wrapper(self, weather_func: Callable) -> Callable:
        """
        Create a wrapper function that checks if weather refresh should run
        to catch up on missed schedules.
        
        Args:
            weather_func: The weather refresh function to wrap
            
        Returns:
            Wrapped function that checks schedule and runs if needed
        """
        async def weather_catchup():
            try:
                # Get timezone-aware current time
                settings_dict = self.settings_service.get_all_settings()
                timezone_str = get_timezone_from_settings(settings_dict)
                now = create_timezone_aware_datetime(timezone_str)
                
                # Check if we're within the first 15 minutes of the hour
                # If so, we might have missed the scheduled refresh at minute 0
                if now.minute <= 15:
                    # TODO: Check last weather refresh time from weather service
                    # For now, just check if we're close to the top of the hour
                    self.log_info("Checking if weather refresh was missed this hour...")
                    
                    # Run weather refresh - the weather service will check if it's needed
                    await weather_func()
                else:
                    self.log_debug("Weather catch-up check: not in catch-up window")
                    
            except Exception as e:
                self.log_error("Error in weather catch-up check", e)
        
        return weather_catchup
