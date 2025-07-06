# backend/app/database/statistics_operations.py
"""
Statistics database operations module - Composition Pattern.

This module handles all statistics-related database operations including:
- System health aggregation
- Dashboard data collection
- Camera/timelapse statistics
- Performance metrics
"""

from typing import List, Dict, Optional, Any
from datetime import datetime

from loguru import logger
from app.models.statistics_model import (
    CameraStatsModel,
    TimelapseStatsModel,
    ImageStatsModel,
    VideoStatsModel,
    AutomationStatsModel,
    RecentActivityModel,
    DashboardStatsModel,
    CameraPerformanceModel,
    QualityTrendDataPoint,
    StorageStatsModel,
    SystemHealthScoreModel,
)
from app.constants import (
    VIDEO_QUEUE_WARNING_THRESHOLD,
    VIDEO_QUEUE_ERROR_THRESHOLD,
    HEALTH_CAMERA_WEIGHT,
    HEALTH_QUALITY_WEIGHT,
    HEALTH_ACTIVITY_WEIGHT,
    HEALTH_DEGRADED_PENALTY,
    HEALTH_FLAGGED_PENALTY,
    HEALTH_ACTIVITY_PERFECT_SCORE,
    DEFAULT_STATISTICS_RETENTION_DAYS,
)
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_sync,
)

# Import database core for composition
from .core import AsyncDatabase, SyncDatabase


class StatisticsOperations:
    """Statistics database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db

    async def get_dashboard_stats(self) -> DashboardStatsModel:
        """
        Get comprehensive dashboard statistics.

        Returns:
            Dictionary containing system-wide statistics
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                    SELECT 
                        COUNT(*) as total_cameras,
                        COUNT(CASE WHEN enabled = true THEN 1 END) as enabled_cameras,
                        COUNT(CASE WHEN degraded_mode_active = true THEN 1 END) as degraded_cameras,
                        COUNT(CASE WHEN corruption_detection_heavy = true THEN 1 END) as cameras_with_heavy_detection
                    FROM cameras
                    """
                    )
                    camera_stats = await cur.fetchone()
                    camera_model = CameraStatsModel(**camera_stats)

                    await cur.execute(
                        """
                    SELECT
                        COUNT(*) as total_timelapses,
                        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_timelapses,
                        COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_timelapses,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_timelapses
                    FROM timelapses
                    """
                    )
                    timelapse_stats = await cur.fetchone()
                    timelapse_model = TimelapseStatsModel(**timelapse_stats)

                    await cur.execute(
                        """
                    SELECT
                        COUNT(*) as total_images,
                        COUNT(CASE WHEN captured_at > NOW() - INTERVAL '24 hours' THEN 1 END) as images_today,
                        COUNT(CASE WHEN is_flagged = true THEN 1 END) as flagged_images,
                        AVG(CASE WHEN corruption_score IS NOT NULL THEN corruption_score ELSE 100 END) as avg_quality_score,
                        SUM(file_size) as total_storage_bytes
                    FROM images
                    """
                    )
                    image_stats = await cur.fetchone()
                    image_model = ImageStatsModel(**image_stats)

                    await cur.execute(
                        """
                    SELECT
                        COUNT(*) as total_videos,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_videos,
                        COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_videos,
                        COUNT(CASE WHEN status = 'canceled' THEN 1 END) as canceled_videos,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_videos,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN file_size END), 0) as total_file_size,
                        COALESCE(AVG(CASE WHEN status = 'completed' THEN duration_seconds END), 0) as avg_duration
                    FROM videos
                    """
                    )
                    video_stats = await cur.fetchone()
                    video_model = VideoStatsModel(**video_stats)

                    await cur.execute(
                        """
                    SELECT
                        COUNT(*) as total_jobs,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_jobs,
                        COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_jobs,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_jobs,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_jobs
                    FROM video_generation_jobs
                    """
                    )
                    automation_stats = await cur.fetchone()
                    
                    # Calculate queue health using constants
                    pending_jobs = automation_stats["pending_jobs"]
                    if pending_jobs >= VIDEO_QUEUE_ERROR_THRESHOLD:
                        queue_health = "unhealthy"
                    elif pending_jobs >= VIDEO_QUEUE_WARNING_THRESHOLD:
                        queue_health = "degraded"
                    else:
                        queue_health = "healthy"
                    
                    automation_model = AutomationStatsModel(
                        **automation_stats,
                        queue_health=queue_health
                    )

                    await cur.execute(
                        """
                    SELECT
                        COUNT(CASE WHEN captured_at > NOW() - INTERVAL '1 hour' THEN 1 END) as captures_last_hour,
                        COUNT(CASE WHEN captured_at > NOW() - INTERVAL '24 hours' THEN 1 END) as captures_last_24h
                    FROM images
                    """
                    )
                    recent_activity = await cur.fetchone()
                    recent_activity_model = RecentActivityModel(**recent_activity)

                    return DashboardStatsModel(
                        camera=camera_model,
                        timelapse=timelapse_model,
                        image=image_model,
                        video=video_model,
                        automation=automation_model,
                        recent_activity=recent_activity_model,
                    )
        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {e}")
            return DashboardStatsModel(
                camera=CameraStatsModel(
                    total_cameras=0,
                    enabled_cameras=0,
                    degraded_cameras=0,
                    cameras_with_heavy_detection=0,
                ),
                timelapse=TimelapseStatsModel(
                    total_timelapses=0,
                    running_timelapses=0,
                    paused_timelapses=0,
                    completed_timelapses=0,
                ),
                image=ImageStatsModel(
                    total_images=0,
                    images_today=0,
                    flagged_images=0,
                    avg_quality_score=0,
                    total_storage_bytes=0,
                ),
                video=VideoStatsModel(
                    total_videos=0,
                    completed_videos=0,
                    processing_videos=0,
                    failed_videos=0,
                    canceled_videos=0,
                    total_file_size=0,
                    avg_duration=0,
                ),
                automation=AutomationStatsModel(
                    total_jobs=0,
                    pending_jobs=0,
                    processing_jobs=0,
                    completed_jobs=0,
                    failed_jobs=0,
                    queue_health="healthy",
                ),
                recent_activity=RecentActivityModel(
                    captures_last_hour=0, captures_last_24h=0
                ),
            )

    async def get_camera_performance_stats(
        self, camera_id: Optional[int] = None
    ) -> List[CameraPerformanceModel]:
        """
        Get camera performance statistics.

        Args:
            camera_id: Optional camera ID to filter by

        Returns:
            List of camera performance dictionaries
        """
        where_clause = "WHERE c.id = %s" if camera_id else ""
        params = (camera_id,) if camera_id else ()

        query = f"""
        SELECT
            c.id,
            c.name,
            c.enabled,
            c.degraded_mode_active,
            c.lifetime_glitch_count,
            c.consecutive_corruption_failures,
            COUNT(i.id) as total_images,
            COUNT(CASE WHEN i.captured_at > NOW() - INTERVAL '24 hours' THEN 1 END) as images_today,
            COUNT(CASE WHEN i.captured_at > NOW() - INTERVAL '7 days' THEN 1 END) as images_week,
            COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as flagged_images,
            AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
            MAX(i.captured_at) as last_capture_at,
            COUNT(v.id) as total_videos,
            SUM(i.file_size) as total_storage_bytes
        FROM cameras c
        LEFT JOIN timelapses t ON c.id = t.camera_id
        LEFT JOIN images i ON t.id = i.timelapse_id
        LEFT JOIN videos v ON t.id = v.timelapse_id
        {where_clause}
        GROUP BY c.id, c.name, c.enabled, c.degraded_mode_active,
                c.lifetime_glitch_count, c.consecutive_corruption_failures
        ORDER BY c.name
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [CameraPerformanceModel(**row) for row in rows]

    async def get_quality_trend_data(
        self, camera_id: Optional[int] = None, hours: int = 24
    ) -> List[QualityTrendDataPoint]:
        """
        Get quality trend data over time.

        Args:
            camera_id: Optional camera ID to filter by
            hours: Number of hours of data to retrieve

        Returns:
            List of quality trend data points
        """
        where_clause = "AND t.camera_id = %s" if camera_id else ""
        params = [hours]
        if camera_id:
            params.append(camera_id)

        query = f"""
        SELECT
            DATE_TRUNC('hour', i.captured_at) as hour,
            AVG(CASE WHEN i.corruption_score IS NOT NULL THEN i.corruption_score ELSE 100 END) as avg_quality_score,
            COUNT(*) as image_count,
            COUNT(CASE WHEN i.is_flagged = true THEN 1 END) as flagged_count
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        WHERE i.captured_at > NOW() - INTERVAL '%s hours'
        {where_clause}
        GROUP BY DATE_TRUNC('hour', i.captured_at)
        ORDER BY hour
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [QualityTrendDataPoint(**row) for row in rows]

    async def get_storage_statistics(self) -> StorageStatsModel:
        """
        Get storage usage statistics.

        Returns:
            Dictionary containing storage statistics
        """
        query = """
        SELECT
            SUM(i.file_size) as total_image_storage,
            SUM(v.file_size) as total_video_storage,
            COUNT(i.id) as total_images,
            COUNT(v.id) as total_videos,
            AVG(i.file_size) as avg_image_size,
            AVG(v.file_size) as avg_video_size
        FROM images i
        FULL OUTER JOIN videos v ON 1=1
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

    async def get_system_health_score(self) -> SystemHealthScoreModel:
        """
        Calculate system health score based on various metrics.

        Returns:
            Dictionary containing health score and component scores
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                    SELECT
                        COUNT(*) as total_cameras,
                        COUNT(CASE WHEN enabled = true THEN 1 END) as enabled_cameras,
                        COUNT(CASE WHEN degraded_mode_active = true THEN 1 END) as degraded_cameras
                    FROM cameras
                    """
                    )
                    camera_health = await cur.fetchone()

                    await cur.execute(
                        """
                    SELECT
                        AVG(CASE WHEN corruption_score IS NOT NULL THEN corruption_score ELSE 100 END) as avg_quality_score,
                        COUNT(CASE WHEN is_flagged = true THEN 1 END) as flagged_images,
                        COUNT(*) as total_images
                    FROM images
                    WHERE captured_at > NOW() - INTERVAL '24 hours'
                    """
                    )
                    quality_health = await cur.fetchone()

                    await cur.execute(
                        """
                    SELECT
                        COUNT(CASE WHEN captured_at > NOW() - INTERVAL '1 hour' THEN 1 END) as captures_last_hour,
                        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_timelapses
                    FROM images i
                    FULL OUTER JOIN timelapses t ON 1=1
                    """
                    )
                    activity_health = await cur.fetchone()

                    camera_score = 100
                    if camera_health["total_cameras"] > 0:
                        enabled_ratio = (
                            camera_health["enabled_cameras"] or 0
                        ) / camera_health["total_cameras"]
                        degraded_ratio = (
                            camera_health["degraded_cameras"] or 0
                        ) / camera_health["total_cameras"]
                        camera_score = max(
                            0, (enabled_ratio * 100) - (degraded_ratio * HEALTH_DEGRADED_PENALTY)
                        )

                    quality_score = quality_health.get("avg_quality_score") or 100
                    if quality_health["total_images"] > 0:
                        flagged_ratio = (
                            quality_health["flagged_images"] or 0
                        ) / quality_health["total_images"]
                        quality_score = max(0, quality_score - (flagged_ratio * HEALTH_FLAGGED_PENALTY))

                    activity_score = min(
                        100, (activity_health["captures_last_hour"] or 0) * HEALTH_ACTIVITY_PERFECT_SCORE
                    )  # Configurable perfect score threshold

                    # Weighted overall health score
                    overall_score = (
                        (camera_score * HEALTH_CAMERA_WEIGHT)
                        + (quality_score * HEALTH_QUALITY_WEIGHT)
                        + (activity_score * HEALTH_ACTIVITY_WEIGHT)
                    )

                    return SystemHealthScoreModel(
                        overall_health_score=round(overall_score, 1),
                        camera_health_score=round(camera_score, 1),
                        quality_health_score=round(quality_score, 1),
                        activity_health_score=round(activity_score, 1),
                        component_details={
                            "camera_health": camera_health,
                            "quality_health": quality_health,
                            "activity_health": activity_health,
                        },
                    )
        except Exception as e:
            logger.error(f"Failed to get system health score: {e}")
            return SystemHealthScoreModel(
                overall_health_score=0.0,
                camera_health_score=0.0,
                quality_health_score=0.0,
                activity_health_score=0.0,
                component_details={},
            )


class SyncStatisticsOperations:
    """Sync statistics database operations for worker processes."""

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance."""
        self.db = db

    def get_system_performance_metrics(self, timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Get system performance metrics for monitoring.

        Args:
            timestamp: ISO formatted timestamp for inclusion in metrics (provided by service layer)

        Returns:
            Dictionary containing performance metrics
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Active operations
                cur.execute(
                    """
                SELECT
                    COUNT(CASE WHEN t.status = 'running' THEN 1 END) as active_timelapses,
                    COUNT(CASE WHEN c.enabled = true THEN 1 END) as enabled_cameras,
                    COUNT(CASE WHEN vgj.status = 'processing' THEN 1 END) as processing_videos
                FROM timelapses t
                FULL OUTER JOIN cameras c ON 1=1
                FULL OUTER JOIN video_generation_jobs vgj ON 1=1
                """
                )
                active_metrics = cur.fetchone()

                # Recent activity
                cur.execute(
                    """
                SELECT
                    COUNT(CASE WHEN i.captured_at > NOW() - INTERVAL '5 minutes' THEN 1 END) as captures_last_5min,
                    COUNT(CASE WHEN cl.created_at > NOW() - INTERVAL '5 minutes' THEN 1 END) as corruption_checks_last_5min,
                    COUNT(CASE WHEN vgj.created_at > NOW() - INTERVAL '1 hour' THEN 1 END) as video_jobs_last_hour
                FROM images i
                FULL OUTER JOIN corruption_logs cl ON 1=1
                FULL OUTER JOIN video_generation_jobs vgj ON 1=1
                """
                )
                recent_metrics = cur.fetchone()

                result = {
                    **active_metrics,
                    **recent_metrics,
                }
                
                # Add timestamp if provided by service layer
                if timestamp:
                    result["timestamp"] = timestamp
                    
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
        logger.debug(f"Camera statistics updated for camera {camera_id}")
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
                COUNT(CASE WHEN cl.action_taken = 'saved' THEN 1 END) as successful_captures
            FROM corruption_logs cl
            WHERE cl.camera_id = %s
            AND cl.created_at > NOW() - INTERVAL '%s hours'
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (camera_id, hours))
                    results = cur.fetchall()

                    if results and results[0]["total_attempts"] > 0:
                        data = results[0]
                        return (
                            data["successful_captures"] / data["total_attempts"]
                        ) * 100
                    return 100.0  # Assume 100% if no data
        except Exception as e:
            logger.error(
                f"Failed to get capture success rate for camera {camera_id}: {e}"
            )
            return 0.0

    def cleanup_old_statistics(self, days_to_keep: int = DEFAULT_STATISTICS_RETENTION_DAYS) -> int:
        """
        Clean up old statistical data.

        Args:
            days_to_keep: Number of days to keep statistics (default: from constants)

        Returns:
            Number of records cleaned up
        """
        # This would clean up cached statistics tables
        # For now, just return 0 as we don't have specific stats tables yet
        logger.debug(f"Statistics cleanup completed (keeping {days_to_keep} days)")
        return 0
