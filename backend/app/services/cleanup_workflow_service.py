# backend/app/services/cleanup_workflow_service.py
"""
Cleanup workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for cleanup operations.
Converts raw data to typed objects at the service boundary.
"""

from datetime import datetime
from typing import Any, Optional

from ..enums import LoggerName, WorkerType
from ..models.health_model import HealthStatus
from ..services.logger import get_service_logger
from ..workers.models.cleanup_responses import CleanupStats, CleanupWorkerStatus

cleanup_service_logger = get_service_logger(LoggerName.SYSTEM)


class CleanupWorkflowService:
    """
    Service layer for cleanup operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern.
    """

    def __init__(self):
        """Initialize cleanup workflow service."""
        pass

    def get_worker_status(
        self,
        log_service: Any,
        corruption_ops: Any,
        video_pipeline: Any,
        timelapse_service: Any,
        image_ops: Any,
        statistics_ops: Any,
        overlay_job_ops: Any,
        last_cleanup_time: Optional[datetime],
        cleanup_interval_hours: int,
        cleanup_stats: CleanupStats,
    ) -> CleanupWorkerStatus:
        """
        Convert raw service status to typed CleanupWorkerStatus at service boundary.

        Args:
            log_service: Log cleanup service instance
            corruption_ops: Corruption operations instance
            video_pipeline: Video pipeline instance
            timelapse_service: Timelapse service instance
            image_ops: Image operations instance
            statistics_ops: Statistics operations instance
            overlay_job_ops: Overlay job operations instance
            last_cleanup_time: Last cleanup timestamp
            cleanup_interval_hours: Cleanup interval in hours
            cleanup_stats: Current cleanup statistics

        Returns:
            CleanupWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status using .value for explicit access
        log_status = HealthStatus.HEALTHY if log_service else HealthStatus.UNREACHABLE
        corruption_status = (
            HealthStatus.HEALTHY if corruption_ops else HealthStatus.UNREACHABLE
        )
        video_status = (
            HealthStatus.HEALTHY if video_pipeline else HealthStatus.UNREACHABLE
        )
        timelapse_status = (
            HealthStatus.HEALTHY if timelapse_service else HealthStatus.UNREACHABLE
        )
        image_status = HealthStatus.HEALTHY if image_ops else HealthStatus.UNREACHABLE
        stats_status = (
            HealthStatus.HEALTHY if statistics_ops else HealthStatus.UNREACHABLE
        )
        overlay_status = (
            HealthStatus.HEALTHY if overlay_job_ops else HealthStatus.UNREACHABLE
        )

        # Return typed object at service boundary
        return CleanupWorkerStatus(
            worker_type=WorkerType.CLEANUP_WORKER.value,
            last_cleanup_time=(
                last_cleanup_time.isoformat() if last_cleanup_time else None
            ),
            cleanup_interval_hours=cleanup_interval_hours,
            cleanup_stats=cleanup_stats,
            total_items_cleaned=cleanup_stats.total_items_cleaned,
            last_duration_seconds=cleanup_stats.duration_seconds,
            log_service_status=log_status,
            corruption_ops_status=corruption_status,
            video_pipeline_status=video_status,
            timelapse_service_status=timelapse_status,
            image_ops_status=image_status,
            statistics_ops_status=stats_status,
            overlay_job_ops_status=overlay_status,
        )
