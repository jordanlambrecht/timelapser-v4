"""
Typed response models for SSE worker operations.

These models provide type-safe access to SSE workflow results and status information,
enhancing error handling and providing operational clarity.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class SSEWorkerStatus:
    """Comprehensive SSE worker status."""

    worker_type: str
    sse_operations_status: str
    database_status: str
    total_events: int = 0
    pending_events: int = 0
    processed_events: int = 0
    last_cleanup_time: Optional[datetime] = None
    cleanup_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "SSEWorkerStatus":
        """Create SSEWorkerStatus from dictionary for backward compatibility."""
        return cls(
            worker_type=data.get("worker_type", ""),
            sse_operations_status=data.get("sse_operations_status", ""),
            database_status=data.get("database_status", ""),
            total_events=data.get("total_events", 0),
            pending_events=data.get("pending_events", 0),
            processed_events=data.get("processed_events", 0),
            last_cleanup_time=data.get("last_cleanup_time"),
            cleanup_enabled=data.get("cleanup_enabled", True),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if SSE worker is healthy."""
        return (
            self.sse_operations_status == "healthy"
            and self.database_status == "healthy"
            and self.cleanup_enabled
        )

    @property
    def processing_rate(self) -> float:
        """Calculate processing rate (processed / total)."""
        if self.total_events == 0:
            return 1.0
        return self.processed_events / self.total_events

    @property
    def has_pending_work(self) -> bool:
        """Check if there are pending events to process."""
        return self.pending_events > 0

    @property
    def event_backlog_size(self) -> int:
        """Get the size of the event backlog."""
        return self.pending_events
