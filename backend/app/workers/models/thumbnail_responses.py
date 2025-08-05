"""
Typed response models for thumbnail worker operations.

These models provide type-safe access to thumbnail workflow results and status information,
enhancing error handling and providing operational clarity.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ThumbnailWorkerStatus:
    """Comprehensive thumbnail worker status."""

    worker_type: str
    thumbnail_pipeline_status: str
    processing_time_warning_threshold_ms: int
    concurrent_jobs_limit: int
    jobs_processed_total: int = 0
    jobs_failed_total: int = 0
    current_queue_size: int = 0
    avg_processing_time_ms: float = 0.0
    last_job_processed: Optional[datetime] = None
    is_processing: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ThumbnailWorkerStatus":
        """Create ThumbnailWorkerStatus from dictionary for backward compatibility."""
        return cls(
            worker_type=data.get("worker_type", ""),
            thumbnail_pipeline_status=data.get("thumbnail_pipeline_status", ""),
            processing_time_warning_threshold_ms=data.get(
                "processing_time_warning_threshold_ms", 0
            ),
            concurrent_jobs_limit=data.get("concurrent_jobs_limit", 0),
            jobs_processed_total=data.get("jobs_processed_total", 0),
            jobs_failed_total=data.get("jobs_failed_total", 0),
            current_queue_size=data.get("current_queue_size", 0),
            avg_processing_time_ms=data.get("avg_processing_time_ms", 0.0),
            last_job_processed=data.get("last_job_processed"),
            is_processing=data.get("is_processing", False),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if thumbnail worker is healthy."""
        return (
            self.thumbnail_pipeline_status == "healthy"
            and not self.is_processing_overloaded
        )

    @property
    def success_rate(self) -> float:
        """Calculate job success rate."""
        total_jobs = self.jobs_processed_total + self.jobs_failed_total
        if total_jobs == 0:
            return 1.0
        return self.jobs_processed_total / total_jobs

    @property
    def is_processing_overloaded(self) -> bool:
        """Check if processing is taking too long."""
        return self.avg_processing_time_ms > self.processing_time_warning_threshold_ms

    @property
    def has_recent_activity(self) -> bool:
        """Check if there has been recent processing activity."""
        if not self.last_job_processed:
            return False
        from datetime import timedelta
        from ...utils.time_utils import utc_now

        return (utc_now() - self.last_job_processed) < timedelta(minutes=30)
