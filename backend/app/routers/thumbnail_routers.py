# backend/app/routers/thumbnail_routers.py
"""
Thumbnail management HTTP endpoints.

Role: Thumbnail management HTTP endpoints
Responsibilities: Thumbnail generation, regeneration, and serving operations
Interactions: Uses ImageService for business logic, delegates to services following the layered architecture pattern

Updated: 2025-07-06 - Debugging thumbnail regeneration endpoints
"""


from fastapi import APIRouter, BackgroundTasks, Query
from loguru import logger

from ..dependencies import ThumbnailServiceDep, SettingsServiceDep
from ..models.shared_models import (
    ThumbnailGenerationResult,
    ThumbnailRegenerationStatus,
    ThumbnailStatistics,
    ThumbnailOperationResponse,
)
from ..utils.router_helpers import handle_exceptions, validate_entity_exists
from ..utils.response_helpers import ResponseFormatter
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_string_async,
)

# TODO: CACHING STRATEGY - MIXED APPROACH
# Thumbnail operations use mixed caching strategy:
# - Statistics: ETag + 10-15 min cache - aggregated data changes slowly
# - Generation/regeneration: No cache + SSE broadcasting - dynamic operations
# - Status endpoints: SSE broadcasting or very short cache - real-time monitoring
# - Cleanup operations: No cache - dynamic DELETE operations
router = APIRouter(tags=["thumbnails"])

# NOTE: Thumbnail regeneration state is now managed by the ImageService layer
# This eliminates global state from the router and follows proper architectural patterns


@router.post(
    "/thumbnails/generate/{image_id}", response_model=ThumbnailGenerationResult
)
@handle_exceptions("generate thumbnail for image")
async def generate_thumbnail_for_image(
    image_id: int,
    thumbnail_service: ThumbnailServiceDep,
    settings_service: SettingsServiceDep,
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
    # Use database-aware timezone for timing (cache-backed)
    start_time = await get_timezone_aware_timestamp_async(settings_service)
    result = await thumbnail_service.generate_thumbnail_for_image(
        image_id, force_regenerate
    )
    end_time = await get_timezone_aware_timestamp_async(settings_service)
    processing_time = int((end_time - start_time).total_seconds() * 1000)

    # Add processing time to existing result using efficient Pydantic model_copy
    thumbnail_result = result.model_copy(update={"processing_time_ms": processing_time})

    # SSE broadcasting handled by service layer (proper architecture)

    return thumbnail_result


@router.get("/thumbnails/stats", response_model=ThumbnailStatistics)
@handle_exceptions("get thumbnail statistics")
async def get_thumbnail_stats(
    thumbnail_service: ThumbnailServiceDep, settings_service: SettingsServiceDep
):
    """
    Get comprehensive thumbnail statistics.

    Returns:
        ThumbnailStatistics with coverage and storage information
    """
    return await thumbnail_service.get_thumbnail_statistics()


@router.post("/thumbnails/regenerate-all", response_model=ThumbnailOperationResponse)
@router.post("/thumbnails/regenerate", deprecated=True)
@handle_exceptions("start thumbnail regeneration")
async def start_thumbnail_regeneration(
    thumbnail_service: ThumbnailServiceDep,
    settings_service: SettingsServiceDep,
    limit: int = Query(
        1000, ge=1, le=10000, description="Maximum number of images to process"
    ),
):
    """
    Start thumbnail regeneration for all images using background processing.
    Returns immediately while processing continues in the background.

    Args:
        limit: Maximum number of images to regenerate (1-10000)

    Returns:
        ThumbnailOperationResponse with session ID and immediate status
    """
    current_time = await get_timezone_aware_timestamp_async(settings_service)

    # Start background regeneration via ThumbnailService
    result = await thumbnail_service.start_thumbnail_regeneration_background(limit)

    return ThumbnailOperationResponse(
        success=result["success"],
        message=result["message"],
        operation="regenerate_background",
        data=result.get("data", {"limit": limit}),
        timestamp=current_time,
    )


@router.get(
    "/thumbnails/regenerate-all/status", response_model=ThumbnailRegenerationStatus
)
@handle_exceptions("get thumbnail regeneration status")
async def get_regeneration_status(
    thumbnail_service: ThumbnailServiceDep,
):
    """
    Get current thumbnail regeneration status.

    Returns:
        ThumbnailRegenerationStatus with current progress
    """
    return await thumbnail_service.get_thumbnail_regeneration_status()


@router.post(
    "/thumbnails/regenerate-all/cancel", response_model=ThumbnailOperationResponse
)
@handle_exceptions("cancel thumbnail regeneration")
async def cancel_thumbnail_regeneration(
    thumbnail_service: ThumbnailServiceDep, settings_service: SettingsServiceDep
):
    """
    Cancel currently running thumbnail regeneration process.

    Returns:
        ThumbnailOperationResponse with cancellation status
    """
    current_time = await get_timezone_aware_timestamp_async(settings_service)

    # Cancel via ThumbnailService
    result = await thumbnail_service.cancel_thumbnail_regeneration()

    return ThumbnailOperationResponse(
        success=result["success"],
        message=result["message"],
        operation="cancel",
        data={"cancelled_at": current_time.isoformat()},
        timestamp=current_time,
    )


@router.delete("/thumbnails/delete-all", response_model=ThumbnailOperationResponse)
@handle_exceptions("delete all thumbnails")
async def delete_all_thumbnails(
    thumbnail_service: ThumbnailServiceDep,
    settings_service: SettingsServiceDep,
):
    """
    Delete all thumbnail files and clear database references.

    Returns:
        ThumbnailOperationResponse with deletion results
    """
    current_time = await get_timezone_aware_timestamp_async(settings_service)

    # Start deletion via ThumbnailService
    result = await thumbnail_service.delete_all_thumbnails()

    return ThumbnailOperationResponse(
        success=result["success"],
        message=result["message"],
        operation="delete_all",
        data={
            "deleted_files": result.get("deleted_files", 0),
            "deleted_size_mb": result.get("deleted_size_mb", 0.0),
            "cameras_processed": result.get("cameras_processed", 0),
            "cleared_database_records": result.get("cleared_database_records", 0),
            "errors": len(result.get("errors", [])),
        },
        timestamp=current_time,
    )


@router.post("/thumbnails/verify", response_model=ThumbnailOperationResponse)
@handle_exceptions("verify all thumbnails")
async def verify_all_thumbnails(
    thumbnail_service: ThumbnailServiceDep,
    settings_service: SettingsServiceDep,
):
    """
    Verify all thumbnail files system-wide.

    Returns:
        ThumbnailOperationResponse with verification results
    """
    current_time = await get_timezone_aware_timestamp_async(settings_service)

    # Start verification via ThumbnailService
    result = await thumbnail_service.verify_all_thumbnails()

    return ThumbnailOperationResponse(
        success=result["success"],
        message=result["message"],
        operation="verify",
        data={
            "total_images": result.get("total_images", 0),
            "images_with_thumbnails": result.get("images_with_thumbnails", 0),
            "images_with_small": result.get("images_with_small", 0),
            "images_without_thumbnails": result.get("images_without_thumbnails", 0),
            "thumbnail_coverage_percentage": result.get(
                "thumbnail_coverage_percentage", 0.0
            ),
        },
        timestamp=current_time,
    )


@router.post("/thumbnails/repair", response_model=ThumbnailOperationResponse)
@handle_exceptions("repair orphaned thumbnails")
async def repair_orphaned_thumbnails(
    thumbnail_service: ThumbnailServiceDep,
    settings_service: SettingsServiceDep,
):
    """
    Repair orphaned thumbnail files by matching them back to database.

    Returns:
        ThumbnailOperationResponse with repair results
    """
    current_time = await get_timezone_aware_timestamp_async(settings_service)

    # Start repair via ThumbnailService
    result = await thumbnail_service.repair_orphaned_thumbnails()

    return ThumbnailOperationResponse(
        success=result["success"],
        message=result["message"],
        operation="repair",
        data={
            "orphaned_files_found": result.get("orphaned_files_found", 0),
            "files_matched": result.get("files_matched", 0),
            "files_deleted": result.get("files_deleted", 0),
            "database_records_updated": result.get("database_records_updated", 0),
            "timelapses_affected": result.get("timelapses_affected", 0),
        },
        timestamp=current_time,
    )


@router.delete("/thumbnails/cleanup", response_model=ThumbnailOperationResponse)
@handle_exceptions("cleanup orphaned thumbnails")
async def cleanup_orphaned_thumbnails(
    thumbnail_service: ThumbnailServiceDep,
    settings_service: SettingsServiceDep,
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
    current_time = await get_timezone_aware_timestamp_async(settings_service)

    # Start cleanup via ThumbnailService
    result = await thumbnail_service.cleanup_orphaned_thumbnails(dry_run)

    return ThumbnailOperationResponse(
        success=result["success"],
        message=result["message"],
        operation="cleanup",
        data={
            "orphaned_files_found": result.get("orphaned_files_found", 0),
            "files_deleted": result.get("files_deleted", 0),
            "files_skipped": result.get("files_skipped", 0),
            "storage_recovered_mb": result.get("storage_recovered_mb", 0.0),
            "dry_run": dry_run,
        },
        timestamp=current_time,
    )


# ARCHITECTURAL COMPLIANCE ACHIEVED:
# - Background task function moved to ImageService (proper service layer)
# - Global state management moved to service layer
# - Router now delegates to service methods following layered architecture
# - All business logic removed from router layer
#
# Service layer methods now handle:
# - start_thumbnail_regeneration() - Initiates background processing
# - get_thumbnail_regeneration_status() - Retrieves current state
# - cancel_thumbnail_regeneration() - Handles cancellation logic
#
# This eliminates all architectural violations and follows proper patterns.
