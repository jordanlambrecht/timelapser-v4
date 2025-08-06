# backend/app/services/video_pipeline/video_workflow_service.py
"""
Video Workflow Service - Pipeline orchestration for video generation.

This service handles the complete video generation workflow orchestration,
coordinating between job management, FFmpeg operations, overlay integration,
and file management. It focuses purely on workflow coordination and does NOT
handle video CRUD operations (use VideoService for that).

Key Features:
- Video generation workflow orchestration
- Job processing and concurrency management
- FFmpeg integration and error handling
- Overlay coordination and integration
- Structured logging and audit trails
- SSE event broadcasting for real-time updates
- Health monitoring for pipeline components

Business Rules:
- ALL timing decisions flow through SchedulerWorker (scheduler-centric)
- No autonomous job creation or scheduling decisions
- Execution-only model when called by scheduler
- Proper error handling and resource cleanup
- Structured logging for all workflow steps

Separation of Concerns:
- Pipeline orchestration and workflow management only
- No video CRUD operations (handled by VideoService)
- No autonomous timing decisions (handled by SchedulerWorker)
- No direct router compatibility layer
"""

from typing import Any, Dict, List, Optional

from ...config import settings
from ...database.core import SyncDatabase
from ...database.sse_events_operations import SyncSSEEventsOperations
from ...enums import (
    JobPriority,
    JobStatus,
    LogEmoji,
    LoggerName,
    LogLevel,
    LogSource,
    SSEEvent,
    SSEEventSource,
    SSEPriority,
    VideoQuality,
)
from ...models.shared_models import VideoGenerationJobWithDetails
from ...services.logger import get_service_logger
from ...utils.file_helpers import (
    ensure_directory_exists,
    get_relative_path,
    validate_file_path,
)
from ...utils.time_utils import (
    format_filename_timestamp,
    get_timezone_aware_timestamp_sync,
)
from ...workers.models.video_responses import (
    ProcessingStatus,
    ProcessQueueResult,
    QueueStatus,
    VideoGenerationResult,
)
from . import ffmpeg_utils
from .overlay_integration_service import OverlayIntegrationService

# from ..log_service import SyncLogService  # Removed: file does not exist
from .video_job_service import VideoJobService

logger = get_service_logger(LoggerName.VIDEO_PIPELINE, LogSource.PIPELINE)


class VideoWorkflowService:
    """
    Video generation workflow orchestration service using composition pattern.

    Responsibilities:
    - Video generation workflow coordination
    - Job processing and concurrency management
    - FFmpeg integration and error handling
    - Overlay system coordination
    - Structured logging and audit trails
    - SSE event broadcasting

    Interactions:
    - Uses VideoJobService for job management
    - Uses OverlayIntegrationService for overlay coordination
    - Uses SyncLogService for audit trails
    - Uses FFmpeg utilities for video generation
    - Broadcasts SSE events for real-time updates

    Scheduler-Centric Model:
    - No autonomous timing decisions
    - Execution-only when called by SchedulerWorker
    - All job creation flows through scheduler authority
    """

    def __init__(
        self,
        db: SyncDatabase,
        job_service: VideoJobService,
        overlay_service: OverlayIntegrationService,
        settings_service,
        video_service=None,
        timelapse_service=None,
        max_concurrent_jobs: int = 3,
    ):
        """
        Initialize VideoWorkflowService with required dependencies.

        Args:
            db: SyncDatabase instance for database operations
            job_service: VideoJobService for job management
            overlay_service: OverlayIntegrationService for overlay coordination
            settings_service: SettingsService for configuration access
            video_service: VideoService for video operations (optional, will create if not provided)
            timelapse_service: TimelapseService for timelapse operations (optional, will create if not provided)
            max_concurrent_jobs: Maximum concurrent video jobs
        """
        self.db = db
        self.job_service = job_service
        self.overlay_service = overlay_service
        self.settings_service = settings_service

        # Initialize services (inject or create)
        if video_service:
            self.video_service = video_service
        else:
            from ...services.video_service import SyncVideoService

            self.video_service = SyncVideoService(db, settings_service)

        if timelapse_service:
            self.timelapse_service = timelapse_service
        else:
            from ...services.timelapse_service import SyncTimelapseService

            self.timelapse_service = SyncTimelapseService(db)

        # SSE operations (keep for now until we have a dedicated SSE service)
        self.sse_ops = SyncSSEEventsOperations(db)

        # Processing limits
        self.max_concurrent_jobs = max_concurrent_jobs
        self.currently_processing = 0

        logger.debug(
            f"VideoWorkflowService initialized with max_concurrent_jobs={max_concurrent_jobs}"
        )

    def execute_video_generation(
        self, job_id: int, timelapse_id: int, settings: Optional[Dict[str, Any]] = None
    ) -> VideoGenerationResult:
        """
        🎯 SCHEDULER-CENTRIC: Execute specific video generation job when scheduled.

        This method is called by SchedulerWorker to execute a specific video
        generation job. It does NOT make autonomous timing decisions.

        Args:
            job_id: Specific job ID to execute
            timelapse_id: Timelapse ID for the job
            settings: Optional video generation settings (reserved for future use)

        Returns:
            Dict containing execution results
        """
        try:
            logger.info(
                f"🎬 Executing scheduled video generation: job {job_id}, timelapse {timelapse_id}"
            )

            # Check concurrency limits
            if self.currently_processing >= self.max_concurrent_jobs:
                return VideoGenerationResult(
                    success=False,
                    error=f"Maximum concurrent jobs ({self.max_concurrent_jobs}) reached",
                )

            # Get the specific job
            job = self.job_service.video_ops.get_video_generation_job_by_id(job_id)
            if not job:
                return VideoGenerationResult(
                    success=False, error=f"Job {job_id} not found"
                )

            # Execute the job
            self.currently_processing += 1
            try:
                success = self._process_video_job(job)
                return VideoGenerationResult(
                    success=success,
                    video_id=job_id,
                    error=None if success else "Video generation failed",
                )
            finally:
                self.currently_processing = max(0, self.currently_processing - 1)

        except Exception as e:
            logger.error(
                f"Error executing scheduled video generation for job {job_id}: {e}",
                exception=e,
            )
            return VideoGenerationResult(success=False, error=str(e))

    def process_next_pending_job(self) -> Optional[int]:
        """
        🎯 SCHEDULER-CENTRIC: Process the next pending job in queue.

        This method processes existing jobs in the queue without making any
        timing decisions. Job creation is handled by SchedulerWorker.

        Returns:
            Job ID if job was processed, None otherwise
        """
        try:
            logger.debug("Processing next pending video job")

            # Check concurrency limits
            if self.currently_processing >= self.max_concurrent_jobs:
                logger.debug(f"Max concurrent jobs reached: {self.max_concurrent_jobs}")
                return None

            # Get next job from queue
            next_job = self.job_service.get_next_pending_job()
            if not next_job:
                logger.debug("No pending jobs in queue")
                return None

            # Process the job
            self.currently_processing += 1
            try:
                success = self._process_video_job(next_job)
                if success:
                    logger.info(f"Successfully processed video job {next_job.id}")
                    return next_job.id
                else:
                    logger.error(f"Failed to process video job {next_job.id}")
                    return None
            finally:
                self.currently_processing = max(0, self.currently_processing - 1)

        except Exception as e:
            logger.error(f"Failed to process next job: {e}", exception=e)
            return None

    def _process_video_job(self, job: VideoGenerationJobWithDetails) -> bool:
        """
        Process a single video generation job with complete workflow.

        Args:
            job: Video generation job to process

        Returns:
            True if job was processed successfully
        """
        job_id = job.id

        try:
            # Start job processing
            job_started = self.job_service.start_job(job_id)
            if not job_started:
                logger.error(f"Failed to start video job {job_id}")
                self._log_job_event(
                    job,
                    LogLevel.ERROR,
                    "Failed to start video job",
                    "job_start_failure",
                )
                return False

            # Log job start
            self._log_job_event(
                job,
                LogLevel.INFO,
                f"Video generation job {job_id} started",
                "job_started",
            )

            # Broadcast job started event
            self._broadcast_job_event(
                SSEEvent.VIDEO_JOB_STARTED,
                {
                    "job_id": job_id,
                    "timelapse_id": job.timelapse_id,
                    "trigger_type": job.trigger_type,
                    "priority": job.priority,
                },
            )

            # Generate video
            video_result = self._generate_video_for_job(job)

            if video_result["success"]:
                # Complete job successfully
                self.job_service.complete_job(
                    job_id=job_id,
                    success=True,
                    video_id=video_result.get("video_id"),
                    video_path=video_result.get("video_path"),
                )

                # Log successful completion
                # Audit trail logging removed: no _log_audit_trail method exists

                # Broadcast success events
                self._broadcast_job_event(
                    SSEEvent.VIDEO_JOB_COMPLETED,
                    {
                        "job_id": job_id,
                        "timelapse_id": job.timelapse_id,
                        "video_id": video_result.get("video_id"),
                        "video_path": video_result.get("video_path"),
                        "duration_seconds": video_result.get("metadata", {}).get(
                            "duration_seconds", 0
                        ),
                        "file_size_bytes": video_result.get("metadata", {}).get(
                            "file_size_bytes", 0
                        ),
                    },
                )

                self._broadcast_job_event(
                    SSEEvent.VIDEO_GENERATED,
                    {
                        "video_id": video_result.get("video_id"),
                        "timelapse_id": job.timelapse_id,
                        "trigger_type": job.trigger_type,
                        "metadata": video_result.get("metadata", {}),
                    },
                    priority=SSEPriority.HIGH,
                )

                return True
            else:
                # Complete job with failure
                self.job_service.complete_job(
                    job_id=job_id,
                    success=False,
                    error_message=video_result.get("error"),
                )

                # Log failure
                self._log_job_event(
                    job,
                    LogLevel.ERROR,
                    f"Video generation failed: {video_result.get('error')}",
                    "video_generation_failure",
                )

                # Broadcast failure event
                self._broadcast_job_event(
                    SSEEvent.VIDEO_JOB_FAILED,
                    {
                        "job_id": job_id,
                        "timelapse_id": job.timelapse_id,
                        "error_message": video_result.get("error"),
                        "error_type": "video_generation_failure",
                    },
                    priority=SSEPriority.HIGH,
                )

                return False

        except Exception as e:
            logger.error(f"Failed to process video job {job_id}: {e}", exception=e)

            # Log unexpected error
            self._log_job_event(
                job,
                LogLevel.ERROR,
                f"Unexpected error processing job: {str(e)}",
                "unexpected_processing_error",
            )

            # Complete job with failure
            self.job_service.complete_job(
                job_id=job_id, success=False, error_message=str(e)
            )

            return False

    def _generate_video_for_job(
        self, job: VideoGenerationJobWithDetails
    ) -> Dict[str, Any]:
        """
        Generate video for a specific job with complete workflow.

        Args:
            job: Video generation job

        Returns:
            Generation result dictionary
        """
        try:
            logger.info(
                f"Starting video generation for job {job.id}, timelapse {job.timelapse_id}"
            )

            # Get timelapse data
            timelapse = self.timelapse_service.get_timelapse_by_id(job.timelapse_id)
            if not timelapse:
                return {
                    "success": False,
                    "error": f"Timelapse {job.timelapse_id} not found",
                }

            # Get job settings (already a dict, not JSON string)
            job_settings = job.settings if job.settings else {}

            # Prepare file paths
            images_dir = validate_file_path(
                f"cameras/camera-{timelapse.camera_id}/images",
                base_directory=settings.data_directory,
                must_exist=True,
            )

            # Generate output filename with timezone-aware timestamp
            timestamp_dt = get_timezone_aware_timestamp_sync(self.settings_service)
            timestamp_str = format_filename_timestamp(
                timestamp_dt, self.settings_service
            )
            output_filename = f"timelapse_{job.timelapse_id}_{timestamp_str}.mp4"

            # Ensure output directory exists
            videos_dir = ensure_directory_exists(settings.videos_directory)
            output_path = videos_dir / output_filename

            # Determine overlay mode
            overlay_mode = self.overlay_service.get_overlay_mode_for_video(
                job.timelapse_id
            )
            use_overlay_images = overlay_mode == "overlay"

            logger.info(f"Generating video with overlay mode: {overlay_mode}")

            # Get video settings with defaults
            video_settings = {
                "fps": job_settings.get("fps", 24.0),
                "quality": job_settings.get("quality", VideoQuality.MEDIUM),
                "rotation": job_settings.get("rotation", 0),
            }

            # Generate video using FFmpeg
            success, message, metadata = ffmpeg_utils.generate_video(
                images_directory=images_dir,
                output_path=str(output_path),
                framerate=float(video_settings["fps"]),
                quality=video_settings["quality"],
                rotation=video_settings["rotation"],
                use_overlay_images=use_overlay_images,
            )

            if success:
                # Create video record
                video_data = {
                    "camera_id": timelapse.camera_id,
                    "timelapse_id": job.timelapse_id,
                    "name": f"Timelapse {timelapse.name}",
                    "file_path": get_relative_path(
                        output_path, settings.data_directory
                    ),
                    "status": "completed",
                    "settings": video_settings,
                    "image_count": metadata.get("image_count", 0),
                    "file_size": metadata.get("file_size_bytes", 0),
                    "duration_seconds": metadata.get("duration_seconds", 0),
                    "calculated_fps": metadata.get("framerate", video_settings["fps"]),
                    "images_start_date": timelapse.start_date,
                    "images_end_date": timelapse.last_capture_at
                    or timelapse.start_date,
                    "trigger_type": job.trigger_type,
                    "job_id": job.id,
                    "created_at": get_timezone_aware_timestamp_sync(
                        self.settings_service
                    ),
                }

                video_record = self.video_service.create_video_record(video_data)
                if not video_record:
                    logger.error(f"Failed to create video record for job {job.id}")
                    return {
                        "success": False,
                        "error": "Failed to create video database record",
                    }

                logger.info(f"Video generation completed successfully for job {job.id}")
                return {
                    "success": True,
                    "video_id": video_record.id,
                    "video_path": str(output_path),
                    "message": message,
                    "metadata": metadata,
                }
            else:
                logger.error(
                    f"FFmpeg video generation failed for job {job.id}: {message}"
                )

                # Log structured FFmpeg error
                self._log_job_event(
                    job,
                    LogLevel.ERROR,
                    "FFmpeg video generation failed",
                    "ffmpeg_generation_failure",
                    {
                        "ffmpeg_error": message,
                        "video_settings": video_settings,
                        "images_directory": str(images_dir),
                        "output_path": str(output_path),
                        "use_overlay_images": use_overlay_images,
                    },
                )

                return {"success": False, "error": message}

        except Exception as e:
            logger.error(f"Video generation failed for job {job.id}: {e}", exception=e)

            # Log unexpected video generation error
            self._log_job_event(
                job,
                LogLevel.ERROR,
                f"Unexpected video generation error: {str(e)}",
                "unexpected_generation_error",
            )

            return {"success": False, "error": str(e)}

    def get_processing_status(self) -> ProcessingStatus:
        """
        Get current video processing status.

        Returns:
            ProcessingStatus object with current processing information
        """
        try:
            queue_status_dict = self.job_service.get_queue_status()

            # Convert dictionary to typed QueueStatus object using enum keys for type safety
            # This prevents typos, enables IDE autocomplete, and is refactor-safe
            # TODO: Consider adding .value for explicit intent in future cleanup pass
            queue_status = QueueStatus(
                pending=queue_status_dict[JobStatus.PENDING],
                processing=queue_status_dict[JobStatus.PROCESSING],
                completed=queue_status_dict[JobStatus.COMPLETED],
                failed=queue_status_dict[JobStatus.FAILED],
            )

            # Return typed ProcessingStatus object - use typed object properties consistently
            return ProcessingStatus(
                currently_processing=self.currently_processing,
                max_concurrent_jobs=self.max_concurrent_jobs,
                queue_status=queue_status,
                pending_jobs=queue_status.pending,  # Use typed object property
                processing_jobs=queue_status.processing,  # Use typed object property
                can_process_more=self.currently_processing < self.max_concurrent_jobs,
                capacity_utilization_percent=(
                    self.currently_processing / self.max_concurrent_jobs
                )
                * 100,
            )

        except Exception as e:
            logger.error(f"Failed to get processing status: {e}", exception=e)
            # Return a default ProcessingStatus object for error cases
            return ProcessingStatus(
                currently_processing=0,
                max_concurrent_jobs=1,
                queue_status=QueueStatus(
                    pending=0, processing=0, completed=0, failed=0
                ),
                pending_jobs=0,
                processing_jobs=0,
                can_process_more=False,
                capacity_utilization_percent=0.0,
            )

    def execute_video_generation_direct(
        self, timelapse_id: int, settings: Optional[Dict[str, Any]] = None
    ) -> VideoGenerationResult:
        """
        🎯 SCHEDULER-CENTRIC: Execute direct video generation when commanded by scheduler.

        This method provides direct execution without job queue management,
        used when SchedulerWorker commands immediate video generation.

        Args:
            timelapse_id: Timelapse ID to generate video for
            settings: Optional video generation settings override

        Returns:
            Dict containing execution results
        """
        try:
            logger.info(
                f"🎬 Direct video generation for timelapse {timelapse_id} (scheduler commanded)"
            )

            # Create a temporary job for direct execution
            trigger_type = (
                settings.get("trigger_type", "manual") if settings else "manual"
            )
            priority = JobPriority.HIGH  # Direct execution gets high priority

            # Use job service to create job
            job_id = self.job_service.create_job(
                timelapse_id=timelapse_id,
                trigger_type=trigger_type,
                priority=priority,
                settings=settings,
            )

            if not job_id:
                return VideoGenerationResult(
                    success=False, error="Failed to create video job"
                )

            # Execute the job immediately
            result = self.execute_video_generation(
                job_id=job_id,
                timelapse_id=timelapse_id,
                settings=settings,
            )

            return result

        except Exception as e:
            logger.error(
                f"Direct video generation failed for timelapse {timelapse_id}: {e}",
                exception=e,
            )
            return VideoGenerationResult(success=False, error=str(e))

    def process_queue_only(self) -> ProcessQueueResult:
        """
        🎯 SCHEDULER-CENTRIC: Process existing jobs without autonomous trigger evaluation.

        This method processes pending jobs in the queue without making any
        autonomous timing decisions or creating new jobs. Used by VideoWorker
        in execution-only mode.

        Returns:
            Dict containing processing results
        """
        try:
            logger.debug(
                "Processing video queue (execution-only mode)", emoji=LogEmoji.QUEUE
            )

            jobs_processed = 0
            errors: List[str] = []

            # Process up to max_concurrent_jobs
            while self.currently_processing < self.max_concurrent_jobs:
                # Get next pending job
                job_id = self.process_next_pending_job()

                if job_id:
                    jobs_processed += 1
                    logger.info(f"Processed video job {job_id}", emoji=LogEmoji.JOB)
                else:
                    # No more pending jobs
                    break

            return ProcessQueueResult(
                success=True,
                jobs_processed=jobs_processed,
                currently_processing=self.currently_processing,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Queue processing failed: {e}", exception=e)
            return ProcessQueueResult(
                success=False,
                jobs_processed=0,
                currently_processing=self.currently_processing,
                errors=[str(e)],
            )

    def get_workflow_health(self) -> Dict[str, Any]:
        """
        Get video workflow health status.

        Returns:
            Workflow health status dictionary
        """
        try:
            # Check database connectivity
            database_connected = self._check_database_connectivity()

            # Check FFmpeg availability
            ffmpeg_available, ffmpeg_version = self._check_ffmpeg_health()

            # Get processing status
            processing_status = self.get_processing_status()

            # Check sub-service health
            job_service_health = self.job_service.get_service_health()
            overlay_service_health = self.overlay_service.get_service_health()

            # Determine overall status
            overall_status = "healthy"
            if not database_connected or not ffmpeg_available:
                overall_status = "unhealthy"
            elif (
                job_service_health.get("status") != "healthy"
                or overlay_service_health.get("status") == "unhealthy"
            ):
                overall_status = "degraded"

            return {
                "service": "video_workflow",
                "status": overall_status,
                "database_connected": database_connected,
                "ffmpeg_available": ffmpeg_available,
                "ffmpeg_version": ffmpeg_version,
                "processing_capacity": {
                    "currently_processing": self.currently_processing,
                    "max_concurrent_jobs": self.max_concurrent_jobs,
                    "capacity_utilization_percent": processing_status.capacity_utilization_percent,
                },
                "sub_services": {
                    "job_service": job_service_health,
                    "overlay_service": overlay_service_health,
                },
                "last_check": get_timezone_aware_timestamp_sync(
                    self.settings_service
                ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Video workflow health check failed: {e}", exception=e)
            return {
                "service": "video_workflow",
                "status": "unhealthy",
                "error": str(e),
                "last_check": get_timezone_aware_timestamp_sync(
                    self.settings_service
                ).isoformat(),
            }

    def cancel_video_generation(self, job_id: int) -> Dict[str, Any]:
        """
        Cancel a video generation job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            Dictionary with cancellation result
        """
        try:
            logger.info(f"Cancelling video generation job {job_id}")

            # Use the job service to cancel the job
            success = self.job_service.cancel_job(job_id)

            if success:
                # Log successful cancellation
                logger.info(
                    f"Video generation job {job_id} cancelled successfully",
                    extra_context={
                        "job_id": job_id,
                        "action": "cancel_job",
                        "cancelled_by": "user",
                    },
                )

                return {
                    "success": True,
                    "message": f"Video generation job {job_id} cancelled successfully",
                    "job_id": job_id,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to cancel video generation job {job_id}",
                    "job_id": job_id,
                }

        except Exception as e:
            logger.error(
                f"Failed to cancel video generation job {job_id}: {e}", exception=e
            )
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id,
            }

    def _check_database_connectivity(self) -> bool:
        """Check database connectivity."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}", exception=e)
            return False

    def _check_ffmpeg_health(self) -> tuple[bool, str]:
        """Check FFmpeg availability and version."""
        try:
            available, version_info = ffmpeg_utils.test_ffmpeg_available()
            return available, version_info
        except Exception as e:
            logger.warning(f"FFmpeg health check failed: {e}")
            return False, "unknown"

    def _log_job_event(
        self,
        job: VideoGenerationJobWithDetails,
        level: LogLevel,
        message: str,
        action: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log job-related events with structured data."""
        try:
            log_data = {
                "job_id": job.id,
                "timelapse_id": job.timelapse_id,
                "trigger_type": job.trigger_type,
                "action": action,
                **(extra_data or {}),
            }

            # Use appropriate logger method based on log level
            if level == LogLevel.INFO:
                logger.info(message, extra_context=log_data)
            elif level == LogLevel.ERROR:
                logger.error(message, extra_context=log_data)
            elif level == LogLevel.WARNING:
                logger.warning(message, extra_context=log_data)
            elif level == LogLevel.DEBUG:
                logger.debug(message, extra_context=log_data)
            else:
                logger.info(message, extra_context=log_data)
        except Exception as e:
            logger.error(f"Failed to log job event: {e}")

    # (Removed stray function signature and parameters outside any function)

    def _broadcast_job_event(
        self,
        event_type: SSEEvent,
        event_data: Dict[str, Any],
        priority: SSEPriority = SSEPriority.NORMAL,
        source: SSEEventSource = SSEEventSource.VIDEO_PIPELINE,
    ) -> None:
        """Broadcast SSE event for workflow operations."""
        try:
            event_data_with_timestamp = {
                **event_data,
                "timestamp": get_timezone_aware_timestamp_sync(
                    self.settings_service
                ).isoformat(),
            }

            self.sse_ops.create_event(
                event_type=event_type,
                event_data=event_data_with_timestamp,
                priority=priority,
                source=source,
            )

            logger.debug(f"Broadcasted SSE event: {event_type}")

        except Exception as e:
            logger.warning(f"Failed to broadcast SSE event {event_type}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get VideoWorkflowService status (STANDARDIZED METHOD NAME).

        Returns:
            Dict[str, Any]: Service status information
        """
        try:
            return {
                "service_name": "VideoWorkflowService",
                "service_type": "video_workflow_orchestration",
                "database_status": "healthy" if self.db else "unavailable",
                "job_service_status": "healthy" if self.job_service else "unavailable",
                "overlay_service_status": (
                    "healthy" if self.overlay_service else "unavailable"
                ),
                "settings_service_status": (
                    "healthy" if self.settings_service else "unavailable"
                ),
                "video_service_status": (
                    "healthy" if self.video_service else "unavailable"
                ),
                "timelapse_service_status": (
                    "healthy" if self.timelapse_service else "unavailable"
                ),
                "sse_ops_status": "healthy" if self.sse_ops else "unavailable",
                "currently_processing": self.currently_processing,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "capacity_utilization_percent": (
                    (self.currently_processing / self.max_concurrent_jobs) * 100
                    if self.max_concurrent_jobs > 0
                    else 0
                ),
                "can_process_more": self.currently_processing
                < self.max_concurrent_jobs,
                "data_directory": settings.data_directory,
                "videos_directory": settings.videos_directory,
                "service_healthy": all(
                    [
                        self.db is not None,
                        self.job_service is not None,
                        self.overlay_service is not None,
                        self.settings_service is not None,
                        self.video_service is not None,
                        self.timelapse_service is not None,
                        self.sse_ops is not None,
                    ]
                ),
            }
        except Exception as e:
            return {
                "service_name": "VideoWorkflowService",
                "service_type": "video_workflow_orchestration",
                "service_healthy": False,
                "status_error": str(e),
            }
