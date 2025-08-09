"""
Statistics service layer for system-wide metrics aggregation.

This service handles ONLY system-wide statistics aggregation and coordination.
Domain-specific statistics should be handled by their respective services:
- Camera statistics → CameraService
- Video statistics → VideoPipeline (VideoWorkflowService)
- Timelapse statistics → TimelapseService
- Image statistics → ImageService
- Corruption statistics → CorruptionService
"""

from typing import Any, Dict, List, Optional

from ..constants import (
    DEFAULT_DASHBOARD_QUALITY_TREND_DAYS,
)
from ..database.core import AsyncDatabase, SyncDatabase
from ..database.statistics_operations import (
    StatisticsOperations,
    SyncStatisticsOperations,
)
from ..enums import LoggerName, LogSource
from ..models.statistics_model import (
    CameraPerformanceModel,
    DashboardStatsModel,
    EnhancedDashboardStatsModel,
    QualityTrendDataPoint,
    StorageStatsModel,
    SystemHealthScoreModel,
    SystemOverviewModel,
)
from ..services.logger import get_service_logger
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
)
from .settings_service import SettingsService, SyncSettingsService

logger = get_service_logger(LoggerName.STATISTICS_SERVICE, LogSource.SYSTEM)


class StatisticsService:
    """
    System-wide metrics aggregation business logic.

    Responsibilities:
    - Cross-service statistics compilation
    - Health overview generation
    - Performance metrics calculation
    - Dashboard data preparation

    NOTE: Domain-specific statistics are handled by respective services.
    This service only aggregates and coordinates system-wide metrics.

    Interactions:
    - Coordinates with domain services to collect statistics
    - Uses StatisticsOperations for complex cross-table queries
    - Provides aggregated system views
    """

    def __init__(self, db: AsyncDatabase, stats_ops, settings_service):
        """
        Initialize service with injected dependencies.

        Args:
            db: AsyncDatabase instance
            stats_ops: Injected StatisticsOperations singleton
            settings_service: Injected SettingsService singleton
        """
        self.db = db
        self.stats_ops = stats_ops
        self.settings_service = settings_service

    async def get_dashboard_stats(self) -> DashboardStatsModel:
        """Get comprehensive dashboard statistics from operations layer."""
        try:
            return await self.stats_ops.get_dashboard_stats()
        except Exception as e:
            logger.error(
                "Failed to get dashboard stats",
                exception=e,
                extra_context={"operation": "get_dashboard_stats"},
            )
            raise

    async def get_enhanced_dashboard_stats(self) -> "EnhancedDashboardStatsModel":
        """Get comprehensive dashboard statistics with system overview."""
        try:
            # Get base dashboard stats
            dashboard_stats = await self.stats_ops.get_dashboard_stats()

            # Get storage statistics
            storage_stats = await self.stats_ops.get_storage_statistics()

            # Get quality trend data (default 7 days, system-wide)
            quality_trends = await self.stats_ops.get_quality_trend_data(
                camera_id=None,  # System-wide trends
                hours=DEFAULT_DASHBOARD_QUALITY_TREND_DAYS * 24,  # Default 7 days
            )

            # Get camera performance data (system-wide)
            camera_performance = await self.stats_ops.get_camera_performance_stats(
                camera_id=None  # System-wide performance data
            )

            # Get system health data
            health_score_dict = await self.stats_ops.get_system_health_data()
            health_score = SystemHealthScoreModel(**health_score_dict)

            # Get timezone-aware timestamp
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Calculate system overview metrics (business logic in service layer)
            total_entities = (
                dashboard_stats.camera.total_cameras
                + dashboard_stats.timelapse.total_timelapses
                + dashboard_stats.image.total_images
                + dashboard_stats.video.total_videos
            )

            active_operations = (
                dashboard_stats.timelapse.running_timelapses
                + dashboard_stats.automation.pending_jobs
                + dashboard_stats.automation.processing_jobs
            )

            system_status = (
                "operational"
                if dashboard_stats.camera.enabled_cameras > 0
                else "standby"
            )

            # Create system overview model
            system_overview = SystemOverviewModel(
                total_entities=total_entities,
                active_operations=active_operations,
                system_status=system_status,
                last_updated=timestamp.isoformat(),
            )

            # Create enhanced dashboard model
            enhanced_stats = EnhancedDashboardStatsModel(
                camera=dashboard_stats.camera,
                timelapse=dashboard_stats.timelapse,
                image=dashboard_stats.image,
                video=dashboard_stats.video,
                automation=dashboard_stats.automation,
                recent_activity=dashboard_stats.recent_activity,
                system_overview=system_overview,
                storage=storage_stats,
                quality_trends=quality_trends,
                camera_performance=camera_performance,
                health_score=health_score,
            )

            # SSE broadcasting handled by higher-level service layer

            return enhanced_stats

        except Exception as e:
            logger.error(
                "Failed to get enhanced dashboard stats",
                exception=e,
                extra_context={"operation": "get_enhanced_dashboard_stats"},
            )
            raise

    async def get_camera_performance_stats(
        self, camera_id: Optional[int] = None
    ) -> List[CameraPerformanceModel]:
        """Get camera performance statistics (delegated to operations layer)."""
        try:
            return await self.stats_ops.get_camera_performance_stats(camera_id)
        except Exception as e:
            logger.error(
                "Failed to get camera performance stats",
                exception=e,
                extra_context={"operation": "get_camera_performance_stats"},
            )
            raise

    async def get_quality_trend_data(
        self,
        camera_id: Optional[int] = None,
        hours: int = DEFAULT_DASHBOARD_QUALITY_TREND_DAYS * 24,
    ) -> List[QualityTrendDataPoint]:
        """Get quality trend data over time."""
        try:
            return await self.stats_ops.get_quality_trend_data(camera_id, hours)
        except Exception as e:
            logger.error(
                "Failed to get quality trend data",
                exception=e,
                extra_context={"operation": "get_quality_trend_data"},
            )
            raise

    async def get_storage_statistics(self) -> StorageStatsModel:
        """Get storage usage statistics."""
        try:
            return await self.stats_ops.get_storage_statistics()
        except Exception as e:
            logger.error(
                "Failed to get storage statistics",
                exception=e,
                extra_context={"operation": "get_storage_statistics"},
            )
            raise

    async def get_system_health_data(self) -> SystemHealthScoreModel:
        """Calculate system health score based on various metrics."""
        try:
            health_data = await self.stats_ops.get_system_health_data()
            # Convert dict to SystemHealthScoreModel
            return SystemHealthScoreModel(**health_data)
        except Exception as e:
            logger.error(
                "Failed to get system health score",
                exception=e,
                extra_context={"operation": "get_system_health_data"},
            )
            raise

    async def compile_system_overview(self) -> Dict[str, Any]:
        """
        Compile system-wide overview statistics.

        Returns:
            System overview with aggregated metrics
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Get basic system statistics from operations layer
            dashboard_stats = await self.get_dashboard_stats()
            storage_stats = await self.get_storage_statistics()
            health_score = await self.get_system_health_data()

            overview_data = {
                "compilation_timestamp": timestamp.isoformat(),
                "dashboard_overview": (
                    dashboard_stats.model_dump() if dashboard_stats else {}
                ),
                "storage_overview": storage_stats.model_dump() if storage_stats else {},
                "health_overview": health_score.model_dump() if health_score else {},
                "system_status": "operational",  # Could be enhanced based on health score
            }

            # SSE broadcasting handled by higher-level service layer

            return overview_data

        except Exception as e:
            logger.error(
                "System overview compilation failed",
                exception=e,
                extra_context={"operation": "compile_system_overview"},
            )
            return {"error": str(e)}

    async def generate_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Generate aggregated system metrics for monitoring using available operations methods.

        Returns:
            Aggregated metrics for system monitoring
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)
            dashboard_stats = await self.stats_ops.get_dashboard_stats()
            storage_stats = await self.stats_ops.get_storage_statistics()
            health_score = await self.stats_ops.get_system_health_data()
            camera_performance = await self.stats_ops.get_camera_performance_stats(
                camera_id=None
            )
            quality_trends = await self.stats_ops.get_quality_trend_data(
                camera_id=None, hours=DEFAULT_DASHBOARD_QUALITY_TREND_DAYS * 24
            )

            metrics = {
                "dashboard": dashboard_stats.model_dump() if dashboard_stats else {},
                "storage": storage_stats.model_dump() if storage_stats else {},
                "health_score": health_score if health_score else {},
                "camera_performance": (
                    [cp.model_dump() for cp in camera_performance]
                    if camera_performance
                    else []
                ),
                "quality_trends": (
                    [qt.model_dump() for qt in quality_trends] if quality_trends else []
                ),
            }

            aggregated_data = {
                "timestamp": timestamp.isoformat(),
                "metrics": metrics,
                "aggregation_source": "statistics_operations",
            }

            # SSE broadcasting handled by higher-level service layer

            return aggregated_data
        except Exception as e:
            logger.error(
                "Aggregated metrics generation failed",
                exception=e,
                extra_context={"operation": "generate_aggregated_metrics"},
            )
            return {"error": str(e)}

    async def prepare_system_dashboard_data(self) -> Dict[str, Any]:
        """
        Prepare system-level dashboard data.

        NOTE: Domain-specific dashboard sections should be prepared by their respective services.

        Returns:
            System dashboard data
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            dashboard_data = {
                "data_timestamp": timestamp.isoformat(),
                "system_overview": await self.compile_system_overview(),
                "aggregated_metrics": await self.generate_aggregated_metrics(),
                "health_summary": await self.get_system_health_data(),
            }

            logger.info(
                "System dashboard data prepared successfully",
            )
            return dashboard_data

        except Exception as e:
            logger.error(
                "System dashboard data preparation failed",
                exception=e,
                extra_context={"operation": "prepare_system_dashboard_data"},
            )
            return {"error": str(e)}


class SyncStatisticsService:
    """Sync statistics service for worker processes."""

    def __init__(self, db: SyncDatabase, stats_ops, settings_service):
        """Initialize service with injected dependencies."""
        self.db = db
        self.stats_ops = stats_ops
        self.settings_service = settings_service

    def get_system_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics for monitoring."""
        try:
            # Calculate timestamp for database operation
            timestamp = get_timezone_aware_timestamp_sync(self.settings_service)
            return self.stats_ops.get_system_performance_metrics(timestamp.isoformat())
        except Exception as e:
            logger.error(
                "Failed to get system performance metrics",
                exception=e,
                extra_context={"operation": "get_system_performance_metrics"},
            )
            raise

    def update_camera_statistics(self, camera_id: int) -> bool:
        """Update cached statistics for a camera."""
        try:
            return self.stats_ops.update_camera_statistics(camera_id)
        except Exception as e:
            logger.error(
                f"Failed to update camera statistics for camera {camera_id}",
                exception=e,
                extra_context={
                    "operation": "update_camera_statistics",
                    "camera_id": camera_id,
                },
            )
            raise

    def get_capture_success_rate(self, camera_id: int, hours: int = 24) -> float:
        """Calculate capture success rate for a camera."""
        try:
            return self.stats_ops.get_capture_success_rate(camera_id, hours)
        except Exception as e:
            logger.error(
                f"Failed to get capture success rate for camera {camera_id}",
                exception=e,
                extra_context={
                    "operation": "get_capture_success_rate",
                    "camera_id": camera_id,
                },
            )
            raise

    def cleanup_old_statistics(self, days_to_keep: int = 365) -> int:
        """Clean up old statistical data."""
        try:
            return self.stats_ops.cleanup_old_statistics(days_to_keep)
        except Exception as e:
            logger.error(
                "Failed to cleanup old statistics",
                exception=e,
                extra_context={"operation": "cleanup_old_statistics"},
            )
            raise

    def get_system_overview_sync(self) -> Dict[str, Any]:
        """Get system overview for worker processes."""
        try:
            timestamp = get_timezone_aware_timestamp_sync(self.settings_service)

            # Get basic metrics from operations layer
            performance_metrics = self.get_system_performance_metrics()

            return {
                "timestamp": timestamp.isoformat(),
                "performance_metrics": performance_metrics,
                "source": "sync_statistics_service",
            }

        except Exception as e:
            logger.error(
                "Sync system overview failed",
                exception=e,
                extra_context={"operation": "get_system_overview_sync"},
            )
            return {"error": str(e)}
