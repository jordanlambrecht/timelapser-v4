# backend/app/services/thumbnail_verification_service.py
"""
Thumbnail Verification Service - File existence and integrity verification.

Responsibilities:
- Verify thumbnail file existence across legacy and new structures
- Generate verification reports and statistics
- Queue repair jobs for missing thumbnails
- Provide batch verification capabilities
- Handle mixed file structure environments

Interactions:
- Uses ThumbnailPathResolver for cross-structure compatibility
- Integrates with ThumbnailJobOperations for repair job queuing
- Uses ImageOperations for database queries
- Broadcasts SSE events for progress updates
"""

import asyncio
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from loguru import logger

from ..database.core import AsyncDatabase
from ..database.image_operations import ImageOperations
from ..database.thumbnail_job_operations import ThumbnailJobOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..models.shared_models import (
    ThumbnailVerificationResult,
    ThumbnailVerificationSummary,
    ThumbnailRepairRequest,
    ThumbnailRepairResult,
    ThumbnailGenerationJobCreate,
)
from ..utils.thumbnail_path_resolver import ThumbnailPathResolver
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import (
    THUMBNAIL_JOB_PRIORITY_HIGH,
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_TYPE_SINGLE,
    DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
)


class ThumbnailVerificationService:
    """
    Service for verifying thumbnail file existence and integrity.
    
    Provides comprehensive verification capabilities for both legacy
    camera-based and new timelapse-based thumbnail structures.
    """

    def __init__(
        self,
        image_ops,
        thumbnail_job_ops,
        sse_operations,
    ):
        """
        Initialize ThumbnailVerificationService with dependency injection.

        Args:
            image_ops: ImageOperations for database queries
            thumbnail_job_ops: ThumbnailJobOperations for repair job queuing
            sse_operations: SSEEventsOperations for progress broadcasting
        """
        self.image_ops = image_ops
        self.thumbnail_job_ops = thumbnail_job_ops
        self.sse_operations = sse_operations
        
        # Initialize path resolver (will be configured with data directory)
        self.path_resolver = None

    async def _initialize_path_resolver(self) -> None:
        """Initialize path resolver with data directory from settings."""
        if not self.path_resolver:
            data_directory = await self.settings_service.get_setting("data_directory")
            if not data_directory:
                raise ValueError("Data directory setting not configured")
            self.path_resolver = ThumbnailPathResolver(data_directory)

    async def verify_single_image(
        self, 
        image_id: int, 
        check_both_structures: bool = True
    ) -> ThumbnailVerificationResult:
        """
        Verify thumbnail existence for a single image.

        Args:
            image_id: ID of the image to verify
            check_both_structures: Whether to check both legacy and new structures

        Returns:
            ThumbnailVerificationResult with verification details
        """
        try:
            await self._initialize_path_resolver()
            
            # Get image details from database
            image = await self.image_ops.get_image_by_id(image_id)
            if not image:
                return ThumbnailVerificationResult(
                    image_id=image_id,
                    camera_id=0,
                    error=f"Image {image_id} not found in database",
                    verified_at=datetime.utcnow()
                )

            result = ThumbnailVerificationResult(
                image_id=image_id,
                camera_id=image.camera_id,
                timelapse_id=getattr(image, 'timelapse_id', None),
                verified_at=datetime.utcnow()
            )

            # Verify thumbnail file
            if image.thumbnail_path:
                thumbnail_result = self.path_resolver.resolve_thumbnail_path(
                    image.thumbnail_path,
                    image.camera_id,
                    getattr(image, 'timelapse_id', None),
                    "thumbnail",
                    fallback_to_legacy=check_both_structures
                )
                
                if thumbnail_result.exists:
                    result.thumbnail_exists = True
                    result.thumbnail_path = str(thumbnail_result.path)
                    result.thumbnail_size_bytes = thumbnail_result.path.stat().st_size
                else:
                    result.missing_files.append(f"thumbnail: {image.thumbnail_path}")

            # Verify small file
            if image.small_path:
                small_result = self.path_resolver.resolve_thumbnail_path(
                    image.small_path,
                    image.camera_id,
                    getattr(image, 'timelapse_id', None),
                    "small",
                    fallback_to_legacy=check_both_structures
                )
                
                if small_result.exists:
                    result.small_exists = True
                    result.small_path = str(small_result.path)
                    result.small_size_bytes = small_result.path.stat().st_size
                else:
                    result.missing_files.append(f"small: {image.small_path}")

            return result

        except Exception as e:
            logger.error(f"Error verifying image {image_id}: {e}")
            return ThumbnailVerificationResult(
                image_id=image_id,
                camera_id=0,
                error=str(e),
                verified_at=datetime.utcnow()
            )

    async def verify_bulk_images(
        self,
        image_ids: Optional[List[int]] = None,
        camera_ids: Optional[List[int]] = None,
        timelapse_ids: Optional[List[int]] = None,
        limit: int = 1000,
        batch_size: int = DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
        broadcast_progress: bool = True
    ) -> ThumbnailVerificationSummary:
        """
        Verify thumbnails for multiple images with progress tracking.

        Args:
            image_ids: Specific image IDs to verify (optional)
            camera_ids: All images from specific cameras (optional) 
            timelapse_ids: All images from specific timelapses (optional)
            limit: Maximum number of images to verify
            batch_size: Number of images to process per batch
            broadcast_progress: Whether to broadcast SSE progress events

        Returns:
            ThumbnailVerificationSummary with bulk verification results
        """
        start_time = time.time()
        verification_started_at = datetime.utcnow()
        
        summary = ThumbnailVerificationSummary(
            verification_started_at=verification_started_at
        )

        try:
            logger.info(f"Starting bulk thumbnail verification (limit={limit})")
            
            # Get list of images to verify
            if image_ids:
                images = await self.image_ops.get_images_by_ids(image_ids[:limit])
            elif camera_ids:
                images = await self.image_ops.get_images_by_cameras(camera_ids, limit)
            elif timelapse_ids:
                images = await self.image_ops.get_images_by_timelapses(timelapse_ids, limit)
            else:
                # Get all images with thumbnail paths for verification
                images = await self.image_ops.get_images_with_thumbnails(limit)

            summary.total_images_checked = len(images)
            
            if not images:
                logger.info("No images found for verification")
                summary.verification_completed_at = datetime.utcnow()
                summary.processing_time_seconds = time.time() - start_time
                return summary

            # Broadcast start event
            if broadcast_progress:
                await self.sse_operations.create_event(
                    event_type="thumbnail_verification_started",
                    event_data={
                        "total_images": len(images),
                        "verification_id": verification_started_at.isoformat(),
                    },
                    priority="normal",
                    source="verification_service"
                )

            # Process in batches
            for batch_start in range(0, len(images), batch_size):
                batch_end = min(batch_start + batch_size, len(images))
                batch = images[batch_start:batch_end]
                
                logger.debug(f"Verifying batch {batch_start//batch_size + 1}: images {batch_start}-{batch_end}")
                
                # Process batch concurrently
                verification_tasks = [
                    self.verify_single_image(image.id) for image in batch
                ]
                batch_results = await asyncio.gather(*verification_tasks, return_exceptions=True)
                
                # Aggregate results
                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        summary.verification_errors += 1
                        logger.error(f"Verification error for image {batch[i].id}: {result}")
                        continue
                    
                    if isinstance(result, ThumbnailVerificationResult):
                        if result.error:
                            summary.verification_errors += 1
                        else:
                            # Update statistics
                            if result.thumbnail_exists:
                                summary.images_with_thumbnails += 1
                                if result.thumbnail_size_bytes:
                                    summary.total_thumbnail_size_mb += result.thumbnail_size_bytes / (1024 * 1024)
                            else:
                                summary.images_missing_thumbnails += 1
                            
                            if result.small_exists:
                                summary.images_with_small += 1
                                if result.small_size_bytes:
                                    summary.total_small_size_mb += result.small_size_bytes / (1024 * 1024)
                            else:
                                summary.images_missing_small += 1
                            
                            # Count missing files
                            summary.total_missing_files += len(result.missing_files)
                            
                            # Check if missing both
                            if not result.thumbnail_exists and not result.small_exists:
                                summary.images_missing_both += 1

                # Broadcast progress event
                if broadcast_progress:
                    progress_percentage = int((batch_end / len(images)) * 100)
                    await self.sse_operations.create_event(
                        event_type="thumbnail_verification_progress",
                        event_data={
                            "progress": progress_percentage,
                            "images_processed": batch_end,
                            "total_images": len(images),
                            "images_with_thumbnails": summary.images_with_thumbnails,
                            "images_missing_thumbnails": summary.images_missing_thumbnails,
                            "verification_errors": summary.verification_errors,
                        },
                        priority="normal",
                        source="verification_service"
                    )

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)

            # Finalize summary
            summary.verification_completed_at = datetime.utcnow()
            summary.processing_time_seconds = time.time() - start_time

            # Broadcast completion event
            if broadcast_progress:
                await self.sse_operations.create_event(
                    event_type="thumbnail_verification_complete",
                    event_data={
                        "total_images_checked": summary.total_images_checked,
                        "images_with_thumbnails": summary.images_with_thumbnails,
                        "images_missing_thumbnails": summary.images_missing_thumbnails,
                        "total_missing_files": summary.total_missing_files,
                        "processing_time_seconds": summary.processing_time_seconds,
                        "success_rate": (
                            (summary.images_with_thumbnails / summary.total_images_checked * 100)
                            if summary.total_images_checked > 0 else 0
                        ),
                    },
                    priority="normal",
                    source="verification_service"
                )

            logger.info(f"Verification complete: {summary.images_with_thumbnails}/{summary.total_images_checked} "
                       f"images have thumbnails, {summary.total_missing_files} missing files")

            return summary

        except Exception as e:
            logger.error(f"Error during bulk verification: {e}")
            summary.verification_errors += 1
            summary.verification_completed_at = datetime.utcnow()
            summary.processing_time_seconds = time.time() - start_time
            
            # Broadcast error event
            if broadcast_progress:
                await self.sse_operations.create_event(
                    event_type="thumbnail_verification_error",
                    event_data={
                        "error": str(e),
                        "images_processed": summary.total_images_checked,
                    },
                    priority="high",
                    source="verification_service"
                )
            
            return summary

    async def repair_missing_thumbnails(
        self,
        repair_request: ThumbnailRepairRequest
    ) -> ThumbnailRepairResult:
        """
        Queue repair jobs for missing thumbnails.

        Args:
            repair_request: Repair request with target images and options

        Returns:
            ThumbnailRepairResult with repair operation details
        """
        repair_started_at = datetime.utcnow()
        
        result = ThumbnailRepairResult(
            success=False,
            repair_started_at=repair_started_at
        )

        try:
            logger.info("Starting thumbnail repair operation")
            
            # Get images that need repair based on request
            if repair_request.image_ids:
                target_images = await self.image_ops.get_images_by_ids(repair_request.image_ids)
            elif repair_request.camera_ids:
                target_images = await self.image_ops.get_images_by_cameras(repair_request.camera_ids)
            elif repair_request.timelapse_ids:
                target_images = await self.image_ops.get_images_by_timelapses(repair_request.timelapse_ids)
            else:
                # Get all images missing thumbnails
                target_images = await self.image_ops.get_images_without_thumbnails()

            result.images_processed = len(target_images)
            
            if not target_images:
                result.success = True
                result.message = "No images found that need thumbnail repair"
                return result

            # Verify which images actually need repair
            repair_needed = []
            
            for image in target_images:
                if repair_request.force_regenerate:
                    repair_needed.append(image)
                else:
                    # Only repair if actually missing
                    verification = await self.verify_single_image(image.id)
                    needs_repair = False
                    
                    if repair_request.repair_missing_thumbnails and not verification.thumbnail_exists:
                        needs_repair = True
                    if repair_request.repair_missing_small and not verification.small_exists:
                        needs_repair = True
                    
                    if needs_repair:
                        repair_needed.append(image)

            # Queue repair jobs
            jobs_queued = 0
            
            for image in repair_needed:
                try:
                    job_data = ThumbnailGenerationJobCreate(
                        image_id=image.id,
                        priority=repair_request.priority,
                        status=THUMBNAIL_JOB_STATUS_PENDING,
                        job_type=THUMBNAIL_JOB_TYPE_SINGLE,
                    )
                    
                    job = await self.thumbnail_job_ops.create_job(job_data)
                    if job:
                        jobs_queued += 1
                    else:
                        result.errors.append(f"Failed to queue repair job for image {image.id}")
                        
                except Exception as e:
                    result.errors.append(f"Error queuing repair job for image {image.id}: {str(e)}")

            result.repair_jobs_queued = jobs_queued
            result.success = True
            result.message = f"Queued {jobs_queued} repair jobs for {len(repair_needed)} images"
            
            # Estimate completion time (rough calculation)
            if jobs_queued > 0:
                # Assume ~2 seconds per job average
                estimated_seconds = jobs_queued * 2
                result.estimated_completion_time = datetime.utcnow().replace(second=0, microsecond=0) + \
                                                 timedelta(seconds=estimated_seconds)

            # Broadcast repair started event
            await self.sse_operations.create_event(
                event_type="thumbnail_repair_started",
                event_data={
                    "repair_jobs_queued": jobs_queued,
                    "images_to_repair": len(repair_needed),
                    "repair_type": "missing_thumbnails",
                    "estimated_completion": result.estimated_completion_time.isoformat() if result.estimated_completion_time else None,
                },
                priority="normal",
                source="verification_service"
            )

            logger.info(f"Thumbnail repair initiated: {jobs_queued} jobs queued for {len(repair_needed)} images")
            
            return result

        except Exception as e:
            logger.error(f"Error during thumbnail repair: {e}")
            result.errors.append(str(e))
            result.message = f"Repair operation failed: {str(e)}"
            
            # Broadcast error event
            await self.sse_operations.create_event(
                event_type="thumbnail_repair_error",
                event_data={
                    "error": str(e),
                    "images_processed": result.images_processed,
                },
                priority="high",
                source="verification_service"
            )
            
            return result

    async def get_verification_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive thumbnail verification statistics.

        Returns:
            Dictionary with verification statistics and health metrics
        """
        try:
            await self._initialize_path_resolver()
            
            # Get basic thumbnail statistics from database
            stats_data = await self.image_ops.get_thumbnail_statistics()
            
            # Add file structure analysis
            structure_status = self.path_resolver.get_structure_migration_status()
            
            # Get current time for timestamps
            current_time = await get_timezone_aware_timestamp_string_async(self.settings_service)
            
            return {
                **stats_data,
                "file_structure_analysis": structure_status,
                "verification_capabilities": {
                    "supports_legacy_structure": True,
                    "supports_new_structure": True,
                    "cross_structure_fallback": True,
                },
                "last_updated": current_time,
            }
            
        except Exception as e:
            logger.error(f"Error getting verification statistics: {e}")
            return {
                "error": str(e),
                "last_updated": await get_timezone_aware_timestamp_string_async(self.settings_service),
            }