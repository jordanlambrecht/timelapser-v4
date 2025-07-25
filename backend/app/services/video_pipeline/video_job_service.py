# backend/app/services/video_pipeline/video_job_service.py
"""
Video Job Service - Simplified Job Management

Consolidates job coordination, queue management, and lifecycle.
Replaces separate JobCoordinationService with integrated functionality.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from ...enums import JobPriority, JobStatus, SSEPriority, SSEEvent, SSEEventSource
from ...constants import JOB_PRIORITY, JOB_STATUS, JOB_PRIORITIES_LIST

from ...database.core import SyncDatabase
from ...database.video_operations import SyncVideoOperations
from ...database.timelapse_operations import SyncTimelapseOperations
from ...database.sse_events_operations import SyncSSEEventsOperations
from ...models.shared_models import (
    VideoGenerationJob,
    VideoGenerationJobWithDetails,
    VideoGenerationJobCreate,
)
from ...utils.time_utils import get_timezone_aware_timestamp_sync
from .constants import (
    DEFAULT_VIDEO_JOB_PRIORITY,
    DEFAULT_VIDEO_CLEANUP_DAYS,
)
from .utils import (
    validate_trigger_type,
    validate_job_status,
    create_video_job_metadata,
    format_video_job_name,
)


class VideoJobService:
    """
    Simplified video job management service.

    Consolidates job coordination, queue management, and lifecycle:
    - Job creation and queuing with priority
    - Job lifecycle management (pending → processing → completed/failed)
    - SSE event broadcasting
    - Queue status and statistics
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize VideoJobService with database dependency.

        Args:
            db: SyncDatabase instance for database operations
        """
        self.db = db
        self.video_ops = SyncVideoOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)

        logger.debug("VideoJobService initialized with simplified architecture")

    def create_job(
        self,
        timelapse_id: int,
        trigger_type: str,
        priority: str = DEFAULT_VIDEO_JOB_PRIORITY,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Create a new video generation job.

        Args:
            timelapse_id: ID of the timelapse to generate video for
            trigger_type: Type of trigger (manual, per_capture, scheduled, milestone)
            priority: Job priority (low, medium, high)
            settings: Optional job-specific settings

        Returns:
            Created job ID or None if failed
        """
        try:
            logger.debug(
                f"Creating video job for timelapse {timelapse_id}, trigger: {trigger_type}"
            )

            # Validate inputs
            if not validate_trigger_type(trigger_type):
                logger.error(f"Invalid trigger type: {trigger_type}")
                return None

            if priority not in JOB_PRIORITIES_LIST:
                logger.error(f"Invalid priority: {priority}")
                return None

            # Get timelapse info with error handling
            try:
                timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
                if not timelapse:
                    logger.error(f"Timelapse {timelapse_id} not found")
                    return None
            except Exception as e:
                logger.error(f"Database error retrieving timelapse {timelapse_id}: {e}")
                return None

            # Create job metadata
            job_metadata = create_video_job_metadata(
                timelapse_id=timelapse_id,
                trigger_type=trigger_type,
                settings=settings or {},
                estimated_duration=60,  # Default 1 minute
            )

            # Create job record
            job_data = {
                "timelapse_id": timelapse_id,
                "trigger_type": trigger_type,
                "priority": priority,
                "status": JOB_STATUS.PENDING,
                "settings": json.dumps(settings or {}),
                "metadata": json.dumps(job_metadata),
                "created_at": get_timezone_aware_timestamp_sync(self.db),
            }

            try:
                job_id = self.video_ops.create_video_generation_job(job_data)
                if not job_id:
                    logger.error(f"Failed to create video generation job in database")
                    return None
            except Exception as e:
                logger.error(f"Database error creating video generation job: {e}")
                return None

            if job_id:
                # Broadcast SSE event
                self._broadcast_job_event(
                    event_type=SSEEvent.VIDEO_JOB_QUEUED,
                    job_id=job_id,
                    timelapse_id=timelapse_id,
                    extra_data={"trigger_type": trigger_type, "priority": priority},
                )

                logger.info(f"Created video job {job_id} for timelapse {timelapse_id}")
                return job_id

            return None

        except Exception as e:
            logger.error(f"Failed to create video job: {e}")
            return None

    def get_next_pending_job(self) -> Optional[VideoGenerationJobWithDetails]:
        """
        Get the next pending job from the queue using priority-based algorithm.

        Priority Processing Order:
        1. All HIGH priority jobs (oldest first within priority)
        2. All MEDIUM priority jobs (oldest first within priority)  
        3. All LOW priority jobs (oldest first within priority)

        Returns:
            Next pending job or None if queue is empty
        """
        try:
            logger.debug("Getting next pending job from priority queue")

            # Get all pending jobs with error handling
            try:
                pending_jobs = self.video_ops.get_pending_video_generation_jobs()
                if pending_jobs is None:
                    logger.error("Failed to retrieve pending jobs from database")
                    return None
            except Exception as e:
                logger.error(f"Database error retrieving pending jobs: {e}")
                return None

            if not pending_jobs:
                logger.debug("No pending jobs in queue")
                return None

            # Priority-based sorting algorithm
            priority_order = {
                JobPriority.HIGH: 1,      # Immediate/per-capture automation
                JobPriority.MEDIUM: 2,    # Milestone-triggered videos
                JobPriority.LOW: 3,       # Scheduled automation videos
            }

            # Sort by priority first, then by creation time (FIFO within priority)
            sorted_jobs = sorted(
                pending_jobs,
                key=lambda x: (
                    priority_order.get(getattr(x, "priority", JobPriority.MEDIUM), 4),
                    x.created_at,
                ),
            )

            next_job = sorted_jobs[0] if sorted_jobs else None

            if next_job:
                logger.debug(
                    f"Next pending job: {next_job.id} "
                    f"(priority: {next_job.priority}, "
                    f"trigger: {getattr(next_job, 'trigger_type', 'unknown')}, "
                    f"created: {next_job.created_at})"
                )

            return next_job

        except Exception as e:
            logger.error(f"Failed to get next pending job: {e}")
            return None

    def start_job(self, job_id: int) -> bool:
        """
        Mark a video job as started.

        Args:
            job_id: ID of the job to start

        Returns:
            True if job was started successfully
        """
        try:
            logger.debug(f"Starting video job {job_id}")

            # Update job status
            success = self.video_ops.update_video_generation_job_status(job_id, JOB_STATUS.PROCESSING)

            if success:
                # Get job details for event
                job = self.video_ops.get_video_generation_job_by_id(job_id)
                if job:
                    self._broadcast_job_event(
                        event_type=SSEEvent.VIDEO_JOB_STARTED,
                        job_id=job_id,
                        timelapse_id=job.timelapse_id,
                        extra_data={"trigger_type": job.trigger_type},
                    )

                logger.info(f"Started video job {job_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to start video job {job_id}: {e}")
            return False

    def complete_job(
        self,
        job_id: int,
        success: bool,
        video_id: Optional[int] = None,
        video_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Mark a video job as completed or failed.

        Args:
            job_id: ID of the job
            success: Whether job completed successfully
            video_id: ID of created video (if successful)
            video_path: Path to created video file (if successful)
            error_message: Error message (if failed)

        Returns:
            True if job was completed successfully
        """
        try:
            logger.debug(f"Completing video job {job_id}, success: {success}")

            # Determine final status
            final_status = JOB_STATUS.COMPLETED if success else JOB_STATUS.FAILED

            # Update job record
            job_update_success = self.video_ops.complete_video_generation_job(
                job_id=job_id,
                success=success,
                error_message=error_message,
                video_path=video_path,
            )

            if job_update_success:
                # Get job details for event
                job = self.video_ops.get_video_generation_job_by_id(job_id)
                if job:
                    # Broadcast appropriate event
                    event_type = (
                        SSEEvent.VIDEO_JOB_COMPLETED
                        if success
                        else SSEEvent.VIDEO_JOB_FAILED
                    )

                    extra_data = {
                        "trigger_type": job.trigger_type,
                        "success": success,
                    }

                    if success and video_id:
                        extra_data["video_id"] = video_id

                    if not success and error_message:
                        extra_data["error"] = error_message

                    self._broadcast_job_event(
                        event_type=event_type,
                        job_id=job_id,
                        timelapse_id=job.timelapse_id,
                        extra_data=extra_data,
                    )

                status_text = "completed" if success else "failed"
                logger.info(f"Video job {job_id} {status_text}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to complete video job {job_id}: {e}")
            return False

    def get_queue_status(self) -> Dict[str, int]:
        """
        Get video job queue status statistics.

        Returns:
            Dictionary with job counts by status
        """
        try:
            logger.debug("Getting job queue status")

            # Get job counts by status
            status_counts = self.video_ops.get_video_job_queue_status()

            # Ensure all statuses are represented
            default_counts = {
                JOB_STATUS.PENDING.value: 0,
                JOB_STATUS.PROCESSING.value: 0,
                JOB_STATUS.COMPLETED.value: 0,
                JOB_STATUS.FAILED.value: 0,
            }

            default_counts.update(status_counts)
            # Return the merged counts (both are now Dict[str, int])
            return default_counts

        except Exception as e:
            logger.error(f"Failed to get job queue status: {e}")
            return {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            }

    def get_jobs_by_status(
        self, status: str, limit: int = 50
    ) -> List[VideoGenerationJobWithDetails]:
        """
        Get video generation jobs by status.

        Args:
            status: Job status to filter by
            limit: Maximum number of jobs to return

        Returns:
            List of jobs matching the status
        """
        try:
            if not validate_job_status(status):
                logger.error(f"Invalid job status: {status}")
                return []

            return self.video_ops.get_video_generation_jobs_by_status(status, limit)

        except Exception as e:
            logger.error(f"Failed to get jobs by status {status}: {e}")
            return []

    def cleanup_old_jobs(
        self, days_to_keep: int = DEFAULT_VIDEO_CLEANUP_DAYS
    ) -> int:
        """
        Clean up old completed video generation jobs.

        Args:
            days_to_keep: Number of days to keep completed jobs

        Returns:
            Number of jobs deleted
        """
        try:
            logger.debug(f"Cleaning up completed jobs older than {days_to_keep} days")

            deleted_count = self.video_ops.cleanup_old_video_jobs(days_to_keep)

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old video jobs")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")
            return 0

    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a video generation job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            True if job was cancelled successfully
        """
        try:
            logger.debug(f"Cancelling video job {job_id}")

            # Get job details first to check if it can be cancelled
            job = self.video_ops.get_video_generation_job_by_id(job_id)
            if not job:
                logger.error(f"Video job {job_id} not found")
                return False

            # Check if job is in a cancellable state
            cancellable_statuses = [JOB_STATUS.PENDING, JOB_STATUS.PROCESSING]
            if job.status not in [status.value for status in cancellable_statuses]:
                logger.error(f"Cannot cancel job {job_id} with status '{job.status}'")
                return False

            # Update job status to cancelled
            success = self.video_ops.update_video_generation_job_status(job_id, JOB_STATUS.CANCELLED.value)

            if success:
                # Broadcast cancellation event
                self._broadcast_job_event(
                    event_type=SSEEvent.VIDEO_JOB_FAILED,  # Using failed event for cancellation
                    job_id=job_id,
                    timelapse_id=job.timelapse_id,
                    extra_data={
                        "trigger_type": job.trigger_type,
                        "cancelled": True,
                        "reason": "cancelled_by_user",
                    },
                )

                logger.info(f"Successfully cancelled video job {job_id}")
                return True

            logger.error(f"Failed to update job {job_id} status to cancelled")
            return False

        except Exception as e:
            logger.error(f"Failed to cancel video job {job_id}: {e}")
            return False

    def _broadcast_job_event(
        self,
        event_type: str,
        job_id: int,
        timelapse_id: int,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast SSE event for job lifecycle.

        Args:
            event_type: Type of SSE event
            job_id: ID of the job
            timelapse_id: ID of the timelapse
            extra_data: Additional event data
        """
        try:
            event_data = {
                "job_id": job_id,
                "timelapse_id": timelapse_id,
                "timestamp": get_timezone_aware_timestamp_sync(self.db).isoformat(),
            }

            if extra_data:
                event_data.update(extra_data)

            self.sse_ops.create_event(
                event_type=event_type,
                event_data=event_data,
                priority=SSEPriority.NORMAL,
                source="video_pipeline",
            )

        except Exception as e:
            logger.error(f"Failed to broadcast job event: {e}")

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get job service health status.

        Returns:
            Service health metrics dictionary
        """
        try:
            queue_status = self.get_queue_status()

            return {
                "service": "video_job_service",
                "status": "healthy",
                "database_connected": self.db is not None,
                "queue_status": queue_status,
                "pending_jobs": queue_status.get("pending", 0),
                "processing_jobs": queue_status.get("processing", 0),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Video job service health check failed: {e}")
            return {
                "service": "video_job_service",
                "status": "unhealthy",
                "database_connected": False,
                "error": str(e),
            }