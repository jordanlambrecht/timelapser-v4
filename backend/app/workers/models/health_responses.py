"""
Typed response models for health worker operations.

These models provide type-safe access to health monitoring results and status information,
following the Service Layer Boundary Pattern for consistent worker architecture.
"""

from pydantic import BaseModel
from ...models.health_model import HealthStatus
from ...enums import WorkerType


class HealthWorkerStatus(BaseModel):
    """Comprehensive health worker status with type-safe property access."""

    worker_type: WorkerType
    camera_service_status: HealthStatus
    rtsp_service_status: HealthStatus
    active_cameras_count: int
    monitoring_enabled: bool
    health_system_healthy: bool

    @property
    def is_healthy(self) -> bool:
        """Check if health worker is fully healthy."""
        return (
            self.camera_service_status == HealthStatus.HEALTHY
            and self.rtsp_service_status == HealthStatus.HEALTHY
            and self.monitoring_enabled
        )

    @property
    def services_online_count(self) -> int:
        """Count of core services that are online."""
        online_services = [
            self.camera_service_status,
            self.rtsp_service_status,
        ]
        return sum(1 for status in online_services if status == HealthStatus.HEALTHY)

    @property
    def has_cameras_to_monitor(self) -> bool:
        """Check if there are cameras available for monitoring."""
        return self.active_cameras_count > 0


class CameraHealthSummary(BaseModel):
    """Summary of camera health monitoring results."""

    total_cameras: int
    online_cameras: int
    offline_cameras: int
    last_check_completed: bool = True

    @property
    def online_percentage(self) -> float:
        """Calculate percentage of cameras that are online."""
        if self.total_cameras == 0:
            return 100.0
        return (self.online_cameras / self.total_cameras) * 100.0

    @property
    def all_cameras_healthy(self) -> bool:
        """Check if all cameras are healthy."""
        return self.total_cameras > 0 and self.offline_cameras == 0
