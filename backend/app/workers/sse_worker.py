"""
SSE worker for Timelapser v4.

Handles SSE events cleanup and maintenance tasks.
"""

from typing import Dict, Any

from .base_worker import BaseWorker
from ..database.sse_events_operations import SSEEventsOperations
from ..database.core import AsyncDatabase
from ..constants import DEFAULT_LOG_RETENTION_DAYS


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
        
    async def initialize(self) -> None:
        """Initialize SSE worker resources."""
        self.log_info("Initialized SSE worker")
        
    async def cleanup(self) -> None:
        """Cleanup SSE worker resources."""
        self.log_info("Cleaned up SSE worker")
        
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
            
            if deleted_count > 0:
                self.log_info(f"Cleaned up {deleted_count} old SSE events (older than {max_age_hours}h)")
            else:
                self.log_debug(f"No old SSE events found for cleanup (older than {max_age_hours}h)")
                
            return deleted_count
            
        except Exception as e:
            self.log_error("Error cleaning up old SSE events", e)
            return 0
            
    async def get_sse_statistics(self) -> Dict[str, Any]:
        """
        Get SSE event statistics for monitoring.
        
        Returns:
            Dictionary with SSE statistics
        """
        try:
            stats = await self.sse_ops.get_event_stats()
            self.log_debug(f"SSE statistics: {stats}")
            return stats
            
        except Exception as e:
            self.log_error("Error getting SSE statistics", e)
            return {
                "total_events": 0,
                "pending_events": 0,
                "processed_events": 0,
                "error": str(e)
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
            self.log_debug(f"Checking for stuck unprocessed events older than {max_age_hours}h")
            
            # TODO: Implement cleanup_stuck_events in SSEEventsOperations
            # deleted_count = await self.sse_ops.cleanup_stuck_events(max_age_hours)
            
            return 0
            
        except Exception as e:
            self.log_error("Error cleaning up stuck SSE events", e)
            return 0
            
    async def optimize_sse_table(self) -> bool:
        """
        Perform database maintenance on SSE events table.
        
        Returns:
            True if optimization succeeded
        """
        try:
            # This could include VACUUM, ANALYZE, or other DB maintenance
            self.log_debug("SSE table optimization would run here")
            
            # TODO: Implement table optimization if needed
            # For PostgreSQL, this might include:
            # - VACUUM sse_events;
            # - ANALYZE sse_events;
            # - Checking for index health
            
            return True
            
        except Exception as e:
            self.log_error("Error optimizing SSE events table", e)
            return False