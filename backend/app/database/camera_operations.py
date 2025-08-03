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


from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import psycopg
from pydantic import ValidationError

from ..models.camera_model import Camera, ImageForCamera
from ..models.corruption_model import CorruptionSettingsModel
from ..models.shared_models import CameraHealthStatus, CameraStatistics
from ..services.settings_service import SettingsService
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.database_helpers import CameraDataProcessor, DatabaseQueryBuilder
from ..utils.time_utils import (
    get_timezone_from_cache_async,
    get_timezone_from_cache_sync,
    utc_now,
)
from .core import AsyncDatabase, SyncDatabase
from .exceptions import CameraOperationError


class CameraQueryBuilder:
    """Centralized query builder for camera operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_cameras_enabled ON cameras(enabled) WHERE enabled = true;
    - CREATE INDEX idx_cameras_id ON cameras(id);
    - CREATE INDEX idx_cameras_updated_at ON cameras(updated_at DESC);
    - CREATE INDEX idx_cameras_degraded ON cameras(degraded_mode_active) WHERE degraded_mode_active = true;
    - CREATE INDEX idx_timelapses_camera_status ON timelapses(camera_id, status) WHERE status IN ('running', 'paused');
    - CREATE INDEX idx_images_camera_captured ON images(camera_id, captured_at DESC);
    - CREATE INDEX idx_corruption_logs_camera ON corruption_logs(camera_id, created_at DESC);
    """

    @staticmethod
    def build_active_cameras_query():
        """Build optimized query for active cameras."""
        return """
        SELECT
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
        WHERE c.enabled = true
        ORDER BY c.id
        """

    @staticmethod
    def build_camera_statistics_query(camera_ids: list):
        """Build optimized query for camera statistics using array aggregation."""
        return """
        WITH camera_stats AS NOT MATERIALIZED (
            SELECT
                t.camera_id,
                COUNT(DISTINCT i.id) FILTER (WHERE i.id IS NOT NULL) as total_images,
                COUNT(DISTINCT i.id) FILTER (WHERE t.status IN ('running', 'paused')) as active_timelapse_images,
                MAX(i.captured_at) as last_capture_at
            FROM timelapses t
            LEFT JOIN images i ON t.id = i.timelapse_id
            WHERE t.camera_id = ANY(%(camera_ids)s)
            GROUP BY t.camera_id
        )
        SELECT * FROM camera_stats
        """

    @staticmethod
    def build_timelapse_counts_query(camera_ids: list):
        """Build optimized query for timelapse counts."""
        return """
        SELECT
            camera_id,
            COUNT(*) as total_timelapses
        FROM timelapses
        WHERE camera_id = ANY(%(camera_ids)s)
        GROUP BY camera_id
        """

    @staticmethod
    def build_camera_health_query():
        """Build optimized query for camera health status."""
        return """
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
            AND cl.created_at > %(twenty_four_hours_ago)s
        WHERE c.id = %(camera_id)s
        GROUP BY c.lifetime_glitch_count, c.consecutive_corruption_failures,
                c.degraded_mode_active, c.last_degraded_at, c.corruption_detection_heavy
        """

    @staticmethod
    def build_atomic_increment_query():
        """Build atomic increment query for corruption failures."""
        return """
        UPDATE cameras
        SET consecutive_corruption_failures = consecutive_corruption_failures + 1,
            lifetime_glitch_count = lifetime_glitch_count + 1,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

    @staticmethod
    def build_reset_failures_query():
        """Build query to reset corruption failure counters."""
        return """
        UPDATE cameras
        SET consecutive_corruption_failures = 0,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

    @staticmethod
    def build_degraded_mode_query():
        """Build query to set degraded mode with conditional timestamp update."""
        return """
        UPDATE cameras
        SET degraded_mode_active = %(is_degraded)s,
            last_degraded_at = CASE WHEN %(is_degraded)s THEN %(now)s ELSE last_degraded_at END,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """


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

    def __init__(self, db: AsyncDatabase, settings_service: Any) -> None:
        self.db = db
        self.settings_service = settings_service
        self.cache_invalidation = CacheInvalidationService()

    @cached_response(ttl_seconds=30, key_prefix="camera")
    async def get_active_cameras(self) -> List[Camera]:
        """
        Retrieve all enabled cameras for worker processing (async).

        Uses sophisticated caching with 30s TTL for performance.

        Returns:
            List of enabled Camera model instances
        """
        try:
            query = CameraQueryBuilder.build_active_cameras_query()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    results = await cur.fetchall()
                    cameras = []
                    for row in results:
                        camera_data = await self._prepare_camera_data(row)
                        try:
                            cameras.append(Camera.model_validate(camera_data))
                        except ValidationError:
                            # Skip invalid camera data but don't fail entire operation
                            continue
                    return cameras
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                "Failed to retrieve active cameras", operation="get_active_cameras"
            ) from e

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
        """
        Create unified Camera model from database row with all fields populated.

        Optimized version using CameraDataProcessor utility for better performance.
        """
        camera_data = await self._prepare_camera_data(row)

        # Extract base camera fields using utility
        camera_model_fields = set(Camera.model_fields.keys())
        camera_fields = CameraDataProcessor.extract_camera_base_fields(
            camera_data, camera_model_fields
        )

        # Add timelapse status fields for Camera compatibility
        camera_fields.update(
            {
                "timelapse_status": row.get("timelapse_status"),
                "timelapse_id": row.get("timelapse_id"),
            }
        )

        # Add statistics fields using utility
        stats = CameraDataProcessor.prepare_camera_statistics(row)
        camera_fields.update(stats)

        try:
            camera = Camera.model_validate(camera_fields)

            # Add image data if available
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
                except ValidationError:
                    # Skip invalid image data but don't fail camera creation
                    camera.last_image = None

            return camera
        except ValidationError as e:
            raise CameraOperationError(
                f"Failed to create camera model for camera {row.get('id')}",
                operation="_create_camera_from_row",
                details={
                    "camera_id": row.get("id"),
                    "validation_errors": (
                        str(e.errors()) if hasattr(e, "errors") else None
                    ),
                },
            ) from e

    @cached_response(ttl_seconds=60, key_prefix="camera")
    async def get_cameras(self) -> List[Camera]:
        """
        Retrieve all cameras with their current status and statistics.

        Optimized version that splits complex aggregation into separate queries
        for better performance and reduced database load.

        Uses sophisticated caching with 60s TTL for performance.

        Returns:
            List of Camera model instances

        Usage:
            cameras = await db.get_cameras()
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Step 1: Get basic camera data with active timelapse info (optimized)
                    camera_query = """
                    SELECT
                        c.*,
                        t.status as timelapse_status,
                        t.id as timelapse_id,
                        t.name as timelapse_name
                    FROM cameras c
                    LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
                    ORDER BY c.created_at ASC
                    """
                    await cur.execute(camera_query)
                    camera_rows = await cur.fetchall()

                    if not camera_rows:
                        return []

                    # Step 2: Get aggregated statistics for all cameras in one query
                    camera_ids = [row["id"] for row in camera_rows]

                    stats_query = CameraQueryBuilder.build_camera_statistics_query(
                        camera_ids
                    )
                    await cur.execute(stats_query, {"camera_ids": camera_ids})
                    stats_rows = await cur.fetchall()
                    stats_dict = {row["camera_id"]: row for row in stats_rows}

                    # Step 3: Get timelapse counts for all cameras in one query
                    timelapse_query = CameraQueryBuilder.build_timelapse_counts_query(
                        camera_ids
                    )
                    await cur.execute(timelapse_query, {"camera_ids": camera_ids})
                    timelapse_rows = await cur.fetchall()
                    timelapse_dict = {
                        row["camera_id"]: row["total_timelapses"]
                        for row in timelapse_rows
                    }

                    # Step 4: Build Camera objects with batched data
                    cameras = []
                    for row in camera_rows:
                        camera_id = row["id"]
                        # Merge statistics
                        if camera_id in stats_dict:
                            stats = stats_dict[camera_id]
                            row = dict(row)
                            row["total_images"] = stats["total_images"] or 0
                            row["active_timelapse_images"] = (
                                stats["active_timelapse_images"] or 0
                            )
                            row["last_capture_at"] = stats["last_capture_at"]
                        else:
                            row = dict(row)
                            row["total_images"] = 0
                            row["active_timelapse_images"] = 0
                            row["last_capture_at"] = None

                        row["total_timelapses"] = timelapse_dict.get(camera_id, 0)

                        try:
                            camera = await self._create_camera_from_row(row)
                            cameras.append(camera)
                        except Exception:
                            # Skip invalid cameras but don't fail entire operation
                            continue

                    return cameras
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                "Failed to retrieve cameras", operation="get_cameras"
            ) from e

    @cached_response(ttl_seconds=60, key_prefix="camera")
    async def get_camera_by_id(self, camera_id: int) -> Optional[Camera]:
        """
        Retrieve a specific camera by ID with its current status.

        Optimized version that uses separate queries instead of complex JOINs
        for better performance and maintainability.

        Uses sophisticated caching with 60s TTL for performance.

        Args:
            camera_id: ID of the camera to retrieve

        Returns:
            Camera model instance, or None if not found

        Usage:
            camera = await db.get_camera_by_id(1)
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Step 1: Get basic camera data with active timelapse info
                camera_query = """
                SELECT
                    c.*,
                    t.status as timelapse_status,
                    t.id as timelapse_id,
                    t.name as timelapse_name
                FROM cameras c
                LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
                WHERE c.id = %(camera_id)s
                """
                await cur.execute(camera_query, {"camera_id": camera_id})
                camera_row = await cur.fetchone()

                if not camera_row:
                    return None

                camera_data = dict(camera_row)

                # Step 2: Get image statistics for this camera
                stats_query = """
                SELECT
                    COUNT(DISTINCT i.id) as total_images,
                    COUNT(DISTINCT CASE WHEN i.timelapse_id IN (
                        SELECT id FROM timelapses WHERE camera_id = %(camera_id_subquery)s AND status IN ('running', 'paused')
                    ) THEN i.id END) as active_timelapse_images,
                    MAX(i.captured_at) as last_capture_at
                FROM images i
                WHERE i.camera_id = %(camera_id)s
                """
                await cur.execute(
                    stats_query,
                    {"camera_id": camera_id, "camera_id_subquery": camera_id},
                )
                stats_row = await cur.fetchone()

                if stats_row:
                    camera_data["total_images"] = stats_row["total_images"] or 0
                    camera_data["active_timelapse_images"] = (
                        stats_row["active_timelapse_images"] or 0
                    )
                    camera_data["last_capture_at"] = stats_row["last_capture_at"]
                else:
                    camera_data["total_images"] = 0
                    camera_data["active_timelapse_images"] = 0
                    camera_data["last_capture_at"] = None

                # Step 3: Get timelapse count for this camera
                timelapse_query = """
                SELECT COUNT(*) as total_timelapses
                FROM timelapses
                WHERE camera_id = %(camera_id)s
                """
                await cur.execute(timelapse_query, {"camera_id": camera_id})
                timelapse_row = await cur.fetchone()
                camera_data["total_timelapses"] = (
                    timelapse_row["total_timelapses"] if timelapse_row else 0
                )

                # Step 4: Get latest image info separately (more efficient than LATERAL JOIN)
                latest_image_query = """
                SELECT id, captured_at, file_path, file_size, day_number,
                        thumbnail_path, thumbnail_size, small_path, small_size
                FROM images
                WHERE camera_id = %(camera_id)s
                ORDER BY captured_at DESC
                LIMIT 1
                """
                await cur.execute(latest_image_query, {"camera_id": camera_id})
                latest_image = await cur.fetchone()

                if latest_image:
                    camera_data.update(
                        {
                            "last_image_id": latest_image["id"],
                            "last_image_captured_at": latest_image["captured_at"],
                            "last_image_file_path": latest_image["file_path"],
                            "last_image_file_size": latest_image["file_size"],
                            "last_image_day_number": latest_image["day_number"],
                            "last_image_thumbnail_path": latest_image["thumbnail_path"],
                            "last_image_thumbnail_size": latest_image["thumbnail_size"],
                            "last_image_small_path": latest_image["small_path"],
                            "last_image_small_size": latest_image["small_size"],
                        }
                    )

                try:
                    return await self._create_camera_from_row(camera_data)
                except Exception as e:
                    raise CameraOperationError(
                        f"Failed to create camera model for camera {camera_id}",
                        operation="get_camera_by_id",
                        details={"camera_id": camera_id},
                    ) from e

    @cached_response(ttl_seconds=30, key_prefix="camera")
    async def get_camera_comprehensive_status(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive camera status including health, connectivity, and corruption data.

        Uses sophisticated caching with 30s TTL for real-time status monitoring.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing comprehensive status information, or None if camera not found
        """
        try:
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
            WHERE c.id = %(camera_id)s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, {"camera_id": camera_id})
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
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                f"Failed to get comprehensive status for camera {camera_id}",
                operation="get_camera_comprehensive_status",
                details={"camera_id": camera_id},
            ) from e

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
                'enabled': True,
                'source_resolution': {'width': 2688, 'height': 1512}
            })
        """
        try:
            query = """
            INSERT INTO cameras (
                name, rtsp_url, status, rotation,
                crop_rotation_enabled, crop_rotation_settings, source_resolution,
                corruption_detection_heavy, corruption_score, is_flagged,
                lifetime_glitch_count, consecutive_corruption_failures,
                degraded_mode_active, last_degraded_at, enabled, is_connected,
                last_error, last_error_message
            ) VALUES (
                %(name)s, %(rtsp_url)s, %(status)s, %(rotation)s,
                %(crop_rotation_enabled)s, %(crop_rotation_settings)s, %(source_resolution)s,
                %(corruption_detection_heavy)s, %(corruption_score)s, %(is_flagged)s,
                %(lifetime_glitch_count)s, %(consecutive_corruption_failures)s,
                %(degraded_mode_active)s, %(last_degraded_at)s, %(enabled)s, %(is_connected)s,
                %(last_error)s, %(last_error_message)s
            ) RETURNING *
            """

            # Ensure all required fields are present with sensible defaults
            camera_data.setdefault("enabled", True)
            camera_data.setdefault("is_connected", True)
            camera_data.setdefault("last_error", None)
            camera_data.setdefault("last_error_message", None)
            camera_data.setdefault("is_flagged", False)

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
                            raise CameraOperationError(
                                "Failed to validate created camera data",
                                operation="create_camera",
                                details={
                                    "validation_errors": (
                                        str(e.errors())
                                        if hasattr(e, "errors")
                                        else None
                                    )
                                },
                            ) from e
                    raise CameraOperationError(
                        "Failed to create camera - no results returned",
                        operation="create_camera",
                    )
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                "Failed to create camera",
                operation="create_camera",
                details={"camera_name": camera_data.get("name")},
            ) from e

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
        try:
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
                    raise CameraOperationError(
                        f"Camera {camera_id} not found",
                        operation="update_camera",
                        details={"camera_id": camera_id},
                    )
                # Return the Camera model
                return Camera(
                    **{
                        k: v
                        for k, v in current_camera.model_dump().items()
                        if k in Camera.model_fields.keys()
                    }
                )

            # Add timezone-aware timestamp for updated_at
            now = utc_now()
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
                            # Clear related caches after successful update
                            await self._clear_camera_caches(camera_id, updated_at=now)
                            return updated_camera
                        except ValidationError as e:
                            raise CameraOperationError(
                                f"Failed to validate updated camera data for camera {camera_id}",
                                operation="update_camera",
                                details={
                                    "camera_id": camera_id,
                                    "validation_errors": (
                                        str(e.errors())
                                        if hasattr(e, "errors")
                                        else None
                                    ),
                                },
                            ) from e
                    raise CameraOperationError(
                        f"Failed to update camera {camera_id} - no results returned",
                        operation="update_camera",
                        details={"camera_id": camera_id},
                    )
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                f"Failed to update camera {camera_id}",
                operation="update_camera",
                details={"camera_id": camera_id},
            ) from e

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
        query = "DELETE FROM cameras WHERE id = %(camera_id)s"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"camera_id": camera_id})
                affected = cur.rowcount

                if affected and affected > 0:
                    # Clear related caches after successful deletion
                    await self._clear_camera_caches(camera_id)
                    return True
                return False

    @cached_response(ttl_seconds=60, key_prefix="camera")
    async def get_camera_health_status(
        self, camera_id: int
    ) -> Optional[CameraHealthStatus]:
        """
        Get camera health status including corruption detection metrics.

        Uses sophisticated caching with 60s TTL for health monitoring.

        Args:
            camera_id: ID of the camera

        Returns:
            CameraHealthStatus model instance or None if camera not found

        Usage:
            health = await db.get_camera_health_status(1)
        """
        # Calculate 24 hours ago using timezone-aware timestamp
        # timedelta already imported at top

        now = utc_now()
        twenty_four_hours_ago = now - timedelta(hours=24)

        query = CameraQueryBuilder.build_camera_health_query()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "twenty_four_hours_ago": twenty_four_hours_ago,
                        "camera_id": camera_id,
                    },
                )
                results = await cur.fetchall()
                if results:
                    try:
                        return CameraHealthStatus.model_validate(dict(results[0]))
                    except ValidationError as e:
                        raise CameraOperationError(
                            f"Failed to validate camera health status for camera {camera_id}",
                            operation="get_camera_health_status",
                            details={
                                "camera_id": camera_id,
                                "validation_errors": (
                                    str(e.errors()) if hasattr(e, "errors") else None
                                ),
                            },
                        ) from e
                return None

    @cached_response(ttl_seconds=300, key_prefix="camera")
    async def get_camera_stats(self, camera_id: int) -> Optional[CameraStatistics]:
        """
        Get comprehensive camera statistics.

        Uses sophisticated caching with 5-minute TTL since stats change slowly.

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
        WHERE c.id = %(camera_id)s
        GROUP BY c.id
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"camera_id": camera_id})
                results = await cur.fetchall()
                if results:
                    try:
                        return CameraStatistics.model_validate(dict(results[0]))
                    except ValidationError as e:
                        raise CameraOperationError(
                            f"Failed to validate camera statistics for camera {camera_id}",
                            operation="get_camera_stats",
                            details={
                                "camera_id": camera_id,
                                "validation_errors": (
                                    str(e.errors()) if hasattr(e, "errors") else None
                                ),
                            },
                        ) from e
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
                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful update
                        from ..utils.time_utils import utc_now

                        current_time = utc_now()
                        await self._clear_camera_caches(
                            camera_id, updated_at=current_time
                        )
                    return success

        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                f"Failed to update camera fields for camera {camera_id}",
                operation="_update_camera_fields",
                details={"camera_id": camera_id, "updates": str(updates)},
            ) from e

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
        query = "UPDATE cameras SET next_capture_at = %(next_capture_at)s WHERE id = %(camera_id)s"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query, {"next_capture_at": next_capture_at, "camera_id": camera_id}
                )
                affected = cur.rowcount
                success = bool(affected and affected > 0)
                if success:
                    # Clear related caches after successful update
                    await self._clear_camera_caches(
                        camera_id, updated_at=next_capture_at
                    )
                return success

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
        now = utc_now()

        query = """
        UPDATE cameras
        SET status = %(status)s,
            last_error = %(error_message)s,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "status": status,
                        "error_message": error_message,
                        "now": now,
                        "camera_id": camera_id,
                    },
                )
                affected = cur.rowcount

                if affected and affected > 0:
                    # Clear related caches after successful update
                    await self._clear_camera_caches(camera_id, updated_at=now)
                    return True
                return False

    async def update_camera_capture_stats(
        self,
        camera_id: int,
        success: bool,
        health_status: str,
    ) -> bool:
        """
        Update camera capture statistics after a capture attempt.

        NOTE: Business logic for health status determination moved to CameraService.
        This method now only updates database fields.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful
            health_status: Health status determined by service layer

        Returns:
            True if stats were updated successfully
        """
        # Get timezone-aware timestamp
        now = utc_now()

        if success:
            # Reset consecutive failures and update last success time
            query = """
            UPDATE cameras
            SET last_capture_at = %(now)s,
                last_capture_success = true,
                consecutive_failures = 0,
                health_status = %(health_status)s,
                updated_at = %(now_updated)s
            WHERE id = %(camera_id)s
            """
            params = {
                "now": now,
                "health_status": health_status,
                "now_updated": now,
                "camera_id": camera_id,
            }
        else:
            # Increment consecutive failures - health status determined by service layer
            query = """
            UPDATE cameras
            SET last_capture_success = false,
                consecutive_failures = consecutive_failures + 1,
                health_status = %(health_status)s,
                updated_at = %(now)s
            WHERE id = %(camera_id)s
            """
            params = {
                "health_status": health_status,
                "now": now,
                "camera_id": camera_id,
            }

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                affected = cur.rowcount
                success = bool(affected and affected > 0)
                if success:
                    # Clear related caches after successful update
                    await self._clear_camera_caches(camera_id, updated_at=now)
                return success

    @cached_response(ttl_seconds=10, key_prefix="camera")
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
        now = utc_now()

        query = """
        SELECT
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id
        WHERE (c.next_capture_at IS NULL OR c.next_capture_at <= %(now)s)
        ORDER BY c.next_capture_at ASC NULLS FIRST
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"now": now})
                results = await cur.fetchall()

                cameras = []
                for row in results:
                    try:
                        camera_data = await self._prepare_camera_data(row)
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError:
                        # Skip invalid camera data but don't fail entire operation
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
            SET crop_rotation_settings = %(settings)s,
                crop_rotation_enabled = %(enabled)s,
                updated_at = %(now)s
            WHERE id = %(camera_id)s
        """

        now = utc_now()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "settings": settings,
                        "enabled": enabled,
                        "now": now,
                        "camera_id": camera_id,
                    },
                )
            # Clear related caches after successful update
            await self._clear_camera_caches(camera_id, updated_at=now)
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
            SET source_resolution = %(resolution)s,
                updated_at = %(now)s
            WHERE id = %(camera_id)s
        """

        now = utc_now()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {"resolution": resolution, "now": now, "camera_id": camera_id},
                )
            # Clear related caches after successful update
            await self._clear_camera_caches(camera_id, updated_at=now)
            return True

    async def _clear_camera_caches(
        self, camera_id: int, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to a specific camera using sophisticated cache system."""
        # Use event-driven cache invalidation for camera status changes
        await self.cache_invalidation.invalidate_camera_status_cache(camera_id)

        # Clear general camera caches using advanced cache manager
        camera_patterns = [
            "camera:get_active_cameras",
            "camera:get_cameras",
            f"camera:get_camera_by_id:{camera_id}",
            f"camera:get_camera_comprehensive_status:{camera_id}",
            f"camera:get_camera_health_status:{camera_id}",
            f"camera:get_camera_stats:{camera_id}",
            "camera:get_cameras_due_for_capture",
        ]

        for pattern in camera_patterns:
            await cache.delete(pattern)

        # If timestamp provided, use ETag-aware invalidation
        if updated_at:
            etag = generate_composite_etag(camera_id, updated_at)
            await self.cache_invalidation.invalidate_with_etag_validation(
                f"camera:metadata:{camera_id}", etag
            )


class SyncCameraOperations:
    """Sync camera database operations for worker processes."""

    def __init__(self, db: SyncDatabase, async_db: AsyncDatabase) -> None:
        # Import moved to top of file to avoid import-outside-toplevel

        self.db = db
        self.async_db = async_db
        self.settings_service = SettingsService(self.async_db)

    def _prepare_camera_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare database row data for Pydantic model validation (sync version).

        Uses shared helper function to eliminate code duplication.
        Gets timezone from database cache and delegates processing to shared helper.
        """
        camera_data = dict(row)

        # Get timezone from database cache (sync)
        tz_str = get_timezone_from_cache_sync(self.settings_service)
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
        try:
            query = CameraQueryBuilder.build_active_cameras_query()

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    results = cur.fetchall()

                    cameras = []
                    for row in results:
                        try:
                            camera_data = self._prepare_camera_data(row)
                            cameras.append(Camera.model_validate(camera_data))
                        except ValidationError:
                            # Skip invalid camera data but don't fail entire operation
                            continue

                    return cameras
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                "Failed to retrieve active cameras", operation="get_active_cameras"
            ) from e

    def get_cameras_with_running_timelapses(self) -> List[Camera]:
        """
        Retrieve cameras that have active running timelapses.

        Returns:
            List of Camera model instances with running timelapses

        Usage:
            cameras = db.get_cameras_with_running_timelapses()
        """
        try:
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
                        except ValidationError:
                            # Skip invalid camera data but don't fail entire operation
                            continue

                    return cameras
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                "Failed to retrieve cameras with running timelapses",
                operation="get_cameras_with_running_timelapses",
            ) from e

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
        try:
            query = """
            SELECT
                c.*,
                t.id as active_timelapse_id,
                t.status as timelapse_status
            FROM cameras c
            LEFT JOIN timelapses t ON c.id = t.camera_id AND t.status IN ('running', 'paused')
            WHERE c.id = %(camera_id)s
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, {"camera_id": camera_id})
                    results = cur.fetchall()

                    if results:
                        try:
                            camera_data = self._prepare_camera_data(results[0])
                            return Camera.model_validate(camera_data)
                        except ValidationError as e:
                            raise CameraOperationError(
                                f"Failed to validate camera data for camera {camera_id}",
                                operation="get_camera_by_id",
                                details={
                                    "camera_id": camera_id,
                                    "validation_errors": (
                                        str(e.errors())
                                        if hasattr(e, "errors")
                                        else None
                                    ),
                                },
                            ) from e

                    return None
        except (psycopg.Error, KeyError, ValueError) as e:
            raise CameraOperationError(
                f"Failed to retrieve camera {camera_id}",
                operation="get_camera_by_id",
                details={"camera_id": camera_id},
            ) from e

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
        now = utc_now()

        query = """
        UPDATE cameras
        SET is_connected = %(is_connected)s,
            last_error = %(error_message)s,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "is_connected": is_connected,
                        "error_message": error_message,
                        "now": now,
                        "camera_id": camera_id,
                    },
                )
                affected = cur.rowcount
                return bool(affected and affected > 0)

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
        query = "UPDATE cameras SET next_capture_at = %(next_capture_at)s WHERE id = %(camera_id)s"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query, {"next_capture_at": next_capture_at, "camera_id": camera_id}
                )
                affected = cur.rowcount
                return bool(affected and affected > 0)

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
        WHERE id = %(camera_id)s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"camera_id": camera_id})
                results = cur.fetchall()
                if results:
                    try:
                        return CorruptionSettingsModel.model_validate(dict(results[0]))
                    except ValidationError as e:
                        raise CameraOperationError(
                            f"Failed to validate corruption settings for camera {camera_id}",
                            operation="get_camera_corruption_settings",
                            details={
                                "camera_id": camera_id,
                                "validation_errors": (
                                    str(e.errors()) if hasattr(e, "errors") else None
                                ),
                            },
                        ) from e
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
        now = utc_now()

        if increment:
            query = CameraQueryBuilder.build_atomic_increment_query()
            params = {"now": now, "camera_id": camera_id}
        else:
            query = CameraQueryBuilder.build_reset_failures_query()
            params = {"now": now, "camera_id": camera_id}

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount
                return bool(affected and affected > 0)

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
        now = utc_now()

        query = CameraQueryBuilder.build_degraded_mode_query()

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {"is_degraded": is_degraded, "now": now, "camera_id": camera_id},
                )
                affected = cur.rowcount
                return bool(affected and affected > 0)

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
        now = utc_now()

        query = """
        UPDATE cameras
        SET consecutive_corruption_failures = 0,
            degraded_mode_active = false,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"now": now, "camera_id": camera_id})
                affected = cur.rowcount
                return bool(affected and affected > 0)

    def update_camera_capture_stats(
        self,
        camera_id: int,
        success: bool,
        health_status: str,
    ) -> bool:
        """
        Update camera capture statistics after a capture attempt.

        NOTE: Business logic for health status determination moved to CameraService.
        This method now only updates database fields.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful
            health_status: Health status determined by service layer

        Returns:
            True if stats were updated successfully

        Usage:
            success = db.update_camera_capture_stats(1, True, 'online')
            success = db.update_camera_capture_stats(1, False, 'degraded', "Connection timeout")
        """
        # Get timezone-aware timestamp for sync operation
        now = utc_now()

        if success:
            # Reset consecutive failures and update last success time
            query = """
            UPDATE cameras
            SET last_capture_at = %(now)s,
                last_capture_success = true,
                consecutive_failures = 0,
                health_status = %(health_status)s,
                updated_at = %(now_updated)s
            WHERE id = %(camera_id)s
            """
            params = {
                "now": now,
                "health_status": health_status,
                "now_updated": now,
                "camera_id": camera_id,
            }
        else:
            # Increment consecutive failures - health status determined by service layer
            query = """
            UPDATE cameras
            SET last_capture_success = false,
                consecutive_failures = consecutive_failures + 1,
                health_status = %(health_status)s,
                updated_at = %(now)s
            WHERE id = %(camera_id)s
            """
            params = {
                "health_status": health_status,
                "now": now,
                "camera_id": camera_id,
            }

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount
                return bool(affected and affected > 0)

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
        now = utc_now()

        query = """
        SELECT
            c.*,
            t.id as active_timelapse_id,
            t.status as timelapse_status
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id
        WHERE (c.next_capture_at IS NULL OR c.next_capture_at <= %(now)s)
        ORDER BY c.next_capture_at ASC NULLS FIRST
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"now": now})
                results = cur.fetchall()

                cameras = []
                for row in results:
                    try:
                        camera_data = self._prepare_camera_data(row)
                        cameras.append(Camera.model_validate(camera_data))
                    except ValidationError:
                        # Skip invalid camera data but don't fail entire operation
                        continue

                return cameras
