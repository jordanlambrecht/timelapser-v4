# backend/app/services/thumbnail_service.py
"""
Thumbnail Service - Job Queue-based architecture.

This service handles thumbnail-related business logic using job queues
and dependency injection, providing type-safe Pydantic model interfaces.

Responsibilities:
- Thumbnail job queue management
- Bulk job creation and tracking
- SSE broadcasting for real-time updates
- Job statistics and monitoring
"""
import os
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger


from ..database.timelapse_operations import TimelapseOperations
from ..config import settings
from ..utils.timezone_utils import utc_now
from ..utils.response_helpers import ResponseFormatter
from ..utils.cache_manager import MemoryCache
from ..utils.file_helpers import (
    scan_directory_for_thumbnails,
    parse_thumbnail_filename,
    delete_file_safe,
    calculate_directory_size,
)

# Global cache for session tracking (shared across all service instances)
_global_session_cache = MemoryCache()

from ..models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
    ThumbnailJobStatistics,
    BulkThumbnailRequest,
    BulkThumbnailResponse,
    ThumbnailRegenerationStatus,
    ThumbnailStatistics,
    ThumbnailGenerationResult,
)
from ..constants import (
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_PRIORITY_HIGH,
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_TYPE_SINGLE,
    THUMBNAIL_JOB_TYPE_BULK,
    THUMBNAIL_VERIFICATION_BATCH_SIZE,
    HIGH_LOAD_THUMBNAIL_JOB_BATCH_SIZE,
    BYTES_TO_MB_DIVISOR,
    BYTES_TO_KB_DIVISOR,
)


class ThumbnailService:
    """
    Thumbnail business logic service focused on job queue management.

    Responsibilities:
    - Thumbnail job creation and management
    - Bulk job operations with progress tracking
    - Real-time SSE progress broadcasting
    - Job queue statistics and monitoring

    Interactions:
    - Uses ThumbnailJobOperations for job queue management
    - Broadcasts SSE events for frontend updates
    - Coordinates with ThumbnailWorker through job queue
    """

    def __init__(
        self,
        thumbnail_job_ops,
        sse_operations,
        image_operations=None,
        thumbnail_job_service=None,
        settings_service=None,
    ):
        """
        Initialize ThumbnailService with dependency injection.

        Args:
            thumbnail_job_ops: ThumbnailJobOperations for job queue management
            sse_operations: SSEEventsOperations for real-time updates
            image_operations: ImageOperations for database queries (optional)
            thumbnail_job_service: ThumbnailJobService for job management (optional)
            settings_service: SettingsService for accessing application settings (optional)
        """
        self.thumbnail_job_ops = thumbnail_job_ops
        self.sse_operations = sse_operations
        self.image_operations = image_operations
        self.thumbnail_job_service = thumbnail_job_service
        self.settings_service = settings_service
        # Use global cache for session tracking to persist across requests
        self._session_cache = _global_session_cache

    async def create_thumbnail_job(
        self, job_data: ThumbnailGenerationJobCreate
    ) -> Optional[ThumbnailGenerationJob]:
        """
        Create a single thumbnail generation job.

        Args:
            job_data: Job creation data

        Returns:
            Created job or None if creation failed
        """
        try:
            job = await self.thumbnail_job_ops.create_job(job_data)

            if job:
                # Broadcast SSE event for job creation
                try:
                    await self.sse_operations.create_event(
                        event_type="thumbnail_job_created",
                        event_data={
                            "job_id": job.id,
                            "image_id": job.image_id,
                            "priority": job.priority,
                            "job_type": job.job_type,
                        },
                        priority="normal",
                        source="thumbnail_service",
                    )
                except Exception as sse_error:
                    logger.warning(
                        f"Failed to broadcast job creation SSE event: {sse_error}"
                    )

            return job

        except Exception as e:
            logger.error(f"Error creating thumbnail job: {e}")
            return None

    async def _create_thumbnail_job_helper(
        self, image_id: int, priority: str = THUMBNAIL_JOB_PRIORITY_MEDIUM
    ) -> Optional[ThumbnailGenerationJob]:
        """
        Helper method to create thumbnail jobs consistently.

        Args:
            image_id: ID of the image to create job for
            priority: Job priority using constants

        Returns:
            Created job or None if failed
        """
        try:
            if self.thumbnail_job_service:
                return await self.thumbnail_job_service.queue_job(
                    image_id=image_id,
                    priority=priority,
                )
            else:
                job_data = ThumbnailGenerationJobCreate(
                    image_id=image_id,
                    priority=priority,
                    status=THUMBNAIL_JOB_STATUS_PENDING,
                    job_type=THUMBNAIL_JOB_TYPE_SINGLE,
                )
                return await self.thumbnail_job_ops.create_job(job_data)
        except Exception as e:
            logger.warning(f"Failed to create job for image {image_id}: {e}")
            return None

    async def generate_thumbnail_for_image(
        self, image_id: int, force_regenerate: bool = False
    ) -> ThumbnailGenerationResult:
        """
        Generate thumbnail for a specific image.

        Args:
            image_id: ID of the image to generate thumbnails for
            force_regenerate: Whether to regenerate existing thumbnails

        Returns:
            ThumbnailGenerationResult with generation details
        """
        try:
            logger.info(
                f"Generating thumbnail for image {image_id} (force_regenerate={force_regenerate})"
            )

            # Check if image exists and get its details
            if not self.image_operations:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error="Image operations service not available",
                )

            # Get image details
            image = await self.image_operations.get_image_by_id(image_id)
            if not image:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Image {image_id} not found",
                )

            # Check if thumbnails already exist (unless force regenerate)
            if not force_regenerate and image.thumbnail_path and image.small_path:
                return ThumbnailGenerationResult(
                    success=True,
                    image_id=image_id,
                    timelapse_id=image.timelapse_id,
                    thumbnail_path=image.thumbnail_path,
                    small_path=image.small_path,
                )

            # Create thumbnail job with high priority for individual requests
            job = await self._create_thumbnail_job_helper(
                image_id=image_id, priority=THUMBNAIL_JOB_PRIORITY_HIGH
            )

            if not job:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error="Failed to create thumbnail job",
                )

            # Broadcast SSE event for individual thumbnail generation
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_individual_requested",
                    event_data={
                        "image_id": image_id,
                        "job_id": job.id,
                        "force_regenerate": force_regenerate,
                        "priority": job.priority,
                    },
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(
                    f"Failed to broadcast individual thumbnail SSE event: {sse_error}"
                )

            return ThumbnailGenerationResult(
                success=True,
                image_id=image_id,
                timelapse_id=image.timelapse_id,
                processing_time_ms=0,  # Will be calculated in router
            )

        except Exception as e:
            logger.error(f"Error generating thumbnail for image {image_id}: {e}")
            return ThumbnailGenerationResult(
                success=False,
                image_id=image_id,
                error=f"Failed to generate thumbnail: {str(e)}",
            )

    async def queue_single_image_thumbnail(
        self, image_id: int, priority: str = THUMBNAIL_JOB_PRIORITY_MEDIUM
    ) -> Optional[ThumbnailGenerationJob]:
        """
        Queue thumbnail generation for a single image.

        Args:
            image_id: ID of the image to generate thumbnails for
            priority: Job priority (use constants)

        Returns:
            Created job or None if creation failed
        """
        return await self._create_thumbnail_job_helper(image_id, priority)

    async def queue_bulk_thumbnails(
        self, request: BulkThumbnailRequest
    ) -> BulkThumbnailResponse:
        """
        Queue thumbnail generation for multiple images.

        Args:
            request: Bulk thumbnail generation request

        Returns:
            Summary of bulk operation results
        """
        response = BulkThumbnailResponse(
            total_requested=len(request.image_ids),
            jobs_created=0,
            jobs_failed=0,
            created_job_ids=[],
            failed_image_ids=[],
        )

        try:
            # Create jobs for each image
            for image_id in request.image_ids:
                job_data = ThumbnailGenerationJobCreate(
                    image_id=image_id,
                    priority=request.priority,
                    status=THUMBNAIL_JOB_STATUS_PENDING,
                    job_type=THUMBNAIL_JOB_TYPE_BULK,
                )

                job = await self.create_thumbnail_job(job_data)

                if job:
                    response.jobs_created += 1
                    response.created_job_ids.append(job.id)
                else:
                    response.jobs_failed += 1
                    response.failed_image_ids.append(image_id)

            # Broadcast bulk operation SSE event
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_bulk_queued",
                    event_data={
                        "total_jobs": response.jobs_created,
                        "failed_jobs": response.jobs_failed,
                        "priority": request.priority,
                    },
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(
                    f"Failed to broadcast bulk operation SSE event: {sse_error}"
                )

        except Exception as e:
            logger.error(f"Error in bulk thumbnail operation: {e}")

        return response

    async def get_job_statistics(self) -> ThumbnailJobStatistics:
        """
        Get thumbnail job queue statistics.

        Returns:
            Job queue statistics
        """
        try:
            stats_data = await self.thumbnail_job_ops.get_job_statistics()
            return ThumbnailJobStatistics(**stats_data)
        except Exception as e:
            logger.error(f"Error getting job statistics: {e}")
            return ThumbnailJobStatistics()  # Return empty stats on error

    async def cancel_jobs_for_image(self, image_id: int) -> int:
        """
        Cancel all pending jobs for a specific image.

        Args:
            image_id: ID of the image

        Returns:
            Number of jobs cancelled
        """
        try:
            cancelled_count = await self.thumbnail_job_ops.cancel_jobs_for_image(
                image_id
            )

            if cancelled_count > 0:
                # Broadcast cancellation SSE event
                try:
                    await self.sse_operations.create_event(
                        event_type="thumbnail_jobs_cancelled",
                        event_data={
                            "image_id": image_id,
                            "cancelled_count": cancelled_count,
                        },
                        priority="normal",
                        source="thumbnail_service",
                    )
                except Exception as sse_error:
                    logger.warning(
                        f"Failed to broadcast job cancellation SSE event: {sse_error}"
                    )

            return cancelled_count

        except Exception as e:
            logger.error(f"Error cancelling jobs for image {image_id}: {e}")
            return 0

    async def cleanup_completed_jobs(self, older_than_hours: int = 24) -> int:
        """
        Clean up old completed jobs.

        Args:
            older_than_hours: Remove jobs completed more than this many hours ago

        Returns:
            Number of jobs cleaned up
        """
        try:
            return await self.thumbnail_job_ops.cleanup_completed_jobs(older_than_hours)
        except Exception as e:
            logger.error(f"Error cleaning up completed jobs: {e}")
            return 0

    async def get_job_by_id(self, job_id: int) -> Optional[ThumbnailGenerationJob]:
        """
        Get a specific job by ID.

        Args:
            job_id: ID of the job

        Returns:
            Job details or None if not found
        """
        try:
            return await self.thumbnail_job_ops.get_job_by_id(job_id)
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None

    async def verify_timelapse_thumbnails(
        self, timelapse_id: int, timelapse_operations
    ) -> dict:
        """
        Verify thumbnail integrity for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse
            timelapse_operations: TimelapseOperations instance for database access

        Returns:
            Verification result dictionary
        """
        try:
            logger.info(f"Starting thumbnail verification for timelapse {timelapse_id}")

            # Get current cached counts from timelapse
            timelapse_before = await timelapse_operations.get_timelapse_by_id(
                timelapse_id
            )
            if not timelapse_before:
                raise ValueError(f"Timelapse {timelapse_id} not found")

            cached_thumbnail_count = timelapse_before.thumbnail_count
            cached_small_count = timelapse_before.small_count

            # Recalculate actual counts from database
            recalculation_success = (
                await timelapse_operations.recalculate_thumbnail_counts(timelapse_id)
            )

            if not recalculation_success:
                raise Exception("Failed to recalculate thumbnail counts")

            # Get updated counts
            timelapse_after = await timelapse_operations.get_timelapse_by_id(
                timelapse_id
            )
            actual_thumbnail_count = timelapse_after.thumbnail_count
            actual_small_count = timelapse_after.small_count

            # Calculate discrepancies
            thumbnail_discrepancy = actual_thumbnail_count - cached_thumbnail_count
            small_discrepancy = actual_small_count - cached_small_count

            verification_result = {
                "timelapse_id": timelapse_id,
                "verification_completed": True,
                "cached_counts": {
                    "thumbnail_count": cached_thumbnail_count,
                    "small_count": cached_small_count,
                },
                "actual_counts": {
                    "thumbnail_count": actual_thumbnail_count,
                    "small_count": actual_small_count,
                },
                "discrepancies": {
                    "thumbnail_discrepancy": thumbnail_discrepancy,
                    "small_discrepancy": small_discrepancy,
                    "counts_corrected": thumbnail_discrepancy != 0
                    or small_discrepancy != 0,
                },
                "status": (
                    "verified_and_corrected"
                    if (thumbnail_discrepancy != 0 or small_discrepancy != 0)
                    else "verified_no_issues"
                ),
            }

            # Broadcast verification SSE event
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_verification_completed",
                    event_data=verification_result,
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(
                    f"Failed to broadcast verification SSE event: {sse_error}"
                )

            logger.info(
                f"Thumbnail verification completed for timelapse {timelapse_id}: {verification_result['status']}"
            )
            return verification_result

        except Exception as e:
            logger.error(
                f"Error verifying thumbnails for timelapse {timelapse_id}: {e}"
            )
            raise

    async def remove_all_timelapse_thumbnails(
        self, timelapse_id: int, image_operations, timelapse_operations
    ) -> dict:
        """
        Remove all thumbnails for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse
            image_operations: ImageOperations instance for database access
            timelapse_operations: TimelapseOperations instance for database access

        Returns:
            Removal result dictionary
        """
        try:
            logger.info(f"Starting thumbnail removal for timelapse {timelapse_id}")

            # Get images for counting before removal
            images_to_process = await image_operations.get_images_by_timelapse_id(
                timelapse_id
            )

            if not images_to_process:
                return {
                    "timelapse_id": timelapse_id,
                    "message": "No images found in timelapse",
                    "thumbnails_removed": 0,
                    "small_thumbnails_removed": 0,
                    "images_processed": 0,
                }

            # Count existing thumbnails before removal
            thumbnails_to_remove = sum(
                1 for img in images_to_process if img.thumbnail_path
            )
            small_thumbnails_to_remove = sum(
                1 for img in images_to_process if img.small_path
            )

            # Clear thumbnail paths in images table
            affected_rows = await image_operations.clear_thumbnail_paths_for_timelapse(
                timelapse_id
            )

            # Reset thumbnail counts in timelapse table
            await timelapse_operations.recalculate_thumbnail_counts(timelapse_id)

            removal_result = {
                "timelapse_id": timelapse_id,
                "message": "Thumbnails removed successfully",
                "images_processed": affected_rows,
                "thumbnails_removed": thumbnails_to_remove,
                "small_thumbnails_removed": small_thumbnails_to_remove,
                "database_paths_cleared": True,
            }

            # Broadcast removal SSE event
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_bulk_removed",
                    event_data=removal_result,
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(f"Failed to broadcast removal SSE event: {sse_error}")

            logger.info(
                f"Thumbnail removal completed for timelapse {timelapse_id}: {affected_rows} images processed"
            )
            return removal_result

        except Exception as e:
            logger.error(f"Error removing thumbnails for timelapse {timelapse_id}: {e}")
            raise

    async def start_thumbnail_regeneration_background(self, limit: int = 1000) -> dict:
        """
        Start thumbnail regeneration for all images using background processing.
        Returns immediately while processing continues in the background.

        Args:
            limit: Maximum number of images to process

        Returns:
            Dictionary with session_id and immediate success status
        """
        try:
            logger.info(
                f"Starting background thumbnail regeneration for up to {limit} images (ALL images, not just missing thumbnails)"
            )

            # Get job statistics to understand current queue state
            stats = await self.get_job_statistics()

            # If there are already many pending jobs, inform user
            if stats.pending_jobs > 100:
                return ResponseFormatter.error(
                    f"Large job queue detected ({stats.pending_jobs} pending jobs). Please wait for current jobs to complete.",
                    error_code="QUEUE_OVERLOADED",
                    details={"pending_jobs": stats.pending_jobs, "limit": limit},
                )

            # Check if image_operations is available
            if not self.image_operations:
                return ResponseFormatter.error(
                    "Image operations service not available",
                    error_code="SERVICE_UNAVAILABLE",
                    details={"missing_dependency": "image_operations"},
                )

            # Get ALL images for regeneration (not just missing thumbnails)
            all_images = await self.image_operations.get_images_for_regeneration(limit)

            total_images_count = len(all_images)

            if total_images_count == 0:
                return ResponseFormatter.success(
                    "No images found in the system",
                    data={
                        "total_images": 0,
                        "jobs_created": 0,
                        "operation": "background_regeneration",
                    },
                )

            # Create regeneration session tracking
            session_id = f"regen_{int(utc_now().timestamp())}"
            regeneration_session = {
                "session_id": session_id,
                "total_images": total_images_count,
                "jobs_created": 0,
                "processed_images": 0,
                "started_at": utc_now(),
                "completed_at": None,
                "status": "running",
            }

            # Store session for tracking using cache (30 minute TTL)
            await self._session_cache.set(
                f"regen_session_{session_id}",
                regeneration_session,
                ttl_seconds=1800,  # 30 minutes
            )

            # Store current session pointer for easy lookup
            await self._session_cache.set(
                "current_regen_session", session_id, ttl_seconds=1800
            )

            # Broadcast initial SSE event with total count
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_regeneration_started",
                    event_data={
                        "session_id": session_id,
                        "total": total_images_count,  # Frontend expects "total"
                        "completed": 0,  # Frontend expects "completed"
                        "progress": 0,
                        "current_image": "Initializing...",  # Frontend expects "current_image"
                        "errors": 0,  # Frontend expects "errors"
                        "status": "initializing",
                        "operation": "background_regeneration",
                    },
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(
                    f"Failed to broadcast initial regeneration SSE event: {sse_error}"
                )

            # Start background processing task
            asyncio.create_task(
                self._process_thumbnail_regeneration_background(session_id, all_images)
            )

            # Return immediately with session info
            return ResponseFormatter.success(
                f"Background thumbnail regeneration started for {total_images_count} images",
                data={
                    "session_id": session_id,
                    "total_images": total_images_count,
                    "operation": "background_regeneration",
                    "status": "started",
                },
            )

        except Exception as e:
            logger.error(f"Error starting background thumbnail regeneration: {e}")
            return ResponseFormatter.error(
                f"Failed to start thumbnail regeneration: {str(e)}",
                error_code="REGENERATION_FAILED",
                details={"limit": limit},
            )

    async def _process_thumbnail_regeneration_background(
        self, session_id: str, images_to_process: list
    ) -> None:
        """
        Background task for processing thumbnail regeneration in batches.

        Args:
            session_id: Session identifier for tracking
            images_to_process: List of ALL images to regenerate thumbnails for
        """
        try:
            logger.info(f"Starting background processing for session {session_id}")

            regeneration_session = await self._session_cache.get(
                f"regen_session_{session_id}"
            )
            if not regeneration_session:
                logger.error(
                    f"Session {session_id} not found during background processing"
                )
                return

            total_images = len(images_to_process)

            # Update session with actual image count (might be different from requested limit)
            regeneration_session["total_images"] = total_images
            await self._session_cache.set(
                f"regen_session_{session_id}", regeneration_session, ttl_seconds=1800
            )

            batch_size = HIGH_LOAD_THUMBNAIL_JOB_BATCH_SIZE  # Use constant instead of hardcoded value
            jobs_created = 0
            processed_count = 0

            # Process images in batches
            for i in range(0, total_images, batch_size):
                batch = images_to_process[i : i + batch_size]
                batch_jobs_created = 0

                # Add a small delay to make the initializing phase more observable
                await asyncio.sleep(0.5)

                # Create jobs for this batch using helper method
                for image in batch:
                    job = await self._create_thumbnail_job_helper(
                        image_id=image[
                            "id"
                        ],  # image is now a dictionary, not an Image object
                        priority=THUMBNAIL_JOB_PRIORITY_HIGH,
                    )

                    if job:
                        batch_jobs_created += 1
                        jobs_created += 1

                processed_count += len(batch)
                progress = int((processed_count / total_images) * 100)

                # Update session
                regeneration_session["jobs_created"] = jobs_created
                regeneration_session["processed_images"] = processed_count

                # Save updated session to cache
                await self._session_cache.set(
                    f"regen_session_{session_id}",
                    regeneration_session,
                    ttl_seconds=1800,
                )

                # Broadcast progress update after each batch
                try:
                    await self.sse_operations.create_event(
                        event_type="thumbnail_regeneration_progress",
                        event_data={
                            "session_id": session_id,
                            "total": total_images,  # Frontend expects "total"
                            "completed": processed_count,  # Frontend expects "completed"
                            "progress": progress,
                            "current_image": f"Processing batch {i // batch_size + 1} of {(total_images + batch_size - 1) // batch_size}",  # Frontend expects "current_image"
                            "errors": 0,  # Frontend expects "errors"
                            "status": "creating_jobs",
                            "jobs_created": jobs_created,
                            "batch_completed": i // batch_size + 1,
                            "total_batches": (total_images + batch_size - 1)
                            // batch_size,
                        },
                        priority="normal",
                        source="thumbnail_service",
                    )
                except Exception as sse_error:
                    logger.warning(
                        f"Failed to broadcast progress SSE event: {sse_error}"
                    )

                # Small delay between batches to prevent overwhelming the system
                if i + batch_size < total_images:
                    await asyncio.sleep(0.1)

            # Mark session as completed
            regeneration_session["status"] = "completed"
            regeneration_session["completed_at"] = utc_now()

            # Save completed session to cache
            await self._session_cache.set(
                f"regen_session_{session_id}", regeneration_session, ttl_seconds=1800
            )

            # Keep current session pointer for a bit so status can be checked
            # Clear it after 5 minutes to allow status queries
            await self._session_cache.set(
                "current_regen_session", session_id, ttl_seconds=300
            )

            # Broadcast completion event
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_regeneration_complete",  # Use consistent naming
                    event_data={
                        "session_id": session_id,
                        "total": total_images,  # Frontend expects "total"
                        "completed": processed_count,  # Frontend expects "completed"
                        "progress": 100,
                        "current_image": "Complete!",  # Frontend expects "current_image"
                        "errors": 0,  # Frontend expects "errors"
                        "status": "completed",
                        "jobs_created": jobs_created,
                        "operation": "background_regeneration",
                    },
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(f"Failed to broadcast completion SSE event: {sse_error}")

            # Clean up any remaining failed jobs from this regeneration session
            try:
                if self.thumbnail_job_service:
                    # Cancel any remaining pending jobs (these would be retries that haven't succeeded)
                    cancelled_jobs = (
                        await self.thumbnail_job_service.cancel_pending_jobs()
                    )
                    if cancelled_jobs > 0:
                        logger.info(
                            f"Cleaned up {cancelled_jobs} remaining jobs after regeneration completion"
                        )

                        # Broadcast cleanup event
                        try:
                            await self.sse_operations.create_event(
                                event_type="thumbnail_jobs_cleaned_up",
                                event_data={
                                    "session_id": session_id,
                                    "cancelled_jobs": cancelled_jobs,
                                    "reason": "regeneration_completion_cleanup",
                                },
                                priority="low",
                                source="thumbnail_service",
                            )
                        except Exception as cleanup_sse_error:
                            logger.warning(
                                f"Failed to broadcast cleanup SSE event: {cleanup_sse_error}"
                            )
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to clean up remaining jobs after regeneration: {cleanup_error}"
                )

            logger.info(
                f"Background regeneration completed for session {session_id}: {jobs_created} jobs created for {total_images} images"
            )

        except Exception as e:
            logger.error(f"Error in background regeneration processing: {e}")

            # Mark session as failed
            regeneration_session = await self._session_cache.get(
                f"regen_session_{session_id}"
            )
            if regeneration_session:
                regeneration_session["status"] = "failed"
                regeneration_session["completed_at"] = utc_now()

                # Save failed session to cache
                await self._session_cache.set(
                    f"regen_session_{session_id}",
                    regeneration_session,
                    ttl_seconds=1800,
                )

                # Keep current session pointer for status queries
                await self._session_cache.set(
                    "current_regen_session", session_id, ttl_seconds=300
                )

            # Broadcast error event
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_regeneration_error",
                    event_data={
                        "session_id": session_id,
                        "error": str(e),
                        "status": "failed",
                        "operation": "background_regeneration",
                    },
                    priority="high",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(f"Failed to broadcast error SSE event: {sse_error}")

    async def get_thumbnail_regeneration_status(self) -> ThumbnailRegenerationStatus:
        """
        Get current thumbnail regeneration status.

        Returns:
            ThumbnailRegenerationStatus with current progress
        """
        try:
            logger.info("🔍 Getting thumbnail regeneration status")

            # Get current session ID from cache
            current_session_id = await self._session_cache.get("current_regen_session")
            active_session = None

            logger.info(f"🔑 Current session ID from cache: {current_session_id}")

            if current_session_id:
                # Get the session data
                active_session = await self._session_cache.get(
                    f"regen_session_{current_session_id}"
                )

                if active_session:
                    logger.info(
                        f"📋 Found session {current_session_id}: status={active_session.get('status', 'unknown')}"
                    )
                    logger.info(
                        f"📊 Session data keys: {list(active_session.keys()) if isinstance(active_session, dict) else 'Not a dict'}"
                    )
                else:
                    logger.info(
                        f"⚠️ Current session {current_session_id} not found in cache"
                    )
            else:
                logger.info("🚫 No current session pointer found")

            if active_session:
                logger.debug(
                    f"📊 Processing session {current_session_id}: {active_session}"
                )
                session_status = active_session["status"]

                # Handle cancelled sessions
                if session_status == "cancelled":
                    logger.info(f"Found cancelled session {current_session_id}, transitioning to idle")
                    
                    # Clear session cache immediately for cancelled sessions
                    await self._session_cache.set(
                        "current_regen_session", None, ttl_seconds=1
                    )
                    await self._session_cache.delete(
                        f"regen_session_{current_session_id}"
                    )

                    return ThumbnailRegenerationStatus(
                        active=False,
                        progress=0,
                        total=0,
                        completed=0,
                        errors=0,
                        status_message="cancelled",
                    )

                # Handle completed sessions
                if session_status == "completed":
                    total_jobs = active_session["jobs_created"]
                    completed_at = active_session.get("completed_at")

                    # Check if we should transition to idle
                    # Transition to idle if completed more than 5 minutes ago OR no pending/processing jobs remain
                    stats = await self.get_job_statistics()
                    should_transition_to_idle = False

                    if completed_at:
                        from datetime import timedelta

                        time_since_completion = utc_now() - completed_at
                        if time_since_completion > timedelta(minutes=5):
                            should_transition_to_idle = True

                    # Also transition if no jobs are active
                    if (stats.pending_jobs + stats.processing_jobs) == 0:
                        should_transition_to_idle = True

                    if should_transition_to_idle:
                        logger.info(
                            f"Transitioning completed session {current_session_id} to idle status"
                        )

                        # Clear session cache
                        await self._session_cache.set(
                            "current_regen_session", None, ttl_seconds=1
                        )
                        await self._session_cache.delete(
                            f"regen_session_{current_session_id}"
                        )

                        return ThumbnailRegenerationStatus(
                            active=False,
                            progress=0,
                            total=0,
                            completed=0,
                            errors=0,
                            status_message="idle",
                        )

                    # Still in completed state
                    return ThumbnailRegenerationStatus(
                        active=False,
                        progress=100,
                        total=total_jobs,
                        completed=total_jobs,
                        errors=0,
                        current_image_id=None,
                        current_image="Complete!",
                        estimated_time_remaining_seconds=0,
                        started_at=active_session["started_at"],
                        status_message="completed",
                    )

                # Handle running sessions
                # Get current job statistics for this session
                stats = await self.get_job_statistics()

                # Determine current phase based on session state
                total_images_to_process = active_session.get("total_images", 0)
                jobs_created = active_session["jobs_created"]
                processed_images = active_session.get("processed_images", 0)

                logger.debug(
                    f"🔢 Session metrics: total_images={total_images_to_process}, jobs_created={jobs_created}, processed_images={processed_images}"
                )
                logger.debug(
                    f"🎯 Phase check: processed_images ({processed_images}) < total_images_to_process ({total_images_to_process}) = {processed_images < total_images_to_process}"
                )

                # Phase 1: Job Creation (initializing)
                if processed_images < total_images_to_process:
                    # Still creating jobs - show initializing status
                    progress = (
                        int((processed_images / total_images_to_process) * 100)
                        if total_images_to_process > 0
                        else 0
                    )
                    status_message = "initializing"

                    logger.debug(
                        f"🚀 Phase 1 - Initializing: progress={progress}%, processed={processed_images}/{total_images_to_process}"
                    )

                    return ThumbnailRegenerationStatus(
                        active=True,
                        progress=min(100, progress),
                        total=total_images_to_process,
                        completed=0,  # No thumbnails created yet
                        errors=0,
                        current_image_id=None,
                        current_image=f"Creating job batch {(processed_images // 50) + 1} of {(total_images_to_process + 49) // 50}",
                        estimated_time_remaining_seconds=None,
                        started_at=active_session["started_at"],
                        status_message=status_message,
                    )

                # Phase 2: Actual Processing
                else:
                    # Job creation complete, now processing thumbnails
                    total_jobs = jobs_created
                    completed_jobs = max(0, stats.completed_jobs_24h)
                    failed_jobs = max(0, stats.failed_jobs_24h)

                    progress = (
                        int((completed_jobs / total_jobs) * 100)
                        if total_jobs > 0
                        else 0
                    )

                    logger.debug(
                        f"⚙️ Phase 2 - Processing: progress={progress}%, completed={completed_jobs}/{total_jobs}"
                    )

                    # Estimate time remaining based on average processing time
                    remaining_jobs = total_jobs - completed_jobs - failed_jobs
                    estimated_time = None
                    if remaining_jobs > 0 and stats.avg_processing_time_ms > 0:
                        estimated_time = int(
                            (remaining_jobs * stats.avg_processing_time_ms) / 1000
                        )

                    return ThumbnailRegenerationStatus(
                        active=True,
                        progress=min(100, progress),  # Cap at 100%
                        total=total_jobs,
                        completed=completed_jobs,
                        errors=failed_jobs,
                        current_image_id=None,  # Would need worker integration to track
                        current_image=None,
                        estimated_time_remaining_seconds=estimated_time,
                        started_at=active_session["started_at"],
                        status_message="processing",
                    )

            # Handle case where active_session exists but status is unhandled
            # This should not normally happen, but provides a fallback
            if active_session:
                logger.warning(f"Unknown session status: {active_session.get('status', 'unknown')}")
                return ThumbnailRegenerationStatus(
                    active=False,
                    progress=0,
                    total=0,
                    completed=0,
                    errors=0,
                    status_message="unknown",
                )

            # No active session found
            logger.debug("🚫 No active regeneration sessions found")

            # Check if there are any active jobs even without a session
            try:
                stats = await self.get_job_statistics()
                active_jobs = stats.pending_jobs + stats.processing_jobs
                
                if active_jobs > 0:
                    # There are active jobs but no session - show generic progress
                    logger.info(f"📊 Found {active_jobs} active jobs without regeneration session")
                    
                    # Calculate rough progress if we have job statistics
                    completed_jobs = stats.completed_jobs_24h
                    failed_jobs = stats.failed_jobs_24h
                    total_jobs = active_jobs + completed_jobs + failed_jobs
                    
                    progress = 0
                    if total_jobs > 0:
                        progress = int((completed_jobs / total_jobs) * 100)
                    
                    return ThumbnailRegenerationStatus(
                        active=True,
                        progress=min(progress, 99),  # Cap at 99% for unknown sessions
                        total=total_jobs,
                        completed=completed_jobs,
                        errors=failed_jobs,
                        current_image_id=None,
                        current_image=f"Processing {active_jobs} jobs",
                        estimated_time_remaining_seconds=None,
                        started_at=None,
                        status_message="processing",
                    )
            except Exception as stats_error:
                logger.warning(f"Failed to get job statistics for active check: {stats_error}")

            # No active session and no active jobs - return idle
            return ThumbnailRegenerationStatus(
                active=False,
                progress=0,
                total=0,
                completed=0,
                errors=0,
                status_message="idle",
            )

        except Exception as e:
            logger.error(f"Error getting thumbnail regeneration status: {e}")
            return ThumbnailRegenerationStatus(
                active=False,
                progress=0,
                total=0,
                completed=0,
                errors=0,
                status_message="error",
            )

    async def cancel_thumbnail_regeneration(self) -> dict:
        """
        Cancel currently running thumbnail regeneration process.

        Returns:
            Dictionary with success status and message
        """
        try:
            logger.info("Cancelling thumbnail regeneration")

            cancelled_jobs = 0
            active_session_id = None

            # Cancel any active regeneration sessions
            current_session_id = await self._session_cache.get("current_regen_session")
            active_session_id = None

            if current_session_id:
                session_data = await self._session_cache.get(
                    f"regen_session_{current_session_id}"
                )
                if session_data and session_data["status"] == "running":
                    session_data["status"] = "cancelled"
                    session_data["completed_at"] = utc_now()
                    active_session_id = current_session_id

                    # Update session in cache
                    await self._session_cache.set(
                        f"regen_session_{current_session_id}",
                        session_data,
                        ttl_seconds=1800,
                    )

                    # Clear current session pointer for cancel
                    await self._session_cache.set(
                        "current_regen_session", None, ttl_seconds=1
                    )

            # Cancel pending jobs using the job service or operations
            try:
                if self.thumbnail_job_service:
                    cancelled_jobs = (
                        await self.thumbnail_job_service.cancel_pending_jobs()
                    )
                else:
                    # Use job operations directly
                    cancelled_jobs = await self.thumbnail_job_ops.cancel_jobs_by_status(
                        "pending"
                    )
                logger.info(f"Cancelled {cancelled_jobs} pending thumbnail jobs")
            except Exception as job_error:
                logger.warning(f"Failed to cancel jobs: {job_error}")

            # Get updated statistics after cancellation
            stats = await self.get_job_statistics()

            # Broadcast SSE event for cancellation
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_regeneration_cancelled",
                    event_data={
                        "session_id": active_session_id,
                        "cancelled_jobs": cancelled_jobs,
                        "remaining_pending": stats.pending_jobs,
                        "operation": "cancel_regeneration",
                    },
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(
                    f"Failed to broadcast cancellation SSE event: {sse_error}"
                )

            message = (
                f"Thumbnail regeneration cancelled: {cancelled_jobs} jobs cancelled"
            )
            if active_session_id:
                message += f" (session {active_session_id})"

            return ResponseFormatter.success(
                message,
                data={
                    "operation": "cancel_regeneration",
                    "session_id": active_session_id,
                    "cancelled_jobs": cancelled_jobs,
                    "remaining_pending": stats.pending_jobs,
                    "note": "Individual jobs will complete naturally. New jobs will not be queued.",
                },
            )

        except Exception as e:
            logger.error(f"Error cancelling thumbnail regeneration: {e}")
            return ResponseFormatter.error(
                f"Failed to cancel thumbnail regeneration: {str(e)}",
                error_code="CANCELLATION_FAILED",
            )

    async def delete_all_thumbnails(self) -> dict:
        """
        Delete all thumbnail files and clear database references.

        Returns:
            Dictionary with deletion results
        """
        try:
            logger.warning(
                "Starting global deletion of all thumbnails - this is a destructive operation"
            )

            # Get all thumbnail paths before deletion
            if not self.image_operations:
                return ResponseFormatter.error("Image operations not available")

            thumbnail_paths = await self.image_operations.get_all_thumbnail_paths()

            # Get data directory for path resolution
            if not self.settings_service:
                return ResponseFormatter.error("Settings service not available")

            data_directory = await self.settings_service.get_setting("data_directory")
            base_path = Path(data_directory)
            
            # Count and delete actual files
            deleted_files = 0
            deleted_size_bytes = 0
            errors = []

            # Method 1: Delete files tracked in database
            if thumbnail_paths:
                logger.info(f"🗃️ Found {len(thumbnail_paths)} thumbnail records in database")
                for row in thumbnail_paths:
                    # Delete thumbnail file
                    if row.get("thumbnail_path"):
                        thumb_path = base_path / row["thumbnail_path"].lstrip("/")
                        try:
                            if thumb_path.exists():
                                file_size = thumb_path.stat().st_size
                                thumb_path.unlink()
                                deleted_files += 1
                                deleted_size_bytes += file_size
                        except Exception as e:
                            errors.append(
                                f"Failed to delete thumbnail {thumb_path}: {str(e)}"
                            )

                    # Delete small image file
                    if row.get("small_path"):
                        small_path = base_path / row["small_path"].lstrip("/")
                        try:
                            if small_path.exists():
                                file_size = small_path.stat().st_size
                                small_path.unlink()
                                deleted_files += 1
                                deleted_size_bytes += file_size
                        except Exception as e:
                            errors.append(
                                f"Failed to delete small image {small_path}: {str(e)}"
                            )
            
            # Method 2: File-system based cleanup (for orphaned files)
            logger.info("🔍 Scanning filesystem for orphaned thumbnail files...")
            thumbnail_dirs = [
                base_path / "cameras",  # Main thumbnail directory structure
                base_path / "thumbnails",  # Legacy thumbnail directory
            ]
            
            for thumbnail_dir in thumbnail_dirs:
                if thumbnail_dir.exists():
                    try:
                        # Find all .jpg files in thumbnail directories
                        for thumb_file in thumbnail_dir.rglob("*.jpg"):
                            # Only delete if it's clearly a thumbnail (contains specific patterns)
                            file_path_str = str(thumb_file)
                            if any(pattern in file_path_str for pattern in [
                                "thumb_", "_small_", "thumbnails/", "/small/", 
                                "/smalls/", "camera-", "timelapse-"
                            ]):
                                try:
                                    file_size = thumb_file.stat().st_size
                                    thumb_file.unlink()
                                    deleted_files += 1
                                    deleted_size_bytes += file_size
                                    logger.debug(f"🗑️ Deleted thumbnail file: {thumb_file}")
                                except Exception as e:
                                    errors.append(f"Failed to delete orphaned thumbnail {thumb_file}: {str(e)}")
                        
                        # Also delete empty directories
                        for dir_path in sorted(thumbnail_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                            if dir_path.is_dir() and not any(dir_path.iterdir()):
                                try:
                                    dir_path.rmdir()
                                    logger.debug(f"🗑️ Removed empty directory: {dir_path}")
                                except Exception as e:
                                    logger.debug(f"Could not remove directory {dir_path}: {e}")
                                    
                    except Exception as e:
                        errors.append(f"Error scanning directory {thumbnail_dir}: {str(e)}")

            # Clear all thumbnail paths in database
            cleared_records = await self.image_operations.clear_all_thumbnail_paths()

            # Get unique camera IDs for count
            camera_query = """
                SELECT DISTINCT camera_id 
                FROM images 
                WHERE camera_id IS NOT NULL
            """
            async with self.image_operations.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(camera_query)
                    camera_results = await cur.fetchall()
                    cameras_processed = len(camera_results) if camera_results else 0

            # Calculate size in MB
            deleted_size_mb = deleted_size_bytes / (1024 * 1024)

            # Broadcast SSE event for deletion operation
            try:
                await self.sse_operations.create_event(
                    event_type="thumbnail_global_deletion_complete",
                    event_data={
                        "operation": "delete_all",
                        "deleted_files": deleted_files,
                        "deleted_size_mb": round(deleted_size_mb, 2),
                        "cameras_processed": cameras_processed,
                        "cleared_database_records": cleared_records,
                        "errors": errors[:10],  # Limit errors in SSE
                    },
                    priority="normal",
                    source="thumbnail_service",
                )
            except Exception as sse_error:
                logger.warning(f"Failed to broadcast deletion SSE event: {sse_error}")

            return ResponseFormatter.success(
                f"Deleted {deleted_files} thumbnail files ({deleted_size_mb:.2f}MB)",
                data={
                    "deleted_files": deleted_files,
                    "deleted_size_mb": round(deleted_size_mb, 2),
                    "cameras_processed": cameras_processed,
                    "cleared_database_records": cleared_records,
                    "errors": errors,
                },
            )

        except Exception as e:
            logger.error(f"Error in delete_all_thumbnails: {e}")
            return ResponseFormatter.error(
                f"Failed to process thumbnail deletion request: {str(e)}",
                error_code="DELETION_FAILED",
                details={
                    "deleted_files": 0,
                    "deleted_size_mb": 0.0,
                    "cameras_processed": 0,
                    "cleared_database_records": 0,
                    "errors": [str(e)],
                },
            )

    async def get_thumbnail_statistics(self) -> ThumbnailStatistics:
        """
        Get comprehensive thumbnail statistics.

        Returns:
            ThumbnailStatistics with coverage and storage information
        """
        try:
            logger.debug("Gathering thumbnail statistics")

            # Check if image_operations is available
            if not self.image_operations:
                logger.warning("Image operations not available for statistics")
                return ThumbnailStatistics(
                    total_images=0,
                    images_with_thumbnails=0,
                    images_with_small=0,
                    images_without_thumbnails=0,
                    thumbnail_coverage_percentage=0.0,
                    total_thumbnail_storage_mb=0.0,
                    total_small_storage_mb=0.0,
                    avg_thumbnail_size_kb=0.0,
                    avg_small_size_kb=0.0,
                    last_updated=utc_now(),
                )

            # Get real statistics from database
            coverage_stats = (
                await self.image_operations.get_thumbnail_coverage_statistics()
            )

            # Calculate coverage percentage
            coverage_percentage = 0.0
            if coverage_stats["total_images"] > 0:
                coverage_percentage = (
                    coverage_stats["images_with_thumbnails"]
                    / coverage_stats["total_images"]
                ) * 100

            # Get storage statistics by scanning filesystem
            storage_stats = await self._calculate_thumbnail_storage_stats()

            # Get average sizes from recent jobs
            avg_sizes = await self._calculate_average_thumbnail_sizes()

            # Log statistics gathering for debugging
            logger.debug(
                f"Coverage: {coverage_stats['images_with_thumbnails']}/{coverage_stats['total_images']} ({coverage_percentage:.1f}%)"
            )

            return ThumbnailStatistics(
                total_images=coverage_stats["total_images"],
                images_with_thumbnails=coverage_stats["images_with_thumbnails"],
                images_with_small=coverage_stats["images_with_small"],
                images_without_thumbnails=coverage_stats["images_without_thumbnails"],
                thumbnail_coverage_percentage=round(coverage_percentage, 2),
                total_thumbnail_storage_mb=storage_stats["thumbnail_storage_mb"],
                total_small_storage_mb=storage_stats["small_storage_mb"],
                avg_thumbnail_size_kb=avg_sizes["avg_thumbnail_size_kb"],
                avg_small_size_kb=avg_sizes["avg_small_size_kb"],
                last_updated=utc_now(),
            )

        except Exception as e:
            logger.error(f"Error getting thumbnail statistics: {e}")
            # Return empty stats on error with proper error logging
            return ThumbnailStatistics(
                total_images=0,
                images_with_thumbnails=0,
                images_with_small=0,
                images_without_thumbnails=0,
                thumbnail_coverage_percentage=0.0,
                total_thumbnail_storage_mb=0.0,
                total_small_storage_mb=0.0,
                avg_thumbnail_size_kb=0.0,
                avg_small_size_kb=0.0,
                last_updated=utc_now(),
            )

    async def _calculate_thumbnail_storage_stats(self) -> dict:
        """
        Calculate storage statistics by scanning filesystem.

        Returns:
            Dictionary with thumbnail and small storage sizes in MB
        """
        try:
            # Use settings service if available, fallback to direct import
            if self.settings_service:
                data_directory = await self.settings_service.get_setting(
                    "data_directory"
                )
                data_path = Path(data_directory) / "cameras"
            else:
                # Fallback for compatibility
                data_path = Path(settings.data_path) / "cameras"

            if not data_path.exists():
                return {"thumbnail_storage_mb": 0.0, "small_storage_mb": 0.0}

            thumbnail_total = 0.0
            small_total = 0.0

            # Scan all camera directories for thumbnail and small subdirectories
            for camera_dir in data_path.iterdir():
                if not camera_dir.is_dir() or not camera_dir.name.startswith("camera-"):
                    continue

                # Scan each timelapse directory within camera
                for timelapse_dir in camera_dir.iterdir():
                    if not timelapse_dir.is_dir() or not timelapse_dir.name.startswith(
                        "timelapse-"
                    ):
                        continue

                    # Calculate thumbnail directory size
                    thumbnails_dir = timelapse_dir / "thumbnails"
                    if thumbnails_dir.exists():
                        thumbnail_total += await self._run_in_executor(
                            calculate_directory_size, str(thumbnails_dir)
                        )

                    # Calculate small directory size
                    smalls_dir = timelapse_dir / "smalls"
                    if smalls_dir.exists():
                        small_total += await self._run_in_executor(
                            calculate_directory_size, str(smalls_dir)
                        )

            return {
                "thumbnail_storage_mb": round(thumbnail_total, 2),
                "small_storage_mb": round(small_total, 2),
            }

        except Exception as e:
            logger.error(f"Error calculating storage stats: {e}")
            return {"thumbnail_storage_mb": 0.0, "small_storage_mb": 0.0}

    async def _run_in_executor(self, func, *args):
        """Helper to run blocking operations in thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    async def _calculate_average_thumbnail_sizes(self) -> dict:
        """
        Calculate average thumbnail file sizes from database.

        Returns:
            Dictionary with average thumbnail and small sizes in KB
        """
        try:
            if not self.image_operations:
                return {"avg_thumbnail_size_kb": 0.0, "avg_small_size_kb": 0.0}

            # Query database for average sizes with timeout
            query = """
                SELECT 
                    AVG(thumbnail_size) as avg_thumbnail_bytes,
                    AVG(small_size) as avg_small_bytes
                FROM images 
                WHERE thumbnail_size IS NOT NULL OR small_size IS NOT NULL
            """

            try:
                # Add timeout to prevent hanging connections
                async with asyncio.timeout(5.0):  # 5 second timeout
                    async with self.image_operations.db.get_connection() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(query)
                            result = await cur.fetchone()

                            if result and (result[0] or result[1]):
                                avg_thumbnail_kb = (
                                    (result[0] / BYTES_TO_KB_DIVISOR) if result[0] else 0.0
                                )
                                avg_small_kb = (
                                    (result[1] / BYTES_TO_KB_DIVISOR) if result[1] else 0.0
                                )

                                return {
                                    "avg_thumbnail_size_kb": round(avg_thumbnail_kb, 2),
                                    "avg_small_size_kb": round(avg_small_kb, 2),
                                }
            except asyncio.TimeoutError:
                logger.warning("Thumbnail size calculation timed out after 5 seconds")
                return {"avg_thumbnail_size_kb": 0.0, "avg_small_size_kb": 0.0}

            return {"avg_thumbnail_size_kb": 0.0, "avg_small_size_kb": 0.0}

        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Error calculating average sizes: {error_msg}")
            return {"avg_thumbnail_size_kb": 0.0, "avg_small_size_kb": 0.0}

    async def verify_all_thumbnails(self) -> dict:
        """
        Verify all thumbnail files system-wide.

        Returns:
            dict with verification results
        """
        try:
            logger.info("Starting system-wide thumbnail verification")

            # Check if image_operations is available
            if not self.image_operations:
                return {
                    "success": False,
                    "message": "Image operations service not available",
                    "total_images_checked": 0,
                    "valid_thumbnails": 0,
                    "valid_smalls": 0,
                    "invalid_thumbnails": 0,
                    "invalid_smalls": 0,
                    "database_records_updated": 0,
                    "verification_complete": False,
                }

            # Get images with thumbnail references for verification
            images_with_thumbnails = (
                await self.image_operations.get_images_with_thumbnails(
                    limit=THUMBNAIL_VERIFICATION_BATCH_SIZE
                )
            )

            valid_thumbnails = 0
            valid_smalls = 0
            invalid_thumbnails = 0
            invalid_smalls = 0
            updated_records = 0

            # Use settings service if available, fallback to direct import
            if self.settings_service:
                data_directory = await self.settings_service.get_setting(
                    "data_directory"
                )
                data_path = Path(data_directory)
            else:
                # Fallback for compatibility
                data_path = Path(settings.data_path)

            # Check file existence for each image
            for image in images_with_thumbnails:
                thumbnail_valid = False
                small_valid = False
                needs_update = False

                # Check thumbnail existence
                if image.thumbnail_path:
                    full_thumbnail_path = data_path / image.thumbnail_path
                    thumbnail_valid = await self._run_in_executor(
                        Path.exists, full_thumbnail_path
                    )

                    if thumbnail_valid:
                        valid_thumbnails += 1
                    else:
                        invalid_thumbnails += 1
                        needs_update = True

                # Check small image existence
                if image.small_path:
                    full_small_path = data_path / image.small_path
                    small_valid = await self._run_in_executor(
                        Path.exists, full_small_path
                    )

                    if small_valid:
                        valid_smalls += 1
                    else:
                        invalid_smalls += 1
                        needs_update = True

                # Clear invalid paths from database
                if needs_update:
                    # Clear paths for missing files
                    new_thumbnail_path = (
                        image.thumbnail_path if thumbnail_valid else None
                    )
                    new_small_path = image.small_path if small_valid else None

                    success = await self.image_operations.update_thumbnail_paths(
                        image.id,
                        thumbnail_path=new_thumbnail_path,
                        small_path=new_small_path,
                    )

                    if success:
                        updated_records += 1

            total_checked = len(images_with_thumbnails)

            return {
                "success": True,
                "message": f"Verification completed: checked {total_checked} images, updated {updated_records} records",
                "total_images_checked": total_checked,
                "valid_thumbnails": valid_thumbnails,
                "valid_smalls": valid_smalls,
                "invalid_thumbnails": invalid_thumbnails,
                "invalid_smalls": invalid_smalls,
                "database_records_updated": updated_records,
                "verification_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in verify_all_thumbnails: {e}")
            return {
                "success": False,
                "message": f"Verification failed: {str(e)}",
                "total_images_checked": 0,
                "valid_thumbnails": 0,
                "valid_smalls": 0,
                "invalid_thumbnails": 0,
                "invalid_smalls": 0,
                "database_records_updated": 0,
                "verification_complete": False,
            }

    async def repair_orphaned_thumbnails(self) -> dict:
        """
        Repair orphaned thumbnail files by matching them back to database.

        Returns:
            dict with repair results
        """
        try:
            logger.info("Starting orphaned thumbnail repair")

            if not self.image_operations:
                return {
                    "success": False,
                    "message": "Image operations service not available",
                    "orphaned_files_found": 0,
                    "files_matched": 0,
                    "files_deleted": 0,
                    "database_records_updated": 0,
                    "timelapses_affected": 0,
                }

            # Initialize counters
            orphaned_files_found = 0
            files_matched = 0
            files_deleted = 0
            database_records_updated = 0
            timelapses_affected = set()

            # Use settings service if available, fallback to direct import
            if self.settings_service:
                data_directory = await self.settings_service.get_setting(
                    "data_directory"
                )
                data_path = Path(data_directory) / "cameras"
            else:
                # Fallback for compatibility
                data_path = Path(settings.data_path) / "cameras"

            if not data_path.exists():
                return {
                    "success": True,
                    "message": "No camera directories found",
                    "orphaned_files_found": 0,
                    "files_matched": 0,
                    "files_deleted": 0,
                    "database_records_updated": 0,
                    "timelapses_affected": 0,
                }

            # Scan all thumbnail files
            all_thumbnail_files = await self._run_in_executor(
                scan_directory_for_thumbnails, str(data_path)
            )
            orphaned_files_found = len(all_thumbnail_files)

            logger.info(f"Found {orphaned_files_found} thumbnail files to check")

            # Check each file for database match
            for file_path in all_thumbnail_files:
                try:
                    filename = Path(file_path).name
                    parsed = await self._run_in_executor(
                        parse_thumbnail_filename, filename
                    )

                    if not parsed["valid"]:
                        # Cannot parse filename - delete orphaned file

                        deleted = await self._run_in_executor(
                            delete_file_safe, file_path
                        )
                        if deleted:
                            files_deleted += 1
                        continue

                    timelapse_id = parsed["timelapse_id"]
                    thumbnail_type = parsed["type"]

                    # Try to find matching image in database by timelapse and timestamp correlation
                    images_in_timelapse = (
                        await self.image_operations.get_images_by_timelapse(
                            timelapse_id
                        )
                    )

                    matched_image = None
                    for image in images_in_timelapse:
                        # Try to match by timestamp correlation or other logic
                        # For now, find first image without the appropriate thumbnail path
                        if thumbnail_type == "thumb" and not image.thumbnail_path:
                            matched_image = image
                            break
                        elif thumbnail_type == "small" and not image.small_path:
                            matched_image = image
                            break

                    if matched_image:
                        # Update database with thumbnail path
                        if self.settings_service:
                            data_directory = await self.settings_service.get_setting(
                                "data_directory"
                            )
                            settings_data_path = data_directory
                        else:
                            settings_data_path = settings.data_path
                        relative_path = str(
                            Path(file_path).relative_to(Path(settings_data_path))
                        )

                        if thumbnail_type == "thumb":
                            success = (
                                await self.image_operations.update_thumbnail_paths(
                                    matched_image.id, thumbnail_path=relative_path
                                )
                            )
                        else:  # small
                            success = (
                                await self.image_operations.update_thumbnail_paths(
                                    matched_image.id, small_path=relative_path
                                )
                            )

                        if success:
                            files_matched += 1
                            database_records_updated += 1
                            timelapses_affected.add(timelapse_id)
                    else:
                        # No matching image found - delete orphaned file

                        deleted = await self._run_in_executor(
                            delete_file_safe, file_path
                        )
                        if deleted:
                            files_deleted += 1

                except Exception as file_error:
                    logger.warning(f"Error processing file {file_path}: {file_error}")
                    continue

            # Update timelapse counts for affected timelapses
            if timelapses_affected and hasattr(self.image_operations, "db"):

                timelapse_ops = TimelapseOperations(self.image_operations.db)

                for timelapse_id in timelapses_affected:
                    await timelapse_ops.recalculate_thumbnail_counts(timelapse_id)

            return {
                "success": True,
                "message": f"Repair completed: {files_matched} files matched, {files_deleted} files deleted",
                "orphaned_files_found": orphaned_files_found,
                "files_matched": files_matched,
                "files_deleted": files_deleted,
                "database_records_updated": database_records_updated,
                "timelapses_affected": len(timelapses_affected),
            }

        except Exception as e:
            logger.error(f"Error in repair_orphaned_thumbnails: {e}")
            return {
                "success": False,
                "message": f"Repair failed: {str(e)}",
                "orphaned_files_found": 0,
                "files_matched": 0,
                "files_deleted": 0,
                "database_records_updated": 0,
                "timelapses_affected": 0,
            }

    async def cleanup_orphaned_thumbnails(self, dry_run: bool = False) -> dict:
        """
        Clean up orphaned thumbnail files.

        Args:
            dry_run: If true, only report what would be deleted

        Returns:
            dict with cleanup results
        """
        try:
            logger.info(f"Starting orphaned thumbnail cleanup (dry_run={dry_run})")

            if not self.image_operations:
                return {
                    "success": False,
                    "message": "Image operations service not available",
                    "orphaned_files_found": 0,
                    "files_deleted": 0,
                    "files_skipped": 0,
                    "storage_recovered_mb": 0.0,
                    "dry_run": dry_run,
                }

            # Initialize counters
            orphaned_files_found = 0
            files_deleted = 0
            files_skipped = 0
            storage_recovered_mb = 0.0

            # Use settings service if available, fallback to direct import
            if self.settings_service:
                data_directory = await self.settings_service.get_setting(
                    "data_directory"
                )
                data_path = Path(data_directory) / "cameras"
                settings_data_path = data_directory
            else:
                # Fallback for compatibility
                data_path = Path(settings.data_path) / "cameras"
                settings_data_path = settings.data_path

            if not data_path.exists():
                return {
                    "success": True,
                    "message": "No camera directories found",
                    "orphaned_files_found": 0,
                    "files_deleted": 0,
                    "files_skipped": 0,
                    "storage_recovered_mb": 0.0,
                    "dry_run": dry_run,
                }

            # Get all existing thumbnail paths from database
            query = """
                SELECT thumbnail_path, small_path 
                FROM images 
                WHERE thumbnail_path IS NOT NULL OR small_path IS NOT NULL
            """

            existing_paths = set()

            async with self.image_operations.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    results = await cur.fetchall()

                    for row in results:
                        if row[0]:  # thumbnail_path
                            existing_paths.add(str(Path(settings_data_path) / row[0]))
                        if row[1]:  # small_path
                            existing_paths.add(str(Path(settings_data_path) / row[1]))

            # Scan all thumbnail files on filesystem
            all_thumbnail_files = await self._run_in_executor(
                scan_directory_for_thumbnails, str(data_path)
            )

            # Check each file to see if it has a database reference
            for file_path in all_thumbnail_files:
                orphaned_files_found += 1

                if file_path not in existing_paths:
                    # File is orphaned - calculate size and delete if not dry run
                    try:

                        file_size = await self._run_in_executor(
                            os.path.getsize, file_path
                        )
                        storage_recovered_mb += file_size / BYTES_TO_MB_DIVISOR

                        if not dry_run:

                            deleted = await self._run_in_executor(
                                delete_file_safe, file_path
                            )
                            if deleted:
                                files_deleted += 1
                            else:
                                files_skipped += 1
                        else:
                            # In dry run, count as "would be deleted"
                            files_deleted += 1

                    except Exception as file_error:
                        logger.warning(
                            f"Error processing orphaned file {file_path}: {file_error}"
                        )
                        files_skipped += 1
                else:
                    # File has database reference - skip
                    files_skipped += 1

            action_word = "would be deleted" if dry_run else "deleted"
            message = f"Orphaned thumbnail cleanup {'preview' if dry_run else 'completed'}: {files_deleted} files {action_word}, {storage_recovered_mb:.2f}MB recovered"

            return {
                "success": True,
                "message": message,
                "orphaned_files_found": orphaned_files_found,
                "files_deleted": 0 if dry_run else files_deleted,
                "files_skipped": files_skipped,
                "storage_recovered_mb": round(storage_recovered_mb, 2),
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(f"Error in cleanup_orphaned_thumbnails: {e}")
            return {
                "success": False,
                "message": f"Cleanup failed: {str(e)}",
                "orphaned_files_found": 0,
                "files_deleted": 0,
                "files_skipped": 0,
                "storage_recovered_mb": 0.0,
                "dry_run": dry_run,
            }
