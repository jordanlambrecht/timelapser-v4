# backend/app/database/corruption_operations.py
"""
Corruption detection database operations module - Composition Pattern.

This module handles all corruption-related database operations including:
- Corruption detection logging
- Corruption statistics
- Degraded mode management
- Corruption settings
"""

from typing import List, Optional, Dict, Any
from ..models.corruption_model import CorruptionLogsPage

from loguru import logger

from .core import AsyncDatabase, SyncDatabase
from ..constants import (
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
    DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
    DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES,
    DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE,
    DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
    DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
    MIN_CORRUPTION_ANALYSIS_SAMPLE_SIZE,
)
from ..models.corruption_model import (
    CorruptionLogEntry,
    CorruptionStats,
    CameraWithCorruption,
    CorruptionAnalysisStats,
)


def _process_corruption_settings_rows(
    settings_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Shared helper to process settings rows from database into a settings dictionary.

    Eliminates duplicate logic between async and sync get_corruption_settings methods.
    Handles type conversion for boolean and numeric strings.

    Args:
        settings_rows: List of database rows with 'key' and 'value' columns

    Returns:
        Dictionary with processed settings
    """
    settings = {}

    for row in settings_rows:
        key = row["key"]
        value = row["value"]

        # Convert boolean strings to actual booleans
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        # Convert numeric strings to numbers
        elif value.isdigit():
            value = int(value)

        settings[key] = value

    return settings


class CorruptionOperations:
    """Corruption database operations using composition pattern (async only)."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db

    def _row_to_corruption_log(self, row: Dict[str, Any]) -> CorruptionLogEntry:
        """Convert database row to CorruptionLogEntry model."""
        # Filter fields that belong to CorruptionLogEntry model
        log_fields = {
            k: v for k, v in row.items() if k in CorruptionLogEntry.model_fields
        }
        return CorruptionLogEntry(**log_fields)

    def _row_to_corruption_stats(self, row: Dict[str, Any]) -> CorruptionStats:
        """Convert database row to CorruptionStats model."""
        # Filter fields that belong to CorruptionStats model
        stats_fields = {
            k: v for k, v in row.items() if k in CorruptionStats.model_fields
        }
        return CorruptionStats(**stats_fields)

    def _row_to_camera_with_corruption(
        self, row: Dict[str, Any]
    ) -> CameraWithCorruption:
        """Convert database row to CameraWithCorruption model."""
        # Filter fields that belong to CameraWithCorruption model
        camera_fields = {
            k: v for k, v in row.items() if k in CameraWithCorruption.model_fields
        }
        return CameraWithCorruption(**camera_fields)

    async def get_corruption_logs(
        self,
        camera_id: Optional[int] = None,
        timelapse_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
    ) -> CorruptionLogsPage:
        """
        Retrieve corruption detection logs with filtering and pagination.

        Args:
            camera_id: Optional camera ID to filter by
            timelapse_id: Optional timelapse ID to filter by
            page: Page number (1-based)
            page_size: Number of logs per page
            min_score: Optional minimum corruption score filter
            max_score: Optional maximum corruption score filter

        Returns:
            CorruptionLogsPage: Pydantic model containing logs and pagination metadata
        """

        offset = (page - 1) * page_size

        # Build WHERE clause based on filters
        where_conditions = []
        params = []

        if camera_id:
            where_conditions.append("cl.camera_id = %s")
            params.append(camera_id)

        if timelapse_id:
            where_conditions.append(
                "cl.image_id IN (SELECT id FROM images WHERE timelapse_id = %s)"
            )
            params.append(timelapse_id)

        if min_score is not None:
            where_conditions.append("cl.corruption_score >= %s")
            params.append(min_score)

        if max_score is not None:
            where_conditions.append("cl.corruption_score <= %s")
            params.append(max_score)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get total count
                count_query = f"""
                SELECT COUNT(*) as total_count
                FROM corruption_logs cl
                WHERE {where_clause}
                """

                await cur.execute(count_query, params)
                count_results = await cur.fetchall()
                total_count = count_results[0]["total_count"] if count_results else 0

                # Get logs with pagination
                logs_query = f"""
                SELECT
                    cl.*,
                    c.name as camera_name,
                    i.file_path as image_path
                FROM corruption_logs cl
                JOIN cameras c ON cl.camera_id = c.id
                LEFT JOIN images i ON cl.image_id = i.id
                WHERE {where_clause}
                ORDER BY cl.created_at DESC
                LIMIT %s OFFSET %s
                """

                logs_params = params + [page_size, offset]
                await cur.execute(logs_query, logs_params)
                results = await cur.fetchall()
                logs = [self._row_to_corruption_log(row) for row in results]

                total_pages = (total_count + page_size - 1) // page_size

                return CorruptionLogsPage(
                    logs=logs,
                    total_count=total_count,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages,
                )

    async def get_corruption_stats(
        self, camera_id: Optional[int] = None
    ) -> CorruptionAnalysisStats:
        """
        Get corruption detection statistics.

        Args:
            camera_id: Optional camera ID to filter by

        Returns:
            Dictionary containing corruption statistics
        """
        where_clause = "WHERE cl.camera_id = %s" if camera_id else ""
        params = (camera_id,) if camera_id else ()

        query = f"""
        SELECT
            COUNT(*) as total_detections,
            COUNT(CASE WHEN cl.action_taken = 'saved' THEN 1 END) as images_saved,
            COUNT(CASE WHEN cl.action_taken = 'discarded' THEN 1 END) as images_discarded,
            COUNT(CASE WHEN cl.action_taken = 'retried' THEN 1 END) as images_retried,
            AVG(cl.corruption_score) as avg_corruption_score,
            MIN(cl.corruption_score) as min_corruption_score,
            MAX(cl.corruption_score) as max_corruption_score,
            AVG(cl.processing_time_ms) as avg_processing_time_ms,
            COUNT(CASE WHEN cl.corruption_score < {DEFAULT_CORRUPTION_DISCARD_THRESHOLD} THEN 1 END) as low_quality_count,
            COUNT(CASE WHEN cl.created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as detections_last_24h,
            MAX(cl.created_at) as most_recent_detection
        FROM corruption_logs cl
        {where_clause}
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()

                if results:
                    row = results[0]
                    return CorruptionAnalysisStats(
                        total_detections=row["total_detections"],
                        images_saved=row["images_saved"],
                        images_discarded=row["images_discarded"],
                        images_retried=row["images_retried"],
                        avg_corruption_score=float(
                            row["avg_corruption_score"] or 100.0
                        ),
                        min_corruption_score=int(row["min_corruption_score"] or 100),
                        max_corruption_score=int(row["max_corruption_score"] or 100),
                        avg_processing_time_ms=float(
                            row["avg_processing_time_ms"] or 0.0
                        ),
                        most_recent_detection=row["most_recent_detection"],
                    )
                else:
                    return CorruptionAnalysisStats(
                        total_detections=0,
                        images_saved=0,
                        images_discarded=0,
                        images_retried=0,
                        avg_corruption_score=100.0,
                        min_corruption_score=100,
                        max_corruption_score=100,
                        avg_processing_time_ms=0.0,
                        unique_cameras=0,
                        most_recent_detection=None,
                    )

    async def get_camera_corruption_history(
        self, camera_id: int, hours: int = 24
    ) -> List[CorruptionLogEntry]:
        """
        Get corruption detection history for a camera over a time period.

        Args:
            camera_id: ID of the camera
            hours: Number of hours of history to retrieve

        Returns:
            List of CorruptionLogEntry models
        """
        query = """
        SELECT
            *
        FROM corruption_logs
        WHERE camera_id = %s
        AND created_at > NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id, hours))
                results = await cur.fetchall()
                return [self._row_to_corruption_log(row) for row in results]

    async def get_degraded_cameras(self) -> List[CameraWithCorruption]:
        """
        Get all cameras currently in degraded mode.

        Returns:
            List of CameraWithCorruption models
        """
        query = """
        SELECT
            c.*,
            COUNT(cl.id) as recent_failures
        FROM cameras c
        LEFT JOIN corruption_logs cl ON c.id = cl.camera_id
            AND cl.created_at > NOW() - INTERVAL '1 hour'
            AND cl.action_taken = 'discarded'
        WHERE c.degraded_mode_active = true
        GROUP BY c.id
        ORDER BY c.last_degraded_at DESC
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                results = await cur.fetchall()
                return [self._row_to_camera_with_corruption(row) for row in results]

    async def reset_camera_degraded_mode(self, camera_id: int) -> bool:
        """
        Reset degraded mode for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful
        """
        query = """
        UPDATE cameras
        SET degraded_mode_active = false,
            consecutive_corruption_failures = 0,
            updated_at = NOW()
        WHERE id = %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    async def get_corruption_settings(self) -> Dict[str, Any]:
        """Get global corruption detection settings from settings table (async version)."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT key, value 
                    FROM settings 
                    WHERE key LIKE 'corruption_%'
                    """
                )
                settings_rows = await cur.fetchall()

                # Use shared helper for processing
                return _process_corruption_settings_rows(settings_rows)

    async def update_corruption_settings(self, settings: Dict[str, Any]) -> None:
        """Update global corruption detection settings (async version)."""
        if not settings:
            return

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                for key, value in settings.items():
                    # Convert setting name to database key format
                    db_key = f"corruption_{key}"
                    await cur.execute(
                        """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                        """,
                        (db_key, str(value)),
                    )

    async def get_camera_corruption_settings(self, camera_id: int) -> Dict[str, Any]:
        """Get camera-specific corruption settings."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT corruption_detection_heavy 
                    FROM cameras 
                    WHERE id = %s
                    """,
                    (camera_id,),
                )
                camera_data = await cur.fetchone()
                if not camera_data:
                    raise ValueError(f"Camera {camera_id} not found")

                return {
                    "corruption_detection_heavy": camera_data[
                        "corruption_detection_heavy"
                    ]
                    or False
                }

    async def get_total_cameras_count(self) -> int:
        """Get total number of cameras."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) as count FROM cameras")
                result = await cur.fetchone()
                return result["count"] if result else 0

    async def get_recent_detections_count(self) -> Dict[str, int]:
        """Get recent corruption detections count."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        COUNT(CASE WHEN created_at > NOW() - INTERVAL '1 day' THEN 1 END) as today,
                        COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END) as week
                    FROM corruption_logs
                    WHERE action_taken = 'discarded'
                    """
                )
                result = await cur.fetchone()
                return {
                    "today": result["today"] or 0,
                    "week": result["week"] or 0,
                }

    async def log_discard_decision(
        self,
        camera_id: int,
        corruption_score: float,
        should_discard: bool,
        reason: Optional[str],
    ) -> None:
        """Log auto-discard decision for audit trail."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO corruption_logs (
                        camera_id, image_id, corruption_score, fast_score, heavy_score,
                        detection_details, action_taken, processing_time_ms
                    ) VALUES (
                        %s, NULL, %s, NULL, NULL, %s, %s, 0
                    )
                    """,
                    (
                        camera_id,
                        corruption_score,
                        {"discard_decision": should_discard, "reason": reason},
                        "auto_discard_decision",
                    ),
                )

    async def get_timelapse_quality_statistics(
        self, timelapse_id: int
    ) -> Dict[str, Any]:
        """Get quality statistics for a specific timelapse."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        COUNT(i.id) as total_images,
                        AVG(i.corruption_score) as avg_score,
                        COUNT(CASE WHEN i.corruption_score < {DEFAULT_CORRUPTION_DISCARD_THRESHOLD} THEN 1 END) as flagged_images,
                        COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as manual_flags
                    FROM images i
                    WHERE i.timelapse_id = %s
                    """,
                    (timelapse_id,),
                )
                result = await cur.fetchone()
                return dict(result) if result else {}

    async def get_camera_quality_statistics(self, camera_id: int) -> Dict[str, Any]:
        """Get quality statistics for a specific camera."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        COUNT(i.id) as total_images,
                        AVG(i.corruption_score) as avg_score,
                        COUNT(CASE WHEN i.corruption_score < {DEFAULT_CORRUPTION_DISCARD_THRESHOLD} THEN 1 END) as flagged_images,
                        COUNT(cl.id) as corruption_detections
                    FROM images i
                    LEFT JOIN corruption_logs cl ON i.id = cl.image_id
                    WHERE i.camera_id = %s
                    """,
                    (camera_id,),
                )
                result = await cur.fetchone()
                return dict(result) if result else {}

    async def get_overall_quality_statistics(self) -> Dict[str, Any]:
        """Get overall system quality statistics."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        COUNT(i.id) as total_images,
                        AVG(i.corruption_score) as avg_score,
                        COUNT(CASE WHEN i.corruption_score < {DEFAULT_CORRUPTION_DISCARD_THRESHOLD} THEN 1 END) as flagged_images,
                        COUNT(cl.id) as corruption_detections,
                        COUNT(DISTINCT i.camera_id) as cameras_with_images
                    FROM images i
                    LEFT JOIN corruption_logs cl ON i.id = cl.image_id
                    """
                )
                result = await cur.fetchone()
                return dict(result) if result else {}

    async def get_camera_id_for_image(self, image_id: int) -> Optional[int]:
        """Get camera ID for a given image.

        Args:
            image_id: ID of the image

        Returns:
            Camera ID or None if image not found
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT camera_id FROM images WHERE id = %s", (image_id,)
                )
                result = await cur.fetchone()
                return result["camera_id"] if result else None

    async def get_camera_corruption_metadata(self, camera_id: int) -> Dict[str, Any]:
        """Get camera corruption metadata including counters and degraded status.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing camera corruption metadata

        Raises:
            ValueError: If camera not found
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
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
                result = await cur.fetchone()
                if not result:
                    raise ValueError(f"Camera {camera_id} not found")
                return dict(result)


class SyncCorruptionOperations:
    """Sync corruption database operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def _row_to_corruption_log(self, row: Dict[str, Any]) -> CorruptionLogEntry:
        """Convert database row to CorruptionLogEntry model."""
        # Filter fields that belong to CorruptionLogEntry model
        log_fields = {
            k: v for k, v in row.items() if k in CorruptionLogEntry.model_fields
        }
        return CorruptionLogEntry(**log_fields)

    def log_corruption_detection(
        self,
        camera_id: int,
        image_id: Optional[int],
        corruption_score: int,
        fast_score: Optional[int],
        heavy_score: Optional[int],
        detection_details: Dict[str, Any],
        action_taken: str,
        processing_time_ms: int,
    ) -> CorruptionLogEntry:
        """
        Log a corruption detection result.

        Args:
            camera_id: ID of the camera
            image_id: ID of the image (None if image was discarded)
            corruption_score: Final corruption score (0-100)
            fast_score: Fast detection score (0-100)
            heavy_score: Heavy detection score (0-100, None if not enabled)
            detection_details: Dictionary containing detection details
            action_taken: Action taken ('saved', 'discarded', 'retried')
            processing_time_ms: Processing time in milliseconds

        Returns:
            Created CorruptionLogEntry model instance
        """
        query = """
        INSERT INTO corruption_logs (
            camera_id, image_id, corruption_score, fast_score, heavy_score,
            detection_details, action_taken, processing_time_ms
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        camera_id,
                        image_id,
                        corruption_score,
                        fast_score,
                        heavy_score,
                        detection_details,
                        action_taken,
                        processing_time_ms,
                    ),
                )
                results = cur.fetchall()

                if results:
                    log_entry_row = results[0]
                    log_entry = self._row_to_corruption_log(log_entry_row)

                    return log_entry

                raise Exception("Failed to log corruption detection")

    def get_camera_corruption_failure_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get corruption failure statistics for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing failure statistics
        """
        query = """
        SELECT
            c.consecutive_corruption_failures,
            c.lifetime_glitch_count,
            c.degraded_mode_active,
            c.last_degraded_at,
            COUNT(cl.id) as failures_last_hour,
            COUNT(cl2.id) as failures_last_30min
        FROM cameras c
        LEFT JOIN corruption_logs cl ON c.id = cl.camera_id
            AND cl.created_at > NOW() - INTERVAL '1 hour'
            AND cl.action_taken = 'discarded'
        LEFT JOIN corruption_logs cl2 ON c.id = cl2.camera_id
            AND cl2.created_at > NOW() - INTERVAL '30 minutes'
            AND cl2.action_taken = 'discarded'
        WHERE c.id = %s
        GROUP BY c.id
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id,))
                results = cur.fetchall()
                return results[0] if results else {}

    def check_degraded_mode_trigger(
        self, camera_id: int, settings: Dict[str, Any]
    ) -> bool:
        """
        Check if a camera should enter degraded mode based on failure patterns.

        Args:
            camera_id: ID of the camera
            settings: Corruption detection settings

        Returns:
            True if camera should enter degraded mode
        """
        stats = self.get_camera_corruption_failure_stats(camera_id)

        if not stats:
            return False

        # Check consecutive failures threshold
        consecutive_threshold = settings.get(
            "corruption_degraded_consecutive_threshold",
            DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
        )
        if stats["consecutive_corruption_failures"] >= consecutive_threshold:
            return True

        # Check failure percentage in time window
        time_window_minutes = settings.get(
            "corruption_degraded_time_window_minutes",
            DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES,
        )
        failure_percentage = settings.get(
            "corruption_degraded_failure_percentage",
            DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE,
        )

        # Get total captures and failures in time window
        query = """
        SELECT
            COUNT(cl.id) as total_failures,
            (
                SELECT COUNT(*)
                FROM images i
                JOIN timelapses t ON i.timelapse_id = t.id
                WHERE t.camera_id = %s
                AND i.captured_at > NOW() - INTERVAL '%s minutes'
            ) as total_captures
        FROM corruption_logs cl
        WHERE cl.camera_id = %s
        AND cl.created_at > NOW() - INTERVAL '%s minutes'
        AND cl.action_taken = 'discarded'
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (camera_id, time_window_minutes, camera_id, time_window_minutes),
                )
                results = cur.fetchall()

                if results:
                    data = results[0]
                    total_captures = data["total_captures"] or 0
                    total_failures = data["total_failures"] or 0

                    if (
                        total_captures >= MIN_CORRUPTION_ANALYSIS_SAMPLE_SIZE
                    ):  # Minimum sample size
                        current_failure_percentage = (
                            total_failures / total_captures
                        ) * 100
                        if current_failure_percentage >= failure_percentage:
                            return True

        return False

    def set_camera_degraded_mode(self, camera_id: int, is_degraded: bool) -> bool:
        """
        Set camera degraded mode status.

        Args:
            camera_id: ID of the camera
            is_degraded: Whether camera should be in degraded mode

        Returns:
            True if update was successful
        """
        query = """
        UPDATE cameras
        SET degraded_mode_active = %s,
            last_degraded_at = CASE WHEN %s THEN NOW() ELSE last_degraded_at END,
            updated_at = NOW()
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (is_degraded, is_degraded, camera_id))
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    def reset_camera_corruption_failures(self, camera_id: int) -> bool:
        """
        Reset camera corruption failure counters.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful
        """
        query = """
        UPDATE cameras
        SET consecutive_corruption_failures = 0,
            degraded_mode_active = false,
            updated_at = NOW()
        WHERE id = %s
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id,))
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    def cleanup_old_corruption_logs(
        self, days_to_keep: int = DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS
    ) -> int:
        """
        Clean up old corruption detection logs.

        Args:
            days_to_keep: Number of days to keep logs (default: from constants)

        Returns:
            Number of logs deleted
        """
        query = """
        DELETE FROM corruption_logs
        WHERE created_at < NOW() - INTERVAL '%s days'
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (days_to_keep,))
                affected = cur.rowcount

                if affected and affected > 0:
                    logger.info(f"Cleaned up {affected} old corruption logs")

                return affected or 0

    def get_corruption_settings(self) -> Dict[str, Any]:
        """Get global corruption detection settings from settings table (sync version)."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key, value 
                    FROM settings 
                    WHERE key LIKE 'corruption_%'
                    """
                )
                settings_rows = cur.fetchall()

                # Use shared helper for processing
                return _process_corruption_settings_rows(settings_rows)

    def update_corruption_settings(self, settings: Dict[str, Any]) -> None:
        """Update global corruption detection settings (sync version)."""
        if not settings:
            return

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                for key, value in settings.items():
                    # Convert setting name to database key format
                    db_key = f"corruption_{key}"
                    cur.execute(
                        """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                        """,
                        (db_key, str(value)),
                    )

    def get_camera_corruption_settings(self, camera_id: int) -> Dict[str, Any]:
        """Get camera-specific corruption settings."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT corruption_detection_heavy 
                    FROM cameras 
                    WHERE id = %s
                    """,
                    (camera_id,),
                )
                camera_data = cur.fetchone()
                if not camera_data:
                    return {"corruption_detection_heavy": False}

                return {
                    "corruption_detection_heavy": camera_data[
                        "corruption_detection_heavy"
                    ]
                    or False
                }

    def update_camera_corruption_stats(
        self, camera_id: int, corruption_score: int, is_valid: bool
    ) -> bool:
        """
        Update camera corruption statistics after evaluation.

        Args:
            camera_id: ID of the camera
            corruption_score: Corruption score from evaluation
            is_valid: Whether the image was considered valid

        Returns:
            True if update was successful
        """
        try:
            if not is_valid:
                # Increment failure counters for invalid images
                query = """
                UPDATE cameras
                SET consecutive_corruption_failures = consecutive_corruption_failures + 1,
                    lifetime_glitch_count = lifetime_glitch_count + 1,
                    updated_at = NOW()
                WHERE id = %s
                """

                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, (camera_id,))
                        affected = cur.rowcount
                        return affected and affected > 0
            else:
                # Reset consecutive failures for valid images
                query = """
                UPDATE cameras
                SET consecutive_corruption_failures = 0,
                    updated_at = NOW()
                WHERE id = %s
                """

                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, (camera_id,))
                        affected = cur.rowcount
                        return affected and affected > 0

        except Exception as e:
            logger.error(
                f"Failed to update camera corruption stats for camera {camera_id}: {e}"
            )
            return False
