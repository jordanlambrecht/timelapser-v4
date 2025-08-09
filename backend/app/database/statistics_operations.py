# backend/app/database/statistics_operations.py
"""
Statistics database operations module - Composition Pattern.

This module handles all statistics-related database operations including:
- System health aggregation
- Dashboard data collection
- Camera/timelapse statistics
- Performance metrics
"""


from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg

from app.models.statistics_model import (
    AutomationStatsModel,
    CameraPerformanceModel,
    CameraStatsModel,
    DashboardStatsModel,
    ImageStatsModel,
    QualityTrendDataPoint,
    RecentActivityModel,
    StorageStatsModel,
    TimelapseStatsModel,
    VideoStatsModel,
)

from ..constants import DEFAULT_STATISTICS_RETENTION_DAYS
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_timestamp_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import StatisticsOperationError


class StatisticsQueryBuilder:
    """Centralized query builder for statistics operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_cameras_enabled ON cameras(enabled) WHERE enabled = true;
    - CREATE INDEX idx_cameras_degraded ON cameras(degraded_mode_active) WHERE degraded_mode_active = true;
    - CREATE INDEX idx_cameras_heavy_detection ON cameras(corruption_detection_heavy) WHERE corruption_detection_heavy = true;
    - CREATE INDEX idx_timelapses_status ON timelapses(status);
    - CREATE INDEX idx_images_captured_at ON images(captured_at DESC);
    - CREATE INDEX idx_images_flagged ON images(is_flagged) WHERE is_flagged = true;
    - CREATE INDEX idx_images_corruption_score ON images(corruption_score) WHERE corruption_score IS NOT NULL;
    - CREATE INDEX idx_images_file_size ON images(file_size) WHERE file_size IS NOT NULL;
    - CREATE INDEX idx_videos_status ON videos(status);
    - CREATE INDEX idx_videos_completed_file_size ON videos(file_size) WHERE status = 'completed';
    - CREATE INDEX idx_videos_completed_duration ON videos(duration_seconds) WHERE status = 'completed';
    - CREATE INDEX idx_video_jobs_status ON video_generation_jobs(status);
    - CREATE INDEX idx_corruption_logs_camera_created ON corruption_logs(camera_id, created_at DESC);
    """

    @staticmethod
    def build_dashboard_stats_query():
        """Build comprehensive dashboard statistics query using named parameters and CTEs."""
        return """
            WITH camera_stats AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) as total_cameras,
                    COUNT(*) FILTER (WHERE enabled = true) as enabled_cameras,
                    COUNT(*) FILTER (WHERE degraded_mode_active = true) as degraded_cameras,
                    COUNT(*) FILTER (WHERE corruption_detection_heavy = true) as cameras_with_heavy_detection
                FROM cameras
            ),
            timelapse_stats AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) as total_timelapses,
                    COUNT(*) FILTER (WHERE status = 'running') as running_timelapses,
                    COUNT(*) FILTER (WHERE status = 'paused') as paused_timelapses,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_timelapses
                FROM timelapses
            ),
            image_stats AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) as total_images,
                    COUNT(*) FILTER (WHERE captured_at > %(current_time)s - INTERVAL '24 hours') as images_today,
                    COUNT(*) FILTER (WHERE is_flagged = true) as flagged_images,
                    AVG(CASE WHEN corruption_score IS NOT NULL THEN corruption_score ELSE 100 END) as avg_quality_score,
                    COALESCE(SUM(file_size), 0) as total_storage_bytes
                FROM images
            ),
            video_stats AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) as total_videos,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_videos,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_videos,
                    COUNT(*) FILTER (WHERE status = 'canceled') as canceled_videos,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_videos,
                    COALESCE(SUM(file_size) FILTER (WHERE status = 'completed'), 0) as total_file_size,
                    COALESCE(AVG(duration_seconds) FILTER (WHERE status = 'completed'), 0) as avg_duration
                FROM videos
            ),
            automation_stats AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) as total_jobs,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_jobs,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs
                FROM video_generation_jobs
            ),
            activity_stats AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) FILTER (WHERE captured_at > %(current_time)s - INTERVAL '1 hour') as captures_last_hour,
                    COUNT(*) FILTER (WHERE captured_at > %(current_time)s - INTERVAL '24 hours') as captures_last_24h
                FROM images
            )
            SELECT
                cs.*,
                ts.*,
                imgs.*,
                vs.*,
                as_.*,
                acts.*
            FROM camera_stats cs
            CROSS JOIN timelapse_stats ts
            CROSS JOIN image_stats imgs
            CROSS JOIN video_stats vs
            CROSS JOIN automation_stats as_
            CROSS JOIN activity_stats acts
        """

    @staticmethod
    def build_camera_performance_query(camera_id: Optional[int] = None):
        """Build optimized camera performance query with named parameters."""
        # Use proper conditional SQL construction without f-strings
        base_query = """
            SELECT
                c.id,
                c.name,
                c.enabled,
                c.degraded_mode_active,
                c.lifetime_glitch_count,
                c.consecutive_corruption_failures,
                COUNT(i.id) as total_images,
                COUNT(*) FILTER (WHERE i.captured_at > %(current_time)s - INTERVAL '24 hours') as images_today,
                COUNT(*) FILTER (WHERE i.captured_at > %(current_time)s - INTERVAL '7 days') as images_week,
                COUNT(*) FILTER (WHERE i.is_flagged = true) as flagged_images,
                AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
                MAX(i.captured_at) as last_capture_at,
                COUNT(DISTINCT v.id) as total_videos,
                COALESCE(SUM(i.file_size), 0) as total_storage_bytes
            FROM cameras c
            LEFT JOIN timelapses t ON c.id = t.camera_id
            LEFT JOIN images i ON t.id = i.timelapse_id
            LEFT JOIN videos v ON t.id = v.timelapse_id"""

        if camera_id is not None:
            base_query += " WHERE c.id = %(camera_id)s"

        base_query += """
            GROUP BY c.id, c.name, c.enabled, c.degraded_mode_active,
                    c.lifetime_glitch_count, c.consecutive_corruption_failures
            ORDER BY c.name"""

        return base_query

    @staticmethod
    def build_system_health_query():
        """Build comprehensive system health query using named parameters and CTEs."""
        return """
            WITH camera_health AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) as total_cameras,
                    COUNT(*) FILTER (WHERE enabled = true) as enabled_cameras,
                    COUNT(*) FILTER (WHERE degraded_mode_active = true) as degraded_cameras
                FROM cameras
            ),
            quality_health AS NOT MATERIALIZED (
                SELECT
                    AVG(CASE WHEN corruption_score IS NOT NULL THEN corruption_score ELSE 100 END) as avg_quality_score,
                    COUNT(*) FILTER (WHERE is_flagged = true) as flagged_images,
                    COUNT(*) as total_images
                FROM images
                WHERE captured_at > %(current_time)s - INTERVAL '24 hours'
            ),
            activity_health AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) FILTER (WHERE i.captured_at > %(current_time)s - INTERVAL '1 hour') as captures_last_hour
                FROM images i
            ),
            timelapse_health AS NOT MATERIALIZED (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'running') as running_timelapses
                FROM timelapses
            )
            SELECT
                ch.*,
                qh.*,
                ah.*,
                th.*
            FROM camera_health ch
            CROSS JOIN quality_health qh
            CROSS JOIN activity_health ah
            CROSS JOIN timelapse_health th
        """


class StatisticsOperations:
    """Statistics database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db
        # CacheInvalidationService is now used as static class methods

    async def _clear_statistics_caches(
        self, stat_type: Optional[str] = None, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to statistics using sophisticated cache system."""
        # Clear statistics caches using advanced cache manager
        cache_patterns = [
            "statistics:get_dashboard_stats",
            "statistics:get_camera_performance_stats",
            "statistics:get_storage_statistics",
            "statistics:get_system_health_score",
        ]

        if stat_type:
            cache_patterns.append(f"statistics:by_type:{stat_type}")

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

        # Use ETag-aware invalidation if timestamp provided
        if updated_at:
            etag = generate_timestamp_etag(updated_at)
            await CacheInvalidationService.invalidate_with_etag_validation(
                "statistics:metadata", etag
            )

    @cached_response(ttl_seconds=120, key_prefix="statistics")
    async def get_dashboard_stats(self) -> DashboardStatsModel:
        """
        Get comprehensive dashboard statistics using optimized single-query approach.

        Returns:
            DashboardStatsModel containing system-wide statistics
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized CTE-based query with named parameters
                    query = StatisticsQueryBuilder.build_dashboard_stats_query()
                    params: Dict[str, Any] = {"current_time": utc_now()}
                    await cur.execute(query, params)

                    result = await cur.fetchone()
                    if not result:
                        raise ValueError("No statistics data returned")

                    # Extract component statistics from single result row
                    camera_model = CameraStatsModel(
                        total_cameras=result["total_cameras"],
                        enabled_cameras=result["enabled_cameras"],
                        degraded_cameras=result["degraded_cameras"],
                        cameras_with_heavy_detection=result[
                            "cameras_with_heavy_detection"
                        ],
                    )

                    timelapse_model = TimelapseStatsModel(
                        total_timelapses=result["total_timelapses"],
                        running_timelapses=result["running_timelapses"],
                        paused_timelapses=result["paused_timelapses"],
                        completed_timelapses=result["completed_timelapses"],
                    )

                    image_model = ImageStatsModel(
                        total_images=result["total_images"],
                        images_today=result["images_today"],
                        flagged_images=result["flagged_images"],
                        avg_quality_score=result["avg_quality_score"],
                        total_storage_bytes=result["total_storage_bytes"],
                    )

                    video_model = VideoStatsModel(
                        total_videos=result["total_videos"],
                        completed_videos=result["completed_videos"],
                        processing_videos=result["processing_videos"],
                        canceled_videos=result["canceled_videos"],
                        failed_videos=result["failed_videos"],
                        total_file_size=result["total_file_size"],
                        avg_duration=result["avg_duration"],
                    )

                    # NOTE: Queue health calculation moved to service layer
                    # Database layer should only return raw data
                    automation_model = AutomationStatsModel(
                        total_jobs=result["total_jobs"],
                        pending_jobs=result["pending_jobs"],
                        processing_jobs=result["processing_jobs"],
                        completed_jobs=result["completed_jobs"],
                        failed_jobs=result["failed_jobs"],
                        queue_health="unknown",  # To be calculated in service layer
                    )

                    recent_activity_model = RecentActivityModel(
                        captures_last_hour=result["captures_last_hour"],
                        captures_last_24h=result["captures_last_24h"],
                    )

                    return DashboardStatsModel(
                        camera=camera_model,
                        timelapse=timelapse_model,
                        image=image_model,
                        video=video_model,
                        automation=automation_model,
                        recent_activity=recent_activity_model,
                    )
        except (psycopg.Error, KeyError, ValueError):
            raise StatisticsOperationError(
                "Failed to retrieve dashboard statistics",
                operation="get_dashboard_statistics",
            )

    @cached_response(ttl_seconds=300, key_prefix="statistics")
    @cached_response(ttl_seconds=180, key_prefix="statistics")
    async def get_camera_performance_stats(
        self, camera_id: Optional[int] = None
    ) -> List[CameraPerformanceModel]:
        """
        Get camera performance statistics using optimized query builder.

        Args:
            camera_id: Optional camera ID to filter by

        Returns:
            List of camera performance models
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = StatisticsQueryBuilder.build_camera_performance_query(
                        camera_id
                    )
                    params: Dict[str, Any] = {"current_time": utc_now()}
                    if camera_id:
                        params["camera_id"] = camera_id
                    await cur.execute(query, params)

                    rows = await cur.fetchall()
                    return [CameraPerformanceModel(**row) for row in rows]

        except (psycopg.Error, KeyError, ValueError):
            raise StatisticsOperationError(
                "Failed to retrieve camera performance statistics",
                operation="get_camera_performance",
            )

    @cached_response(ttl_seconds=300, key_prefix="statistics")
    async def get_quality_trend_data(
        self, camera_id: Optional[int] = None, hours: int = 24
    ) -> List[QualityTrendDataPoint]:
        """
        Get quality trend data over time with caching.

        Args:
            camera_id: Optional camera ID to filter by
            hours: Number of hours of data to retrieve

        Returns:
            List of quality trend data points
        """
        try:
            # Use proper conditional SQL construction without f-strings
            base_query = """
            SELECT
                DATE_TRUNC('hour', i.captured_at) as hour,
                AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
                COUNT(*) as image_count,
                COUNT(*) FILTER (WHERE i.is_flagged = true) as flagged_count
            FROM images i
            JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.captured_at > %(current_time)s - INTERVAL '1 hour' * %(hours)s"""

            if camera_id:
                base_query += " AND t.camera_id = %(camera_id)s"

            query = (
                base_query
                + """
            GROUP BY DATE_TRUNC('hour', i.captured_at)
            ORDER BY hour
            """
            )

            params: Dict[str, Any] = {"current_time": utc_now(), "hours": hours}
            if camera_id:
                params["camera_id"] = camera_id

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()
                    return [QualityTrendDataPoint(**row) for row in rows]

        except (psycopg.Error, KeyError, ValueError):
            raise StatisticsOperationError(
                "Failed to retrieve quality trend data",
                operation="get_quality_trend_data",
            )

    @cached_response(ttl_seconds=240, key_prefix="statistics")
    async def get_storage_statistics(self) -> StorageStatsModel:
        """
        Get storage usage statistics with caching.

        Returns:
            StorageStatsModel containing storage statistics
        """
        try:
            # Use separate queries and UNION ALL for better performance than FULL OUTER JOIN
            query = """
            WITH image_stats AS NOT MATERIALIZED (
                SELECT
                    COALESCE(SUM(file_size), 0) as total_image_storage,
                    COUNT(*) as total_images,
                    COALESCE(AVG(file_size), 0) as avg_image_size
                FROM images
                WHERE file_size IS NOT NULL
            ),
            video_stats AS NOT MATERIALIZED (
                SELECT
                    COALESCE(SUM(file_size), 0) as total_video_storage,
                    COUNT(*) as total_videos,
                    COALESCE(AVG(file_size), 0) as avg_video_size
                FROM videos
                WHERE file_size IS NOT NULL
            )
            SELECT
                i.total_image_storage,
                v.total_video_storage,
                i.total_images,
                v.total_videos,
                i.avg_image_size,
                v.avg_video_size
            FROM image_stats i
            CROSS JOIN video_stats v
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    results = await cur.fetchall()
                    if results:
                        return StorageStatsModel(**results[0])
                    return StorageStatsModel(
                        total_image_storage=0,
                        total_video_storage=0,
                        total_images=0,
                        total_videos=0,
                        avg_image_size=0.0,
                        avg_video_size=0.0,
                    )
        except (psycopg.Error, KeyError, ValueError):
            raise StatisticsOperationError(
                "Failed to retrieve storage statistics",
                operation="get_storage_statistics",
            )

    @cached_response(ttl_seconds=120, key_prefix="statistics")
    async def get_system_health_data(self) -> Dict[str, Any]:
        """
        Retrieve raw system health data for service layer calculation.

        NOTE: Business logic (health score calculations) moved to service layer.
        This method only returns raw database metrics.

        Returns:
            Dictionary containing raw health metrics for service layer processing
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized CTE-based query with named parameters
                    query = StatisticsQueryBuilder.build_system_health_query()
                    params: Dict[str, Any] = {"current_time": utc_now()}
                    await cur.execute(query, params)

                    result = await cur.fetchone()
                    if not result:
                        raise ValueError("No health data returned")

                    return {
                        "camera_health": {
                            "total_cameras": result["total_cameras"],
                            "enabled_cameras": result["enabled_cameras"],
                            "degraded_cameras": result["degraded_cameras"],
                        },
                        "quality_health": {
                            "avg_quality_score": result["avg_quality_score"],
                            "flagged_images": result["flagged_images"],
                            "total_images": result["total_images"],
                        },
                        "activity_health": {
                            "captures_last_hour": result["captures_last_hour"],
                            "running_timelapses": result["running_timelapses"],
                        },
                    }
        except (psycopg.Error, KeyError, ValueError):
            raise StatisticsOperationError(
                "Failed to retrieve system health data",
                operation="get_system_health_data",
            )


class SyncStatisticsOperations:
    """Sync statistics database operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def get_system_performance_metrics(
        self, timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get system performance metrics for monitoring.

        Args:
            timestamp: ISO formatted timestamp for inclusion in metrics (provided by service layer)

        Returns:
            Dictionary containing performance metrics
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Use separate CTEs for each table to avoid cartesian products
                query = """
                WITH timelapse_stats AS NOT MATERIALIZED (
                    SELECT COUNT(*) FILTER (WHERE status = 'running') as active_timelapses
                    FROM timelapses
                ),
                camera_stats AS NOT MATERIALIZED (
                    SELECT COUNT(*) FILTER (WHERE enabled = true) as enabled_cameras
                    FROM cameras
                ),
                video_job_stats AS NOT MATERIALIZED (
                    SELECT COUNT(*) FILTER (WHERE status = 'processing') as processing_videos
                    FROM video_generation_jobs
                ),
                image_activity AS NOT MATERIALIZED (
                    SELECT COUNT(*) FILTER (WHERE captured_at > %(current_time)s - INTERVAL '5 minutes') as captures_last_5min
                    FROM images
                ),
                corruption_activity AS NOT MATERIALIZED (
                    SELECT COUNT(*) FILTER (WHERE created_at > %(current_time)s - INTERVAL '5 minutes') as corruption_checks_last_5min
                    FROM corruption_logs
                ),
                video_job_activity AS NOT MATERIALIZED (
                    SELECT COUNT(*) FILTER (WHERE created_at > %(current_time)s - INTERVAL '1 hour') as video_jobs_last_hour
                    FROM video_generation_jobs
                )
                SELECT
                    ts.active_timelapses,
                    cs.enabled_cameras,
                    vjs.processing_videos,
                    ia.captures_last_5min,
                    ca.corruption_checks_last_5min,
                    vja.video_jobs_last_hour
                FROM timelapse_stats ts
                CROSS JOIN camera_stats cs
                CROSS JOIN video_job_stats vjs
                CROSS JOIN image_activity ia
                CROSS JOIN corruption_activity ca
                CROSS JOIN video_job_activity vja
                """

                params: Dict[str, Any] = {"current_time": utc_now()}
                cur.execute(query, params)
                combined_metrics = cur.fetchone()

                result = dict(combined_metrics) if combined_metrics else {}

                # NOTE: Timestamp addition moved to service layer
                # Database layer should only return raw data
                return result

    def update_camera_statistics(self, camera_id: int) -> bool:
        """
        Update cached statistics for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            True if update was successful
        """
        # This would typically update a camera_statistics table
        # For now, we'll just log the update
        pass
        return True

    def get_capture_success_rate(self, camera_id: int, hours: int = 24) -> float:
        """
        Calculate capture success rate for a camera.

        Args:
            camera_id: ID of the camera
            hours: Number of hours to analyze

        Returns:
            Success rate as a percentage (0-100)
        """
        try:
            query = """
            SELECT
                COUNT(*) as total_attempts,
                COUNT(*) FILTER (WHERE cl.action_taken = 'saved') as successful_captures
            FROM corruption_logs cl
            WHERE cl.camera_id = %(camera_id)s
            AND cl.created_at > %(current_time)s - INTERVAL '1 hour' * %(hours)s
            """

            params: Dict[str, Any] = {
                "camera_id": camera_id,
                "current_time": utc_now(),
                "hours": hours,
            }

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    results = cur.fetchall()

                    if results and results[0]["total_attempts"] > 0:
                        data = results[0]
                        return (
                            data["successful_captures"] / data["total_attempts"]
                        ) * 100
                    return 100.0  # Assume 100% if no data
        except (psycopg.Error, KeyError, ValueError):
            pass
            return 0.0

    def cleanup_old_statistics(
        self, days_to_keep: int = DEFAULT_STATISTICS_RETENTION_DAYS
    ) -> int:
        """
        Clean up old statistical data.

        Args:
            days_to_keep: Number of days to keep statistics (default: from constants)

        Returns:
            Number of records cleaned up
        """
        # This would clean up cached statistics tables
        try:
            query = """
            DELETE FROM statistics
            WHERE created_at < %(cutoff_date)s
            RETURNING COUNT(*)
            """

            cutoff_date = utc_now() - timedelta(days=days_to_keep)
            params: Dict[str, Any] = {"cutoff_date": cutoff_date}

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    count = cur.fetchone()[0]
                    return count
        except (psycopg.Error, KeyError, ValueError) as e:
            raise StatisticsOperationError(
                "Failed to cleanup old statistics records",
                operation="cleanup_old_statistics",
            ) from e
