# backend/app/workers/mixins/job_batch_processor.py
"""
Job Batch Processor for Worker Queue Management.

Provides standardized job batch processing with concurrency control and performance monitoring,
eliminating duplication between ThumbnailWorker and OverlayWorker.
"""

import asyncio
import time
from typing import (
    List,
    Dict,
    Any,
    Callable,
    Optional,
    Protocol,
    runtime_checkable,
    Sequence,
    TypeVar,
    Generic,
)
from datetime import datetime, timedelta
from ...services.logger import get_service_logger, LogEmoji
from ...enums import LoggerName

logger = get_service_logger(LoggerName.SCHEDULER_WORKER)

from ...utils.time_utils import utc_now

# Enum imports removed - using Any for priority field flexibility


@runtime_checkable
class ProcessableJob(Protocol):
    """Protocol for jobs that can be processed in batches."""

    id: int
    priority: Any  # Allow any priority type - will be handled by specific workers
    retry_count: int


# Generic type variable for job types
T = TypeVar("T", bound=ProcessableJob)


class JobBatchProcessor(Generic[T]):
    """
    Manages batch processing of jobs with concurrency control and performance monitoring.

    This class eliminates the duplicated job processing logic found in both
    ThumbnailWorker and OverlayWorker, providing consistent batch processing
    with adaptive performance features.

    Features:
    - Configurable batch sizes with adaptive scaling
    - Concurrent job processing with semaphore throttling
    - Performance monitoring and metrics collection
    - Queue load-based optimization
    - Comprehensive error handling and recovery
    """

    def __init__(
        self,
        worker_name: str,
        default_batch_size: int = 5,
        max_concurrent_jobs: int = 3,
        high_load_batch_size: int = 15,
        high_load_threshold: int = 20,
        low_load_threshold: int = 5,
        performance_check_interval: int = 60,  # seconds
    ):
        """
        Initialize job batch processor.

        Args:
            worker_name: Name of the worker for logging
            default_batch_size: Default number of jobs to process per batch
            max_concurrent_jobs: Maximum concurrent jobs within a batch
            high_load_batch_size: Batch size to use during high load periods
            high_load_threshold: Queue size threshold to trigger high load mode
            low_load_threshold: Queue size threshold to return to normal mode
            performance_check_interval: Seconds between performance evaluations
        """
        self.worker_name = worker_name
        self.default_batch_size = default_batch_size
        self.max_concurrent_jobs = max_concurrent_jobs
        self.high_load_batch_size = high_load_batch_size
        self.high_load_threshold = high_load_threshold
        self.low_load_threshold = low_load_threshold
        self.performance_check_interval = performance_check_interval

        # Performance tracking
        self.high_load_mode = False
        self.current_batch_size = default_batch_size
        self.processed_jobs_count = 0
        self.failed_jobs_count = 0
        self.total_processing_time_ms = 0
        self.processing_times: List[float] = []
        self.last_performance_check = utc_now()

        # Concurrency control - will be initialized when needed
        self.concurrent_jobs_semaphore: Optional[asyncio.Semaphore] = None
        self._max_concurrent_jobs = max_concurrent_jobs

        # Statistics
        self.batch_count = 0
        self.empty_batch_count = 0

    def _ensure_semaphore(self) -> asyncio.Semaphore:
        """Ensure semaphore is initialized for current event loop."""
        if self.concurrent_jobs_semaphore is None:
            self.concurrent_jobs_semaphore = asyncio.Semaphore(
                self._max_concurrent_jobs
            )
        return self.concurrent_jobs_semaphore

    async def process_job_batch(
        self,
        get_pending_jobs: Callable[[int], Sequence[T]],
        process_single_job: Callable[[T], bool],
        get_queue_stats: Optional[Callable[[], Dict[str, int]]] = None,
    ) -> int:
        """
        Process a batch of pending jobs with adaptive performance scaling.

        Args:
            get_pending_jobs: Function to retrieve pending jobs (takes batch_size)
            process_single_job: Function to process a single job (returns success bool)
            get_queue_stats: Optional function to get current queue statistics

        Returns:
            Number of jobs successfully processed in this batch
        """
        try:
            # Check and adjust performance settings
            if get_queue_stats:
                await self._adaptive_performance_scaling(get_queue_stats)

            # Get pending jobs from queue (priority-ordered)
            pending_jobs = get_pending_jobs(self.current_batch_size)

            if not pending_jobs:
                self.empty_batch_count += 1
                return 0

            self.batch_count += 1
            batch_start_time = time.time()

            logger.debug(
                f"[{self.worker_name}] Processing batch of {len(pending_jobs)} jobs "
                f"(high_load_mode={self.high_load_mode})"
            )

            processed_count = 0

            # Process jobs concurrently with semaphore limit
            if len(pending_jobs) <= self._max_concurrent_jobs:
                # Small batch - process all concurrently
                processed_count = await self._process_concurrent_batch(
                    pending_jobs, process_single_job
                )
            else:
                # Large batch - process in smaller concurrent chunks
                processed_count = await self._process_chunked_batch(
                    pending_jobs, process_single_job
                )

            # Update performance metrics
            batch_time = time.time() - batch_start_time
            self._update_batch_metrics(batch_time, len(pending_jobs), processed_count)

            logger.debug(
                f"[{self.worker_name}] Completed batch: {processed_count}/{len(pending_jobs)} "
                f"successful in {batch_time:.2f}s"
            )

            return processed_count

        except Exception as e:
            logger.error(f"[{self.worker_name}] Error in job batch processing: {e}")
            return 0

    async def _process_concurrent_batch(
        self,
        jobs: Sequence[T],
        process_single_job: Callable[[T], bool],
    ) -> int:
        """
        Process a small batch of jobs concurrently.

        Args:
            jobs: List of jobs to process
            process_single_job: Function to process individual jobs

        Returns:
            Number of jobs processed successfully
        """
        tasks = []
        for job in jobs:
            task = asyncio.create_task(
                self._process_job_with_semaphore(job, process_single_job)
            )
            tasks.append(task)

        # Wait for all jobs to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for result in results if result is True)

    async def _process_chunked_batch(
        self,
        jobs: Sequence[T],
        process_single_job: Callable[[T], bool],
    ) -> int:
        """
        Process a large batch of jobs in smaller concurrent chunks.

        Args:
            jobs: List of jobs to process
            process_single_job: Function to process individual jobs

        Returns:
            Number of jobs processed successfully
        """
        processed_count = 0

        for i in range(0, len(jobs), self._max_concurrent_jobs):
            chunk = jobs[i : i + self._max_concurrent_jobs]
            tasks = []

            for job in chunk:
                task = asyncio.create_task(
                    self._process_job_with_semaphore(job, process_single_job)
                )
                tasks.append(task)

            # Wait for chunk to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            processed_count += sum(1 for result in results if result is True)

        return processed_count

    async def _process_job_with_semaphore(
        self, job: T, process_single_job: Callable[[T], bool]
    ) -> bool:
        """
        Process a single job with concurrency control via semaphore.

        Args:
            job: Job to process
            process_single_job: Function to process the job

        Returns:
            True if job completed successfully, False otherwise
        """
        async with self._ensure_semaphore():
            try:
                job_start_time = time.time()
                success = await asyncio.get_event_loop().run_in_executor(
                    None, process_single_job, job
                )

                # Track individual job performance
                job_time = time.time() - job_start_time
                if success:
                    self.processed_jobs_count += 1
                    self.total_processing_time_ms += int(job_time * 1000)
                else:
                    self.failed_jobs_count += 1

                return success

            except Exception as e:
                logger.error(
                    f"[{self.worker_name}] Error processing job {job.id} in semaphore: {e}"
                )
                self.failed_jobs_count += 1
                return False

    async def _adaptive_performance_scaling(
        self, get_queue_stats: Callable[[], Dict[str, int]]
    ) -> None:
        """
        Dynamically adjust batch processing performance based on queue load.

        Args:
            get_queue_stats: Function to get current queue statistics
        """
        try:
            # Check queue size periodically
            now = utc_now()
            if (
                now - self.last_performance_check
            ).total_seconds() < self.performance_check_interval:
                return

            self.last_performance_check = now

            # Get current queue statistics
            queue_stats = get_queue_stats()
            pending_count = queue_stats.get("pending_jobs", 0)
            processing_count = queue_stats.get("processing_jobs", 0)
            total_active = pending_count + processing_count

            # Determine if we should switch modes
            should_be_high_load = total_active >= self.high_load_threshold
            should_be_normal_load = total_active <= self.low_load_threshold

            # Switch to high load mode
            if should_be_high_load and not self.high_load_mode:
                self.high_load_mode = True
                self.current_batch_size = self.high_load_batch_size
                logger.info(
                    f"[{self.worker_name}] Switched to HIGH LOAD mode: {total_active} jobs in queue"
                )

            # Switch back to normal mode
            elif should_be_normal_load and self.high_load_mode:
                self.high_load_mode = False
                self.current_batch_size = self.default_batch_size
                logger.info(
                    f"[{self.worker_name}] Switched to NORMAL mode: {total_active} jobs in queue"
                )

            # No return value needed

        except Exception as e:
            logger.error(
                f"[{self.worker_name}] Error in adaptive performance scaling: {e}"
            )

    def _update_batch_metrics(
        self, batch_time: float, total_jobs: int, successful_jobs: int
    ) -> None:
        """
        Update batch processing metrics.

        Args:
            batch_time: Time taken to process the batch
            total_jobs: Total number of jobs in the batch
            successful_jobs: Number of successfully processed jobs
        """
        self.processing_times.append(batch_time)

        # Keep only last 10 measurements for rolling average
        if len(self.processing_times) > 10:
            self.processing_times = self.processing_times[-10:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get current performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        avg_batch_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times
            else 0
        )

        avg_job_time = (
            self.total_processing_time_ms / self.processed_jobs_count
            if self.processed_jobs_count > 0
            else 0
        )

        success_rate = (
            (
                self.processed_jobs_count
                / (self.processed_jobs_count + self.failed_jobs_count)
            )
            * 100
            if (self.processed_jobs_count + self.failed_jobs_count) > 0
            else 0
        )

        return {
            "worker_name": self.worker_name,
            "high_load_mode": self.high_load_mode,
            "current_batch_size": self.current_batch_size,
            "processed_jobs_total": self.processed_jobs_count,
            "failed_jobs_total": self.failed_jobs_count,
            "success_rate_percent": round(success_rate, 2),
            "avg_batch_time_seconds": round(avg_batch_time, 2),
            "avg_job_time_ms": round(avg_job_time, 2),
            "batch_count": self.batch_count,
            "empty_batch_count": self.empty_batch_count,
            "concurrency_limit": self._max_concurrent_jobs,
            "performance_thresholds": {
                "high_load_threshold": self.high_load_threshold,
                "low_load_threshold": self.low_load_threshold,
                "high_load_batch_size": self.high_load_batch_size,
                "default_batch_size": self.default_batch_size,
            },
        }

    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self.processed_jobs_count = 0
        self.failed_jobs_count = 0
        self.total_processing_time_ms = 0
        self.processing_times.clear()
        self.batch_count = 0
        self.empty_batch_count = 0

    def __repr__(self) -> str:
        """String representation of job batch processor."""
        return (
            f"JobBatchProcessor(worker='{self.worker_name}', "
            f"batch_size={self.current_batch_size}, "
            f"high_load_mode={self.high_load_mode}, "
            f"processed={self.processed_jobs_count})"
        )
