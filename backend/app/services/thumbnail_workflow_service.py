# backend/app/services/thumbnail_workflow_service.py
"""
Thumbnail workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for thumbnail operations.
Converts raw data to typed objects at the service boundary.
"""

from typing import Any, Dict

from ..enums import LoggerName, WorkerType
from ..services.logger import get_service_logger
from ..workers.models.thumbnail_responses import ThumbnailWorkerStatus

thumbnail_service_logger = get_service_logger(LoggerName.THUMBNAIL_WORKER)


class ThumbnailWorkflowService:
    """
    Service layer for thumbnail operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern.
    """

    def __init__(self):
        """Initialize thumbnail workflow service."""
        pass

    def get_worker_status(
        self,
        thumbnail_pipeline: Any,
        processing_time_warning_threshold_ms: int,
        concurrent_jobs_limit: int,
        base_status: Dict[str, Any],
    ) -> ThumbnailWorkerStatus:
        """
        Convert raw service status to typed ThumbnailWorkerStatus at service boundary.

        Args:
            thumbnail_pipeline: Thumbnail pipeline instance
            processing_time_warning_threshold_ms: Warning threshold for processing time
            concurrent_jobs_limit: Maximum concurrent jobs
            base_status: Base status from JobProcessingMixin

        Returns:
            ThumbnailWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status using .value for explicit access
        pipeline_status = "healthy" if thumbnail_pipeline else "unavailable"

        # Extract data from base status (guaranteed by mixin contract)
        jobs_processed = base_status.get("jobs_processed_total", 0)
        jobs_failed = base_status.get("jobs_failed_total", 0)
        queue_size = base_status.get("current_queue_size", 0)
        avg_time = base_status.get("avg_processing_time_ms", 0.0)
        last_job = base_status.get("last_job_processed")
        is_processing = base_status.get("is_processing", False)

        # Return typed object at service boundary
        return ThumbnailWorkerStatus(
            worker_type=WorkerType.THUMBNAIL_WORKER.value,
            thumbnail_pipeline_status=pipeline_status,
            processing_time_warning_threshold_ms=processing_time_warning_threshold_ms,
            concurrent_jobs_limit=concurrent_jobs_limit,
            jobs_processed_total=jobs_processed,
            jobs_failed_total=jobs_failed,
            current_queue_size=queue_size,
            avg_processing_time_ms=avg_time,
            last_job_processed=last_job,
            is_processing=is_processing,
        )
