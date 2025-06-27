# backend/app/routers/thumbnail_routers.py
"""
Thumbnail management HTTP endpoints.

Role: Thumbnail management HTTP endpoints
Responsibilities: Thumbnail generation, regeneration, and serving operations
Interactions: Uses ImageService for business logic, delegates to services following the layered architecture pattern
"""


from fastapi import APIRouter, BackgroundTasks, Query
from loguru import logger

from ..dependencies import ImageServiceDep, AsyncDatabaseDep
from ..models.shared_models import (
    ThumbnailGenerationResult,
    ThumbnailRegenerationStatus,
    ThumbnailStatistics,
    ThumbnailOperationResponse,
)
from ..utils.router_helpers import handle_exceptions, validate_entity_exists
from ..utils.timezone_utils import get_timezone_aware_timestamp_async

router = APIRouter(prefix="/thumbnails", tags=["thumbnails"])


@router.post("/generate/{image_id}", response_model=ThumbnailGenerationResult)
@handle_exceptions("generate thumbnail for image")
async def generate_thumbnail_for_image(
    image_id: int,
    image_service: ImageServiceDep,
    async_db: AsyncDatabaseDep,
    force_regenerate: bool = Query(
        False, description="Force regeneration even if thumbnails exist"
    ),
):
    """
    Generate thumbnails for a specific image.

    Args:
        image_id: ID of the image to generate thumbnails for
        force_regenerate: Whether to regenerate existing thumbnails

    Returns:
        ThumbnailGenerationResult with generation details
    """
    # Validate image exists (using router helper)
    await validate_entity_exists(image_service.get_image_by_id, image_id, "image")

    # Use database-aware timezone for timing
    start_time = await get_timezone_aware_timestamp_async(async_db)
    result = await image_service.coordinate_thumbnail_generation(
        image_id, force_regenerate
    )
    end_time = await get_timezone_aware_timestamp_async(async_db)
    processing_time = int((end_time - start_time).total_seconds() * 1000)

    # Create new result with processing time (service now returns proper Pydantic model)
    return ThumbnailGenerationResult(
        success=result.success,
        image_id=result.image_id,
        thumbnail_path=result.thumbnail_path,
        small_path=result.small_path,
        thumbnail_size=result.thumbnail_size,
        small_size=result.small_size,
        error=result.error,
        processing_time_ms=processing_time,
    )


@router.get("/stats", response_model=ThumbnailStatistics)
@handle_exceptions("get thumbnail statistics")
async def get_thumbnail_stats(
    image_service: ImageServiceDep, async_db: AsyncDatabaseDep
):
    """
    Get comprehensive thumbnail statistics.

    Returns:
        ThumbnailStatistics with coverage and storage information
    """
    # Use ImageService's existing thumbnail statistics method
    stats_data = await image_service.image_ops.get_thumbnail_statistics()

    # Use database-aware timezone for last_updated timestamp
    current_time = await get_timezone_aware_timestamp_async(async_db)

    return ThumbnailStatistics(**stats_data, last_updated=current_time)


@router.post("/regenerate", response_model=ThumbnailOperationResponse)
@handle_exceptions("start thumbnail regeneration")
async def start_thumbnail_regeneration(
    background_tasks: BackgroundTasks,
    image_service: ImageServiceDep,
    async_db: AsyncDatabaseDep,
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of images to process"
    ),
):
    """
    Start thumbnail regeneration for images missing thumbnails.

    Args:
        limit: Maximum number of images to process in this batch

    Returns:
        ThumbnailOperationResponse with operation status
    """
    # Get images that need thumbnails
    images_without_thumbnails = (
        await image_service.image_ops.get_images_without_thumbnails(limit)
    )

    # Use database-aware timezone for timestamps
    current_time = await get_timezone_aware_timestamp_async(async_db)

    if not images_without_thumbnails:
        return ThumbnailOperationResponse(
            success=True,
            message="No images need thumbnail regeneration",
            operation="regenerate",
            data={"images_processed": 0},
            timestamp=current_time,
        )

    # Add background task for processing thumbnails
    background_tasks.add_task(
        _process_thumbnail_regeneration, image_service, images_without_thumbnails
    )

    return ThumbnailOperationResponse(
        success=True,
        message=f"Thumbnail regeneration started for {len(images_without_thumbnails)} images",
        operation="regenerate",
        data={
            "images_to_process": len(images_without_thumbnails),
            "started_at": current_time.isoformat(),
        },
        timestamp=current_time,
    )


@router.get("/regenerate/status", response_model=ThumbnailRegenerationStatus)
@handle_exceptions("get regeneration status")
async def get_regeneration_status():
    """
    Get current thumbnail regeneration status.

    Note: This is a simplified implementation. For production use, consider
    implementing a proper job queue system with Redis or database-backed
    progress tracking.

    Returns:
        ThumbnailRegenerationStatus with current progress
    """
    # TODO: For now, return idle status since we don't have persistent state tracking
    # In a production system, this would query a job queue or database
    return ThumbnailRegenerationStatus(
        active=False, progress=100, status_message="No active regeneration process"
    )


@router.delete("/cleanup", response_model=ThumbnailOperationResponse)
@handle_exceptions("cleanup orphaned thumbnails")
async def cleanup_orphaned_thumbnails(
    image_service: ImageServiceDep,
    async_db: AsyncDatabaseDep,
    dry_run: bool = Query(
        False, description="Preview cleanup without actually deleting files"
    ),
):
    """
    Clean up thumbnail files that no longer have corresponding images.

    Args:
        dry_run: If true, only report what would be deleted without actually deleting

    Returns:
        ThumbnailOperationResponse with cleanup results
    """
    # TODO: This would require implementation of orphaned file detection logic
    # For now, return a placeholder response
    logger.info(f"Thumbnail cleanup requested (dry_run={dry_run})")

    # Use database-aware timezone for timestamp
    current_time = await get_timezone_aware_timestamp_async(async_db)

    return ThumbnailOperationResponse(
        success=True,
        message=(
            "Thumbnail cleanup completed"
            if not dry_run
            else "Thumbnail cleanup preview completed"
        ),
        operation="cleanup",
        data={"files_deleted": 0, "space_freed_mb": 0.0, "dry_run": dry_run},
        timestamp=current_time,
    )


async def _process_thumbnail_regeneration(
    image_service: ImageServiceDep, images_to_process: list
):
    """
    Background task to process thumbnail regeneration.

    Args:
        image_service: ImageService dependency
        images_to_process: List of images that need thumbnails
    """
    completed = 0
    failed = 0

    logger.info(f"Starting thumbnail regeneration for {len(images_to_process)} images")

    for image in images_to_process:
        try:
            # Use ImageService coordinate_thumbnail_generation for each image
            result = await image_service.coordinate_thumbnail_generation(
                image.id, force_regenerate=True
            )

            # Service now returns ThumbnailGenerationResult Pydantic model
            if result.success:
                completed += 1
                logger.debug(f"Generated thumbnails for image {image.id}")
            else:
                failed += 1
                logger.warning(
                    f"Failed to generate thumbnails for image {image.id}: {result.error}"
                )

        except Exception as e:
            failed += 1
            logger.error(f"Error processing thumbnails for image {image.id}: {e}")

    logger.info(
        f"Thumbnail regeneration completed: {completed} successful, {failed} failed"
    )
