"""
SSE worker for Timelapser v4.

Handles SSE events cleanup and maintenance tasks.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from ..database.core import AsyncDatabase
from ..database.sse_events_operations import SSEEventsOperations
from ..enums import LogEmoji, LoggerName, LogSource, WorkerType
from ..services.logger import get_service_logger
from ..services.sse_workflow_service import SSEWorkflowService
from ..utils.time_utils import utc_now
from .base_worker import BaseWorker
from .utils.worker_status_builder import WorkerStatusBuilder

logger = get_service_logger(LoggerName.SSE_WORKER, LogSource.WORKER)


class SSEWorker(BaseWorker):
    """
    Worker responsible for SSE events maintenance and cleanup.

    Handles:
    - Periodic cleanup of old processed SSE events
    - SSE event statistics monitoring
    - Database maintenance for SSE events table
    """

    def __init__(self, db: AsyncDatabase):
        """
        Initialize SSE worker with injected dependencies.

        Args:
            db: Async database instance
        """
        super().__init__("SSEWorker")
        self.db = db
        self.sse_ops = SSEEventsOperations(db)
        self.last_cleanup_time: Optional[datetime] = None

        # Initialize workflow service for Service Layer Boundary Pattern
        self.sse_service = SSEWorkflowService()

    async def initialize(self) -> None:
        """Initialize SSE worker resources."""
        logger.info("Initialized SSE worker", store_in_db=False, emoji=LogEmoji.SYSTEM)

    async def cleanup(self) -> None:
        """Cleanup SSE worker resources."""
        logger.info("Cleaned up SSE worker", store_in_db=False, emoji=LogEmoji.SYSTEM)

    async def cleanup_old_events(self, max_age_hours: int = 24) -> int:
        """
        Clean up old processed SSE events to prevent database bloat.

        Args:
            max_age_hours: Maximum age of processed events to keep in hours

        Returns:
            Number of events cleaned up
        """
        try:
            deleted_count = await self.sse_ops.cleanup_old_events(max_age_hours)

            # Track cleanup time for status reporting
            self.last_cleanup_time = utc_now()

            if deleted_count > 0:
                logger.info(
                    f"Cleaned up {deleted_count} old SSE events (older than {max_age_hours}h)",
                    emoji=LogEmoji.CLEANUP
                )
            else:
                logger.debug(
                    f"No old SSE events found for cleanup (older than {max_age_hours}h)",
                    store_in_db=False
                )

            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old SSE events: {e}", store_in_db=False)
            return 0

    async def get_sse_statistics(self) -> Dict[str, Any]:
        """
        Get SSE event statistics for monitoring.

        Returns:
            Dictionary with SSE statistics
        """
        try:
            stats = await self.sse_ops.get_event_stats()
            logger.debug(f"SSE statistics: {stats}", store_in_db=False)
            return stats

        except Exception as e:
            logger.error(f"Error getting SSE statistics: {e}", store_in_db=False)
            return {
                "total_events": 0,
                "pending_events": 0,
                "processed_events": 0,
                "error": str(e),
            }

    async def cleanup_unprocessed_events(self, max_age_hours: int = 72) -> int:
        """
        Clean up very old unprocessed events that may be stuck.

        Args:
            max_age_hours: Maximum age of unprocessed events to keep

        Returns:
            Number of stuck events cleaned up
        """
        try:
            # This would require a new method in SSEEventsOperations
            # For now, just log that this maintenance task exists
            logger.debug(
                f"Checking for stuck unprocessed events older than {max_age_hours}h",
                store_in_db=False
            )

            # Clean up stuck events using implemented method
            deleted_count = await self.sse_ops.cleanup_stuck_events(max_age_hours)

            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up stuck SSE events: {e}", store_in_db=False)
            return 0

    async def optimize_sse_table(self) -> bool:
        """
        Perform database maintenance on SSE events table.

        Returns:
            True if optimization succeeded
        """
        try:
            # This could include VACUUM, ANALYZE, or other DB maintenance
            logger.debug("SSE table optimization would run here", store_in_db=False)

            # TODO: Implement table optimization if needed
            # For PostgreSQL, this might include:
            # - VACUUM sse_events;
            # - ANALYZE sse_events;
            # - Checking for index health

            return True

        except Exception as e:
            logger.error(f"Error optimizing SSE events table: {e}", store_in_db=False)
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive SSE worker status using Service Layer Boundary Pattern.

        Returns:
            Dictionary with complete worker status
        """
        try:
            # Build explicit base status - no super() calls
            base_status = WorkerStatusBuilder.build_base_status(
                name=self.name,
                running=self.running,
                worker_type=WorkerType.SSE_WORKER.value
            )

            # Get current SSE statistics
            import asyncio

            try:
                sse_statistics = asyncio.run(self.get_sse_statistics())
            except Exception as e:
                logger.debug(f"Could not get SSE statistics: {e}", store_in_db=False)
                sse_statistics = {
                    "total_events": 0,
                    "pending_events": 0,
                    "processed_events": 0,
                }

            # Use service layer to get typed status object (Service Layer Boundary Pattern)
            sse_status = self.sse_service.get_worker_status(
                db=self.db,
                sse_ops=self.sse_ops,
                sse_statistics=sse_statistics,
                last_cleanup_time=self.last_cleanup_time,
            )

            # Add SSE-specific status information using typed object (follows VideoWorker pattern)
            base_status.update(
                {
                    "worker_type": sse_status.worker_type,
                    "sse_operations_status": sse_status.sse_operations_status,
                    "database_status": sse_status.database_status,
                    "total_events": sse_status.total_events,
                    "pending_events": sse_status.pending_events,
                    "processed_events": sse_status.processed_events,
                    "last_cleanup_time": (
                        sse_status.last_cleanup_time.isoformat()
                        if sse_status.last_cleanup_time
                        else None
                    ),
                    "cleanup_enabled": sse_status.cleanup_enabled,
                    # Computed properties from typed model (clean property access)
                    "is_healthy": sse_status.is_healthy,
                    "processing_rate": sse_status.processing_rate,
                    "has_pending_work": sse_status.has_pending_work,
                    "event_backlog_size": sse_status.event_backlog_size,
                }
            )

            return base_status

        except Exception as e:
            logger.error(f"Unexpected error getting SSE worker status: {e}", store_in_db=False)
            return WorkerStatusBuilder.build_error_status(
                name=self.name,
                worker_type=WorkerType.SSE_WORKER.value,
                error_type="unexpected",
                error_message=str(e)
            )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status for worker management system compatibility.

        This method provides simple binary health information separate
        from the detailed status reporting in get_status().
        """
        return WorkerStatusBuilder.build_simple_health_status(
            running=self.running,
            worker_type=WorkerType.SSE_WORKER.value,
            additional_checks={
                "sse_ops_available": self.sse_ops is not None,
                "database_available": self.db is not None,
            }
        )
