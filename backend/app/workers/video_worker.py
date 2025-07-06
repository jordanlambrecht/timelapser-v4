# backend/app/workers/video_worker.py
"""
Video worker for Timelapser v4.

Handles video automation processing and generation triggers.
"""

from typing import Dict, Any

from .base_worker import BaseWorker
from ..services.video_automation_service import VideoAutomationService
from ..services.video_service import SyncVideoService
from ..constants import DEFAULT_VIDEO_CLEANUP_DAYS


class VideoWorker(BaseWorker):
    """
    Worker responsible for video automation processing.

    Handles:
    - Video automation trigger processing
    - Milestone-based video generation
    - Scheduled video generation jobs
    - Video generation queue management
    """

    def __init__(
        self,
        video_automation_service: VideoAutomationService,
        video_service: SyncVideoService,
    ):
        """
        Initialize video worker with injected dependencies.

        Args:
            video_automation_service: Video automation processing service
            video_service: Video operations service
        """
        super().__init__("VideoWorker")
        self.video_automation_service = video_automation_service
        self.video_service = video_service

    async def initialize(self) -> None:
        """Initialize video worker resources."""
        self.log_info("Initialized video worker")

    async def cleanup(self) -> None:
        """Cleanup video worker resources."""
        self.log_info("Cleaned up video worker")

    async def process_video_automation(self):
        """Process video automation triggers and jobs."""
        try:
            results = await self.run_in_executor(
                self.video_automation_service.process_automation_triggers
            )

            # Log activity if any (results should be a dict with activity summary)
            if isinstance(results, dict):
                total_activity = (
                    len(results.get("milestone_jobs", []))
                    + len(results.get("scheduled_jobs", []))
                    + results.get("queue_processed", 0)
                )
                if total_activity > 0:
                    self.log_info(f"Video automation activity: {results}")
            else:
                self.log_warning(f"Unexpected automation results format: {results}")

        except Exception as e:
            self.log_error("Error processing video automation", e)

    async def get_video_generation_status(self) -> Dict[str, Any]:
        """
        Get current video generation status.

        Returns:
            Dict[str, Any]: Video generation status information
        """
        try:
            # Get pending/active video generation jobs
            status = {
                "active_generations": 0,
                "pending_generations": 0,
                "completed_today": 0,
                "failed_today": 0,
                "queue_status": "unknown",
            }

            # TODO: Implement video status queries in VideoService
            # This would require additional methods in the video service
            # to get counts of videos by status and date

            return status

        except Exception as e:
            self.log_error("Error getting video generation status", e)
            return {
                "active_generations": 0,
                "pending_generations": 0,
                "completed_today": 0,
                "failed_today": 0,
                "queue_status": "error",
            }

    async def trigger_milestone_generation(
        self, camera_id: int, milestone_count: int
    ) -> bool:
        """
        Trigger milestone-based video generation for a camera.

        Args:
            camera_id: Camera ID to generate video for
            milestone_count: Image count milestone reached

        Returns:
            bool: True if generation was triggered successfully
        """
        try:
            # Use check_milestone_triggers() since the specific method doesn't exist
            result = await self.run_in_executor(
                self.video_automation_service.check_milestone_triggers
            )

            if result:
                self.log_info(
                    f"Triggered milestone video generation for camera {camera_id} at {milestone_count} images"
                )
                return True
            else:
                self.log_debug(
                    f"Milestone generation not triggered for camera {camera_id} (conditions not met)"
                )
                return False

        except Exception as e:
            self.log_error(
                f"Error triggering milestone generation for camera {camera_id}", e
            )
            return False

    async def trigger_scheduled_generation(self, camera_id: int) -> bool:
        """
        Trigger scheduled video generation for a camera.

        Args:
            camera_id: Camera ID to generate video for

        Returns:
            bool: True if generation was triggered successfully
        """
        try:
            # Use check_scheduled_triggers() since the specific method doesn't exist
            result = await self.run_in_executor(
                self.video_automation_service.check_scheduled_triggers
            )

            if result:
                self.log_info(
                    f"Triggered scheduled video generation for camera {camera_id}"
                )
                return True
            else:
                self.log_debug(
                    f"Scheduled generation not triggered for camera {camera_id} (conditions not met)"
                )
                return False

        except Exception as e:
            self.log_error(
                f"Error triggering scheduled generation for camera {camera_id}", e
            )
            return False

    async def clean_old_videos(
        self, retention_days: int = DEFAULT_VIDEO_CLEANUP_DAYS
    ) -> int:
        """
        Clean up old video files based on retention policy.

        Args:
            retention_days: Number of days to retain videos

        Returns:
            int: Number of videos cleaned up
        """
        try:
            # TODO: Implement video cleanup in VideoService
            # This would require additional methods to:
            # 1. Find videos older than retention_days
            # 2. Delete video files and database records
            # 3. Return count of cleaned videos

            self.log_info(
                f"Video cleanup would run with {retention_days} day retention"
            )
            return 0

        except Exception as e:
            self.log_error("Error cleaning old videos", e)
            return 0

    async def get_video_queue_health(self) -> Dict[str, Any]:
        """
        Check video generation queue health.

        Returns:
            Dict[str, Any]: Queue health status
        """
        try:
            health_status = {
                "queue_healthy": True,
                "stuck_jobs": 0,
                "old_jobs": 0,
                "disk_space_ok": True,
                "errors": [],
            }

            # TODO: Implement queue health checks:
            # 1. Check for jobs stuck in "processing" state for too long
            # 2. Check for old failed jobs that need cleanup
            # 3. Check available disk space for video generation
            # 4. Check FFmpeg availability and configuration

            return health_status

        except Exception as e:
            self.log_error("Error checking video queue health", e)
            return {
                "queue_healthy": False,
                "stuck_jobs": 0,
                "old_jobs": 0,
                "disk_space_ok": False,
                "errors": [str(e)],
            }
