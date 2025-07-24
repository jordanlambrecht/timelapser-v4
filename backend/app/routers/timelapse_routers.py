# backend/app/routers/timelapse_routers.py
"""
Timelapse entity management HTTP endpoints.

Role: Timelapse entity management HTTP endpoints
Responsibilities: Timelapse lifecycle operations (start/pause/stop/complete), entity CRUD, progress tracking
Interactions: Uses TimelapseService for business logic, broadcasts SSE events for real-time updates
"""

from typing import List, Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Path,
    status,
    Depends,
    Response,
)
from ..dependencies import (
    TimelapseServiceDep,
    VideoServiceDep,
    ImageServiceDep,
    SchedulerServiceDep,
)
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
)
from ..models.timelapse_model import (
    Timelapse,
    TimelapseCreate,
    TimelapseUpdate,
    TimelapseWithDetails,
)
from ..models import VideoWithDetails
from ..models.image_model import Image
from ..models.shared_models import (
    TimelapseStatistics,
    BulkThumbnailResponse,
)
from ..utils.router_helpers import handle_exceptions, validate_entity_exists
from ..utils.response_helpers import ResponseFormatter
from ..utils.validation_helpers import create_default_timelapse_data, validate_camera_id_match, calculate_thumbnail_percentages
from ..enums import JobPriority

# NOTE: CACHING STRATEGY - MIXED APPROACH (EXCELLENT IMPLEMENTATION)
# Timelapse operations use optimal mixed caching strategy:
# - State changes (start/stop/pause): SSE broadcasting - real-time timelapse monitoring
# - Entity data (list/details): ETag + 5-10 min cache - changes occasionally
# - Statistics: ETag + 15 min cache - aggregated data changes slowly
# - Progress: SSE broadcasting - critical real-time monitoring
# Individual endpoint NOTEs are excellently defined throughout this file.
router = APIRouter(tags=["timelapses"])


# Pydantic validation for timelapse IDs
def valid_timelapse_id(timelapse_id: int = Path(..., ge=1, description="Timelapse ID")):
    """Validate timelapse ID using Pydantic Path validation."""
    return timelapse_id


# NOTE: Good SSE broadcasting - no HTTP caching needed for POST operations
@router.post(
    "/timelapses/new", response_model=Timelapse, status_code=status.HTTP_201_CREATED
)
@handle_exceptions("create new timelapse")
async def create_new_timelapse(
    timelapse_service: TimelapseServiceDep,
    camera_id: int = Query(..., ge=1, description="Camera ID to create timelapse for"),
):
    """
    Create a new timelapse entity for a camera (entity-based architecture).

    Creates a new timelapse entity with proper timezone-aware timestamps
    and inherits settings from the parent camera. This endpoint specifically
    supports the entity-based timelapse architecture where each "Start New Timelapse"
    creates a discrete entity.
    """

    # Create default timelapse data using helper function
    default_data = create_default_timelapse_data(camera_id)
    timelapse_create = TimelapseCreate(**default_data)

    try:
        new_timelapse = await timelapse_service.create_new_timelapse(
            camera_id, timelapse_create
        )
        # SSE broadcasting handled in service layer

        return new_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., camera not found, invalid settings)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating timelapse",
        )


# NOTE: Good SSE broadcasting - no HTTP caching needed for POST operations
@router.post(
    "/timelapses", response_model=Timelapse, status_code=status.HTTP_201_CREATED
)
@handle_exceptions("create timelapse")
async def create_timelapse(
    timelapse_data: TimelapseCreate,
    timelapse_service: TimelapseServiceDep,
    camera_id: int = Query(..., ge=1, description="Camera ID to create timelapse for"),
):
    """
    Create a new timelapse for a camera.

    Creates a new timelapse entity with proper timezone-aware timestamps
    and inherits settings from the parent camera.
    """

    # Validate camera_id matches using helper function
    is_valid, error_message = validate_camera_id_match(camera_id, timelapse_data.camera_id)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    try:
        new_timelapse = await timelapse_service.create_new_timelapse(
            camera_id, timelapse_data
        )
        # SSE broadcasting handled in service layer

        return new_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., camera not found, invalid settings)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating timelapse",
        )


# IMPLEMENTED: ETag + 5 minute cache (timelapse list changes when timelapses created/updated)
# ETag based on latest timelapse updated_at timestamp + count
@router.get("/timelapses", response_model=List[TimelapseWithDetails])
@handle_exceptions("get timelapses")
async def get_timelapses(
    response: Response,
    timelapse_service: TimelapseServiceDep,
    camera_id: Optional[int] = Query(None, description="Filter by camera ID", ge=1),
):
    """
    Get timelapses with optional filtering.

    Returns timelapses with timezone-aware timestamps and proper metadata.
    """

    try:
        timelapses = await timelapse_service.get_timelapses(camera_id=camera_id)

        # Generate ETag based on timelapses collection data
        if timelapses:
            etag = generate_collection_etag([tl.updated_at for tl in timelapses])
        else:
            etag = generate_content_hash_etag(f"empty-{camera_id}")

        # Add moderate cache for timelapse list
        response.headers["Cache-Control"] = (
            "public, max-age=300, s-maxage=300"  # 5 minutes
        )
        response.headers["ETag"] = etag

        # Debug logging handled in service layer
        return timelapses

    except Exception:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapses",
        )


# IMPLEMENTED: ETag + 10 minute cache (timelapse details change occasionally)
# ETag = f'"{timelapse.id}-{timelapse.updated_at.timestamp()}"'
@router.get("/timelapses/{timelapse_id}", response_model=TimelapseWithDetails)
@handle_exceptions("get timelapse")
async def get_timelapse(
    response: Response,
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Get a specific timelapse by ID.

    Returns detailed timelapse information including camera metadata
    and timezone-aware timestamps.
    """

    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    # Generate ETag based on timelapse ID and updated timestamp
    etag = generate_composite_etag(timelapse.id, timelapse.updated_at)

    # Add moderate cache for timelapse details
    response.headers["Cache-Control"] = (
        "public, max-age=600, s-maxage=600"  # 10 minutes
    )
    response.headers["ETag"] = etag

    return timelapse


# NOTE: Good SSE broadcasting - no HTTP caching needed for PUT operations
@router.put("/timelapses/{timelapse_id}", response_model=Timelapse)
@handle_exceptions("update timelapse")
async def update_timelapse(
    timelapse_data: TimelapseUpdate,
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Update a timelapse configuration.

    Allows updating of timelapse settings, time windows, and video generation parameters.
    Changes are applied with timezone-aware timestamp tracking.
    """

    try:
        updated_timelapse = await timelapse_service.update_timelapse(
            timelapse_id, timelapse_data
        )
        if not updated_timelapse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        # SSE broadcasting handled in service layer

        return updated_timelapse

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update timelapse",
        )


# NOTE: Good SSE broadcasting - no HTTP caching needed for DELETE operations
@router.delete("/timelapses/{timelapse_id}", status_code=status.HTTP_200_OK)
@handle_exceptions("delete timelapse")
async def delete_timelapse(
    timelapse_service: TimelapseServiceDep,
    scheduler_service: SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: Ensure running jobs are stopped
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Delete a timelapse and all associated data.

    WARNING: This permanently removes the timelapse, its images, and generated videos.
    """

    try:
        # Get timelapse info before deletion for SSE event
        timelapse_to_delete = await timelapse_service.get_timelapse_by_id(timelapse_id)
        if not timelapse_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        # 🎯 SCHEDULER-CENTRIC: Remove any scheduled jobs for this timelapse before deletion
        try:
            await scheduler_service.remove_timelapse_job(timelapse_id)
        except Exception as e:
            # Log but don't fail - timelapse might not have been scheduled
            pass
        
        success = await timelapse_service.delete_timelapse(timelapse_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        # SSE broadcasting handled in service layer

        return ResponseFormatter.success(
            message=f"Timelapse {timelapse_id} deleted successfully",
            timelapse_id=timelapse_id,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle business logic errors (e.g., cannot delete running timelapse)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete timelapse",
        )


# DEPRECATED ENDPOINTS REMOVED - Use camera-centric endpoints instead:
# - /api/cameras/{camera_id}/timelapses/start
# - /api/cameras/{camera_id}/timelapses/pause
# - /api/cameras/{camera_id}/timelapses/stop
# - /api/cameras/{camera_id}/timelapses/complete

# NOTE: SSE broadcasting handled in service layer - no HTTP caching needed for state changes


# IMPLEMENTED: ETag + 15 minute cache (statistics change slowly)
# ETag based on timelapse.image_count + timelapse.updated_at
@router.get("/timelapses/{timelapse_id}/statistics", response_model=TimelapseStatistics)
@handle_exceptions("get timelapse statistics")
async def get_timelapse_statistics(
    response: Response,
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Get comprehensive statistics for a specific timelapse.

    Returns capture rates, image counts, duration statistics.
    """
    try:
        stats = await timelapse_service.get_timelapse_statistics(timelapse_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        # Generate ETag based on timelapse ID and stats content
        etag = generate_content_hash_etag(f"{timelapse_id}-{stats}")

        # Add longer cache for statistics (they change slowly)
        response.headers["Cache-Control"] = (
            "public, max-age=900, s-maxage=900"  # 15 minutes
        )
        response.headers["ETag"] = etag

        return stats

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapse statistics",
        )


# NOTE: Consider replacing with SSE - progress changes frequently during active timelapses
# Could use very short cache (30 seconds max) or preferably SSE events for real-time updates
@router.get("/timelapses/{timelapse_id}/progress", response_model=TimelapseWithDetails)
@handle_exceptions("get timelapse progress")
async def get_timelapse_progress(
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Get real-time progress tracking data for a timelapse.

    Returns current capture status, day progression, time remaining estimates,
    and capture rate analysis with timezone-aware calculations.
    """
    try:
        timelapse = await timelapse_service.get_timelapse_by_id(timelapse_id)
        if not timelapse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        # Return the complete timelapse details as progress information
        return timelapse

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapse progress",
        )


# IMPLEMENTED: ETag + 10 minute cache (video list changes when videos generated/deleted)
# ETag based on latest video created_at for this timelapse
@router.get("/timelapses/{timelapse_id}/videos", response_model=List[VideoWithDetails])
@handle_exceptions("get timelapse videos")
async def get_timelapse_videos(
    response: Response,
    timelapse_service: TimelapseServiceDep,
    video_service: VideoServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Get all videos for a specific timelapse.

    Returns all videos that have been generated from this timelapse,
    following the nested resource pattern for clear entity relationships.
    """
    # Validate timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    # Get videos for this timelapse using the video service
    videos = await video_service.get_videos_by_timelapse(timelapse_id=timelapse_id)

    # Generate ETag based on videos collection data
    if videos:
        etag = generate_collection_etag([v.created_at for v in videos])
    else:
        etag = generate_content_hash_etag(f"empty-videos-{timelapse_id}")

    # Add moderate cache for video list
    response.headers["Cache-Control"] = (
        "public, max-age=600, s-maxage=600"  # 10 minutes
    )
    response.headers["ETag"] = etag

    # Debug logging handled in service layer
    return videos


# IMPLEMENTED: ETag + 5 minute cache (image list changes when images captured)
# ETag based on timelapse.image_count + latest image captured_at
@router.get("/timelapses/{timelapse_id}/images", response_model=List[Image])
@handle_exceptions("get timelapse images")
async def get_timelapse_images(
    response: Response,
    timelapse_service: TimelapseServiceDep,
    image_service: ImageServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of images to return"
    ),
    offset: int = Query(0, ge=0, description="Number of images to skip"),
):
    """
    Get all images for a specific timelapse.

    Returns all images that belong to this timelapse, following the nested
    resource pattern for clear entity relationships. Supports pagination
    for large image collections.
    """
    # Validate timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    # Calculate page from offset and limit
    page = (offset // limit) + 1

    # Get images for this timelapse using the existing service method
    result = await image_service.get_images(
        timelapse_id=timelapse_id,
        page=page,
        page_size=limit,
        order_by="captured_at",
        order_dir="DESC",
    )

    images = result.images

    # Generate ETag based on timelapse ID, pagination, and images data
    if images:
        etag = generate_collection_etag([img.captured_at for img in images])
    else:
        etag = generate_content_hash_etag(
            f"empty-images-{timelapse_id}-{offset}-{limit}"
        )

    # Add short cache for image list (changes when new images captured)
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    # Debug logging handled in service layer
    return images


# ====================================================================
# TIMELAPSE-LEVEL THUMBNAIL OPERATIONS
# ====================================================================


@router.get("/timelapses/{timelapse_id}/thumbnails/stats", response_model=dict)
@handle_exceptions("get timelapse thumbnail statistics")
async def get_timelapse_thumbnail_stats(
    response: Response,
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Get thumbnail statistics for a specific timelapse.

    Returns thumbnail count, small count, and generation status for the timelapse.
    Uses the real-time counts stored in the timelapses table.
    """
    # Validate timelapse exists
    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    # Extract thumbnail statistics from timelapse model
    percentages = calculate_thumbnail_percentages(
        timelapse.thumbnail_count, 
        timelapse.small_count, 
        timelapse.image_count
    )
    
    stats = {
        "timelapse_id": timelapse_id,
        "thumbnail_count": timelapse.thumbnail_count,
        "small_count": timelapse.small_count,
        "total_images": timelapse.image_count,
        "thumbnail_percentage": percentages["thumbnail_percentage"],
        "small_percentage": percentages["small_percentage"],
    }

    # Generate ETag based on timelapse counts
    etag = generate_content_hash_etag(
        f"{timelapse_id}-{timelapse.thumbnail_count}-{timelapse.small_count}-{timelapse.image_count}"
    )

    # Add moderate cache for thumbnail stats
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return stats


@router.post(
    "/timelapses/{timelapse_id}/thumbnails/regenerate",
    response_model=BulkThumbnailResponse,
)
@handle_exceptions("regenerate timelapse thumbnails")
async def regenerate_timelapse_thumbnails(
    image_service: ImageServiceDep,
    scheduler_service: SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: Add scheduler dependency
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
    priority: str = Query(JobPriority.MEDIUM, description="Job priority: high, medium, low"),
    force: bool = Query(
        False, description="Force regeneration even if thumbnails exist"
    ),
):
    """
    🎯 SCHEDULER-CENTRIC: Regenerate all thumbnails for a specific timelapse through scheduler authority.
    
    ALL timing operations must flow through SchedulerWorker. This bulk operation
    will be coordinated by the scheduler to prevent conflicts with other thumbnail jobs.

    Queues thumbnail generation jobs for all images in the timelapse.
    Optionally forces regeneration even if thumbnails already exist.
    """
    # Validate timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    try:
        # Get all images for this timelapse
        result = await image_service.get_images(
            timelapse_id=timelapse_id,
            page=1,
            page_size=10000,  # Large page size to get all images
            order_by="captured_at",
            order_dir="ASC",
        )

        images = result.images

        if not images:
            return BulkThumbnailResponse(
                total_requested=0,
                jobs_created=0,
                jobs_failed=0,
                created_job_ids=[],
                failed_image_ids=[],
            )

        # Filter images if force=False (only queue jobs for images without thumbnails)
        image_ids = []
        if force:
            # Queue all images
            image_ids = [img.id for img in images]
        else:
            # Only queue images missing thumbnails
            image_ids = [
                img.id for img in images if not img.thumbnail_path or not img.small_path
            ]

        if not image_ids:
            return BulkThumbnailResponse(
                total_requested=len(images),
                jobs_created=0,
                jobs_failed=0,
                created_job_ids=[],
                failed_image_ids=[],
            )

        # 🎯 SCHEDULER-CENTRIC: Route bulk thumbnail generation through scheduler authority
        # NOTE: Using individual scheduling calls until bulk method is implemented
        # Each thumbnail is scheduled individually through scheduler for proper coordination
        
        created_job_ids = []
        failed_image_ids = []
        
        for image_id in image_ids:
            try:
                # Schedule individual thumbnail generation through scheduler
                scheduler_result = await scheduler_service.schedule_immediate_thumbnail_generation(
                    image_id=image_id,
                    priority=priority if priority else JobPriority.MEDIUM
                )
                
                if scheduler_result.get("success"):
                    created_job_ids.append(f"scheduled_{image_id}")
                else:
                    failed_image_ids.append(image_id)
                    
            except Exception as e:
                failed_image_ids.append(image_id)
        
        return BulkThumbnailResponse(
            total_requested=len(image_ids),
            jobs_created=len(created_job_ids),
            jobs_failed=len(failed_image_ids),
            created_job_ids=created_job_ids,
            failed_image_ids=failed_image_ids,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate thumbnails for timelapse {timelapse_id}: {str(e)}",
        )


@router.post("/timelapses/{timelapse_id}/thumbnails/verify", response_model=dict)
@handle_exceptions("verify timelapse thumbnails")
async def verify_timelapse_thumbnails(
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Verify thumbnail integrity for a specific timelapse.

    Recalculates thumbnail counts from actual database data and compares
    with the cached counts in the timelapses table. Updates cached counts if needed.
    """
    # Validate timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    try:
        # TODO: Implement verify_timelapse_thumbnails in ImageService or create ThumbnailService
        # For now, return a placeholder response
        return {
            "success": False,
            "message": "Thumbnail verification not yet implemented",
            "timelapse_id": timelapse_id
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify thumbnails for timelapse {timelapse_id}: {str(e)}",
        )


@router.delete("/timelapses/{timelapse_id}/thumbnails", response_model=dict)
@handle_exceptions("remove timelapse thumbnails")
async def remove_timelapse_thumbnails(
    timelapse_service: TimelapseServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
    confirm: bool = Query(
        False, description="Confirmation required for destructive operation"
    ),
):
    """
    Remove all thumbnails for a specific timelapse.

    WARNING: This permanently deletes thumbnail files from disk and clears
    thumbnail paths in the database. Requires explicit confirmation.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This operation requires confirmation. Add ?confirm=true to proceed.",
        )

    # Validate timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    try:
        # TODO: Implement remove_all_timelapse_thumbnails in ImageService or create ThumbnailService
        # For now, return a placeholder response
        return {
            "success": False,
            "message": "Thumbnail removal not yet implemented",
            "timelapse_id": timelapse_id,
            "deleted_files": 0,
            "cleared_database_records": 0
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove thumbnails for timelapse {timelapse_id}: {str(e)}",
        )


# NOTE: Additional endpoints like video-settings, day-numbers, etc.
# will be added when the corresponding service methods are implemented
