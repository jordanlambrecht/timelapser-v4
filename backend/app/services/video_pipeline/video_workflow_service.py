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

from typing import Dict, Any, Optional
from loguru import logger

from ...enums import SSEPriority, VideoQuality

from ...database.core import SyncDatabase
from ...database.video_operations import SyncVideoOperations
from ...database.timelapse_operations import SyncTimelapseOperations
from ...database.sse_events_operations import SyncSSEEventsOperations
from ...models.shared_models import VideoGenerationJobWithDetails
from ...utils.file_helpers import (
    validate_file_path,
    ensure_directory_exists,
    get_relative_path,
)
from ...utils.time_utils import get_timezone_aware_timestamp_sync
from ...config import settings
from ..log_service import SyncLogService
from .video_job_service import VideoJobService
from .overlay_integration_service import OverlayIntegrationService
from . import ffmpeg_utils


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
        log_service: Optional[SyncLogService] = None,
        max_concurrent_jobs: int = 3,
    ):
        """
        Initialize VideoWorkflowService with required dependencies.

        Args:
            db: SyncDatabase instance for database operations
            job_service: VideoJobService for job management
            overlay_service: OverlayIntegrationService for overlay coordination
            log_service: Optional log service for audit trails
            max_concurrent_jobs: Maximum concurrent video jobs
        """
        self.db = db
        self.job_service = job_service
        self.overlay_service = overlay_service
        self.log_service = log_service

        # Database operations
        self.video_ops = SyncVideoOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)

        # Processing limits
        self.max_concurrent_jobs = max_concurrent_jobs
        self.currently_processing = 0

        logger.debug(
            f"VideoWorkflowService initialized with max_concurrent_jobs={max_concurrent_jobs}"
        )

    def execute_video_generation(
        self, job_id: int, timelapse_id: int, settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
                return {
                    "success": False,
                    "error": f"Maximum concurrent jobs ({self.max_concurrent_jobs}) reached",
                    "job_id": job_id,
                }

            # Get the specific job
            job = self.video_ops.get_video_generation_job_by_id(job_id)
            if not job:
                return {
                    "success": False,
                    "error": f"Job {job_id} not found",
                    "job_id": job_id,
                }

            # Execute the job
            self.currently_processing += 1
            try:
                success = self._process_video_job(job)
                return {
                    "success": success,
                    "job_id": job_id,
                    "timelapse_id": timelapse_id,
                    "message": "Video generation completed" if success else "Video generation failed",
                }
            finally:
                self.currently_processing = max(0, self.currently_processing - 1)

        except Exception as e:
            logger.error(f"Error executing scheduled video generation for job {job_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id,
            }

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
            logger.error(f"Failed to process next job: {e}")
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
                    job, "ERROR", "Failed to start video job", "job_start_failure"
                )
                return False

            # Log job start
            self._log_job_event(
                job, "INFO", f"Video generation job {job_id} started", "job_started"
            )

            # Broadcast job started event
            self._broadcast_job_event(
                "video_job_started",
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
                self._log_audit_trail(
                    "generate",
                    "video",
                    video_result.get("video_id"),
                    {
                        "job_id": job_id,
                        "timelapse_id": job.timelapse_id,
                        "trigger_type": job.trigger_type,
                        "video_path": video_result.get("video_path"),
                        "metadata": video_result.get("metadata", {}),
                    },
                )

                # Broadcast success events
                self._broadcast_job_event(
                    "video_job_completed",
                    {
                        "job_id": job_id,
                        "timelapse_id": job.timelapse_id,
                        "video_id": video_result.get("video_id"),
                        "video_path": video_result.get("video_path"),
                        "duration_seconds": video_result.get("metadata", {}).get("duration_seconds", 0),
                        "file_size_bytes": video_result.get("metadata", {}).get("file_size_bytes", 0),
                    },
                )

                self._broadcast_job_event(
                    "video_generated",
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
                    "ERROR",
                    f"Video generation failed: {video_result.get('error')}",
                    "video_generation_failure",
                )

                # Broadcast failure event
                self._broadcast_job_event(
                    "video_job_failed",
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
            logger.error(f"Failed to process video job {job_id}: {e}")

            # Log unexpected error
            self._log_job_event(
                job,
                "ERROR",
                f"Unexpected error processing job: {str(e)}",
                "unexpected_processing_error",
            )

            # Complete job with failure
            self.job_service.complete_job(
                job_id=job_id, success=False, error_message=str(e)
            )

            return False

    def _generate_video_for_job(self, job: VideoGenerationJobWithDetails) -> Dict[str, Any]:
        """
        Generate video for a specific job with complete workflow.

        Args:
            job: Video generation job

        Returns:
            Generation result dictionary
        """
        try:
            logger.info(f"Starting video generation for job {job.id}, timelapse {job.timelapse_id}")

            # Get timelapse data
            timelapse = self.timelapse_ops.get_timelapse_by_id(job.timelapse_id)
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

            # Generate output filename
            timestamp_str = get_timezone_aware_timestamp_sync(self.db).strftime("%Y%m%d_%H%M%S")
            output_filename = f"timelapse_{job.timelapse_id}_{timestamp_str}.mp4"

            # Ensure output directory exists
            videos_dir = ensure_directory_exists(settings.videos_directory)
            output_path = videos_dir / output_filename

            # Determine overlay mode
            overlay_mode = self.overlay_service.get_overlay_mode_for_video(job.timelapse_id)
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
                    "file_path": get_relative_path(output_path, settings.data_directory),
                    "status": "completed",
                    "settings": video_settings,
                    "image_count": metadata.get("image_count", 0),
                    "file_size": metadata.get("file_size_bytes", 0),
                    "duration_seconds": metadata.get("duration_seconds", 0),
                    "calculated_fps": metadata.get("framerate", video_settings["fps"]),
                    "images_start_date": timelapse.start_date,
                    "images_end_date": timelapse.last_capture_at or timelapse.start_date,
                    "trigger_type": job.trigger_type,
                    "job_id": job.id,
                    "created_at": get_timezone_aware_timestamp_sync(self.db),
                }

                video_record = self.video_ops.create_video_record(video_data)
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
                logger.error(f"FFmpeg video generation failed for job {job.id}: {message}")

                # Log structured FFmpeg error
                self._log_job_event(
                    job,
                    "ERROR",
                    f"FFmpeg video generation failed",
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
            logger.error(f"Video generation failed for job {job.id}: {e}")

            # Log unexpected video generation error
            self._log_job_event(
                job,
                "ERROR",
                f"Unexpected video generation error: {str(e)}",
                "unexpected_generation_error",
            )

            return {"success": False, "error": str(e)}

    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current video processing status.

        Returns:
            Processing status dictionary
        """
        try:
            queue_status = self.job_service.get_queue_status()

            return {
                "currently_processing": self.currently_processing,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "queue_status": queue_status,
                "pending_jobs": queue_status.get("pending", 0),
                "processing_jobs": queue_status.get("processing", 0),
                "can_process_more": self.currently_processing < self.max_concurrent_jobs,
                "capacity_utilization_percent": (
                    self.currently_processing / self.max_concurrent_jobs
                ) * 100,
            }

        except Exception as e:
            logger.error(f"Failed to get processing status: {e}")
            return {"error": str(e)}

    def execute_video_generation_direct(
        self, timelapse_id: int, settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
            job_data = {
                "timelapse_id": timelapse_id,
                "trigger_type": settings.get("trigger_type", "manual") if settings else "manual",
                "priority": SSEPriority.HIGH,
                "settings": settings,
            }
            
            # Use job service to create job
            job_id = self.job_service.create_job(
                timelapse_id=timelapse_id,
                trigger_type=job_data["trigger_type"],
                priority=job_data["priority"],
                settings=settings,
            )
            
            if not job_id:
                return {
                    "success": False,
                    "error": "Failed to create video job",
                }
            
            # Execute the job immediately
            result = self.execute_video_generation(
                job_id=job_id,
                timelapse_id=timelapse_id,
                settings=settings,
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Direct video generation failed for timelapse {timelapse_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def process_queue_only(self) -> Dict[str, Any]:
        """
        🎯 SCHEDULER-CENTRIC: Process existing jobs without autonomous trigger evaluation.
        
        This method processes pending jobs in the queue without making any
        autonomous timing decisions or creating new jobs. Used by VideoWorker
        in execution-only mode.
        
        Returns:
            Dict containing processing results
        """
        try:
            logger.debug("Processing video queue (execution-only mode)")
            
            jobs_processed = 0
            errors = []
            
            # Process up to max_concurrent_jobs
            while self.currently_processing < self.max_concurrent_jobs:
                # Get next pending job
                job_id = self.process_next_pending_job()
                
                if job_id:
                    jobs_processed += 1
                    logger.info(f"Processed video job {job_id}")
                else:
                    # No more pending jobs
                    break
                    
            return {
                "success": True,
                "jobs_processed": jobs_processed,
                "currently_processing": self.currently_processing,
                "errors": errors,
            }
            
        except Exception as e:
            logger.error(f"Queue processing failed: {e}")
            return {
                "success": False,
                "jobs_processed": 0,
                "errors": [str(e)],
            }

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
                    "capacity_utilization_percent": processing_status.get(
                        "capacity_utilization_percent", 0
                    ),
                },
                "sub_services": {
                    "job_service": job_service_health,
                    "overlay_service": overlay_service_health,
                },
                "last_check": get_timezone_aware_timestamp_sync(self.db).isoformat(),
            }

        except Exception as e:
            logger.error(f"Video workflow health check failed: {e}")
            return {
                "service": "video_workflow",
                "status": "unhealthy",
                "error": str(e),
                "last_check": get_timezone_aware_timestamp_sync(self.db).isoformat(),
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
                if self.log_service:
                    self.log_service.write_log_entry(
                        level="INFO",
                        message=f"Video generation job {job_id} cancelled successfully",
                        logger_name="video_pipeline",
                        source="video_workflow",
                        extra_data={
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
            logger.error(f"Failed to cancel video generation job {job_id}: {e}")
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
            logger.error(f"Database connectivity check failed: {e}")
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
        level: str,
        message: str,
        action: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log job-related events with structured data."""
        if not self.log_service:
            return

        try:
            log_data = {
                "job_id": job.id,
                "timelapse_id": job.timelapse_id,
                "trigger_type": job.trigger_type,
                "action": action,
                **(extra_data or {}),
            }

            self.log_service.write_log_entry(
                level=level,
                message=message,
                logger_name="video_pipeline",
                source="video_workflow",
                extra_data=log_data,
            )
        except Exception as e:
            logger.warning(f"Failed to write structured log: {e}")

    def _log_audit_trail(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        changes: Dict[str, Any],
    ) -> None:
        """Log audit trail for video operations."""
        if not self.log_service:
            return

        try:
            # Use write_log_entry since SyncLogService doesn't have maintain_audit_trail
            audit_data = {
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "changes": changes,
                "user_id": "system",
                "audit_trail": True,
            }
            
            self.log_service.write_log_entry(
                level="INFO",
                message=f"Audit: {action} {entity_type} {entity_id}",
                logger_name="audit_trail",
                source="video_workflow",
                extra_data=audit_data,
            )
        except Exception as e:
            logger.warning(f"Failed to write audit trail: {e}")

    def _broadcast_job_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: str = SSEPriority.NORMAL,
        source: str = "video_workflow",
    ) -> None:
        """Broadcast SSE event for workflow operations."""
        try:
            event_data_with_timestamp = {
                **event_data,
                "timestamp": get_timezone_aware_timestamp_sync(self.db).isoformat(),
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