# backend/app/services/capture_pipeline/job_coordination_service.py
"""
Capture Pipeline Job Coordination Service

Background job coordination within the capture pipeline workflow.

🎯 SERVICE SCOPE: Background job coordination and management
- Thumbnail generation job queuing
- Video automation trigger evaluation
- Job priority management
- Background job status tracking
- Cross-job coordination and dependencies

📝 KEY ARCHITECTURAL BOUNDARIES:
- NO direct job execution (delegates to worker services)
- NO RTSP operations (receives job requests from workflow)
- NO database record creation (coordinates with existing job services)
- NO file I/O operations (coordinates file-based job parameters)

🚀 JOB COORDINATION RESPONSIBILITIES:
This service manages the coordination of background jobs within the capture
pipeline workflow, ensuring proper queuing, prioritization, and status tracking
while maintaining clean separation from job execution logic.
"""

from enum import Enum
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from ...models.health_model import HealthStatus
from ...services.logger import get_service_logger
from ...utils.enum_helpers import parse_enum

if TYPE_CHECKING:
    from ..scheduling import SyncJobQueueService

# Global constants
from ...constants import (
    BOOLEAN_TRUE_STRING,
    DEFAULT_GENERATE_THUMBNAILS,
    SETTING_KEY_THUMBNAIL_GENERATION_ENABLED,
    VIDEO_QUEUE_ERROR_THRESHOLD,
    VIDEO_QUEUE_WARNING_THRESHOLD,
)

# Initialize database operations
from ...database.core import AsyncDatabase, SyncDatabase
from ...database.sse_events_operations import SyncSSEEventsOperations
from ...database.thumbnail_job_operations import SyncThumbnailJobOperations
from ...database.timelapse_operations import SyncTimelapseOperations
from ...database.video_operations import SyncVideoOperations
from ...enums import (
    JobPriority,
    JobStatus,
    JobTypes,
    LogEmoji,
    LoggerName,
    LogSource,
    OverlayJobStatus,
    SSEEvent,
    SSEEventSource,
    SSEPriority,
    ThumbnailJobPriority,
    ThumbnailJobStatus,
    ThumbnailJobType,
    VideoAutomationMode,
)
from ...models.shared_models import ThumbnailGenerationJobCreate
from ...utils.time_utils import (
    get_timezone_aware_timestamp_sync,
    utc_timestamp,
)

# Module constants
from .constants import (
    JOB_VALIDATION_ERRORS_KEY,
    JOB_VALIDATION_RESULT_VALID,
    JOB_VALIDATION_SANITIZED_KEY,
    JOB_VALIDATION_WARNINGS_KEY,
)

logger = get_service_logger(
    LoggerName.CAPTURE_PIPELINE, LogSource.PIPELINE
)  # Use service logger for capture pipeline domain


class JobCoordinationService:
    """
    Job coordination service for the capture pipeline domain.

    🎯 SCHEDULER-CENTRIC ARCHITECTURE: This service follows proper separation of concerns.
    The capture pipeline creates jobs but does NOT make timing decisions.

    ARCHITECTURAL PRINCIPLE:
    - Capture Pipeline: Creates jobs and queues them
    - SchedulerWorker: Coordinates timing and job execution
    - This maintains proper boundaries and prevents circular dependencies

    Responsibilities:
    - Queue thumbnail generation jobs (timing coordinated by scheduler)
    - Queue overlay generation jobs (timing coordinated by scheduler)
    - Maintain job status tracking and dependency coordination
    - NO direct scheduler calls (avoids sync/async mismatch)
    """

    def __init__(
        self,
        db: SyncDatabase,
        async_db: AsyncDatabase,
        settings_service,
        scheduler_service=None,
    ):
        """
        Initialize job coordination service with scheduler dependency.

        Args:
            db: Synchronized database connection
            async_db: Asynchronous database connection
            settings_service: SettingsService for configuration access
            scheduler_service: Optional SchedulerService for immediate operations
        """
        self.db = db

        # Core database operations (for status tracking only)
        self.settings_service = settings_service
        self.thumbnail_job_ops = SyncThumbnailJobOperations(db)
        self.video_ops = SyncVideoOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)

        # Scheduler authority (the new boss!)
        self.scheduler_service = scheduler_service  # Will be injected

        # Legacy services for backward compatibility (deprecated)
        self.job_queue_service: Optional[SyncJobQueueService] = (
            None  # Will be injected if available
        )
        self.video_pipeline_service = (
            None  # Will be injected - simplified video pipeline
        )

    def coordinate_thumbnail_job(
        self,
        image_id: int,
        priority: ThumbnailJobPriority = ThumbnailJobPriority.MEDIUM,
        job_context: Optional[
            Dict[str, Any]
        ] = None,  # Job context for future enhancement
    ) -> Dict[str, Any]:
        """
        🎯 SCHEDULER-CENTRIC: Route thumbnail generation through scheduler authority.

        All thumbnail requests now go through the SchedulerService to enforce
        the "scheduler says jump, pipelines say how high" philosophy.

        Args:
            image_id: Database image record ID
            priority: Job priority ('high', 'medium', 'low')
            job_context: Additional context for job execution

        Returns:
            Job coordination result with scheduler routing status
        """
        try:
            # Check if thumbnail generation is enabled
            if not self.check_thumbnail_generation_enabled():
                logger.debug(
                    f"Thumbnail generation disabled, skipping job for image {image_id}"
                )
                return {"success": False, "reason": "thumbnail_generation_disabled"}

            # 🎯 SCHEDULER-CENTRIC ARCHITECTURE COMPLIANCE:
            # The capture pipeline should NOT make timing decisions.
            # Instead, queue thumbnail jobs directly and let SchedulerWorker handle timing.
            # This maintains proper separation: capture pipeline creates jobs, scheduler coordinates timing.

            logger.debug(
                f"⚡ Queuing thumbnail job for image {image_id} - scheduler will coordinate timing"
            )

            # Use JobQueueService to queue the job directly (proper architecture)
            if self.job_queue_service:
                logger.debug(
                    f"Queuing thumbnail job for image {image_id} via JobQueueService - scheduler will coordinate timing"
                )
                job_id = self.job_queue_service.create_thumbnail_job(
                    image_id=image_id,
                    priority=priority,
                    job_type=ThumbnailJobType.SINGLE,
                    broadcast_sse=True,  # Enable SSE broadcasting
                )

                if job_id:
                    logger.debug(
                        f"✅ Queued thumbnail job {job_id} for image {image_id} - scheduler will coordinate execution"
                    )
                    return {
                        "success": True,
                        "job_id": job_id,
                        "method": "job_queue_service",
                        "note": "Scheduler will coordinate timing and execution",
                    }
                else:
                    logger.warning(
                        f"Failed to queue thumbnail job for image {image_id} via JobQueueService",
                        emoji=LogEmoji.WARNING,
                    )
                    return {
                        "success": False,
                        "error": "job_queue_service_failed",
                    }

            # Final fallback to direct database operations (not recommended)
            else:
                logger.warning(
                    f"Using direct database fallback for image {image_id} - scheduler and job queue not available"
                )

                job_data = ThumbnailGenerationJobCreate(
                    image_id=image_id,
                    priority=ThumbnailJobPriority(priority),
                    status=ThumbnailJobStatus.PENDING,
                    job_type=ThumbnailJobType.SINGLE,
                )

                job = self.thumbnail_job_ops.create_job(job_data)
                if job:
                    logger.debug(
                        f"Queued thumbnail job {job.id} for image {image_id} (direct database fallback)"
                    )
                    return {
                        "success": True,
                        "job_id": job.id,
                        "method": "direct_database_fallback",
                    }
                else:
                    logger.warning(
                        f"Failed to queue thumbnail job for image {image_id} (direct database fallback)"
                    )
                    return {"success": False, "error": "database_creation_failed"}

        except Exception as e:
            logger.error(f"Error coordinating thumbnail job for image {image_id}: {e}")
            return {"success": False, "error": str(e)}

    # Evaluate video automation triggers after capture
    def evaluate_video_automation_triggers(
        self, timelapse_id: int, image_count: int, capture_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate video automation triggers after image capture.

        Checks video automation settings and triggers appropriate video jobs.

        Args:
            timelapse_id: Timelapse identifier
            image_count: Current image count for milestone checks
            capture_metadata: Image capture metadata for context

        Returns:
            Video automation evaluation result with triggered jobs
        """
        try:
            triggered_jobs = []
            automation_settings = self.get_video_automation_settings(timelapse_id)

            if not automation_settings:
                return {
                    "success": True,
                    "triggered_jobs": [],
                    "reason": "no_automation_settings",
                }

            automation_mode = automation_settings.get(
                "VideoAutomationMode", VideoAutomationMode
            )

            # 🎯 SCHEDULER-CENTRIC: Per-capture automation is now handled by SchedulerWorker
            # after each successful capture. This ensures all timing decisions flow through
            # the scheduler authority. No autonomous video triggering happens here.
            if automation_mode == VideoAutomationMode.PER_CAPTURE:
                logger.debug(
                    f"✅ Per-capture automation enabled for timelapse {timelapse_id} - "
                    f"will be handled by scheduler after capture completes"
                )

            # Check milestone automation
            elif automation_mode == VideoAutomationMode.MILESTONE:
                milestone_results = self._check_milestone_triggers(
                    timelapse_id, image_count, automation_settings
                )
                triggered_jobs.extend(milestone_results)

            # Check scheduled automation
            elif automation_mode == VideoAutomationMode.SCHEDULED:
                scheduled_results = self._check_scheduled_triggers(
                    timelapse_id, automation_settings
                )
                triggered_jobs.extend(scheduled_results)

            logger.debug(
                f"Video automation evaluation for timelapse {timelapse_id}: {len(triggered_jobs)} jobs triggered"
            )

            return {
                "success": True,
                "triggered_jobs": triggered_jobs,
                "automation_mode": automation_mode,
                "total_jobs": len(triggered_jobs),
            }

        except Exception as e:
            logger.error(
                f"Error evaluating video automation for timelapse {timelapse_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def coordinate_video_job(
        self,
        timelapse_id: int,
        trigger_type: str,
        priority: JobPriority = JobPriority.MEDIUM,
        job_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        🎯 SCHEDULER-CENTRIC: Route video generation through scheduler authority.

        All video requests now go through the SchedulerService to enforce
        the "scheduler says jump, pipelines say how high" philosophy.

        Args:
            timelapse_id: Timelapse identifier
            trigger_type: Type of trigger ('per_capture', 'milestone', 'scheduled', 'manual')
            priority: Job priority based on trigger type
            job_context: Additional context for video generation

        Returns:
            Video job coordination result with scheduler routing status
        """
        try:
            # 🎯 SCHEDULER-CENTRIC: Route through scheduler authority (preferred)
            if self.scheduler_service:
                logger.debug(
                    f"⚡ Routing video job for timelapse {timelapse_id} through scheduler authority"
                )

                # Use scheduler worker's immediate video scheduling
                success = self.scheduler_service.get_scheduler_worker().schedule_immediate_video_generation(
                    timelapse_id=timelapse_id,
                    video_settings=job_context,
                    priority=priority,
                )

                if success:
                    logger.debug(
                        f"✅ Scheduled immediate video generation for timelapse {timelapse_id} via scheduler authority"
                    )
                    return {
                        "success": True,
                        "job_id": f"immediate_video_{timelapse_id}",  # Temporary ID for tracking
                        "method": "scheduler_authority",
                        "trigger_type": trigger_type,
                        "priority": priority,
                        "message": "Routed through scheduler authority",
                    }
                else:
                    logger.warning(
                        f"Scheduler authority rejected video job for timelapse {timelapse_id}"
                    )
                    return {"success": False, "error": "scheduler_rejected"}

            # Legacy fallback - Use simplified video pipeline service if available
            elif self.video_pipeline_service:
                logger.warning(
                    f"Using legacy video pipeline for timelapse {timelapse_id} - scheduler not available"
                )

                # Handle per-capture trigger separately (immediate processing)
                if trigger_type == "per_capture":
                    job_id = self.video_pipeline_service.evaluate_per_capture_trigger(
                        timelapse_id
                    )
                    if job_id:
                        logger.debug(
                            f"✅ Triggered per-capture video job {job_id} for timelapse {timelapse_id} via legacy video pipeline"
                        )
                        return {
                            "success": True,
                            "job_id": job_id,
                            "method": "legacy_video_pipeline_per_capture",
                            "trigger_type": trigger_type,
                            "priority": priority,
                        }
                    else:
                        return {"success": False, "reason": "per_capture_not_triggered"}
                else:
                    # For other triggers, create job through job service
                    job_id = self.video_pipeline_service.job_service.create_job(
                        timelapse_id=timelapse_id,
                        trigger_type=trigger_type,
                        priority=priority,
                        settings=job_context or {},
                    )

                    if job_id:
                        logger.debug(
                            f"Queued video job {job_id} for timelapse {timelapse_id} via legacy video pipeline",
                            emoji=LogEmoji.SUCCESS,
                        )
                        return {
                            "success": True,
                            "job_id": job_id,
                            "method": "legacy_video_pipeline_job_service",
                            "trigger_type": trigger_type,
                            "priority": priority,
                        }
                    else:
                        logger.warning(
                            f"Failed to queue video job for timelapse {timelapse_id} via legacy video pipeline"
                        )
                        return {
                            "success": False,
                            "error": "legacy_video_pipeline_job_creation_failed",
                        }

            # Final fallback to direct video operations (not recommended)
            else:
                logger.warning(
                    f"Using direct database fallback for timelapse {timelapse_id} - scheduler and video pipeline not available"
                )
                job_data = {
                    "timelapse_id": timelapse_id,
                    "trigger_type": trigger_type,
                    "priority": priority,
                    "settings": job_context or {},
                }

                # Use video operations to create job directly
                event_timestamp = get_timezone_aware_timestamp_sync(
                    self.settings_service
                )
                job_data["event_timestamp"] = event_timestamp.isoformat()
                job_id = self.video_ops.create_video_generation_job(job_data)

                if job_id:
                    logger.debug(
                        f"Queued video job {job_id} for timelapse {timelapse_id} (direct database fallback)"
                    )
                    return {
                        "success": True,
                        "job_id": job_id,
                        "method": "direct_database_fallback",
                        "trigger_type": trigger_type,
                        "priority": priority,
                    }
                else:
                    logger.warning(
                        f"Failed to queue video job for timelapse {timelapse_id} (direct database fallback)"
                    )
                    return {"success": False, "error": "database_creation_failed"}

        except Exception as e:
            logger.error(
                f"Error coordinating video job for timelapse {timelapse_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def coordinate_overlay_job(
        self,
        image_id: int,
        priority: JobPriority = JobPriority.MEDIUM,
        job_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        🎯 SCHEDULER-CENTRIC: Route overlay generation through scheduler authority.

        All overlay requests now go through the SchedulerService to enforce
        the "scheduler says jump, pipelines say how high" philosophy.

        Args:
            image_id: Database image record ID
            priority: Job priority ('high', 'medium', 'low')
            job_context: Additional context for overlay generation

        Returns:
            Overlay job coordination result with scheduler routing status
        """
        try:
            # 🎯 SCHEDULER-CENTRIC: Route through scheduler authority (preferred)
            if self.scheduler_service:
                logger.debug(
                    f"⚡ Routing overlay job for image {image_id} through scheduler authority"
                )

                # Use scheduler worker's immediate overlay scheduling
                success = self.scheduler_service.get_scheduler_worker().schedule_immediate_overlay_generation(
                    image_id=image_id, priority=priority
                )

                if success:
                    logger.debug(
                        f"Scheduled immediate overlay generation for image {image_id} via scheduler authority",
                        emoji=LogEmoji.SUCCESS,
                    )
                    return {
                        "success": True,
                        "job_id": f"immediate_overlay_{image_id}",  # Temporary ID for tracking
                        "method": "scheduler_authority",
                        "priority": priority,
                        "message": "Routed through scheduler authority",
                    }
                else:
                    logger.warning(
                        f"Scheduler authority rejected overlay job for image {image_id}"
                    )
                    return {"success": False, "error": "scheduler_rejected"}

            # Legacy fallback - overlay jobs not implemented in legacy systems
            else:
                logger.warning(
                    f"Overlay job coordination not available without scheduler for image {image_id}"
                )
                return {
                    "success": False,
                    "error": "overlay_coordination_requires_scheduler",
                    "message": "Overlay jobs require scheduler authority - legacy fallback not available",
                }

        except Exception as e:
            logger.error(f"Error coordinating overlay job for image {image_id}: {e}")
            return {"success": False, "error": str(e)}

    def check_thumbnail_generation_enabled(self) -> bool:
        """
        Check if thumbnail generation is globally enabled.

        Determines whether thumbnail jobs should be queued.

        Returns:
            True if thumbnail generation enabled, False otherwise
        """
        thumbnail_enabled = self.settings_service.get_setting(
            SETTING_KEY_THUMBNAIL_GENERATION_ENABLED
        )
        if thumbnail_enabled is None:
            thumbnail_enabled = DEFAULT_GENERATE_THUMBNAILS

        # Handle different value types properly
        if isinstance(thumbnail_enabled, bool):
            return thumbnail_enabled
        if isinstance(thumbnail_enabled, str):
            return thumbnail_enabled.lower() == BOOLEAN_TRUE_STRING

        # For any other type, convert to bool
        return bool(thumbnail_enabled)

    def get_job_priority_for_trigger(
        self, trigger_type: VideoAutomationMode
    ) -> JobPriority:
        """
        Get appropriate job priority for trigger type.

        Maps trigger types to job priorities for proper queue management.

        Args:
            trigger_type: Type of automation trigger

        Returns:
            Job priority enum for trigger type
        """
        trigger_priority_map = {
            VideoAutomationMode.IMMEDIATE: JobPriority.HIGH,
            VideoAutomationMode.MILESTONE: JobPriority.MEDIUM,
            VideoAutomationMode.PER_CAPTURE: JobPriority.LOW,
            VideoAutomationMode.SCHEDULED: JobPriority.MEDIUM,
            VideoAutomationMode.MANUAL: JobPriority.HIGH,
            VideoAutomationMode.THUMBNAIL: JobPriority.MEDIUM,
        }
        return trigger_priority_map.get(trigger_type, JobPriority.MEDIUM)

    def get_video_automation_settings(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Get video automation settings for timelapse.

        Retrieves video automation configuration for trigger evaluation.

        Args:
            timelapse_id: Timelapse identifier

        Returns:
            Video automation settings dictionary
        """
        # Get video automation settings from timelapse
        try:

            # Get timelapse data
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                logger.warning(f"Timelapse {timelapse_id} not found")
                return {}

            # Extract automation settings from timelapse
            automation_settings = {}

            automation_settings["VideoAutomationMode"] = timelapse.video_automation_mode
            automation_settings["milestone_config"] = timelapse.milestone_config
            automation_settings["schedule_config"] = timelapse.generation_schedule

            return automation_settings

        except Exception as e:
            logger.error(
                f"Error getting video automation settings for timelapse {timelapse_id}: {e}"
            )
            return {}

    def check_milestone_triggers(
        self, timelapse_id: int, current_image_count: int
    ) -> List[Dict[str, Any]]:
        """
        Check for milestone-based video triggers.

        Evaluates if current image count triggers milestone video generation.

        Args:
            timelapse_id: Timelapse identifier
            current_image_count: Current number of images in timelapse

        Returns:
            List of triggered milestone video jobs
        """
        try:
            # Get automation settings for this timelapse
            automation_settings = self.get_video_automation_settings(timelapse_id)

            # Check if milestone automation is enabled
            if not automation_settings:
                return []

            automation_mode = automation_settings.get("VideoAutomationMode")
            if automation_mode != VideoAutomationMode.MILESTONE:
                return []

            # Delegate to internal helper method
            return self._check_milestone_triggers(
                timelapse_id, current_image_count, automation_settings
            )

        except Exception as e:
            logger.error(
                f"Error checking milestone triggers for timelapse {timelapse_id}: {e}"
            )
            return []

    # Track job status across different job types
    def track_job_status(self, job_id: str, job_types: JobTypes) -> Dict[str, Any]:
        """
        Track status of coordinated background job.

        Monitors job execution status for workflow feedback.

        Args:
            job_id: Job identifier to track
            JobTypes: Type of job ('thumbnail', 'video', 'overlay')

        Returns:
            Current job status and metadata
        """
        try:

            job_status = {
                "job_id": job_id,
                "JobTypes": JobTypes,
                "status": JobStatus.UNKNOWN,
                "progress": 0,
                "metadata": {},
                "last_updated": None,
                "error_message": None,
            }

            if job_types == JobTypes.THUMBNAIL:
                # Track thumbnail job status
                try:
                    thumbnail_job = self.thumbnail_job_ops.get_job_by_id(int(job_id))
                    if thumbnail_job:
                        # Extract job properties with safe defaults
                        job_status.update(
                            {
                                "status": getattr(
                                    thumbnail_job, "status", ThumbnailJobStatus.UNKNOWN
                                ),
                                "priority": getattr(
                                    thumbnail_job,
                                    "priority",
                                    ThumbnailJobPriority.MEDIUM,
                                ),
                                "created_at": getattr(
                                    thumbnail_job, "created_at", None
                                ),
                                "updated_at": getattr(
                                    thumbnail_job, "updated_at", None
                                ),
                                "progress": self._calculate_job_progress(
                                    getattr(thumbnail_job, "status", JobStatus.UNKNOWN),
                                    JobTypes.THUMBNAIL,
                                ),
                                "metadata": {
                                    "image_id": getattr(
                                        thumbnail_job, "image_id", None
                                    ),
                                    "JobTypes_detail": getattr(
                                        thumbnail_job,
                                        "JobTypes",
                                        ThumbnailJobType.SINGLE,
                                    ),
                                    "processing_attempts": getattr(
                                        thumbnail_job, "processing_attempts", 0
                                    ),
                                },
                            }
                        )

                        if getattr(thumbnail_job, "error_message", None):
                            job_status["error_message"] = thumbnail_job.error_message
                    else:
                        job_status["status"] = "not_found"

                except Exception as thumb_error:
                    logger.warning(
                        f"Error tracking thumbnail job {job_id}: {thumb_error}"
                    )
                    job_status["error_message"] = f"tracking_error: {thumb_error}"

            elif job_types == JobTypes.VIDEO_GENERATION:
                # Track video job status
                try:
                    video_job = self.video_ops.get_video_generation_job_by_id(
                        int(job_id)
                    )
                    if video_job:
                        job_status.update(
                            {
                                "status": getattr(
                                    video_job, "status", JobStatus.UNKNOWN
                                ),
                                "priority": getattr(
                                    video_job, "priority", JobPriority.MEDIUM
                                ),
                                "created_at": getattr(video_job, "created_at", None),
                                "updated_at": getattr(video_job, "updated_at", None),
                                "progress": self._calculate_job_progress(
                                    getattr(video_job, "status", JobStatus.UNKNOWN),
                                    JobTypes.VIDEO_GENERATION,
                                ),
                                "metadata": {
                                    "timelapse_id": getattr(
                                        video_job, "timelapse_id", None
                                    ),
                                    "trigger_type": getattr(
                                        video_job,
                                        "trigger_type",
                                        VideoAutomationMode.UNKNOWN,
                                    ),
                                    "output_path": getattr(
                                        video_job, "output_path", None
                                    ),
                                    "processing_time_minutes": getattr(
                                        video_job, "processing_time_minutes", 0
                                    ),
                                },
                            }
                        )

                        if getattr(video_job, "error_message", None):
                            job_status["error_message"] = video_job.error_message
                    else:
                        job_status["status"] = "not_found"

                except Exception as video_error:
                    logger.warning(f"Error tracking video job {job_id}: {video_error}")
                    job_status["error_message"] = f"tracking_error: {video_error}"

            elif job_types == JobTypes.OVERLAY:
                # TODO: Finish writing this method
                # Track overlay job status (if overlay jobs are implemented)
                try:
                    # Note: Overlay jobs might be handled differently
                    # This is a placeholder for future overlay job tracking
                    # Overlay job tracking not yet implemented
                    job_status.update(
                        {
                            "status": OverlayJobStatus.NOT_IMPLEMENTED,
                            "metadata": {
                                "note": "Overlay job tracking not yet implemented"
                            },
                        }
                    )
                except Exception as overlay_error:
                    logger.warning(
                        f"Error tracking overlay job {job_id}: {overlay_error}"
                    )
                    job_status["error_message"] = f"tracking_error: {overlay_error}"

            else:
                job_status["error_message"] = f"unsupported_JobTypes: {JobTypes}"

            # Add tracking timestamp

            job_status["tracked_at"] = utc_timestamp()

            logger.debug(
                f" Job status tracking - {job_types} {job_id}: {job_status['status']}",
                emoji=LogEmoji.CHART,
            )

            return job_status

        except Exception as e:
            logger.error(f"Error tracking job status for {job_types} {job_id}: {e}")
            return {
                "job_id": job_id,
                "job_types": job_types,
                "status": JobStatus.TRACKING_ERROR,
                "error_message": str(e),
                "tracked_at": utc_timestamp(),
            }

    def cancel_pending_jobs(
        self,
        camera_id: Optional[int] = None,
        timelapse_id: Optional[int] = None,
        job_type: JobTypes = JobTypes.UNKNOWN,
    ) -> Dict[str, Any]:
        """
        Cancel pending background jobs based on criteria.

        Cancels queued jobs when camera/timelapse is stopped or disabled.

        Args:
            camera_id: Camera identifier for targeted cancellation
            timelapse_id: Timelapse identifier for targeted cancellation
            JobTypes: Job type for targeted cancellation

        Returns:
            Cancellation result with affected job counts
        """
        try:

            cancellation_results = {
                "success": True,
                "cancelled_jobs": [],
                "failed_cancellations": [],
                "total_cancelled": 0,
                "criteria": {
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "job_type": job_type,
                },
            }

            logger.info(
                f"🚫 Cancelling pending jobs - Camera: {camera_id}, Timelapse: {timelapse_id}, Type: {job_type}",
                emoji=LogEmoji.CANCELED,
            )

            # Cancel thumbnail jobs
            if not job_type or job_type == JobTypes.THUMBNAIL:
                try:
                    if camera_id:
                        # Cancel thumbnail jobs by camera (via images)
                        cancelled_thumbnails = (
                            self.thumbnail_job_ops.cancel_jobs_by_camera(camera_id)
                        )
                    elif timelapse_id:
                        # Cancel thumbnail jobs by timelapse (via images)
                        cancelled_thumbnails = (
                            self.thumbnail_job_ops.cancel_jobs_by_timelapse(
                                timelapse_id
                            )
                        )
                    else:
                        # Cancel all pending thumbnail jobs
                        cancelled_thumbnails = (
                            self.thumbnail_job_ops.cancel_jobs_by_status(
                                ThumbnailJobStatus.PENDING
                            )
                        )

                    if cancelled_thumbnails > 0:
                        cancellation_results["cancelled_jobs"].append(
                            {
                                "job_type": JobTypes.THUMBNAIL,
                                "count": cancelled_thumbnails,
                            }
                        )
                        cancellation_results["total_cancelled"] += cancelled_thumbnails

                except Exception as thumb_error:
                    logger.warning(f"Error cancelling thumbnail jobs: {thumb_error}")
                    cancellation_results["failed_cancellations"].append(
                        {"job_type": JobTypes.THUMBNAIL, "error": str(thumb_error)}
                    )

            # Cancel video jobs
            if not job_type or job_type == JobTypes.VIDEO_GENERATION:
                try:
                    if timelapse_id:
                        # Cancel video jobs by timelapse
                        cancelled_videos = (
                            self.video_ops.cancel_pending_jobs_by_timelapse(
                                timelapse_id
                            )
                        )
                    elif camera_id:
                        # Cancel video jobs by camera (via timelapses)
                        cancelled_videos = self.video_ops.cancel_pending_jobs_by_camera(
                            camera_id
                        )
                    else:
                        # Cancel all pending video jobs
                        cancelled_videos = self.video_ops.cancel_pending_jobs()

                    if cancelled_videos > 0:
                        cancellation_results["cancelled_jobs"].append(
                            {
                                "job_type": JobTypes.VIDEO_GENERATION,
                                "count": cancelled_videos,
                            }
                        )
                        cancellation_results["total_cancelled"] += cancelled_videos

                except Exception as video_error:
                    logger.warning(f"Error cancelling video jobs: {video_error}")
                    cancellation_results["failed_cancellations"].append(
                        {
                            "job_type": JobTypes.VIDEO_GENERATION,
                            "error": str(video_error),
                        }
                    )

            # Handle overlay jobs (if implemented)
            if not job_type or job_type == JobTypes.OVERLAY:
                try:
                    # Placeholder for overlay job cancellation
                    # Note: Overlay jobs might be handled differently
                    logger.debug("Overlay job cancellation not yet implemented")

                except Exception as overlay_error:
                    logger.warning(f"Error cancelling overlay jobs: {overlay_error}")
                    cancellation_results["failed_cancellations"].append(
                        {"JobTypes": JobTypes.OVERLAY, "error": str(overlay_error)}
                    )

            # Update success status based on failures
            if cancellation_results["failed_cancellations"]:
                cancellation_results["success"] = False

            # Add timestamp

            cancellation_results["cancelled_at"] = utc_timestamp()

            logger.info(
                f"Job cancellation completed: {cancellation_results['total_cancelled']} jobs cancelled, "
                f"{len(cancellation_results['failed_cancellations'])} failures",
                emoji=LogEmoji.SUCCESS,
            )

            return cancellation_results

        except Exception as e:
            logger.error(f"Error cancelling pending jobs: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_cancelled": 0,
                "criteria": {
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "job_types": JobTypes,
                },
            }

    def get_job_queue_status(self) -> Dict[str, Any]:
        """
        Get current status of all job queues.

        Provides overview of job queue health and backlog.

        Returns:
            Job queue status with counts and health metrics
        """
        try:

            queue_status = {
                "success": True,
                "timestamp": utc_timestamp(),
                "overall_health": HealthStatus.HEALTHY,
                "total_pending": 0,
                "total_processing": 0,
                "queues": {},
            }

            # Get thumbnail queue status
            try:
                thumbnail_stats = self.thumbnail_job_ops.get_job_statistics()
                thumbnail_queue = {
                    "pending": thumbnail_stats.get("pending_count", 0),
                    "processing": thumbnail_stats.get("processing_count", 0),
                    "completed_today": thumbnail_stats.get("completed_today", 0),
                    "failed_today": thumbnail_stats.get("failed_today", 0),
                    "average_processing_time_minutes": thumbnail_stats.get(
                        "avg_processing_time", 0
                    ),
                    "oldest_pending_age_minutes": thumbnail_stats.get(
                        "oldest_pending_age", 0
                    ),
                    "health": HealthStatus.HEALTHY,
                }

                # Determine thumbnail queue health
                if thumbnail_queue[ThumbnailJobStatus.PENDING] > 100:
                    thumbnail_queue["health"] = HealthStatus.OVERLOADED
                elif thumbnail_queue[ThumbnailJobStatus.PENDING] > 50:
                    thumbnail_queue["health"] = HealthStatus.DEGRADED
                elif (
                    thumbnail_queue["failed_today"] > thumbnail_queue["completed_today"]
                ):
                    thumbnail_queue["health"] = HealthStatus.UNHEALTHY

                queue_status["queues"][JobTypes.THUMBNAIL] = thumbnail_queue
                queue_status["total_pending"] += thumbnail_queue[
                    ThumbnailJobStatus.PENDING
                ]
                queue_status["total_processing"] += thumbnail_queue[
                    ThumbnailJobStatus.PROCESSING
                ]

            except Exception as thumb_error:
                logger.warning(f"Error getting thumbnail queue status: {thumb_error}")
                queue_status["queues"][JobTypes.THUMBNAIL] = {
                    "error": str(thumb_error),
                    "health": HealthStatus.UNKNOWN,
                }

            # Get video queue status
            try:
                video_stats = self.video_ops.get_video_job_statistics()
                video_queue = {
                    JobStatus.PENDING: video_stats.get("pending_count", 0),
                    JobStatus.PROCESSING: video_stats.get("processing_count", 0),
                    JobStatus.COMPLETED: video_stats.get("completed_today", 0),
                    JobStatus.FAILED: video_stats.get("failed_today", 0),
                    "average_processing_time_minutes": video_stats.get(
                        "avg_processing_time", 0
                    ),
                    "oldest_pending_age_minutes": video_stats.get(
                        "oldest_pending_age", 0
                    ),
                    "health": HealthStatus.HEALTHY,
                }

                # Determine video queue health
                if video_queue[JobStatus.PENDING] >= VIDEO_QUEUE_ERROR_THRESHOLD:
                    video_queue["health"] = HealthStatus.OVERLOADED
                elif video_queue[JobStatus.PENDING] >= VIDEO_QUEUE_WARNING_THRESHOLD:
                    video_queue["health"] = HealthStatus.DEGRADED
                elif video_queue["failed_today"] > video_queue["completed_today"]:
                    video_queue["health"] = HealthStatus.UNHEALTHY

                queue_status["queues"][JobTypes.VIDEO_GENERATION] = video_queue
                queue_status["total_pending"] += video_queue[JobStatus.PENDING]
                queue_status["total_processing"] += video_queue[JobStatus.PROCESSING]

            except Exception as video_error:
                logger.warning(f"Error getting video queue status: {video_error}")
                queue_status["queues"][JobTypes.VIDEO_GENERATION] = {
                    "error": str(video_error),
                    "health": HealthStatus.UNKNOWN,
                }

            # Get overlay queue status (placeholder)
            try:
                # Note: Overlay jobs might be handled differently
                overlay_queue = {
                    OverlayJobStatus.PENDING: 0,
                    OverlayJobStatus.PROCESSING: 0,
                    OverlayJobStatus.COMPLETED: 0,
                    OverlayJobStatus.FAILED: 0,
                    "health": OverlayJobStatus.NOT_IMPLEMENTED,
                    "note": "Overlay queue monitoring not yet implemented",
                }
                queue_status["queues"][JobTypes.OVERLAY] = overlay_queue

            except Exception as overlay_error:
                logger.warning(f"Error getting overlay queue status: {overlay_error}")
                queue_status["queues"][JobTypes.OVERLAY] = {
                    "error": str(overlay_error),
                    "health": HealthStatus.UNKNOWN,
                }

            # Determine overall health
            queue_healths = [
                queue.get("health", HealthStatus.UNKNOWN)
                for queue in queue_status["queues"].values()
            ]

            if HealthStatus.OVERLOADED in queue_healths:
                queue_status["overall_health"] = HealthStatus.OVERLOADED
            elif HealthStatus.UNHEALTHY in queue_healths:
                queue_status["overall_health"] = HealthStatus.UNHEALTHY
            elif HealthStatus.DEGRADED in queue_healths:
                queue_status["overall_health"] = HealthStatus.DEGRADED
            elif HealthStatus.UNKNOWN in queue_healths:
                queue_status["overall_health"] = HealthStatus.UNKNOWN
            else:
                queue_status["overall_health"] = HealthStatus.HEALTHY

            # Add summary metrics
            # Job queue health summary using proper constants
            queue_status["summary"] = {
                "total_queues": len(queue_status["queues"]),
                "healthy_queues": len(
                    [h for h in queue_healths if h == HealthStatus.HEALTHY]
                ),
                "unhealthy_queues": len(
                    [
                        h
                        for h in queue_healths
                        if h
                        in [
                            HealthStatus.DEGRADED,
                            HealthStatus.UNHEALTHY,
                            HealthStatus.OVERLOADED,
                        ]
                    ]
                ),
                "total_active_jobs": queue_status["total_pending"]
                + queue_status["total_processing"],
            }

            logger.debug(
                f"Job queue status: {queue_status['overall_health']} - {queue_status['total_pending']} pending",
                emoji=LogEmoji.QUEUE,
            )

            return queue_status

        except Exception as e:
            logger.error(f"Error getting job queue status: {e}")
            return {
                "success": False,
                "error": str(e),
                "overall_health": HealthStatus.ERROR,
                "timestamp": utc_timestamp(),
            }

    def _determine_thumbnail_priority(self, capture_context: Dict[str, Any]) -> str:
        """
        Determine appropriate priority for thumbnail job.

        Internal helper for thumbnail job priority assignment.

        Args:
            capture_context: Context information from capture workflow

        Returns:
            Priority string for thumbnail job
        """

        # Check if this is a retry or urgent capture
        if capture_context.get("is_retry", False):
            return JobPriority.HIGH
        elif capture_context.get("capture_type") == VideoAutomationMode.MANUAL:
            return JobPriority.HIGH
        elif capture_context.get("timelapse_priority") == JobPriority.HIGH:
            return JobPriority.MEDIUM
        else:
            return JobPriority.MEDIUM  # Default priority

    def _trigger_per_capture_video(
        self, timelapse_id: int, automation_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🎯 SCHEDULER-CENTRIC TRANSFORMATION: Per-capture triggers moved to SchedulerWorker.

        This method is now disabled as part of the scheduler-centric architecture transformation.
        Per-capture video generation is now handled by SchedulerWorker after each successful
        capture to ensure all timing decisions flow through the scheduler authority.

        Args:
            timelapse_id: Timelapse identifier (unused)
            automation_settings: Video automation configuration (unused)

        Returns:
            Disabled result indicating scheduler handles this
        """
        logger.debug(
            f"Per-capture trigger for timelapse {timelapse_id} - "
            f"delegated to SchedulerWorker (scheduler-centric architecture)",
            emoji=LogEmoji.SCHEDULER,
        )

        return {
            "success": False,
            "reason": "per_capture_moved_to_scheduler",
            "message": "Per-capture triggers are now handled by SchedulerWorker",
        }

    def _check_milestone_triggers(
        self, timelapse_id: int, image_count: int, automation_settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check milestone triggers for video generation using simplified pipeline.

        Internal helper for milestone-based video automation.

        Args:
            timelapse_id: Timelapse identifier
            image_count: Current image count
            automation_settings: Video automation configuration

        Returns:
            List of triggered milestone video jobs
        """
        triggered_jobs = []

        try:
            # Note: Milestone triggers are handled by video pipeline automation cycle
            # This method is called for specific per-capture evaluations
            # The video pipeline will evaluate all milestones during its automation cycle

            # For now, we delegate to the coordinate_video_job method for compatibility
            # The actual milestone evaluation logic is in VideoWorkflowService
            milestone_config = automation_settings.get("milestone_config", {})
            if isinstance(milestone_config, str):
                milestone_config = json.loads(milestone_config)

            thresholds = milestone_config.get("thresholds", [])

            for threshold in thresholds:
                if image_count == threshold:
                    # Trigger milestone video generation
                    # Note: Duplicate checking is handled by the video generation system
                    result = self.coordinate_video_job(
                        timelapse_id=timelapse_id,
                        trigger_type=VideoAutomationMode.MILESTONE,
                        priority=JobPriority.MEDIUM,
                        job_context={
                            "threshold": threshold,
                            "image_count": image_count,
                        },
                    )
                    if result.get("success"):
                        triggered_jobs.append(result)

        except Exception as e:
            logger.error(
                f"Error checking milestone triggers for timelapse {timelapse_id}: {e}"
            )

        return triggered_jobs

    def _check_scheduled_triggers(
        self, timelapse_id: int, automation_settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check scheduled triggers for video generation using simplified pipeline.

        Internal helper for time-based video automation.

        Args:
            timelapse_id: Timelapse identifier
            automation_settings: Video automation configuration

        Returns:
            List of triggered scheduled video jobs
        """
        triggered_jobs = []

        try:
            # Note: Scheduled triggers are handled by video pipeline automation cycle
            # This method is called for specific per-capture evaluations
            # The video pipeline will evaluate all scheduled triggers during its automation cycle

            # For now, we delegate to the coordinate_video_job method for compatibility
            # The actual scheduled evaluation logic is in VideoWorkflowService
            schedule_config = automation_settings.get("schedule_config", {})
            if schedule_config:
                result = self.coordinate_video_job(
                    timelapse_id=timelapse_id,
                    trigger_type=VideoAutomationMode.SCHEDULED,
                    priority=JobPriority.LOW,  # Scheduled videos are low priority
                    job_context={"schedule": schedule_config},
                )
                if result.get("success"):
                    triggered_jobs.append(result)

        except Exception as e:
            logger.error(
                f"Error checking scheduled triggers for timelapse {timelapse_id}: {e}"
            )

        return triggered_jobs

    def _calculate_job_progress(
        self, job_status: JobStatus, job_types: JobTypes
    ) -> int:
        """
        Calculate job progress percentage based on status.

        Args:
            job_status: Current job status
            job_types: Type of job

        Returns:
            Progress percentage (0-100)
        """

        if job_types == JobTypes.THUMBNAIL:
            status_progress_map = {
                JobStatus.PENDING: 0,
                JobStatus.PROCESSING: 50,
                JobStatus.COMPLETED: 100,
                JobStatus.FAILED: 0,
            }
        elif job_types == JobTypes.VIDEO_GENERATION:
            status_progress_map = {
                JobStatus.PENDING: 0,
                JobStatus.PROCESSING: 25,
                "encoding": 75,  # Video encoding is considered 75% complete
                JobStatus.COMPLETED: 100,
                JobStatus.FAILED: 0,
            }
        else:
            # Generic progress mapping
            status_progress_map = {
                JobStatus.PENDING: 0,
                JobStatus.PROCESSING: 50,
                JobStatus.COMPLETED: 100,
                JobStatus.FAILED: 0,
            }

        return status_progress_map.get(job_status, 0)

    def _validate_job_parameters(
        self, job_types: JobTypes, job_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate job parameters before coordination.

        Internal helper for job parameter validation.

        Args:
            JobTypes: Type of job to validate
            job_parameters: Job parameters to validate

        Returns:
            Validation result with status and errors
        """
        # Validate job parameters with constants
        try:
            validation_result = {
                "valid": JOB_VALIDATION_RESULT_VALID,
                JOB_VALIDATION_ERRORS_KEY: [],
                JOB_VALIDATION_WARNINGS_KEY: [],
                JOB_VALIDATION_SANITIZED_KEY: job_parameters.copy(),
            }

            if job_types == JobTypes.THUMBNAIL:
                # Validate thumbnail job parameters
                if "image_id" not in job_parameters:
                    validation_result["errors"].append(
                        "image_id is required for thumbnail jobs"
                    )
                    validation_result["valid"] = False
                elif not isinstance(job_parameters["image_id"], int):
                    validation_result["errors"].append("image_id must be an integer")
                    validation_result["valid"] = False

                # Validate priority
                valid_priorities = cast(List[Enum], list(JobPriority))
                priority = job_parameters.get("priority", JobPriority.MEDIUM)
                sanitized_priority = parse_enum(
                    JobPriority,
                    priority,
                    valid_members=valid_priorities,
                    default=JobPriority.MEDIUM,
                )
                if sanitized_priority != priority:
                    validation_result["warnings"].append(
                        f"Invalid priority '{priority}', using '{sanitized_priority.name.lower()}'"
                    )
                validation_result["sanitized_parameters"][
                    "priority"
                ] = sanitized_priority

            elif job_types == JobTypes.VIDEO_GENERATION:
                # Validate video job parameters
                if "timelapse_id" not in job_parameters:
                    validation_result["errors"].append(
                        "timelapse_id is required for video jobs"
                    )
                    validation_result["valid"] = False
                elif not isinstance(job_parameters["timelapse_id"], int):
                    validation_result["errors"].append(
                        "timelapse_id must be an integer"
                    )
                    validation_result["valid"] = False

                # Validate trigger type
                # trigger_type = job_parameters.get(
                #     "trigger_type", VideoAutomationMode.MANUAL
                # )
                # sanitized_trigger_type = parse_enum(
                #     VideoAutomationMode,
                #     trigger_type,
                #     valid_members=valid_triggers,
                #     default=VideoAutomationMode.MANUAL,
                # )
                # valid_triggers = cast(List[Enum], list(VideoAutomationMode))

                # if sanitized_trigger_type != trigger_type:
                #     validation_result["warnings"].append(
                #         f"Invalid trigger_type '{trigger_type}', using '{sanitized_trigger_type.name.lower()}'"
                #     )
                # validation_result["sanitized_parameters"][
                #     "trigger_type"
                # ] = sanitized_trigger_type

            elif job_types == JobTypes.OVERLAY:
                # Validate overlay job parameters (if implemented)
                validation_result["warnings"].append(
                    "Overlay job validation not fully implemented"
                )

            else:
                validation_result["errors"].append(f"Unknown job type: {JobTypes}")
                validation_result["valid"] = False

            return validation_result

        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Parameter validation error: {str(e)}"],
                "warnings": [],
                "sanitized_parameters": job_parameters,
            }

    def _broadcast_job_coordination_events(
        self, job_results: List[Dict[str, Any]]
    ) -> bool:
        """
        Broadcast SSE events for job coordination activities.

        Internal helper for job coordination event broadcasting.

        Args:
            job_results: List of job coordination results

        Returns:
            True if broadcasting successful, False otherwise
        """
        try:

            events_broadcast = 0

            for job_result in job_results:
                try:
                    if not job_result.get("success", False):
                        continue  # Skip failed job results

                    job_types_value = job_result.get("JobTypes")
                    if job_types_value is None:
                        job_types_value = JobTypes.UNKNOWN
                    job_id = job_result.get("job_id")

                    if not job_id:
                        continue  # Skip if no job ID

                    # Create event data for SSE
                    event_data = {
                        "job_id": job_id,
                        "job_types": job_types_value,
                        "priority": job_result.get("priority", JobPriority.MEDIUM),
                        "trigger_type": job_result.get(
                            "trigger_type", "workflow_coordination"
                        ),
                        "method": job_result.get("method", "coordination_service"),
                        "coordinated_at": utc_timestamp(),
                    }

                    # Add type-specific data
                    if job_types_value == JobTypes.THUMBNAIL:
                        event_data["image_id"] = job_result.get("image_id")
                    elif job_types_value == JobTypes.VIDEO_GENERATION:
                        event_data["timelapse_id"] = job_result.get("timelapse_id")

                    # Broadcast SSE event using operations
                    self.sse_ops.create_event(
                        event_type=SSEEvent.JOB_CREATED,
                        event_data=event_data,
                        priority=SSEPriority.NORMAL,
                        source=SSEEventSource.CAPTURE_PIPELINE,
                    )
                    events_broadcast += 1

                except Exception as event_error:
                    logger.warning(
                        f"Error broadcasting job coordination event: {event_error}"
                    )
                    continue

            if events_broadcast > 0:
                logger.debug(
                    f"Broadcast {events_broadcast} job coordination events",
                    emoji=LogEmoji.BROADCAST,
                )

            return events_broadcast > 0

        except Exception as e:
            logger.error(f"Error broadcasting job coordination events: {e}")
            return False
