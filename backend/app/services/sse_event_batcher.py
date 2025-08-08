# backend/app/services/sse_event_batcher.py
"""
SSE Event Batcher - Batches similar SSE events for efficient database
writes and frontend delivery.

Based on the proven BatchingDatabaseHandler pattern, this batcher collects
similar SSE events and flushes them as aggregated batches to reduce database
load and frontend bombardment.
"""

import threading
import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..constants import (
    SSE_BATCH_SIZE,
    SSE_BATCH_TIMEOUT_SECONDS,
    SSE_BATCH_MAX_RETRIES,
    SSE_BATCH_RETRY_DELAY,
)
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..enums import LoggerName, SSEPriority
from ..services.logger import get_service_logger
from ..utils.time_utils import utc_now, utc_timestamp

sse_logger = get_service_logger(LoggerName.SSEBROADCASTER)


def _serialize_event_data(data: Any) -> Any:
    """
    Recursively serialize data to be JSON-compatible, handling Decimal
    and other types.

    Args:
        data: Data to serialize (can be dict, list, or primitive types)

    Returns:
        JSON-serializable version of the data
    """
    if isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, dict):
        return {key: _serialize_event_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_serialize_event_data(item) for item in data]
    elif isinstance(data, (datetime,)):
        return data.isoformat()
    else:
        return data


class SSEEventBatcher:
    """
    Batches similar SSE events for efficient database writes and reduced frontend spam.

    Features:
    - Groups similar events by type and worker
    - Time-based flush (configurable timeout)
    - Size-based flush (configurable batch size)
    - Thread-safe for concurrent worker access
    - Retry logic for failed batches
    - Event aggregation (N individual → 1 batch event)
    - Graceful shutdown with final flush
    """

    def __init__(
        self,
        sse_ops: SyncSSEEventsOperations,
        batch_size: int = SSE_BATCH_SIZE,
        batch_timeout: float = SSE_BATCH_TIMEOUT_SECONDS,
        max_retries: int = SSE_BATCH_MAX_RETRIES,
        retry_delay: float = SSE_BATCH_RETRY_DELAY,
    ):
        """
        Initialize SSE event batcher.

        Args:
            sse_ops: SSE operations service for database writes
            batch_size: Maximum events per batch before flush
            batch_timeout: Maximum seconds to wait before flush
            max_retries: Maximum retry attempts for failed batches
            retry_delay: Seconds to wait between retries
        """
        self.sse_ops = sse_ops
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Event batching storage - grouped by event type and worker
        self._event_batches: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._batch_timestamps: Dict[str, float] = {}

        # Thread safety
        self._lock = threading.RLock()
        self._shutdown = False

        # Background flush thread
        self._flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self._flush_event = threading.Event()
        self._flush_thread.start()

        # Statistics
        self._stats = {
            "events_batched": 0,
            "batches_created": 0,
            "batches_failed": 0,
            "events_saved": 0,  # Events that would have been individual
        }

        sse_logger.info(
            f"SSEEventBatcher initialized (batch_size={batch_size}, timeout={batch_timeout}s)"
        )

    def add_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: SSEPriority = SSEPriority.NORMAL,
        source: str = "worker",
        worker_name: Optional[str] = None,
    ) -> bool:
        """
        Add an SSE event to the appropriate batch.

        Args:
            event_type: Type of event (e.g., 'JOB_STARTED', 'JOB_COMPLETED')
            event_data: Event payload data
            priority: Event priority level
            source: Source of the event
            worker_name: Name of worker creating the event

        Returns:
            True if event was successfully added to batch
        """
        if self._shutdown:
            return False

        try:
            with self._lock:
                # Create batch key (group similar events together)
                batch_key = self._create_batch_key(event_type, worker_name, source)

                # Add event to batch (serialize data to handle Decimal objects)
                event = {
                    "event_type": event_type,
                    "event_data": _serialize_event_data(event_data),
                    "priority": (
                        priority.value if hasattr(priority, "value") else priority
                    ),
                    "source": source,
                    "worker_name": worker_name,
                    "timestamp": utc_timestamp(),
                }

                self._event_batches[batch_key].append(event)
                self._stats["events_batched"] += 1

                # Set batch timestamp if this is the first event in batch
                if batch_key not in self._batch_timestamps:
                    self._batch_timestamps[batch_key] = time.time()

                # Check if batch should be flushed immediately
                if len(self._event_batches[batch_key]) >= self.batch_size:
                    self._flush_batch_immediate(batch_key)

                return True

        except Exception as e:
            sse_logger.error(f"Failed to add SSE event to batch: {e}")
            return False

    def _create_batch_key(
        self, event_type: str, worker_name: Optional[str], source: str
    ) -> str:
        """Create a unique key for batching similar events."""
        return f"{worker_name or 'unknown'}_{event_type}_{source}"

    def _flush_worker(self) -> None:
        """Background worker that periodically flushes batches based on timeout."""
        while not self._shutdown:
            try:
                # Wait for flush event or timeout
                self._flush_event.wait(timeout=self.batch_timeout)

                if self._shutdown:
                    break

                # Flush any batches that have timed out
                self._flush_timeout_batches()

                # Clear the event for next cycle
                self._flush_event.clear()

            except Exception as e:
                sse_logger.error(f"Error in SSE batch flush worker: {e}")
                time.sleep(self.retry_delay)

    def _flush_timeout_batches(self) -> None:
        """Flush batches that have exceeded the timeout."""
        current_time = time.time()
        batches_to_flush = []

        with self._lock:
            for batch_key, batch_time in self._batch_timestamps.items():
                if current_time - batch_time >= self.batch_timeout:
                    if (
                        batch_key in self._event_batches
                        and self._event_batches[batch_key]
                    ):
                        batches_to_flush.append(batch_key)

        # Flush timed out batches
        for batch_key in batches_to_flush:
            self._flush_batch_immediate(batch_key)

    def _flush_batch_immediate(self, batch_key: str) -> None:
        """Flush a specific batch immediately."""
        events_to_flush = []

        with self._lock:
            if batch_key in self._event_batches and self._event_batches[batch_key]:
                events_to_flush = self._event_batches[batch_key].copy()
                self._event_batches[batch_key].clear()
                del self._batch_timestamps[batch_key]

        if events_to_flush:
            self._write_batch_to_database(batch_key, events_to_flush)

    def _write_batch_to_database(
        self, batch_key: str, events: List[Dict[str, Any]]
    ) -> None:
        """Write a batch of events to the database, with aggregation for similar events."""
        if not events:
            return

        try:
            # Aggregate similar events into batch events
            aggregated_events = self._aggregate_events(events)

            # Write to database using existing batch method
            event_ids = self.sse_ops.create_events_batch(aggregated_events)

            # Update statistics
            self._stats["batches_created"] += 1
            self._stats["events_saved"] += len(events) - len(
                aggregated_events
            )  # Events we didn't send individually

            sse_logger.debug(
                f"Flushed SSE batch {batch_key}: {len(events)} events → {len(aggregated_events)} aggregated events"
            )

        except Exception as e:
            self._stats["batches_failed"] += 1
            sse_logger.error(f"Failed to flush SSE batch {batch_key}: {e}")

            # Fallback: try individual writes
            self._fallback_individual_writes(events)

    def _aggregate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregate similar events into batch events to reduce frontend bombardment.

        Example:
        3x JOB_STARTED → 1x JOBS_BATCH_STARTED with job_ids array
        """
        if len(events) == 1:
            return events  # No aggregation needed for single events

        # Group events by exact type
        event_groups = defaultdict(list)
        for event in events:
            event_groups[event["event_type"]].append(event)

        aggregated = []

        for event_type, group_events in event_groups.items():
            if len(group_events) == 1:
                # Single event, keep as-is
                aggregated.extend(group_events)
            else:
                # Multiple similar events, create batch event
                batch_event = self._create_batch_event(event_type, group_events)
                aggregated.append(batch_event)

        return aggregated

    def _create_batch_event(
        self, event_type: str, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a single batch event from multiple similar events."""
        if not events:
            return {}

        first_event = events[0]

        # Extract common data
        worker_name = first_event.get("worker_name")
        source = first_event.get("source")
        priority = first_event.get("priority")

        # Aggregate event-specific data
        job_ids = []
        processing_times = []
        error_messages = []

        for event in events:
            event_data = event.get("event_data", {})
            if "job_id" in event_data:
                job_ids.append(event_data["job_id"])
            if "processing_time_ms" in event_data:
                processing_times.append(event_data["processing_time_ms"])
            if "error_message" in event_data:
                error_messages.append(event_data["error_message"])

        # Create batch event type
        if event_type.endswith("_JOB_STARTED"):
            batch_event_type = event_type.replace("_JOB_STARTED", "_JOBS_BATCH_STARTED")
        elif event_type.endswith("_JOB_COMPLETED"):
            batch_event_type = event_type.replace(
                "_JOB_COMPLETED", "_JOBS_BATCH_COMPLETED"
            )
        elif event_type.endswith("_job_failed_permanently"):
            batch_event_type = event_type.replace(
                "_job_failed_permanently", "_jobs_batch_failed_permanently"
            )
        elif event_type.endswith("_job_failed"):
            batch_event_type = event_type.replace("_job_failed", "_jobs_batch_failed")
        else:
            batch_event_type = f"{event_type}_BATCH"

        # Create aggregated event data (serialize to handle Decimal objects)
        batch_data = _serialize_event_data(
            {
                "worker_name": worker_name,
                "batch_count": len(events),
                "timestamp": utc_timestamp(),
            }
        )

        if job_ids:
            batch_data["job_ids"] = _serialize_event_data(job_ids)
        if processing_times:
            batch_data["processing_times_ms"] = _serialize_event_data(processing_times)
            batch_data["avg_processing_time_ms"] = _serialize_event_data(
                sum(processing_times) / len(processing_times)
            )
        if error_messages:
            batch_data["error_messages"] = _serialize_event_data(error_messages)

        return {
            "event_type": batch_event_type,
            "event_data": batch_data,
            "priority": _serialize_event_data(priority),
            "source": source,
        }

    def _fallback_individual_writes(self, events: List[Dict[str, Any]]) -> None:
        """Fallback to individual event writes if batch write fails."""
        success_count = 0

        for event in events:
            try:
                self.sse_ops.create_event(
                    event_type=event["event_type"],
                    event_data=_serialize_event_data(event["event_data"]),
                    priority=event["priority"],
                    source=event["source"],
                )
                success_count += 1
            except Exception as e:
                sse_logger.error(f"Failed to write individual SSE event fallback: {e}")

        if success_count > 0:
            sse_logger.info(
                f"Fallback successful for {success_count}/{len(events)} SSE events"
            )

    def flush_all(self) -> None:
        """Flush all pending batches immediately (for shutdown)."""
        batches_to_flush = []

        with self._lock:
            for batch_key in list(self._event_batches.keys()):
                if self._event_batches[batch_key]:
                    batches_to_flush.append(batch_key)

        for batch_key in batches_to_flush:
            self._flush_batch_immediate(batch_key)

    def get_stats(self) -> Dict[str, Any]:
        """Get batcher statistics."""
        with self._lock:
            return {
                **self._stats,
                "pending_batches": len(
                    [k for k, v in self._event_batches.items() if v]
                ),
                "total_pending_events": sum(
                    len(batch) for batch in self._event_batches.values()
                ),
            }

    def shutdown(self) -> None:
        """Gracefully shutdown the batcher."""
        sse_logger.info("Shutting down SSEEventBatcher...")

        self._shutdown = True
        self._flush_event.set()

        # Flush remaining batches
        self.flush_all()

        # Wait for flush thread to finish
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)

        sse_logger.info(
            f"SSEEventBatcher shutdown complete. Final stats: {self.get_stats()}"
        )

    def __del__(self):
        """Ensure cleanup on deletion."""
        if not self._shutdown:
            self.shutdown()
