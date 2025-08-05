# backend/app/services/overlay_workflow_service.py
"""
Service layer for OverlayWorker status management with Service Layer Boundary Pattern.

Converts raw Dict[str, Any] responses from OverlayWorker to typed objects,
eliminating defensive coding patterns throughout the codebase.
"""

from typing import Dict, Any

from .overlay_responses import OverlayWorkerStatus
from ..enums import LoggerName, LogSource
from ..services.logger import get_service_logger

# Initialize service logger
overlay_workflow_logger = get_service_logger(
    LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE
)


class OverlayWorkflowService:
    """
    Service layer for OverlayWorker status management.

    Provides typed responses following Service Layer Boundary Pattern,
    converting raw dictionary responses to typed objects at the service boundary.
    This eliminates the need for defensive .get() calls throughout the codebase.
    """

    def get_worker_status(
        self, overlay_worker, operation_context: str = "overlay_worker_status"
    ) -> OverlayWorkerStatus:
        """
        Get typed OverlayWorker status, converting raw dictionary to typed object.

        This is the Service Layer Boundary conversion point that provides
        clean property access without defensive coding patterns.

        Args:
            overlay_worker: OverlayWorker instance
            operation_context: Context description for logging

        Returns:
            Typed OverlayWorkerStatus object with clean property access

        Raises:
            Exception: If worker status cannot be retrieved
        """
        overlay_workflow_logger.debug(
            f"Retrieving overlay worker status for {operation_context}"
        )

        try:
            # Get raw status from worker (returns Dict[str, Any])
            raw_status = overlay_worker.get_status()

            # Convert to typed object at service boundary
            typed_status = OverlayWorkerStatus.from_dict(raw_status)

            overlay_workflow_logger.debug(
                f"Successfully converted overlay worker status to typed object: "
                f"{typed_status.status_summary}"
            )

            return typed_status

        except Exception as e:
            overlay_workflow_logger.error(
                f"Failed to retrieve overlay worker status for {operation_context}: {e}"
            )
            raise

    def get_queue_summary(
        self, overlay_worker, operation_context: str = "overlay_queue_summary"
    ) -> Dict[str, Any]:
        """
        Get overlay job queue summary with typed response.

        Args:
            overlay_worker: OverlayWorker instance
            operation_context: Context description for logging

        Returns:
            Queue summary information
        """
        overlay_workflow_logger.debug(
            f"Retrieving overlay queue summary for {operation_context}"
        )

        try:
            # Get typed status which includes queue summary
            status = self.get_worker_status(overlay_worker, operation_context)

            return {
                "pending_jobs": status.queue_pending_count,
                "processing_jobs": status.queue_stats.processing_jobs,
                "completed_jobs": status.queue_stats.completed_jobs,
                "queue_load_level": status.queue_stats.queue_load_level,
                "is_active": status.queue_stats.is_active,
                "total_jobs": status.queue_stats.total_jobs,
            }

        except Exception as e:
            overlay_workflow_logger.error(
                f"Failed to retrieve overlay queue summary for {operation_context}: {e}"
            )
            raise
