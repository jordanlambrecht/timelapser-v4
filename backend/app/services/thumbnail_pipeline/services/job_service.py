# backend/app/services/thumbnail_pipeline/services/job_service.py
"""
Thumbnail Job Service - Job queue management for thumbnail generation.
"""

from typing import Any, Dict, List, Optional

from ....enums import LogSource, LoggerName
from ....services.logger import get_service_logger


from ....database.core import AsyncDatabase, SyncDatabase
from ....database.thumbnail_job_operations import (
    SyncThumbnailJobOperations,
    ThumbnailJobOperations,
)
from ....enums import (
    ThumbnailJobPriority,
    ThumbnailJobType,
)
from ....models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
)

logger = get_service_logger(LoggerName.THUMBNAIL_PIPELINE, LogSource.PIPELINE)


class SyncThumbnailJobService:
    """Synchronous thumbnail job service for worker processes."""

    def __init__(self, db: SyncDatabase, settings_service=None) -> None:
        """Initialize with sync database."""
        self.db = db
        self.thumbnail_job_ops = SyncThumbnailJobOperations(db)
        self.settings_service = settings_service

    def queue_job(
        self,
        image_id: int,
        priority: ThumbnailJobPriority = ThumbnailJobPriority.MEDIUM,
        force_regenerate: bool = False,
    ) -> Optional[int]:
        """Queue a thumbnail generation job."""
        try:
            job_data = ThumbnailGenerationJobCreate(
                image_id=image_id, priority=priority, job_type=ThumbnailJobType.SINGLE
            )
            job = self.thumbnail_job_ops.create_job(job_data)
            return job.id if job else None
        except Exception as e:
            logger.error(
                f"Failed to queue thumbnail job for image {image_id}", exception=e
            )
            return None

    def get_pending_jobs(self, batch_size: int = 5) -> List[ThumbnailGenerationJob]:
        """Get pending jobs for processing."""
        try:
            return self.thumbnail_job_ops.get_pending_jobs(batch_size=batch_size)
        except Exception as e:
            logger.error("Failed to get pending jobs", exception=e)
            return []

    def mark_job_completed(self, job_id: int, result: Dict[str, Any]) -> bool:
        """Mark job as completed."""
        try:
            processing_time = result.get("processing_time_ms", 0)
            return self.thumbnail_job_ops.mark_job_completed(
                job_id=job_id, processing_time_ms=processing_time
            )
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as completed", exception=e)
            return False

    def mark_job_failed(self, job_id: int, error: str) -> bool:
        """Mark job as failed."""
        try:
            return self.thumbnail_job_ops.mark_job_failed(
                job_id=job_id, error_message=error
            )
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed", exception=e)
            return False

    def mark_job_started(self, job_id: int) -> bool:
        """Mark job as started."""
        try:
            return self.thumbnail_job_ops.mark_job_started(job_id)
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as started", exception=e)
            return False

    def schedule_retry(self, job_id: int, retry_count: int, delay_minutes: int) -> bool:
        """Schedule job retry with delay."""
        try:
            return self.thumbnail_job_ops.schedule_retry(
                job_id, retry_count, delay_minutes
            )
        except Exception as e:
            logger.error(f"Failed to schedule retry for job {job_id}", exception=e)
            return False

    def cleanup_completed_jobs(self, older_than_hours: int) -> int:
        """Clean up old completed jobs."""
        try:
            return self.thumbnail_job_ops.cleanup_completed_jobs(older_than_hours)
        except Exception as e:
            logger.error("Failed to cleanup completed jobs", exception=e)
            return 0

    def get_job_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics."""
        try:
            return self.thumbnail_job_ops.get_job_statistics()
        except Exception as e:
            logger.error("Failed to get job statistics", exception=e)
            return {}


class ThumbnailJobService:
    """Async thumbnail job service for API endpoints."""

    def __init__(self, db: AsyncDatabase, settings_service=None) -> None:
        """Initialize with async database."""
        self.db = db
        self.thumbnail_job_ops = ThumbnailJobOperations(db)
        self.settings_service = settings_service

    async def queue_job(
        self,
        image_id: int,
        priority: ThumbnailJobPriority = ThumbnailJobPriority.MEDIUM,
        force_regenerate: bool = False,
    ) -> Optional[int]:
        """Queue a thumbnail generation job (async)."""
        try:
            job_data = ThumbnailGenerationJobCreate(
                image_id=image_id, priority=priority, job_type=ThumbnailJobType.SINGLE
            )
            job = await self.thumbnail_job_ops.create_job(job_data)
            return job.id if job else None
        except Exception as e:
            logger.error(
                f"Failed to queue thumbnail job for image {image_id}", exception=e
            )
            return None

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics (async)."""
        try:
            return await self.thumbnail_job_ops.get_job_statistics()
        except Exception as e:
            logger.error("Failed to get job statistics", exception=e)
            return {}
