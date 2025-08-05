# backend/app/workers/mixins/job_processing_mixin.py
"""
Job Processing Mixin for Background Workers.

Provides standardized job processing functionality that eliminates the 800+ lines
of duplicated code found across ThumbnailWorker and OverlayWorker.
"""

import asyncio
import time
from abc import abstractmethod
from datetime import timedelta
from typing import Any, Dict, Generic, List, Optional, Sequence, TypeVar

from ...enums import SSEEventSource
from ...utils.time_utils import utc_now
from ..base_worker import BaseWorker
from .job_batch_processor import JobBatchProcessor, ProcessableJob
from .retry_manager import RetryManager
from .sse_broadcaster import SSEBroadcaster

# Generic type variable for specific job types
JobType = TypeVar("JobType", bound=ProcessableJob)


class JobProcessingMixin(BaseWorker, Generic[JobType]):
    """
    Abstract mixin providing standardized job processing functionality.

    This mixin eliminates the massive code duplication found between
    ThumbnailWorker and OverlayWorker by providing shared implementations
    of common job processing patterns including:

    - Batch job processing with adaptive performance scaling
    - Retry logic with exponential backoff
    - SSE event broadcasting for job lifecycle events
    - Performance monitoring and statistics collection
    - Periodic cleanup operations
    - Concurrent job processing with throttling

    Workers that inherit from this mixin need only implement the
    job-specific logic while gaining all the shared infrastructure.

    PROVIDES: Consistent, tested, optimized job processing patterns
    """

    def __init__(
        self,
        name: str,
        sse_ops,
        event_source: SSEEventSource,
        max_retries: int = 3,
        retry_delays: Optional[List[int]] = None,
        batch_size: int = 5,
        worker_interval: int = 10,
        cleanup_hours: int = 24,
        max_concurrent_jobs: int = 3,
        high_load_batch_size: int = 15,
        high_load_threshold: int = 20,
        low_load_threshold: int = 5,
    ):
        """
        Initialize job processing mixin.

        Args:
            name: Worker name for logging and identification
            sse_ops: SSE operations service for event broadcasting
            event_source: SSE event source for this worker type
            max_retries: Maximum retry attempts for failed jobs
            retry_delays: List of delay minutes for retry attempts
            batch_size: Default number of jobs to process per batch
            worker_interval: Seconds between job processing cycles
            cleanup_hours: Hours after which completed jobs are cleaned up
            max_concurrent_jobs: Maximum concurrent jobs within a batch
            high_load_batch_size: Batch size during high load periods
            high_load_threshold: Queue size to trigger high load mode
            low_load_threshold: Queue size to return to normal mode
        """
        super().__init__(name)

        # Set default retry delays if not provided
        if retry_delays is None:
            retry_delays = [1, 5, 15]  # 1 min, 5 min, 15 min

        # Initialize shared components
        self.retry_manager = RetryManager(
            max_retries=max_retries, retry_delays=retry_delays, worker_name=name
        )

        self.sse_broadcaster = SSEBroadcaster(
            sse_ops=sse_ops, worker_name=name, event_source=event_source
        )

        self.job_batch_processor = JobBatchProcessor(
            worker_name=name,
            default_batch_size=batch_size,
            max_concurrent_jobs=max_concurrent_jobs,
            high_load_batch_size=high_load_batch_size,
            high_load_threshold=high_load_threshold,
            low_load_threshold=low_load_threshold,
        )

        # Configuration
        self.worker_interval = worker_interval
        self.cleanup_hours = cleanup_hours

        # Cleanup tracking - initialize to allow immediate first cleanup
        self.last_cleanup_time = utc_now() - timedelta(hours=cleanup_hours)

    # Abstract methods that must be implemented by concrete workers

    @abstractmethod
    def get_pending_jobs(self, batch_size: int) -> Sequence[JobType]:
        """
        Get pending jobs from the queue.

        Args:
            batch_size: Maximum number of jobs to retrieve

        Returns:
            Sequence of pending jobs to process
        """
        pass

    @abstractmethod
    def process_single_job_impl(self, job: JobType) -> bool:
        """
        Process a single job (worker-specific implementation).

        Args:
            job: Job to process

        Returns:
            True if job completed successfully, False otherwise
        """
        pass

    @abstractmethod
    def mark_job_failed(self, job_id: int, error_message: str) -> bool:
        """
        Mark a job as permanently failed.

        Args:
            job_id: ID of the job to mark as failed
            error_message: Reason for failure

        Returns:
            True if successfully marked as failed
        """
        pass

    @abstractmethod
    def schedule_job_retry(
        self, job_id: int, retry_count: int, delay_minutes: int
    ) -> bool:
        """
        Schedule a job for retry.

        Args:
            job_id: ID of the job to retry
            retry_count: New retry count
            delay_minutes: Minutes to wait before retry

        Returns:
            True if retry was successfully scheduled
        """
        pass

    @abstractmethod
    def cleanup_completed_jobs(self, hours_to_keep: int) -> int:
        """
        Clean up completed jobs older than specified hours.

        Args:
            hours_to_keep: Number of hours of completed jobs to keep

        Returns:
            Number of jobs cleaned up
        """
        pass

    @abstractmethod
    def get_queue_statistics(self) -> Dict[str, int]:
        """
        Get current job queue statistics.

        Returns:
            Dictionary with queue statistics (pending_jobs, processing_jobs, etc.)
        """
        pass

    # Shared implementations using the utility classes

    async def process_jobs(self) -> int:
        """
        Main job processing method that handles a batch of jobs.

        This method orchestrates the entire job processing cycle including:
        - Retrieving pending jobs
        - Processing them with concurrency control
        - Handling failures with retry logic
        - Broadcasting lifecycle events
        - Collecting performance metrics

        Returns:
            Number of jobs successfully processed
        """
        return await self.job_batch_processor.process_job_batch(
            get_pending_jobs=self.get_pending_jobs,
            process_single_job=self._process_single_job_with_lifecycle,
            get_queue_stats=self.get_queue_statistics,
        )

    def _process_single_job_with_lifecycle(self, job: JobType) -> bool:
        """
        Process a single job with full lifecycle management.

        This method handles:
        - Broadcasting job started events
        - Calling the worker-specific processing implementation
        - Handling success/failure outcomes
        - Broadcasting completion/failure events
        - Managing retry logic

        Args:
            job: Job to process

        Returns:
            True if job completed successfully
        """
        try:
            # Broadcast job started event
            self.sse_broadcaster.broadcast_job_started(
                job_id=job.id, job_data=self._get_job_data_for_events(job)
            )

            # Process the job using worker-specific implementation
            start_time = time.time()
            success = self.process_single_job_impl(job)
            processing_time_ms = int((time.time() - start_time) * 1000)

            if success:
                # Broadcast completion event
                self.sse_broadcaster.broadcast_job_completed(
                    job_id=job.id,
                    processing_time_ms=processing_time_ms,
                    job_data=self._get_job_data_for_events(job),
                )
                return True
            else:
                # Handle failure with retry logic
                return self._handle_job_failure(job, "Job processing failed")

        except Exception as e:
            self.log_error(f"Exception processing job {job.id}", e)
            return self._handle_job_failure(job, str(e))

    def _handle_job_failure(self, job: JobType, error_message: str) -> bool:
        """
        Handle job failure with retry logic and event broadcasting.

        Args:
            job: Failed job
            error_message: Description of the failure

        Returns:
            True if job was scheduled for retry, False if permanently failed
        """
        try:
            if self.retry_manager.should_retry(job):
                # Schedule retry
                retry_info = self.retry_manager.get_retry_info(job)
                next_retry_count = retry_info["next_retry_count"]
                delay_minutes = retry_info["retry_delay_minutes"]

                if self.schedule_job_retry(job.id, next_retry_count, delay_minutes):
                    # Broadcast retry scheduled event
                    self.sse_broadcaster.broadcast_job_retry_scheduled(
                        job_id=job.id,
                        retry_count=next_retry_count,
                        retry_delay_minutes=delay_minutes,
                        error_message=error_message,
                        job_data=self._get_job_data_for_events(job),
                    )

                    self.retry_manager.log_retry_scheduled(job, error_message)
                    return True
                else:
                    self.log_error(f"Failed to schedule retry for job {job.id}")

            # Maximum retries exceeded or retry scheduling failed
            self.mark_job_failed(job.id, error_message)

            # Broadcast permanent failure event
            self.sse_broadcaster.broadcast_job_failed(
                job_id=job.id,
                error_message=error_message,
                job_data=self._get_job_data_for_events(job),
                is_permanent=True,
            )

            self.log_error(
                f"Job {job.id} permanently failed after {job.retry_count} retries: {error_message}"
            )
            return False

        except Exception as e:
            self.log_error(f"Error handling job failure for job {job.id}: {e}")
            return False

    async def periodic_cleanup(self) -> None:
        """
        Perform periodic cleanup of old completed jobs.

        This method runs cleanup based on the configured cleanup interval
        and broadcasts cleanup statistics via SSE events.
        """
        now = utc_now()

        # Only run cleanup after the configured interval has passed
        if (now - self.last_cleanup_time).total_seconds() < (self.cleanup_hours * 3600):
            return  # Not enough time has passed since last cleanup

        try:
            self.log_debug("Running periodic job cleanup")

            # Cleanup completed jobs
            cleaned_count = self.cleanup_completed_jobs(self.cleanup_hours)

            if cleaned_count > 0:
                self.log_info(f"Cleaned up {cleaned_count} old completed jobs")

                # Broadcast cleanup statistics
                self.sse_broadcaster.broadcast_worker_statistics(
                    {
                        "cleanup_completed": True,
                        "jobs_cleaned": cleaned_count,
                        "cleanup_hours": self.cleanup_hours,
                    }
                )

            self.last_cleanup_time = now

        except Exception as e:
            self.log_error(f"Error during periodic cleanup: {e}")

    async def run(self) -> None:
        """
        Main worker loop - processes jobs continuously while running.

        This is the standardized run loop that all job processing workers
        can use, providing consistent behavior across different worker types.
        """
        self.log_info(f"Starting {self.name} worker main loop")

        # Broadcast worker startup
        self.sse_broadcaster.broadcast_worker_started(
            worker_config=self._get_worker_config()
        )

        while self.running:
            try:
                # Process a batch of jobs
                processed_count = await self.process_jobs()

                # Perform periodic cleanup
                await self.periodic_cleanup()

                # Broadcast statistics periodically
                if processed_count > 0 or self._should_broadcast_stats():
                    await self._broadcast_worker_statistics()

                # Wait before next cycle
                await asyncio.sleep(self.worker_interval)

            except asyncio.CancelledError:
                self.log_info(f"{self.name} worker loop cancelled")
                break
            except Exception as e:
                self.log_error(f"Unexpected error in {self.name} worker loop", e)

                # Broadcast error event
                self.sse_broadcaster.broadcast_worker_error(
                    error_message=f"Unexpected error in {self.name} worker loop: {e}",
                    error_context={"loop_iteration": True}
                )

                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(5)

        # Broadcast worker shutdown
        final_stats = self.get_status()
        self.sse_broadcaster.broadcast_worker_stopped(
            stop_reason="Normal shutdown", final_stats=final_stats
        )

        self.log_info(f"{self.name} worker main loop stopped")

    async def _broadcast_worker_statistics(self) -> None:
        """Broadcast current worker statistics via SSE."""
        try:
            stats = self.get_status()
            self.sse_broadcaster.broadcast_worker_statistics(stats)
        except Exception as e:
            self.log_warning(f"Failed to broadcast worker statistics: {e}")

    def _should_broadcast_stats(self) -> bool:
        """
        Determine if worker statistics should be broadcasted.

        Returns:
            True if statistics should be broadcasted
        """
        # Broadcast stats every 5 minutes during normal operation
        return utc_now().minute % 5 == 0

    def _get_job_data_for_events(self, job: JobType) -> Dict[str, Any]:
        """
        Extract relevant job data for SSE events.

        Can be overridden by concrete workers to include job-specific data.

        Args:
            job: Job to extract data from

        Returns:
            Dictionary with job data for events
        """
        return {
            "job_id": job.id,
            "priority": job.priority,
            "retry_count": job.retry_count,
        }

    def _get_worker_config(self) -> Dict[str, Any]:
        """
        Get worker configuration for startup events.

        Returns:
            Dictionary with worker configuration
        """
        return {
            "worker_interval": self.worker_interval,
            "cleanup_hours": self.cleanup_hours,
            "batch_size": self.job_batch_processor.current_batch_size,
            "max_retries": self.retry_manager.max_retries,
            "retry_delays": self.retry_manager.retry_delays,
            "max_concurrent_jobs": self.job_batch_processor._max_concurrent_jobs,
        }

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive worker status including all shared components.

        Returns:
            Dictionary with complete worker status
        """
        # Get base status from BaseWorker
        base_status = super().get_status()

        # Add JobProcessingMixin-specific fields
        base_status.update(
            {
                "worker_interval": self.worker_interval,
                "cleanup_hours": self.cleanup_hours,
                "last_cleanup": self.last_cleanup_time.isoformat(),
            }
        )

        # Add performance stats from job batch processor
        performance_stats = self.job_batch_processor.get_performance_stats()
        base_status.update(performance_stats)

        # Add retry manager stats
        retry_stats = self.retry_manager.get_stats()
        base_status["retry_config"] = retry_stats

        # Add SSE broadcast stats
        sse_stats = self.sse_broadcaster.get_broadcast_stats()
        base_status["sse_stats"] = sse_stats

        # Add queue statistics
        try:
            queue_stats = self.get_queue_statistics()
            base_status["queue_stats"] = queue_stats
        except Exception as e:
            base_status["queue_stats_error"] = str(e)

        return base_status
