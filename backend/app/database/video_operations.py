# backend/app/database/video_operations.py
"""
Video database operations module - Simplified composition-based architecture.

This module handles all video-related database operations using dependency injection
instead of mixin inheritance, providing type-safe Pydantic model interfaces.

Note: Complex automation features have been removed - automation is now handled by video pipeline.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from pydantic import ValidationError

from .core import AsyncDatabase, SyncDatabase
from ..models.video_model import Video, VideoWithDetails
from ..models.shared_models import (
    VideoGenerationJob,
    VideoGenerationJobWithDetails,
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
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[VideoWithDetails]:
        """
        Retrieve videos with optional filtering.

        Args:
            timelapse_id: Optional timelapse ID to filter by
            camera_id: Optional camera ID to filter by
            status: Optional status to filter by
            limit: Maximum number of videos to return
            offset: Number of videos to skip for pagination

        Returns:
            List of VideoWithDetails model instances

        Usage:
            videos = await video_ops.get_videos()
            timelapse_videos = await video_ops.get_videos(timelapse_id=1)
            camera_videos = await video_ops.get_videos(camera_id=1, limit=50)
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Build dynamic query based on filters
                    conditions = []
                    params = []

                    if timelapse_id is not None:
                        conditions.append("v.timelapse_id = %s")
                        params.append(timelapse_id)

                    if camera_id is not None:
                        conditions.append("v.camera_id = %s")
                        params.append(camera_id)

                    if status is not None:
                        conditions.append("v.status = %s")
                        params.append(status)

                    where_clause = (
                        "WHERE " + " AND ".join(conditions) if conditions else ""
                    )

                    query = f"""
                        SELECT
                            v.*,
                            t.name as timelapse_name,
                            c.name as camera_name
                        FROM videos v
                        LEFT JOIN timelapses t ON v.timelapse_id = t.id
                        LEFT JOIN cameras c ON v.camera_id = c.id
                        {where_clause}
                        ORDER BY v.created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    params.extend([limit, offset])

                    await cur.execute(query, params)
                    results = await cur.fetchall()
                    return [
                        self._row_to_video_with_details(dict(row)) for row in results
                    ]
        except Exception as e:
            logger.error(f"Error getting videos: {e}")
            return []

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
                    return job
                raise Exception(f"Failed to update video generation job {job_id}")

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
            timelapse_id: Optional timelapse ID to filter by
            camera_id: Optional camera ID to filter by
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            VideoStatistics model instance
        """
        try:
            # Build dynamic query based on filters
            conditions = []
            params = []

            if timelapse_id is not None:
                conditions.append("timelapse_id = %s")
                params.append(timelapse_id)

            if camera_id is not None:
                conditions.append("camera_id = %s")
                params.append(camera_id)

            if start_date is not None:
                conditions.append("created_at >= %s")
                params.append(start_date)

            if end_date is not None:
                conditions.append("created_at <= %s")
                params.append(end_date)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            query = f"""
                SELECT 
                    COUNT(*) as total_videos,
                    SUM(file_size) as total_size_bytes,
                    AVG(duration_seconds) as avg_duration_seconds,
                    AVG(calculated_fps) as avg_fps,
                    MAX(created_at) as latest_video_at
                FROM videos
                {where_clause}
            """

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
        except Exception as e:
            logger.error(f"Error getting video statistics: {e}")
            return VideoStatistics()  # Return empty stats

    async def search_videos(self, search_term: str, limit: int = 50) -> List[Video]:
        """
        Search videos by name.

        Args:
            search_term: Term to search for in video names
            limit: Maximum number of results to return

        Returns:
            List of videos matching the search term
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    query = """
                        SELECT v.*, c.name as camera_name
                        FROM videos v
                        LEFT JOIN cameras c ON v.camera_id = c.id
                        WHERE v.name ILIKE %s
                        ORDER BY v.created_at DESC
                        LIMIT %s
                    """
                    await cur.execute(query, (f"%{search_term}%", limit))
                    rows = await cur.fetchall()
                    return [self._row_to_video(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            return []


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
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Build dynamic query based on filters
                    conditions = []
                    params = []

                    if timelapse_id is not None:
                        conditions.append("v.timelapse_id = %s")
                        params.append(timelapse_id)

                    if camera_id is not None:
                        conditions.append("v.camera_id = %s")
                        params.append(camera_id)

                    if status is not None:
                        conditions.append("v.status = %s")
                        params.append(status)

                    where_clause = (
                        "WHERE " + " AND ".join(conditions) if conditions else ""
                    )

                    query = f"""
                        SELECT v.*
                        FROM videos v
                        {where_clause}
                        ORDER BY v.created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    params.extend([limit, offset])

                    cur.execute(query, params)
                    rows = cur.fetchall()
                    return [self._row_to_video(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting videos (sync): {e}")
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
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT v.*
                        FROM videos v
                        WHERE v.id = %s
                    """
                    cur.execute(query, (video_id,))
                    row = cur.fetchone()
                    return self._row_to_video(dict(row)) if row else None
        except Exception as e:
            logger.error(f"Error getting video by ID (sync): {e}")
            return None

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
                    return video
                raise Exception("Failed to create video record")

    def delete_video(self, video_id: int) -> bool:
        """
        Delete a video record (sync version).

        Args:
            video_id: Video ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = "DELETE FROM videos WHERE id = %s"
                    cur.execute(query, (video_id,))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting video (sync): {e}")
            return False

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

    def create_video_generation_job(
        self, job_data: Dict[str, Any], event_timestamp: Optional[str] = None
    ) -> Optional[int]:
        """
        Create a new video generation job (sync version).

        Args:
            job_data: Dictionary containing job configuration
            event_timestamp: ISO formatted timestamp for SSE events (provided by service layer)

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

                        return job_id
                    return None
        except Exception as e:
            logger.error(f"Failed to create video generation job: {e}")
            return None

    def start_video_generation_job(
        self, job_id: int, event_timestamp: Optional[str] = None
    ) -> bool:
        """
        Mark a video generation job as started.

        Args:
            job_id: ID of the job to start
            event_timestamp: ISO formatted timestamp for SSE events (provided by service layer)

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

                    return success
        except Exception as e:
            logger.error(f"Failed to start video generation job {job_id}: {e}")
            return False

    def complete_video_generation_job(
        self,
        job_id: int,
        success: bool,
        error_message: Optional[str] = None,
        video_path: Optional[str] = None,
        event_timestamp: Optional[str] = None,
    ) -> bool:
        """
        Mark a video generation job as completed.

        Args:
            job_id: ID of the job to complete
            success: Whether the job completed successfully
            error_message: Error message if job failed
            video_path: Path to generated video if successful
            event_timestamp: ISO formatted timestamp for SSE events (provided by service layer)

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

                    return update_success
        except Exception as e:
            logger.error(f"Failed to complete video generation job {job_id}: {e}")
            return False

    def get_video_generation_jobs_by_status(
        self, status: Optional[str] = None, limit: int = 50
    ) -> List[VideoGenerationJobWithDetails]:
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

    # Removed over-engineered automation settings - automation is now handled by video pipeline

    # Removed unused per-capture throttling - throttling is now handled by video pipeline

    # Removed unused milestone automation - milestone logic is now handled by video pipeline

    # Removed unused milestone checking - milestone logic is now handled by video pipeline

    # Removed unused scheduled automation - scheduling is now handled by video pipeline

    # Removed unused scheduled generation checking - scheduling is now handled by video pipeline

    def get_active_job_count(self) -> int:
        """Get count of currently processing jobs."""
        try:
            query = "SELECT COUNT(*) as count FROM video_generation_jobs WHERE status = 'processing'"
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    return dict(result)["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get active job count: {e}")
            return 0

    def get_timelapse_video_settings(
        self, timelapse_id: int, job_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get effective video generation settings for a timelapse.
        Simplified version - complex inheritance now handled by video pipeline.

        Args:
            timelapse_id: ID of the timelapse
            job_settings: Optional job-specific settings (highest priority)

        Returns:
            Dictionary with effective video generation settings
        """
        try:
            # Simplified query - basic settings only
            query = """
                SELECT
                    t.standard_fps as fps,
                    COALESCE(t.video_generation_mode, 'standard') as video_generation_mode
                FROM timelapses t
                WHERE t.id = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    row = cur.fetchone()

                    if not row:
                        logger.warning(
                            f"Timelapse {timelapse_id} not found, using defaults"
                        )
                        return self._get_default_video_settings()

                    row_dict = dict(row)
                    job_settings = job_settings or {}

                    # Simple settings with job override
                    settings = {
                        "fps": job_settings.get("fps") or row_dict["fps"] or 24.0,
                        "video_generation_mode": job_settings.get(
                            "video_generation_mode"
                        )
                        or row_dict["video_generation_mode"],
                        "quality": job_settings.get("quality", "medium"),
                    }

                    return settings

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
            "quality": "medium",
        }

    # Removed unused automation mode statistics - automation is now handled by video pipeline

    def cancel_pending_jobs_by_timelapse(self, timelapse_id: int) -> int:
        """Cancel pending video jobs for a specific timelapse."""
        try:
            query = """
                UPDATE video_generation_jobs
                SET status = 'cancelled', completed_at = NOW()
                WHERE timelapse_id = %s AND status = 'pending'
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    return cur.rowcount or 0
        except Exception as e:
            logger.error(
                f"Error cancelling video jobs for timelapse {timelapse_id}: {e}"
            )
            return 0

    def cancel_pending_jobs_by_camera(self, camera_id: int) -> int:
        """Cancel pending video jobs for a specific camera."""
        try:
            query = """
                UPDATE video_generation_jobs j
                SET status = 'cancelled', completed_at = NOW()
                FROM timelapses t
                WHERE j.timelapse_id = t.id AND t.camera_id = %s AND j.status = 'pending'
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (camera_id,))
                    return cur.rowcount or 0
        except Exception as e:
            logger.error(f"Error cancelling video jobs for camera {camera_id}: {e}")
            return 0

    def cancel_pending_jobs(self) -> int:
        """Cancel all pending video jobs."""
        try:
            query = "UPDATE video_generation_jobs SET status = 'cancelled', completed_at = NOW() WHERE status = 'pending'"
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return cur.rowcount or 0
        except Exception as e:
            logger.error(f"Error cancelling all pending video jobs: {e}")
            return 0

    def get_video_job_statistics(self) -> Dict[str, Any]:
        """Get basic statistics for the video job queue."""
        try:
            query = """
                SELECT status, COUNT(*) as count
                FROM video_generation_jobs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY status
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()

            stats = {
                "pending_count": 0,
                "processing_count": 0,
                "completed_today": 0,
                "failed_today": 0,
            }
            for row in results:
                status = row["status"]
                count = row["count"]
                if status == "pending":
                    stats["pending_count"] = count
                elif status == "processing":
                    stats["processing_count"] = count
                elif status == "completed":
                    stats["completed_today"] = count
                elif status == "failed":
                    stats["failed_today"] = count

            return stats
        except Exception as e:
            logger.error(f"Error getting video job statistics: {e}")
            return {}

    # Removed unused priority promotion - job prioritization is now handled by video pipeline

    def get_video_job_queue_status(self) -> Dict[str, int]:
        """
        Get video job queue status counts by status.

        Returns:
            Dictionary with job counts by status
        """
        try:
            query = """
            SELECT status, COUNT(*) as count
            FROM video_generation_jobs
            GROUP BY status
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()
                    return {row["status"]: row["count"] for row in results}
        except Exception as e:
            logger.error(f"Error getting video job queue status: {e}")
            return {}

    def get_video_generation_job_by_id(
        self, job_id: int
    ) -> Optional[VideoGenerationJobWithDetails]:
        """
        Get a video generation job by ID.

        Args:
            job_id: ID of the job to retrieve

        Returns:
            VideoGenerationJobWithDetails if found, None otherwise
        """
        try:
            query = """
            SELECT
                vgj.*,
                t.name as timelapse_name,
                c.name as camera_name,
                c.id as camera_id
            FROM video_generation_jobs vgj
            JOIN timelapses t ON vgj.timelapse_id = t.id
            JOIN cameras c ON t.camera_id = c.id
            WHERE vgj.id = %s
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (job_id,))
                    row = cur.fetchone()
                    if row:
                        return self._row_to_video_generation_job_with_details(row)
                    return None
        except Exception as e:
            logger.error(f"Error getting video generation job by ID {job_id}: {e}")
            return None

    def update_video_generation_job_status(self, job_id: int, status: str) -> bool:
        """
        Update the status of a video generation job.

        Args:
            job_id: ID of the job to update
            status: New status for the job

        Returns:
            True if update was successful, False otherwise
        """
        try:
            query = """
            UPDATE video_generation_jobs
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (status, job_id))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating video generation job status: {e}")
            return False

    def get_last_scheduled_video(self, timelapse_id: int) -> Optional[Video]:
        """
        Get the most recent video for a timelapse that was triggered by scheduled automation.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Most recent scheduled video or None if not found
        """
        try:
            query = """
            SELECT * FROM videos 
            WHERE timelapse_id = %s 
            AND trigger_type = 'scheduled'
            ORDER BY created_at DESC 
            LIMIT 1
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    row = cur.fetchone()
                    if row:
                        return self._row_to_video(dict(row))
                    return None
        except Exception as e:
            logger.error(
                f"Error getting last scheduled video for timelapse {timelapse_id}: {e}"
            )
            return None

    def get_last_milestone_video(self, timelapse_id: int) -> Optional[Video]:
        """
        Get the most recent video for a timelapse that was triggered by milestone automation.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Most recent milestone video or None if not found
        """
        try:
            query = """
            SELECT * FROM videos 
            WHERE timelapse_id = %s 
            AND trigger_type = 'milestone'
            ORDER BY created_at DESC 
            LIMIT 1
            """
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    row = cur.fetchone()
                    if row:
                        return self._row_to_video(dict(row))
                    return None
        except Exception as e:
            logger.error(
                f"Error getting last milestone video for timelapse {timelapse_id}: {e}"
            )
            return None
