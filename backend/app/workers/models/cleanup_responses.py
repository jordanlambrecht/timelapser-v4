"""
Typed response models for cleanup worker operations.

These models provide type-safe attributes and compile-time safety
for cleanup operations.
"""

from dataclasses import dataclass
from typing import Optional

from ...models.health_model import HealthStatus


@dataclass
class RetentionSettings:
    """Cleanup retention settings configuration."""

    log_retention_days: int
    image_retention_days: int
    video_cleanup_days: int
    timelapse_retention_days: int
    corruption_logs_retention_days: int
    statistics_retention_days: int
    overlay_cleanup_hours: int

    @classmethod
    def from_dict(cls, data: dict) -> "RetentionSettings":
        """Create RetentionSettings from dictionary."""
        return cls(
            log_retention_days=data.get("log_retention_days", 0),
            image_retention_days=data.get("image_retention_days", 0),
            video_cleanup_days=data.get("video_cleanup_days", 0),
            timelapse_retention_days=data.get("timelapse_retention_days", 0),
            corruption_logs_retention_days=data.get(
                "corruption_logs_retention_days", 0
            ),
            statistics_retention_days=data.get("statistics_retention_days", 0),
            overlay_cleanup_hours=data.get("overlay_cleanup_hours", 0),
        )


@dataclass
class CleanupResults:
    """Results from cleanup operations."""

    logs: int = 0
    images: int = 0
    video_jobs: int = 0
    timelapses: int = 0
    corruption_logs: int = 0
    overlay_jobs: int = 0
    sse_events: int = 0
    statistics: int = 0
    rate_limiter: int = 0
    temp_files: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "CleanupResults":
        """Create CleanupResults from dictionary."""
        return cls(
            logs=data.get("logs", 0),
            images=data.get("images", 0),
            video_jobs=data.get("video_jobs", 0),
            timelapses=data.get("timelapses", 0),
            corruption_logs=data.get("corruption_logs", 0),
            overlay_jobs=data.get("overlay_jobs", 0),
            sse_events=data.get("sse_events", 0),
            statistics=data.get("statistics", 0),
            rate_limiter=data.get("rate_limiter", 0),
            temp_files=data.get("temp_files", 0),
        )

    @property
    def total_cleaned(self) -> int:
        """Total number of items cleaned across all categories."""
        return (
            self.logs
            + self.images
            + self.video_jobs
            + self.timelapses
            + self.corruption_logs
            + self.overlay_jobs
            + self.sse_events
            + self.statistics
            + self.rate_limiter
            + self.temp_files
        )


@dataclass
class CleanupStats:
    """Cleanup cycle statistics."""

    last_run: Optional[str] = None
    duration_seconds: float = 0.0
    results: Optional[CleanupResults] = None
    total_items_cleaned: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "CleanupStats":
        """Create CleanupStats from dictionary."""
        results_data = data.get("results")
        results = CleanupResults.from_dict(results_data) if results_data else None

        return cls(
            last_run=data.get("last_run"),
            duration_seconds=data.get("duration_seconds", 0.0),
            results=results,
            total_items_cleaned=data.get("total_items_cleaned", 0),
        )


@dataclass
class LogCleanupResult:
    """Result from log cleanup operations."""

    success: bool
    logs_deleted: int = 0
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "LogCleanupResult":
        """Create LogCleanupResult from dictionary."""
        return cls(
            success=data.get("success", False),
            logs_deleted=data.get("logs_deleted", 0),
            error=data.get("error"),
        )

    @property
    def is_successful(self) -> bool:
        """Check if cleanup was successful."""
        return self.success and self.error is None


@dataclass
class CleanupWorkerStatus:
    """Comprehensive cleanup worker status."""

    worker_type: str
    last_cleanup_time: Optional[str] = None
    cleanup_interval_hours: int = 6
    cleanup_stats: Optional[CleanupStats] = None
    total_items_cleaned: int = 0
    last_duration_seconds: float = 0.0
    log_service_status: HealthStatus = HealthStatus.UNREACHABLE
    corruption_ops_status: HealthStatus = HealthStatus.UNREACHABLE
    video_pipeline_status: HealthStatus = HealthStatus.UNREACHABLE
    timelapse_service_status: HealthStatus = HealthStatus.UNREACHABLE
    image_ops_status: HealthStatus = HealthStatus.UNREACHABLE
    statistics_ops_status: HealthStatus = HealthStatus.UNREACHABLE
    overlay_job_ops_status: HealthStatus = HealthStatus.UNREACHABLE

    @classmethod
    def from_dict(cls, data: dict) -> "CleanupWorkerStatus":
        """Create CleanupWorkerStatus from dictionary."""
        cleanup_stats_data = data.get("cleanup_stats")
        cleanup_stats = (
            CleanupStats.from_dict(cleanup_stats_data) if cleanup_stats_data else None
        )

        return cls(
            worker_type=data.get("worker_type", "cleanup_worker"),
            last_cleanup_time=data.get("last_cleanup_time"),
            cleanup_interval_hours=data.get("cleanup_interval_hours", 6),
            cleanup_stats=cleanup_stats,
            total_items_cleaned=data.get("total_items_cleaned", 0),
            last_duration_seconds=data.get("last_duration_seconds", 0.0),
            log_service_status=HealthStatus(
                data.get("log_service_status", "unreachable")
            ),
            corruption_ops_status=HealthStatus(
                data.get("corruption_ops_status", "unreachable")
            ),
            video_pipeline_status=HealthStatus(
                data.get("video_pipeline_status", "unreachable")
            ),
            timelapse_service_status=HealthStatus(
                data.get("timelapse_service_status", "unreachable")
            ),
            image_ops_status=HealthStatus(data.get("image_ops_status", "unreachable")),
            statistics_ops_status=HealthStatus(
                data.get("statistics_ops_status", "unreachable")
            ),
            overlay_job_ops_status=HealthStatus(
                data.get("overlay_job_ops_status", "unreachable")
            ),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if cleanup worker is healthy."""
        return all(
            [
                self.log_service_status == HealthStatus.HEALTHY,
                self.corruption_ops_status == HealthStatus.HEALTHY,
                self.video_pipeline_status == HealthStatus.HEALTHY,
                self.timelapse_service_status == HealthStatus.HEALTHY,
                self.image_ops_status == HealthStatus.HEALTHY,
                self.statistics_ops_status == HealthStatus.HEALTHY,
                self.overlay_job_ops_status == HealthStatus.HEALTHY,
            ]
        )

    @property
    def services_available(self) -> int:
        """Count of available services."""
        services = [
            self.log_service_status,
            self.corruption_ops_status,
            self.video_pipeline_status,
            self.timelapse_service_status,
            self.image_ops_status,
            self.statistics_ops_status,
            self.overlay_job_ops_status,
        ]
        return sum(1 for status in services if status == HealthStatus.HEALTHY)
