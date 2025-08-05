# backend/app/workers/mixins/retry_manager.py
"""
Retry Manager for Worker Job Processing.

Provides standardized exponential backoff retry logic for failed jobs,
eliminating duplication between ThumbnailWorker and OverlayWorker.
"""


from datetime import datetime, timedelta
from typing import List, Protocol, runtime_checkable

from ...enums import LoggerName
from ...services.logger import get_service_logger
from ...utils.time_utils import utc_now, utc_timestamp

logger = get_service_logger(LoggerName.SCHEDULER_WORKER)


@runtime_checkable
class JobWithRetry(Protocol):
    """Protocol for jobs that support retry logic."""

    id: int
    retry_count: int


class RetryManager:
    """
    Manages exponential backoff retry logic for failed worker jobs.

    This class eliminates the duplicated retry logic found in both
    ThumbnailWorker and OverlayWorker, providing a consistent approach
    to handling job failures with exponential backoff delays.

    Features:
    - Configurable maximum retry attempts
    - Exponential backoff with customizable delay intervals
    - Consistent retry scheduling across different job types
    - Comprehensive logging for debugging retry scenarios
    """

    def __init__(
        self, max_retries: int, retry_delays: List[int], worker_name: str = "Worker"
    ):
        """
        Initialize retry manager.

        Args:
            max_retries: Maximum number of retry attempts before permanent failure
            retry_delays: List of delay minutes for each retry attempt (e.g., [1, 5, 15])
            worker_name: Name of the worker for logging purposes
        """
        self.max_retries = max_retries
        self.retry_delays = retry_delays
        self.worker_name = worker_name

        # Validate configuration
        if max_retries <= 0:
            raise ValueError("max_retries must be greater than 0")
        if not retry_delays:
            raise ValueError("retry_delays cannot be empty")
        if any(delay <= 0 for delay in retry_delays):
            raise ValueError("All retry delays must be positive")

    def should_retry(self, job: JobWithRetry) -> bool:
        """
        Determine if a job should be retried based on its current retry count.

        Args:
            job: Job object with retry_count attribute

        Returns:
            True if job should be retried, False if max retries exceeded
        """
        return job.retry_count < self.max_retries

    def get_retry_delay(self, retry_count: int) -> int:
        """
        Get the delay in minutes for a specific retry attempt.

        Uses exponential backoff with configured delays. If retry_count
        exceeds the number of configured delays, uses the last delay value.

        Args:
            retry_count: Current retry attempt number (0-based)

        Returns:
            Delay in minutes before the next retry attempt
        """
        if retry_count < 0:
            return self.retry_delays[0]

        # Use the last delay if retry_count exceeds configured delays
        delay_index = min(retry_count, len(self.retry_delays) - 1)
        return self.retry_delays[delay_index]

    def calculate_next_retry_time(self, retry_count: int) -> datetime:
        """
        Calculate the next retry time based on retry count.

        Args:
            retry_count: Current retry attempt number

        Returns:
            UTC datetime when the job should be retried
        """
        delay_minutes = self.get_retry_delay(retry_count)
        return utc_now() + timedelta(minutes=delay_minutes)

    def get_retry_info(self, job: JobWithRetry) -> dict:
        """
        Get comprehensive retry information for a job.

        Args:
            job: Job object with retry information

        Returns:
            Dictionary containing retry status and timing information
        """
        next_retry_count = job.retry_count + 1
        can_retry = self.should_retry(job)

        info = {
            "job_id": job.id,
            "current_retry_count": job.retry_count,
            "next_retry_count": next_retry_count,
            "max_retries": self.max_retries,
            "can_retry": can_retry,
            "is_final_attempt": next_retry_count >= self.max_retries,
        }

        if can_retry:
            delay_minutes = self.get_retry_delay(job.retry_count)
            next_retry_time = self.calculate_next_retry_time(job.retry_count)

            info.update(
                {
                    "retry_delay_minutes": delay_minutes,
                    "next_retry_time": next_retry_time.isoformat(),
                    "next_retry_timestamp": next_retry_time,
                }
            )

        return info

    def log_retry_scheduled(self, job: JobWithRetry, error_message: str) -> None:
        """
        Log that a retry has been scheduled for a job.

        Args:
            job: Job being retried
            error_message: Error that caused the failure
        """
        retry_info = self.get_retry_info(job)

        if retry_info["can_retry"]:
            logger.warning(
                f"[{self.worker_name}] ⚠️ Job {job.id} failed (attempt {job.retry_count + 1}), "
                f"scheduled for retry in {retry_info['retry_delay_minutes']} minutes: {error_message}"
            )
        else:
            logger.error(
                f"[{self.worker_name}] ❌ Job {job.id} permanently failed after {job.retry_count} retries: {error_message}"
            )

    def log_retry_attempt(self, job: JobWithRetry) -> None:
        """
        Log that a retry attempt is starting.

        Args:
            job: Job being retried
        """
        logger.info(
            f"[{self.worker_name}] 🔄 Starting retry attempt {job.retry_count + 1}/{self.max_retries} for job {job.id}"
        )

    def create_retry_event_data(self, job: JobWithRetry, error_message: str) -> dict:
        """
        Create standardized event data for retry broadcasts.

        Args:
            job: Job being retried
            error_message: Error that caused the failure

        Returns:
            Dictionary suitable for SSE broadcasting
        """
        retry_info = self.get_retry_info(job)

        event_data = {
            "job_id": job.id,
            "retry_count": retry_info["next_retry_count"],
            "max_retries": self.max_retries,
            "error_message": error_message,
            "timestamp": utc_timestamp(),
            "is_final_attempt": retry_info["is_final_attempt"],
        }

        if retry_info["can_retry"]:
            event_data.update(
                {
                    "retry_delay_minutes": retry_info["retry_delay_minutes"],
                    "next_retry_time": retry_info["next_retry_time"],
                }
            )

        return event_data

    def get_stats(self) -> dict:
        """
        Get retry manager configuration and statistics.

        Returns:
            Dictionary with retry manager configuration
        """
        return {
            "worker_name": self.worker_name,
            "max_retries": self.max_retries,
            "retry_delays": self.retry_delays,
            "total_delay_levels": len(self.retry_delays),
            "max_total_delay_minutes": sum(self.retry_delays),
        }

    def __repr__(self) -> str:
        """String representation of retry manager."""
        return (
            f"RetryManager(worker='{self.worker_name}', "
            f"max_retries={self.max_retries}, "
            f"delays={self.retry_delays})"
        )
