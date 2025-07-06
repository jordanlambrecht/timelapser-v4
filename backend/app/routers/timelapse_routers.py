# backend/app/routers/timelapse_routers.py
"""
Timelapse entity management HTTP endpoints.

Role: Timelapse entity management HTTP endpoints
Responsibilities: Timelapse lifecycle operations (start/pause/stop/complete), entity CRUD, progress tracking
Interactions: Uses TimelapseService for business logic, broadcasts SSE events for real-time updates
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Path, status, Depends, Body, Response

from ..database import async_db
from ..dependencies import (
    TimelapseServiceDep,
    SettingsServiceDep,
    CameraServiceDep,
    VideoServiceDep,
    ImageServiceDep,
)
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
    generate_timestamp_etag
)
from ..services.timelapse_service import TimelapseService
from ..services.settings_service import SettingsService
from ..models.timelapse_model import (
    Timelapse,
    TimelapseCreate,
    TimelapseCreateData,
    TimelapseUpdate,
    TimelapseWithDetails,
)
from ..models import VideoWithDetails
from ..models.image_model import ImageWithDetails
from ..models.shared_models import (
    TimelapseStatistics,
    VideoGenerationMode,
    VideoAutomationMode,
)
from ..utils.router_helpers import handle_exceptions, validate_entity_exists
from ..utils.response_helpers import ResponseFormatter
from ..utils.timezone_utils import (
    get_timezone_from_cache_async,
    get_timezone_aware_timestamp_string_async,
)

# TODO: CACHING STRATEGY - MIXED APPROACH (EXCELLENT IMPLEMENTATION)
# Timelapse operations use optimal mixed caching strategy:
# - State changes (start/stop/pause): SSE broadcasting - real-time timelapse monitoring
# - Entity data (list/details): ETag + 5-10 min cache - changes occasionally
# - Statistics: ETag + 15 min cache - aggregated data changes slowly
# - Progress: SSE broadcasting - critical real-time monitoring
# Individual endpoint TODOs are excellently defined throughout this file.
router = APIRouter(tags=["timelapses"])


# Pydantic validation for timelapse IDs
def valid_timelapse_id(timelapse_id: int = Path(..., ge=1, description="Timelapse ID")):
    """Validate timelapse ID using Pydantic Path validation."""
    return timelapse_id


# TODO: Good SSE broadcasting - no HTTP caching needed for POST operations
@router.post(
    "/timelapses/new", response_model=Timelapse, status_code=status.HTTP_201_CREATED
)
@handle_exceptions("create new timelapse")
async def create_new_timelapse(
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    camera_id: int = Query(..., ge=1, description="Camera ID to create timelapse for"),
):
    """
    Create a new timelapse entity for a camera (entity-based architecture).

    Creates a new timelapse entity with proper timezone-aware timestamps
    and inherits settings from the parent camera. This endpoint specifically
    supports the entity-based timelapse architecture where each "Start New Timelapse"
    creates a discrete entity.
    """

    # Create default timelapse data with all required fields

    timelapse_create = TimelapseCreate(
        camera_id=camera_id,
        name=None,
        auto_stop_at=None,
        time_window_type="none",
        time_window_start=None,
        time_window_end=None,
        sunrise_offset_minutes=None,
        sunset_offset_minutes=None,
        use_custom_time_window=False,
        video_generation_mode=VideoGenerationMode.STANDARD,
        standard_fps=30,
        enable_time_limits=False,
        min_time_seconds=None,
        max_time_seconds=None,
        target_time_seconds=None,
        fps_bounds_min=15,
        fps_bounds_max=60,
        video_automation_mode=VideoAutomationMode.MANUAL,
        generation_schedule=None,
        milestone_config=None,
    )

    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

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


# TODO: Good SSE broadcasting - no HTTP caching needed for POST operations
@router.post(
    "/timelapses", response_model=Timelapse, status_code=status.HTTP_201_CREATED
)
@handle_exceptions("create timelapse")
async def create_timelapse(
    timelapse_data: TimelapseCreate,
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    camera_id: int = Query(..., ge=1, description="Camera ID to create timelapse for"),
):
    """
    Create a new timelapse for a camera.

    Creates a new timelapse entity with proper timezone-aware timestamps
    and inherits settings from the parent camera.
    """

    # Validate camera_id matches the one in timelapse_data
    if timelapse_data.camera_id != camera_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera ID in URL must match camera ID in request body",
        )

    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

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
    settings_service: SettingsServiceDep,
    camera_id: Optional[int] = Query(None, description="Filter by camera ID", ge=1),
):
    """
    Get timelapses with optional filtering.

    Returns timelapses with timezone-aware timestamps and proper metadata.
    """

    # Get timezone for proper timestamp formatting in logs
    timezone_str = await get_timezone_from_cache_async(settings_service)

    try:
        timelapses = await timelapse_service.get_timelapses(camera_id=camera_id)

        # Generate ETag based on timelapses collection data
        if timelapses:
            etag = generate_collection_etag([tl.updated_at for tl in timelapses])
        else:
            etag = generate_content_hash_etag(f"empty-{camera_id}")
        
        # Add moderate cache for timelapse list
        response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
        response.headers["ETag"] = etag

        # Debug logging handled in service layer
        return timelapses

    except Exception as e:
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
    response.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"  # 10 minutes
    response.headers["ETag"] = etag
    
    return timelapse


# TODO: Good SSE broadcasting - no HTTP caching needed for PUT operations
@router.put("/timelapses/{timelapse_id}", response_model=Timelapse)
@handle_exceptions("update timelapse")
async def update_timelapse(
    timelapse_data: TimelapseUpdate,
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    Update a timelapse configuration.

    Allows updating of timelapse settings, time windows, and video generation parameters.
    Changes are applied with timezone-aware timestamp tracking.
    """

    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

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


# TODO: Good SSE broadcasting - no HTTP caching needed for DELETE operations
@router.delete("/timelapses/{timelapse_id}", status_code=status.HTTP_200_OK)
@handle_exceptions("delete timelapse")
async def delete_timelapse(
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
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


# TODO: DEPRECATED but add SSE broadcasting - no HTTP caching needed for state changes
@router.post(
    "/{timelapse_id}/start",
    response_model=Timelapse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
@handle_exceptions("start timelapse")
async def start_timelapse(
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    DEPRECATED: Use /api/cameras/{camera_id}/timelapses/start instead.

    Start a timelapse recording session.

    Transitions the timelapse to 'running' status and begins image capture
    according to the configured schedule and time windows.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

    try:
        updated_timelapse = await timelapse_service.start_timelapse(timelapse_id)
        # SSE broadcasting handled in service layer

        return updated_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse already running, invalid state)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start timelapse",
        )


# TODO: DEPRECATED but add SSE broadcasting - no HTTP caching needed for state changes
@router.post(
    "/{timelapse_id}/pause",
    response_model=Timelapse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
@handle_exceptions("pause timelapse")
async def pause_timelapse(
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    DEPRECATED: Use /api/cameras/{camera_id}/timelapses/pause instead.

    Pause a running timelapse.

    Temporarily stops image capture while preserving the ability to resume.
    The timelapse can be restarted later from where it left off.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

    try:
        updated_timelapse = await timelapse_service.pause_timelapse(timelapse_id)
        # SSE broadcasting handled in service layer

        return updated_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse not running)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause timelapse",
        )


# TODO: DEPRECATED but add SSE broadcasting - no HTTP caching needed for state changes
@router.post(
    "/{timelapse_id}/stop",
    response_model=Timelapse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
@handle_exceptions("stop timelapse")
async def stop_timelapse(
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    DEPRECATED: Use /api/cameras/{camera_id}/timelapses/stop instead.

    Stop a timelapse recording session.

    Stops image capture and transitions to 'stopped' status.
    The timelapse can be resumed or completed from this state.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

    try:
        updated_timelapse = await timelapse_service.stop_timelapse(timelapse_id)
        # SSE broadcasting handled in service layer

        return updated_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse not running)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop timelapse",
        )


# TODO: DEPRECATED but add SSE broadcasting - no HTTP caching needed for state changes
@router.post(
    "/{timelapse_id}/complete",
    response_model=Timelapse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
@handle_exceptions("complete timelapse")
async def complete_timelapse(
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    timelapse_id: int = Depends(valid_timelapse_id),
):
    """
    DEPRECATED: Use /api/cameras/{camera_id}/timelapses/complete instead.

    Complete a timelapse and mark as finished.

    Marks the timelapse as 'completed', making it a permanent historical record.
    Completed timelapses cannot be resumed but can be used for video generation.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_timezone_from_cache_async(settings_service)

    try:
        completed_timelapse = await timelapse_service.complete_timelapse(timelapse_id)
        # SSE broadcasting handled in service layer

        return completed_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse already completed)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete timelapse",
        )


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
        response.headers["Cache-Control"] = "public, max-age=900, s-maxage=900"  # 15 minutes
        response.headers["ETag"] = etag
        
        return stats

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Error logging handled in service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapse statistics",
        )


# TODO: Replace with SSE - progress changes frequently during active timelapses
# Use very short cache (30 seconds max) or preferably SSE events
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
    except Exception as e:
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

    # Get videos for this timelapse using the existing service method
    videos = await video_service.get_videos(timelapse_id=timelapse_id)

    # Generate ETag based on videos collection data
    if videos:
        etag = generate_collection_etag([v.created_at for v in videos])
    else:
        etag = generate_content_hash_etag(f"empty-videos-{timelapse_id}")
    
    # Add moderate cache for video list
    response.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"  # 10 minutes
    response.headers["ETag"] = etag

    # Debug logging handled in service layer
    return videos


# IMPLEMENTED: ETag + 5 minute cache (image list changes when images captured)
# ETag based on timelapse.image_count + latest image captured_at
@router.get("/timelapses/{timelapse_id}/images", response_model=List[ImageWithDetails])
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

    images = result.get("images", [])
    
    # Generate ETag based on timelapse ID, pagination, and images data
    if images:
        etag = generate_collection_etag([img.captured_at for img in images])
    else:
        etag = generate_content_hash_etag(f"empty-images-{timelapse_id}-{offset}-{limit}")
    
    # Add short cache for image list (changes when new images captured)
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag
    
    # Debug logging handled in service layer
    return images


# NOTE: Additional endpoints like images, video-settings, day-numbers, etc.
# will be added when the corresponding service methods are implemented
