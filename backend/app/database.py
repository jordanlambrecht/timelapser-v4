# backend/app/database.py
import asyncio
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from datetime import datetime, date
from typing import List, Dict, Optional, Any, cast
from loguru import logger
import json
import requests
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
                open=False,
            )
            await self._pool.open()
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
                return cast(List[Dict[str, Any]], await cur.fetchall())

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
                                       consecutive_failures)
                    VALUES (%(name)s, %(rtsp_url)s, %(status)s, %(time_window_start)s,
                           %(time_window_end)s, %(use_time_window)s, 'unknown', 0)
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
        """Get all cameras with their latest image details using LATERAL join"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        c.*,
                        t.status as timelapse_status,
                        t.id as timelapse_id,
                        i.id as last_image_id,
                        i.captured_at as last_image_captured_at,
                        i.file_path as last_image_file_path,
                        i.file_size as last_image_file_size,
                        i.day_number as last_image_day_number
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.id = t.camera_id 
                    LEFT JOIN LATERAL (
                        SELECT id, captured_at, file_path, file_size, day_number
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
        """Get a specific camera with its latest image details using LATERAL join"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        c.*,
                        t.status as timelapse_status,
                        t.id as timelapse_id,
                        i.id as last_image_id,
                        i.captured_at as last_image_captured_at,
                        i.file_path as last_image_file_path,
                        i.file_size as last_image_file_size,
                        i.day_number as last_image_day_number
                    FROM cameras c 
                    LEFT JOIN timelapses t ON c.id = t.camera_id 
                    LEFT JOIN LATERAL (
                        SELECT id, captured_at, file_path, file_size, day_number
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
                existing_row = await cur.fetchone()
                existing_dict = cast(Optional[Dict[str, Any]], existing_row)
                timelapse_id: Optional[int] = None

                if existing_dict:
                    timelapse_id = cast(int, existing_dict["id"])
                    # If changing from stopped/paused to running, update start_date
                    if existing_dict["status"] != "running" and status == "running":
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
                    result_row_new = await cur.fetchone()
                    result_dict_new = cast(Optional[Dict[str, Any]], result_row_new)
                    timelapse_id = result_dict_new["id"] if result_dict_new else None

                return timelapse_id

    # Duplicate method removed - using the first one at line 148

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
                        SELECT *
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
                client_count = response_data.get('clients', 0)
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
                "camera_id": camera_id,
                "image_count": image_count,
                "day_number": day_number,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def notify_camera_status_changed(
        self, camera_id: int, status: str, health_status: Optional[str] = None
    ) -> None:
        """Notify frontend that camera status changed"""
        event_data = {
            "type": "camera_status_changed",
            "camera_id": camera_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if health_status:
            event_data["health_status"] = health_status

        self.broadcast_event(event_data)

    def notify_timelapse_status_changed(
        self, camera_id: int, timelapse_id: int, status: str
    ) -> None:
        """Notify frontend that timelapse status changed"""
        self.broadcast_event(
            {
                "type": "timelapse_status_changed",
                "camera_id": camera_id,
                "timelapse_id": timelapse_id,
                "status": status,
                "timestamp": datetime.now().isoformat(),
            }
        )


# Sync database wrapper for non-async operations
class SyncDatabase:
    """Synchronous database interface for worker processes"""

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None

    def initialize(self):
        """Initialize the sync connection pool"""
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
                        SELECT *
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
                return cast(List[Dict[str, Any]], cur.fetchall())

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

                # Insert image record
                cur.execute(
                    """
                    INSERT INTO images (camera_id, timelapse_id, file_path, captured_at, day_number, file_size)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                    RETURNING id
                """,
                    (camera_id, timelapse_id, file_path, day_number, file_size),
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
                camera_stats = cast(Dict[str, Any], camera_stats_row) if camera_stats_row else {}

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
                timelapse_stats = cast(Dict[str, Any], timelapse_stats_row) if timelapse_stats_row else {}

                # Get recent captures (last 24 hours)
                cur.execute(
                    """
                    SELECT COUNT(*) as recent_captures
                    FROM images 
                    WHERE captured_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                """
                )
                capture_stats_row = cur.fetchone()
                capture_stats = cast(Dict[str, Any], capture_stats_row) if capture_stats_row else {}

                # Get total images
                cur.execute("SELECT COUNT(*) as total_images FROM images")
                image_stats_row = cur.fetchone()
                image_stats = cast(Dict[str, Any], image_stats_row) if image_stats_row else {}

                return {
                    "cameras": {
                        "total_cameras": camera_stats.get("total_cameras", 0),
                        "online_cameras": camera_stats.get("online_cameras", 0),
                        "offline_cameras": camera_stats.get("offline_cameras", 0),
                        "active_cameras": camera_stats.get("active_cameras", 0),
                    },
                    "timelapses": {
                        "running_timelapses": timelapse_stats.get("running_timelapses", 0),
                        "paused_timelapses": timelapse_stats.get("paused_timelapses", 0),
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
                client_count = response_data.get('clients', 0)
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
                "camera_id": camera_id,
                "image_count": image_count,
                "day_number": day_number,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def notify_camera_status_changed(
        self, camera_id: int, status: str, health_status: Optional[str] = None
    ) -> None:
        """Notify frontend that camera status changed"""
        event_data = {
            "type": "camera_status_changed",
            "camera_id": camera_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if health_status:
            event_data["health_status"] = health_status

        self.broadcast_event(event_data)


# Global instances
async_db = AsyncDatabase()
sync_db = SyncDatabase()
