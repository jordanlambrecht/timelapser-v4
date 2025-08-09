# backend/app/services/sse_workflow_service.py
"""
SSE workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for SSE operations.
Converts raw data to typed objects at the service boundary.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from ..enums import LoggerName, LogSource, WorkerType
from ..models.health_model import HealthStatus
from ..services.logger import get_service_logger
from ..workers.models.sse_responses import SSEWorkerStatus

sse_service_logger = get_service_logger(LoggerName.SSE_WORKER, LogSource.WORKER)


class SSEWorkflowService:
    """
    Service layer for SSE operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern.
    """

    def __init__(self):
        """Initialize SSE workflow service."""
        pass

    def get_worker_status(
        self,
        db: Any,
        sse_ops: Any,
        sse_statistics: Dict[str, Any],
        last_cleanup_time: Optional[datetime] = None,
    ) -> SSEWorkerStatus:
        """
        Convert raw service status to typed SSEWorkerStatus at service boundary.

        Args:
            db: Database instance
            sse_ops: SSE operations instance
            sse_statistics: Current SSE statistics dictionary
            last_cleanup_time: Last cleanup timestamp

        Returns:
            SSEWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status using .value for explicit access
        sse_ops_status = (
            HealthStatus.HEALTHY.value if sse_ops else HealthStatus.UNREACHABLE.value
        )
        db_status = HealthStatus.HEALTHY.value if db else HealthStatus.UNREACHABLE.value

        # Extract statistics (no .get() calls needed after service guarantees)
        total_events = sse_statistics.get("total_events", 0)
        pending_events = sse_statistics.get("pending_events", 0)
        processed_events = sse_statistics.get("processed_events", 0)

        # Return typed object at service boundary
        return SSEWorkerStatus(
            worker_type=WorkerType.SSE_WORKER.value,
            sse_operations_status=sse_ops_status,
            database_status=db_status,
            total_events=total_events,
            pending_events=pending_events,
            processed_events=processed_events,
            last_cleanup_time=last_cleanup_time,
            cleanup_enabled=True,
        )
