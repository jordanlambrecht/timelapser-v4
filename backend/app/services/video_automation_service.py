"""
Video Automation Service for Timelapser V4

This service orchestrates automated video generation with multiple trigger modes:
- Per-Capture: Generate after each image capture (with throttling)
- Scheduled: Time-based triggers (daily/weekly/custom)
- Milestone: Trigger at image count thresholds
- Manual: User-initiated generation

Follows AI-CONTEXT patterns:
- Entity-based timelapse
- Settings inheritance (camera defaults → timelapse overrides)
- Timezone-aware calculations
- psycopg3 sync database connections
- SSE event broadcasting
"""

from loguru import logger
import json
from typing import Optional, Dict, Any, List, Tuple

from app.database import SyncDatabase
from .video_service import SyncVideoService
from ..database.video_operations import SyncVideoOperations
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..database.settings_operations import SyncSettingsOperations
from ..models.shared_models import (
    VideoGenerationJob,
    VideoGenerationJobWithDetails,
    VideoGenerationJobCreate,
)
from ..utils.timezone_utils import (
    create_timezone_aware_datetime,
    get_timezone_aware_timestamp_sync,
    format_filename_timestamp,
    get_timezone_aware_timestamp_string_sync,
)
from ..constants import (
    EVENT_VIDEO_JOB_QUEUED,
    EVENT_VIDEO_JOB_STARTED,
    EVENT_VIDEO_JOB_COMPLETED,
    DEFAULT_PER_CAPTURE_THROTTLE_MINUTES,
    DEFAULT_OVERLAY_SETTINGS,
)


class VideoQueue:
    """
    Video generation job queue manager

    Handles job creation, prioritization, and processing with proper
    database integration and error handling.
    """

    def __init__(self, db: SyncDatabase):
        self.db = db
        self.video_ops = SyncVideoOperations(db)
        self.settings_ops = SyncSettingsOperations(db)

    def add_job(
        self,
        timelapse_id: int,
        trigger_type: str,
        priority: str = "medium",
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Add a new video generation job to the queue

        Args:
            timelapse_id: ID of the timelapse to generate video from
            trigger_type: Type of trigger ('per_capture', 'scheduled', 'milestone', 'manual')
            priority: Job priority ('low', 'medium', 'high')
            settings: Optional video generation settings

        Returns:
            Job ID if successful, None if failed
        """
        try:
            # Use operations layer for database operations
            job_data = {
                "timelapse_id": timelapse_id,
                "trigger_type": trigger_type,
                "priority": priority,
                "settings": json.dumps(settings or {}),
            }
            
            # Calculate timestamp for database operation
            event_timestamp = get_timezone_aware_timestamp_sync(self.settings_ops)
            job_id = self.video_ops.create_video_generation_job(job_data, event_timestamp)
            
            if job_id:
                logger.info(
                    f"Added video generation job {job_id} for timelapse {timelapse_id} (trigger: {trigger_type})"
                )
            
            return job_id

        except Exception as e:
            logger.error(f"Failed to add video generation job: {e}")
            return None

    def get_next_job(self) -> Optional[VideoGenerationJobWithDetails]:
        """
        Get the next pending job from the queue

        Returns jobs in priority order: high > medium > low
        Within same priority, returns oldest job first (FIFO)
        """
        try:
            # Use operations layer for database operations
            pending_jobs = self.video_ops.get_pending_video_generation_jobs()
            
            if not pending_jobs:
                return None
            
            # Sort by priority and creation time (operations layer returns in correct order)
            # The operations layer should handle this, but we ensure correct priority order here
            priority_order = {'high': 1, 'medium': 2, 'low': 3}
            
            sorted_jobs = sorted(
                pending_jobs,
                key=lambda x: (priority_order.get(getattr(x, 'priority', 'medium'), 4), x.created_at)
            )
            
            return sorted_jobs[0] if sorted_jobs else None

        except Exception as e:
            logger.error(f"Failed to get next job from queue: {e}")
            return None

    def start_job(self, job_id: int) -> bool:
        """Mark a job as started"""
        try:
            # Use operations layer for database operations
            # Calculate timestamp for database operation
            event_timestamp = get_timezone_aware_timestamp_sync(self.settings_ops)
            return self.video_ops.start_video_generation_job(job_id, event_timestamp)

        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")
            return False

    def complete_job(
        self,
        job_id: int,
        success: bool,
        video_id: Optional[int] = None,
        video_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Mark a job as completed or failed"""
        try:
            # Use operations layer for database operations
            # Calculate timestamp for database operation
            event_timestamp = get_timezone_aware_timestamp_sync(self.settings_ops)
            return self.video_ops.complete_video_generation_job(
                job_id=job_id,
                success=success,
                error_message=error_message,
                video_path=video_path,
                event_timestamp=event_timestamp
            )

        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")
            return False

    def get_queue_status(self) -> Dict[str, int]:
        """Get queue statistics by status."""
        try:
            # Use operations layer for database operations
            stats = self.video_ops.get_queue_status()
            
            # Return defaults for missing stats
            default_stats = {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            }
            default_stats.update(stats)

            return default_stats

        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {"pending": 0, "processing": 0, "completed": 0, "failed": 0}

    def get_queue_jobs(
        self, status: Optional[str] = None, limit: int = 50
    ) -> List[VideoGenerationJobWithDetails]:
        """Get video generation jobs with optional status filtering."""
        try:
            # Use operations layer for database operations
            return self.video_ops.get_video_generation_jobs_by_status(status=status, limit=limit)

        except Exception as e:
            logger.error(f"Error getting queue jobs: {e}")
            return []


class VideoAutomationService:
    """
    Automated video generation workflow business logic.

    Responsibilities:
    - Scheduling triggers (per-capture/milestone/scheduled)
    - Job queue prioritization
    - Automation rule evaluation
    - Throttling logic

    Interactions:
    - Uses VideoOperations for job queue
    - Calls VideoService for generation
    - Monitors TimelapseService for trigger conditions
    """

    def __init__(self, db: SyncDatabase, timelapse_service=None):
        self.db = db
        self.queue = VideoQueue(db)
        self.video_service = SyncVideoService(db)
        self.timelapse_service = timelapse_service
        
        # Operations layer composition
        self.video_ops = SyncVideoOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)
        self.settings_ops = SyncSettingsOperations(db)

        # Throttling settings
        self.per_capture_throttle_minutes = DEFAULT_PER_CAPTURE_THROTTLE_MINUTES
        self.max_concurrent_jobs = 3

    def get_effective_automation_settings(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Get effective automation settings using inheritance pattern

        Follows AI-CONTEXT pattern: timelapse settings override camera defaults
        """
        try:
            # Use operations layer for database operations
            return self.video_ops.get_timelapse_automation_settings(timelapse_id)

        except Exception as e:
            logger.error(
                f"Failed to get automation settings for timelapse {timelapse_id}: {e}"
            )
            return {"video_automation_mode": "manual"}

    def should_throttle_per_capture(self, camera_id: int) -> bool:
        """
        Check if per-capture generation should be throttled

        Returns True if last generation was within throttle window
        """
        try:
            # Use operations layer for database operations
            return self.video_ops.check_per_capture_throttle(camera_id, self.per_capture_throttle_minutes)

        except Exception as e:
            logger.error(f"Failed to check throttling for camera {camera_id}: {e}")
            return True  # Err on the side of caution

    def trigger_per_capture_generation(self, camera_id: int) -> bool:
        """
        Trigger per-capture video generation if enabled and not throttled

        Called after each successful image capture
        """
        try:
            # Get active timelapse for camera using operations layer
            from ..database.timelapse_operations import SyncTimelapseOperations
            timelapse_ops = SyncTimelapseOperations(self.db)
            
            timelapse = timelapse_ops.get_active_timelapse_for_camera(camera_id)
            if not timelapse:
                return False

            timelapse_id = timelapse.id

            # Get automation settings
            settings = self.get_effective_automation_settings(timelapse_id)

            if settings.get("video_automation_mode") != "per_capture":
                return False

            # Check throttling
            if self.should_throttle_per_capture(camera_id):
                logger.debug(f"Per-capture generation throttled for camera {camera_id}")
                return False

            # Add job to queue with low priority
            job_id = self.queue.add_job(
                timelapse_id=timelapse_id, trigger_type="per_capture", priority="low"
            )

            return job_id is not None

        except Exception as e:
            logger.error(
                f"Failed to trigger per-capture generation for camera {camera_id}: {e}"
            )
            return False

    def check_milestone_triggers(self) -> List[int]:
        """
        Check for milestone-based triggers across all active timelapses

        Returns list of job IDs created
        """
        job_ids = []

        try:
            # Get all timelapses with milestone automation enabled using operations layer
            milestone_timelapses = self.video_ops.get_milestone_automation_timelapses()
            
            for timelapse_data in milestone_timelapses:
                timelapse_id = timelapse_data["id"]
                image_count = timelapse_data["image_count"]
                milestone_config = timelapse_data["milestone_config"]

                if not milestone_config:
                    continue

                # Parse milestone config
                if isinstance(milestone_config, str):
                    milestone_config = json.loads(milestone_config)

                thresholds = milestone_config.get("thresholds", [])

                # Check if we've hit any thresholds
                for threshold in thresholds:
                    if image_count == threshold:
                        # Check if we already generated for this threshold
                        if self.video_ops.check_milestone_already_generated(timelapse_id, threshold):
                            continue  # Already generated for this threshold

                        # Add milestone job
                        job_id = self.queue.add_job(
                            timelapse_id=timelapse_id,
                            trigger_type="milestone",
                            priority="medium",
                            settings={
                                "threshold": threshold,
                                "image_count": image_count,
                            },
                        )

                        if job_id:
                            job_ids.append(job_id)
                            logger.info(
                                f"Triggered milestone video for timelapse {timelapse_id} at {threshold} images"
                            )

        except Exception as e:
            logger.error(f"Failed to check milestone triggers: {e}")

        return job_ids

    def check_scheduled_triggers(self) -> List[int]:
        """
        Check for scheduled triggers based on time-based automation

        Returns list of job IDs created
        """
        job_ids = []

        try:
            # Get timezone from settings using proper operations layer
            from ..database.settings_operations import SyncSettingsOperations
            settings_ops = SyncSettingsOperations(self.db)
            timezone_str = settings_ops.get_setting("timezone") or "UTC"

            # Get timelapses with scheduled automation using operations layer
            scheduled_timelapses = self.video_ops.get_scheduled_automation_timelapses()
            
            for timelapse_data in scheduled_timelapses:
                timelapse_id = timelapse_data["id"]
                schedule = timelapse_data["schedule"]

                if not schedule:
                    continue

                # Parse schedule config
                if isinstance(schedule, str):
                    schedule = json.loads(schedule)

                # Check if we should trigger based on schedule
                if self._should_trigger_scheduled(schedule, timezone_str):
                    # Check if we already generated today/this period
                    if not self._already_generated_for_period(
                        timelapse_id, schedule
                    ):
                        job_id = self.queue.add_job(
                            timelapse_id=timelapse_id,
                            trigger_type="scheduled",
                            priority="medium",
                            settings={"schedule": schedule},
                        )

                        if job_id:
                            job_ids.append(job_id)
                            logger.info(
                                f"Triggered scheduled video for timelapse {timelapse_id}"
                            )

        except Exception as e:
            logger.error(f"Failed to check scheduled triggers: {e}")

        return job_ids

    def _should_trigger_scheduled(
        self, schedule: Dict[str, Any], timezone_str: str
    ) -> bool:
        """Check if a scheduled trigger should fire now"""
        try:

            now = create_timezone_aware_datetime(timezone_str)

            schedule_type = schedule.get("type", "daily")
            schedule_time = schedule.get("time", "00:00")  # HH:MM format

            # Parse the scheduled time
            hour, minute = map(int, schedule_time.split(":"))

            if schedule_type == "daily":
                # Check if we're at the right time (within a minute window)
                return now.hour == hour and now.minute == minute

            elif schedule_type == "weekly":
                schedule_day = schedule.get("day", "monday").lower()
                day_map = {
                    "monday": 0,
                    "tuesday": 1,
                    "wednesday": 2,
                    "thursday": 3,
                    "friday": 4,
                    "saturday": 5,
                    "sunday": 6,
                }

                target_weekday = day_map.get(schedule_day, 0)

                return (
                    now.weekday() == target_weekday
                    and now.hour == hour
                    and now.minute == minute
                )

            return False

        except Exception as e:
            logger.error(f"Failed to check schedule trigger: {e}")
            return False

    def _already_generated_for_period(
        self, timelapse_id: int, schedule: Dict[str, Any]
    ) -> bool:
        """Check if we already generated a video for this schedule period"""
        try:
            schedule_type = schedule.get("type", "daily")
            
            # Use operations layer for database operations
            return self.video_ops.check_scheduled_already_generated(timelapse_id, schedule_type)

        except Exception as e:
            logger.error(f"Failed to check if already generated: {e}")
            return True  # Err on the side of caution

    def process_queue(self) -> bool:
        """
        Process the next job in the queue

        Returns True if a job was processed, False if queue is empty
        """
        try:
            # Check if we're at max concurrent jobs
            if self._get_active_job_count() >= self.max_concurrent_jobs:
                logger.debug("Max concurrent jobs reached, skipping queue processing")
                return False

            # Get next job
            job = self.queue.get_next_job()
            if not job:
                return False  # No jobs pending

            job_id = job.id
            timelapse_id = job.timelapse_id
            camera_id = job.camera_id

            logger.info(
                f"Processing video generation job {job_id} for timelapse {timelapse_id}"
            )

            # Mark job as started
            if not self.queue.start_job(job_id):
                logger.error(f"Failed to start job {job_id}")
                return False

            # Create SSE event for job start
            self.sse_ops.create_event(
                event_type="video_job_started",
                event_data={
                    "job_id": job_id,
                    "timelapse_id": timelapse_id,
                    "camera_id": camera_id,
                    "trigger_type": job.trigger_type
                },
                priority="normal",
                source="worker"
            )

            try:
                # Generate the video
                success, result = self._generate_video_for_job(job.model_dump())

                if success:
                    video_id = result.get("video_id")
                    video_path = result.get("video_path")

                    self.queue.complete_job(
                        job_id=job_id,
                        success=True,
                        video_id=video_id,
                        video_path=video_path,
                    )

                    # Create SSE event for successful completion
                    self.sse_ops.create_event(
                        event_type="video_job_completed",
                        event_data={
                            "job_id": job_id,
                            "timelapse_id": timelapse_id,
                            "camera_id": camera_id,
                            "video_id": video_id,
                            "success": True
                        },
                        priority="normal",
                        source="worker"
                    )

                    logger.info(f"Successfully completed video generation job {job_id}")

                else:
                    error_message = result.get("error", "Unknown error")

                    self.queue.complete_job(
                        job_id=job_id, success=False, error_message=error_message
                    )

                    # Create SSE event for failed completion
                    self.sse_ops.create_event(
                        event_type="video_job_failed",
                        event_data={
                            "job_id": job_id,
                            "timelapse_id": timelapse_id,
                            "camera_id": camera_id,
                            "error": error_message,
                            "success": False
                        },
                        priority="high",
                        source="worker"
                    )

                    logger.error(
                        f"Failed video generation job {job_id}: {error_message}"
                    )

                return True

            except Exception as e:
                # Mark job as failed
                self.queue.complete_job(
                    job_id=job_id, success=False, error_message=str(e)
                )

                # Create SSE event for exception failure
                self.sse_ops.create_event(
                    event_type="video_job_failed",
                    event_data={
                        "job_id": job_id,
                        "timelapse_id": timelapse_id,
                        "camera_id": camera_id,
                        "error": str(e),
                        "success": False
                    },
                    priority="high",
                    source="worker"
                )

                logger.error(f"Exception during video generation job {job_id}: {e}")
                return True  # Still processed a job

        except Exception as e:
            logger.error(f"Failed to process queue: {e}")
            return False

    def _get_active_job_count(self) -> int:
        """Get count of currently processing jobs"""
        try:
            # Use operations layer for database operations
            return self.video_ops.get_active_job_count()

        except Exception as e:
            logger.error(f"Failed to get active job count: {e}")
            return self.max_concurrent_jobs  # Assume max to be safe

    def _generate_video_for_job(
        self, job: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Generate video for a specific job"""
        try:
            timelapse_id = job["timelapse_id"]
            camera_id = job["camera_id"]
            job_settings = job.get("settings", {})

            # Get data directory from global config (AI-CONTEXT compliant)
            from ..config import settings as global_settings

            data_directory = global_settings.data_directory
            videos_directory = global_settings.videos_directory

            # Get timelapse info using operations layer
            from ..database.timelapse_operations import SyncTimelapseOperations
            from ..database.camera_operations import SyncCameraOperations
            
            timelapse_ops = SyncTimelapseOperations(self.db)
            camera_ops = SyncCameraOperations(self.db)
            
            timelapse_record = timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse_record:
                return False, {"error": "Timelapse not found"}
                
            camera_record = camera_ops.get_camera_by_id(timelapse_record.camera_id)
            if not camera_record:
                return False, {"error": "Camera not found"}
                
            # Combine timelapse and camera data
            timelapse = timelapse_record.model_dump()
            timelapse["camera_name"] = camera_record.name

            # Build video name
            camera_name = timelapse["camera_name"]
            trigger_type = job["trigger_type"]

            # Get timezone-aware timestamp for file naming
            try:
                timestamp = get_timezone_aware_timestamp_string_sync(self.settings_ops)
            except Exception as e:
                logger.warning(f"Failed to get timezone for filename: {e}")
                timestamp = format_filename_timestamp()

            if trigger_type == "milestone":
                threshold = job_settings.get("threshold", "unknown")
                video_name = f"{camera_name}_milestone_{threshold}_{timestamp}"
            elif trigger_type == "scheduled":
                video_name = f"{camera_name}_scheduled_{timestamp}"
            elif trigger_type == "per_capture":
                video_name = f"{camera_name}_auto_{timestamp}"
            else:
                video_name = f"{camera_name}_manual_{timestamp}"

            # Use VideoService to create the video
            try:
                # Get effective video settings (inheritance pattern: timelapse → camera → defaults)
                video_settings = self._get_effective_video_settings(
                    timelapse_id, job_settings
                )
                video_settings["trigger_type"] = trigger_type

                # Initialize VideoService
                video_service = SyncVideoService(self.db)

                # Generate video using the new architecture
                success, message, video_record = (
                    video_service.generate_video_for_timelapse(
                        timelapse_id=timelapse_id,
                        job_id=job["id"],
                        video_settings=video_settings,
                    )
                )

                if success and video_record:
                    return True, {
                        "video_id": video_record.id,
                        "video_path": video_record.file_path,
                        "message": message,
                    }
                else:
                    return False, {"error": message}

            except Exception as e:
                return False, {"error": f"Video generation failed: {str(e)}"}

        except Exception as e:
            logger.error(f"Failed to generate video for job: {e}")
            return False, {"error": str(e)}

    def _get_effective_video_settings(
        self, timelapse_id: int, job_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get effective video settings using inheritance pattern.

        Follows AI-CONTEXT pattern: timelapse settings override camera defaults.

        Args:
            timelapse_id: ID of the timelapse
            job_settings: Job-specific settings (highest priority)

        Returns:
            Dictionary with effective video generation settings
        """
        try:
            # Use operations layer for database operations
            return self.video_ops.get_timelapse_video_settings(timelapse_id, job_settings)

        except Exception as e:
            logger.error(
                f"Failed to get effective video settings for timelapse {timelapse_id}: {e}"
            )
            return self._get_default_video_settings()

    def _get_default_video_settings(self) -> Dict[str, Any]:
        """Get default video generation settings."""
        return {
            "video_generation_mode": "standard",
            "fps": 24.0,
            "enable_time_limits": False,
            "min_time_seconds": 5,
            "max_time_seconds": 300,
            "target_time_seconds": 60,
            "fps_bounds_min": 1,
            "fps_bounds_max": 60,
            "quality": "medium",
            "overlay_settings": DEFAULT_OVERLAY_SETTINGS,
        }

    def get_automation_stats(self) -> Dict[str, Any]:
        """Get automation statistics"""
        try:
            stats = {
                "queue_status": self.queue.get_queue_status(),
                "active_jobs": self._get_active_job_count(),
                "max_concurrent": self.max_concurrent_jobs,
                "throttle_minutes": self.per_capture_throttle_minutes,
            }

            # Get automation mode distribution using operations layer
            mode_stats = self.video_ops.get_automation_mode_stats()
            stats["automation_modes"] = mode_stats

            return stats

        except Exception as e:
            logger.error(f"Failed to get automation stats: {e}")
            return {
                "queue_status": {},
                "active_jobs": 0,
                "max_concurrent": self.max_concurrent_jobs,
                "throttle_minutes": self.per_capture_throttle_minutes,
                "automation_modes": {},
            }

    def process_automation_triggers(self) -> Dict[str, Any]:
        """
        Process all automation triggers and return activity summary

        This method is called by the worker to check and process all types
        of automation triggers in a single call.

        Returns:
            Dictionary with trigger activity summary
        """
        try:
            logger.debug("Processing automation triggers...")

            activity = {
                "milestone_jobs": [],
                "scheduled_jobs": [],
                "queue_processed": 0,
                "errors": [],
            }

            # Check milestone triggers
            try:
                milestone_jobs = self.check_milestone_triggers()
                activity["milestone_jobs"] = milestone_jobs
                if milestone_jobs:
                    logger.info(f"Created {len(milestone_jobs)} milestone jobs")
            except Exception as e:
                error_msg = f"Milestone trigger check failed: {e}"
                logger.error(error_msg)
                activity["errors"].append(error_msg)

            # Check scheduled triggers
            try:
                scheduled_jobs = self.check_scheduled_triggers()
                activity["scheduled_jobs"] = scheduled_jobs
                if scheduled_jobs:
                    logger.info(f"Created {len(scheduled_jobs)} scheduled jobs")
            except Exception as e:
                error_msg = f"Scheduled trigger check failed: {e}"
                logger.error(error_msg)
                activity["errors"].append(error_msg)

            # Process pending jobs in queue
            try:
                jobs_processed = 0
                while self.process_queue() and jobs_processed < 5:
                    jobs_processed += 1

                activity["queue_processed"] = jobs_processed
                if jobs_processed > 0:
                    logger.info(f"Processed {jobs_processed} queue jobs")
            except Exception as e:
                error_msg = f"Queue processing failed: {e}"
                logger.error(error_msg)
                activity["errors"].append(error_msg)

            # Log summary
            total_new_jobs = len(activity["milestone_jobs"]) + len(
                activity["scheduled_jobs"]
            )
            if total_new_jobs > 0 or activity["queue_processed"] > 0:
                logger.info(
                    f"Automation cycle complete: {total_new_jobs} new jobs, {activity['queue_processed']} processed"
                )

            return activity

        except Exception as e:
            logger.error(f"Critical error in process_automation_triggers: {e}")
            return {
                "milestone_jobs": [],
                "scheduled_jobs": [],
                "queue_processed": 0,
                "errors": [f"Critical error: {e}"],
            }
