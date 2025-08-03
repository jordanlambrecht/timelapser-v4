# backend/app/services/corruption_pipeline/services/health_service.py
"""
Corruption Health Monitoring Service

Specialized service for monitoring corruption detection health,
managing degraded mode, and tracking system-wide corruption metrics.

Responsibilities:
- Camera health assessment based on corruption patterns
- Degraded mode trigger evaluation and management
- System-wide corruption health monitoring
- Health-based alerting and notifications
- Performance impact monitoring
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ....services.logger import get_service_logger, LogEmoji
from ....enums import LoggerName

logger = get_service_logger(LoggerName.CORRUPTION_PIPELINE)

from ....database.core import AsyncDatabase, SyncDatabase
from ....models.corruption_model import (
    CameraHealthAssessment,
    CameraWithCorruption,
    CorruptionAnalysisStats,
)
from ....constants import (
    DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
    DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES,
    DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE,
    MIN_CORRUPTION_ANALYSIS_SAMPLE_SIZE,
    HEALTH_DEGRADED_MODE_PENALTY,
    HEALTH_CONSECUTIVE_FAILURES_HIGH_THRESHOLD,
    HEALTH_CONSECUTIVE_FAILURES_HIGH_PENALTY,
    HEALTH_CONSECUTIVE_FAILURES_MEDIUM_THRESHOLD,
    HEALTH_CONSECUTIVE_FAILURES_MEDIUM_PENALTY,
    HEALTH_POOR_QUALITY_THRESHOLD,
    HEALTH_POOR_QUALITY_PENALTY,
    HEALTH_AVERAGE_QUALITY_THRESHOLD,
    HEALTH_AVERAGE_QUALITY_PENALTY,
)

from ....database.corruption_operations import (
    CorruptionOperations,
    SyncCorruptionOperations,
)


class CorruptionHealthService:
    """
    Async corruption health monitoring service.

    Provides comprehensive health monitoring for corruption detection
    across cameras and system-wide metrics.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance"""
        self.db = db
        self.db_ops = CorruptionOperations(db)

    async def assess_camera_health(self, camera_id: int) -> CameraHealthAssessment:
        """
        Comprehensive health assessment for a specific camera.

        Args:
            camera_id: ID of the camera to assess

        Returns:
            CameraHealthAssessment with detailed health metrics
        """
        try:
            # Get camera corruption metadata
            metadata = await self.db_ops.get_camera_corruption_metadata(camera_id)

            # Get corruption statistics
            stats = await self.db_ops.get_corruption_stats(camera_id=camera_id)

            # Calculate health score using established constants
            health_score = 100.0
            penalties = []
            issues = []
            recommendations = []

            # Degraded mode penalty
            if metadata.get("degraded_mode_active", False):
                health_score -= HEALTH_DEGRADED_MODE_PENALTY
                penalties.append(
                    f"Degraded mode active (-{HEALTH_DEGRADED_MODE_PENALTY})"
                )
                issues.append(
                    "Camera is in degraded mode - corruption detection limited"
                )
                recommendations.append(
                    "Investigate camera feed quality and connection stability"
                )

            # Consecutive failures penalty
            consecutive_failures = metadata.get("consecutive_corruption_failures", 0)
            if consecutive_failures >= HEALTH_CONSECUTIVE_FAILURES_HIGH_THRESHOLD:
                health_score -= HEALTH_CONSECUTIVE_FAILURES_HIGH_PENALTY
                penalties.append(
                    f"High consecutive failures: {consecutive_failures} (-{HEALTH_CONSECUTIVE_FAILURES_HIGH_PENALTY})"
                )
                issues.append(
                    f"Camera has {consecutive_failures} consecutive corruption failures"
                )
                recommendations.append(
                    "Check camera feed stability and image quality settings"
                )
            elif consecutive_failures >= HEALTH_CONSECUTIVE_FAILURES_MEDIUM_THRESHOLD:
                health_score -= HEALTH_CONSECUTIVE_FAILURES_MEDIUM_PENALTY
                penalties.append(
                    f"Medium consecutive failures: {consecutive_failures} (-{HEALTH_CONSECUTIVE_FAILURES_MEDIUM_PENALTY})"
                )

            # Average corruption score penalties
            avg_score = stats.avg_corruption_score
            if avg_score >= HEALTH_POOR_QUALITY_THRESHOLD:
                health_score -= HEALTH_POOR_QUALITY_PENALTY
                penalties.append(
                    f"Poor average quality: {avg_score:.1f} (-{HEALTH_POOR_QUALITY_PENALTY})"
                )
                issues.append(f"Average corruption score is high: {avg_score:.1f}")
                recommendations.append(
                    "Review camera positioning, lens cleanliness, and lighting conditions"
                )
            elif avg_score >= HEALTH_AVERAGE_QUALITY_THRESHOLD:
                health_score -= HEALTH_AVERAGE_QUALITY_PENALTY
                penalties.append(
                    f"Average quality: {avg_score:.1f} (-{HEALTH_AVERAGE_QUALITY_PENALTY})"
                )

            # Detection ratio analysis
            if stats.total_detections > 10:
                discard_ratio = stats.images_discarded / stats.total_detections
                if discard_ratio > 0.3:  # More than 30% discarded
                    penalty = min(discard_ratio * 20, 15.0)
                    health_score -= penalty
                    penalties.append(
                        f"High discard ratio: {discard_ratio:.1%} (-{penalty:.1f})"
                    )
                    issues.append(
                        f"High percentage of images being discarded: {discard_ratio:.1%}"
                    )
                    recommendations.append(
                        "Investigate image quality issues or adjust detection thresholds"
                    )

            # Processing time analysis
            if stats.avg_processing_time_ms > 100.0:  # Over 100ms average
                penalty = min((stats.avg_processing_time_ms - 100) / 10, 5.0)
                health_score -= penalty
                penalties.append(
                    f"Slow processing: {stats.avg_processing_time_ms:.1f}ms (-{penalty:.1f})"
                )
                issues.append(
                    f"Corruption detection is slow: {stats.avg_processing_time_ms:.1f}ms average"
                )

            # Ensure health score doesn't go below 0
            health_score = max(0.0, health_score)

            # Determine health status
            if health_score >= 90.0:
                status = "excellent"
            elif health_score >= 80.0:
                status = "healthy"
            elif health_score >= 60.0:
                status = "monitoring"
            elif health_score >= 40.0:
                status = "degraded"
            else:
                status = "critical"

            # Add general recommendations based on status
            if status in ["degraded", "critical"]:
                recommendations.append(
                    "Consider temporary camera maintenance or replacement"
                )
                recommendations.append(
                    "Review camera feed configuration and network stability"
                )
            elif status == "monitoring":
                recommendations.append(
                    "Monitor camera closely for any further degradation"
                )

            # Create metrics dictionary
            metrics_dict = {
                "degraded_mode_active": metadata.get("degraded_mode_active", False),
                "consecutive_failures": consecutive_failures,
                "lifetime_glitch_count": metadata.get("lifetime_glitch_count", 0),
                "last_degraded_at": metadata.get("last_degraded_at"),
                "corruption_stats": (
                    stats.model_dump() if hasattr(stats, "model_dump") else stats
                ),
                "penalties": penalties,
            }

            return CameraHealthAssessment(
                camera_id=camera_id,
                health_score=int(health_score),
                health_status=status,
                issues=issues,
                recommendations=recommendations,
                # TODO: Use timezone-aware datetime from settings instead of UTC
                # Should use get_timezone_aware_timestamp_async(settings_service)
                assessment_timestamp=datetime.utcnow(),
                metrics=metrics_dict,
            )

        except Exception as e:
            logger.error(
                f"Error assessing camera {camera_id} health: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def get_system_health_overview(self) -> Dict[str, Any]:
        """
        Get system-wide corruption detection health overview.

        Returns:
            Dictionary with system health metrics and status
        """
        try:
            # Get basic system stats
            system_stats = await self.db_ops.get_corruption_stats()
            total_cameras = await self.db_ops.get_total_cameras_count()
            degraded_cameras = await self.db_ops.get_degraded_cameras()
            recent_detections = await self.db_ops.get_recent_detections_count()

            # Calculate system health metrics
            degraded_count = len(degraded_cameras)
            healthy_cameras = total_cameras - degraded_count

            # System health score calculation
            system_health_score = 100.0

            # Degraded cameras penalty
            if total_cameras > 0:
                degraded_ratio = degraded_count / total_cameras
                if degraded_ratio > 0.1:  # More than 10% degraded
                    penalty = degraded_ratio * 50  # Up to 50 point penalty
                    system_health_score -= penalty

            # High system-wide corruption penalty
            if system_stats.avg_corruption_score > 50.0:
                penalty = (system_stats.avg_corruption_score - 50.0) / 2
                system_health_score -= penalty

            # Recent detection failure rate
            if system_stats.total_detections > 0:
                discard_ratio = (
                    system_stats.images_discarded / system_stats.total_detections
                )
                if discard_ratio > 0.2:  # More than 20% system-wide
                    penalty = discard_ratio * 30
                    system_health_score -= penalty

            system_health_score = max(0.0, system_health_score)

            # Determine system status
            if system_health_score >= 90.0:
                system_status = "excellent"
            elif system_health_score >= 80.0:
                system_status = "healthy"
            elif system_health_score >= 60.0:
                system_status = "monitoring"
            elif system_health_score >= 40.0:
                system_status = "degraded"
            else:
                system_status = "critical"

            return {
                "system_health_score": system_health_score,
                "system_status": system_status,
                "total_cameras": total_cameras,
                "healthy_cameras": healthy_cameras,
                "degraded_cameras": degraded_count,
                "degraded_cameras_list": [
                    {
                        "camera_id": cam.id,
                        "camera_name": cam.name,
                        "last_degraded_at": cam.last_degraded_at,
                        "consecutive_failures": cam.consecutive_corruption_failures,
                    }
                    for cam in degraded_cameras
                ],
                "corruption_stats": {
                    "total_detections": system_stats.total_detections,
                    "images_saved": system_stats.images_saved,
                    "images_discarded": system_stats.images_discarded,
                    "avg_corruption_score": system_stats.avg_corruption_score,
                    "avg_processing_time_ms": system_stats.avg_processing_time_ms,
                },
                "recent_activity": {
                    "images_flagged_today": recent_detections["today"],
                    "images_flagged_week": recent_detections["week"],
                },
                "last_updated": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(
                f"Error getting system health overview: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def check_degraded_mode_triggers(self) -> List[Dict[str, Any]]:
        """
        Check all cameras for degraded mode trigger conditions.

        Returns:
            List of cameras that should enter degraded mode
        """
        try:
            # Get detection thresholds
            thresholds = await self.db_ops.get_corruption_settings()

            # This would need to query all cameras and check their failure patterns
            # For now, returning empty list as this requires more complex logic
            cameras_to_degrade = []

            return cameras_to_degrade

        except Exception as e:
            logger.error(
                f"Error checking degraded mode triggers: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def reset_camera_health(self, camera_id: int) -> bool:
        """
        Reset camera health metrics and exit degraded mode.

        Args:
            camera_id: ID of the camera to reset

        Returns:
            True if reset was successful
        """
        try:
            return await self.db_ops.reset_camera_degraded_mode(camera_id)

        except Exception as e:
            logger.error(
                f"Error resetting camera {camera_id} health: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise

    async def get_health_trends(
        self, camera_id: int, hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get health trends for a camera over time.

        Args:
            camera_id: ID of the camera
            hours: Number of hours of history to analyze

        Returns:
            Dictionary with trend analysis
        """
        try:
            # Get corruption history
            history = await self.db_ops.get_camera_corruption_history(camera_id, hours)

            if not history:
                return {
                    "camera_id": camera_id,
                    "trend_period_hours": hours,
                    "trend": "insufficient_data",
                    "score_trend": [],
                    "detection_count": 0,
                }

            # Analyze trends
            scores = [entry.corruption_score for entry in history]
            avg_score = sum(scores) / len(scores)

            # Simple trend analysis
            if len(scores) >= 2:
                recent_avg = sum(scores[: len(scores) // 2]) / (len(scores) // 2)
                older_avg = sum(scores[len(scores) // 2 :]) / (
                    len(scores) - len(scores) // 2
                )

                if recent_avg < older_avg - 10:
                    trend = "improving"
                elif recent_avg > older_avg + 10:
                    trend = "degrading"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            return {
                "camera_id": camera_id,
                "trend_period_hours": hours,
                "trend": trend,
                "avg_score": avg_score,
                "score_range": [min(scores), max(scores)],
                "detection_count": len(history),
                "recent_detections": len(
                    [
                        h
                        for h in history
                        if h.created_at is not None
                        and h.created_at > datetime.utcnow() - timedelta(hours=6)
                    ]
                ),
            }

        except Exception as e:
            logger.error(
                f"Error getting health trends for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise


class SyncCorruptionHealthService:
    """
    Sync corruption health monitoring service for worker processes.

    Provides essential health monitoring functionality for worker
    processes that need to make degraded mode decisions.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance"""
        self.db = db
        self.db_ops = SyncCorruptionOperations(db)

    def check_degraded_mode_trigger(self, camera_id: int) -> bool:
        """
        Check if a camera should enter degraded mode (sync version).

        Args:
            camera_id: ID of the camera to check

        Returns:
            True if camera should enter degraded mode
        """
        try:
            # Get settings for degraded mode evaluation
            settings = self.db_ops.get_corruption_settings()

            # Use the existing logic from database operations
            return self.db_ops.check_degraded_mode_trigger(camera_id, settings)

        except Exception as e:
            logger.error(
                f"Error checking degraded mode trigger for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return False

    def set_camera_degraded_mode(self, camera_id: int, is_degraded: bool) -> bool:
        """
        Set camera degraded mode status (sync version).

        Args:
            camera_id: ID of the camera
            is_degraded: Whether camera should be in degraded mode

        Returns:
            True if update was successful
        """
        try:
            return self.db_ops.set_camera_degraded_mode(camera_id, is_degraded)

        except Exception as e:
            logger.error(
                f"Error setting degraded mode for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return False

    def get_camera_failure_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get camera failure statistics (sync version).

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary with failure statistics
        """
        try:
            return self.db_ops.get_camera_corruption_failure_stats(camera_id)

        except Exception as e:
            logger.error(
                f"Error getting failure stats for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return {}

    def reset_camera_corruption_failures(self, camera_id: int) -> bool:
        """
        Reset camera corruption failure counters (sync version).

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful
        """
        try:
            return self.db_ops.reset_camera_corruption_failures(camera_id)

        except Exception as e:
            logger.error(
                f"Error resetting corruption failures for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return False
