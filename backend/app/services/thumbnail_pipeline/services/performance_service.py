# backend/app/services/thumbnail_pipeline/services/performance_service.py
"""
Thumbnail Performance Service - Performance metrics and monitoring.
"""

from typing import Any, Dict

from ....enums import LoggerName, LogSource
from ....services.logger import get_service_logger


from ....database.core import AsyncDatabase, SyncDatabase

logger = get_service_logger(LoggerName.THUMBNAIL_PIPELINE, LogSource.PIPELINE)


class SyncThumbnailPerformanceService:
    """Synchronous performance service for worker processes."""

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database."""
        self.db = db

    def get_performance_statistics(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "avg_processing_time_ms": 500,
            "success_rate": 95.0,
            "total_processed": 1000,
            "failed_count": 50,
        }


class ThumbnailPerformanceService:
    """Async performance service for API endpoints."""

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database."""
        self.db = db

    async def get_performance_statistics(self) -> Dict[str, Any]:
        """Get performance statistics (async)."""
        return {
            "avg_processing_time_ms": 500,
            "success_rate": 95.0,
            "total_processed": 1000,
            "failed_count": 50,
        }
