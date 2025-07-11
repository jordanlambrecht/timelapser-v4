# backend/app/workers/thumbnail_worker.py
"""
Thumbnail Worker for background thumbnail generation processing.

Handles:
- Background processing of thumbnail generation jobs
- Priority-based job queue processing
- Retry logic with exponential backoff
- Job status updates and error handling
- Integration with existing ThumbnailService for actual generation
"""

import asyncio
import time
from typing import Optional, List
from datetime import datetime, timedelta

from .base_worker import BaseWorker
from ..utils.timezone_utils import utc_now
from ..services.thumbnail_job_service import SyncThumbnailJobService
from ..services.thumbnail_service import ThumbnailService
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..models.shared_models import ThumbnailGenerationJob, ThumbnailGenerationResult
from ..constants import (
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_STATUS_PROCESSING,
    THUMBNAIL_JOB_STATUS_COMPLETED,
    THUMBNAIL_JOB_STATUS_FAILED,
    THUMBNAIL_JOB_PRIORITY_HIGH,
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_PRIORITY_LOW,
    SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE,
    THUMBNAIL_GENERATION_MODE_ALL,
    SETTING_KEY_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION,
    DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
    DEFAULT_THUMBNAIL_WORKER_INTERVAL,
    DEFAULT_THUMBNAIL_MAX_RETRIES,
    DEFAULT_THUMBNAIL_CLEANUP_HOURS,
    THUMBNAIL_JOB_RETRY_DELAYS,
    HIGH_LOAD_THUMBNAIL_JOB_BATCH_SIZE,
    HIGH_LOAD_THUMBNAIL_WORKER_INTERVAL,
    THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD,
    THUMBNAIL_QUEUE_SIZE_LOW_THRESHOLD,
    THUMBNAIL_PROCESSING_TIME_WARNING_MS,
    THUMBNAIL_MEMORY_WARNING_THRESHOLD,
    THUMBNAIL_CONCURRENT_JOBS,
)


class ThumbnailWorker(BaseWorker):
    """
    High-performance background worker for thumbnail generation job processing.

    The ThumbnailWorker implements a sophisticated job processing pipeline that
    decouples thumbnail generation from the critical RTSP capture workflow,
    ensuring that thumbnail processing never impacts capture timing or reliability.

    Core Responsibilities:
    - Priority-based job queue processing (high > medium > low)
    - Concurrent thumbnail generation with configurable limits
    - Adaptive performance scaling based on queue load
    - Comprehensive retry logic with exponential backoff
    - Real-time progress broadcasting via SSE events
    - Automatic cleanup of completed jobs
    - Performance monitoring and statistics collection

    Adaptive Performance Features:
    - Switches between normal and high-load processing modes
    - Adjusts batch sizes dynamically (5 → 15 jobs)
    - Modifies polling intervals for optimal throughput
    - Concurrent processing with semaphore-based throttling

    Integration Architecture:
    - Integrates with existing ThumbnailService infrastructure
    - Coordinates with CaptureWorker via job queuing
    - Updates timelapse thumbnail counts in real-time
    - Broadcasts job lifecycle events for frontend updates

    Error Handling:
    - Maximum 3 retry attempts with exponential backoff (30s, 2min, 5min)
    - Graceful degradation on thumbnail generation failures
    - Detailed error logging with job context
    - Automatic job cleanup to prevent queue bloat

    Performance Characteristics:
    - Processes 5-15 jobs per batch depending on load
    - 10-second polling in normal mode, 3-second in high-load
    - Concurrent processing up to THUMBNAIL_CONCURRENT_JOBS limit
    - Hourly cleanup of completed jobs older than 24 hours

    Monitoring Integration:
    - Real-time job statistics via get_worker_stats()
    - Performance metrics with processing time tracking
    - Queue size monitoring with threshold-based scaling
    - SSE event broadcasting for frontend visibility
    """

    def __init__(
        self,
        thumbnail_job_service: SyncThumbnailJobService,
        thumbnail_service: ThumbnailService,
        sse_ops: SyncSSEEventsOperations,
        batch_size: int = DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
        worker_interval: int = DEFAULT_THUMBNAIL_WORKER_INTERVAL,
        max_retries: int = DEFAULT_THUMBNAIL_MAX_RETRIES,
        cleanup_hours: int = DEFAULT_THUMBNAIL_CLEANUP_HOURS,
    ):
        """
        Initialize ThumbnailWorker with dependencies.

        Args:
            thumbnail_job_service: Service for job queue operations
            thumbnail_service: Service for thumbnail generation
            sse_ops: SSE operations for progress broadcasting
            batch_size: Number of jobs to process per batch
            worker_interval: Seconds between job queue polling
            max_retries: Maximum retry attempts for failed jobs
            cleanup_hours: Hours to keep completed jobs before cleanup
        """
        super().__init__("ThumbnailWorker")
        self.thumbnail_job_service = thumbnail_job_service
        self.thumbnail_service = thumbnail_service
        self.sse_ops = sse_ops
        self.batch_size = batch_size
        self.worker_interval = worker_interval
        self.max_retries = max_retries
        self.cleanup_hours = cleanup_hours

        # Worker state
        self.processing_job_id: Optional[int] = None
        self.last_cleanup_time = utc_now()

        # Performance monitoring
        self.high_load_mode = False
        self.processed_jobs_count = 0
        self.total_processing_time_ms = 0
        self.last_performance_check = utc_now()
        self.concurrent_jobs_semaphore = asyncio.Semaphore(THUMBNAIL_CONCURRENT_JOBS)

    async def initialize(self) -> None:
        """Initialize thumbnail worker resources."""
        self.log_info(
            f"Initialized with batch_size={self.batch_size}, interval={self.worker_interval}s"
        )

        # Broadcast worker startup event
        await self.run_in_executor(
            self.sse_ops.create_event,
            "thumbnail_worker_started",
            {
                "worker_name": self.name,
                "batch_size": self.batch_size,
                "worker_interval": self.worker_interval,
                "max_retries": self.max_retries,
            },
            "normal",
            "worker",
        )

    async def cleanup(self) -> None:
        """Cleanup thumbnail worker resources."""
        self.log_info("Cleaned up thumbnail worker")

        # Broadcast worker shutdown event
        await self.run_in_executor(
            self.sse_ops.create_event,
            "thumbnail_worker_stopped",
            {
                "worker_name": self.name,
                "last_processed_job": self.processing_job_id,
            },
            "normal",
            "worker",
        )

    async def run(self) -> None:
        """
        Main worker loop - processes jobs continuously while running.

        This method should be called after start() to begin job processing.
        """
        self.log_info("Starting thumbnail worker main loop")

        while self.running:
            try:
                # Check and adjust performance settings
                await self.adaptive_performance_scaling()

                # Process a batch of jobs
                processed_count = await self.process_job_batch()

                # Perform periodic cleanup if needed
                await self.periodic_cleanup()

                # Log activity if jobs were processed
                if processed_count > 0:
                    self.log_debug(
                        f"Processed {processed_count} jobs in this batch (high_load_mode={self.high_load_mode})"
                    )

                # Dynamic interval based on load
                current_interval = (
                    HIGH_LOAD_THUMBNAIL_WORKER_INTERVAL
                    if self.high_load_mode
                    else self.worker_interval
                )
                await asyncio.sleep(current_interval)

            except Exception as e:
                self.log_error("Error in thumbnail worker main loop", e)

                # Broadcast error event
                await self.run_in_executor(
                    self.sse_ops.create_event,
                    "thumbnail_worker_error",
                    {
                        "worker_name": self.name,
                        "error": str(e),
                        "processing_job_id": self.processing_job_id,
                    },
                    "high",
                    "worker",
                )

                # Wait before retrying to avoid tight error loops
                await asyncio.sleep(5)

    async def adaptive_performance_scaling(self) -> None:
        """
        Dynamically adjust worker performance based on queue load.

        Switches between normal and high-load mode based on queue size
        and broadcasts performance metrics via SSE events.
        """
        try:
            # Check queue size every minute
            now = utc_now()
            if (now - self.last_performance_check).total_seconds() < 60:
                return

            self.last_performance_check = now

            # Get current queue statistics
            queue_stats = await self.run_in_executor(
                self.thumbnail_job_service.get_job_statistics
            )

            pending_count = queue_stats.get("pending_jobs", 0)
            processing_count = queue_stats.get("processing_jobs", 0)
            total_active = pending_count + processing_count

            # Determine if we should switch modes
            should_be_high_load = total_active >= THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD
            should_be_normal_load = total_active <= THUMBNAIL_QUEUE_SIZE_LOW_THRESHOLD

            mode_changed = False

            # Switch to high load mode
            if should_be_high_load and not self.high_load_mode:
                self.high_load_mode = True
                self.batch_size = HIGH_LOAD_THUMBNAIL_JOB_BATCH_SIZE
                mode_changed = True
                self.log_info(
                    f"Switched to HIGH LOAD mode: {total_active} jobs in queue"
                )

            # Switch back to normal mode
            elif should_be_normal_load and self.high_load_mode:
                self.high_load_mode = False
                self.batch_size = DEFAULT_THUMBNAIL_JOB_BATCH_SIZE
                mode_changed = True
                self.log_info(f"Switched to NORMAL mode: {total_active} jobs in queue")

            # Calculate performance metrics
            avg_processing_time = 0
            if self.processed_jobs_count > 0:
                avg_processing_time = (
                    self.total_processing_time_ms / self.processed_jobs_count
                )

            # Broadcast performance update if mode changed or every 5 minutes
            if mode_changed or (now.minute % 5 == 0 and now.second < 60):
                await self.run_in_executor(
                    self.sse_ops.create_event,
                    "thumbnail_worker_performance",
                    {
                        "worker_name": self.name,
                        "high_load_mode": self.high_load_mode,
                        "current_batch_size": self.batch_size,
                        "queue_size": total_active,
                        "pending_jobs": pending_count,
                        "processing_jobs": processing_count,
                        "processed_jobs_total": self.processed_jobs_count,
                        "avg_processing_time_ms": round(avg_processing_time, 2),
                        "performance_threshold_high": THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD,
                        "performance_threshold_low": THUMBNAIL_QUEUE_SIZE_LOW_THRESHOLD,
                    },
                    "low",
                    "thumbnail_worker",
                )

        except Exception as e:
            self.log_error("Error in adaptive performance scaling", e)

    async def process_job_batch(self) -> int:
        """
        Process a batch of pending jobs.

        Returns:
            Number of jobs processed in this batch
        """
        try:
            # Get pending jobs from queue (priority-ordered)
            pending_jobs = await self.run_in_executor(
                self.thumbnail_job_service.get_pending_jobs, self.batch_size
            )

            if not pending_jobs:
                return 0

            processed_count = 0

            # Process jobs concurrently with semaphore limit
            if len(pending_jobs) <= THUMBNAIL_CONCURRENT_JOBS:
                # Small batch - process concurrently
                tasks = []
                for job in pending_jobs:
                    task = asyncio.create_task(self._process_job_with_semaphore(job))
                    tasks.append(task)

                # Wait for all jobs to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                processed_count = sum(1 for result in results if result is True)

            else:
                # Large batch - process in smaller concurrent chunks
                for i in range(0, len(pending_jobs), THUMBNAIL_CONCURRENT_JOBS):
                    if not self.running:
                        break

                    chunk = pending_jobs[i : i + THUMBNAIL_CONCURRENT_JOBS]
                    tasks = []
                    for job in chunk:
                        task = asyncio.create_task(
                            self._process_job_with_semaphore(job)
                        )
                        tasks.append(task)

                    # Wait for chunk to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    processed_count += sum(1 for result in results if result is True)

            return processed_count

        except Exception as e:
            self.log_error("Error processing job batch", e)
            return 0

    async def _process_job_with_semaphore(self, job: ThumbnailGenerationJob) -> bool:
        """
        Process a single job with concurrency control via semaphore.

        Args:
            job: Job to process

        Returns:
            True if job completed successfully, False otherwise
        """
        async with self.concurrent_jobs_semaphore:
            try:
                success = await self.process_single_job(job)
                return success
            except Exception as e:
                self.log_error(f"Error processing job {job.id} in semaphore", e)

                # Mark job as failed
                try:
                    await self.run_in_executor(
                        self.thumbnail_job_service.mark_job_failed,
                        job.id,
                        str(e),
                        job.retry_count,
                    )
                except Exception as db_error:
                    self.log_error(f"Failed to mark job {job.id} as failed", db_error)

                return False

    async def process_single_job(self, job: ThumbnailGenerationJob) -> bool:
        """
        Process a single thumbnail generation job.

        Args:
            job: Job to process

        Returns:
            True if job completed successfully, False otherwise
        """
        self.processing_job_id = job.id
        start_time = time.time()

        try:
            self.log_debug(
                f"Processing job {job.id} for image {job.image_id} (priority: {job.priority})"
            )

            # Mark job as started
            await self.run_in_executor(
                self.thumbnail_job_service.mark_job_started, job.id
            )

            # Broadcast job start event
            await self.run_in_executor(
                self.sse_ops.create_event,
                "thumbnail_job_started",
                {
                    "job_id": job.id,
                    "image_id": job.image_id,
                    "priority": job.priority,
                    "retry_count": job.retry_count,
                },
                "normal",
                "thumbnail_worker",
            )

            # Generate thumbnails using utility functions directly
            result = await self._generate_thumbnails_for_job(job)

            processing_time_ms = int((time.time() - start_time) * 1000)

            if result.success:
                # Mark job as completed
                await self.run_in_executor(
                    self.thumbnail_job_service.mark_job_completed,
                    job.id,
                    processing_time_ms,
                )

                # Update thumbnail counts in timelapse table if timelapse_id exists
                if result.timelapse_id:
                    increment_thumbnail = bool(result.thumbnail_path)
                    increment_small = bool(result.small_path)

                    if increment_thumbnail or increment_small:
                        from ..database.timelapse_operations import (
                            SyncTimelapseOperations,
                        )

                        timelapse_ops = SyncTimelapseOperations(
                            self.thumbnail_job_service.sync_db
                        )

                        # Update counts synchronously in worker
                        success = timelapse_ops.increment_thumbnail_counts_sync(
                            result.timelapse_id,
                            increment_thumbnail=increment_thumbnail,
                            increment_small=increment_small,
                        )

                        if success:
                            self.log_debug(
                                f"Updated thumbnail counts for timelapse {result.timelapse_id}"
                            )
                        else:
                            self.log_warning(
                                f"Failed to update thumbnail counts for timelapse {result.timelapse_id}"
                            )

                # Broadcast success event
                await self.run_in_executor(
                    self.sse_ops.create_event,
                    "thumbnail_job_completed",
                    {
                        "job_id": job.id,
                        "image_id": job.image_id,
                        "thumbnail_path": result.thumbnail_path,
                        "small_path": result.small_path,
                        "processing_time_ms": processing_time_ms,
                        "timelapse_id": result.timelapse_id,
                    },
                    "normal",
                    "thumbnail_worker",
                )

                # Update performance metrics
                self.processed_jobs_count += 1
                self.total_processing_time_ms += processing_time_ms

                # Log slow processing as warning
                if processing_time_ms > THUMBNAIL_PROCESSING_TIME_WARNING_MS:
                    self.log_warning(
                        f"Slow thumbnail processing detected: job {job.id} took {processing_time_ms}ms"
                    )

                self.log_debug(
                    f"Successfully completed job {job.id} in {processing_time_ms}ms"
                )
                return True

            else:
                # Job failed - handle retry logic
                error_msg = result.error or "Unknown error occurred"
                return await self.handle_job_failure(job, error_msg)

        except Exception as e:
            self.log_error(f"Exception processing job {job.id}", e)
            return await self.handle_job_failure(job, str(e))

        finally:
            self.processing_job_id = None

    async def handle_job_failure(
        self, job: ThumbnailGenerationJob, error_message: str
    ) -> bool:
        """
        Handle job failure with retry logic.

        Args:
            job: Failed job
            error_message: Error description

        Returns:
            True if job was scheduled for retry, False if permanently failed
        """
        retry_count = job.retry_count + 1

        if retry_count <= self.max_retries:
            # Schedule retry with exponential backoff
            delay_index = min(retry_count - 1, len(THUMBNAIL_JOB_RETRY_DELAYS) - 1)
            delay_minutes = THUMBNAIL_JOB_RETRY_DELAYS[delay_index]

            # Schedule retry with exponential backoff
            await self.run_in_executor(
                self.thumbnail_job_service.schedule_retry,
                job.id,
                retry_count,
                delay_minutes,
            )

            # Broadcast retry event
            await self.run_in_executor(
                self.sse_ops.create_event,
                "thumbnail_job_retry_scheduled",
                {
                    "job_id": job.id,
                    "image_id": job.image_id,
                    "retry_count": retry_count,
                    "delay_minutes": delay_minutes,
                    "error": error_message,
                },
                "normal",
                "thumbnail_worker",
            )

            self.log_info(
                f"Scheduled retry {retry_count}/{self.max_retries} for job {job.id} (delay: {delay_minutes}min)"
            )
            return True

        else:
            # Max retries exceeded - mark as permanently failed
            await self.run_in_executor(
                self.thumbnail_job_service.mark_job_failed,
                job.id,
                f"Max retries exceeded: {error_message}",
                retry_count,
            )

            # Broadcast permanent failure event
            await self.run_in_executor(
                self.sse_ops.create_event,
                "thumbnail_job_failed_permanently",
                {
                    "job_id": job.id,
                    "image_id": job.image_id,
                    "final_error": error_message,
                    "retry_count": retry_count,
                },
                "normal",
                "thumbnail_worker",
            )

            self.log_warning(
                f"Job {job.id} failed permanently after {retry_count} retries: {error_message}"
            )
            return False

    async def periodic_cleanup(self) -> None:
        """
        Perform periodic cleanup of old completed jobs.

        Runs cleanup every hour to avoid excessive database operations.
        """
        now = utc_now()

        # Only run cleanup once per hour
        if (now - self.last_cleanup_time).total_seconds() < 3600:
            return

        try:
            self.log_debug("Running periodic job cleanup")

            # Cleanup completed jobs older than configured hours
            cleaned_count = await self.run_in_executor(
                self.thumbnail_job_service.cleanup_completed_jobs, self.cleanup_hours
            )

            if cleaned_count > 0:
                self.log_info(f"Cleaned up {cleaned_count} old completed jobs")

                # Broadcast cleanup event
                await self.run_in_executor(
                    self.sse_ops.create_event,
                    "thumbnail_jobs_cleaned_up",
                    {
                        "worker_name": self.name,
                        "cleaned_count": cleaned_count,
                        "older_than_hours": self.cleanup_hours,
                    },
                    "low",
                    "thumbnail_worker",
                )

            self.last_cleanup_time = now

        except Exception as e:
            self.log_error("Error during periodic cleanup", e)

    async def get_worker_stats(self) -> dict:
        """
        Get current worker statistics for monitoring.

        Returns:
            Dictionary with worker status and job queue statistics
        """
        try:
            job_stats = await self.run_in_executor(
                self.thumbnail_job_service.get_job_statistics
            )

            return {
                "worker_name": self.name,
                "worker_running": self.running,
                "processing_job_id": self.processing_job_id,
                "batch_size": self.batch_size,
                "worker_interval": self.worker_interval,
                "max_retries": self.max_retries,
                "last_cleanup": self.last_cleanup_time.isoformat(),
                "job_statistics": job_stats,
            }

        except Exception as e:
            self.log_error("Error getting worker stats", e)
            return {
                "worker_name": self.name,
                "worker_running": self.running,
                "error": str(e),
            }

    async def _generate_thumbnails_for_job(self, job: ThumbnailGenerationJob):
        """
        Generate thumbnail variants for a specific image using the timelapse-based file structure.

        This method implements the core thumbnail generation logic, integrating with the
        existing thumbnail utilities while maintaining proper error handling and database
        consistency. It supports both legacy images (without timelapse_id) and new
        timelapse-organized images.

        Process Flow:
        1. Retrieve image metadata from database using job.image_id
        2. Validate image file exists on filesystem
        3. Generate thumbnail variants using existing utilities
        4. Update database with new thumbnail paths
        5. Return comprehensive result for job status updates

        File Structure Integration:
        - Uses timelapse-based directory organization when available
        - Falls back to legacy structure for older images
        - Generates both 200x150 thumbnails and 800x600 small images
        - Respects user settings for small image generation mode

        Error Handling:
        - Validates image existence before processing
        - Handles missing settings service gracefully
        - Returns detailed error messages for debugging
        - Maintains database consistency on failures

        Args:
            job: ThumbnailGenerationJob containing image_id and processing context

        Returns:
            ThumbnailGenerationResult containing:
            - success: Boolean indicating overall operation success
            - image_id: Original image ID for tracking
            - timelapse_id: Associated timelapse (if available)
            - thumbnail_path: Relative path to generated thumbnail
            - small_path: Relative path to generated small image
            - error: Detailed error message if generation failed
            - message: Success message with generation details

        Raises:
            Exception: Propagated from utility functions for logging purposes

        Performance Notes:
        - Database operations are synchronous to match worker context
        - File operations are executed in thread pool for non-blocking processing
        - Thumbnail paths are stored as relative paths for portability
        """
        try:
            # Import here to avoid circular dependencies. Don't move to top
            from ..database.image_operations import SyncImageOperations
            from ..utils.thumbnail_utils import generate_thumbnails_for_timelapse_image
            from pathlib import Path

            # Get image details from database
            image_ops = SyncImageOperations(self.thumbnail_job_service.sync_db)
            image = image_ops.get_image_by_id(job.image_id)

            if not image:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=job.image_id,
                    timelapse_id=None,
                    error=f"Image {job.image_id} not found in database",
                )

            # Get data directory from settings with null safety
            if not self.thumbnail_job_service.settings_service:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=job.image_id,
                    timelapse_id=None,
                    error="Settings service not available",
                )

            data_directory = self.thumbnail_job_service.settings_service.get_setting(
                "data_directory"
            )

            if not data_directory:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=job.image_id,
                    timelapse_id=None,
                    error="Data directory setting not configured",
                )

            # Construct full image path
            image_path = Path(data_directory) / image.file_path

            if not image_path.exists():
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=job.image_id,
                    timelapse_id=getattr(image, "timelapse_id", None),
                    error=f"Image file not found: {image_path}",
                )

            # Get thumbnail generation settings
            small_generation_mode = (
                self.thumbnail_job_service.settings_service.get_setting(
                    SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE,
                    THUMBNAIL_GENERATION_MODE_ALL,
                )
            )

            # Check if this is the latest image for "latest" mode
            # For now, we'll assume all images could be latest (this could be optimized)
            is_latest_image = True  # TODO: Implement proper latest image detection

            # Generate thumbnails using new timelapse-based structure
            # Handle both legacy (no timelapse_id) and new (with timelapse_id) images
            timelapse_id = getattr(image, "timelapse_id", None)
            results = await self.run_in_executor(
                generate_thumbnails_for_timelapse_image,
                image_path,
                image.camera_id,
                timelapse_id,
                None,  # filename_override
                small_generation_mode,
                is_latest_image,
            )

            # Check if generation was successful
            if results.get("thumbnail") or results.get("small"):
                # Update database with thumbnail paths - handle None values safely
                thumbnail_result = results.get("thumbnail")
                small_result = results.get("small")
                
                thumbnail_path = thumbnail_result[0] if thumbnail_result else None
                small_path = small_result[0] if small_result else None

                image_ops.update_image_thumbnail_paths(
                    job.image_id, thumbnail_path, small_path
                )

                return ThumbnailGenerationResult(
                    success=True,
                    image_id=job.image_id,
                    timelapse_id=timelapse_id,
                    thumbnail_path=thumbnail_path,
                    small_path=small_path,
                )
            else:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=job.image_id,
                    timelapse_id=timelapse_id,
                    error="Failed to generate thumbnails",
                )

        except Exception as e:
            self.log_error(f"Error generating thumbnails for job {job.id}", e)
            return ThumbnailGenerationResult(
                success=False,
                image_id=job.image_id,
                timelapse_id=None,  # Unknown due to error
                error=str(e),
            )
