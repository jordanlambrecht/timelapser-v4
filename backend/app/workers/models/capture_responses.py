"""
Typed response models for capture worker operations.

These models provide type-safe access to capture workflow results and status information,
enhancing error handling and providing operational clarity.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CaptureWorkflowResult:
    """Result from capture workflow execution."""

    success: bool
    error: Optional[str] = None
    image_path: Optional[str] = None
    image_id: Optional[int] = None
    thumbnail_created: bool = False
    overlay_queued: bool = False
    corruption_detected: bool = False
    workflow_duration_ms: float = 0.0

    @property
    def is_successful(self) -> bool:
        """Check if capture workflow was successful."""
        return self.success and self.error is None

    @property
    def has_output(self) -> bool:
        """Check if workflow produced output (image)."""
        return self.success and self.image_path is not None


@dataclass
class CameraInfo:
    """Camera information for capture operations."""

    id: int
    name: str
    rtsp_url: str
    is_active: bool = True
    connectivity_status: str = "unknown"
    last_capture_attempt: Optional[datetime] = None

    @property
    def is_ready_for_capture(self) -> bool:
        """Check if camera is ready for capture."""
        return self.is_active and bool(self.rtsp_url)


@dataclass
class TimelapseInfo:
    """Timelapse information for capture operations."""

    id: int
    camera_id: int
    name: str
    is_active: bool = True
    status: str = "unknown"

    @property
    def is_ready_for_capture(self) -> bool:
        """Check if timelapse is ready for capture."""
        return self.is_active and self.status in ["running", "active"]


@dataclass
class CaptureWorkerStatus:
    """Comprehensive capture worker status."""

    worker_type: str
    workflow_orchestrator_status: str
    camera_service_status: str
    timelapse_ops_status: str
    weather_manager_enabled: bool
    thumbnail_job_service_enabled: bool
    overlay_job_service_enabled: bool
    pipeline_healthy: bool

    @property
    def is_healthy(self) -> bool:
        """Check if capture worker is healthy."""
        return (
            self.workflow_orchestrator_status == "healthy"
            and self.camera_service_status == "healthy"
            and self.timelapse_ops_status == "healthy"
            and self.pipeline_healthy
        )

    @property
    def core_services_count(self) -> int:
        """Count of core services that are healthy."""
        core_services = [
            self.workflow_orchestrator_status,
            self.camera_service_status,
            self.timelapse_ops_status,
        ]
        return sum(1 for status in core_services if status == "healthy")

    @property
    def optional_services_count(self) -> int:
        """Count of optional services that are enabled."""
        optional_services = [
            self.weather_manager_enabled,
            self.thumbnail_job_service_enabled,
            self.overlay_job_service_enabled,
        ]
        return sum(1 for enabled in optional_services if enabled)
