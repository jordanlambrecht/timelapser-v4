# backend/app/database/video_operations.py
"""
Video database operations module - Composition-based architecture.

This module handles all video-related database operations using dependency injection
instead of mixin inheritance, providing type-safe Pydantic model interfaces.
"""
# TODO: Not using timeezone aware timestamps yet.
from typing import List, Optional, Dict, Any
from datetime import datetime
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
            c.name as camera_name
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
