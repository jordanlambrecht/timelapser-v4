"""
Timelapse database operations module - Composition Pattern.

This module handles all timelapse-related database operations including:
- Timelapse lifecycle management (create, update, complete)
- Entity-based timelapse operations
- Active timelapse management
- Video settings inheritance
"""

from typing import List, Optional, Dict, Any
from pydantic import ValidationError
from loguru import logger

from .core import AsyncDatabase, SyncDatabase
from ..models.timelapse_model import (
    Timelapse,
    TimelapseWithDetails,
    TimelapseCreate,
    TimelapseUpdate,
)
from ..models.shared_models import (
    TimelapseStatistics,
    TimelapseForCleanup,
    TimelapseVideoSettings,
)


class TimelapseOperations:
    async def get_timelapse_settings(
        self, timelapse_id: int
    ) -> Optional[TimelapseVideoSettings]:
        """
        Get timelapse settings for video generation (async).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            TimelapseVideoSettings model instance or None if timelapse not found
        """
        query = """
        SELECT
            video_generation_mode,
            standard_fps,
            enable_time_limits,
            min_time_seconds,
            max_time_seconds,
            target_time_seconds,
            fps_bounds_min,
            fps_bounds_max
        FROM timelapses
        WHERE id = %s
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                result = await cur.fetchone()
                if result:
                    try:
                        return TimelapseVideoSettings.model_validate(dict(result))
                    except ValidationError as e:
                        logger.error(
                            f"Error creating TimelapseVideoSettings model: {e}"
                        )
                        return None
                return None

    """Async timelapse database operations for FastAPI endpoints."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db

    def _row_to_timelapse(self, row: Dict[str, Any]) -> Timelapse:
        """Convert database row to Timelapse model."""
        # Filter fields that belong to Timelapse model
        timelapse_fields = {k: v for k, v in row.items() if k in Timelapse.model_fields}
        return Timelapse(**timelapse_fields)

    def _row_to_timelapse_with_details(
        self, row: Dict[str, Any]
    ) -> TimelapseWithDetails:
        """Convert database row to TimelapseWithDetails model."""
        # Extract base timelapse fields
        timelapse_fields = {k: v for k, v in row.items() if k in Timelapse.model_fields}

        # Add additional fields for TimelapseWithDetails
        details_fields = timelapse_fields.copy()
        if "camera_name" in row:
            details_fields["camera_name"] = row["camera_name"]

        return TimelapseWithDetails(**details_fields)

    async def get_timelapses(
        self, camera_id: Optional[int] = None
    ) -> List[TimelapseWithDetails]:
        """
        Retrieve timelapses with optional camera filtering.

        Args:
            camera_id: Optional camera ID to filter by

        Returns:
            List of TimelapseWithDetails model instances
        """
        base_query = """
        SELECT 
            t.*,
            c.name as camera_name,
            COUNT(i.id) as image_count,
            COUNT(v.id) as video_count,
            MIN(i.captured_at) as first_capture_at,
            MAX(i.captured_at) as last_capture_at,
            AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
            COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as flagged_images,
            COALESCE(t.glitch_count, 0) as glitch_count
        FROM timelapses t
        JOIN cameras c ON t.camera_id = c.id
        LEFT JOIN images i ON t.id = i.timelapse_id
        LEFT JOIN videos v ON t.id = v.timelapse_id
        """

        if camera_id:
            query = (
                base_query
                + " WHERE t.camera_id = %s GROUP BY t.id, c.name ORDER BY t.created_at DESC"
            )
            params = (camera_id,)
        else:
            query = base_query + " GROUP BY t.id, c.name ORDER BY t.created_at DESC"
            params = ()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_timelapse_with_details(row) for row in results]

    async def get_timelapse_by_id(
        self, timelapse_id: int
    ) -> Optional[TimelapseWithDetails]:
        """
        Retrieve a specific timelapse by ID with metadata.

        Args:
            timelapse_id: ID of the timelapse to retrieve

        Returns:
            TimelapseWithDetails model instance, or None if not found
        """
        query = """
        SELECT 
            t.*,
            c.name as camera_name,
            COUNT(i.id) as image_count,
            COUNT(v.id) as video_count,
            MIN(i.captured_at) as first_capture_at,
            MAX(i.captured_at) as last_capture_at,
            AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
            COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as flagged_images,
            COALESCE(t.glitch_count, 0) as glitch_count
        FROM timelapses t
        JOIN cameras c ON t.camera_id = c.id
        LEFT JOIN images i ON t.id = i.timelapse_id
        LEFT JOIN videos v ON t.id = v.timelapse_id
        WHERE t.id = %s
        GROUP BY t.id, c.name
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                results = await cur.fetchall()
                if results:
                    row = results[0]
                    return self._row_to_timelapse_with_details(dict(row))
                return None

    async def create_new_timelapse(
        self, camera_id: int, timelapse_data: TimelapseCreate
    ) -> Timelapse:
        """
        Create a new timelapse for a camera using entity-based architecture.

        Args:
            camera_id: ID of the camera
            timelapse_data: TimelapseCreate model instance

        Returns:
            Created Timelapse model instance
        """
        # Convert Pydantic model to dict for database insertion, including defaults
        insert_data = timelapse_data.model_dump(exclude_unset=False)
        insert_data["camera_id"] = camera_id

        # Create the timelapse record
        query = """
        INSERT INTO timelapses (
            camera_id, name, status, auto_stop_at,
            time_window_type, time_window_start, time_window_end, 
            sunrise_offset_minutes, sunset_offset_minutes, use_custom_time_window,
            video_generation_mode, standard_fps, enable_time_limits,
            min_time_seconds, max_time_seconds, target_time_seconds,
            fps_bounds_min, fps_bounds_max, video_automation_mode,
            generation_schedule, milestone_config
        ) VALUES (
            %(camera_id)s, %(name)s, %(status)s, %(auto_stop_at)s,
            %(time_window_type)s, %(time_window_start)s, %(time_window_end)s,
            %(sunrise_offset_minutes)s, %(sunset_offset_minutes)s, %(use_custom_time_window)s,
            %(video_generation_mode)s, %(standard_fps)s, %(enable_time_limits)s,
            %(min_time_seconds)s, %(max_time_seconds)s, %(target_time_seconds)s,
            %(fps_bounds_min)s, %(fps_bounds_max)s, %(video_automation_mode)s,
            %(generation_schedule)s, %(milestone_config)s
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, insert_data)
                results = await cur.fetchall()

                if results:
                    row = results[0]
                    new_timelapse = self._row_to_timelapse(row)

                    # Update camera's active_timelapse_id if status is running
                    if row.get("status") in ("running", "paused"):
                        await cur.execute(
                            "UPDATE cameras SET active_timelapse_id = %s WHERE id = %s",
                            (row["id"], camera_id),
                        )

                    return new_timelapse

                raise Exception("Failed to create timelapse")

    async def update_timelapse(
        self, timelapse_id: int, timelapse_data: TimelapseUpdate
    ) -> Timelapse:
        """
        Update an existing timelapse.

        Args:
            timelapse_id: ID of the timelapse to update
            timelapse_data: TimelapseUpdate model instance

        Returns:
            Updated Timelapse model instance
        """
        # Convert Pydantic model to dict, excluding unset fields
        update_data = timelapse_data.model_dump(exclude_unset=True)

        if not update_data:
            # Return current timelapse if no updates
            current = await self.get_timelapse_by_id(timelapse_id)
            if current is None:
                raise ValueError(f"Timelapse {timelapse_id} not found")
            # Convert TimelapseWithDetails to Timelapse for return type consistency
            return Timelapse(
                **{
                    k: v
                    for k, v in current.model_dump().items()
                    if k in Timelapse.model_fields
                }
            )

        # Build dynamic update query
        update_fields = []
        params = {"timelapse_id": timelapse_id}

        for field, value in update_data.items():
            update_fields.append(f"{field} = %({field})s")
            params[field] = value

        update_fields.append("updated_at = NOW()")

        query = f"""
        UPDATE timelapses 
        SET {', '.join(update_fields)}
        WHERE id = %(timelapse_id)s 
        RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()

                if results:
                    row = results[0]
                    updated_timelapse = self._row_to_timelapse(row)

                    # Update camera's active_timelapse_id if status changed
                    if "status" in update_data:
                        if row["status"] in ("running", "paused"):
                            await cur.execute(
                                "UPDATE cameras SET active_timelapse_id = %s WHERE id = %s",
                                (timelapse_id, row["camera_id"]),
                            )
                        elif row["status"] == "completed":
                            await cur.execute(
                                "UPDATE cameras SET active_timelapse_id = NULL WHERE id = %s",
                                (row["camera_id"],),
                            )

                    return updated_timelapse

                raise Exception(f"Failed to update timelapse {timelapse_id}")

    async def delete_timelapse(self, timelapse_id: int) -> bool:
        """
        Delete a timelapse and all associated data.

        Args:
            timelapse_id: ID of the timelapse to delete

        Returns:
            True if timelapse was deleted successfully
        """
        query = "DELETE FROM timelapses WHERE id = %s"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    async def get_timelapse_statistics(
        self, timelapse_id: int
    ) -> Optional[TimelapseStatistics]:
        """
        Get comprehensive statistics for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            TimelapseStatistics model instance or None if timelapse not found
        """
        query = """
        SELECT 
            COUNT(i.id) as total_images,
            COUNT(v.id) as total_videos,
            MIN(i.captured_at) as first_capture_at,
            MAX(i.captured_at) as last_capture_at,
            AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
            COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as flagged_images,
            SUM(i.file_size) as total_storage_bytes,
            SUM(v.file_size) as total_video_storage_bytes
        FROM timelapses t
        LEFT JOIN images i ON t.id = i.timelapse_id
        LEFT JOIN videos v ON t.id = v.timelapse_id
        WHERE t.id = %s
        GROUP BY t.id
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                results = await cur.fetchall()
                if results:
                    try:
                        return TimelapseStatistics.model_validate(dict(results[0]))
                    except ValidationError as e:
                        logger.error(f"Error creating TimelapseStatistics model: {e}")
                        return None
                return None

    async def get_active_timelapse_for_camera(
        self, camera_id: int
    ) -> Optional[Timelapse]:
        """
        Get the currently active timelapse for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Active Timelapse model instance, or None if no active timelapse
        """
        query = """
        SELECT t.*
        FROM timelapses t
        JOIN cameras c ON c.active_timelapse_id = t.id
        WHERE c.id = %s AND t.status IN ('running', 'paused')
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                results = await cur.fetchall()
                return self._row_to_timelapse(results[0]) if results else None

    async def complete_timelapse(self, timelapse_id: int) -> Timelapse:
        """
        Mark a timelapse as completed and clean up camera references.

        Args:
            timelapse_id: ID of the timelapse to complete

        Returns:
            Completed Timelapse model instance
        """
        query = """
        UPDATE timelapses 
        SET status = 'completed', 
            updated_at = NOW()
        WHERE id = %s 
        RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                results = await cur.fetchall()

                if results:
                    row = results[0]
                    completed_timelapse = self._row_to_timelapse(row)

                    # Clear camera's active_timelapse_id
                    await cur.execute(
                        "UPDATE cameras SET active_timelapse_id = NULL WHERE active_timelapse_id = %s",
                        (timelapse_id,),
                    )

                    # Note: SSE events should be handled by the service layer, not database layer
                    # This will be removed once all SSE events are properly centralized
                    return completed_timelapse

                raise ValueError(
                    f"Timelapse {timelapse_id} not found or already completed"
                )

    async def cleanup_completed_timelapses(self, retention_days: int = 90) -> int:
        """
        Clean up old completed timelapses.

        Args:
            retention_days: Number of days to keep completed timelapses

        Returns:
            Number of timelapses deleted
        """
        query = """
        DELETE FROM timelapses 
        WHERE status = 'completed' 
        AND updated_at < NOW() - INTERVAL '%s days'
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (retention_days,))
                affected = cur.rowcount

                if affected and affected > 0:
                    logger.info(f"Cleaned up {affected} completed timelapses")

                return affected or 0

    # ====================================================================
    # THUMBNAIL COUNT TRACKING METHODS (ASYNC VERSION)
    # ====================================================================

    async def increment_thumbnail_counts(
        self,
        timelapse_id: int,
        increment_thumbnail: bool = True,
        increment_small: bool = True,
    ) -> bool:
        """
        Increment thumbnail counts for a timelapse (async version).

        Args:
            timelapse_id: ID of the timelapse
            increment_thumbnail: Whether to increment thumbnail_count
            increment_small: Whether to increment small_count

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build the SET clause dynamically
            set_clauses = []
            if increment_thumbnail:
                set_clauses.append("thumbnail_count = thumbnail_count + 1")
            if increment_small:
                set_clauses.append("small_count = small_count + 1")

            if not set_clauses:
                return True  # Nothing to update

            query = f"""
                UPDATE timelapses 
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (timelapse_id,))
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(
                f"Error incrementing thumbnail counts for timelapse {timelapse_id}: {e}"
            )
            return False

    async def recalculate_thumbnail_counts(self, timelapse_id: int) -> bool:
        """
        Recalculate thumbnail counts for a timelapse by counting actual files.

        This method should be used for verification and repair operations.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE timelapses 
                SET 
                    thumbnail_count = COALESCE(thumb_stats.thumbnail_count, 0),
                    small_count = COALESCE(thumb_stats.small_count, 0)
                FROM (
                    SELECT 
                        COUNT(CASE WHEN thumbnail_path IS NOT NULL AND thumbnail_path != '' THEN 1 END) as thumbnail_count,
                        COUNT(CASE WHEN small_path IS NOT NULL AND small_path != '' THEN 1 END) as small_count
                    FROM images 
                    WHERE timelapse_id = %s
                ) as thumb_stats
                WHERE timelapses.id = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (timelapse_id, timelapse_id))
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(
                f"Error recalculating thumbnail counts for timelapse {timelapse_id}: {e}"
            )
            return False


class SyncTimelapseOperations:
    """Sync timelapse database operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def _row_to_timelapse(self, row: Dict[str, Any]) -> Timelapse:
        """Convert database row to Timelapse model."""
        # Filter fields that belong to Timelapse model
        timelapse_fields = {k: v for k, v in row.items() if k in Timelapse.model_fields}
        return Timelapse(**timelapse_fields)

    def get_active_timelapse_for_camera(self, camera_id: int) -> Optional[Timelapse]:
        """
        Get the currently active timelapse for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Active Timelapse model instance, or None if no active timelapse
        """
        query = """
        SELECT t.*
        FROM timelapses t
        JOIN cameras c ON c.active_timelapse_id = t.id
        WHERE c.id = %s AND t.status IN ('running', 'paused')
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id,))
                results = cur.fetchall()
                return self._row_to_timelapse(results[0]) if results else None

    def get_timelapse_by_id(self, timelapse_id: int) -> Optional[Timelapse]:
        """
        Retrieve a specific timelapse by ID.

        Args:
            timelapse_id: ID of the timelapse to retrieve

        Returns:
            Timelapse model instance or None if not found
        """
        query = "SELECT * FROM timelapses WHERE id = %s"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                results = cur.fetchall()
                return self._row_to_timelapse(results[0]) if results else None

    def update_timelapse_status(self, timelapse_id: int, status: str) -> bool:
        """
        Update timelapse status.

        Args:
            timelapse_id: ID of the timelapse
            status: New status ('running', 'paused', 'completed')

        Returns:
            True if update was successful
        """
        query = """
        UPDATE timelapses 
        SET status = %s, updated_at = NOW()
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, timelapse_id))
                affected = cur.rowcount
                return affected and affected > 0

    def increment_glitch_count(self, timelapse_id: int) -> bool:
        """
        Increment the glitch count for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            True if increment was successful
        """
        query = """
        UPDATE timelapses 
        SET glitch_count = glitch_count + 1,
            updated_at = NOW()
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                affected = cur.rowcount
                return affected and affected > 0

    def update_timelapse_last_activity(self, timelapse_id: int) -> bool:
        """
        Update the last activity timestamp for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            True if update was successful
        """
        query = """
        UPDATE timelapses 
        SET last_activity_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                affected = cur.rowcount
                return affected and affected > 0

    def get_timelapses_for_cleanup(
        self, retention_days: int = 90
    ) -> List[TimelapseForCleanup]:
        """
        Get completed timelapses older than retention period.

        Args:
            retention_days: Number of days to keep completed timelapses

        Returns:
            List of TimelapseForCleanup model instances eligible for cleanup
        """
        query = """
        SELECT t.*, c.name as camera_name
        FROM timelapses t
        JOIN cameras c ON t.camera_id = c.id
        WHERE t.status = 'completed'
        AND t.updated_at < NOW() - INTERVAL '%s days'
        ORDER BY t.updated_at ASC
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (retention_days,))
                results = cur.fetchall()

                timelapses = []
                for row in results:
                    try:
                        timelapse = TimelapseForCleanup.model_validate(dict(row))
                        timelapses.append(timelapse)
                    except ValidationError as e:
                        logger.error(f"Error creating TimelapseForCleanup model: {e}")
                        continue

                return timelapses

    def cleanup_completed_timelapses(self, retention_days: int = 90) -> int:
        """
        Clean up old completed timelapses.

        Args:
            retention_days: Number of days to keep completed timelapses

        Returns:
            Number of timelapses deleted
        """
        query = """
        DELETE FROM timelapses
        WHERE status = 'completed'
        AND updated_at < NOW() - INTERVAL '%s days'
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (retention_days,))
                affected = cur.rowcount

                if affected and affected > 0:
                    logger.info(f"Cleaned up {affected} completed timelapses")

                return affected or 0

    def get_timelapse_image_count(self, timelapse_id: int) -> int:
        """
        Get the current image count for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Number of images in the timelapse
        """
        query = "SELECT COUNT(*) as count FROM images WHERE timelapse_id = %s"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                result = cur.fetchone()
                return result["count"] if result else 0

    def get_timelapse_settings(
        self, timelapse_id: int
    ) -> Optional[TimelapseVideoSettings]:
        """
        Get timelapse settings for video generation.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            TimelapseVideoSettings model instance or None if timelapse not found
        """
        query = """
        SELECT
            video_generation_mode,
            standard_fps,
            enable_time_limits,
            min_time_seconds,
            max_time_seconds,
            target_time_seconds,
            fps_bounds_min,
            fps_bounds_max
        FROM timelapses
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                result = cur.fetchone()
                if result:
                    try:
                        return TimelapseVideoSettings.model_validate(dict(result))
                    except ValidationError as e:
                        logger.error(
                            f"Error creating TimelapseVideoSettings model: {e}"
                        )
                        return None
                return None

    def create_timelapse(self, timelapse_data: TimelapseCreate) -> Timelapse:
        """
        Create a new timelapse (sync version for worker).

        Args:
            timelapse_data: TimelapseCreate model instance

        Returns:
            Created Timelapse model instance
        """
        # Convert Pydantic model to dict for database insertion
        insert_data = timelapse_data.model_dump(exclude_unset=True)

        query = """
        INSERT INTO timelapses (
            camera_id, name, status, auto_stop_at,
            time_window_type, time_window_start, time_window_end, 
            sunrise_offset_minutes, sunset_offset_minutes, use_custom_time_window,
            video_generation_mode, standard_fps, enable_time_limits,
            min_time_seconds, max_time_seconds, target_time_seconds,
            fps_bounds_min, fps_bounds_max, video_automation_mode,
            generation_schedule, milestone_config
        ) VALUES (
            %(camera_id)s, %(name)s, %(status)s, %(auto_stop_at)s,
            %(time_window_type)s, %(time_window_start)s, %(time_window_end)s,
            %(sunrise_offset_minutes)s, %(sunset_offset_minutes)s, %(use_custom_time_window)s,
            %(video_generation_mode)s, %(standard_fps)s, %(enable_time_limits)s,
            %(min_time_seconds)s, %(max_time_seconds)s, %(target_time_seconds)s,
            %(fps_bounds_min)s, %(fps_bounds_max)s, %(video_automation_mode)s,
            %(generation_schedule)s, %(milestone_config)s
        ) RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, insert_data)
                results = cur.fetchall()

                if results:
                    row = results[0]
                    new_timelapse = self._row_to_timelapse(row)

                    # Update camera's active_timelapse_id if status is running
                    if row.get("status") in ("running", "paused"):
                        cur.execute(
                            "UPDATE cameras SET active_timelapse_id = %s WHERE id = %s",
                            (row["id"], insert_data["camera_id"]),
                        )

                    return new_timelapse

                raise Exception("Failed to create timelapse")

    # ====================================================================
    # THUMBNAIL COUNT TRACKING METHODS (SYNC VERSION)
    # ====================================================================

    def increment_thumbnail_counts_sync(
        self,
        timelapse_id: int,
        increment_thumbnail: bool = True,
        increment_small: bool = True,
    ) -> bool:
        """
        Increment thumbnail counts for a timelapse (sync version for worker).

        Args:
            timelapse_id: ID of the timelapse
            increment_thumbnail: Whether to increment thumbnail_count
            increment_small: Whether to increment small_count

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build the SET clause dynamically
            set_clauses = []
            if increment_thumbnail:
                set_clauses.append("thumbnail_count = thumbnail_count + 1")
            if increment_small:
                set_clauses.append("small_count = small_count + 1")

            if not set_clauses:
                return True  # Nothing to update

            query = f"""
                UPDATE timelapses 
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (timelapse_id,))
                    return cur.rowcount > 0

        except Exception as e:
            logger.error(
                f"Error incrementing thumbnail counts for timelapse {timelapse_id}: {e}"
            )
            return False

    # ====================================================================
