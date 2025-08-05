# backend/app/workers/utils/worker_status_builder.py
"""
WorkerStatusBuilder - Pure utility class for explicit worker status handling.

This replaces the complex StatusReportingMixin pattern with simple, explicit
composition-based status building. No inheritance, no super() calls,
no method reference passing - just clear, obvious status construction.

Design Principles:
- Explicit is better than implicit
- Single Responsibility Principle
- Pure functions with no side effects
- Composition over inheritance
- No architectural debt from super() or complex MRO

Benefits over StatusReportingMixin:
- No confusing super().get_status method reference passing
- No MRO dependencies or inheritance magic
- Clear separation of base status vs service status
- Easier testing and debugging
- New developers can easily understand the flow
"""

from typing import Dict, Any, Optional
from ...utils.time_utils import utc_now


class WorkerStatusBuilder:
    """
    Pure utility class for building worker status dictionaries.

    Uses static methods to avoid any inheritance or instance state.
    All methods are pure functions that take explicit inputs and
    return predictable outputs.
    """

    @staticmethod
    def build_base_status(name: str, running: bool, worker_type: str) -> Dict[str, Any]:
        """
        Build base worker status with explicit parameters.

        This replaces BaseWorker.get_status() and eliminates the need
        for super() calls in concrete workers.

        Args:
            name: Worker name (e.g., "CaptureWorker")
            running: Whether worker is currently running
            worker_type: Worker type string (e.g., "CaptureWorker")

        Returns:
            Dictionary with base worker status fields
        """
        return {
            "name": name,
            "running": running,
            "worker_type": worker_type,
            "timestamp": utc_now().isoformat(),
        }

    @staticmethod
    def merge_service_status(
        base_status: Dict[str, Any], service_status: Any
    ) -> Dict[str, Any]:
        """
        Merge base worker status with service-specific status.

        Handles conversion of typed service status objects to dictionaries
        and merges them with base status cleanly.

        Args:
            base_status: Base worker status from build_base_status()
            service_status: Typed status object from service layer

        Returns:
            Complete merged status dictionary
        """
        if service_status is None:
            return base_status

        # Convert typed status object to dictionary
        if hasattr(service_status, "to_dict"):
            # If the typed status has a to_dict method, use it
            service_dict = service_status.to_dict()
        elif hasattr(service_status, "__dict__"):
            # If it's a dataclass or similar, use __dict__
            service_dict = {
                key: value.value if hasattr(value, "value") else value
                for key, value in service_status.__dict__.items()
            }
        elif isinstance(service_status, dict):
            # Already a dictionary
            service_dict = service_status
        else:
            # Fallback: try to convert to dict
            try:
                service_dict = dict(service_status)
            except (TypeError, ValueError):
                # If we can't convert, just add it as a nested object
                service_dict = {"service_status": service_status}

        # Merge base status with service status
        return {**base_status, **service_dict}

    @staticmethod
    def build_simple_health_status(
        running: bool, worker_type: str, additional_checks: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Build simple health status for worker management systems.

        Provides binary health information separate from detailed status.
        This maintains clear separation between status (detailed info)
        and health (simple health check).

        Args:
            running: Whether worker is running
            worker_type: Worker type string
            additional_checks: Optional dict of additional boolean health checks

        Returns:
            Simple health status dictionary
        """
        health_checks = {"running": running}

        if additional_checks:
            health_checks.update(additional_checks)

        # Overall health is true only if all checks pass
        overall_healthy = all(health_checks.values())

        return {
            "healthy": overall_healthy,
            "worker_type": worker_type,
            "checks": health_checks,
        }

    @staticmethod
    def build_error_status(
        name: str, worker_type: str, error_type: str, error_message: str
    ) -> Dict[str, Any]:
        """
        Build standardized error status response.

        Used when status gathering fails due to service unavailability
        or other errors.

        Args:
            name: Worker name
            worker_type: Worker type string
            error_type: Type of error (e.g., "service_unavailable", "unexpected")
            error_message: Error description

        Returns:
            Standardized error status dictionary
        """
        return {
            "name": name,
            "running": False,  # Assume not running if we can't get status
            "worker_type": worker_type,
            "timestamp": utc_now().isoformat(),
            "status_error": error_message,
            "status_error_type": error_type,
            "healthy": False,
        }
