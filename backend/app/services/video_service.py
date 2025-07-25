# backend/app/services/video_service.py
"""
Video Service - Pure video data management.

This service handles all video-related CRUD operations and data management
using dependency injection for database operations, providing type-safe
Pydantic model interfaces.

Key Features:
- Video record creation, retrieval, updating, and deletion
- Video metadata management and statistics
- File path validation and management
- Timelapse-video relationship management
- Search and filtering capabilities
- Frontend data formatting

Business Rules:
- Videos are linked to timelapses and cameras
- File paths are stored relative to data directory
- Video metadata includes duration, file size, image count
- Soft delete preservation for audit trails
- Automatic timestamp management

Separation of Concerns:
- This service handles ONLY data operations
- No workflow orchestration or pipeline logic
- No video generation or FFmpeg operations
- No job queue or scheduling decisions
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from pathlib import Path

from ..enums import SSEPriority

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.video_operations import VideoOperations, SyncVideoOperations
from ..database.sse_events_operations import (
    SSEEventsOperations,
    SyncSSEEventsOperations,
)
from ..models.video_model import Video, VideoCreate, VideoUpdate, VideoWithDetails
from ..models.shared_models import VideoStatistics
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
)
from ..utils.file_helpers import (
    validate_file_path,
    get_relative_path,
    get_file_size,
)
from ..constants import (
    EVENT_VIDEO_CREATED,
    EVENT_VIDEO_UPDATED,
    EVENT_VIDEO_DELETED,
    EVENT_VIDEO_STATS_CALCULATED,
)
from ..config import settings


class VideoService:
    """
    Video data management service using composition pattern.

    Responsibilities:
    - Video record CRUD operations
    - Video metadata and statistics management
    - File path validation and management
    - Timelapse-video relationship management
    - Search and filtering capabilities

    Interactions:
    - Uses VideoOperations for database access
    - Uses SSEEventsOperations for event broadcasting
    - Provides type-safe Pydantic model interfaces
    """

    def __init__(self, db: AsyncDatabase):
        """
        Initialize VideoService with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db
        self.video_ops = VideoOperations(db)
        self.sse_ops = SSEEventsOperations(db)

    async def get_videos(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[VideoWithDetails]:
        """
        Get videos with optional filtering.

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID
            status: Optional filter by video status
            limit: Maximum number of videos to return
            offset: Number of videos to skip for pagination

        Returns:
            List of video records matching criteria
        """
        try:
            logger.debug(
                f"Retrieving videos with filters: timelapse_id={timelapse_id}, camera_id={camera_id}, status={status}"
            )

            videos = await self.video_ops.get_videos(
                timelapse_id=timelapse_id,
                camera_id=camera_id,
                status=status,
                limit=limit,
                offset=offset,
            )

            logger.debug(f"Retrieved {len(videos)} videos")
            return videos

        except Exception as e:
            logger.error(f"Failed to get videos: {e}")
            return []

    async def get_video_by_id(self, video_id: int) -> Optional[VideoWithDetails]:
        """
        Get video by ID.

        Args:
            video_id: Video ID to retrieve

        Returns:
            Video record or None if not found
        """
        try:
            logger.debug(f"Retrieving video {video_id}")

            video = await self.video_ops.get_video_by_id(video_id)
            if video:
                logger.debug(f"Found video {video_id}")
            else:
                logger.warning(f"Video {video_id} not found")

            return video

        except Exception as e:
            logger.error(f"Failed to get video {video_id}: {e}")
            return None

    async def create_video_record(self, video_data: VideoCreate) -> Optional[Video]:
        """
        Create a new video record.

        Args:
            video_data: Video creation data

        Returns:
            Created video record or None if failed
        """
        try:
            logger.debug(
                f"Creating video record for timelapse {video_data.timelapse_id}"
            )

            # Ensure timezone-aware timestamp
            current_time = await get_timezone_aware_timestamp_async(self.db)

            # Validate file path if provided
            if video_data.file_path:
                try:
                    # Convert to relative path if absolute
                    if Path(video_data.file_path).is_absolute():
                        video_data.file_path = get_relative_path(
                            Path(video_data.file_path), settings.data_directory
                        )

                    # Validate the file exists
                    full_path = Path(settings.data_directory) / video_data.file_path
                    if not full_path.exists():
                        logger.warning(f"Video file does not exist: {full_path}")

                except Exception as e:
                    logger.warning(f"File path validation failed: {e}")

            # Prepare video record data
            video_record_data = {
                **video_data.model_dump(),
                "created_at": current_time,
                "updated_at": current_time,
            }

            # Create video record
            video_record = await self.video_ops.create_video_record(video_record_data)

            if video_record:
                logger.info(
                    f"✅ Created video record {video_record.id} for timelapse {video_data.timelapse_id}"
                )

                # Broadcast SSE event
                await self._broadcast_video_event(
                    event_type=EVENT_VIDEO_CREATED,
                    video_id=video_record.id,
                    event_data={
                        "video_id": video_record.id,
                        "timelapse_id": video_data.timelapse_id,
                        "camera_id": video_data.camera_id,
                        "name": video_data.name,
                        "file_path": video_data.file_path,
                        "status": video_data.status,
                        "trigger_type": getattr(video_data, "trigger_type", "unknown"),
                    },
                )

                return video_record
            else:
                logger.error(
                    f"❌ Failed to create video record for timelapse {video_data.timelapse_id}"
                )
                return None

        except Exception as e:
            logger.error(f"❌ Error creating video record: {e}")
            return None

    async def update_video_record(
        self, video_id: int, update_data: VideoUpdate
    ) -> Optional[Video]:
        """
        Update an existing video record.

        Args:
            video_id: Video ID to update
            update_data: Video update data

        Returns:
            Updated video record or None if failed
        """
        try:
            logger.debug(f"Updating video record {video_id}")

            # Check if video exists
            existing_video = await self.get_video_by_id(video_id)
            if not existing_video:
                logger.error(f"Video {video_id} not found for update")
                return None

            # Prepare update data with timestamp
            current_time = await get_timezone_aware_timestamp_async(self.db)
            update_record_data = {
                **update_data.model_dump(exclude_unset=True),
                "updated_at": current_time,
            }

            # Update video record
            updated_video = await self.video_ops.update_video(
                video_id, update_record_data
            )

            if updated_video:
                logger.info(f"✅ Updated video record {video_id}")

                # Broadcast SSE event
                await self._broadcast_video_event(
                    event_type=EVENT_VIDEO_UPDATED,
                    video_id=video_id,
                    event_data={
                        "video_id": video_id,
                        "updated_fields": list(
                            update_data.model_dump(exclude_unset=True).keys()
                        ),
                        "previous_status": existing_video.status,
                        "new_status": getattr(
                            update_data, "status", existing_video.status
                        ),
                    },
                )

                return updated_video
            else:
                logger.error(f"❌ Failed to update video record {video_id}")
                return None

        except Exception as e:
            logger.error(f"❌ Error updating video record {video_id}: {e}")
            return None

    async def delete_video(self, video_id: int, soft_delete: bool = True) -> bool:
        """
        Delete a video record.

        Args:
            video_id: Video ID to delete
            soft_delete: Whether to soft delete (mark as deleted) or hard delete

        Returns:
            True if deleted successfully
        """
        try:
            logger.debug(f"Deleting video {video_id} (soft_delete={soft_delete})")

            # Get video info before deletion for event data
            video_info = await self.get_video_by_id(video_id)
            if not video_info:
                logger.error(f"Video {video_id} not found for deletion")
                return False

            # Perform deletion
            if soft_delete:
                # Soft delete by updating status to failed (closest allowed status)
                update_data = VideoUpdate(
                    name=video_info.name,
                    timelapse_id=video_info.timelapse_id,
                    status="failed",
                )
                success = (
                    await self.update_video_record(video_id, update_data) is not None
                )
            else:
                # Hard delete from database
                success = await self.video_ops.delete_video(video_id)

            if success:
                logger.info(
                    f"✅ {'Soft' if soft_delete else 'Hard'} deleted video {video_id}"
                )

                # Broadcast SSE event
                await self._broadcast_video_event(
                    event_type=EVENT_VIDEO_DELETED,
                    video_id=video_id,
                    event_data={
                        "video_id": video_id,
                        "timelapse_id": video_info.timelapse_id,
                        "camera_id": video_info.camera_id,
                        "name": video_info.name,
                        "soft_delete": soft_delete,
                        "file_path": video_info.file_path,
                    },
                )

                return True
            else:
                logger.error(f"❌ Failed to delete video {video_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error deleting video {video_id}: {e}")
            return False

    async def get_video_statistics(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> VideoStatistics:
        """
        Get video statistics with optional filtering.

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Video statistics response
        """
        try:
            logger.debug(f"Calculating video statistics with filters")

            # Get video statistics from database
            stats = await self.video_ops.get_video_statistics(
                timelapse_id=timelapse_id,
                camera_id=camera_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Broadcast SSE event for statistics calculation
            await self._broadcast_video_event(
                event_type=EVENT_VIDEO_STATS_CALCULATED,
                video_id=None,
                event_data={
                    "total_videos": stats.total_videos,
                    "total_size_bytes": stats.total_size_bytes,
                    "avg_duration_seconds": stats.avg_duration_seconds,
                    "avg_fps": stats.avg_fps,
                    "latest_video_at": (
                        stats.latest_video_at.isoformat()
                        if stats.latest_video_at
                        else None
                    ),
                    "filters_applied": {
                        "timelapse_id": timelapse_id,
                        "camera_id": camera_id,
                        "date_range": bool(start_date or end_date),
                    },
                },
            )

            logger.debug(f"Calculated video statistics: {stats.total_videos} videos")
            return stats

        except Exception as e:
            logger.error(f"Failed to calculate video statistics: {e}")
            return VideoStatistics(
                total_videos=0,
                total_size_bytes=0,
                avg_duration_seconds=0,
                avg_fps=0,
                latest_video_at=None,
            )

    async def get_videos_by_timelapse(
        self, timelapse_id: int
    ) -> List[VideoWithDetails]:
        """
        Get all videos for a specific timelapse.

        Args:
            timelapse_id: Timelapse ID to get videos for

        Returns:
            List of video records for the timelapse
        """
        return await self.get_videos(timelapse_id=timelapse_id)

    async def get_videos_by_camera(self, camera_id: int) -> List[VideoWithDetails]:
        """
        Get all videos for a specific camera.

        Args:
            camera_id: Camera ID to get videos for

        Returns:
            List of video records for the camera
        """
        return await self.get_videos(camera_id=camera_id)

    async def search_videos(self, search_term: str, limit: int = 50) -> List[Video]:
        """
        Search videos by name or description.

        Args:
            search_term: Search term to match against video names
            limit: Maximum number of results to return

        Returns:
            List of matching video records
        """
        try:
            logger.debug(f"Searching videos for term: {search_term}")

            videos = await self.video_ops.search_videos(search_term, limit)

            logger.debug(f"Found {len(videos)} videos matching search term")
            return videos

        except Exception as e:
            logger.error(f"Failed to search videos: {e}")
            return []

    async def validate_video_file(self, video_id: int) -> Dict[str, Any]:
        """
        Validate that a video file exists and get its metadata.

        Args:
            video_id: Video ID to validate

        Returns:
            Dictionary with validation results and file metadata
        """
        try:
            logger.debug(f"Validating video file for video {video_id}")

            video = await self.get_video_by_id(video_id)
            if not video:
                return {
                    "valid": False,
                    "error": "Video record not found",
                }

            if not video.file_path:
                return {
                    "valid": False,
                    "error": "Video has no file path",
                }

            # Construct full file path
            full_path = Path(settings.data_directory) / video.file_path

            if not full_path.exists():
                return {
                    "valid": False,
                    "error": f"Video file does not exist: {full_path}",
                    "file_path": str(full_path),
                }

            # Get file metadata
            file_size = get_file_size(str(full_path))

            return {
                "valid": True,
                "file_path": str(full_path),
                "file_size_bytes": file_size,
                "file_exists": True,
            }

        except Exception as e:
            logger.error(f"Failed to validate video file for video {video_id}: {e}")
            return {
                "valid": False,
                "error": str(e),
            }

    async def _broadcast_video_event(
        self,
        event_type: str,
        video_id: Optional[int],
        event_data: Dict[str, Any],
        priority: str = SSEPriority.NORMAL,
        source: str = "video_service",
    ) -> None:
        """
        Broadcast SSE event for video operations.

        Args:
            event_type: Type of event
            video_id: Video ID (if applicable)
            event_data: Event payload data
            priority: Event priority
            source: Event source
        """
        try:
            # Add timestamp to all events
            event_data_with_timestamp = {
                **event_data,
                "timestamp": (
                    await get_timezone_aware_timestamp_async(self.db)
                ).isoformat(),
            }

            await self.sse_ops.create_event(
                event_type=event_type,
                event_data=event_data_with_timestamp,
                priority=priority,
                source=source,
            )

            logger.debug(f"Broadcasted SSE event: {event_type} for video {video_id}")

        except Exception as e:
            logger.warning(f"Failed to broadcast SSE event {event_type}: {e}")

    async def get_queue_statistics_with_health(self, video_pipeline) -> dict:
        """
        Get comprehensive queue statistics with health assessment (async version).
        
        Args:
            video_pipeline: Video pipeline service for accessing job data
            
        Returns:
            Dictionary with queue statistics and health status
        """
        from ..constants import VIDEO_QUEUE_WARNING_THRESHOLD, VIDEO_QUEUE_ERROR_THRESHOLD
        from ..utils.router_helpers import run_sync_service_method
        
        try:
            # Get basic queue statistics from job service using async wrapper
            queue_status = await run_sync_service_method(
                video_pipeline.job_service.get_queue_status
            )
            
            # Calculate derived statistics
            total_jobs = sum(queue_status.values())
            pending_jobs = queue_status.get("pending", 0)
            processing_jobs = queue_status.get("processing", 0)
            completed_jobs = queue_status.get("completed", 0)
            failed_jobs = queue_status.get("failed", 0)
            
            # Determine queue health based on thresholds
            if pending_jobs >= VIDEO_QUEUE_ERROR_THRESHOLD:
                queue_health = "unhealthy"
            elif pending_jobs >= VIDEO_QUEUE_WARNING_THRESHOLD:
                queue_health = "degraded"
            else:
                queue_health = "healthy"
            
            return {
                "total_jobs": total_jobs,
                "pending_jobs": pending_jobs,
                "processing_jobs": processing_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "queue_health": queue_health
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue statistics (async): {e}")
            return {
                "total_jobs": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "queue_health": "unhealthy"
            }


class SyncVideoService:
    """
    Sync video service for worker processes using composition pattern.

    This service provides synchronous video data management for worker processes
    that need to create or manage video records without async/await complexity.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncVideoService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.video_ops = SyncVideoOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)

    def get_videos(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Video]:
        """
        Get videos with optional filtering (sync version).

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID
            status: Optional filter by video status
            limit: Maximum number of videos to return
            offset: Number of videos to skip for pagination

        Returns:
            List of video records matching criteria
        """
        try:
            logger.debug(
                f"Retrieving videos (sync) with filters: timelapse_id={timelapse_id}, camera_id={camera_id}"
            )

            videos = self.video_ops.get_videos(
                timelapse_id=timelapse_id,
                camera_id=camera_id,
                status=status,
                limit=limit,
                offset=offset,
            )

            logger.debug(f"Retrieved {len(videos)} videos (sync)")
            return videos

        except Exception as e:
            logger.error(f"Failed to get videos (sync): {e}")
            return []

    def get_video_by_id(self, video_id: int) -> Optional[Video]:
        """
        Get video by ID (sync version).

        Args:
            video_id: Video ID to retrieve

        Returns:
            Video record or None if not found
        """
        try:
            logger.debug(f"Retrieving video {video_id} (sync)")

            video = self.video_ops.get_video_by_id(video_id)
            if video:
                logger.debug(f"Found video {video_id} (sync)")
            else:
                logger.warning(f"Video {video_id} not found (sync)")

            return video

        except Exception as e:
            logger.error(f"Failed to get video {video_id} (sync): {e}")
            return None

    def create_video_record(self, video_data: Dict[str, Any]) -> Optional[Video]:
        """
        Create a new video record (sync version).

        Args:
            video_data: Video creation data as dictionary

        Returns:
            Created video record or None if failed
        """
        try:
            logger.debug(
                f"Creating video record (sync) for timelapse {video_data.get('timelapse_id')}"
            )

            # Ensure timezone-aware timestamp
            current_time = get_timezone_aware_timestamp_sync(self.db)

            # Prepare video record data
            video_record_data = {
                **video_data,
                "created_at": current_time,
                "updated_at": current_time,
            }

            # Create video record
            video_record = self.video_ops.create_video_record(video_record_data)

            if video_record:
                logger.info(
                    f"✅ Created video record {video_record.id} (sync) for timelapse {video_data.get('timelapse_id')}"
                )

                # Broadcast SSE event
                self._broadcast_video_event(
                    event_type=EVENT_VIDEO_CREATED,
                    video_id=video_record.id,
                    event_data={
                        "video_id": video_record.id,
                        "timelapse_id": video_data.get("timelapse_id"),
                        "camera_id": video_data.get("camera_id"),
                        "name": video_data.get("name"),
                        "file_path": video_data.get("file_path"),
                        "status": video_data.get("status"),
                        "trigger_type": video_data.get("trigger_type", "unknown"),
                    },
                )

                return video_record
            else:
                logger.error(
                    f"❌ Failed to create video record (sync) for timelapse {video_data.get('timelapse_id')}"
                )
                return None

        except Exception as e:
            logger.error(f"❌ Error creating video record (sync): {e}")
            return None

    def delete_video(self, video_id: int) -> bool:
        """
        Delete a video record (sync version).

        Args:
            video_id: Video ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            logger.debug(f"Deleting video {video_id} (sync)")

            # Get video info before deletion for event data
            video_info = self.get_video_by_id(video_id)
            if not video_info:
                logger.error(f"Video {video_id} not found for deletion (sync)")
                return False

            # Perform deletion
            success = self.video_ops.delete_video(video_id)

            if success:
                logger.info(f"✅ Deleted video {video_id} (sync)")

                # Broadcast SSE event
                self._broadcast_video_event(
                    event_type=EVENT_VIDEO_DELETED,
                    video_id=video_id,
                    event_data={
                        "video_id": video_id,
                        "timelapse_id": video_info.timelapse_id,
                        "camera_id": video_info.camera_id,
                        "name": video_info.name,
                        "file_path": video_info.file_path,
                    },
                )

                return True
            else:
                logger.error(f"❌ Failed to delete video {video_id} (sync)")
                return False

        except Exception as e:
            logger.error(f"❌ Error deleting video {video_id} (sync): {e}")
            return False

    def _broadcast_video_event(
        self,
        event_type: str,
        video_id: Optional[int],
        event_data: Dict[str, Any],
        priority: str = SSEPriority.NORMAL,
        source: str = "video_service",
    ) -> None:
        """
        Broadcast SSE event for video operations (sync version).

        Args:
            event_type: Type of event
            video_id: Video ID (if applicable)
            event_data: Event payload data
            priority: Event priority
            source: Event source
        """
        try:
            # Add timestamp to all events
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

            logger.debug(
                f"Broadcasted SSE event (sync): {event_type} for video {video_id}"
            )

        except Exception as e:
            logger.warning(f"Failed to broadcast SSE event (sync) {event_type}: {e}")

    def get_queue_statistics_with_health(self, video_pipeline) -> dict:
        """
        Get comprehensive queue statistics with health assessment.
        
        Args:
            video_pipeline: Video pipeline service for accessing job data
            
        Returns:
            Dictionary with queue statistics and health status
        """
        from ..constants import VIDEO_QUEUE_WARNING_THRESHOLD, VIDEO_QUEUE_ERROR_THRESHOLD
        
        try:
            # Get basic queue statistics from job service
            queue_status = video_pipeline.job_service.get_queue_status()
            
            # Calculate derived statistics
            total_jobs = sum(queue_status.values())
            pending_jobs = queue_status.get("pending", 0)
            processing_jobs = queue_status.get("processing", 0)
            completed_jobs = queue_status.get("completed", 0)
            failed_jobs = queue_status.get("failed", 0)
            
            # Determine queue health based on thresholds
            if pending_jobs >= VIDEO_QUEUE_ERROR_THRESHOLD:
                queue_health = "unhealthy"
            elif pending_jobs >= VIDEO_QUEUE_WARNING_THRESHOLD:
                queue_health = "degraded"
            else:
                queue_health = "healthy"
            
            return {
                "total_jobs": total_jobs,
                "pending_jobs": pending_jobs,
                "processing_jobs": processing_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "queue_health": queue_health
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue statistics: {e}")
            return {
                "total_jobs": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "queue_health": "unhealthy"
            }
