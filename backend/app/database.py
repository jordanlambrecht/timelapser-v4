import asyncio
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from loguru import logger
import json
from contextlib import asynccontextmanager, contextmanager

from .config import settings


class AsyncDatabase:
    """Async database interface for FastAPI"""

    def __init__(self):
        self._pool: Optional[AsyncConnectionPool] = None

    async def initialize(self):
        """Initialize the async connection pool"""
        try:
            self._pool = AsyncConnectionPool(
                settings.database_url,
                min_size=2,
                max_size=settings.db_pool_size,
                max_waiting=settings.db_max_overflow,
                kwargs={"row_factory": dict_row},
            )
            await self._pool.wait()
            logger.info("Async database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize async database pool: {e}")
            raise

    async def close(self):
        """Close the connection pool"""
        if self._pool:
            await self._pool.close()
            logger.info("Async database pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get an async database connection from the pool"""
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
        """Get all cameras"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT c.*, t.status as timelapse_status, t.id as timelapse_id
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.id = t.camera_id 
                    ORDER BY c.id
                """
                )
                return await cur.fetchall()

    async def get_camera_by_id(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific camera by ID"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT c.*, t.status as timelapse_status, t.id as timelapse_id
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.id = t.camera_id 
                    WHERE c.id = %s
                """,
                    (camera_id,),
                )
                return await cur.fetchone()

    async def create_camera(self, camera_data: Dict[str, Any]) -> Optional[int]:
        """Create a new camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO cameras (name, rtsp_url, status, time_window_start, 
                                       time_window_end, use_time_window, health_status,
                                       consecutive_failures)
                    VALUES (%(name)s, %(rtsp_url)s, %(status)s, %(time_window_start)s,
                           %(time_window_end)s, %(use_time_window)s, 'unknown', 0)
                    RETURNING id
                """,
                    camera_data,
                )
                result = await cur.fetchone()
                return result["id"] if result else None

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
                return await cur.fetchall()

    async def create_or_update_timelapse(
        self, camera_id: int, status: str
    ) -> Optional[int]:
        """Create or update timelapse for camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                # Check if timelapse exists
                await cur.execute(
                    "SELECT id, status FROM timelapses WHERE camera_id = %s",
                    (camera_id,),
                )
                existing = await cur.fetchone()

                if existing:
                    timelapse_id = existing["id"]
                    # If changing from stopped/paused to running, update start_date
                    if existing["status"] != "running" and status == "running":
                        await cur.execute(
                            """
                            UPDATE timelapses 
                            SET status = %s, start_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (status, timelapse_id),
                        )
                    else:
                        await cur.execute(
                            """
                            UPDATE timelapses 
                            SET status = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (status, timelapse_id),
                        )
                else:
                    # Create new timelapse
                    await cur.execute(
                        """
                        INSERT INTO timelapses (camera_id, status, start_date)
                        VALUES (%s, %s, CURRENT_DATE)
                        RETURNING id
                    """,
                        (camera_id, status),
                    )
                    result = await cur.fetchone()
                    timelapse_id = result["id"] if result else None

                return timelapse_id

    # Video methods
    async def get_videos(self, camera_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get videos, optionally filtered by camera"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                if camera_id:
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
                else:
                    await cur.execute(
                        """
                        SELECT v.*, c.name as camera_name 
                        FROM videos v
                        JOIN cameras c ON v.camera_id = c.id
                        ORDER BY v.created_at DESC
                    """
                    )
                return await cur.fetchall()

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
                return await cur.fetchone()

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
                result = await cur.fetchone()
                return result["id"] if result else None

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


class SyncDatabase:
    """Sync database interface for worker processes"""

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None

    def initialize(self):
        """Initialize the sync connection pool"""
        try:
            self._pool = ConnectionPool(
                settings.database_url,
                min_size=1,
                max_size=5,
                kwargs={"row_factory": dict_row},
            )
            self._pool.wait()
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
            try:
                yield conn
            except Exception as e:
                conn.rollback()
                logger.error(f"Database error: {e}")
                raise

    # Add sync versions of commonly used methods for the worker
    def get_running_timelapses(self) -> List[Dict]:
        """Get cameras with running timelapses"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.*, t.status as timelapse_status, t.id as timelapse_id
                    FROM cameras c 
                    INNER JOIN timelapses t ON c.id = t.camera_id 
                    WHERE c.status = 'active' AND t.status = 'running'
                    ORDER BY c.id
                """
                )
                return cur.fetchall()

    def record_captured_image(
        self, camera_id: int, timelapse_id: int, file_path: str, file_size: int
    ) -> Optional[int]:
        """Record a captured image in the database"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get timelapse start date to calculate day number
                cur.execute(
                    "SELECT start_date FROM timelapses WHERE id = %s", (timelapse_id,)
                )
                timelapse = cur.fetchone()

                if not timelapse or not timelapse["start_date"]:
                    logger.error(
                        f"Timelapse {timelapse_id} not found or missing start_date"
                    )
                    return None

                # Calculate day number (1-based)
                start_date = timelapse["start_date"]
                current_date = date.today()
                day_number = (current_date - start_date).days + 1

                # Insert image record
                cur.execute(
                    """
                    INSERT INTO images (camera_id, timelapse_id, file_path, captured_at, day_number, file_size)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                    RETURNING id
                """,
                    (camera_id, timelapse_id, file_path, day_number, file_size),
                )

                image_id = cur.fetchone()["id"]

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

                conn.commit()
                return image_id

    def update_camera_health(self, camera_id: int, success: bool):
        """Update camera capture success status (separate from connectivity)"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if success:
                    # Capture was successful
                    cur.execute(
                        """
                        UPDATE cameras 
                        SET last_capture_at = CURRENT_TIMESTAMP,
                            last_capture_success = true,
                            consecutive_failures = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )
                else:
                    # Capture failed
                    cur.execute(
                        """
                        UPDATE cameras 
                        SET last_capture_success = false,
                            consecutive_failures = consecutive_failures + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )

                conn.commit()

    def update_camera_connectivity(self, camera_id: int, is_online: bool):
        """Update camera health status based on RTSP connectivity test"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                new_status = "online" if is_online else "offline"

                cur.execute(
                    """
                    UPDATE cameras 
                    SET health_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """,
                    (new_status, camera_id),
                )

                conn.commit()

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
                return cur.fetchall()

    def get_active_timelapse_for_camera(self, camera_id: int) -> Optional[Dict]:
        """Get the active (running) timelapse for a camera"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM timelapses 
                    WHERE camera_id = %s AND status = 'running'
                    ORDER BY created_at DESC 
                    LIMIT 1
                """,
                    (camera_id,),
                )
                return cur.fetchone()

    def get_offline_cameras(self) -> List[Dict]:
        """Get cameras that are currently offline"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, health_status, last_capture_at, consecutive_failures
                    FROM cameras 
                    WHERE status = 'active' AND health_status = 'offline'
                    ORDER BY last_capture_at DESC NULLS LAST
                """
                )
                return cur.fetchall()

    def update_camera_last_image(self, camera_id: int, image_path: str):
        """Update camera's last image path for UI display"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cameras 
                    SET last_image_path = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """,
                    (image_path, camera_id),
                )
                conn.commit()


# Global instances
async_db = AsyncDatabase()
sync_db = SyncDatabase()
