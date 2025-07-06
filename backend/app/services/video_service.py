# backend/app/services/video_service.py

"""
Video Service - Composition-based architecture following AI-CONTEXT principles.

This service handles video-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.

Responsibilities (per Target Architecture):
- Video record management
- FFmpeg coordination via utils
- Generation job queue management
- File lifecycle management

Interactions:
- Uses VideoOperations for database
- Calls ffmpeg_utils for rendering
- Coordinates with VideoAutomationService for automated generation
"""

from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.video_operations import VideoOperations, SyncVideoOperations
from ..database.timelapse_operations import SyncTimelapseOperations
from ..database.camera_operations import SyncCameraOperations
from ..database.image_operations import SyncImageOperations
from ..database.settings_operations import SettingsOperations, SyncSettingsOperations
from ..models.video_model import Video, VideoWithDetails
from ..models.shared_models import (
    VideoGenerationJob,
    VideoGenerationJobWithDetails,
    VideoStatistics,
)
from ..utils import ffmpeg_utils
from ..utils.file_helpers import (
    validate_file_path,
    ensure_directory_exists,
    get_relative_path,
    get_file_size,
)
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
    get_timezone_aware_timestamp_string_async,
)
from ..database.sse_events_operations import SSEEventsOperations
from ..config import settings
from ..constants import (
    VIDEO_QUALITIES,
    DEFAULT_VIDEO_CLEANUP_DAYS,
    DEFAULT_VIDEO_ARCHIVE_DIRECTORY,
    DEFAULT_VIDEO_GENERATION_PRIORITY,
)


class VideoService:
    """
    Video metadata and generation coordination business logic.

    Responsibilities:
    - Video record management
    - FFmpeg coordination via utils
    - Generation job queue management
    - File lifecycle management

    Interactions:
    - Uses VideoOperations for database
    - Calls ffmpeg_utils for rendering
    - Coordinates with VideoAutomationService for automated generation
    """

    def __init__(self, db: AsyncDatabase, video_automation_service=None):
        """
        Initialize VideoService with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            video_automation_service: Optional VideoAutomationService for automation coordination
        """
        self.db = db
        self.video_ops = VideoOperations(db)
        self.settings_ops = SettingsOperations(db)
        self.sse_ops = SSEEventsOperations(db)
        self.video_automation_service = video_automation_service

    async def get_videos(
        self, timelapse_id: Optional[int] = None
    ) -> List[VideoWithDetails]:
        """
        Retrieve videos with optional timelapse filtering.

        Args:
            timelapse_id: Optional timelapse ID to filter by

        Returns:
            List of VideoWithDetails model instances
        """
        return await self.video_ops.get_videos(timelapse_id)

    async def get_video_by_id(self, video_id: int) -> Optional[VideoWithDetails]:
        """
        Retrieve a specific video by ID.

        Args:
            video_id: ID of the video to retrieve

        Returns:
            VideoWithDetails model instance, or None if not found
        """
        return await self.video_ops.get_video_by_id(video_id)

    async def create_video_record(self, video_data: Dict[str, Any]) -> Video:
        """
        Create a new video record with timezone-aware timestamps.

        Args:
            video_data: Dictionary containing video metadata

        Returns:
            Created Video model instance
        """
        # Ensure timezone-aware creation timestamp
        if "created_at" not in video_data:
            video_data["created_at"] = await get_timezone_aware_timestamp_async(self.db)

        video = await self.video_ops.create_video_record(video_data)
        
        # Create SSE event for real-time updates
        await self.sse_ops.create_event(
            event_type="video_created",
            event_data={
                "video_id": video.id,
                "camera_id": video_data.get("camera_id"),
                "video_name": video_data.get("name"),
                "status": video_data.get("status"),
            },
            priority="normal",
            source="api"
        )
        
        return video

    async def update_video(self, video_id: int, video_data: Dict[str, Any]) -> Video:
        """
        Update an existing video record with timezone-aware timestamps.

        Args:
            video_id: ID of the video to update
            video_data: Dictionary containing updated video data

        Returns:
            Updated Video model instance
        """
        # Ensure timezone-aware update timestamp
        video_data["updated_at"] = await get_timezone_aware_timestamp_async(self.db)

        return await self.video_ops.update_video(video_id, video_data)

    async def delete_video(self, video_id: int) -> bool:
        """
        Delete a video record and associated files.

        Args:
            video_id: ID of the video to delete

        Returns:
            True if video was deleted successfully
        """
        # Get video info before deletion for file cleanup and SSE event
        video = await self.get_video_by_id(video_id)
        
        # Extract file path before database deletion
        file_path_to_cleanup = video.file_path if video else None
        
        # Delete from database first
        success = await self.video_ops.delete_video(video_id)
        
        # Clean up file directly using file_helpers (no database lookup needed)
        if success and file_path_to_cleanup:
            try:
                validated_path = validate_file_path(
                    file_path_to_cleanup, 
                    base_directory=settings.data_directory, 
                    must_exist=False
                )
                if validated_path.exists():
                    validated_path.unlink()
                    logger.info(f"Deleted video file: {validated_path}")
            except Exception as e:
                logger.warning(f"Database deletion succeeded but file cleanup failed for video {video_id}: {e}")
        
        # Create SSE event for real-time updates
        if success and video:
            await self.sse_ops.create_event(
                event_type="video_deleted",
                event_data={
                    "video_id": video_id,
                    "video_name": video.name,
                    "camera_id": video.camera_id,
                },
                priority="normal",
                source="api"
            )
        
        return success

    async def get_video_generation_jobs(
        self, status: Optional[str] = None
    ) -> List[VideoGenerationJobWithDetails]:
        """
        Get video generation jobs with optional status filtering.

        Args:
            status: Optional status to filter by ('pending', 'processing', 'completed', 'failed')

        Returns:
            List of VideoGenerationJobWithDetails model instances
        """
        return await self.video_ops.get_video_generation_jobs(status)

    async def create_video_generation_job(
        self, job_data: Dict[str, Any]
    ) -> VideoGenerationJob:
        """
        Create a new video generation job with timezone-aware timestamps.

        Args:
            job_data: Dictionary containing job configuration

        Returns:
            Created VideoGenerationJob model instance
        """
        # Ensure timezone-aware creation timestamp
        if "created_at" not in job_data:
            job_data["created_at"] = await get_timezone_aware_timestamp_async(self.settings_ops)

        # Calculate event timestamp for database operation
        event_timestamp = await get_timezone_aware_timestamp_async(self.settings_ops)
        job = await self.video_ops.create_video_generation_job(job_data, event_timestamp)
        return job

    async def update_video_generation_job_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> VideoGenerationJob:
        """
        Update the status of a video generation job with timezone-aware timestamps.

        Args:
            job_id: ID of the job
            status: New status ('pending', 'processing', 'completed', 'failed')
            error_message: Optional error message if failed
            video_path: Optional path to generated video if completed

        Returns:
            Updated VideoGenerationJob model instance
        """
        job = await self.video_ops.update_video_generation_job_status(
            job_id, status, error_message, video_path
        )
        return job

    async def get_video_statistics(
        self, timelapse_id: Optional[int] = None
    ) -> VideoStatistics:
        """
        Get video statistics for a timelapse or overall.

        Args:
            timelapse_id: Optional timelapse ID to filter by

        Returns:
            VideoStatistics model instance
        """
        return await self.video_ops.get_video_statistics(timelapse_id)

    async def manage_file_lifecycle(self, video_id: int, action: str) -> Dict[str, Any]:
        """
        Manage video file lifecycle operations using file_helpers.

        Args:
            video_id: ID of the video
            action: Lifecycle action ('cleanup', 'archive', 'restore', 'verify')

        Returns:
            Lifecycle management results
        """
        try:
            video = await self.get_video_by_id(video_id)
            if not video:
                return {"success": False, "error": f"Video {video_id} not found"}

            if not video.file_path:
                return {
                    "success": False,
                    "error": f"Video file path is missing for video {video_id}",
                }

            # Use file_helpers for secure path operations
            file_path = validate_file_path(
                video.file_path,
                base_directory=settings.data_directory,
                must_exist=(action != "cleanup"),
            )

            if action == "cleanup":
                # Remove video file and update database record
                if file_path.exists():
                    file_path.unlink()
                    await self.update_video(
                        video_id,
                        {
                            "file_path": None,
                            "deleted_at": await get_timezone_aware_timestamp_async(
                                self.db
                            ),
                        },
                    )
                    return {
                        "success": True,
                        "action": "cleanup",
                        "message": f"Video file removed: {file_path}",
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Video file not found: {file_path}",
                    }

            elif action == "verify":
                # Verify video file exists and is accessible
                if file_path.exists():
                    file_size = get_file_size(file_path)
                    return {
                        "success": True,
                        "action": "verify",
                        "exists": True,
                        "file_size": file_size,
                        "file_path": str(file_path),
                    }
                else:
                    return {
                        "success": False,
                        "action": "verify",
                        "exists": False,
                        "error": f"Video file missing: {file_path}",
                    }

            elif action == "archive":
                # Move to archive directory using file_helpers
                archive_dir = ensure_directory_exists(
                    str(Path(settings.data_directory) / DEFAULT_VIDEO_ARCHIVE_DIRECTORY)
                )
                archive_path = archive_dir / file_path.name

                if file_path.exists():
                    file_path.rename(archive_path)
                    relative_archive_path = get_relative_path(
                        archive_path, settings.data_directory
                    )
                    await self.update_video(
                        video_id,
                        {
                            "file_path": relative_archive_path,
                            "archived_at": await get_timezone_aware_timestamp_async(
                                self.db
                            ),
                        },
                    )
                    return {
                        "success": True,
                        "action": "archive",
                        "new_path": str(archive_path),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Video file not found for archiving: {file_path}",
                    }

            else:
                return {
                    "success": False,
                    "error": f"Unknown lifecycle action: {action}",
                }

        except Exception as e:
            logger.error(f"File lifecycle management failed for video {video_id}: {e}")
            return {"success": False, "error": str(e)}

    async def coordinate_with_automation(
        self, timelapse_id: int, trigger_type: str
    ) -> Dict[str, Any]:
        """
        Coordinate with VideoAutomationService for automated generation.

        Args:
            timelapse_id: ID of the timelapse
            trigger_type: Type of automation trigger

        Returns:
            Automation coordination results
        """
        try:
            if self.video_automation_service:
                # Request automated video generation
                automation_result = (
                    await self.video_automation_service.queue_video_generation(
                        timelapse_id=timelapse_id,
                        trigger_type=trigger_type,
                        priority=DEFAULT_VIDEO_GENERATION_PRIORITY,
                    )
                )

                # Log coordination
                logger.info(
                    f"Coordinated with automation service for timelapse {timelapse_id}, trigger: {trigger_type}"
                )
                return automation_result
            else:
                logger.warning(
                    f"VideoAutomationService not available for timelapse {timelapse_id}"
                )
                return {
                    "success": False,
                    "error": "VideoAutomationService not configured",
                }

        except Exception as e:
            logger.error(
                f"Automation coordination failed for timelapse {timelapse_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    async def generate_video_workflow(
        self,
        timelapse_id: int,
        video_settings: Dict[str, Any],
        trigger_type: str = "manual",
    ) -> Dict[str, Any]:
        """
        Complete video generation workflow coordination.

        Args:
            timelapse_id: ID of the timelapse
            video_settings: Video generation settings
            trigger_type: Type of generation trigger

        Returns:
            Complete workflow results
        """
        try:
            # Note: This method would need to be implemented when actual video generation
            # functionality is added. For now, it serves as a placeholder for the
            # complete workflow that would coordinate FFmpeg rendering.

            logger.info(
                f"Video generation workflow requested for timelapse {timelapse_id}"
            )

            # Placeholder for future implementation
            return {
                "workflow": "pending_implementation",
                "message": "Video generation workflow not yet implemented",
                "timelapse_id": timelapse_id,
                "trigger_type": trigger_type,
            }

        except Exception as e:
            logger.error(
                f"Video generation workflow failed for timelapse {timelapse_id}: {e}"
            )
            return {"workflow": "failed", "error": str(e)}

    async def get_service_health(self) -> Dict[str, Any]:
        """
        Get video service health status for monitoring.

        Returns:
            Dictionary with service health metrics
        """
        try:
            # Get basic statistics for health assessment
            stats = await self.get_video_statistics()
            
            # Get recent job status for health check
            recent_jobs = await self.get_video_generation_jobs()
            
            # Calculate health metrics
            total_jobs = len(recent_jobs)
            failed_jobs = len([job for job in recent_jobs if job.status == "failed"])
            processing_jobs = len([job for job in recent_jobs if job.status == "processing"])
            
            # Determine health status
            if total_jobs == 0:
                health_status = "unknown"
            elif failed_jobs > total_jobs * 0.5:  # More than 50% failed
                health_status = "unhealthy"
            elif failed_jobs > total_jobs * 0.2:  # More than 20% failed
                health_status = "degraded"
            else:
                health_status = "healthy"
            
            health_data = {
                "status": health_status,
                "total_videos": stats.total_videos,
                "total_jobs": total_jobs,
                "failed_jobs": failed_jobs,
                "processing_jobs": processing_jobs,
                "service": "video_service",
                "timestamp": await get_timezone_aware_timestamp_async(self.settings_ops),
            }
            
            return health_data
            
        except Exception as e:
            logger.error(f"Video service health check failed: {e}")
            return {
                "status": "unknown",
                "error": str(e),
                "service": "video_service",
                "timestamp": await get_timezone_aware_timestamp_async(self.settings_ops),
            }


class SyncVideoService:
    """
    Sync video service for worker processes using composition pattern.

    This service orchestrates video-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncVideoService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.video_ops = SyncVideoOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.camera_ops = SyncCameraOperations(db)
        self.image_ops = SyncImageOperations(db)
        self.settings_ops = SyncSettingsOperations(db)

    def get_pending_video_generation_jobs(self) -> List[VideoGenerationJobWithDetails]:
        """
        Get pending video generation jobs for processing.

        Returns:
            List of VideoGenerationJobWithDetails model instances
        """
        return self.video_ops.get_pending_video_generation_jobs()

    def claim_video_generation_job(self, job_id: int) -> bool:
        """
        Claim a video generation job for processing.

        Args:
            job_id: ID of the job to claim

        Returns:
            True if job was successfully claimed
        """
        return self.video_ops.claim_video_generation_job(job_id)

    def complete_video_generation_job(
        self,
        job_id: int,
        video_path: str,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Complete a video generation job.

        Args:
            job_id: ID of the job
            video_path: Path to the generated video
            success: Whether the job completed successfully
            error_message: Optional error message if failed

        Returns:
            True if job was successfully completed
        """
        # Calculate timestamp for database operation
        event_timestamp = get_timezone_aware_timestamp_sync(self.settings_ops)
        return self.video_ops.complete_video_generation_job(
            job_id, success, error_message, video_path, event_timestamp
        )

    def create_video_record(self, video_data: Dict[str, Any]) -> Video:
        """
        Create a new video record with timezone-aware timestamps.

        Args:
            video_data: Dictionary containing video metadata

        Returns:
            Created Video model instance
        """
        # Ensure timezone-aware creation timestamp
        if "created_at" not in video_data:
            video_data["created_at"] = get_timezone_aware_timestamp_sync(self.settings_ops)

        return self.video_ops.create_video_record(video_data)

    def generate_video_for_timelapse(
        self, timelapse_id: int, job_id: int, video_settings: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Video]]:
        """
        Generate video for a timelapse using FFmpeg utilities and proper Pydantic models.

        This method orchestrates the complete video generation process:
        1. Get timelapse and image data from database using operations
        2. Configure video generation settings
        3. Call FFmpeg utilities to generate video
        4. Create video record in database
        5. Update job status

        Args:
            timelapse_id: ID of the timelapse to generate video for
            job_id: ID of the video generation job
            video_settings: Video generation configuration

        Returns:
            Tuple of (success, message, video_record_or_none)
        """
        try:
            # Get timelapse data using operations (returns Pydantic model)
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                error_msg = f"Timelapse {timelapse_id} not found"
                self.complete_video_generation_job(job_id, "", False, error_msg)
                return False, error_msg, None

            # Get images for timelapse using the new method (returns Pydantic models)
            images = self.image_ops.get_images_for_timelapse(timelapse_id)
            if not images:
                error_msg = f"No images found for timelapse {timelapse_id}"
                self.complete_video_generation_job(job_id, "", False, error_msg)
                return False, error_msg, None

            # Get camera data using operations (returns Pydantic model)
            camera_data = self.camera_ops.get_camera_by_id(timelapse.camera_id)
            if not camera_data:
                error_msg = f"Camera {timelapse.camera_id} not found"
                self.complete_video_generation_job(job_id, "", False, error_msg)
                return False, error_msg, None

            # Use file_helpers for secure path operations
            images_dir = validate_file_path(
                f"cameras/camera-{timelapse.camera_id}/images",
                base_directory=settings.data_directory,
                must_exist=True,
            )

            # Generate output filename with timezone-aware timestamp
            timestamp_str = get_timezone_aware_timestamp_sync(self.settings_ops).strftime(
                "%Y%m%d_%H%M%S"
            )
            output_filename = f"timelapse_{timelapse_id}_{timestamp_str}.mp4"

            # Use file_helpers to ensure output directory exists
            videos_dir = ensure_directory_exists(settings.videos_directory)
            output_path = videos_dir / output_filename

            # Extract day numbers from images using Pydantic model attributes
            day_numbers = [img.day_number for img in images]

            # Configure overlay settings
            overlay_settings = video_settings.get(
                "overlay_settings", ffmpeg_utils.DEFAULT_OVERLAY_SETTINGS
            )
            
            # Get quality from constants if not specified
            quality = video_settings.get("quality")
            if quality not in VIDEO_QUALITIES:
                quality = "medium"  # Default fallback

            logger.info(f"Starting video generation for timelapse {timelapse_id}")

            # Generate video using FFmpeg utilities
            success, message, metadata = ffmpeg_utils.generate_video(
                images_directory=images_dir,
                output_path=str(output_path),
                framerate=float(video_settings.get("fps", 24.0)),
                quality=quality,
                overlay_settings=overlay_settings,
                day_numbers=day_numbers,
            )

            if success:
                # Create video record using Pydantic model attributes
                video_data = {
                    "camera_id": timelapse.camera_id,
                    "timelapse_id": timelapse_id,
                    "name": f"Timelapse {timelapse.name}",
                    "file_path": get_relative_path(
                        output_path, settings.data_directory
                    ),
                    "status": "completed",
                    "settings": video_settings,
                    "image_count": metadata.get("image_count", len(images)),
                    "file_size": metadata.get("file_size_bytes", 0),
                    "duration_seconds": metadata.get("duration_seconds", 0),
                    "calculated_fps": metadata.get(
                        "framerate", video_settings.get("fps", 24.0)
                    ),
                    "images_start_date": timelapse.start_date,
                    "images_end_date": timelapse.last_capture_at
                    or timelapse.start_date,
                    "trigger_type": video_settings.get("trigger_type", "manual"),
                    "job_id": job_id,
                    "created_at": get_timezone_aware_timestamp_sync(self.settings_ops),
                }

                video_record = self.create_video_record(video_data)

                # Complete job successfully
                self.complete_video_generation_job(job_id, str(output_path), True)

                logger.info(
                    f"Video generation completed successfully for timelapse {timelapse_id}"
                )
                return (
                    True,
                    f"Video generated successfully: {output_path}",
                    video_record,
                )

            else:
                # Complete job with failure
                self.complete_video_generation_job(job_id, "", False, message)
                logger.error(
                    f"Video generation failed for timelapse {timelapse_id}: {message}"
                )
                return False, message, None

        except Exception as e:
            error_msg = f"Error generating video for timelapse {timelapse_id}: {str(e)}"
            logger.error(error_msg)
            try:
                self.complete_video_generation_job(job_id, "", False, error_msg)
            except Exception as completion_error:
                logger.error(f"Failed to update job status: {completion_error}")
            return False, error_msg, None

    def cleanup_old_video_jobs(self, days_to_keep: int = DEFAULT_VIDEO_CLEANUP_DAYS) -> int:
        """
        Clean up old completed video generation jobs.

        Args:
            days_to_keep: Number of days to keep completed jobs (default: 30)

        Returns:
            Number of jobs deleted
        """
        return self.video_ops.cleanup_old_video_jobs(days_to_keep)
