# backend/app/database/camera_operations.py
"""
Camera database operations module.

This module handles all camera-related database operations including:
- Camera CRUD operations
- Camera health monitoring
- Camera statistics and status updates
- Camera corruption settings

All operations return proper Pydantic models directly, eliminating Dict[str, Any] conversions.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

from loguru import logger
from pydantic import ValidationError
import psycopg

from .core import AsyncDatabase, SyncDatabase
from ..utils.database_helpers import DatabaseQueryBuilder
# Removed unused constants imports
from ..models.camera_model import (
    Camera,
    ImageForCamera,
)
from ..models.corruption_model import CorruptionSettingsModel
from ..models.shared_models import CameraHealthStatus, CameraStatistics
from .settings_operations import SyncSettingsOperations
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
    get_timezone_from_cache_async,
    get_timezone_from_cache_sync,
)


def _prepare_camera_data_shared(
    camera_data: Dict[str, Any], tz: ZoneInfo
) -> Dict[str, Any]:
    """
    Shared helper function for preparing camera data from database rows.

    This eliminates duplicate logic between async and sync _prepare_camera_data methods.
    Handles timezone localization.

    Args:
        camera_data: Camera data dictionary from database row
        tz: ZoneInfo timezone object for localization

    Returns:
        Processed camera data dictionary
    """
    # Localize datetime fields using provided timezone
    for dt_field in [
        "created_at",
        "updated_at",
        "next_capture_at",
        "last_degraded_at",
    ]:
        if camera_data.get(dt_field) and isinstance(camera_data[dt_field], datetime):
            if camera_data[dt_field].tzinfo is None:
                camera_data[dt_field] = camera_data[dt_field].replace(tzinfo=tz)

    return camera_data


class AsyncCameraOperations:
    """Async camera database operations using composition pattern."""
    def __init__(self, db: AsyncDatabase, settings_service) -> None:
        self.db = db
        self.settings_service = settings_service

    async def get_active_cameras(self) -> List[Camera]:
        """
        Retrieve all enabled cameras for worker processing (async).

        Returns:
            List of enabled Camera model instances
        """
        query = """
        SELECT 
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
        WHERE c.enabled = true
        ORDER BY c.id
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                results = await cur.fetchall()
                cameras = []
                for row in results:
                    camera_data = await self._prepare_camera_data(row)
                    try:
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model for row {row}: {e}")
                        continue
                return cameras

    async def _prepare_camera_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare database row data for Pydantic model validation (async version).

        Uses shared helper function to eliminate code duplication.
        Gets timezone from database cache and delegates processing to shared helper.
        """
        camera_data = dict(row)

        # Get timezone from database cache (async)
        tz_str = await get_timezone_from_cache_async(self.settings_service)
        tz = ZoneInfo(tz_str)

        # Use shared helper for common processing logic
        return _prepare_camera_data_shared(camera_data, tz)

    async def _create_camera_from_row(self, row: Dict[str, Any]) -> Camera:
        """Create unified Camera model from database row with all fields populated."""
        camera_data = await self._prepare_camera_data(row)

        # Extract camera fields for base model
        camera_fields = {
            k: v for k, v in camera_data.items() if k in Camera.model_fields.keys()
        }

        # Add timelapse status fields for Camera compatibility
        camera_fields.update(
            {
                "timelapse_status": row.get("timelapse_status"),
                "timelapse_id": row.get("timelapse_id"),
            }
        )

        # Add statistics fields directly to camera model (no separate CameraStats object)
        camera_fields.update(
            {
                "image_count_lifetime": row.get(
                    "total_images", 0
                ),  # All images ever captured
                "image_count_active_timelapse": (
                    row.get("active_timelapse_images", 0)
                    if row.get("timelapse_status") in ["running", "paused"]
                    else 0
                ),
                "total_videos": 0,  # Will be populated by service layer if needed
                "current_timelapse_name": row.get("timelapse_name"),
                "timelapse_count": row.get(
                    "total_timelapses", 0
                ),  # Use actual count from query
                "first_capture_at": None,  # Would need separate query for this
                "avg_capture_interval_minutes": None,  # Would need calculation
                "days_since_first_capture": None,  # Would need calculation
                # Legacy fields for backward compatibility
                "total_images": row.get("total_images", 0),
                "current_timelapse_images": (
                    row.get("active_timelapse_images", 0)
                    if row.get("timelapse_status") in ["running", "paused"]
                    else 0
                ),
            }
        )

        try:
            camera = Camera.model_validate(camera_fields)

            # Add image data if available (since Camera now inherits all functionality)
            if row.get("last_image_id"):
                try:
                    camera.last_image = ImageForCamera.model_validate(
                        {
                            "id": int(row["last_image_id"]),
                            "captured_at": row["last_image_captured_at"],
                            "file_path": row["last_image_file_path"],
                            "file_size": row.get("last_image_file_size"),
                            "day_number": row["last_image_day_number"],
                            "thumbnail_path": row.get("last_image_thumbnail_path"),
                            "thumbnail_size": row.get("last_image_thumbnail_size"),
                            "small_path": row.get("last_image_small_path"),
                            "small_size": row.get("last_image_small_size"),
                        }
                    )
                except ValidationError as e:
                    logger.error(f"Error creating ImageForCamera model: {e}")
                    camera.last_image = None

            return camera
        except ValidationError as e:
            logger.error(f"Error creating Camera model: {e}")
            raise

    async def get_cameras(self) -> List[Camera]:
        """
        Retrieve all cameras with their current status and statistics.

        Returns:
            List of Camera model instances

        Usage:
            cameras = await db.get_cameras()
        """
        query = """
        SELECT 
            c.*,
            t.status as timelapse_status,
            t.id as timelapse_id,
            t.name as timelapse_name,
            COUNT(DISTINCT i_all.id) as total_images,  -- All images ever captured for this camera
            COUNT(DISTINCT i_active.id) as active_timelapse_images,  -- Images in active timelapse only
            COUNT(DISTINCT t_all.id) as total_timelapses,  -- All timelapses ever created for this camera
            MAX(i_all.captured_at) as last_capture_at,
            c.next_capture_at,
            -- Corruption detection fields
            c.lifetime_glitch_count,
            c.consecutive_corruption_failures,
            c.corruption_detection_heavy,
            c.last_degraded_at,
            c.degraded_mode_active
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
        LEFT JOIN timelapses t_all ON c.id = t_all.camera_id  -- All timelapses for count
        LEFT JOIN images i_all ON i_all.camera_id = c.id  -- All images for lifetime count
        LEFT JOIN images i_active ON i_active.timelapse_id = t.id  -- Only active timelapse images
        GROUP BY c.id, t.id, t.status, t.name
        ORDER BY c.created_at ASC
        """

        # asyncio already imported at top

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                results = await cur.fetchall()
                return await asyncio.gather(
                    *(self._create_camera_from_row(row) for row in results)
                )

    async def get_camera_by_id(self, camera_id: int) -> Optional[Camera]:
        """
        Retrieve a specific camera by ID with its current status.

        Args:
            camera_id: ID of the camera to retrieve

        Returns:
            Camera model instance, or None if not found

        Usage:
            camera = await db.get_camera_by_id(1)
        """
        query = """
        SELECT 
            c.*,
            t.status as timelapse_status,
            t.id as timelapse_id,
            t.name as timelapse_name,
            COUNT(DISTINCT i_all.id) as total_images,  -- All images ever captured for this camera
            COUNT(DISTINCT i_active.id) as active_timelapse_images,  -- Images in active timelapse only
            COUNT(DISTINCT t_all.id) as total_timelapses,  -- All timelapses ever created for this camera
            MAX(i_all.captured_at) as last_capture_at,
            c.next_capture_at,
            -- Corruption detection fields
            c.lifetime_glitch_count,
            c.consecutive_corruption_failures,
            c.corruption_detection_heavy,
            c.last_degraded_at,
            c.degraded_mode_active,
            -- Latest image fields
            latest_img.id as last_image_id,
            latest_img.captured_at as last_image_captured_at,
            latest_img.file_path as last_image_file_path,
            latest_img.file_size as last_image_file_size,
            latest_img.day_number as last_image_day_number,
            latest_img.thumbnail_path as last_image_thumbnail_path,
            latest_img.thumbnail_size as last_image_thumbnail_size,
            latest_img.small_path as last_image_small_path,
            latest_img.small_size as last_image_small_size
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
        LEFT JOIN timelapses t_all ON c.id = t_all.camera_id  -- All timelapses for count
        LEFT JOIN images i_all ON i_all.camera_id = c.id  -- All images for lifetime count
        LEFT JOIN images i_active ON i_active.timelapse_id = t.id  -- Only active timelapse images
        LEFT JOIN LATERAL (
            SELECT id, captured_at, file_path, file_size, day_number,
                   thumbnail_path, thumbnail_size, small_path, small_size
            FROM images 
            WHERE camera_id = c.id 
            ORDER BY captured_at DESC 
            LIMIT 1
        ) latest_img ON true
        WHERE c.id = %s
        GROUP BY c.id, t.id, t.status, t.name, 
                 latest_img.id, latest_img.captured_at, latest_img.file_path, 
                 latest_img.file_size, latest_img.day_number, latest_img.thumbnail_path,
                 latest_img.thumbnail_size, latest_img.small_path, latest_img.small_size
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                results = await cur.fetchall()
                if results:
                    return await self._create_camera_from_row(results[0])
                return None

    async def get_camera_comprehensive_status(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive camera status including health, connectivity, and corruption data.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing comprehensive status information, or None if camera not found
        """
        query = """
        SELECT 
            c.id,
            c.status,
            c.health_status,
            c.last_capture_at,
            c.last_capture_success,
            c.consecutive_failures,
            c.next_capture_at,
            c.active_timelapse_id,
            c.corruption_score,
            c.is_flagged,
            c.consecutive_corruption_failures,
            c.updated_at,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id
        WHERE c.id = %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                results = await cur.fetchall()
                if results:
                    row = results[0]
                    data = await self._prepare_camera_data(row)
                    # Add connectivity placeholders (would be filled by service layer)
                    data.update(
                        {
                            "connectivity_status": "unknown",
                            "last_connectivity_test": None,
                            "connectivity_message": None,
                            "response_time_ms": None,
                        }
                    )
                    return data
                return None

    async def create_camera(self, camera_data: Dict[str, Any]) -> Camera:
        """
        Create a new camera with the provided data.

        Args:
            camera_data: Dictionary containing camera configuration

        Returns:
            Created Camera model instance

        Usage:
            camera = await db.create_camera({
                'name': 'Front Door',
                'rtsp_url': 'rtsp://camera/stream',
                'enabled': True
            })
        """
        query = """
        INSERT INTO cameras (
            name, rtsp_url, enabled, rotation,
            capture_interval, quality_setting, resolution_width, resolution_height,
            overlay_text, watermark_enabled, watermark_text, watermark_position,
            watermark_font_size, watermark_opacity, fps, video_bitrate,
            corruption_detection_heavy
        ) VALUES (
            %(name)s, %(rtsp_url)s, %(enabled)s, %(rotation)s,
            %(capture_interval)s, %(quality_setting)s, %(resolution_width)s, %(resolution_height)s,
            %(overlay_text)s, %(watermark_enabled)s, %(watermark_text)s, %(watermark_position)s,
            %(watermark_font_size)s, %(watermark_opacity)s, %(fps)s, %(video_bitrate)s,
            %(corruption_detection_heavy)s
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, camera_data)
                results = await cur.fetchall()

                if results:
                    row = results[0]
                    camera_data = await self._prepare_camera_data(row)
                    try:
                        created_camera = Camera.model_validate(camera_data)
                        return created_camera
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model: {e}")
                        raise
                raise psycopg.DatabaseError("Failed to create camera")

    async def update_camera(
        self, camera_id: int, camera_data: Dict[str, Any]
    ) -> Camera:
        """
        Update an existing camera with the provided data.

        Args:
            camera_id: ID of the camera to update
            camera_data: Dictionary containing updated camera configuration

        Returns:
            Updated Camera model instance

        Usage:
            camera = await db.update_camera(1, {'enabled': False})
        """
        # Build dynamic update query based on provided fields
        update_fields = []
        params: Dict[str, Any] = {"camera_id": camera_id}

        # Dynamically determine updateable fields from Camera model, excluding immutable fields
        updateable_fields = [
            field
            for field in Camera.model_fields.keys()
            if field not in {"id", "created_at", "updated_at"}
        ]

        for field in updateable_fields:
            if field in camera_data:
                update_fields.append(f"{field} = %({field})s")
                params[field] = camera_data[field]

        if not update_fields:
            # If no fields to update, just return current camera
            current_camera = await self.get_camera_by_id(camera_id)
            if current_camera is None:
                raise ValueError(f"Camera {camera_id} not found")
            # Return the Camera model
            return Camera(
                **{
                    k: v
                    for k, v in current_camera.model_dump().items()
                    if k in Camera.model_fields.keys()
                }
            )

        # Add timezone-aware timestamp for updated_at
        now = await get_timezone_aware_timestamp_async(self.db)
        update_fields.append("updated_at = %(updated_at)s")
        params["updated_at"] = now

        query = f"""
        UPDATE cameras 
        SET {', '.join(update_fields)}
        WHERE id = %(camera_id)s 
        RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()

                if results:
                    row = results[0]
                    camera_data = await self._prepare_camera_data(row)
                    try:
                        updated_camera = Camera.model_validate(camera_data)
                        return updated_camera
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model: {e}")
                        raise
                raise psycopg.DatabaseError(f"Failed to update camera {camera_id}")

    async def delete_camera(self, camera_id: int) -> bool:
        """
        Delete a camera and all its associated data.

        Args:
            camera_id: ID of the camera to delete

        Returns:
            True if camera was deleted successfully

        Usage:
            success = await db.delete_camera(1)
        """
        query = "DELETE FROM cameras WHERE id = %s"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    async def get_camera_health_status(
        self, camera_id: int
    ) -> Optional[CameraHealthStatus]:
        """
        Get camera health status including corruption detection metrics.

        Args:
            camera_id: ID of the camera

        Returns:
            CameraHealthStatus model instance or None if camera not found

        Usage:
            health = await db.get_camera_health_status(1)
        """
        # Calculate 24 hours ago using timezone-aware timestamp
        # timedelta already imported at top

        now = await get_timezone_aware_timestamp_async(self.db)
        twenty_four_hours_ago = now - timedelta(hours=24)

        query = """
        SELECT 
            c.lifetime_glitch_count,
            c.consecutive_corruption_failures,
            c.degraded_mode_active,
            c.last_degraded_at,
            c.corruption_detection_heavy,
            COUNT(cl.id) as corruption_logs_count,
            AVG(cl.corruption_score) as avg_corruption_score
        FROM cameras c
        LEFT JOIN corruption_logs cl ON c.id = cl.camera_id 
            AND cl.created_at > %s
        WHERE c.id = %s
        GROUP BY c.id
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (twenty_four_hours_ago, camera_id))
                results = await cur.fetchall()
                if results:
                    try:
                        return CameraHealthStatus.model_validate(dict(results[0]))
                    except ValidationError as e:
                        logger.error(f"Error creating CameraHealthStatus model: {e}")
                        return None
                return None

    async def get_camera_stats(self, camera_id: int) -> Optional[CameraStatistics]:
        """
        Get comprehensive camera statistics.

        Args:
            camera_id: ID of the camera

        Returns:
            CameraStatistics model instance or None if camera not found

        Usage:
            stats = await db.get_camera_stats(1)
        """
        query = """
        SELECT 
            COUNT(DISTINCT t.id) as total_timelapses,
            COUNT(i.id) as total_images,
            COUNT(v.id) as total_videos,
            MAX(i.captured_at) as last_capture_at,
            MIN(i.captured_at) as first_capture_at,
            AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
            COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as flagged_images
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id
        LEFT JOIN images i ON t.id = i.timelapse_id
        LEFT JOIN videos v ON t.id = v.timelapse_id
        WHERE c.id = %s
        GROUP BY c.id
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                results = await cur.fetchall()
                if results:
                    try:
                        return CameraStatistics.model_validate(dict(results[0]))
                    except ValidationError as e:
                        logger.error(f"Error creating CameraStatistics model: {e}")
                        return None
                return None

    async def _update_camera_fields(
        self, camera_id: int, updates: Dict[str, Any], allowed_fields: set[str]
    ) -> bool:
        """
        Helper method to update specific camera fields using DatabaseQueryBuilder.

        Args:
            camera_id: ID of the camera to update
            updates: Dictionary containing field updates
            allowed_fields: Set of fields that are allowed to be updated

        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Use existing DatabaseQueryBuilder instead of custom implementation
            query, params = DatabaseQueryBuilder.build_update_query(
                table_name="cameras",
                updates=updates,
                where_conditions={"id": camera_id},
                allowed_fields=allowed_fields,
            )

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Failed to update camera fields: {e}")
            return False

    async def update_camera_next_capture_time(
        self, camera_id: int, next_capture_at: datetime
    ) -> bool:
        """
        Update the next capture time for a camera.

        Args:
            camera_id: ID of the camera
            next_capture_at: Next capture timestamp

        Returns:
            True if update was successful

        Usage:
            from ..utils.time_utils import utc_now
            success = await db.update_camera_next_capture_time(1, utc_now())
        """
        query = "UPDATE cameras SET next_capture_at = %s WHERE id = %s"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (next_capture_at, camera_id))
                affected = cur.rowcount
                return bool(affected and affected > 0)

    async def update_camera_corruption_settings(
        self, camera_id: int, settings: Dict[str, Any]
    ) -> bool:
        """
        Update camera-specific corruption detection settings.

        Args:
            camera_id: ID of the camera
            settings: Dictionary containing corruption settings

        Returns:
            True if update was successful

        Usage:
            success = await db.update_camera_corruption_settings(1, {
                'corruption_detection_heavy': True
            })
        """
        corruption_fields = [
            "corruption_detection_heavy",
            "corruption_score",
            "is_flagged",
            "consecutive_corruption_failures",
            "lifetime_glitch_count",
        ]

        return await self._update_camera_fields(
            camera_id, settings, set(corruption_fields)
        )

    async def update_camera_health(
        self, camera_id: int, health_data: Dict[str, Any]
    ) -> bool:
        """
        Update camera health metrics.

        Args:
            camera_id: ID of the camera
            health_data: Dictionary containing health metrics

        Returns:
            True if update was successful

        Usage:
            success = await db.update_camera_health(1, {
                'consecutive_corruption_failures': 0
            })
        """
        health_fields = [
            "consecutive_corruption_failures",
            "lifetime_glitch_count",
            "degraded_mode_active",
            "last_degraded_at",
            "health_status",
            "last_capture_at",
            "last_capture_success",
            "consecutive_failures",
        ]

        return await self._update_camera_fields(
            camera_id, health_data, set(health_fields)
        )

    async def update_camera_status(
        self, camera_id: int, status: str, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera status and error information.

        Args:
            camera_id: ID of the camera
            status: New status ('active', 'inactive', 'error')
            _error_message: Optional error message (unused)

        Returns:
            True if status was updated successfully

        Usage:
            success = await db.update_camera_status(1, 'active')
        """
        # Get timezone-aware timestamp
        now = await get_timezone_aware_timestamp_async(self.db)

        query = """
        UPDATE cameras 
        SET status = %s, 
            last_error = %s,
            updated_at = %s
        WHERE id = %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (status, error_message, now, camera_id))
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    async def update_camera_capture_stats(
        self,
        camera_id: int,
        success: bool,
        health_status: str,
        _error_message: Optional[str] = None,
    ) -> bool:
        """
        Update camera capture statistics after a capture attempt.

        NOTE: Business logic for health status determination moved to CameraService.
        This method now only updates database fields.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful
            health_status: Health status determined by service layer
            _error_message: Optional error message (unused) if capture failed

        Returns:
            True if stats were updated successfully
        """
        # Get timezone-aware timestamp
        now = await get_timezone_aware_timestamp_async(self.db)

        if success:
            # Reset consecutive failures and update last success time
            query = """
            UPDATE cameras
            SET last_capture_at = %s,
                last_capture_success = true,
                consecutive_failures = 0,
                health_status = %s,
                updated_at = %s
            WHERE id = %s
            """
            params = (now, health_status, now, camera_id)
        else:
            # Increment consecutive failures - health status determined by service layer
            query = """
            UPDATE cameras
            SET last_capture_success = false,
                consecutive_failures = consecutive_failures + 1,
                health_status = %s,
                updated_at = %s
            WHERE id = %s
            """
            params = (health_status, now, camera_id)

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                affected = cur.rowcount
                return bool(affected and affected) > 0

    async def get_cameras_due_for_capture(self) -> List[Camera]:
        """
        Get cameras that are due for capture based on schedule.

        NOTE: Business logic for capture readiness moved to CameraService.
        This method now only retrieves cameras due by schedule.

        Returns cameras that are:
        - Due for capture (next_capture_at <= now)

        Returns:
            List of Camera model instances due for capture
        """
        # Get current timezone-aware timestamp for comparison
        now = await get_timezone_aware_timestamp_async(self.db)

        query = """
        SELECT 
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
        WHERE (c.next_capture_at IS NULL OR c.next_capture_at <= %s)
        ORDER BY c.next_capture_at ASC NULLS FIRST
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (now,))
                results = await cur.fetchall()

                cameras = []
                for row in results:
                    try:
                        camera_data = await self._prepare_camera_data(row)
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model for row {row}: {e}")
                        continue

                return cameras

    async def update_camera_crop_settings(
        self, camera_id: int, settings: Dict[str, Any], enabled: bool
    ) -> bool:
        """
        Update crop/rotation settings for a camera.

        Args:
            camera_id: Camera ID
            settings: Crop/rotation settings dictionary
            enabled: Whether crop/rotation is enabled

        Returns:
            True if successful
        """
        query = """
            UPDATE cameras 
            SET crop_rotation_settings = $1, 
                crop_rotation_enabled = $2, 
                updated_at = $3
            WHERE id = $4
        """

        now = await get_timezone_aware_timestamp_async(self.settings_service)

        async with self.db.get_connection() as conn:
            await conn.execute(query, (settings, enabled, now, camera_id))
            logger.debug(f"Updated crop/rotation settings for camera {camera_id}")
            return True

    async def update_source_resolution(
        self, camera_id: int, resolution: Dict[str, Any]
    ) -> bool:
        """
        Update source resolution for a camera.

        Args:
            camera_id: Camera ID
            resolution: Source resolution dictionary

        Returns:
            True if successful
        """
        query = """
            UPDATE cameras 
            SET source_resolution = $1, 
                updated_at = $2
            WHERE id = $3
        """

        now = await get_timezone_aware_timestamp_async(self.settings_service)

        async with self.db.get_connection() as conn:
            await conn.execute(query, (resolution, now, camera_id))
            logger.debug(f"Updated source resolution for camera {camera_id}")
            return True


class SyncCameraOperations:
    """Sync camera database operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        # Import moved to top of file to avoid import-outside-toplevel

        self.db = db
        self.settings_ops = SyncSettingsOperations(db)

    def _prepare_camera_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare database row data for Pydantic model validation (sync version).

        Uses shared helper function to eliminate code duplication.
        Gets timezone from database cache and delegates processing to shared helper.
        """
        camera_data = dict(row)

        # Get timezone from database cache (sync)
        tz_str = get_timezone_from_cache_sync(self.settings_ops)
        tz = ZoneInfo(tz_str)

        # Use shared helper for common processing logic
        return _prepare_camera_data_shared(camera_data, tz)

    def get_active_cameras(self) -> List[Camera]:
        """
        Retrieve all enabled cameras for worker processing.

        Returns:
            List of enabled Camera model instances

        Usage:
            cameras = db.get_active_cameras()
        """
        query = """
        SELECT 
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
        WHERE c.enabled = true
        ORDER BY c.id
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()

                cameras = []
                for row in results:
                    try:
                        camera_data = self._prepare_camera_data(row)
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model for row {row}: {e}")
                        continue

                return cameras

    def get_cameras_with_running_timelapses(self) -> List[Camera]:
        """
        Retrieve cameras that have active running timelapses.

        Returns:
            List of Camera model instances with running timelapses

        Usage:
            cameras = db.get_cameras_with_running_timelapses()
        """
        query = """
        SELECT 
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        INNER JOIN timelapses t ON c.id = t.camera_id AND t.status = 'running'
        WHERE c.enabled = true
        ORDER BY c.id
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()

                cameras = []
                for row in results:
                    try:
                        camera_data = self._prepare_camera_data(row)
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model for row {row}: {e}")
                        continue

                return cameras

    def get_camera_by_id(self, camera_id: int) -> Optional[Camera]:
        """
        Retrieve a specific camera by ID.

        Args:
            camera_id: ID of the camera to retrieve

        Returns:
            Camera model instance or None if not found

        Usage:
            camera = db.get_camera_by_id(1)
        """
        query = """
        SELECT 
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
        WHERE c.id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id,))
                results = cur.fetchall()

                if results:
                    try:
                        camera_data = self._prepare_camera_data(results[0])
                        return Camera.model_validate(camera_data)
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model: {e}")
                        return None

                return None

    def update_camera_connectivity(
        self, camera_id: int, is_connected: bool, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera connectivity status.

        Args:
            camera_id: ID of the camera
            is_connected: Whether camera is currently connected
            error_message: Optional error message if disconnected

        Returns:
            True if update was successful

        Usage:
            success = db.update_camera_connectivity(1, False, "Connection timeout")
        """
        # Get timezone-aware timestamp for sync operation
        now = get_timezone_aware_timestamp_sync(self.settings_ops)

        query = """
        UPDATE cameras 
        SET is_connected = %s, 
            last_error = %s,
            updated_at = %s
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (is_connected, error_message, now, camera_id))
                affected = cur.rowcount
                return bool(affected and affected) > 0

    def update_next_capture_time(
        self, camera_id: int, next_capture_at: datetime
    ) -> bool:
        """
        Update the next capture time for a camera.

        Args:
            camera_id: ID of the camera
            next_capture_at: Next capture timestamp

        Returns:
            True if update was successful

        Usage:
            from ..utils.time_utils import utc_now
            success = db.update_next_capture_time(1, utc_now())
        """
        query = "UPDATE cameras SET next_capture_at = %s WHERE id = %s"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (next_capture_at, camera_id))
                affected = cur.rowcount
                return bool(affected and affected) > 0

    def get_camera_corruption_settings(
        self, camera_id: int
    ) -> Optional[CorruptionSettingsModel]:
        """
        Get camera-specific corruption detection settings.

        Args:
            camera_id: ID of the camera

        Returns:
            CorruptionSettingsModel instance or None if not found

        Usage:
            settings = db.get_camera_corruption_settings(1)
        """
        query = """
        SELECT
            corruption_detection_heavy,
            lifetime_glitch_count,
            consecutive_corruption_failures,
            degraded_mode_active
        FROM cameras
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id,))
                results = cur.fetchall()
                if results:
                    try:
                        return CorruptionSettingsModel.model_validate(dict(results[0]))
                    except ValidationError as e:
                        logger.error(f"Error creating CorruptionSettingsModel: {e}")
                        return None
                return None

    def update_camera_corruption_failure_count(
        self, camera_id: int, increment: bool = True
    ) -> bool:
        """
        Update camera corruption failure counters.

        Args:
            camera_id: ID of the camera
            increment: Whether to increment (True) or reset (False) counters

        Returns:
            True if update was successful

        Usage:
            success = db.update_camera_corruption_failure_count(1, True)
        """
        # Get timezone-aware timestamp for sync operation
        now = get_timezone_aware_timestamp_sync(self.settings_ops)

        if increment:
            query = """
            UPDATE cameras
            SET consecutive_corruption_failures = consecutive_corruption_failures + 1,
                lifetime_glitch_count = lifetime_glitch_count + 1,
                updated_at = %s
            WHERE id = %s
            """
            params = (now, camera_id)
        else:
            query = """
            UPDATE cameras
            SET consecutive_corruption_failures = 0,
                updated_at = %s
            WHERE id = %s
            """
            params = (now, camera_id)

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount
                return bool(affected and affected) > 0

    def set_camera_degraded_mode(self, camera_id: int, is_degraded: bool) -> bool:
        """
        Set camera degraded mode status.

        Args:
            camera_id: ID of the camera
            is_degraded: Whether camera should be in degraded mode

        Returns:
            True if update was successful

        Usage:
            success = db.set_camera_degraded_mode(1, True)
        """
        # Get timezone-aware timestamp for sync operation
        now = get_timezone_aware_timestamp_sync(self.settings_ops)

        query = """
        UPDATE cameras
        SET degraded_mode_active = %s,
            last_degraded_at = CASE WHEN %s THEN %s ELSE last_degraded_at END,
            updated_at = %s
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (is_degraded, is_degraded, now, now, camera_id))
                affected = cur.rowcount
                return bool(affected and affected) > 0

    def reset_camera_corruption_failures(self, camera_id: int) -> bool:
        """
        Reset camera corruption failure counters.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful

        Usage:
            success = db.reset_camera_corruption_failures(1)
        """
        # Get timezone-aware timestamp for sync operation
        now = get_timezone_aware_timestamp_sync(self.settings_ops)

        query = """
        UPDATE cameras
        SET consecutive_corruption_failures = 0,
            degraded_mode_active = false,
            updated_at = %s
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (now, camera_id))
                affected = cur.rowcount
                return bool(affected and affected) > 0

    def update_camera_capture_stats(
        self,
        camera_id: int,
        success: bool,
        health_status: str,
        _error_message: Optional[str] = None,
    ) -> bool:
        """
        Update camera capture statistics after a capture attempt.

        NOTE: Business logic for health status determination moved to CameraService.
        This method now only updates database fields.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful
            health_status: Health status determined by service layer
            _error_message: Optional error message (unused) if capture failed

        Returns:
            True if stats were updated successfully

        Usage:
            success = db.update_camera_capture_stats(1, True, 'online')
            success = db.update_camera_capture_stats(1, False, 'degraded', "Connection timeout")
        """
        # Get timezone-aware timestamp for sync operation
        now = get_timezone_aware_timestamp_sync(self.settings_ops)

        if success:
            # Reset consecutive failures and update last success time
            query = """
            UPDATE cameras
            SET last_capture_at = %s,
                last_capture_success = true,
                consecutive_failures = 0,
                health_status = %s,
                updated_at = %s
            WHERE id = %s
            """
            params = (now, health_status, now, camera_id)
        else:
            # Increment consecutive failures - health status determined by service layer
            query = """
            UPDATE cameras
            SET last_capture_success = false,
                consecutive_failures = consecutive_failures + 1,
                health_status = %s,
                updated_at = %s
            WHERE id = %s
            """
            params = (health_status, now, camera_id)

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount
                return bool(affected and affected) > 0

    def get_cameras_due_for_capture(self) -> List[Camera]:
        """
        Get cameras that are due for capture based on schedule.

        NOTE: Business logic for capture readiness moved to CameraService.
        This method now only retrieves cameras due by schedule.

        Returns cameras that are:
        - Due for capture (next_capture_at <= now)

        Returns:
            List of Camera model instances due for capture

        Usage:
            due_cameras = db.get_cameras_due_for_capture()
        """
        # Get current timezone-aware timestamp for comparison (sync)
        now = get_timezone_aware_timestamp_sync(self.settings_ops)

        query = """
        SELECT 
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
        WHERE (c.next_capture_at IS NULL OR c.next_capture_at <= %s)
        ORDER BY c.next_capture_at ASC NULLS FIRST
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (now,))
                results = cur.fetchall()

                cameras = []
                for row in results:
                    try:
                        camera_data = self._prepare_camera_data(row)
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError as e:
                        logger.error(f"Error creating Camera model for row {row}: {e}")
                        continue

                return cameras
