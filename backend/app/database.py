"""
Database Layer for Timelapser v4

This module provides a comprehensive database abstraction layer for the Timelapser application,
managing PostgreSQL connections and operations for both async (FastAPI) and sync (worker) contexts.

The module implements two main database classes:
- AsyncDatabase: For use with FastAPI endpoints requiring async operations
- SyncDatabase: For use with worker processes requiring synchronous operations

Features:
- Connection pooling with configurable pool sizes
- Automatic transaction management with rollback on errors
- Comprehensive CRUD operations for all entities (cameras, timelapses, images, videos, settings)
- Real-time event broadcasting via Server-Sent Events (SSE)
- Health monitoring and statistics collection
- Time window and scheduling management
- Video generation settings and metadata handling
- Thumbnail and image size variant management

Database Schema Entities:
- cameras: Camera configuration and status
- timelapses: Timelapse sessions and metadata
- images: Captured image records with thumbnails
- videos: Generated video files and settings
- settings: Application configuration key-value pairs
- logs: System and camera event logs

Connection Management:
- Uses psycopg3 with connection pooling for performance
- Configurable pool sizes via settings
- Automatic connection health checks and recovery
- Context managers for safe connection handling

Event System:
- Broadcasts real-time updates to frontend via SSE
- Supports camera status changes, image captures, and timelapse events
- Integrates with Next.js frontend for live dashboard updates

Authors: Timelapser Development Team
Version: 4.0
License: Private
"""

import asyncio
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from datetime import datetime, date, timezone
from typing import List, Dict, Optional, Any, cast
from loguru import logger
import json
import requests
from contextlib import asynccontextmanager, contextmanager

from .config import settings


class AsyncDatabase:
    """
    Asynchronous database interface for FastAPI endpoints.

    This class provides async database operations optimized for web requests.
    It manages connection pooling, transaction handling, and provides comprehensive
    CRUD operations for all application entities.

    Features:
    - Async connection pooling with automatic lifecycle management
    - Transaction safety with automatic rollback on errors
    - Real-time event broadcasting via SSE
    - Comprehensive statistics and health monitoring
    - Support for complex queries with relationships and aggregations

    Attributes:
        _pool: AsyncConnectionPool instance for managing database connections

    Usage:
        async_db = AsyncDatabase()
        await async_db.initialize()

        # Use in FastAPI endpoints
        cameras = await async_db.get_cameras()

        # Clean shutdown
        await async_db.close()
    """

    def __init__(self):
        """Initialize the AsyncDatabase instance with empty connection pool."""
        self._pool: Optional[AsyncConnectionPool] = None

    async def initialize(self):
        """
        Initialize the async connection pool.

        Creates and opens an AsyncConnectionPool with configuration from settings.
        This method must be called before using any database operations.

        Raises:
            Exception: If connection pool initialization fails

        Note:
            This is typically called during FastAPI application startup.
        """
        try:
            self._pool = AsyncConnectionPool(
                settings.database_url,
                min_size=2,
                max_size=settings.db_pool_size,
                max_waiting=settings.db_max_overflow,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            await self._pool.open()
            logger.info("Async database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize async database pool: {e}")
            raise

    async def close(self):
        """
        Close the connection pool and cleanup resources.

        This should be called during application shutdown to ensure
        all database connections are properly closed.
        """
        if self._pool:
            await self._pool.close()
            logger.info("Async database pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """
        Get an async database connection from the pool with automatic transaction management.

        This context manager provides a database connection with automatic
        rollback on exceptions and proper connection cleanup.

        Yields:
            AsyncConnection: Database connection from the pool

        Raises:
            RuntimeError: If database pool is not initialized
            Exception: Database errors are logged and re-raised after rollback

        Usage:
            async with db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM cameras")
                    return await cur.fetchall()
        """
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.connection() as conn:
            try:
                yield conn
            except Exception as e:
                await conn.rollback()
                logger.error(f"Database error: {e}")
                raise

    # Camera methods
    async def get_cameras(self) -> List[Dict[str, Any]]:
        """
        Get all cameras with active timelapse information.

        Retrieves all cameras from the database along with their associated
        active timelapse details using a LEFT JOIN to include cameras without
        active timelapses.

        Returns:
            List[Dict[str, Any]]: List of camera dictionaries containing:
                - All camera fields (id, name, rtsp_url, status, etc.)
                - timelapse_status: Status of active timelapse (if any)
                - timelapse_id: ID of active timelapse (if any)
                - timelapse_name: Name of active timelapse (if any)

        Example:
            cameras = await db.get_cameras()
            for camera in cameras:
                print(f"Camera {camera['name']}: {camera['status']}")
                if camera['timelapse_status']:
                    print(f"  Active timelapse: {camera['timelapse_name']}")
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        c.*, 
                        t.status as timelapse_status, 
                        t.id as timelapse_id,
                        t.name as timelapse_name
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
                    ORDER BY c.id
                """
                )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_camera_by_id(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific camera by ID with active timelapse info"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        c.*, 
                        t.status as timelapse_status, 
                        t.id as timelapse_id,
                        t.name as timelapse_name
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
                    WHERE c.id = %s
                """,
                    (camera_id,),
                )
                row = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], row)

    async def create_camera(self, camera_data: Dict[str, Any]) -> Optional[int]:
        """Create a new camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO cameras (name, rtsp_url, status, time_window_start, 
                                       time_window_end, use_time_window, health_status,
                                       consecutive_failures, video_generation_mode, 
                                       standard_fps, enable_time_limits, min_time_seconds,
                                       max_time_seconds, target_time_seconds, fps_bounds_min,
                                       fps_bounds_max, corruption_detection_heavy)
                    VALUES (%(name)s, %(rtsp_url)s, %(status)s, %(time_window_start)s,
                           %(time_window_end)s, %(use_time_window)s, 'unknown', 0,
                           %(video_generation_mode)s, %(standard_fps)s, %(enable_time_limits)s,
                           %(min_time_seconds)s, %(max_time_seconds)s, %(target_time_seconds)s,
                           %(fps_bounds_min)s, %(fps_bounds_max)s, %(corruption_detection_heavy)s)
                    RETURNING id
                """,
                    camera_data,
                )
                result_row = await cur.fetchone()
                result_dict = cast(Optional[Dict[str, Any]], result_row)
                return result_dict["id"] if result_dict else None

    async def update_camera(self, camera_id: int, camera_data: Dict[str, Any]) -> bool:
        """Update a camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Build dynamic update query
                fields = []
                values = {}

                for field, value in camera_data.items():
                    if field in [
                        "name",
                        "rtsp_url",
                        "status",
                        "time_window_start",
                        "time_window_end",
                        "use_time_window",
                        "active_timelapse_id",
                        "video_generation_mode",
                        "standard_fps",
                        "enable_time_limits",
                        "min_time_seconds",
                        "max_time_seconds",
                        "target_time_seconds",
                        "fps_bounds_min",
                        "fps_bounds_max",
                        "corruption_detection_heavy",
                    ]:
                        fields.append(f"{field} = %({field})s")
                        values[field] = value

                if not fields:
                    return False

                values["camera_id"] = camera_id
                fields.append("updated_at = CURRENT_TIMESTAMP")

                query = (
                    f"UPDATE cameras SET {', '.join(fields)} WHERE id = %(camera_id)s"
                )
                await cur.execute(query, values)
                return cur.rowcount > 0

    async def delete_camera(self, camera_id: int) -> bool:
        """Delete a camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM cameras WHERE id = %s", (camera_id,))
                return cur.rowcount > 0

    # Enhanced camera methods with relationships
    async def get_cameras_with_images(self) -> List[Dict[str, Any]]:
        """Get all cameras with their latest image details using LATERAL join and active timelapse info"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        c.*,
                        t.status as timelapse_status,
                        t.id as timelapse_id,
                        t.name as timelapse_name,
                        i.id as last_image_id,
                        i.captured_at as last_image_captured_at,
                        i.file_path as last_image_file_path,
                        i.file_size as last_image_file_size,
                        i.day_number as last_image_day_number,
                        i.thumbnail_path as last_image_thumbnail_path,
                        i.thumbnail_size as last_image_thumbnail_size,
                        i.small_path as last_image_small_path,
                        i.small_size as last_image_small_size
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
                    LEFT JOIN LATERAL (
                        SELECT id, captured_at, file_path, file_size, day_number,
                               thumbnail_path, thumbnail_size, small_path, small_size
                        FROM images 
                        WHERE camera_id = c.id 
                        ORDER BY captured_at DESC 
                        LIMIT 1
                    ) i ON true
                    ORDER BY c.id
                """
                )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_camera_with_images_by_id(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get a specific camera with its latest image details using LATERAL join and active timelapse info"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        c.*,
                        t.status as timelapse_status,
                        t.id as timelapse_id,
                        t.name as timelapse_name,
                        i.id as last_image_id,
                        i.captured_at as last_image_captured_at,
                        i.file_path as last_image_file_path,
                        i.file_size as last_image_file_size,
                        i.day_number as last_image_day_number,
                        i.thumbnail_path as last_image_thumbnail_path,
                        i.thumbnail_size as last_image_thumbnail_size,
                        i.small_path as last_image_small_path,
                        i.small_size as last_image_small_size
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
                    LEFT JOIN LATERAL (
                        SELECT id, captured_at, file_path, file_size, day_number,
                               thumbnail_path, thumbnail_size, small_path, small_size
                        FROM images 
                        WHERE camera_id = c.id 
                        ORDER BY captured_at DESC 
                        LIMIT 1
                    ) i ON true
                    WHERE c.id = %s
                """,
                    (camera_id,),
                )
                row = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], row)

    async def get_camera_stats(self, camera_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get basic stats
                await cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total_images,
                        COUNT(CASE WHEN captured_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 1 END) as last_24h_images,
                        SUM(COALESCE(file_size, 0)) as total_file_size,
                        AVG(EXTRACT(EPOCH FROM (captured_at - LAG(captured_at) OVER (ORDER BY captured_at)))/60) as avg_interval_minutes
                    FROM images 
                    WHERE camera_id = %s
                """,
                    (camera_id,),
                )
                stats_row = await cur.fetchone()

                # Get success rate from camera table
                await cur.execute(
                    """
                    SELECT 
                        CASE WHEN consecutive_failures = 0 THEN 100.0
                             ELSE GREATEST(0, 100.0 - (consecutive_failures * 10.0))
                        END as success_rate_percent
                    FROM cameras 
                    WHERE id = %s
                """,
                    (camera_id,),
                )
                success_row = await cur.fetchone()

                stats = cast(Dict[str, Any], stats_row) if stats_row else {}
                success_data = cast(Dict[str, Any], success_row) if success_row else {}

                return {
                    "total_images": stats.get("total_images", 0),
                    "last_24h_images": stats.get("last_24h_images", 0),
                    "avg_capture_interval_minutes": stats.get("avg_interval_minutes"),
                    "success_rate_percent": success_data.get("success_rate_percent"),
                    "storage_used_mb": (
                        round(stats.get("total_file_size", 0) / 1024 / 1024, 2)
                        if stats.get("total_file_size")
                        else 0
                    ),
                }

    async def get_cameras_with_stats(self) -> List[Dict[str, Any]]:
        """Get all cameras with their image details and statistics"""
        cameras = await self.get_cameras_with_images()

        # Add stats to each camera
        for camera in cameras:
            camera["stats"] = await self.get_camera_stats(camera["id"])

        return cameras

    # Timelapse methods
    async def get_timelapses(
        self, camera_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get timelapses, optionally filtered by camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                if camera_id:
                    await cur.execute(
                        """
                        SELECT t.*, c.name as camera_name 
                        FROM timelapses t
                        JOIN cameras c ON t.camera_id = c.id
                        WHERE t.camera_id = %s
                        ORDER BY t.created_at DESC
                    """,
                        (camera_id,),
                    )
                else:
                    await cur.execute(
                        """
                        SELECT t.*, c.name as camera_name 
                        FROM timelapses t
                        JOIN cameras c ON t.camera_id = c.id
                        ORDER BY t.created_at DESC
                    """
                    )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_timelapse_by_id(self, timelapse_id: int) -> Optional[Dict[str, Any]]:
        """Get a single timelapse by ID"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT t.*, c.name as camera_name 
                    FROM timelapses t
                    JOIN cameras c ON t.camera_id = c.id
                    WHERE t.id = %s
                    """,
                    (timelapse_id,),
                )
                result = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], result)

    async def create_new_timelapse(
        self, camera_id: int, config: Dict[str, Any]
    ) -> Optional[int]:
        """
        Create a new timelapse entity using the entity-based model.

        This method implements the entity-based timelapse system where each
        timelapse is a separate entity that can be managed independently.
        It automatically completes any existing active timelapses for the camera
        before creating the new one.

        Args:
            camera_id: ID of the camera to create the timelapse for
            config: Configuration dictionary containing:
                - name: Optional name for the timelapse
                - auto_stop_at: Optional automatic stop timestamp
                - time_window_start: Optional custom time window start (HH:MM:SS)
                - time_window_end: Optional custom time window end (HH:MM:SS)
                - use_custom_time_window: Boolean for custom time window usage

        Returns:
            Optional[int]: ID of the created timelapse, or None if creation failed

        Note:
            This method automatically sets the new timelapse as the camera's
            active_timelapse_id and marks any existing timelapses as completed.
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # First, complete any existing active timelapse
                await cur.execute(
                    """
                    UPDATE timelapses 
                    SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                    WHERE camera_id = %s AND status IN ('running', 'paused', 'stopped')
                    """,
                    (camera_id,),
                )

                # Create new timelapse record
                await cur.execute(
                    """
                    INSERT INTO timelapses (camera_id, status, start_date, name, auto_stop_at,
                                          time_window_start, time_window_end, use_custom_time_window)
                    VALUES (%s, 'running', CURRENT_DATE, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        camera_id,
                        config.get("name"),
                        config.get("auto_stop_at"),
                        config.get("time_window_start"),
                        config.get("time_window_end"),
                        config.get("use_custom_time_window", False),
                    ),
                )
                result_row = await cur.fetchone()
                result_dict = cast(Optional[Dict[str, Any]], result_row)
                timelapse_id = result_dict["id"] if result_dict else None

                if timelapse_id:
                    # Set this as the active timelapse for the camera
                    await cur.execute(
                        """
                        UPDATE cameras 
                        SET active_timelapse_id = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (timelapse_id, camera_id),
                    )

                return timelapse_id

    async def trigger_immediate_capture_for_timelapse(
        self, camera_id: int, timelapse_id: int
    ) -> dict:
        """
        Trigger an immediate capture for a specific camera and timelapse.
        This is used when starting a new timelapse to get the first image immediately.

        Args:
            camera_id: ID of the camera to capture from
            timelapse_id: ID of the timelapse to associate the image with

        Returns:
            dict: Result containing success status and details
        """
        try:
            # Import here to avoid circular imports
            import asyncio
            from pathlib import Path
            from datetime import datetime

            # Get camera details
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                return {"success": False, "error": "Camera not found"}

            if camera.get("health_status") != "online":
                return {
                    "success": False,
                    "error": f"Camera is {camera.get('health_status', 'unknown')}",
                }

            # Get timelapse details
            timelapse = await self.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return {"success": False, "error": "Timelapse not found"}

            if timelapse.get("status") != "running":
                return {"success": False, "error": "Timelapse is not running"}

            # Check time window
            if not self._is_camera_within_time_window(camera):
                return {"success": False, "error": "Camera is outside time window"}

            # Import here to avoid circular imports
            from rtsp_capture import RTSPCapture

            # Initialize capture system
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            capture = RTSPCapture(base_data_dir=str(data_dir))

            # Get thumbnail generation setting
            def get_thumbnail_setting():
                try:
                    # Access global sync_db instance
                    import app.database

                    sync_instance = app.database.sync_db
                    with sync_instance.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT value FROM settings WHERE key = 'generate_thumbnails'"
                            )
                            result = cur.fetchone()
                            if result:
                                return result[0].lower() == "true"
                            return True
                except Exception as e:
                    logger.warning(f"Failed to get thumbnail setting: {e}")
                    return True

            # Get thumbnail setting
            loop = asyncio.get_event_loop()
            generate_thumbnails = await loop.run_in_executor(
                None, get_thumbnail_setting
            )

            # Access global sync_db instance for capture operations
            import app.database

            sync_instance = app.database.sync_db

            # Perform immediate capture
            success, message, saved_file_path = await loop.run_in_executor(
                None,
                capture.capture_image,
                camera_id,
                camera["name"],
                camera["rtsp_url"],
                sync_instance,  # RTSPCapture still uses sync_db
                timelapse_id,
                generate_thumbnails,
            )

            if success:
                # Update camera health
                await loop.run_in_executor(
                    None, sync_instance.update_camera_health, camera_id, "online", True
                )

                # Calculate and update next capture time to reset the timer
                capture_interval = await loop.run_in_executor(
                    None, sync_instance.get_capture_interval_setting
                )
                await loop.run_in_executor(
                    None,
                    sync_instance.calculate_and_update_next_capture,
                    camera_id,
                    capture_interval,
                )

                # Get updated timelapse info for accurate image count
                updated_timelapse = await loop.run_in_executor(
                    None, sync_instance.get_active_timelapse_for_camera, camera_id
                )

                # Broadcast image captured event
                await loop.run_in_executor(
                    None,
                    sync_instance.broadcast_event,
                    {
                        "type": "image_captured",
                        "data": {
                            "camera_id": camera_id,
                            "timelapse_id": timelapse_id,
                            "image_count": (
                                updated_timelapse.get("image_count", 0)
                                if updated_timelapse
                                else 0
                            ),
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                return {
                    "success": True,
                    "message": message,
                    "file_path": saved_file_path,
                    "image_count": (
                        updated_timelapse.get("image_count", 0)
                        if updated_timelapse
                        else 0
                    ),
                }
            else:
                # Update camera health to offline
                await loop.run_in_executor(
                    None,
                    sync_instance.update_camera_health,
                    camera_id,
                    "offline",
                    False,
                )
                return {"success": False, "error": message}

        except Exception as e:
            logger.error(f"Error in immediate capture for camera {camera_id}: {e}")
            return {"success": False, "error": str(e)}

    def _is_camera_within_time_window(self, camera: dict) -> bool:
        """
        Check if camera is currently within its configured time window.
        This is a helper method for immediate capture validation.
        """
        try:
            if not camera.get("use_time_window") or not camera.get("time_window_start"):
                return True  # No time window restrictions

            from datetime import datetime, time

            # Get current time in the configured timezone
            # Note: This assumes the time window is in the database timezone
            now = datetime.now()
            current_time = now.time()

            start_time_str = camera["time_window_start"]
            end_time_str = camera["time_window_end"]

            start_time = datetime.strptime(start_time_str, "%H:%M:%S").time()
            end_time = datetime.strptime(end_time_str, "%H:%M:%S").time()

            # Handle overnight windows
            if start_time <= end_time:
                # Normal window (e.g., 06:00 - 18:00)
                return start_time <= current_time <= end_time
            else:
                # Overnight window (e.g., 22:00 - 06:00)
                return current_time >= start_time or current_time <= end_time

        except Exception as e:
            logger.warning(
                f"Error checking time window for camera {camera.get('id')}: {e}"
            )
            return True  # Default to allowing capture if time window check fails

    async def copy_camera_video_settings_to_timelapse(
        self, camera_id: int, timelapse_id: int
    ) -> bool:
        """Copy video generation settings from camera to timelapse"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get camera's video generation settings
                await cur.execute(
                    """
                    SELECT video_generation_mode, standard_fps, enable_time_limits,
                           min_time_seconds, max_time_seconds, target_time_seconds,
                           fps_bounds_min, fps_bounds_max
                    FROM cameras
                    WHERE id = %s
                    """,
                    (camera_id,),
                )
                camera_settings_row = await cur.fetchone()

                if not camera_settings_row:
                    logger.error(
                        f"Camera {camera_id} not found for copying video settings"
                    )
                    return False

                camera_settings = cast(Dict[str, Any], camera_settings_row)

                # Update timelapse with camera's settings
                await cur.execute(
                    """
                    UPDATE timelapses 
                    SET video_generation_mode = %s, standard_fps = %s, enable_time_limits = %s,
                        min_time_seconds = %s, max_time_seconds = %s, target_time_seconds = %s,
                        fps_bounds_min = %s, fps_bounds_max = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        camera_settings["video_generation_mode"],
                        camera_settings["standard_fps"],
                        camera_settings["enable_time_limits"],
                        camera_settings["min_time_seconds"],
                        camera_settings["max_time_seconds"],
                        camera_settings["target_time_seconds"],
                        camera_settings["fps_bounds_min"],
                        camera_settings["fps_bounds_max"],
                        timelapse_id,
                    ),
                )

                return cur.rowcount > 0

    async def get_effective_video_settings(
        self, camera_id: int, timelapse_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get effective video generation settings (timelapse overrides or camera defaults)"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get camera defaults
                await cur.execute(
                    """
                    SELECT video_generation_mode, standard_fps, enable_time_limits,
                           min_time_seconds, max_time_seconds, target_time_seconds,
                           fps_bounds_min, fps_bounds_max
                    FROM cameras
                    WHERE id = %s
                    """,
                    (camera_id,),
                )
                camera_row = await cur.fetchone()

                if not camera_row:
                    raise ValueError(f"Camera {camera_id} not found")

                camera_settings = cast(Dict[str, Any], camera_row)

                if timelapse_id:
                    # Get timelapse overrides
                    await cur.execute(
                        """
                        SELECT video_generation_mode, standard_fps, enable_time_limits,
                               min_time_seconds, max_time_seconds, target_time_seconds,
                               fps_bounds_min, fps_bounds_max
                        FROM timelapses
                        WHERE id = %s
                        """,
                        (timelapse_id,),
                    )
                    timelapse_row = await cur.fetchone()

                    if timelapse_row:
                        timelapse_settings = cast(Dict[str, Any], timelapse_row)

                        # Use timelapse settings where not null, fall back to camera settings
                        effective_settings = {}
                        for key in camera_settings.keys():
                            timelapse_value = timelapse_settings.get(key)
                            effective_settings[key] = (
                                timelapse_value
                                if timelapse_value is not None
                                else camera_settings[key]
                            )

                        return effective_settings

                return camera_settings

    async def update_timelapse_video_settings(
        self, timelapse_id: int, settings: Dict[str, Any]
    ) -> bool:
        """Update video generation settings for a timelapse"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Build dynamic update query for video settings
                fields = []
                values = {}

                for field, value in settings.items():
                    if field in [
                        "video_generation_mode",
                        "standard_fps",
                        "enable_time_limits",
                        "min_time_seconds",
                        "max_time_seconds",
                        "target_time_seconds",
                        "fps_bounds_min",
                        "fps_bounds_max",
                    ]:
                        fields.append(f"{field} = %({field})s")
                        values[field] = value

                if not fields:
                    return False

                values["timelapse_id"] = timelapse_id
                fields.append("updated_at = CURRENT_TIMESTAMP")

                query = f"UPDATE timelapses SET {', '.join(fields)} WHERE id = %(timelapse_id)s"
                await cur.execute(query, values)
                return cur.rowcount > 0

    async def update_timelapse_status(self, timelapse_id: int, status: str) -> bool:
        """Update status of an existing timelapse (for pause/resume/stop/complete)"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE timelapses 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (status, timelapse_id),
                )
                return cur.rowcount > 0

    async def update_timelapse(
        self, timelapse_id: int, updates: Dict[str, Any]
    ) -> bool:
        """Update properties of an existing timelapse (name, auto_stop_at, etc.)"""
        if not updates:
            return True

        # Build the SET clause dynamically based on provided updates
        set_parts = []
        values = []

        allowed_fields = {
            "name": "name",
            "auto_stop_at": "auto_stop_at",
            "time_window_start": "time_window_start",
            "time_window_end": "time_window_end",
            "use_custom_time_window": "use_custom_time_window",
            "status": "status",
        }

        for key, value in updates.items():
            if key in allowed_fields:
                set_parts.append(f"{allowed_fields[key]} = %s")
                values.append(value)

        if not set_parts:
            return True  # No valid fields to update

        # Always update the timestamp
        set_parts.append("updated_at = CURRENT_TIMESTAMP")

        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                query = f"""
                    UPDATE timelapses 
                    SET {', '.join(set_parts)}
                    WHERE id = %s
                """
                values.append(timelapse_id)

                await cur.execute(query, values)
                return cur.rowcount > 0

    async def delete_timelapse(self, timelapse_id: int) -> bool:
        """Delete a timelapse and all associated data (images, videos)"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # First, clear any camera's active_timelapse_id that points to this timelapse
                await cur.execute(
                    """
                    UPDATE cameras 
                    SET active_timelapse_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE active_timelapse_id = %s
                    """,
                    (timelapse_id,),
                )

                # Delete associated videos (this should cascade to delete video files on disk)
                await cur.execute(
                    "DELETE FROM videos WHERE timelapse_id = %s",
                    (timelapse_id,),
                )

                # Delete associated images (this should cascade to delete image files on disk)
                await cur.execute(
                    "DELETE FROM images WHERE timelapse_id = %s",
                    (timelapse_id,),
                )

                # Finally, delete the timelapse itself
                await cur.execute(
                    "DELETE FROM timelapses WHERE id = %s",
                    (timelapse_id,),
                )

                return cur.rowcount > 0

    async def complete_timelapse(self, camera_id: int, timelapse_id: int) -> bool:
        """Complete a timelapse and clear active_timelapse_id"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Mark timelapse as completed
                await cur.execute(
                    """
                    UPDATE timelapses 
                    SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (timelapse_id,),
                )

                # Clear active_timelapse_id from camera
                await cur.execute(
                    """
                    UPDATE cameras 
                    SET active_timelapse_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (camera_id,),
                )

                return cur.rowcount > 0

    async def get_camera_timelapse_stats(self, camera_id: int) -> Dict[str, Any]:
        """Get timelapse-specific statistics for a camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get total images for camera
                await cur.execute(
                    """
                    SELECT COUNT(*) as total_images
                    FROM images 
                    WHERE camera_id = %s
                """,
                    (camera_id,),
                )
                total_row = await cur.fetchone()

                # Get current timelapse info and image count
                await cur.execute(
                    """
                    SELECT 
                        t.id,
                        t.name,
                        t.status,
                        COALESCE(COUNT(i.id), 0) as current_timelapse_images
                    FROM cameras c
                    LEFT JOIN timelapses t ON c.active_timelapse_id = t.id
                    LEFT JOIN images i ON i.camera_id = c.id AND i.timelapse_id = t.id
                    WHERE c.id = %s
                    GROUP BY t.id, t.name, t.status
                """,
                    (camera_id,),
                )
                timelapse_row = await cur.fetchone()

                total_data = cast(Dict[str, Any], total_row) if total_row else {}
                timelapse_data = (
                    cast(Dict[str, Any], timelapse_row) if timelapse_row else {}
                )

                return {
                    "total_images": total_data.get("total_images", 0),
                    "current_timelapse_images": timelapse_data.get(
                        "current_timelapse_images", 0
                    ),
                    "current_timelapse_name": timelapse_data.get("name"),
                    "current_timelapse_status": timelapse_data.get("status"),
                }

    # Video methods
    async def get_videos(
        self, camera_id: Optional[int] = None, timelapse_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get videos, optionally filtered by camera or timelapse"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                if camera_id and timelapse_id:
                    await cur.execute(
                        """
                        SELECT v.*, c.name as camera_name 
                        FROM videos v
                        JOIN cameras c ON v.camera_id = c.id
                        WHERE v.camera_id = %s AND v.timelapse_id = %s
                        ORDER BY v.created_at DESC
                    """,
                        (camera_id, timelapse_id),
                    )
                elif camera_id:
                    await cur.execute(
                        """
                        SELECT v.*, c.name as camera_name 
                        FROM videos v
                        JOIN cameras c ON v.camera_id = c.id
                        WHERE v.camera_id = %s
                        ORDER BY v.created_at DESC
                    """,
                        (camera_id,),
                    )
                elif timelapse_id:
                    await cur.execute(
                        """
                        SELECT v.*, c.name as camera_name 
                        FROM videos v
                        JOIN cameras c ON v.camera_id = c.id
                        WHERE v.timelapse_id = %s
                        ORDER BY v.created_at DESC
                    """,
                        (timelapse_id,),
                    )
                else:
                    await cur.execute(
                        """
                        SELECT v.*, c.name as camera_name 
                        FROM videos v
                        JOIN cameras c ON v.camera_id = c.id
                        ORDER BY v.created_at DESC
                    """
                    )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_video_by_id(self, video_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific video by ID"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT v.*, c.name as camera_name 
                    FROM videos v
                    JOIN cameras c ON v.camera_id = c.id
                    WHERE v.id = %s
                """,
                    (video_id,),
                )
                row = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], row)

    async def create_video_record(
        self, camera_id: int, name: str, settings: dict
    ) -> Optional[int]:
        """Create a new video record"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO videos (camera_id, name, status, settings)
                    VALUES (%s, %s, 'generating', %s)
                    RETURNING id
                """,
                    (camera_id, name, json.dumps(settings)),
                )
                result_row = await cur.fetchone()
                result_dict = cast(Optional[Dict[str, Any]], result_row)
                return result_dict["id"] if result_dict else None

    async def update_video_record(self, video_id: int, **kwargs):
        """Update video record with provided fields"""
        valid_fields = [
            "name",
            "file_path",
            "status",
            "settings",
            "image_count",
            "file_size",
            "duration_seconds",
            "images_start_date",
            "images_end_date",
            "calculated_fps",
            "target_duration",
            "actual_duration",
            "fps_was_adjusted",
            "adjustment_reason",
        ]

        updates = []
        values = {}

        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = %({field})s")
                if field == "settings" and isinstance(value, dict):
                    values[field] = json.dumps(value)
                else:
                    values[field] = value

        if not updates:
            return

        values["video_id"] = video_id
        updates.append("updated_at = CURRENT_TIMESTAMP")
        query = f"UPDATE videos SET {', '.join(updates)} WHERE id = %(video_id)s"

        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)

    async def delete_video(self, video_id: int) -> bool:
        """Delete a video"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))
                return cur.rowcount > 0

    async def get_logs(
        self, camera_id: Optional[int] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get logs, optionally filtered by camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                if camera_id:
                    await cur.execute(
                        """
                        SELECT id, timestamp, level, message, camera_id
                        FROM logs 
                        WHERE camera_id = %s OR camera_id IS NULL
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """,
                        (camera_id, limit),
                    )
                else:
                    await cur.execute(
                        """
                        SELECT id, timestamp, level, message, camera_id
                        FROM logs 
                        ORDER BY timestamp DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_recent_images(
        self, camera_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent images for a camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, captured_at, file_path, file_size, day_number,
                           thumbnail_path, thumbnail_size, small_path, small_size
                    FROM images 
                    WHERE camera_id = %s
                    ORDER BY captured_at DESC
                    LIMIT %s
                    """,
                    (camera_id, limit),
                )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_dashboard_data(self):
        """Get aggregated dashboard data in parallel"""
        # Fetch all dashboard data in parallel using the existing methods
        cameras_data, timelapses_data, videos_data = await asyncio.gather(
            self.get_cameras(), self.get_timelapses(), self.get_videos()
        )

        return cameras_data, timelapses_data, videos_data

    async def get_latest_image_for_camera(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get the latest image for a camera using LATERAL join"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        i.*,
                        c.name as camera_name
                    FROM cameras c
                    LEFT JOIN LATERAL (
                        SELECT id, captured_at, file_path, file_size, day_number,
                               thumbnail_path, thumbnail_size, small_path, small_size,
                               camera_id, timelapse_id, created_at, date_directory, file_name
                        FROM images 
                        WHERE camera_id = c.id 
                        ORDER BY captured_at DESC 
                        LIMIT 1
                    ) i ON true
                    WHERE c.id = %s AND i.id IS NOT NULL
                    """,
                    (camera_id,),
                )
                result_row = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], result_row)

    async def get_timelapse_images(
        self,
        timelapse_id: int,
        day_start: Optional[int] = None,
        day_end: Optional[int] = None,
    ) -> List[Dict]:
        """Get images for a specific timelapse, optionally filtered by day range"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                query = """
                    SELECT * FROM images 
                    WHERE timelapse_id = %s
                """
                params = [timelapse_id]

                if day_start is not None:
                    query += " AND day_number >= %s"
                    params.append(day_start)

                if day_end is not None:
                    query += " AND day_number <= %s"
                    params.append(day_end)

                query += " ORDER BY captured_at"

                await cur.execute(query, params)
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_timelapse_images_paginated(
        self,
        timelapse_id: int,
        offset: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> List[Dict]:
        """Get images for a specific timelapse with pagination and search"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                query = """
                    SELECT * FROM images 
                    WHERE timelapse_id = %s
                """
                params: List[Any] = [timelapse_id]

                if search:
                    query += " AND file_path ILIKE %s"
                    params.append(f"%{search}%")

                query += " ORDER BY captured_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                await cur.execute(query, params)
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Get a single image by ID"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM images WHERE id = %s
                    """,
                    (image_id,),
                )
                result = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], result)

    # Settings methods
    async def get_settings(self) -> List[Dict[str, Any]]:
        """Get all settings"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, key, value, created_at, updated_at FROM settings ORDER BY key"
                )
                return cast(List[Dict[str, Any]], await cur.fetchall())

    async def get_settings_dict(self) -> Dict[str, str]:
        """Get all settings as a key-value dictionary"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT key, value FROM settings")
                rows = cast(List[Dict[str, Any]], await cur.fetchall())
                return {row["key"]: row["value"] for row in rows}

    async def get_setting_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a specific setting by key"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, key, value, created_at, updated_at FROM settings WHERE key = %s",
                    (key,),
                )
                result = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], result)

    async def create_or_update_setting(
        self, key: str, value: str
    ) -> Optional[Dict[str, Any]]:
        """Create or update a setting"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Use UPSERT to create or update
                await cur.execute(
                    """
                    INSERT INTO settings (key, value) 
                    VALUES (%s, %s)
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id, key, value, created_at, updated_at
                    """,
                    (key, value),
                )
                result = await cur.fetchone()
                return cast(Optional[Dict[str, Any]], result)

    async def delete_setting(self, key: str) -> bool:
        """Delete a setting by key"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM settings WHERE key = %s", (key,))
                return cur.rowcount > 0

    def broadcast_event(self, event_data: Dict[str, Any]) -> None:
        """
        Broadcast real-time events via Server-Sent Events (SSE) to connected frontend clients.

        This method sends events to the Next.js frontend via HTTP POST to the SSE endpoint.
        The frontend maintains persistent connections and broadcasts these events to all
        connected dashboard clients for real-time updates.

        Args:
            event_data: Dictionary containing event information:
                - type: Event type (e.g., 'image_captured', 'camera_status_changed')
                - Additional fields specific to event type
                - timestamp: ISO formatted timestamp (added automatically if not present)

        Event Types:
            - image_captured: New image was captured for a camera/timelapse
            - camera_status_changed: Camera online/offline status changed
            - timelapse_status_changed: Timelapse started/stopped/paused

        Note:
            This method handles network failures gracefully and logs errors without
            raising exceptions to avoid disrupting database operations.
        """
        try:
            # Send event to Next.js SSE endpoint (POST method for broadcasting)
            sse_url = f"{settings.frontend_url}/api/events"
            response = requests.post(
                sse_url,
                json=event_data,  # Send as JSON
                timeout=5,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                response_data = response.json()
                client_count = response_data.get("clients", 0)
                logger.debug(
                    f"Broadcasted SSE event: {event_data['type']} to {client_count} clients"
                )
            else:
                logger.warning(
                    f"Failed to broadcast SSE event: {response.status_code} - {response.text}"
                )

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to send SSE event to Next.js: {e}")
        except Exception as e:
            logger.error(f"Unexpected error broadcasting SSE event: {e}")

    def notify_image_captured(
        self, camera_id: int, image_count: int, day_number: int
    ) -> None:
        """Notify frontend that a new image was captured"""
        self.broadcast_event(
            {
                "type": "image_captured",
                "data": {
                    "camera_id": camera_id,
                    "image_count": image_count,
                    "day_number": day_number,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    def notify_camera_status_changed(
        self, camera_id: int, status: str, health_status: Optional[str] = None
    ) -> None:
        """Notify frontend that camera status changed"""
        event_data = {
            "type": "camera_status_changed",
            "data": {
                "camera_id": camera_id,
                "status": status,
            },
            "timestamp": datetime.now().isoformat(),
        }

        if health_status:
            event_data["data"]["health_status"] = health_status

        self.broadcast_event(event_data)

    def notify_timelapse_status_changed(
        self, camera_id: int, timelapse_id: int, status: str
    ) -> None:
        """Notify frontend that timelapse status changed"""
        self.broadcast_event(
            {
                "type": "timelapse_status_changed",
                "data": {
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "status": status,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    # Corruption Detection Methods (Async)

    async def get_corruption_settings(self) -> Dict[str, Any]:
        """Get corruption detection settings from database"""
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Fetch corruption settings from key-value pairs
                    await cur.execute(
                        """
                        SELECT key, value 
                        FROM settings 
                        WHERE key IN (
                            'corruption_detection_enabled',
                            'corruption_score_threshold',
                            'corruption_auto_discard_enabled',
                            'corruption_auto_disable_degraded',
                            'corruption_degraded_consecutive_threshold',
                            'corruption_degraded_time_window_minutes',
                            'corruption_degraded_failure_percentage'
                        )
                    """
                    )
                    rows = cast(List[Dict[str, Any]], await cur.fetchall())

                    # Convert to dictionary with proper type conversion
                    settings = {}
                    for row in rows:
                        key = row["key"]
                        value = row["value"]

                        # Convert boolean settings
                        if key in [
                            "corruption_detection_enabled",
                            "corruption_auto_discard_enabled",
                            "corruption_auto_disable_degraded",
                        ]:
                            settings[key] = value.lower() == "true"
                        # Convert integer settings
                        elif key in [
                            "corruption_score_threshold",
                            "corruption_degraded_consecutive_threshold",
                            "corruption_degraded_time_window_minutes",
                            "corruption_degraded_failure_percentage",
                        ]:
                            settings[key] = int(value)
                        else:
                            settings[key] = value

                    # Provide defaults for any missing settings
                    defaults = {
                        "corruption_detection_enabled": True,
                        "corruption_score_threshold": 70,
                        "corruption_auto_discard_enabled": False,
                        "corruption_auto_disable_degraded": False,
                        "corruption_degraded_consecutive_threshold": 10,
                        "corruption_degraded_time_window_minutes": 30,
                        "corruption_degraded_failure_percentage": 50,
                    }

                    for key, default_value in defaults.items():
                        if key not in settings:
                            settings[key] = default_value

                    return settings

        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            return {
                "corruption_detection_enabled": True,
                "corruption_score_threshold": 70,
                "corruption_auto_discard_enabled": False,
                "corruption_auto_disable_degraded": False,
                "corruption_degraded_consecutive_threshold": 10,
                "corruption_degraded_time_window_minutes": 30,
                "corruption_degraded_failure_percentage": 50,
            }

    async def get_camera_corruption_settings(self, camera_id: int) -> Dict[str, Any]:
        """Get per-camera corruption detection settings"""
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT corruption_detection_heavy
                        FROM cameras 
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )
                    result_row = await cur.fetchone()
                    if result_row:
                        return cast(Dict[str, Any], result_row)
                    else:
                        return {"corruption_detection_heavy": False}
        except Exception as e:
            logger.error(
                f"Failed to get camera corruption settings for {camera_id}: {e}"
            )
            return {"corruption_detection_heavy": False}

    async def update_camera_corruption_settings(
        self, camera_id: int, corruption_detection_heavy: bool
    ) -> bool:
        """Update per-camera corruption detection settings"""
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE cameras 
                        SET corruption_detection_heavy = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (corruption_detection_heavy, camera_id),
                    )
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update camera corruption settings: {e}")
            return False

    async def get_corruption_logs(
        self, camera_id: Optional[int] = None, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get corruption detection logs"""
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cur:
                    if camera_id:
                        await cur.execute(
                            """
                            SELECT cl.*, c.name as camera_name
                            FROM corruption_logs cl
                            JOIN cameras c ON cl.camera_id = c.id
                            WHERE cl.camera_id = %s
                            ORDER BY cl.created_at DESC
                            LIMIT %s OFFSET %s
                        """,
                            (camera_id, limit, offset),
                        )
                    else:
                        await cur.execute(
                            """
                            SELECT cl.*, c.name as camera_name
                            FROM corruption_logs cl
                            JOIN cameras c ON cl.camera_id = c.id
                            ORDER BY cl.created_at DESC
                            LIMIT %s OFFSET %s
                        """,
                            (limit, offset),
                        )

                    rows = await cur.fetchall()
                    return [cast(Dict[str, Any], row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get corruption logs: {e}")
            return []

    async def get_corruption_stats(
        self, camera_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get corruption detection statistics"""
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cur:
                    if camera_id:
                        # Camera-specific stats
                        await cur.execute(
                            """
                            SELECT 
                                lifetime_glitch_count,
                                consecutive_corruption_failures,
                                degraded_mode_active,
                                last_degraded_at
                            FROM cameras
                            WHERE id = %s
                        """,
                            (camera_id,),
                        )
                        camera_stats = await cur.fetchone()

                        # Recent average score
                        await cur.execute(
                            """
                            SELECT AVG(corruption_score) as avg_score
                            FROM corruption_logs
                            WHERE camera_id = %s 
                            AND created_at > NOW() - INTERVAL '7 days'
                        """,
                            (camera_id,),
                        )
                        avg_result = await cur.fetchone()

                        if camera_stats:
                            stats = cast(Dict[str, Any], camera_stats)
                            avg_data = cast(Dict[str, Any], avg_result)
                            stats["recent_average_score"] = float(
                                avg_data["avg_score"] or 100.0
                            )
                            return stats

                    else:
                        # System-wide stats
                        await cur.execute(
                            """
                            SELECT 
                                COUNT(*) as total_cameras,
                                COUNT(CASE WHEN degraded_mode_active = false THEN 1 END) as healthy_cameras,
                                COUNT(CASE WHEN degraded_mode_active = true THEN 1 END) as degraded_cameras,
                                AVG(lifetime_glitch_count) as avg_glitch_count
                            FROM cameras
                        """
                        )
                        system_stats = await cur.fetchone()

                        # Today's flagged images
                        await cur.execute(
                            """
                            SELECT COUNT(*) as flagged_today
                            FROM corruption_logs
                            WHERE action_taken IN ('discarded', 'retried_failed')
                            AND created_at > CURRENT_DATE
                        """
                        )
                        today_stats = await cur.fetchone()

                        if system_stats and today_stats:
                            stats = cast(Dict[str, Any], system_stats)
                            today_data = cast(Dict[str, Any], today_stats)
                            stats["images_flagged_today"] = today_data["flagged_today"]
                            return stats

                    return {}
        except Exception as e:
            logger.error(f"Failed to get corruption stats: {e}")
            return {}

    async def reset_camera_degraded_mode(self, camera_id: int) -> bool:
        """Reset a camera's degraded mode status"""
        try:
            loop = asyncio.get_event_loop()

            def _reset_degraded_mode():
                sync_db.set_camera_degraded_mode(camera_id, False)
                return True

            return await loop.run_in_executor(None, _reset_degraded_mode)
        except Exception as e:
            logger.error(f"Error resetting camera {camera_id} degraded mode: {e}")
            return False


# Sync database wrapper for non-async operations
class SyncDatabase:
    """
    Synchronous database interface for worker processes and background tasks.

    This class provides synchronous database operations optimized for worker processes,
    background tasks, and other non-async contexts. It mirrors the functionality of
    AsyncDatabase but uses synchronous psycopg connections.

    Features:
    - Synchronous connection pooling for worker processes
    - Image capture recording with thumbnail management
    - Camera health monitoring and status updates
    - Video generation record management
    - System health statistics and monitoring
    - Real-time event broadcasting to frontend
    - Time window calculation and scheduling

    Attributes:
        _pool: ConnectionPool instance for managing synchronous database connections

    Usage:
        sync_db = SyncDatabase()
        sync_db.initialize()

        # Use in worker processes
        cameras = sync_db.get_running_timelapses()

        # Clean shutdown
        sync_db.close()
    """

    def __init__(self):
        """Initialize the SyncDatabase instance with empty connection pool."""
        self._pool: Optional[ConnectionPool] = None

    def initialize(self):
        """
        Initialize the synchronous connection pool.

        Creates and opens a ConnectionPool with configuration from settings.
        This method must be called before using any database operations.

        Raises:
            Exception: If connection pool initialization fails

        Note:
            This is typically called during worker process startup.
        """
        try:
            self._pool = ConnectionPool(
                settings.database_url,
                min_size=2,
                max_size=settings.db_pool_size,
                max_waiting=settings.db_max_overflow,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            self._pool.open()
            logger.info("Sync database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize sync database pool: {e}")
            raise

    def close(self):
        """Close the connection pool"""
        if self._pool:
            self._pool.close()
            logger.info("Sync database pool closed")

    @contextmanager
    def get_connection(self):
        """Get a sync database connection from the pool"""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        with self._pool.connection() as conn:
            yield conn

    def get_latest_image_for_camera(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest image for a camera using LATERAL join"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        i.*,
                        c.name as camera_name
                    FROM cameras c
                    LEFT JOIN LATERAL (
                        SELECT id, captured_at, file_path, file_size, day_number,
                               thumbnail_path, thumbnail_size, small_path, small_size,
                               camera_id, timelapse_id, created_at, date_directory, file_name
                        FROM images 
                        WHERE camera_id = c.id 
                        ORDER BY captured_at DESC 
                        LIMIT 1
                    ) i ON true
                    WHERE c.id = %s AND i.id IS NOT NULL
                    """,
                    (camera_id,),
                )
                result_row = cur.fetchone()
                return cast(Optional[Dict[str, Any]], result_row)

    def get_running_timelapses(self) -> List[Dict]:
        """Get cameras with running timelapses using active_timelapse_id"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        c.*,
                        t.id as timelapse_id,
                        t.status as timelapse_status,
                        t.name as timelapse_name,
                        t.use_custom_time_window,
                        t.time_window_start as custom_time_window_start,
                        t.time_window_end as custom_time_window_end
                    FROM cameras c 
                    INNER JOIN timelapses t ON c.active_timelapse_id = t.id 
                    WHERE c.status = 'active' AND t.status = 'running'
                    ORDER BY c.id
                """
                )
                return cast(List[Dict[str, Any]], cur.fetchall())

    def record_captured_image(
        self,
        camera_id: int,
        timelapse_id: int,
        file_path: str,
        file_size: int,
        thumbnail_path: Optional[str] = None,
        thumbnail_size: Optional[int] = None,
        small_path: Optional[str] = None,
        small_size: Optional[int] = None,
    ) -> Optional[int]:
        """
        Record a captured image in the database with optional thumbnail and size variant data.

        This method is the primary interface for recording new images captured by
        the worker processes. It handles day number calculation, thumbnail metadata,
        and updates related camera and timelapse statistics.

        Args:
            camera_id: ID of the camera that captured the image
            timelapse_id: ID of the timelapse this image belongs to
            file_path: Full file system path to the captured image
            file_size: Size of the image file in bytes
            thumbnail_path: Optional path to thumbnail image
            thumbnail_size: Optional size of thumbnail file in bytes
            small_path: Optional path to small size variant
            small_size: Optional size of small variant file in bytes

        Returns:
            Optional[int]: ID of the created image record, or None if creation failed

        Side Effects:
            - Increments timelapse image_count
            - Updates timelapse last_capture_at timestamp
            - Updates camera last_capture_at and next_capture_at times
            - Logs image creation details

        Note:
            Day numbers are calculated as 1-based offsets from the timelapse start_date.
            The method assumes 5-minute capture intervals for next_capture_at calculation.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get timelapse start date to calculate day number
                cur.execute(
                    "SELECT start_date FROM timelapses WHERE id = %s", (timelapse_id,)
                )
                timelapse_row = cur.fetchone()
                timelapse_dict = cast(Optional[Dict[str, Any]], timelapse_row)

                if not timelapse_dict or not timelapse_dict.get("start_date"):
                    logger.error(
                        f"Timelapse {timelapse_id} not found or missing start_date"
                    )
                    return None

                # Calculate day number (1-based)
                start_date = timelapse_dict["start_date"]
                current_date = date.today()
                day_number = (current_date - start_date).days + 1

                # Insert image record with thumbnail data
                cur.execute(
                    """
                    INSERT INTO images (camera_id, timelapse_id, file_path, captured_at, day_number, file_size,
                                       thumbnail_path, thumbnail_size, small_path, small_size)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        camera_id,
                        timelapse_id,
                        file_path,
                        day_number,
                        file_size,
                        thumbnail_path,
                        thumbnail_size,
                        small_path,
                        small_size,
                    ),
                )

                image_row = cur.fetchone()
                image_dict = cast(Optional[Dict[str, Any]], image_row)
                if not image_dict:
                    logger.error(
                        f"Failed to retrieve image ID after insert for timelapse {timelapse_id}"
                    )
                    return None
                image_id = cast(int, image_dict["id"])

                # Update timelapse image count and last capture
                cur.execute(
                    """
                    UPDATE timelapses 
                    SET image_count = image_count + 1,
                        last_capture_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """,
                    (timelapse_id,),
                )

                # Update camera with last capture time and next capture time
                # Calculate next capture time (assuming 5-minute intervals for now)
                cur.execute(
                    """
                    UPDATE cameras 
                    SET last_capture_at = CURRENT_TIMESTAMP,
                        next_capture_at = CURRENT_TIMESTAMP + INTERVAL '5 minutes',
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """,
                    (camera_id,),
                )

                logger.info(
                    f"Recorded image {image_id} for timelapse {timelapse_id}, day {day_number}. Updated camera {camera_id} last capture time."
                )

                return image_id

    def update_camera_health(
        self, camera_id: int, health_status: str, capture_success: Optional[bool] = None
    ) -> None:
        """Update camera health status"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if capture_success is not None:
                    if capture_success:
                        cur.execute(
                            """
                            UPDATE cameras 
                            SET health_status = %s, 
                                last_capture_success = %s,
                                consecutive_failures = 0,
                                last_capture_at = CURRENT_TIMESTAMP,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (health_status, capture_success, camera_id),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE cameras 
                            SET health_status = %s, 
                                last_capture_success = %s,
                                consecutive_failures = consecutive_failures + 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (health_status, capture_success, camera_id),
                        )
                else:
                    cur.execute(
                        """
                        UPDATE cameras 
                        SET health_status = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (health_status, camera_id),
                    )

    def create_video_record(
        self, camera_id: int, name: str, settings: dict
    ) -> Optional[int]:
        """Create a new video record"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO videos (camera_id, name, status, settings)
                    VALUES (%s, %s, 'generating', %s)
                    RETURNING id
                """,
                    (camera_id, name, json.dumps(settings)),
                )
                result_row = cur.fetchone()
                result_dict = cast(Optional[Dict[str, Any]], result_row)
                return result_dict["id"] if result_dict else None

    def update_video_record(self, video_id: int, **kwargs):
        """Update video record with provided fields"""
        valid_fields = [
            "name",
            "file_path",
            "status",
            "settings",
            "image_count",
            "file_size",
            "duration_seconds",
            "images_start_date",
            "images_end_date",
            "calculated_fps",
            "target_duration",
            "actual_duration",
            "fps_was_adjusted",
            "adjustment_reason",
        ]

        updates = []
        values = {}

        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = %({field})s")
                if field == "settings" and isinstance(value, dict):
                    values[field] = json.dumps(value)
                else:
                    values[field] = value

        if not updates:
            return

        values["video_id"] = video_id
        updates.append("updated_at = CURRENT_TIMESTAMP")
        query = f"UPDATE videos SET {', '.join(updates)} WHERE id = %(video_id)s"

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)

    def get_timelapse_images(
        self,
        timelapse_id: int,
        day_start: Optional[int] = None,
        day_end: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get images for a timelapse with optional day range filtering"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        i.id,
                        i.camera_id,
                        i.timelapse_id,
                        i.file_path,
                        i.captured_at,
                        i.day_number,
                        i.file_size
                    FROM images i
                    WHERE i.timelapse_id = %s
                """
                params = [timelapse_id]

                # Add day range filtering if specified
                if day_start is not None:
                    query += " AND i.day_number >= %s"
                    params.append(day_start)

                if day_end is not None:
                    query += " AND i.day_number <= %s"
                    params.append(day_end)

                query += " ORDER BY i.captured_at"

                cur.execute(query, params)
                return cast(List[Dict[str, Any]], cur.fetchall())

    def get_timelapse_day_range(self, timelapse_id: int) -> Dict:
        """Get day range and statistics for a timelapse"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        MIN(day_number) as min_day,
                        MAX(day_number) as max_day,
                        COUNT(*) as total_images,
                        COUNT(DISTINCT day_number) as days_with_images
                    FROM images 
                    WHERE timelapse_id = %s
                """,
                    (timelapse_id,),
                )

                row = cur.fetchone()
                result_dict = cast(Optional[Dict[str, Any]], row)
                if result_dict:
                    return {
                        "min_day": result_dict.get("min_day", 0) or 0,
                        "max_day": result_dict.get("max_day", 0) or 0,
                        "total_images": result_dict.get("total_images", 0) or 0,
                        "days_with_images": result_dict.get("days_with_images", 0) or 0,
                    }

                return {
                    "min_day": 0,
                    "max_day": 0,
                    "total_images": 0,
                    "days_with_images": 0,
                }

    def get_active_cameras(self) -> List[Dict]:
        """Get all active cameras (for health checking)"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, rtsp_url, health_status, status
                    FROM cameras 
                    WHERE status = 'active'
                    ORDER BY id
                """
                )
                return cast(List[Dict[str, Any]], cur.fetchall())

    def update_camera_connectivity(self, camera_id: int, is_online: bool) -> None:
        """Update camera connectivity status based on health check"""
        health_status = "online" if is_online else "offline"
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cameras 
                    SET health_status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """,
                    (health_status, camera_id),
                )

    def get_active_timelapse_for_camera(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get active timelapse for a specific camera"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.*, c.name as camera_name
                    FROM timelapses t
                    INNER JOIN cameras c ON t.camera_id = c.id
                    WHERE c.id = %s AND t.status = 'running'
                    """,
                    (camera_id,),
                )
                result_row = cur.fetchone()
                return cast(Optional[Dict[str, Any]], result_row)

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health statistics"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get camera statistics
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total_cameras,
                        COUNT(CASE WHEN health_status = 'online' THEN 1 END) as online_cameras,
                        COUNT(CASE WHEN health_status = 'offline' THEN 1 END) as offline_cameras,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_cameras
                    FROM cameras
                """
                )
                camera_stats_row = cur.fetchone()
                camera_stats = (
                    cast(Dict[str, Any], camera_stats_row) if camera_stats_row else {}
                )

                # Get timelapse statistics
                cur.execute(
                    """
                    SELECT 
                        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_timelapses,
                        COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_timelapses
                    FROM timelapses
                """
                )
                timelapse_stats_row = cur.fetchone()
                timelapse_stats = (
                    cast(Dict[str, Any], timelapse_stats_row)
                    if timelapse_stats_row
                    else {}
                )

                # Get recent captures (last 24 hours)
                cur.execute(
                    """
                    SELECT COUNT(*) as recent_captures
                    FROM images 
                    WHERE captured_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                """
                )
                capture_stats_row = cur.fetchone()
                capture_stats = (
                    cast(Dict[str, Any], capture_stats_row) if capture_stats_row else {}
                )

                # Get total images
                cur.execute("SELECT COUNT(*) as total_images FROM images")
                image_stats_row = cur.fetchone()
                image_stats = (
                    cast(Dict[str, Any], image_stats_row) if image_stats_row else {}
                )

                return {
                    "cameras": {
                        "total_cameras": camera_stats.get("total_cameras", 0),
                        "online_cameras": camera_stats.get("online_cameras", 0),
                        "offline_cameras": camera_stats.get("offline_cameras", 0),
                        "active_cameras": camera_stats.get("active_cameras", 0),
                    },
                    "timelapses": {
                        "running_timelapses": timelapse_stats.get(
                            "running_timelapses", 0
                        ),
                        "paused_timelapses": timelapse_stats.get(
                            "paused_timelapses", 0
                        ),
                    },
                    "captures": {
                        "recent_captures": capture_stats.get("recent_captures", 0),
                    },
                    "images": {
                        "total_images": image_stats.get("total_images", 0),
                    },
                    "status": "healthy",
                }

    def broadcast_event(self, event_data: Dict[str, Any]) -> None:
        """Broadcast event via SSE to connected frontend clients"""
        try:
            # Send event to Next.js SSE endpoint (POST method for broadcasting)
            sse_url = f"{settings.frontend_url}/api/events"
            response = requests.post(
                sse_url,
                json=event_data,  # Send as JSON
                timeout=5,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                response_data = response.json()
                client_count = response_data.get("clients", 0)
                logger.debug(
                    f"Worker broadcasted SSE event: {event_data['type']} to {client_count} clients"
                )
            else:
                logger.warning(
                    f"Worker failed to broadcast SSE event: {response.status_code} - {response.text}"
                )

        except requests.exceptions.RequestException as e:
            logger.warning(f"Worker failed to send SSE event to Next.js: {e}")
        except Exception as e:
            logger.error(f"Worker unexpected error broadcasting SSE event: {e}")

    def notify_image_captured(
        self, camera_id: int, image_count: int, day_number: int
    ) -> None:
        """Notify frontend that a new image was captured"""
        self.broadcast_event(
            {
                "type": "image_captured",
                "data": {
                    "camera_id": camera_id,
                    "image_count": image_count,
                    "day_number": day_number,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    def notify_camera_status_changed(
        self, camera_id: int, status: str, health_status: Optional[str] = None
    ) -> None:
        """Notify frontend that camera status changed"""
        event_data = {
            "type": "camera_status_changed",
            "data": {
                "camera_id": camera_id,
                "status": status,
            },
            "timestamp": datetime.now().isoformat(),
        }

        if health_status:
            event_data["data"]["health_status"] = health_status

        self.broadcast_event(event_data)

    def update_next_capture_time(self, camera_id: int, next_capture_at: str) -> bool:
        """Update the next_capture_at field for a camera"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cameras 
                        SET next_capture_at = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (next_capture_at, camera_id),
                    )

                    if cur.rowcount > 0:
                        logger.debug(
                            f"Updated next_capture_at for camera {camera_id}: {next_capture_at}"
                        )
                        return True
                    else:
                        logger.warning(
                            f"No camera found with ID {camera_id} for next_capture_at update"
                        )
                        return False

        except Exception as e:
            logger.error(
                f"Failed to update next_capture_at for camera {camera_id}: {e}"
            )
            return False

    def calculate_and_update_next_capture(
        self, camera_id: int, capture_interval: int
    ) -> bool:
        """Calculate and update next capture time based on time windows and interval"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get camera settings
                    cur.execute(
                        """
                        SELECT use_time_window, time_window_start, time_window_end
                        FROM cameras WHERE id = %s
                    """,
                        (camera_id,),
                    )
                    camera_settings_row = cur.fetchone()

                    if not camera_settings_row:
                        logger.error(
                            f"Camera {camera_id} not found for next capture calculation"
                        )
                        return False

                    # Cast to dictionary for type checking
                    camera_settings = cast(Dict[str, Any], camera_settings_row)

                    from datetime import datetime, timedelta

                    # Calculate base next capture time (now + interval)
                    now = datetime.now(timezone.utc)
                    next_capture = now + timedelta(seconds=capture_interval)

                    # Adjust for time window if enabled
                    if (
                        camera_settings["use_time_window"]
                        and camera_settings["time_window_start"]
                    ):
                        try:
                            start_time_str = camera_settings["time_window_start"]
                            end_time_str = camera_settings["time_window_end"]

                            # Parse time window
                            start_time = datetime.strptime(
                                start_time_str, "%H:%M:%S"
                            ).time()
                            end_time = datetime.strptime(
                                end_time_str, "%H:%M:%S"
                            ).time()

                            # Check if next capture is within window
                            next_capture_time = next_capture.time()

                            # Handle overnight windows
                            if start_time <= end_time:
                                # Normal window (e.g., 06:00 - 18:00)
                                in_window = start_time <= next_capture_time <= end_time
                            else:
                                # Overnight window (e.g., 22:00 - 06:00)
                                in_window = (
                                    next_capture_time >= start_time
                                    or next_capture_time <= end_time
                                )

                            # If outside window, move to next window start
                            if not in_window:
                                # Find next window start
                                window_start = next_capture.replace(
                                    hour=start_time.hour,
                                    minute=start_time.minute,
                                    second=start_time.second,
                                    microsecond=0,
                                )

                                # If start time is in the past, move to tomorrow
                                if window_start <= now:
                                    window_start += timedelta(days=1)

                                next_capture = window_start

                        except Exception as e:
                            logger.warning(
                                f"Error parsing time window for camera {camera_id}: {e}"
                            )
                            # Continue with original next_capture time

                    # Update database - remove timezone info for PostgreSQL timestamp without time zone
                    next_capture_iso = next_capture.replace(tzinfo=None).isoformat()
                    return self.update_next_capture_time(camera_id, next_capture_iso)

        except Exception as e:
            logger.error(
                f"Failed to calculate next capture for camera {camera_id}: {e}"
            )
            return False

    def get_capture_interval_setting(self) -> int:
        """Get the capture interval from settings"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT value FROM settings WHERE key = 'capture_interval'
                    """
                    )
                    result_row = cur.fetchone()
                    if result_row:
                        result = cast(Dict[str, Any], result_row)
                        return int(result["value"])
                    return 300  # Default 5 minutes
        except Exception as e:
            logger.error(f"Failed to get capture interval setting: {e}")
            return 300

    # Corruption Detection Methods (Sync)

    def get_corruption_settings(self) -> Dict[str, Any]:
        """Get corruption detection settings from database (sync version)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 
                            corruption_detection_enabled,
                            corruption_score_threshold,
                            corruption_auto_discard_enabled,
                            corruption_auto_disable_degraded,
                            corruption_degraded_consecutive_threshold,
                            corruption_degraded_time_window_minutes,
                            corruption_degraded_failure_percentage
                        FROM settings 
                        LIMIT 1
                    """
                    )
                    result_row = cur.fetchone()
                    if result_row:
                        return cast(Dict[str, Any], result_row)
                    else:
                        # Return defaults if no settings found
                        return {
                            "corruption_detection_enabled": True,
                            "corruption_score_threshold": 70,
                            "corruption_auto_discard_enabled": False,
                            "corruption_auto_disable_degraded": False,
                            "corruption_degraded_consecutive_threshold": 10,
                            "corruption_degraded_time_window_minutes": 30,
                            "corruption_degraded_failure_percentage": 50,
                        }
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            return {
                "corruption_detection_enabled": True,
                "corruption_score_threshold": 70,
                "corruption_auto_discard_enabled": False,
                "corruption_auto_disable_degraded": False,
                "corruption_degraded_consecutive_threshold": 10,
                "corruption_degraded_time_window_minutes": 30,
                "corruption_degraded_failure_percentage": 50,
            }

    def get_camera_corruption_settings(self, camera_id: int) -> Dict[str, Any]:
        """Get per-camera corruption detection settings (sync version)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT corruption_detection_heavy
                        FROM cameras 
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )
                    result_row = cur.fetchone()
                    if result_row:
                        return cast(Dict[str, Any], result_row)
                    else:
                        return {"corruption_detection_heavy": False}
        except Exception as e:
            logger.error(
                f"Failed to get camera corruption settings for {camera_id}: {e}"
            )
            return {"corruption_detection_heavy": False}

    def log_corruption_result(self, camera_id: int, result) -> Optional[int]:
        """Log corruption detection result to database"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO corruption_logs 
                        (camera_id, corruption_score, fast_score, heavy_score, 
                         detection_details, action_taken, processing_time_ms)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """,
                        (
                            camera_id,
                            result.score,
                            result.corruption_score.fast_score,
                            result.corruption_score.heavy_score,
                            json.dumps(result.corruption_score.details),
                            result.action_taken,
                            result.corruption_score.details.get(
                                "total_processing_time_ms"
                            ),
                        ),
                    )

                    result_row = cur.fetchone()
                    result_dict = cast(Optional[Dict[str, Any]], result_row)
                    return result_dict["id"] if result_dict else None

        except Exception as e:
            logger.error(f"Failed to log corruption result: {e}")
            return None

    def update_camera_corruption_failure_count(self, camera_id: int, is_success: bool):
        """Update camera corruption failure count and lifetime glitch count"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if is_success:
                        # Reset consecutive failures on success
                        cur.execute(
                            """
                            UPDATE cameras 
                            SET consecutive_corruption_failures = 0,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (camera_id,),
                        )
                    else:
                        # Increment both consecutive and lifetime counts on failure
                        cur.execute(
                            """
                            UPDATE cameras 
                            SET consecutive_corruption_failures = consecutive_corruption_failures + 1,
                                lifetime_glitch_count = lifetime_glitch_count + 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (camera_id,),
                        )

        except Exception as e:
            logger.error(
                f"Failed to update corruption failure count for camera {camera_id}: {e}"
            )

    def get_camera_corruption_failure_stats(self, camera_id: int) -> Dict[str, Any]:
        """Get corruption failure statistics for a camera"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 
                            consecutive_corruption_failures,
                            lifetime_glitch_count,
                            degraded_mode_active,
                            last_degraded_at
                        FROM cameras
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )
                    result_row = cur.fetchone()
                    if result_row:
                        return cast(Dict[str, Any], result_row)
                    else:
                        return {
                            "consecutive_corruption_failures": 0,
                            "lifetime_glitch_count": 0,
                            "degraded_mode_active": False,
                            "last_degraded_at": None,
                        }
        except Exception as e:
            logger.error(
                f"Failed to get corruption failure stats for camera {camera_id}: {e}"
            )
            return {
                "consecutive_corruption_failures": 0,
                "lifetime_glitch_count": 0,
                "degraded_mode_active": False,
                "last_degraded_at": None,
            }

    def set_camera_degraded_mode(
        self, camera_id: int, is_degraded: bool, auto_disable: bool = False
    ):
        """Set camera degraded mode status and optionally disable camera"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if is_degraded:
                        # Entering degraded mode
                        if auto_disable:
                            # Auto-disable camera
                            cur.execute(
                                """
                                UPDATE cameras 
                                SET degraded_mode_active = %s,
                                    last_degraded_at = CURRENT_TIMESTAMP,
                                    status = 'inactive',
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """,
                                (is_degraded, camera_id),
                            )
                            logger.warning(
                                f"Camera {camera_id} auto-disabled due to persistent corruption"
                            )
                        else:
                            # Just mark as degraded
                            cur.execute(
                                """
                                UPDATE cameras 
                                SET degraded_mode_active = %s,
                                    last_degraded_at = CURRENT_TIMESTAMP,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """,
                                (is_degraded, camera_id),
                            )
                    else:
                        # Exiting degraded mode (recovery)
                        cur.execute(
                            """
                            UPDATE cameras 
                            SET degraded_mode_active = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (is_degraded, camera_id),
                        )

        except Exception as e:
            logger.error(f"Failed to set degraded mode for camera {camera_id}: {e}")

    def get_corruption_failures_since(
        self, camera_id: int, cutoff_time: datetime
    ) -> int:
        """Get number of corruption failures since the cutoff time"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) as failure_count
                        FROM corruption_logs
                        WHERE camera_id = %s 
                        AND action_taken IN ('discarded', 'retried_failed')
                        AND created_at > %s
                    """,
                        (camera_id, cutoff_time),
                    )
                    result_row = cur.fetchone()
                    if result_row:
                        result = cast(Dict[str, Any], result_row)
                        return result["failure_count"]
                    return 0
        except Exception as e:
            logger.error(
                f"Failed to get corruption failures since {cutoff_time} for camera {camera_id}: {e}"
            )
            return 0

    def get_recent_corruption_failure_rate(
        self, camera_id: int, capture_count: int
    ) -> float:
        """Get failure rate over the last N corruption evaluations (0.0 to 1.0)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get last N corruption logs for this camera
                    cur.execute(
                        """
                        SELECT action_taken
                        FROM corruption_logs
                        WHERE camera_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """,
                        (camera_id, capture_count),
                    )
                    results = cur.fetchall()

                    if not results:
                        return 0.0

                    total_evaluations = len(results)
                    failed_evaluations = sum(
                        1
                        for row in results
                        if cast(Dict[str, Any], row)["action_taken"]
                        in ["discarded", "retried_failed"]
                    )

                    return failed_evaluations / total_evaluations

        except Exception as e:
            logger.error(
                f"Failed to get recent failure rate for camera {camera_id}: {e}"
            )
            return 0.0

    def reset_camera_corruption_failures(self, camera_id: int):
        """Reset camera corruption failure counts (for manual recovery)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cameras 
                        SET consecutive_corruption_failures = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )

        except Exception as e:
            logger.error(
                f"Failed to reset corruption failures for camera {camera_id}: {e}"
            )

    def broadcast_corruption_event(
        self,
        camera_id: int,
        corruption_score: int,
        is_corrupted: bool,
        action_taken: str,
        failed_checks: list,
        processing_time_ms: int,
    ) -> None:
        """Broadcast corruption detection event via SSE"""
        self.broadcast_event(
            {
                "type": "image_corruption_detected",
                "data": {
                    "camera_id": camera_id,
                    "corruption_score": corruption_score,
                    "is_corrupted": is_corrupted,
                    "action_taken": action_taken,
                    "failed_checks": failed_checks,
                    "processing_time_ms": processing_time_ms,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    # Weather Methods (Sync)

    def get_settings_dict(self) -> Dict[str, str]:
        """Get all settings as a key-value dictionary"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM settings")
                rows = cast(List[Dict[str, Any]], cur.fetchall())
                return {row["key"]: row["value"] for row in rows}

    def create_or_update_setting(self, key: str, value: str) -> Optional[Dict[str, Any]]:
        """Create or update a setting"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Use UPSERT to create or update
                cur.execute(
                    """
                    INSERT INTO settings (key, value) 
                    VALUES (%s, %s)
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id, key, value, created_at, updated_at
                    """,
                    (key, value),
                )
                result = cur.fetchone()
                return cast(Optional[Dict[str, Any]], result)


# Global Database Instances
# These pre-configured instances are used throughout the application

async_db = AsyncDatabase()
"""
Global AsyncDatabase instance for FastAPI endpoints.

This instance should be initialized during FastAPI application startup
and used for all async database operations in API endpoints.

Usage:
    # In FastAPI startup
    await async_db.initialize()
    
    # In endpoints  
    cameras = await async_db.get_cameras()
    
    # In shutdown
    await async_db.close()
"""

sync_db = SyncDatabase()
"""
Global SyncDatabase instance for worker processes and background tasks.

This instance should be initialized during worker startup and used
for all synchronous database operations in background processes.

Usage:
    # In worker startup
    sync_db.initialize()
    
    # In worker processes
    timelapses = sync_db.get_running_timelapses()
    
    # In shutdown
    sync_db.close()
"""
