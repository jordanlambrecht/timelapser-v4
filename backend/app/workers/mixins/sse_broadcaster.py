# backend/app/workers/mixins/sse_broadcaster.py
"""
SSE Broadcaster for Worker Events.

Provides standardized Server-Sent Events broadcasting for worker job lifecycle events,
eliminating duplication between ThumbnailWorker and OverlayWorker.
"""

from typing import Dict, Any, Optional
from ...services.logger import get_service_logger
from ...enums import LoggerName, SSEEvent

logger = get_service_logger(LoggerName.SSEBROADCASTER)

from ...database.sse_events_operations import SyncSSEEventsOperations
from ...enums import SSEPriority, SSEEventSource
from ...utils.time_utils import utc_timestamp


class SSEBroadcaster:
    """
    Standardized SSE event broadcasting for worker job lifecycle events.

    This class eliminates the duplicated SSE broadcasting logic found in both
    ThumbnailWorker and OverlayWorker, providing consistent event structures
    and error handling across all job processing workers.

    Features:
    - Standardized event data structures for job lifecycle events
    - Consistent error handling for failed broadcasts
    - Worker-specific event source identification
    - Priority-based event classification
    - Performance metrics broadcasting
    """

    def __init__(
        self,
        sse_ops: SyncSSEEventsOperations,
        worker_name: str,
        event_source: SSEEventSource,
    ):
        """
        Initialize SSE broadcaster.

        Args:
            sse_ops: SSE operations service for database event creation
            worker_name: Name of the worker for logging and identification
            event_source: SSE event source enumeration for this worker type
        """
        self.sse_ops = sse_ops
        self.worker_name = worker_name
        self.event_source = event_source
        self.failed_broadcast_count = 0

    def broadcast_job_started(
        self,
        job_id: int,
        job_data: Dict[str, Any],
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast job started event.

        Args:
            job_id: ID of the job being started
            job_data: Additional job-specific data
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "job_id": job_id,
            "worker_name": self.worker_name,
            "timestamp": utc_timestamp(),
            **job_data,
        }

        return self._create_event(
            event_type=SSEEvent.JOB_STARTED, event_data=event_data, priority=priority
        )

    def broadcast_job_completed(
        self,
        job_id: int,
        processing_time_ms: int,
        job_data: Dict[str, Any],
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast job completion event.

        Args:
            job_id: ID of the completed job
            processing_time_ms: Time taken to process the job in milliseconds
            job_data: Additional job-specific data
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "job_id": job_id,
            "worker_name": self.worker_name,
            "processing_time_ms": processing_time_ms,
            "timestamp": utc_timestamp(),
            **job_data,
        }

        return self._create_event(
            event_type=SSEEvent.JOB_COMPLETED, event_data=event_data, priority=priority
        )

    def broadcast_job_failed(
        self,
        job_id: int,
        error_message: str,
        job_data: Dict[str, Any],
        is_permanent: bool = False,
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast job failure event.

        Args:
            job_id: ID of the failed job
            error_message: Description of the failure
            job_data: Additional job-specific data
            is_permanent: Whether this is a permanent failure (no more retries)
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_type = "job_failed_permanently" if is_permanent else "job_failed"

        event_data = {
            "job_id": job_id,
            "worker_name": self.worker_name,
            "error_message": error_message,
            "is_permanent_failure": is_permanent,
            "timestamp": utc_timestamp(),
            **job_data,
        }

        return self._create_event(
            event_type=event_type, event_data=event_data, priority=priority
        )

    def broadcast_job_retry_scheduled(
        self,
        job_id: int,
        retry_count: int,
        retry_delay_minutes: int,
        error_message: str,
        job_data: Dict[str, Any],
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast job retry scheduled event.

        Args:
            job_id: ID of the job being retried
            retry_count: Current retry attempt number
            retry_delay_minutes: Minutes until retry attempt
            error_message: Error that caused the failure
            job_data: Additional job-specific data
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "job_id": job_id,
            "worker_name": self.worker_name,
            "retry_count": retry_count,
            "retry_delay_minutes": retry_delay_minutes,
            "error_message": error_message,
            "timestamp": utc_timestamp(),
            **job_data,
        }

        return self._create_event(
            event_type=SSEEvent.JOB_RETRY_SCHEDULED,
            event_data=event_data,
            priority=priority,
        )

    def broadcast_worker_statistics(
        self, stats: Dict[str, Any], priority: SSEPriority = SSEPriority.LOW
    ) -> bool:
        """
        Broadcast worker performance statistics.

        Args:
            stats: Worker statistics data
            priority: Event priority level (typically LOW for statistics)

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "worker_name": self.worker_name,
            "timestamp": utc_timestamp(),
            **stats,
        }

        return self._create_event(
            event_type=SSEEvent.WORKER_STATISTICS,
            event_data=event_data,
            priority=priority,
        )

    def broadcast_worker_started(
        self, worker_config: Dict[str, Any], priority: SSEPriority = SSEPriority.NORMAL
    ) -> bool:
        """
        Broadcast worker startup event.

        Args:
            worker_config: Worker configuration parameters
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "worker_name": self.worker_name,
            "timestamp": utc_timestamp(),
            **worker_config,
        }

        return self._create_event(
            event_type=SSEEvent.WORKER_STARTED, event_data=event_data, priority=priority
        )

    def broadcast_worker_stopped(
        self,
        stop_reason: str = "Normal shutdown",
        final_stats: Optional[Dict[str, Any]] = None,
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast worker shutdown event.

        Args:
            stop_reason: Reason for worker shutdown
            final_stats: Final worker statistics before shutdown
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "worker_name": self.worker_name,
            "stop_reason": stop_reason,
            "timestamp": utc_timestamp(),
        }

        if final_stats:
            event_data.update(final_stats)

        return self._create_event(
            event_type=SSEEvent.WORKER_STOPPED, event_data=event_data, priority=priority
        )

    def broadcast_worker_error(
        self,
        error_message: str,
        error_context: Dict[str, Any],
        priority: SSEPriority = SSEPriority.HIGH,
    ) -> bool:
        """
        Broadcast worker error event.

        Args:
            error_message: Description of the error
            error_context: Additional context about the error
            priority: Event priority level (typically HIGH for errors)

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "worker_name": self.worker_name,
            "error_message": error_message,
            "timestamp": utc_timestamp(),
            **error_context,
        }

        return self._create_event(
            event_type=SSEEvent.WORKER_ERROR, event_data=event_data, priority=priority
        )

    def broadcast_performance_update(
        self,
        performance_metrics: Dict[str, Any],
        priority: SSEPriority = SSEPriority.LOW,
    ) -> bool:
        """
        Broadcast worker performance update.

        Args:
            performance_metrics: Performance metrics and thresholds
            priority: Event priority level

        Returns:
            True if broadcast successful, False otherwise
        """
        event_data = {
            "worker_name": self.worker_name,
            "timestamp": utc_timestamp(),
            **performance_metrics,
        }

        return self._create_event(
            event_type=SSEEvent.SYSTEM_HEALTH_CHECK,
            event_data=event_data,
            priority=priority,
        )

    def _create_event(
        self, event_type: str, event_data: Dict[str, Any], priority: SSEPriority
    ) -> bool:
        """
        Internal method to create SSE events with error handling.

        Args:
            event_type: Type of event being created
            event_data: Event data payload
            priority: Event priority level

        Returns:
            True if event created successfully, False otherwise
        """
        try:
            self.sse_ops.create_event(
                event_type=f"{self.worker_name.lower()}_{event_type}",
                event_data=event_data,
                priority=priority,
                source=self.event_source.value,
            )
            return True

        except Exception as e:
            self.failed_broadcast_count += 1
            logger.warning(
                f"[{self.worker_name}] Failed to broadcast {event_type} event: {e}"
            )
            return False

    def get_broadcast_stats(self) -> Dict[str, Any]:
        """
        Get broadcasting statistics.

        Returns:
            Dictionary with broadcast statistics
        """
        return {
            "worker_name": self.worker_name,
            "event_source": self.event_source.value,
            "failed_broadcast_count": self.failed_broadcast_count,
        }

    def reset_stats(self) -> None:
        """Reset broadcasting statistics."""
        self.failed_broadcast_count = 0

    def __repr__(self) -> str:
        """String representation of SSE broadcaster."""
        return (
            f"SSEBroadcaster(worker='{self.worker_name}', "
            f"source={self.event_source.value}, "
            f"failed_broadcasts={self.failed_broadcast_count})"
        )
