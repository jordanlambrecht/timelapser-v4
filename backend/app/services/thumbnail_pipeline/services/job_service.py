# backend/app/services/thumbnail_pipeline/services/job_service.py
"""
Thumbnail Job Service - Job queue management for thumbnail generation.
"""

from typing import List, Optional, Dict, Any
from loguru import logger

from ....database.core import SyncDatabase, AsyncDatabase
from ....database.thumbnail_job_operations import SyncThumbnailJobOperations
from ....models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
)
from ....enums import (
    JobPriority,
    JobStatus,
    JobTypes,
)


class SyncThumbnailJobService:
    """Synchronous thumbnail job service for worker processes."""

    def __init__(self, db: SyncDatabase, settings_service=None):
        """Initialize with sync database."""
        self.db = db
        self.thumbnail_job_ops = SyncThumbnailJobOperations(db)
        self.settings_service = settings_service

    def queue_job(
        self, image_id: int, priority: str = JobPriority.MEDIUM, force_regenerate: bool = False
    ) -> Optional[int]:
        """Queue a thumbnail generation job."""
        try:
            job_data = ThumbnailGenerationJobCreate(
                image_id=image_id, priority=priority, job_type="single"
            )
            job = self.thumbnail_job_ops.create_job(job_data)
            return job.id if job else None
        except Exception as e:
            logger.error(f"Failed to queue thumbnail job for image {image_id}: {e}")
            return None

    def get_pending_jobs(self, batch_size: int = 5) -> List[ThumbnailGenerationJob]:
        """Get pending jobs for processing."""
        try:
            return self.thumbnail_job_ops.get_pending_jobs(batch_size=batch_size)
        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}")
            return []

    def mark_job_completed(self, job_id: int, result: Dict[str, Any]) -> bool:
        """Mark job as completed."""
        try:
            processing_time = result.get("processing_time_ms", 0)
            return self.thumbnail_job_ops.mark_job_completed(
                job_id=job_id, processing_time_ms=processing_time
            )
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as completed: {e}")
            return False

    def mark_job_failed(self, job_id: int, error: str) -> bool:
        """Mark job as failed."""
        try:
            return self.thumbnail_job_ops.mark_job_failed(
                job_id=job_id, error_message=error
            )
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")
            return False

    def mark_job_started(self, job_id: int) -> bool:
        """Mark job as started."""
        try:
            return self.thumbnail_job_ops.mark_job_started(job_id)
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as started: {e}")
            return False

    def schedule_retry(self, job_id: int, retry_count: int, delay_minutes: int) -> bool:
        """Schedule job retry with delay."""
        try:
            return self.thumbnail_job_ops.schedule_retry(job_id, retry_count, delay_minutes)
        except Exception as e:
            logger.error(f"Failed to schedule retry for job {job_id}: {e}")
            return False

    def cleanup_completed_jobs(self, older_than_hours: int) -> int:
        """Clean up old completed jobs."""
        try:
            return self.thumbnail_job_ops.cleanup_completed_jobs(older_than_hours)
        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")
            return 0

    def get_job_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics."""
        try:
            return self.thumbnail_job_ops.get_job_statistics()
        except Exception as e:
            logger.error(f"Failed to get job statistics: {e}")
            return {}


class ThumbnailJobService:
    """Async thumbnail job service for API endpoints."""

    def __init__(self, db: AsyncDatabase, settings_service=None):
        """Initialize with async database."""
        self.db = db
        # TODO: Implement async operations when needed
        pass

    async def queue_job(
        self, image_id: int, priority: str = JobPriority.MEDIUM, force_regenerate: bool = False
    ) -> Optional[int]:
        """Queue a thumbnail generation job (async)."""
        # TODO: Implement async version when needed
        pass

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics (async)."""
        # TODO: Implement async version when needed
        return {}
