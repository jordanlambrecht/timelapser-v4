# backend/app/services/overlay_responses.py
"""
Typed response models for OverlayWorker Service Layer Boundary Pattern compliance.

Converts raw dictionary responses from JobProcessingMixin to typed objects,
following the established pattern from health_responses.py and other workers.
"""

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime

from ..enums import WorkerType
from ..models.health_model import HealthStatus
from ..utils.time_utils import utc_now


@dataclass
class OverlayQueueSummary:
    """Typed model for overlay job queue statistics."""

    pending_jobs: int
    processing_jobs: int
    completed_jobs: int
    failed_jobs: int = 0

    @property
    def total_jobs(self) -> int:
        """Total number of jobs across all states."""
        return (
            self.pending_jobs
            + self.processing_jobs
            + self.completed_jobs
            + self.failed_jobs
        )

    @property
    def is_active(self) -> bool:
        """True if there are jobs pending or processing."""
        return self.pending_jobs > 0 or self.processing_jobs > 0

    @property
    def queue_load_level(self) -> str:
        """Human-readable queue load level."""
        total = self.total_jobs
        if total == 0:
            return "empty"
        elif total <= 5:
            return "low"
        elif total <= 15:
            return "normal"
        elif total <= 30:
            return "high"
        else:
            return "overloaded"


@dataclass
class OverlayPerformanceStats:
    """Typed model for overlay worker performance metrics."""

    processed_jobs_total: int
    failed_jobs_total: int
    success_rate_percent: float
    avg_processing_time_ms: float
    current_batch_size: int
    max_concurrent_jobs: int

    @property
    def is_performing_well(self) -> bool:
        """True if worker is performing within acceptable parameters."""
        return (
            self.success_rate_percent >= 90.0
            and self.avg_processing_time_ms < 30000  # Less than 30 seconds average
        )

    @property
    def performance_grade(self) -> str:
        """Letter grade for performance assessment."""
        if self.success_rate_percent >= 95.0:
            return "A"
        elif self.success_rate_percent >= 90.0:
            return "B"
        elif self.success_rate_percent >= 80.0:
            return "C"
        elif self.success_rate_percent >= 70.0:
            return "D"
        else:
            return "F"


@dataclass
class OverlayWorkerStatus:
    """
    Typed model for OverlayWorker status following Service Layer Boundary Pattern.

    Converts raw Dict[str, Any] from JobProcessingMixin.get_status() to typed object
    with clean property access methods, eliminating defensive coding patterns.
    """

    # Core worker status
    name: str
    running: bool
    worker_type: WorkerType
    healthy: bool

    # Worker configuration
    worker_interval: int
    cleanup_hours: int
    last_cleanup: datetime

    # Queue and performance stats
    queue_stats: OverlayQueueSummary
    performance_stats: OverlayPerformanceStats

    # Service status
    overlay_service_status: HealthStatus
    job_service_status: HealthStatus
    weather_manager_enabled: bool

    # Retry configuration
    max_retries: int
    retry_delays: list[int]

    # SSE broadcasting stats
    sse_events_sent: int = 0
    sse_errors: int = 0

    @classmethod
    def from_dict(cls, raw_status: Dict[str, Any]) -> "OverlayWorkerStatus":
        """
        Convert raw dictionary status to typed OverlayWorkerStatus object.

        This is the Service Layer Boundary conversion point that eliminates
        the need for defensive .get() calls throughout the codebase.

        Args:
            raw_status: Raw dictionary from worker.get_status()

        Returns:
            Typed OverlayWorkerStatus object with clean property access
        """
        # Extract queue statistics
        queue_data = raw_status.get("queue_stats", {})
        queue_stats = OverlayQueueSummary(
            pending_jobs=queue_data.get("pending_jobs", 0),
            processing_jobs=queue_data.get("processing_jobs", 0),
            completed_jobs=queue_data.get("completed_jobs", 0),
            failed_jobs=queue_data.get("failed_jobs", 0),
        )

        # Extract performance statistics
        performance_stats = OverlayPerformanceStats(
            processed_jobs_total=raw_status.get("processed_jobs_total", 0),
            failed_jobs_total=raw_status.get("failed_jobs_total", 0),
            success_rate_percent=raw_status.get("success_rate_percent", 0.0),
            avg_processing_time_ms=raw_status.get("avg_processing_time_ms", 0.0),
            current_batch_size=raw_status.get("current_batch_size", 5),
            max_concurrent_jobs=raw_status.get("max_concurrent_jobs", 3),
        )

        # Parse last cleanup time
        last_cleanup_str = raw_status.get("last_cleanup", utc_now().isoformat())
        try:
            last_cleanup = datetime.fromisoformat(
                last_cleanup_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            last_cleanup = utc_now()

        # Extract retry configuration
        retry_config = raw_status.get("retry_config", {})
        retry_delays = retry_config.get("retry_delays", [1, 5, 15])

        # Extract SSE stats
        sse_stats = raw_status.get("sse_stats", {})

        return cls(
            name=raw_status.get("name", "OverlayWorker"),
            running=raw_status.get("running", False),
            worker_type=WorkerType.OVERLAY_WORKER,
            healthy=raw_status.get("healthy", False),
            worker_interval=raw_status.get("worker_interval", 10),
            cleanup_hours=raw_status.get("cleanup_hours", 24),
            last_cleanup=last_cleanup,
            queue_stats=queue_stats,
            performance_stats=performance_stats,
            overlay_service_status=raw_status.get(
                "overlay_service_status", HealthStatus.UNKNOWN
            ),
            job_service_status=raw_status.get(
                "job_service_status", HealthStatus.UNKNOWN
            ),
            weather_manager_enabled=raw_status.get("weather_manager_enabled", False),
            max_retries=retry_config.get("max_retries", 3),
            retry_delays=retry_delays,
            sse_events_sent=sse_stats.get("events_sent", 0),
            sse_errors=sse_stats.get("errors", 0),
        )

    @property
    def is_healthy(self) -> bool:
        """True if worker is running and all services are healthy."""
        return (
            self.running
            and self.healthy
            and self.overlay_service_status == HealthStatus.HEALTHY
            and self.job_service_status == HealthStatus.HEALTHY
        )

    @property
    def is_processing_jobs(self) -> bool:
        """True if worker is currently processing jobs."""
        return self.queue_stats.processing_jobs > 0

    @property
    def queue_pending_count(self) -> int:
        """Number of jobs waiting to be processed."""
        return self.queue_stats.pending_jobs

    @property
    def overall_performance_grade(self) -> str:
        """Overall performance assessment."""
        return self.performance_stats.performance_grade

    @property
    def status_summary(self) -> str:
        """Human-readable status summary."""
        if not self.running:
            return "stopped"
        elif not self.is_healthy:
            return "unhealthy"
        elif self.is_processing_jobs:
            return "processing"
        elif self.queue_pending_count > 0:
            return "queued"
        else:
            return "idle"

    @property
    def needs_attention(self) -> bool:
        """True if worker requires administrator attention."""
        return (
            not self.is_healthy
            or self.performance_stats.success_rate_percent < 80.0
            or self.queue_stats.queue_load_level in ["high", "overloaded"]
        )
