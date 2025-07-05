# backend/app/database/video_operations.py
"""
Video database operations module - Composition-based architecture.

This module handles all video-related database operations using dependency injection
instead of mixin inheritance, providing type-safe Pydantic model interfaces.
"""
# TODO: Not using timeezone aware timestamps yet.
from typing import List, Optional, Dict, Any
from loguru import logger
from pydantic import ValidationError

from .core import AsyncDatabase, SyncDatabase
from ..models.video_model import Video, VideoWithDetails
from ..models.shared_models import (
    VideoGenerationJob,
    VideoGenerationJobWithDetails,
    VideoGenerationJobCreate,  # why is this not used?
    VideoStatistics,
)


class VideoOperations:
    """
    Video database operations using composition pattern.

    This class receives database instance via dependency injection,
    providing type-safe Pydantic model interfaces.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """
        Initialize VideoOperations with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db

    def _row_to_video(self, row: Dict[str, Any]) -> Video:
        """Convert database row to Video model."""
        # Filter fields that belong to Video model
        video_fields = {k: v for k, v in row.items() if k in Video.model_fields}
        return Video(**video_fields)

    def _row_to_video_with_details(self, row: Dict[str, Any]) -> VideoWithDetails:
        """Convert database row to VideoWithDetails model."""
        # Extract base video fields
        video_fields = {k: v for k, v in row.items() if k in Video.model_fields}

        # Add additional fields for VideoWithDetails
        details_fields = video_fields.copy()
        if "camera_name" in row:
            details_fields["camera_name"] = row["camera_name"]

        return VideoWithDetails(**details_fields)

    def _row_to_video_generation_job(self, row: Dict[str, Any]) -> VideoGenerationJob:
        """Convert database row to VideoGenerationJob model."""
        try:

            job_fields = {
                k: v for k, v in row.items() if k in VideoGenerationJob.model_fields
            }
            return VideoGenerationJob.model_validate(job_fields)
        except ValidationError as e:
            logger.error(f"Error creating VideoGenerationJob model: {e}")
            raise

    def _row_to_video_generation_job_with_details(
        self, row: Dict[str, Any]
    ) -> VideoGenerationJobWithDetails:
        """Convert database row to VideoGenerationJobWithDetails model."""
        try:

            # Extract base job fields
            job_fields = {
                k: v for k, v in row.items() if k in VideoGenerationJob.model_fields
            }

            # Add additional fields for details
            details_fields = job_fields.copy()
            if "timelapse_name" in row:
                details_fields["timelapse_name"] = row["timelapse_name"]
            if "camera_name" in row:
                details_fields["camera_name"] = row["camera_name"]

            return VideoGenerationJobWithDetails.model_validate(details_fields)
        except ValidationError as e:
            logger.error(f"Error creating VideoGenerationJobWithDetails model: {e}")
            raise

    async def get_videos(
        self, timelapse_id: Optional[int] = None
    ) -> List[VideoWithDetails]:
        """
        Retrieve videos with optional timelapse filtering.

        Args:
            timelapse_id: Optional timelapse ID to filter by

        Returns:
            List of VideoWithDetails model instances

        Usage:
            videos = await video_ops.get_videos()
            timelapse_videos = await video_ops.get_videos(timelapse_id=1)
        """
        base_query = """
        SELECT
            v.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM videos v
        JOIN timelapses t ON v.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        """

        if timelapse_id:
            query = base_query + " WHERE v.timelapse_id = %s ORDER BY v.created_at DESC"
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (timelapse_id,))
                    results = await cur.fetchall()
                    return [self._row_to_video_with_details(row) for row in results]
        else:
            query = base_query + " ORDER BY v.created_at DESC"
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    results = await cur.fetchall()
                    return [self._row_to_video_with_details(row) for row in results]

    async def get_video_by_id(self, video_id: int) -> Optional[VideoWithDetails]:
        """
        Retrieve a specific video by ID.

        Args:
            video_id: ID of the video to retrieve

        Returns:
            VideoWithDetails model instance, or None if not found

        Usage:
            video = await video_ops.get_video_by_id(1)
        """
        query = """
        SELECT 
            v.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM videos v
        JOIN timelapses t ON v.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE v.id = %s
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (video_id,))
                results = await cur.fetchall()
                return self._row_to_video_with_details(results[0]) if results else None

    async def create_video_record(self, video_data: Dict[str, Any]) -> Video:
        """
        Create a new video record.

        Args:
            video_data: Dictionary containing video metadata

        Returns:
            Created Video model instance

        Usage:
            video = await video_ops.create_video_record({
                'timelapse_id': 1,
                'file_path': '/path/to/video.mp4',
                'title': 'Daily Timelapse'
            })
        """
        # Pydantic models will handle validation automatically
        query = """
        INSERT INTO videos (
            timelapse_id, file_path, file_size, duration_seconds,
            title, description, fps, bitrate, width, height,
            generation_settings, start_day, end_day, total_frames
        ) VALUES (
            %(timelapse_id)s, %(file_path)s, %(file_size)s, %(duration_seconds)s,
            %(title)s, %(description)s, %(fps)s, %(bitrate)s, %(width)s, %(height)s,
            %(generation_settings)s, %(start_day)s, %(end_day)s, %(total_frames)s
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, video_data)
                results = await cur.fetchall()
                if results:
                    row = results[0]
                    created_video = self._row_to_video(row)
                    await self.db.broadcast_event(
                        "video_created", {"video": created_video.model_dump()}
                    )
                    return created_video
                raise Exception("Failed to create video record")

    async def update_video(self, video_id: int, video_data: Dict[str, Any]) -> Video:
        """
        Update an existing video record.

        Args:
            video_id: ID of the video to update
            video_data: Dictionary containing updated video data

        Returns:
            Updated Video model instance

        Usage:
            video = await video_ops.update_video(1, {'title': 'Updated Title'})
        """
        # Build dynamic update query
        update_fields = []
        params = {"video_id": video_id}

        # Dynamically determine updateable fields from Video model, excluding immutable fields
        updateable_fields = [
            field
            for field in Video.model_fields
            if field not in {"id", "timelapse_id", "created_at", "updated_at"}
        ]

        for field in updateable_fields:
            if field in video_data:
                update_fields.append(f"{field} = %({field})s")
                params[field] = video_data[field]

        if not update_fields:
            current_video = await self.get_video_by_id(video_id)
            if current_video is None:
                raise ValueError(f"Video {video_id} not found")
            # Convert VideoWithDetails to Video for return type consistency
            return Video(
                **{
                    k: v
                    for k, v in current_video.model_dump().items()
                    if k in Video.model_fields
                }
            )

        update_fields.append("updated_at = NOW()")

        query = f"""
        UPDATE videos 
        SET {', '.join(update_fields)}
        WHERE id = %(video_id)s 
        RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                if results:
                    row = results[0]
                    updated_video = self._row_to_video(row)
                    await self.db.broadcast_event(
                        "video_updated", {"video": updated_video.model_dump()}
                    )
                    return updated_video
                raise Exception(f"Failed to update video {video_id}")

    async def delete_video(self, video_id: int) -> bool:
        """
        Delete a video record.

        Args:
            video_id: ID of the video to delete

        Returns:
            True if video was deleted successfully

        Usage:
            success = await video_ops.delete_video(1)
        """
        query = "DELETE FROM videos WHERE id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (video_id,))
                affected = cur.rowcount

                if affected and affected > 0:
                    await self.db.broadcast_event(
                        "video_deleted", {"video_id": video_id}
                    )
                    return True
                return False

    async def get_video_generation_jobs(
        self, status: Optional[str] = None
    ) -> List[VideoGenerationJobWithDetails]:
        """
        Get video generation jobs with optional status filtering.

        Args:
            status: Optional status to filter by ('pending', 'processing', 'completed', 'failed')

        Returns:
            List of VideoGenerationJobWithDetails model instances

        Usage:
            jobs = await video_ops.get_video_generation_jobs()
            pending_jobs = await video_ops.get_video_generation_jobs('pending')
        """
        base_query = """
        SELECT 
            vgj.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM video_generation_jobs vgj
        JOIN timelapses t ON vgj.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                if status:
                    query = (
                        base_query
                        + " WHERE vgj.status = %s ORDER BY vgj.created_at DESC"
                    )
                    await cur.execute(query, (status,))
                else:
                    query = base_query + " ORDER BY vgj.created_at DESC"
                    await cur.execute(query)

                results = await cur.fetchall()
                return [
                    self._row_to_video_generation_job_with_details(row)
                    for row in results
                ]

    async def create_video_generation_job(
        self, job_data: Dict[str, Any]
    ) -> VideoGenerationJob:
        """
        Create a new video generation job.

        Args:
            job_data: Dictionary containing job configuration

        Returns:
            Created job record

        Usage:
            job = await video_ops.create_video_generation_job({
                'timelapse_id': 1,
                'trigger_type': 'manual',
                'settings': {...}
            })
        """
        query = """
        INSERT INTO video_generation_jobs (
            timelapse_id, trigger_type, status, settings
        ) VALUES (
            %(timelapse_id)s, %(trigger_type)s, 'pending', %(settings)s
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, job_data)
                results = await cur.fetchall()
                if results:
                    job = self._row_to_video_generation_job(results[0])
                    await self.db.broadcast_event(
                        "video_job_created", {"job": job.model_dump()}
                    )
                    return job
                raise Exception("Failed to create video generation job")

    async def update_video_generation_job_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> VideoGenerationJob:
        """
        Update the status of a video generation job.

        Args:
            job_id: ID of the job
            status: New status ('pending', 'processing', 'completed', 'failed')
            error_message: Optional error message if failed
            video_path: Optional path to generated video if completed

        Returns:
            Updated job record

        Usage:
            job = await video_ops.update_video_generation_job_status(1, 'completed', video_path='/path/to/video.mp4')
        """
        query = """
        UPDATE video_generation_jobs 
        SET status = %s,
            error_message = %s,
            video_path = %s,
            started_at = CASE WHEN %s = 'processing' THEN NOW() ELSE started_at END,
            completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE completed_at END,
            updated_at = NOW()
        WHERE id = %s 
        RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query, (status, error_message, video_path, status, status, job_id)
                )
                results = await cur.fetchall()
                if results:
                    job = self._row_to_video_generation_job(results[0])
                    await self.db.broadcast_event(
                        "video_job_status_changed", {"job_id": job_id, "status": status}
                    )
                    return job
                raise Exception(f"Failed to update video generation job {job_id}")

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
        if timelapse_id:
            query = """
            SELECT 
                COUNT(*) as total_videos,
                SUM(file_size) as total_size_bytes,
                AVG(duration_seconds) as avg_duration_seconds,
                AVG(fps) as avg_fps,
                MAX(created_at) as latest_video_at
            FROM videos 
            WHERE timelapse_id = %s
            """
            params = (timelapse_id,)
        else:
            query = """
            SELECT 
                COUNT(*) as total_videos,
                SUM(file_size) as total_size_bytes,
                AVG(duration_seconds) as avg_duration_seconds,
                AVG(fps) as avg_fps,
                MAX(created_at) as latest_video_at
            FROM videos
            """
            params = ()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                if results:
                    try:
                        return VideoStatistics.model_validate(dict(results[0]))
                    except ValidationError as e:
                        logger.error(f"Error creating VideoStatistics model: {e}")
                        return VideoStatistics()  # Return empty stats
                return VideoStatistics()  # Return empty stats


class SyncVideoOperations:
    """
    Sync video database operations for worker processes.

    Uses sync database methods for worker process compatibility.
    """

    def __init__(self, db: SyncDatabase) -> None:
        """
        Initialize SyncVideoOperations with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db

    def _row_to_video_generation_job_with_details(
        self, row: Dict[str, Any]
    ) -> VideoGenerationJobWithDetails:
        """Convert database row to VideoGenerationJobWithDetails model."""
        try:

            # Extract base job fields
            job_fields = {
                k: v for k, v in row.items() if k in VideoGenerationJob.model_fields
            }

            # Add additional fields for details
            details_fields = job_fields.copy()
            if "timelapse_name" in row:
                details_fields["timelapse_name"] = row["timelapse_name"]
            if "camera_name" in row:
                details_fields["camera_name"] = row["camera_name"]

            return VideoGenerationJobWithDetails.model_validate(details_fields)
        except ValidationError as e:
            logger.error(f"Error creating VideoGenerationJobWithDetails model: {e}")
            raise

    def get_pending_video_generation_jobs(self) -> List[VideoGenerationJobWithDetails]:
        """
        Get pending video generation jobs for processing.

        Returns:
            List of VideoGenerationJobWithDetails model instances

        Usage:
            jobs = video_ops.get_pending_video_generation_jobs()
        """
        query = """
        SELECT
            vgj.*,
            t.name as timelapse_name,
            c.name as camera_name,
            c.id as camera_id
        FROM video_generation_jobs vgj
        JOIN timelapses t ON vgj.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE vgj.status = 'pending'
        ORDER BY vgj.created_at ASC
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()
                return [
                    self._row_to_video_generation_job_with_details(row)
                    for row in results
                ]

    def claim_video_generation_job(self, job_id: int) -> bool:
        """
        Claim a video generation job for processing.

        Args:
            job_id: ID of the job to claim

        Returns:
            True if job was successfully claimed

        Usage:
            claimed = video_ops.claim_video_generation_job(1)
        """
        query = """
        UPDATE video_generation_jobs 
        SET status = 'processing',
            started_at = NOW(),
            updated_at = NOW()
        WHERE id = %s AND status = 'pending'
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (job_id,))
                return cur.rowcount > 0

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

        Usage:
            completed = video_ops.complete_video_generation_job(1, '/path/to/video.mp4')
        """
        status = "completed" if success else "failed"

        query = """
        UPDATE video_generation_jobs 
        SET status = %s,
            video_path = %s,
            error_message = %s,
            completed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, video_path, error_message, job_id))
                if cur.rowcount > 0:
                    self.db.broadcast_event(
                        "video_job_completed",
                        {"job_id": job_id, "status": status, "video_path": video_path},
                    )
                    return True
                return False

    def create_video_record(self, video_data: Dict[str, Any]) -> Video:
        """
        Create a new video record.

        Args:
            video_data: Dictionary containing video metadata

        Returns:
            Created Video model instance

        Usage:
            video = video_ops.create_video_record({...})
        """
        query = """
        INSERT INTO videos (
            timelapse_id, file_path, file_size, duration_seconds,
            title, description, fps, bitrate, width, height,
            generation_settings, start_day, end_day, total_frames
        ) VALUES (
            %(timelapse_id)s, %(file_path)s, %(file_size)s, %(duration_seconds)s,
            %(title)s, %(description)s, %(fps)s, %(bitrate)s, %(width)s, %(height)s,
            %(generation_settings)s, %(start_day)s, %(end_day)s, %(total_frames)s
        ) RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, video_data)
                results = cur.fetchall()
                if results:
                    video_row = results[0]
                    video = self._row_to_video(video_row)
                    self.db.broadcast_event(
                        "video_created", {"video": video.model_dump()}
                    )
                    return video
                raise Exception("Failed to create video record")

    def _row_to_video(self, row: Dict[str, Any]) -> Video:
        """Convert database row to Video model."""
        # Filter fields that belong to Video model
        video_fields = {k: v for k, v in row.items() if k in Video.model_fields}
        return Video.model_validate(video_fields)

    def cleanup_old_video_jobs(self, days_to_keep: int = 30) -> int:
        """
        Clean up old completed video generation jobs.

        Args:
            days_to_keep: Number of days to keep completed jobs (default: 30)

        Returns:
            Number of jobs deleted

        Usage:
            deleted_count = video_ops.cleanup_old_video_jobs(7)
        """
        query = """
        DELETE FROM video_generation_jobs 
        WHERE status IN ('completed', 'failed')
        AND completed_at < NOW() - INTERVAL '%s days'
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (days_to_keep,))
                affected = cur.rowcount

                if affected and affected > 0:
                    logger.info(f"Cleaned up {affected} old video generation jobs")

                return affected or 0

    def create_video_generation_job(self, job_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new video generation job (sync version).
        
        Args:
            job_data: Dictionary containing job configuration
            
        Returns:
            Job ID if successful, None if failed
            
        Usage:
            job_id = video_ops.create_video_generation_job({
                'timelapse_id': 1,
                'trigger_type': 'manual',
                'priority': 'medium',
                'settings': {...}
            })
        """
        query = """
        INSERT INTO video_generation_jobs (
            timelapse_id, trigger_type, priority, settings, status
        ) VALUES (
            %(timelapse_id)s, %(trigger_type)s, %(priority)s, %(settings)s, 'pending'
        ) RETURNING id
        """
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, job_data)
                    result = cur.fetchone()
                    if result:
                        job_id = dict(result)["id"]
                        conn.commit()
                        
                        # Broadcast SSE event
                        try:
                            from ..utils.timezone_utils import get_timezone_aware_timestamp_sync
                            from ..constants import EVENT_VIDEO_JOB_QUEUED
                            
                            self.db.broadcast_event(
                                EVENT_VIDEO_JOB_QUEUED,
                                {
                                    "job_id": job_id,
                                    "timelapse_id": job_data.get("timelapse_id"),
                                    "trigger_type": job_data.get("trigger_type"),
                                    "priority": job_data.get("priority", "medium"),
                                    "timestamp": get_timezone_aware_timestamp_sync(self.db).isoformat(),
                                },
                            )
                        except Exception as e:
                            logger.warning(f"Failed to broadcast job queued event: {e}")
                        
                        return job_id
                    return None
        except Exception as e:
            logger.error(f"Failed to create video generation job: {e}")
            return None

    def start_video_generation_job(self, job_id: int) -> bool:
        """
        Mark a video generation job as started.
        
        Args:
            job_id: ID of the job to start
            
        Returns:
            True if successful, False otherwise
            
        Usage:
            success = video_ops.start_video_generation_job(123)
        """
        query = """
        UPDATE video_generation_jobs 
        SET status = 'processing', started_at = NOW()
        WHERE id = %s AND status = 'pending'
        """
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (job_id,))
                    success = cur.rowcount > 0
                    if success:
                        conn.commit()
                        
                        # Broadcast SSE event
                        try:
                            from ..utils.timezone_utils import get_timezone_aware_timestamp_sync
                            from ..constants import EVENT_VIDEO_JOB_STARTED
                            
                            self.db.broadcast_event(
                                EVENT_VIDEO_JOB_STARTED,
                                {
                                    "job_id": job_id,
                                    "timestamp": get_timezone_aware_timestamp_sync(self.db).isoformat(),
                                },
                            )
                        except Exception as e:
                            logger.warning(f"Failed to broadcast job started event: {e}")
                    
                    return success
        except Exception as e:
            logger.error(f"Failed to start video generation job {job_id}: {e}")
            return False

    def complete_video_generation_job(self, job_id: int, success: bool, error_message: Optional[str] = None, video_path: Optional[str] = None) -> bool:
        """
        Mark a video generation job as completed.
        
        Args:
            job_id: ID of the job to complete
            success: Whether the job completed successfully
            error_message: Error message if job failed
            video_path: Path to generated video if successful
            
        Returns:
            True if update successful, False otherwise
            
        Usage:
            video_ops.complete_video_generation_job(123, True, video_path="/path/to/video.mp4")
        """
        status = "completed" if success else "failed"
        query = """
        UPDATE video_generation_jobs 
        SET status = %s, completed_at = NOW(), error_message = %s, video_path = %s
        WHERE id = %s
        """
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (status, error_message, video_path, job_id))
                    update_success = cur.rowcount > 0
                    if update_success:
                        conn.commit()
                        
                        # Broadcast SSE event
                        try:
                            from ..utils.timezone_utils import get_timezone_aware_timestamp_sync
                            from ..constants import EVENT_VIDEO_JOB_COMPLETED
                            
                            self.db.broadcast_event(
                                EVENT_VIDEO_JOB_COMPLETED,
                                {
                                    "job_id": job_id,
                                    "success": success,
                                    "video_path": video_path,
                                    "timestamp": get_timezone_aware_timestamp_sync(self.db).isoformat(),
                                },
                            )
                        except Exception as e:
                            logger.warning(f"Failed to broadcast job completed event: {e}")
                    
                    return update_success
        except Exception as e:
            logger.error(f"Failed to complete video generation job {job_id}: {e}")
            return False

    def get_queue_status(self) -> Dict[str, int]:
        """
        Get current queue status with job counts by status.
        
        Returns:
            Dictionary with job counts
            
        Usage:
            status = video_ops.get_queue_status()
            # Returns: {"pending": 5, "processing": 2, "completed": 10, "failed": 1}
        """
        query = """
        SELECT status, COUNT(*) as count
        FROM video_generation_jobs
        GROUP BY status
        """
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    
                    status_counts = {}
                    for row in results:
                        row_dict = dict(row)
                        status_counts[row_dict["status"]] = row_dict["count"]
                    
                    return status_counts
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {}
    
    def get_video_generation_jobs_by_status(self, status: Optional[str] = None, limit: int = 50) -> List[VideoGenerationJobWithDetails]:
        """
        Get video generation jobs with optional status filtering and limit.
        
        Args:
            status: Optional status to filter by
            limit: Maximum number of jobs to return
            
        Returns:
            List of VideoGenerationJobWithDetails
        """
        try:
            if status:
                query = """
                    SELECT j.*, t.name as timelapse_name, c.name as camera_name, c.id as camera_id
                    FROM video_generation_jobs j
                    JOIN timelapses t ON j.timelapse_id = t.id
                    JOIN cameras c ON t.camera_id = c.id
                    WHERE j.status = %s
                    ORDER BY j.created_at DESC LIMIT %s
                """
                params = (status, limit)
            else:
                query = """
                    SELECT j.*, t.name as timelapse_name, c.name as camera_name, c.id as camera_id
                    FROM video_generation_jobs j
                    JOIN timelapses t ON j.timelapse_id = t.id
                    JOIN cameras c ON t.camera_id = c.id
                    ORDER BY j.created_at DESC LIMIT %s
                """
                params = (limit,)
                
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    results = cur.fetchall()
                    
                    return [
                        self._row_to_video_generation_job_with_details(row)
                        for row in results
                    ]
        except Exception as e:
            logger.error(f"Failed to get video generation jobs by status: {e}")
            return []
    
    def get_timelapse_automation_settings(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Get effective automation settings for a timelapse.
        
        Follows inheritance pattern: timelapse settings override camera defaults.
        
        Args:
            timelapse_id: ID of the timelapse
            
        Returns:
            Dictionary with automation settings
        """
        try:
            query = """
                SELECT 
                    t.video_automation_mode as t_mode,
                    t.generation_schedule as t_schedule,
                    t.milestone_config as t_milestone,
                    c.video_automation_mode as c_mode,
                    c.generation_schedule as c_schedule,
                    c.milestone_config as c_milestone
                FROM timelapses t
                JOIN cameras c ON t.camera_id = c.id
                WHERE t.id = %s
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    row = cur.fetchone()
                    
                    if not row:
                        return {"video_automation_mode": "manual"}
                    
                    # Apply inheritance pattern
                    row_dict = dict(row)
                    return {
                        "video_automation_mode": row_dict["t_mode"] or row_dict["c_mode"] or "manual",
                        "generation_schedule": row_dict["t_schedule"] or row_dict["c_schedule"],
                        "milestone_config": row_dict["t_milestone"] or row_dict["c_milestone"],
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get automation settings for timelapse {timelapse_id}: {e}")
            return {"video_automation_mode": "manual"}
    
    def check_per_capture_throttle(self, camera_id: int, throttle_minutes: int) -> bool:
        """
        Check if per-capture generation should be throttled for a camera.
        
        Args:
            camera_id: ID of the camera
            throttle_minutes: Throttle window in minutes
            
        Returns:
            True if should throttle (recent job exists), False otherwise
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM video_generation_jobs j
                JOIN timelapses t ON j.timelapse_id = t.id
                WHERE t.camera_id = %s
                AND j.trigger_type = 'per_capture'
                AND j.created_at > NOW() - INTERVAL '%s minutes'
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (camera_id, throttle_minutes))
                    result = cur.fetchone()
                    
                    if result:
                        count = dict(result)["count"]
                        return count > 0
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to check per-capture throttle for camera {camera_id}: {e}")
            return True  # Err on the side of caution
    
    def get_milestone_automation_timelapses(self) -> List[Dict[str, Any]]:
        """
        Get all running timelapses with milestone automation enabled.
        
        Returns:
            List of dicts with timelapse_id, image_count, and milestone_config
        """
        try:
            query = """
                SELECT 
                    t.id,
                    COUNT(i.id) as image_count,
                    COALESCE(t.milestone_config, c.milestone_config) as milestone_config
                FROM timelapses t
                JOIN cameras c ON t.camera_id = c.id
                LEFT JOIN images i ON t.id = i.timelapse_id
                WHERE t.status = 'running'
                AND (
                    (t.video_automation_mode = 'milestone') OR 
                    (t.video_automation_mode IS NULL AND c.video_automation_mode = 'milestone')
                )
                GROUP BY t.id, t.milestone_config, c.milestone_config
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    
                    return [dict(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Failed to get milestone automation timelapses: {e}")
            return []
    
    def check_milestone_already_generated(self, timelapse_id: int, threshold: int) -> bool:
        """
        Check if a milestone video was already generated for a specific threshold.
        
        Args:
            timelapse_id: ID of the timelapse
            threshold: The milestone threshold
            
        Returns:
            True if already generated, False otherwise
        """
        try:
            query = """
                SELECT id FROM video_generation_jobs
                WHERE timelapse_id = %s 
                AND trigger_type = 'milestone'
                AND settings::json->>'threshold' = %s
                LIMIT 1
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id, str(threshold)))
                    return cur.fetchone() is not None
                    
        except Exception as e:
            logger.error(f"Failed to check milestone generation for timelapse {timelapse_id}: {e}")
            return True  # Err on the side of caution
    
    def get_scheduled_automation_timelapses(self) -> List[Dict[str, Any]]:
        """
        Get all running timelapses with scheduled automation enabled.
        
        Returns:
            List of dicts with timelapse_id and schedule config
        """
        try:
            query = """
                SELECT 
                    t.id,
                    COALESCE(t.generation_schedule, c.generation_schedule) as schedule
                FROM timelapses t
                JOIN cameras c ON t.camera_id = c.id
                WHERE t.status = 'running'
                AND (
                    (t.video_automation_mode = 'scheduled') OR 
                    (t.video_automation_mode IS NULL AND c.video_automation_mode = 'scheduled')
                )
                AND (t.generation_schedule IS NOT NULL OR c.generation_schedule IS NOT NULL)
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    
                    return [dict(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Failed to get scheduled automation timelapses: {e}")
            return []
    
    def check_scheduled_already_generated(self, timelapse_id: int, schedule_type: str) -> bool:
        """
        Check if a scheduled video was already generated for the current period.
        
        Args:
            timelapse_id: ID of the timelapse
            schedule_type: 'daily' or 'weekly'
            
        Returns:
            True if already generated, False otherwise
        """
        try:
            if schedule_type == "daily":
                query = """
                    SELECT id FROM video_generation_jobs
                    WHERE timelapse_id = %s 
                    AND trigger_type = 'scheduled'
                    AND created_at >= CURRENT_DATE
                    LIMIT 1
                """
            elif schedule_type == "weekly":
                query = """
                    SELECT id FROM video_generation_jobs
                    WHERE timelapse_id = %s 
                    AND trigger_type = 'scheduled'
                    AND created_at >= date_trunc('week', CURRENT_DATE)
                    LIMIT 1
                """
            else:
                return False
                
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    return cur.fetchone() is not None
                    
        except Exception as e:
            logger.error(f"Failed to check scheduled generation for timelapse {timelapse_id}: {e}")
            return True  # Err on the side of caution
    
    def get_active_job_count(self) -> int:
        """
        Get count of currently processing jobs.
        
        Returns:
            Number of jobs with 'processing' status
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM video_generation_jobs
                WHERE status = 'processing'
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    
                    if result:
                        return dict(result)["count"]
                    return 0
                    
        except Exception as e:
            logger.error(f"Failed to get active job count: {e}")
            return 0
    
    def get_timelapse_video_settings(self, timelapse_id: int, job_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get effective video generation settings for a timelapse.
        
        Follows inheritance pattern: job_settings > timelapse settings > camera defaults > system defaults.
        
        Args:
            timelapse_id: ID of the timelapse
            job_settings: Optional job-specific settings (highest priority)
            
        Returns:
            Dictionary with effective video generation settings
        """
        try:
            # Import constants here to avoid circular imports
            from ..constants import DEFAULT_OVERLAY_SETTINGS
            
            query = """
                SELECT 
                    t.video_generation_mode as t_mode,
                    t.standard_fps as t_fps,
                    t.enable_time_limits as t_time_limits,
                    t.min_time_seconds as t_min_time,
                    t.max_time_seconds as t_max_time,
                    t.target_time_seconds as t_target_time,
                    t.fps_bounds_min as t_fps_min,
                    t.fps_bounds_max as t_fps_max,
                    c.video_generation_mode as c_mode,
                    c.standard_fps as c_fps,
                    c.enable_time_limits as c_time_limits,
                    c.min_time_seconds as c_min_time,
                    c.max_time_seconds as c_max_time,
                    c.target_time_seconds as c_target_time,
                    c.fps_bounds_min as c_fps_min,
                    c.fps_bounds_max as c_fps_max
                FROM timelapses t
                JOIN cameras c ON t.camera_id = c.id
                WHERE t.id = %s
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    row = cur.fetchone()
                    
                    if not row:
                        logger.warning(f"Timelapse {timelapse_id} not found, using defaults")
                        return self._get_default_video_settings()
                        
                    row_dict = dict(row)
                    job_settings = job_settings or {}
                    
                    # Apply inheritance: job_settings > timelapse > camera > defaults
                    settings = {
                        "video_generation_mode": job_settings.get("video_generation_mode")
                        or row_dict["t_mode"]
                        or row_dict["c_mode"]
                        or "standard",
                        "fps": job_settings.get("fps")
                        or row_dict["t_fps"]
                        or row_dict["c_fps"]
                        or 24.0,
                        "enable_time_limits": (
                            job_settings.get("enable_time_limits")
                            if "enable_time_limits" in job_settings
                            else (
                                row_dict["t_time_limits"]
                                if row_dict["t_time_limits"] is not None
                                else row_dict["c_time_limits"]
                            )
                            or False
                        ),
                        "min_time_seconds": job_settings.get("min_time_seconds")
                        or row_dict["t_min_time"]
                        or row_dict["c_min_time"]
                        or 5,
                        "max_time_seconds": job_settings.get("max_time_seconds")
                        or row_dict["t_max_time"]
                        or row_dict["c_max_time"]
                        or 300,
                        "target_time_seconds": job_settings.get("target_time_seconds")
                        or row_dict["t_target_time"]
                        or row_dict["c_target_time"]
                        or 60,
                        "fps_bounds_min": job_settings.get("fps_bounds_min")
                        or row_dict["t_fps_min"]
                        or row_dict["c_fps_min"]
                        or 1,
                        "fps_bounds_max": job_settings.get("fps_bounds_max")
                        or row_dict["t_fps_max"]
                        or row_dict["c_fps_max"]
                        or 60,
                        "quality": job_settings.get("quality", "medium"),
                        "overlay_settings": job_settings.get(
                            "overlay_settings",
                            DEFAULT_OVERLAY_SETTINGS,
                        ),
                    }

                    return settings
                    
        except Exception as e:
            logger.error(f"Failed to get effective video settings for timelapse {timelapse_id}: {e}")
            return self._get_default_video_settings()
    
    def _get_default_video_settings(self) -> Dict[str, Any]:
        """Get default video generation settings."""
        from ..constants import DEFAULT_OVERLAY_SETTINGS
        
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
    
    def get_automation_mode_stats(self) -> Dict[str, int]:
        """
        Get distribution of automation modes for running timelapses.
        
        Returns:
            Dictionary with mode counts
        """
        try:
            query = """
                SELECT 
                    COALESCE(t.video_automation_mode, c.video_automation_mode, 'manual') as mode,
                    COUNT(*) as count
                FROM timelapses t
                JOIN cameras c ON t.camera_id = c.id
                WHERE t.status = 'running'
                GROUP BY COALESCE(t.video_automation_mode, c.video_automation_mode, 'manual')
            """
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    
                    mode_stats = {}
                    for row in results:
                        row_dict = dict(row)
                        mode_stats[row_dict["mode"]] = row_dict["count"]
                        
                    return mode_stats
                    
        except Exception as e:
            logger.error(f"Failed to get automation mode stats: {e}")
            return {}
