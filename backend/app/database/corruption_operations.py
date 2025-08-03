# backend/app/database/corruption_operations.py
"""
Corruption detection database operations module - Composition Pattern.

This module handles all corruption-related database operations including:
- Corruption detection logging
- Corruption statistics
- Degraded mode management
- Corruption settings
"""


from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg

from ..constants import (
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
    DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
    DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
    DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE,
    DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
    DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES,
    MIN_CORRUPTION_ANALYSIS_SAMPLE_SIZE,
)
from ..models.corruption_model import (
    CameraWithCorruption,
    CorruptionAnalysisStats,
    CorruptionLogEntry,
    CorruptionLogsPage,
    CorruptionStats,
)
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase


class CorruptionQueryBuilder:
    """Centralized query builder for corruption operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_corruption_logs_camera_id ON corruption_logs(camera_id);
    - CREATE INDEX idx_corruption_logs_created_at ON corruption_logs(created_at DESC);
    - CREATE INDEX idx_corruption_logs_action_taken ON corruption_logs(action_taken);
    - CREATE INDEX idx_corruption_logs_composite ON corruption_logs(camera_id, created_at DESC);
    - CREATE INDEX idx_corruption_logs_score ON corruption_logs(corruption_score);
    - CREATE INDEX idx_cameras_degraded ON cameras(degraded_mode_active) WHERE degraded_mode_active = true;
    - CREATE INDEX idx_images_corruption ON images(corruption_score) WHERE corruption_score IS NOT NULL;
    """

    @staticmethod
    def build_corruption_logs_query(where_clause: str):
        """Build optimized query for corruption logs with filtering using named parameters."""
        return f"""
            SELECT
                cl.*,
                c.name as camera_name,
                i.file_path as image_path
            FROM corruption_logs cl
            JOIN cameras c ON cl.camera_id = c.id
            LEFT JOIN images i ON cl.image_id = i.id
            WHERE {where_clause}
            ORDER BY cl.created_at DESC
            LIMIT %(page_size)s OFFSET %(offset)s
        """

    @staticmethod
    def build_corruption_stats_query(where_clause: str = ""):
        """Build optimized corruption statistics query using modern PostgreSQL features."""
        return f"""
            SELECT
                COUNT(*) as total_detections,
                COUNT(*) FILTER (WHERE cl.action_taken = 'saved') as images_saved,
                COUNT(*) FILTER (WHERE cl.action_taken = 'discarded') as images_discarded,
                COUNT(*) FILTER (WHERE cl.action_taken = 'retried') as images_retried,
                AVG(cl.corruption_score) as avg_corruption_score,
                MIN(cl.corruption_score) as min_corruption_score,
                MAX(cl.corruption_score) as max_corruption_score,
                AVG(cl.processing_time_ms) as avg_processing_time_ms,
                COUNT(*) FILTER (WHERE cl.corruption_score < %(discard_threshold)s) as low_quality_count,
                COUNT(*) FILTER (WHERE cl.created_at > %(now)s - INTERVAL '24 hours') as detections_last_24h,
                MAX(cl.created_at) as most_recent_detection,
                COUNT(DISTINCT cl.camera_id) as unique_cameras
            FROM corruption_logs cl
            {where_clause}
        """

    @staticmethod
    def build_camera_corruption_history_query():
        """Build optimized query for camera corruption history with named parameters."""
        return """
            SELECT
                cl.*,
                c.name as camera_name,
                i.file_path as image_path
            FROM corruption_logs cl
            JOIN cameras c ON cl.camera_id = c.id
            LEFT JOIN images i ON cl.image_id = i.id
            WHERE cl.camera_id = %(camera_id)s
                AND cl.created_at > %(now)s - INTERVAL %(hours)s * INTERVAL '1 hour'
            ORDER BY cl.created_at DESC
        """

    @staticmethod
    def build_degraded_cameras_query():
        """Build optimized query for degraded cameras with recent failures using named parameters."""
        return """
            SELECT
                c.*,
                COUNT(*) FILTER (WHERE cl.action_taken = 'discarded') as recent_failures
            FROM cameras c
            LEFT JOIN corruption_logs cl ON c.id = cl.camera_id
                AND cl.created_at > %(now)s - INTERVAL '1 hour'
            WHERE c.degraded_mode_active = true
            GROUP BY c.id, c.name, c.enabled, c.degraded_mode_active,
                    c.consecutive_corruption_failures, c.lifetime_glitch_count,
                    c.last_degraded_at, c.created_at, c.updated_at
            ORDER BY c.last_degraded_at DESC NULLS LAST
        """

    @staticmethod
    def build_quality_stats_query(table_filter: str):
        """Build optimized query for quality statistics using named parameters."""
        return f"""
            SELECT
                COUNT(i.id) as total_images,
                AVG(i.corruption_score) as avg_score,
                COUNT(*) FILTER (WHERE i.corruption_score < %(discard_threshold)s) as flagged_images,
                COUNT(cl.id) as corruption_detections
            FROM images i
            LEFT JOIN corruption_logs cl ON i.id = cl.image_id
            {table_filter}
        """


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
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_corruption_caches(
        self,
        corruption_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Clear caches related to corruption operations using sophisticated cache system."""
        # Clear corruption-related caches using advanced cache manager
        cache_patterns = [
            "corruption:get_corruption_logs",
            "corruption:get_corruption_stats",
            "corruption:get_degraded_cameras",
            "corruption:get_recent_detections_count",
            "corruption:get_overall_quality_statistics",
        ]

        if corruption_id:
            cache_patterns.extend(
                [
                    f"corruption:log_by_id:{corruption_id}",
                    f"corruption:metadata:{corruption_id}",
                ]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(corruption_id, updated_at)
                await self.cache_invalidation.invalidate_with_etag_validation(
                    f"corruption:metadata:{corruption_id}", etag
                )

        if camera_id:
            cache_patterns.extend(
                [
                    f"corruption:camera_history:{camera_id}",
                    f"corruption:camera_stats:{camera_id}",
                    f"corruption:camera_metadata:{camera_id}",
                ]
            )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    def _row_to_corruption_log(self, row: Dict[str, Any]) -> CorruptionLogEntry:
        """Convert database row to CorruptionLogEntry model."""
        # Filter fields that belong to CorruptionLogEntry model
        log_fields = {
            k: v for k, v in row.items() if k in CorruptionLogEntry.model_fields.keys()
        }
        return CorruptionLogEntry(**log_fields)

    def _row_to_corruption_stats(self, row: Dict[str, Any]) -> CorruptionStats:
        """Convert database row to CorruptionStats model."""
        # Filter fields that belong to CorruptionStats model
        stats_fields = {
            k: v for k, v in row.items() if k in CorruptionStats.model_fields.keys()
        }
        return CorruptionStats(**stats_fields)

    def _row_to_camera_with_corruption(
        self, row: Dict[str, Any]
    ) -> CameraWithCorruption:
        """Convert database row to CameraWithCorruption model."""
        # Filter fields that belong to CameraWithCorruption model
        camera_fields = {
            k: v
            for k, v in row.items()
            if k in CameraWithCorruption.model_fields.keys()
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

                # Get logs with pagination using query builder
                logs_query = CorruptionQueryBuilder.build_corruption_logs_query(
                    where_clause
                )

                # Convert positional params to named params for consistency
                logs_params = dict(
                    zip([f"param_{i}" for i in range(len(params))], params)
                )
                logs_params.update({"page_size": page_size, "offset": offset})

                # Update where_clause to use named parameters
                param_names = list(logs_params.keys())[
                    :-2
                ]  # Exclude page_size and offset
                if param_names:
                    # Replace %s with %(param_name)s in where_clause
                    where_conditions_named = []
                    param_index = 0
                    for condition in where_conditions:
                        if "%s" in condition:
                            condition = condition.replace(
                                "%s", f"%(param_{param_index})s"
                            )
                            param_index += 1
                        where_conditions_named.append(condition)
                    where_clause_named = (
                        " AND ".join(where_conditions_named)
                        if where_conditions_named
                        else "1=1"
                    )
                    logs_query = CorruptionQueryBuilder.build_corruption_logs_query(
                        where_clause_named
                    )

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

        # Use centralized time management and query builder
        now = utc_now()

        # Build named parameters for consistency
        params = {
            "discard_threshold": DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
            "now": now,
        }

        if camera_id:
            params["camera_id"] = camera_id
            where_clause = "WHERE cl.camera_id = %(camera_id)s"

        query = CorruptionQueryBuilder.build_corruption_stats_query(where_clause)

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
                        unique_cameras=row["unique_cameras"] or 0,
                        most_recent_detection=row["most_recent_detection"],
                    )

                # Return default stats if no results
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

    @cached_response(ttl_seconds=60, key_prefix="corruption")
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
        # Use optimized query builder with named parameters
        query = CorruptionQueryBuilder.build_camera_corruption_history_query()
        params = {
            "camera_id": camera_id,
            "now": utc_now(),
            "hours": hours,
        }

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_corruption_log(row) for row in results]

    @cached_response(ttl_seconds=30, key_prefix="corruption")
    async def get_degraded_cameras(self) -> List[CameraWithCorruption]:
        """
        Get all cameras currently in degraded mode.

        Returns:
            List of CameraWithCorruption models
        """
        # Use optimized query builder with named parameters
        query = CorruptionQueryBuilder.build_degraded_cameras_query()
        params = {"now": utc_now()}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
            updated_at = %s
        WHERE id = %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (utc_now(), camera_id))
                affected = cur.rowcount

                # Clear related caches after successful reset
                if affected and affected > 0:
                    await self._clear_corruption_caches(
                        camera_id=camera_id, updated_at=utc_now()
                    )
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
        """Update global corruption detection settings using efficient batch upsert (async version)."""
        if not settings:
            return

        # Use batch upsert for better performance
        query = """
        INSERT INTO settings (key, value, updated_at)
        VALUES (%(key)s, %(value)s, %(updated_at)s)
        ON CONFLICT (key)
        DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        """

        current_time = utc_now()
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Execute settings updates efficiently
                for key, value in settings.items():
                    params = {
                        "key": f"corruption_{key}",
                        "value": str(value),
                        "updated_at": current_time,
                    }
                    await cur.execute(query, params)

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
                query = """
                    SELECT
                        COUNT(CASE WHEN created_at > %s - INTERVAL '1 day' THEN 1 END) as today,
                        COUNT(CASE WHEN created_at > %s - INTERVAL '7 days' THEN 1 END) as week
                    FROM corruption_logs
                    WHERE action_taken = 'discarded'
                    """
                now = utc_now()
                await cur.execute(query, (now, now))
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

    @cached_response(ttl_seconds=120, key_prefix="corruption")
    async def get_timelapse_quality_statistics(
        self, timelapse_id: int
    ) -> Dict[str, Any]:
        """Get quality statistics for a specific timelapse."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Use query builder for quality statistics with named parameters
                query = CorruptionQueryBuilder.build_quality_stats_query(
                    "WHERE i.timelapse_id = %(timelapse_id)s"
                )
                params = {
                    "discard_threshold": DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
                    "timelapse_id": timelapse_id,
                }
                await cur.execute(query, params)
                result = await cur.fetchone()
                return dict(result) if result else {}

    @cached_response(ttl_seconds=120, key_prefix="corruption")
    async def get_camera_quality_statistics(self, camera_id: int) -> Dict[str, Any]:
        """Get quality statistics for a specific camera."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Use query builder for quality statistics with named parameters
                query = CorruptionQueryBuilder.build_quality_stats_query(
                    "WHERE i.camera_id = %(camera_id)s"
                )
                params = {
                    "discard_threshold": DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
                    "camera_id": camera_id,
                }
                await cur.execute(query, params)
                result = await cur.fetchone()
                return dict(result) if result else {}

    @cached_response(ttl_seconds=180, key_prefix="corruption")
    async def get_overall_quality_statistics(self) -> Dict[str, Any]:
        """Get overall system quality statistics."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                query = """
                    SELECT
                        COUNT(i.id) as total_images,
                        AVG(i.corruption_score) as avg_score,
                        COUNT(*) FILTER (WHERE i.corruption_score < %(discard_threshold)s) as flagged_images,
                        COUNT(cl.id) as corruption_detections,
                        COUNT(DISTINCT i.camera_id) as cameras_with_images
                    FROM images i
                    LEFT JOIN corruption_logs cl ON i.id = cl.image_id
                """
                params = {"discard_threshold": DEFAULT_CORRUPTION_DISCARD_THRESHOLD}
                await cur.execute(query, params)
                result = await cur.fetchone()
                return dict(result) if result else {}

    @cached_response(ttl_seconds=300, key_prefix="corruption")
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

    @cached_response(ttl_seconds=60, key_prefix="corruption")
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
            k: v for k, v in row.items() if k in CorruptionLogEntry.model_fields.keys()
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
        Log a corruption detection result using optimized INSERT with named parameters.

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
            detection_details, action_taken, processing_time_ms, created_at
        ) VALUES (
            %(camera_id)s, %(image_id)s, %(corruption_score)s, %(fast_score)s, %(heavy_score)s,
            %(detection_details)s, %(action_taken)s, %(processing_time_ms)s, %(created_at)s
        ) RETURNING *
        """

        params = {
            "camera_id": camera_id,
            "image_id": image_id,
            "corruption_score": corruption_score,
            "fast_score": fast_score,
            "heavy_score": heavy_score,
            "detection_details": detection_details,
            "action_taken": action_taken,
            "processing_time_ms": processing_time_ms,
            "created_at": utc_now(),
        }

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()

                if results:
                    log_entry_row = results[0]
                    log_entry = self._row_to_corruption_log(log_entry_row)

                    return log_entry

                raise psycopg.DatabaseError("Failed to log corruption detection")

    def get_camera_corruption_failure_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get corruption failure statistics for a camera using optimized query with named parameters.

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
            COUNT(*) FILTER (WHERE cl.created_at > %(now)s - INTERVAL '1 hour'
                            AND cl.action_taken = 'discarded') as failures_last_hour,
            COUNT(*) FILTER (WHERE cl.created_at > %(now)s - INTERVAL '30 minutes'
                            AND cl.action_taken = 'discarded') as failures_last_30min
        FROM cameras c
        LEFT JOIN corruption_logs cl ON c.id = cl.camera_id
        WHERE c.id = %(camera_id)s
        GROUP BY c.id, c.consecutive_corruption_failures, c.lifetime_glitch_count,
                c.degraded_mode_active, c.last_degraded_at
        """

        params = {"now": utc_now(), "camera_id": camera_id}

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
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

        # Get total captures and failures in time window using optimized CTE query
        query = """
        WITH time_window AS (
            SELECT %(now)s - INTERVAL %(time_window)s * INTERVAL '1 minute' as window_start
        ),
        failure_stats AS (
            SELECT COUNT(*) as total_failures
            FROM corruption_logs cl, time_window tw
            WHERE cl.camera_id = %(camera_id)s
                AND cl.created_at > tw.window_start
                AND cl.action_taken = 'discarded'
        ),
        capture_stats AS (
            SELECT COUNT(*) as total_captures
            FROM images i
            JOIN timelapses t ON i.timelapse_id = t.id, time_window tw
            WHERE t.camera_id = %(camera_id)s
                AND i.captured_at > tw.window_start
        )
        SELECT
            fs.total_failures,
            cs.total_captures
        FROM failure_stats fs
        CROSS JOIN capture_stats cs
        """

        params = {
            "now": utc_now(),
            "time_window": time_window_minutes,
            "camera_id": camera_id,
        }

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
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
        Set camera degraded mode status using atomic operation.

        Args:
            camera_id: ID of the camera
            is_degraded: Whether camera should be in degraded mode

        Returns:
            True if update was successful
        """
        query = """
        UPDATE cameras
        SET degraded_mode_active = %(is_degraded)s,
            last_degraded_at = CASE WHEN %(is_degraded)s THEN %(now)s ELSE last_degraded_at END,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

        params = {
            "is_degraded": is_degraded,
            "now": utc_now(),
            "camera_id": camera_id,
        }

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    def reset_camera_corruption_failures(self, camera_id: int) -> bool:
        """
        Reset camera corruption failure counters using atomic operation.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful
        """
        query = """
        UPDATE cameras
        SET consecutive_corruption_failures = 0,
            degraded_mode_active = false,
            updated_at = %(now)s
        WHERE id = %(camera_id)s
        """

        params = {"now": utc_now(), "camera_id": camera_id}

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount

                if affected and affected > 0:
                    return True
                return False

    def cleanup_old_corruption_logs(
        self, days_to_keep: int = DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS
    ) -> int:
        """
        Clean up old corruption detection logs using efficient batch deletion.

        Args:
            days_to_keep: Number of days to keep logs (default: from constants)

        Returns:
            Number of logs deleted
        """
        query = """
        DELETE FROM corruption_logs
        WHERE created_at < %(now)s - INTERVAL %(days)s * INTERVAL '1 day'
        """

        params = {
            "now": utc_now(),
            "days": days_to_keep,
        }

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected = cur.rowcount

                if affected and affected > 0:
                    pass

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
        """Update global corruption detection settings using efficient batch upsert."""
        if not settings:
            return

        # Use batch upsert for better performance
        query = """
        INSERT INTO settings (key, value, updated_at)
        VALUES (%(key)s, %(value)s, %(updated_at)s)
        ON CONFLICT (key)
        DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        """

        current_time = utc_now()
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Batch execute all settings updates
                params_list = [
                    {
                        "key": f"corruption_{key}",
                        "value": str(value),
                        "updated_at": current_time,
                    }
                    for key, value in settings.items()
                ]
                cur.executemany(query, params_list)

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
        self, camera_id: int, _corruption_score: int, is_valid: bool
    ) -> bool:
        """
        Update camera corruption statistics after evaluation using atomic operations.

        Args:
            camera_id: ID of the camera
            _corruption_score: Corruption score from evaluation (unused)
            is_valid: Whether the image was considered valid

        Returns:
            True if update was successful
        """
        try:
            # Use single query to handle both valid and invalid cases atomically
            query = """
            UPDATE cameras
            SET consecutive_corruption_failures = CASE
                    WHEN %(is_valid)s THEN 0
                    ELSE consecutive_corruption_failures + 1
                END,
                lifetime_glitch_count = CASE
                    WHEN NOT %(is_valid)s THEN lifetime_glitch_count + 1
                    ELSE lifetime_glitch_count
                END,
                updated_at = %(now)s
            WHERE id = %(camera_id)s
            """

            params = {
                "is_valid": is_valid,
                "now": utc_now(),
                "camera_id": camera_id,
            }

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    affected = cur.rowcount
                    return affected and affected > 0

        except (psycopg.Error, KeyError, ValueError):
            return False
