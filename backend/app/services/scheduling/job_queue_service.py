# backend/app/services/scheduling/job_queue_service.py
"""
Job Queue Service - Centralized background job management.

This service provides a unified interface for creating, managing, and monitoring
background jobs across the application, eliminating duplication in job handling
patterns and providing consistent job lifecycle management.

Key Features:
- Unified job creation interface for all job types
- Automatic timestamp management with timezone awareness
- Consistent error handling and logging
- Optional SSE event broadcasting for job lifecycle events
- Job priority and status management
- Retry logic and failure handling

Supported Job Types:
- Thumbnail generation jobs
- Video generation jobs
- Overlay processing jobs
- Custom job types via extensible interface

Business Rules:
- All jobs get timezone-aware timestamps
- Job creation failures are logged consistently
- SSE events are broadcast for job lifecycle changes
- Priority-based job queuing is supported
"""

from typing import Dict, Any, Optional, Union, TYPE_CHECKING
from datetime import datetime
from loguru import logger

from ...database.core import AsyncDatabase, SyncDatabase
from ...database.thumbnail_job_operations import (
    ThumbnailJobOperations,
    SyncThumbnailJobOperations,
)
from ...database.overlay_job_operations import (
    OverlayJobOperations,
    SyncOverlayJobOperations,
)
from ...database.video_operations import VideoOperations, SyncVideoOperations
from ...database.sse_events_operations import (
    SSEEventsOperations,
    SyncSSEEventsOperations,
)
from ...models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
    VideoGenerationJob,
    VideoGenerationJobCreate,
)
from ...models.overlay_model import (
    OverlayGenerationJob,
    OverlayGenerationJobCreate,
)
from ...utils.time_utils import (
    get_timezone_aware_timestamp_async,
)
from ...enums import SSEPriority, JobPriority, JobStatus
from ...constants import (
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_TYPE_SINGLE,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
)

if TYPE_CHECKING:
    pass


class JobQueueService:
    """
    Centralized background job queue management using composition pattern.

    Responsibilities:
    - Unified job creation interface across all job types
    - Automatic timezone-aware timestamp management
    - Consistent error handling and logging patterns
    - Optional SSE event broadcasting for job events
    - Job lifecycle management coordination

    Interactions:
    - Uses job-specific operations for database access
    - Uses SSEEventsOperations for event broadcasting
    - Provides type-safe interfaces for all job types
    """

    def __init__(self, db: AsyncDatabase):
        """
        Initialize JobQueueService with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db
        self.thumbnail_job_ops = ThumbnailJobOperations(db)
        self.overlay_job_ops = OverlayJobOperations(db)
        self.video_ops = VideoOperations(db)
        self.sse_ops = SSEEventsOperations(db)

    async def create_thumbnail_job(
        self,
        image_id: int,
        priority: str = THUMBNAIL_JOB_PRIORITY_MEDIUM,
        job_type: str = THUMBNAIL_JOB_TYPE_SINGLE,
        broadcast_sse: bool = True,
    ) -> Optional[ThumbnailGenerationJob]:
        """
        Create a thumbnail generation job with centralized management.

        Args:
            image_id: ID of the image to generate thumbnail for
            priority: Job priority level
            job_type: Type of thumbnail job
            broadcast_sse: Whether to broadcast SSE events

        Returns:
            Created ThumbnailGenerationJob or None if creation failed
        """
        try:
            job_data = ThumbnailGenerationJobCreate(
                image_id=image_id,
                priority=priority,
                status=JobStatus.PENDING,
                job_type=job_type,
            )

            # Create job via database operations
            job = await self.thumbnail_job_ops.create_job(job_data)

            if job:
                logger.debug(f"✅ Created thumbnail job {job.id} for image {image_id}")

                # Broadcast SSE event if requested
                if broadcast_sse:
                    await self._broadcast_job_created_event(
                        job_type="thumbnail",
                        job_id=job.id,
                        related_id=image_id,
                        priority=priority,
                    )

                return job
            else:
                logger.warning(
                    f"❌ Failed to create thumbnail job for image {image_id}"
                )

                # Broadcast failure event if requested
                if broadcast_sse:
                    await self._broadcast_job_failed_event(
                        job_type="thumbnail",
                        related_id=image_id,
                        error="Job creation returned None",
                    )

                return None

        except Exception as e:
            logger.error(f"❌ Error creating thumbnail job for image {image_id}: {e}")

            # Broadcast failure event if requested
            if broadcast_sse:
                await self._broadcast_job_failed_event(
                    job_type="thumbnail",
                    related_id=image_id,
                    error=str(e),
                )

            return None

    async def create_video_job(
        self,
        job_data: Dict[str, Any],
        broadcast_sse: bool = True,
    ) -> Optional[VideoGenerationJob]:
        """
        Create a video generation job with centralized management.

        Args:
            job_data: Dictionary containing job configuration
            broadcast_sse: Whether to broadcast SSE events

        Returns:
            Created VideoGenerationJob or None if creation failed
        """
        try:
            # Ensure timezone-aware timestamp
            if "created_at" not in job_data:
                job_data["created_at"] = await get_timezone_aware_timestamp_async(
                    self.db
                )

            # Create job via database operations
            job = await self.video_ops.create_video_generation_job(job_data)

            if job:
                logger.debug(f"✅ Created video generation job {job.id}")

                # Broadcast SSE event if requested
                if broadcast_sse:
                    await self._broadcast_job_created_event(
                        job_type="video",
                        job_id=job.id,
                        related_id=job_data.get("timelapse_id"),
                        priority=job_data.get("priority", JobPriority.MEDIUM),
                    )

                return job
            else:
                logger.warning("❌ Failed to create video generation job")

                # Broadcast failure event if requested
                if broadcast_sse:
                    await self._broadcast_job_failed_event(
                        job_type="video",
                        related_id=job_data.get("timelapse_id"),
                        error="Job creation returned None",
                    )

                return None

        except Exception as e:
            logger.error(f"❌ Error creating video generation job: {e}")

            # Broadcast failure event if requested
            if broadcast_sse:
                await self._broadcast_job_failed_event(
                    job_type="video",
                    related_id=job_data.get("timelapse_id"),
                    error=str(e),
                )

            return None

    async def create_overlay_job(
        self,
        job_data: Dict[str, Any],
        broadcast_sse: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Create an overlay processing job with centralized management.

        Args:
            job_data: Dictionary containing job configuration
            broadcast_sse: Whether to broadcast SSE events

        Returns:
            Created overlay job data or None if creation failed
        """
        try:
            # Validate required fields
            image_id = job_data.get("image_id")
            if not image_id:
                logger.error("Missing required field: image_id")
                return None

            # Convert dict to proper model
            overlay_job_data = OverlayGenerationJobCreate(
                image_id=image_id,
                priority=job_data.get("priority", JobPriority.MEDIUM),
                status=job_data.get("status", JobStatus.PENDING),
                job_type=job_data.get("job_type", "single"),
            )

            # Create job via database operations
            job = await self.overlay_job_ops.create_job(overlay_job_data)

            if job:
                job_id = (
                    job.get("id") if isinstance(job, dict) else getattr(job, "id", None)
                )
                logger.debug(f"✅ Created overlay job {job_id}")

                # Broadcast SSE event if requested
                if broadcast_sse:
                    await self._broadcast_job_created_event(
                        job_type="overlay",
                        job_id=job_id,
                        related_id=job_data.get("image_id"),
                        priority=job_data.get("priority", JobPriority.MEDIUM),
                    )

                # Convert job to dict if it's a model
                if hasattr(job, "model_dump"):
                    return job.model_dump()
                elif isinstance(job, dict):
                    return job
                else:
                    return {"id": job_id} if job_id else None
            else:
                logger.warning("❌ Failed to create overlay job")

                # Broadcast failure event if requested
                if broadcast_sse:
                    await self._broadcast_job_failed_event(
                        job_type="overlay",
                        related_id=job_data.get("image_id"),
                        error="Job creation returned None",
                    )

                return None

        except Exception as e:
            logger.error(f"❌ Error creating overlay job: {e}")

            # Broadcast failure event if requested
            if broadcast_sse:
                await self._broadcast_job_failed_event(
                    job_type="overlay",
                    related_id=job_data.get("image_id"),
                    error=str(e),
                )

            return None

    async def _broadcast_job_created_event(
        self,
        job_type: str,
        job_id: Optional[int],
        related_id: Optional[int] = None,
        priority: str = SSEPriority.NORMAL,
    ) -> None:
        """
        Broadcast SSE event for successful job creation.

        Args:
            job_type: Type of job created
            job_id: ID of the created job
            related_id: Related entity ID (image_id, timelapse_id, etc.)
            priority: Job priority level
        """
        try:
            event_data = {
                "job_type": job_type,
                "job_id": job_id,
                "priority": priority,
                "operation": "created",
            }

            if related_id:
                event_data[f"{job_type}_related_id"] = str(related_id)

            await self.sse_ops.create_event(
                event_type=EVENT_JOB_CREATED,
                event_data=event_data,
                priority=SSEPriority.NORMAL,
                source="job_queue",
            )

        except Exception as e:
            logger.warning(f"Failed to broadcast job created event: {e}")

    async def _broadcast_job_failed_event(
        self,
        job_type: str,
        related_id: Optional[int] = None,
        error: str = "Unknown error",
    ) -> None:
        """
        Broadcast SSE event for failed job creation.

        Args:
            job_type: Type of job that failed
            related_id: Related entity ID (image_id, timelapse_id, etc.)
            error: Error message
        """
        try:
            event_data = {
                "job_type": job_type,
                "error": error,
                "operation": "creation_failed",
            }

            if related_id:
                event_data[f"{job_type}_related_id"] = str(related_id)

            await self.sse_ops.create_event(
                event_type=EVENT_JOB_FAILED,
                event_data=event_data,
                priority=SSEPriority.HIGH,
                source="job_queue",
            )

        except Exception as e:
            logger.warning(f"Failed to broadcast job failed event: {e}")


class SyncJobQueueService:
    """
    Sync job queue service for worker processes using composition pattern.

    This service provides synchronous job management for worker processes
    that need to create jobs without async/await complexity.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncJobQueueService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.thumbnail_job_ops = SyncThumbnailJobOperations(db)
        self.overlay_job_ops = SyncOverlayJobOperations(db)
        self.video_ops = SyncVideoOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)

    def create_thumbnail_job(
        self,
        image_id: int,
        priority: str = THUMBNAIL_JOB_PRIORITY_MEDIUM,
        job_type: str = THUMBNAIL_JOB_TYPE_SINGLE,
        broadcast_sse: bool = True,
    ) -> Optional[int]:
        """
        Create a thumbnail generation job (sync version).

        Args:
            image_id: ID of the image to generate thumbnail for
            priority: Job priority level
            job_type: Type of thumbnail job
            broadcast_sse: Whether to broadcast SSE events

        Returns:
            Created job ID or None if creation failed
        """
        try:
            job_data = ThumbnailGenerationJobCreate(
                image_id=image_id,
                priority=priority,
                status=JobStatus.PENDING,
                job_type=job_type,
            )

            # Create job via database operations
            job = self.thumbnail_job_ops.create_job(job_data)

            if job:
                if hasattr(job, "id"):
                    job_id = job.id
                elif isinstance(job, (int, str)):
                    job_id = int(job)
                else:
                    job_id = None
                logger.debug(f"✅ Created thumbnail job {job_id} for image {image_id}")

                # Broadcast SSE event if requested
                if broadcast_sse:
                    self._broadcast_job_created_event(
                        job_type="thumbnail",
                        job_id=job_id,
                        related_id=image_id,
                        priority=priority,
                    )

                return job_id
            else:
                logger.warning(
                    f"❌ Failed to create thumbnail job for image {image_id}"
                )

                # Broadcast failure event if requested
                if broadcast_sse:
                    self._broadcast_job_failed_event(
                        job_type="thumbnail",
                        related_id=image_id,
                        error="Job creation returned None",
                    )

                return None

        except Exception as e:
            logger.error(f"❌ Error creating thumbnail job for image {image_id}: {e}")

            # Broadcast failure event if requested
            if broadcast_sse:
                self._broadcast_job_failed_event(
                    job_type="thumbnail",
                    related_id=image_id,
                    error=str(e),
                )

            return None

    def _broadcast_job_created_event(
        self,
        job_type: str,
        job_id: Optional[int],
        related_id: Optional[int] = None,
        priority: str = SSEPriority.NORMAL,
    ) -> None:
        """
        Broadcast SSE event for successful job creation (sync version).

        Args:
            job_type: Type of job created
            job_id: ID of the created job
            related_id: Related entity ID (image_id, timelapse_id, etc.)
            priority: Job priority level
        """
        try:
            event_data = {
                "job_type": job_type,
                "job_id": job_id,
                "priority": priority,
                "operation": "created",
            }

            if related_id:
                event_data[f"{job_type}_related_id"] = str(related_id)

            self.sse_ops.create_event(
                event_type=EVENT_JOB_CREATED,
                event_data=event_data,
                priority=SSEPriority.NORMAL,
                source="job_queue",
            )

        except Exception as e:
            logger.warning(f"Failed to broadcast job created event: {e}")

    def _broadcast_job_failed_event(
        self,
        job_type: str,
        related_id: Optional[int] = None,
        error: str = "Unknown error",
    ) -> None:
        """
        Broadcast SSE event for failed job creation (sync version).

        Args:
            job_type: Type of job that failed
            related_id: Related entity ID (image_id, timelapse_id, etc.)
            error: Error message
        """
        try:
            event_data = {
                "job_type": job_type,
                "error": error,
                "operation": "creation_failed",
            }

            if related_id:
                event_data[f"{job_type}_related_id"] = str(related_id)

            self.sse_ops.create_event(
                event_type=EVENT_JOB_FAILED,
                event_data=event_data,
                priority=SSEPriority.HIGH,
                source="job_queue",
            )

        except Exception as e:
            logger.warning(f"Failed to broadcast job failed event: {e}")


# Backwards compatibility aliases
JobQueueService = JobQueueService
SyncJobQueueService = SyncJobQueueService
