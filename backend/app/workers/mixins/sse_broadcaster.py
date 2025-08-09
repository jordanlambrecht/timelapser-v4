# backend/app/workers/mixins/sse_broadcaster.py
"""
SSE Broadcaster for Worker Events.

Provides standardized Server-Sent Events broadcasting for worker job lifecycle events,
eliminating duplication between ThumbnailWorker and OverlayWorker.
"""

from typing import Any, Dict, List, Optional

from ...database.sse_events_operations import SyncSSEEventsOperations
from ...enums import LogSource, LoggerName, SSEEvent, SSEEventSource, SSEPriority
from ...services.sse_event_batcher import SSEEventBatcher
from ...utils.time_utils import utc_timestamp

from ...services.logger import get_service_logger

logger = get_service_logger(LoggerName.SSEBROADCASTER, LogSource.WORKER)


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
        use_batching: bool = True,
    ):
        """
        Initialize SSE broadcaster.

        Args:
            sse_ops: SSE operations service for database event creation
            worker_name: Name of the worker for logging and identification
            event_source: SSE event source enumeration for this worker type
            use_batching: Whether to use event batching (default True)
        """
        self.sse_ops = sse_ops
        self.worker_name = worker_name
        self.event_source = event_source
        self.failed_broadcast_count = 0
        self.use_batching = use_batching

        # Initialize event batcher if batching is enabled
        if self.use_batching:
            self.event_batcher = SSEEventBatcher(sse_ops)
        else:
            self.event_batcher = None

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

    def broadcast_jobs_started_batch(
        self,
        job_data_list: List[Dict[str, Any]],
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast multiple job started events in a single batch operation.

        Args:
            job_data_list: List of job data dictionaries (each with job_id and other data)
            priority: Event priority level

        Returns:
            True if batch broadcast successful, False otherwise
        """
        if not job_data_list:
            return True

        events = []
        timestamp = utc_timestamp()

        for job_data in job_data_list:
            event_data = {
                "job_id": job_data.get("job_id"),
                "worker_name": self.worker_name,
                "timestamp": timestamp,
                **{k: v for k, v in job_data.items() if k != "job_id"},
            }

            events.append(
                {
                    "event_type": f"{self.worker_name.lower()}_{SSEEvent.JOB_STARTED}",
                    "event_data": event_data,
                    "priority": priority.value,
                    "source": self.event_source.value,
                }
            )

        return self._create_events_batch(events)

    def broadcast_jobs_completed_batch(
        self,
        job_data_list: List[Dict[str, Any]],
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast multiple job completed events in a single batch operation.

        Args:
            job_data_list: List of job completion data (each with job_id, processing_time_ms, etc.)
            priority: Event priority level

        Returns:
            True if batch broadcast successful, False otherwise
        """
        if not job_data_list:
            return True

        events = []
        timestamp = utc_timestamp()

        for job_data in job_data_list:
            event_data = {
                "job_id": job_data.get("job_id"),
                "worker_name": self.worker_name,
                "processing_time_ms": job_data.get("processing_time_ms", 0),
                "timestamp": timestamp,
                **{
                    k: v
                    for k, v in job_data.items()
                    if k not in ["job_id", "processing_time_ms"]
                },
            }

            events.append(
                {
                    "event_type": f"{self.worker_name.lower()}_{SSEEvent.JOB_COMPLETED}",
                    "event_data": event_data,
                    "priority": priority.value,
                    "source": self.event_source.value,
                }
            )

        return self._create_events_batch(events)

    def broadcast_jobs_failed_batch(
        self,
        job_failures: List[Dict[str, Any]],
        is_permanent: bool = False,
        priority: SSEPriority = SSEPriority.NORMAL,
    ) -> bool:
        """
        Broadcast multiple job failure events in a single batch operation.

        Args:
            job_failures: List of failure data (each with job_id, error_message, etc.)
            is_permanent: Whether these are permanent failures
            priority: Event priority level

        Returns:
            True if batch broadcast successful, False otherwise
        """
        if not job_failures:
            return True

        events = []
        timestamp = utc_timestamp()
        event_type = "job_failed_permanently" if is_permanent else "job_failed"

        for failure_data in job_failures:
            event_data = {
                "job_id": failure_data.get("job_id"),
                "worker_name": self.worker_name,
                "error_message": failure_data.get("error_message", "Unknown error"),
                "is_permanent_failure": is_permanent,
                "timestamp": timestamp,
                **{
                    k: v
                    for k, v in failure_data.items()
                    if k not in ["job_id", "error_message"]
                },
            }

            events.append(
                {
                    "event_type": f"{self.worker_name.lower()}_{event_type}",
                    "event_data": event_data,
                    "priority": priority.value,
                    "source": self.event_source.value,
                }
            )

        return self._create_events_batch(events)

    def _create_events_batch(self, events: List[Dict[str, Any]]) -> bool:
        """
        Create multiple SSE events in batch using the existing batch operation.

        Args:
            events: List of event dictionaries

        Returns:
            True if batch creation successful, False otherwise
        """
        try:
            # Use the existing create_events_batch method
            self.sse_ops.create_events_batch(events)
            return True
        except Exception as e:
            self.failed_broadcast_count += len(events)
            logger.warning(
                f"[{self.worker_name}] Failed to broadcast batch of {len(events)} events: {e}"
            )
            return False

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
            full_event_type = f"{self.worker_name.lower()}_{event_type}"

            if self.use_batching and self.event_batcher:
                # Use batching for better performance and reduced frontend spam
                return self.event_batcher.add_event(
                    event_type=full_event_type,
                    event_data=event_data,
                    priority=priority,
                    source=self.event_source.value,
                    worker_name=self.worker_name,
                )
            else:
                # Direct database write (fallback)
                self.sse_ops.create_event(
                    event_type=full_event_type,
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
        stats = {
            "worker_name": self.worker_name,
            "event_source": self.event_source.value,
            "failed_broadcast_count": self.failed_broadcast_count,
            "batching_enabled": self.use_batching,
        }

        # Add batcher statistics if available
        if self.use_batching and self.event_batcher:
            batcher_stats = self.event_batcher.get_stats()
            stats.update({"batcher_" + k: v for k, v in batcher_stats.items()})

        return stats

    def reset_stats(self) -> None:
        """Reset broadcasting statistics."""
        self.failed_broadcast_count = 0

    def shutdown(self) -> None:
        """Gracefully shutdown the broadcaster and flush any pending events."""
        if self.use_batching and self.event_batcher:
            self.event_batcher.shutdown()

    def __repr__(self) -> str:
        """String representation of SSE broadcaster."""
        return (
            f"SSEBroadcaster(worker='{self.worker_name}', "
            f"source={self.event_source.value}, "
            f"batching={self.use_batching}, "
            f"failed_broadcasts={self.failed_broadcast_count})"
        )

    def __del__(self):
        """Ensure cleanup on deletion."""
        self.shutdown()
