"""
Typed response models for video worker operations.

These models replace defensive dictionary access with type-safe attributes,
eliminating the need for .get() calls and providing compile-time safety.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProcessQueueResult:
    """Result from processing the video job queue."""

    success: bool
    jobs_processed: int
    currently_processing: int
    errors: List[str]


@dataclass
class VideoGenerationResult:
    """Result from direct video generation."""

    success: bool
    video_path: Optional[str] = None
    video_id: Optional[int] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None


@dataclass
class RecoveryResult:
    """Result from stuck job recovery operations."""

    stuck_jobs_found: int
    stuck_jobs_recovered: int
    errors: List[str]


@dataclass
class WorkflowHealth:
    """Video workflow health status."""

    status: str  # "healthy", "degraded", "unhealthy"
    active_generations: int
    pending_generations: int
    can_process_more: bool
    queue_health: dict
    job_health: dict
    error: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        """Check if workflow is healthy."""
        return self.status == "healthy"

    @property
    def is_degraded(self) -> bool:
        """Check if workflow is degraded."""
        return self.status == "degraded"


@dataclass
class QueueStatus:
    """Job queue status information."""

    pending: int
    processing: int
    completed: int
    failed: int


@dataclass
class ProcessingStatus:
    """Video processing status information."""

    currently_processing: int
    max_concurrent_jobs: int
    queue_status: QueueStatus
    pending_jobs: int
    processing_jobs: int
    can_process_more: bool
    capacity_utilization_percent: float
