# backend/app/services/corruption_pipeline/services/statistics_service.py
"""
Corruption Statistics Service

Specialized service for collecting, analyzing, and reporting
corruption detection statistics and metrics.

Responsibilities:
- System-wide corruption statistics aggregation
- Camera-specific corruption metrics
- Timelapse quality analysis
- Performance monitoring and reporting
- Trend analysis and reporting
- Data export and reporting capabilities
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from ....services.logger import get_service_logger, LogEmoji
from ....enums import LoggerName

logger = get_service_logger(LoggerName.CORRUPTION_PIPELINE)

from ....database.core import AsyncDatabase, SyncDatabase

from ....constants import (
    DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
)

from ....database.corruption_operations import (
    CorruptionOperations,
    SyncCorruptionOperations,
)


class CorruptionStatisticsService:
    """
    Async corruption statistics service.

    Provides comprehensive statistics and analytics for corruption
    detection across the entire system.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance"""
        self.db = db
        self.db_ops = CorruptionOperations(db)

    async def get_system_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive system-wide corruption statistics.

        Returns:
            Dictionary with detailed system statistics
        """
        try:
            # Get basic corruption stats
            stats = await self.db_ops.get_corruption_stats()

            # Get additional system metrics
            total_cameras = await self.db_ops.get_total_cameras_count()
            degraded_cameras = await self.db_ops.get_degraded_cameras()
            recent_detections = await self.db_ops.get_recent_detections_count()

            # Calculate derived metrics
            degraded_count = len(degraded_cameras)
            healthy_cameras = total_cameras - degraded_count

            # Detection efficiency metrics
            detection_efficiency = 0.0
            if stats.total_detections > 0:
                detection_efficiency = (
                    stats.images_saved / stats.total_detections
                ) * 100

            # Storage impact estimation (rough calculation)
            avg_image_size_mb = 2.5  # Estimate
            storage_saved_mb = stats.images_discarded * avg_image_size_mb

            return {
                "overview": {
                    "total_cameras": total_cameras,
                    "healthy_cameras": healthy_cameras,
                    "degraded_cameras": degraded_count,
                    "cameras_monitoring": total_cameras,
                },
                "detection_stats": {
                    "total_detections": stats.total_detections,
                    "images_saved": stats.images_saved,
                    "images_discarded": stats.images_discarded,
                    "images_retried": stats.images_retried,
                    "detection_efficiency_percent": detection_efficiency,
                },
                "quality_metrics": {
                    "avg_corruption_score": stats.avg_corruption_score,
                    "min_corruption_score": stats.min_corruption_score,
                    "max_corruption_score": stats.max_corruption_score,
                    "quality_threshold": DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
                },
                "performance_metrics": {
                    "avg_processing_time_ms": stats.avg_processing_time_ms,
                    "total_processing_time_hours": (
                        stats.total_detections * stats.avg_processing_time_ms
                    )
                    / (1000 * 3600),
                },
                "recent_activity": {
                    "images_flagged_today": recent_detections["today"],
                    "images_flagged_week": recent_detections["week"],
                    "most_recent_detection": stats.most_recent_detection,
                },
                "storage_impact": {
                    "storage_saved_mb": storage_saved_mb,
                    "storage_saved_gb": storage_saved_mb / 1024,
                },
                "degraded_cameras_detail": [
                    {
                        "camera_id": cam.id,
                        "camera_name": cam.name,
                        "consecutive_failures": cam.consecutive_corruption_failures,
                        "lifetime_glitch_count": cam.lifetime_glitch_count,
                        "last_degraded_at": cam.last_degraded_at,
                    }
                    for cam in degraded_cameras
                ],
                "generated_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Error getting system statistics: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def get_camera_statistics(self, camera_id: int) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary with camera-specific statistics
        """
        try:
            # Get camera corruption stats
            stats = await self.db_ops.get_corruption_stats(camera_id=camera_id)

            # Get camera metadata
            metadata = await self.db_ops.get_camera_corruption_metadata(camera_id)

            # Get camera settings
            camera_settings = await self.db_ops.get_camera_corruption_settings(
                camera_id
            )

            # Calculate camera-specific metrics
            detection_efficiency = 0.0
            if stats.total_detections > 0:
                detection_efficiency = (
                    stats.images_saved / stats.total_detections
                ) * 100

            discard_rate = 0.0
            if stats.total_detections > 0:
                discard_rate = (stats.images_discarded / stats.total_detections) * 100

            return {
                "camera_id": camera_id,
                "detection_stats": {
                    "total_detections": stats.total_detections,
                    "images_saved": stats.images_saved,
                    "images_discarded": stats.images_discarded,
                    "images_retried": stats.images_retried,
                    "detection_efficiency_percent": detection_efficiency,
                    "discard_rate_percent": discard_rate,
                },
                "quality_metrics": {
                    "avg_corruption_score": stats.avg_corruption_score,
                    "min_corruption_score": stats.min_corruption_score,
                    "max_corruption_score": stats.max_corruption_score,
                },
                "performance_metrics": {
                    "avg_processing_time_ms": stats.avg_processing_time_ms,
                },
                "health_metrics": {
                    "consecutive_failures": metadata.get(
                        "consecutive_corruption_failures", 0
                    ),
                    "lifetime_glitch_count": metadata.get("lifetime_glitch_count", 0),
                    "degraded_mode_active": metadata.get("degraded_mode_active", False),
                    "last_degraded_at": metadata.get("last_degraded_at"),
                },
                "settings": {
                    "heavy_detection_enabled": camera_settings.get(
                        "heavy_detection_enabled", False
                    ),
                },
                "most_recent_detection": stats.most_recent_detection,
                "generated_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Error getting camera {camera_id} statistics: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def get_timelapse_quality_statistics(
        self, timelapse_id: int
    ) -> Dict[str, Any]:
        """
        Get quality statistics for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Dictionary with timelapse quality statistics
        """
        try:
            stats = await self.db_ops.get_timelapse_quality_statistics(timelapse_id)

            # Calculate derived metrics
            quality_score = 100.0
            flagged_percentage = 0.0

            if stats.get("total_images", 0) > 0:
                flagged_percentage = (
                    stats.get("flagged_images", 0) / stats["total_images"]
                ) * 100
                quality_score = 100.0 - (
                    flagged_percentage * 2
                )  # Simple quality scoring
                quality_score = max(0.0, min(100.0, quality_score))

            return {
                "timelapse_id": timelapse_id,
                "image_stats": {
                    "total_images": stats.get("total_images", 0),
                    "flagged_images": stats.get("flagged_images", 0),
                    "manual_flags": stats.get("manual_flags", 0),
                    "flagged_percentage": flagged_percentage,
                },
                "quality_metrics": {
                    "avg_corruption_score": stats.get("avg_score", 100.0),
                    "quality_score": quality_score,
                },
                "generated_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Error getting timelapse {timelapse_id} quality statistics: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def get_detection_trends(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get corruption detection trends over time.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with trend analysis
        """
        try:
            # This would require more complex database queries to get time-series data
            # For now, providing a basic structure

            # Get recent corruption logs to analyze trends
            logs_page = await self.db_ops.get_corruption_logs(
                page=1,
                page_size=DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,  # Large page to get recent data
            )

            # Filter logs within the time window
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_logs = [
                log
                for log in logs_page.logs
                if log.created_at and log.created_at > cutoff_time
            ]

            if not recent_logs:
                return {
                    "trend_period_hours": hours,
                    "trend_direction": "insufficient_data",
                    "detection_count": 0,
                    "generated_at": datetime.utcnow(),
                }

            # Basic trend analysis
            total_detections = len(recent_logs)
            avg_score = (
                sum(log.corruption_score for log in recent_logs) / total_detections
            )
            discarded_count = len(
                [log for log in recent_logs if log.action_taken == "discarded"]
            )
            discard_rate = (
                (discarded_count / total_detections) * 100
                if total_detections > 0
                else 0
            )

            # Simple trend direction (would need more sophisticated analysis)
            trend_direction = "stable"  # Placeholder

            return {
                "trend_period_hours": hours,
                "trend_direction": trend_direction,
                "detection_count": total_detections,
                "avg_corruption_score": avg_score,
                "discard_rate_percent": discard_rate,
                "hourly_detection_rate": total_detections / hours,
                "generated_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Error getting detection trends: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get corruption detection performance metrics.

        Returns:
            Dictionary with performance analysis
        """
        try:
            # Get system stats
            stats = await self.db_ops.get_corruption_stats()

            # Calculate performance metrics
            total_processing_time_seconds = (
                stats.total_detections * stats.avg_processing_time_ms
            ) / 1000
            total_processing_time_hours = total_processing_time_seconds / 3600

            # Estimate system impact
            detections_per_hour = 0.0
            if stats.most_recent_detection:
                # Simple estimation - would need more sophisticated calculation
                hours_since_first = 24  # Placeholder
                detections_per_hour = stats.total_detections / hours_since_first

            return {
                "processing_performance": {
                    "avg_processing_time_ms": stats.avg_processing_time_ms,
                    "total_processing_time_hours": total_processing_time_hours,
                    "total_detections": stats.total_detections,
                },
                "system_impact": {
                    "detections_per_hour": detections_per_hour,
                    "cpu_time_saved_by_discarding": stats.images_discarded
                    * 50,  # Estimate
                },
                "efficiency_metrics": {
                    "detection_accuracy": (
                        (stats.images_saved / stats.total_detections * 100)
                        if stats.total_detections > 0
                        else 0
                    ),
                    "false_positive_rate": 0.0,  # Would need manual verification data
                },
                "generated_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Error getting performance metrics: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def export_statistics_report(self, format: str = "json") -> Dict[str, Any]:
        """
        Export comprehensive statistics report.

        Args:
            format: Export format (currently only "json" supported)

        Returns:
            Dictionary with complete statistics export
        """
        try:
            # Gather all statistics
            system_stats = await self.get_system_statistics()
            performance_metrics = await self.get_performance_metrics()
            detection_trends = await self.get_detection_trends(hours=24)

            # Compile comprehensive report
            report = {
                "report_metadata": {
                    "generated_at": datetime.utcnow(),
                    "format": format,
                    "report_type": "corruption_detection_statistics",
                    "version": "1.0",
                },
                "system_statistics": system_stats,
                "performance_metrics": performance_metrics,
                "detection_trends_24h": detection_trends,
                "export_summary": {
                    "total_cameras_analyzed": system_stats["overview"]["total_cameras"],
                    "total_detections_analyzed": system_stats["detection_stats"][
                        "total_detections"
                    ],
                    "report_scope": "system_wide",
                },
            }

            return report

        except Exception as e:
            logger.error(
                f"Error exporting statistics report: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise


class SyncCorruptionStatisticsService:
    """
    Sync corruption statistics service for worker processes.

    Provides basic statistics functionality for worker processes
    that need to report metrics or make decisions based on stats.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance"""
        self.db = db
        self.db_ops = SyncCorruptionOperations(db)

    def get_basic_camera_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get basic statistics for a camera (sync version).

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary with basic camera statistics
        """
        try:
            # Get camera failure stats
            failure_stats = self.db_ops.get_camera_corruption_failure_stats(camera_id)

            return {
                "camera_id": camera_id,
                "consecutive_failures": failure_stats.get(
                    "consecutive_corruption_failures", 0
                ),
                "lifetime_glitch_count": failure_stats.get("lifetime_glitch_count", 0),
                "degraded_mode_active": failure_stats.get(
                    "degraded_mode_active", False
                ),
                "failures_last_hour": failure_stats.get("failures_last_hour", 0),
                "failures_last_30min": failure_stats.get("failures_last_30min", 0),
            }

        except Exception as e:
            logger.error(
                f"Error getting basic camera {camera_id} stats: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return {
                "camera_id": camera_id,
                "consecutive_failures": 0,
                "lifetime_glitch_count": 0,
                "degraded_mode_active": False,
                "failures_last_hour": 0,
                "failures_last_30min": 0,
            }
