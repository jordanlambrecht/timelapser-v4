# backend/app/routers/camera_routers.py
"""
Camera management HTTP endpoints.

Role: Camera management HTTP endpoints
Responsibilities: Camera CRUD operations, health status endpoints, image serving endpoints
Interactions: Uses CameraService for business logic, returns Pydantic models,
             handles HTTP status codes and error responses

Architecture: API Layer - delegates all business logic to services
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Path as FastAPIPath, Response, Request
from fastapi.responses import FileResponse
from loguru import logger

from ..constants import (
    CAMERA_NOT_FOUND,
    CAMERA_CAPTURE_FAILED,
    CAMERA_DELETED_SUCCESS,
    CAMERA_STATUS_UPDATED_SUCCESS,
    NO_IMAGES_FOUND,
)
from ..dependencies import (
    CameraServiceDep,
    TimelapseServiceDep,
    VideoServiceDep,
    ImageServiceDep,
    LogServiceDep,
    SettingsServiceDep,
)
from ..models import Camera, CameraCreate, CameraUpdate
from ..models.camera_model import (
    CameraWithLastImage,
    CameraWithStats,
    CameraDetailsResponse,
    CameraStats,
)
from ..models.shared_models import (
    CameraHealthStatus,
    CameraConnectivityTestResult,
    CameraCaptureWorkflowResult,
    ImageStatisticsResponse,
    CameraLatestImageResponse,
    CameraLatestImageData,
    CameraLatestImageUrls,
    CameraLatestImageMetadata,
)
from ..utils.file_helpers import clean_filename
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
)
from ..utils.cache_manager import (
    generate_timestamp_etag,
    generate_composite_etag,
    generate_collection_etag,
    generate_content_hash_etag,
    validate_etag_match,
)

# TODO: CACHING STRATEGY - MIXED APPROACH
# Camera operations use mixed caching strategy:
# - Real-time data (status, health, counts): SSE broadcasting (no HTTP cache)
# - Semi-static data (camera details, settings): ETag + short cache (2-5 min)
# - Immutable content (images, thumbnails): Long cache with ETag validation
# Individual endpoint TODOs are well-defined throughout this file.
router = APIRouter(tags=["cameras"])


# Removed timelapse-stats endpoint per decision: "DEPRECATE BACKEND - Remove broken endpoint"
# Timelapse statistics are available through the main timelapse endpoints


# TODO: Add SSE broadcasting for real-time timelapse status updates (no HTTP caching needed)
@router.post("/cameras/{camera_id}/start-timelapse", response_model=Dict[str, Any])
@handle_exceptions("start timelapse")
async def start_timelapse(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
    timelapse_data: Optional[Dict[str, Any]] = None,
):
    """Start a new timelapse for a camera."""

    # Delegate entirely to the service layer
    result = await camera_service.start_new_timelapse(camera_id, timelapse_data or {})
    return result


# TODO: Add SSE broadcasting for real-time timelapse status updates (no HTTP caching needed)
@router.post("/cameras/{camera_id}/pause-timelapse", response_model=Dict[str, Any])
@handle_exceptions("pause timelapse")
async def pause_timelapse(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Pause the active timelapse for a camera."""

    # Delegate entirely to the service layer
    result = await camera_service.pause_active_timelapse(camera_id)
    return result


# TODO: Add SSE broadcasting for real-time timelapse status updates (no HTTP caching needed)
@router.post("/cameras/{camera_id}/resume-timelapse", response_model=Dict[str, Any])
@handle_exceptions("resume timelapse")
async def resume_timelapse(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Resume the active timelapse for a camera."""

    # Delegate entirely to the service layer
    result = await camera_service.resume_active_timelapse(camera_id)
    return result


# TODO: Add SSE broadcasting for real-time timelapse status updates (no HTTP caching needed)
@router.post("/cameras/{camera_id}/stop-timelapse", response_model=Dict[str, Any])
@handle_exceptions("stop timelapse")
async def stop_timelapse(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Stop the active timelapse for a camera."""

    # Delegate entirely to the service layer
    result = await camera_service.stop_active_timelapse(camera_id)
    return result


# TODO: Add SSE broadcasting for real-time timelapse status updates (no HTTP caching needed)
@router.post("/cameras/{camera_id}/complete-timelapse", response_model=Dict[str, Any])
@handle_exceptions("complete timelapse")
async def complete_timelapse(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Complete the active timelapse for a camera, marking it as a historical record."""

    # Delegate entirely to the service layer
    result = await camera_service.complete_active_timelapse(camera_id)
    return result


# ✅ IMPLEMENTED: ETag + 3 minute cache for composite camera details data
# ETag based on camera.updated_at + timelapse.updated_at + latest_image.captured_at
@router.get("/cameras/{camera_id}/details", response_model=CameraDetailsResponse)
@handle_exceptions("get camera details")
async def get_camera_details(
    response: Response,
    camera_service: CameraServiceDep,
    timelapse_service: TimelapseServiceDep,
    video_service: VideoServiceDep,
    image_service: ImageServiceDep,
    log_service: LogServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """
    CAMERA DETAILS - Single endpoint for camera detail page

    Replaces 6 separate API calls with one comprehensive response containing:
    - Camera with latest image
    - Active timelapse (if any)
    - All timelapses for this camera
    - Recent images (last 10)
    - Videos for this camera
    - Recent activity/logs (last 10)
    - Comprehensive statistics
    """
    logger.info(f"Starting camera details for camera {camera_id}")

    # Get camera data first to ensure it exists
    try:
        camera_data = await camera_service.get_camera_by_id(camera_id)
        if not camera_data:
            raise HTTPException(status_code=404, detail=CAMERA_NOT_FOUND)
        logger.info(f"Camera data retrieved: {camera_data.id}")
    except Exception as e:
        logger.error(f"Failed to get camera by ID: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get camera: {str(e)}")

    # Get camera with image for the response
    try:
        cameras_with_images = await camera_service.get_cameras_with_images()
        camera_with_image = next(
            (c for c in cameras_with_images if c.id == camera_id), None
        )

        if not camera_with_image:
            raise HTTPException(status_code=404, detail=CAMERA_NOT_FOUND)

        logger.info(
            f"Camera with image found: {camera_with_image.id}, timelapse_id: {camera_with_image.timelapse_id}"
        )
    except Exception as e:
        logger.error(f"Failed to get camera with images: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get camera data: {str(e)}"
        )

    # Get additional data using proper service methods that return models
    # Use individual try-catch instead of asyncio.gather to isolate failures
    timelapses_data = []
    videos_data = []
    recent_images_data = []
    logs_data = []

    # Try each operation individually with error handling
    try:
        timelapses_data = await timelapse_service.get_timelapses_for_camera(camera_id)
    except Exception as e:
        logger.error(f"Failed to get timelapses for camera {camera_id}: {e}")
        timelapses_data = []

    try:
        if camera_with_image.timelapse_id:
            videos_data = await video_service.get_videos(
                timelapse_id=camera_with_image.timelapse_id
            )
        else:
            videos_data = await video_service.get_videos()
    except Exception as e:
        logger.error(f"Failed to get videos for camera {camera_id}: {e}")
        videos_data = []

    try:
        recent_images_data = await image_service.get_images_for_camera(
            camera_id, limit=10
        )
    except Exception as e:
        logger.error(f"Failed to get recent images for camera {camera_id}: {e}")
        recent_images_data = []

    try:
        logs_data = await log_service.get_logs_for_camera(camera_id, limit=10)
    except Exception as e:
        logger.error(f"Failed to get logs for camera {camera_id}: {e}")
        logs_data = []

    # Handle stats properly - create default if not available
    camera_stats = (
        camera_data.stats
        if camera_data.stats
        else CameraStats(
            total_images=0,
            last_24h_images=0,
            success_rate_percent=0.0,
            storage_used_mb=0.0,
            avg_capture_interval_minutes=None,
            current_timelapse_images=0,
            current_timelapse_name=None,
            total_videos=0,
            timelapse_count=0,
            days_since_first_capture=None,
        )
    )

    response_data = CameraDetailsResponse(
        camera=camera_with_image,  # Already proper model
        stats=camera_stats,  # Properly typed CameraStats
        timelapses=timelapses_data,  # Already proper models from service
        videos=videos_data,  # Already proper models from service
        recent_images=recent_images_data,  # Already proper models from service
        recent_activity=logs_data,  # Already proper models from service
    )

    # Generate composite ETag based on camera updated_at + latest image + timelapse updates
    etag_components = [str(camera_data.updated_at.timestamp())]
    if camera_with_image.last_image:
        etag_components.append(
            str(camera_with_image.last_image.captured_at.timestamp())
        )
    if timelapses_data:
        latest_timelapse_update = max(
            (t.updated_at for t in timelapses_data), default=camera_data.updated_at
        )
        etag_components.append(str(latest_timelapse_update.timestamp()))

    # Use content hash ETag since we have composite data
    from ..utils.cache_manager import generate_content_hash_etag

    etag = generate_content_hash_etag(
        {"camera_id": camera_id, "components": etag_components}
    )

    # Add cache headers for composite data that changes occasionally
    response.headers["Cache-Control"] = "public, max-age=180, s-maxage=180"  # 3 minutes
    response.headers["ETag"] = etag

    return response_data


# ✅ IMPLEMENTED: Improved ETag strategy using collection of camera timestamps
# Current cache headers are good (15 seconds) for dashboard data
@router.get("/cameras", response_model=List[CameraWithLastImage])
@handle_exceptions("get cameras")
async def get_cameras(response: Response, camera_service: CameraServiceDep):
    """Get all cameras with their latest image"""

    cameras = await camera_service.get_cameras_with_images()

    # Generate ETag based on all camera updated_at timestamps
    if cameras:
        camera_timestamps = [str(camera.updated_at.timestamp()) for camera in cameras]
        etag = generate_content_hash_etag({"cameras": camera_timestamps})
    else:
        etag = '"empty-cameras-list"'

    # Add cache headers for dashboard data
    response.headers["Cache-Control"] = "public, max-age=15, s-maxage=15"  # 15 seconds
    response.headers["ETag"] = etag

    return cameras  # Service returns proper models


# ✅ IMPLEMENTED: ETag + 5 minute cache for individual camera data
# ETag = f'"{camera.updated_at.timestamp()}"'
@router.get("/cameras/{camera_id}", response_model=CameraWithStats)
@handle_exceptions("get camera")
async def get_camera(
    response: Response,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Get a specific camera by ID"""

    # Get camera data from service
    camera = await camera_service.get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=CAMERA_NOT_FOUND)

    # Generate ETag based on camera updated_at timestamp
    etag = generate_timestamp_etag(camera)

    # Add cache headers for camera data that changes occasionally
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return camera  # Service returns proper model


# TODO: Good SSE broadcasting - no HTTP caching needed for POST operations
@router.post("/cameras", response_model=Camera)
@handle_exceptions("create camera")
async def create_camera(
    camera: CameraCreate,
    camera_service: CameraServiceDep,
    settings_service: SettingsServiceDep,
):
    """Create a new camera with timezone-aware timestamp"""

    # Get timezone-aware timestamp for audit trail
    current_timestamp = await get_timezone_aware_timestamp_async(settings_service)

    # Delegate to service - no business logic in router
    new_camera = await camera_service.create_camera(camera)

    # SSE broadcasting handled by service layer (proper architecture)

    return new_camera


# TODO: Good SSE broadcasting - no HTTP caching needed for PUT operations
@router.put("/cameras/{camera_id}", response_model=Camera)
@handle_exceptions("update camera")
async def update_camera(
    camera: CameraUpdate,
    camera_service: CameraServiceDep,
    settings_service: SettingsServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Update an existing camera"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    # Get timezone-aware timestamp for audit trail
    current_timestamp = await get_timezone_aware_timestamp_async(settings_service)

    # Delegate to service
    updated_camera = await camera_service.update_camera(camera_id, camera)

    # SSE broadcasting handled by service layer (proper architecture)

    return updated_camera


# TODO: Good SSE broadcasting - no HTTP caching needed for DELETE operations
@router.delete("/cameras/{camera_id}")
@handle_exceptions("delete camera")
async def delete_camera(
    camera_service: CameraServiceDep,
    settings_service: SettingsServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Delete a camera"""

    # Get camera info before deletion for SSE event
    camera_to_delete = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "camera"
    )

    success = await camera_service.delete_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to delete camera",
        )

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(CAMERA_DELETED_SUCCESS)


# TODO: Replace with SSE - status changes frequently and users need real-time updates
# Remove HTTP caching, use SSE events instead
@router.get("/cameras/{camera_id}/status")
@handle_exceptions("get camera status")
async def get_camera_status(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Get camera status"""

    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "camera"
    )

    status_data = {
        "camera_id": camera_id,
        "status": camera.status,
        "health_status": camera.health_status,
    }

    return ResponseFormatter.success(
        "Camera status retrieved successfully", data=status_data
    )


# TODO: Good SSE broadcasting - no HTTP caching needed for status updates
@router.put("/cameras/{camera_id}/status")
@handle_exceptions("update camera status")
async def update_camera_status(
    status_data: str,
    camera_service: CameraServiceDep,
    settings_service: SettingsServiceDep,
    error_message: Optional[str] = None,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Update camera status"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    success = await camera_service.update_camera_status(
        camera_id, status_data, error_message
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to update camera status",
        )

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(CAMERA_STATUS_UPDATED_SUCCESS)


# TODO: Replace with SSE - health changes frequently and is critical for monitoring
# Remove HTTP caching, use SSE events instead
@router.get("/cameras/{camera_id}/health", response_model=Optional[CameraHealthStatus])
@handle_exceptions("get camera health")
async def get_camera_health(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Get camera health metrics"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    health_status = await camera_service.get_camera_health_status(camera_id)
    return health_status


# TODO: No caching needed - connection tests should always run fresh
@router.post(
    "/cameras/{camera_id}/test-connection", response_model=CameraConnectivityTestResult
)
@handle_exceptions("test camera connection")
async def test_camera_connection(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> CameraConnectivityTestResult:
    """Test RTSP connection for a camera"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    # Get connectivity test result from service
    result = await camera_service.test_connectivity(camera_id)
    return result  # Return Pydantic model directly


# TODO: Good SSE broadcasting - no HTTP caching needed for manual capture triggers
@router.post(
    "/cameras/{camera_id}/capture-now", response_model=CameraCaptureWorkflowResult
)
@handle_exceptions("trigger manual capture")
async def trigger_manual_capture(
    camera_service: CameraServiceDep,
    settings_service: SettingsServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> CameraCaptureWorkflowResult:
    """Trigger manual image capture for a camera"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    # Get timezone-aware timestamp for capture
    capture_timestamp = await get_timezone_aware_timestamp_async(settings_service)

    try:
        result = await camera_service.coordinate_capture_workflow(camera_id)

        # SSE broadcasting handled by service layer (proper architecture)

        return result  # Return Pydantic model directly
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{CAMERA_CAPTURE_FAILED}: {str(e)}",
        )


# ✅ IMPLEMENTED: Short cache (2 minutes) for connectivity status
# Cache-Control: private, max-age=120
@router.get(
    "/cameras/{camera_id}/connectivity", response_model=CameraConnectivityTestResult
)
@handle_exceptions("get camera connectivity status")
async def get_camera_connectivity_status(
    response: Response,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> CameraConnectivityTestResult:
    """Get camera connectivity status and history"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    # Get connectivity result from service
    connectivity_result = await camera_service.test_connectivity(camera_id)

    # Add cache headers since connectivity doesn't change frequently
    response.headers["Cache-Control"] = (
        "private, max-age=120, s-maxage=120"  # 2 minutes
    )

    return connectivity_result


# ✅ IMPLEMENTED: 30-second cache for latest image metadata with proper ETag
# Consider SSE updates when new images are captured instead
@router.get("/cameras/{camera_id}/images/latest")
@handle_exceptions("get camera latest image")
async def get_camera_latest_image(
    response: Response,
    image_service: ImageServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Get the latest image for a camera with timezone-aware timestamps"""

    # Add cache headers to prevent API flooding
    response.headers["Cache-Control"] = "public, max-age=30, s-maxage=30"
    response.headers["ETag"] = f"latest-{camera_id}"

    # Validate camera exists (through image service)
    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_IMAGES_FOUND
        )

    return latest_image


# ===== NEW UNIFIED LATEST-IMAGE ENDPOINTS =====


# ✅ IMPLEMENTED: 30-second cache for latest image metadata with improved ETag strategy
# Consider SSE updates when new images are captured for real-time updates
@router.get(
    "/cameras/{camera_id}/latest-image", response_model=CameraLatestImageResponse
)
@handle_exceptions("get camera latest image metadata")
async def get_camera_latest_image_unified(
    response: Response,
    image_service: ImageServiceDep,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> CameraLatestImageResponse:
    """Get complete metadata + URLs for latest camera image (UNIFIED ENDPOINT)"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    # Get latest image
    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_IMAGES_FOUND
        )

    # Generate ETag based on image ID and captured timestamp
    etag = generate_composite_etag(latest_image.id, latest_image.captured_at)

    # Add cache headers to prevent API flooding with improved ETag
    response.headers["Cache-Control"] = "public, max-age=30, s-maxage=30"  # 30 seconds
    response.headers["ETag"] = etag
    response.headers["X-RateLimit-WindowMs"] = "30000"
    response.headers["X-RateLimit-Max"] = "1"

    # Build URLs for image variants
    urls = CameraLatestImageUrls(
        full=f"/api/cameras/{camera_id}/latest-image/full",
        small=f"/api/cameras/{camera_id}/latest-image/small",
        thumbnail=f"/api/cameras/{camera_id}/latest-image/thumbnail",
        download=f"/api/cameras/{camera_id}/latest-image/download",
    )

    # Build metadata about variants
    metadata = CameraLatestImageMetadata(
        camera_id=camera_id,
        has_thumbnail=bool(getattr(latest_image, "thumbnail_path", None)),
        has_small=bool(getattr(latest_image, "small_path", None)),
        thumbnail_size=getattr(latest_image, "thumbnail_size", None),
        small_size=getattr(latest_image, "small_size", None),
    )

    # Build core image data
    image_data = CameraLatestImageData(
        image_id=latest_image.id,
        captured_at=latest_image.captured_at.isoformat(),
        day_number=latest_image.day_number,
        timelapse_id=latest_image.timelapse_id,
        file_size=latest_image.file_size,
        corruption_score=latest_image.corruption_score,
        is_flagged=latest_image.is_flagged,
        urls=urls,
        metadata=metadata,
    )

    # Return proper Pydantic model
    return CameraLatestImageResponse(
        success=True,
        message="Latest image metadata retrieved successfully",
        data=image_data,
    )


# ✅ IMPLEMENTED: Improved ETag strategy using image.id + image.captured_at 
# Current 5-minute cache is reasonable for latest thumbnails
@router.get("/cameras/{camera_id}/latest-image/thumbnail")
@handle_exceptions("serve camera latest image thumbnail")
async def serve_camera_latest_image_thumbnail(
    request: Request,
    response: Response,
    image_service: ImageServiceDep,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Serve latest image thumbnail for a camera (200×150 optimized for dashboard)"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_IMAGES_FOUND
        )

    # Generate ETag based on image ID and captured timestamp for cache validation
    etag = generate_composite_etag(latest_image.id, latest_image.captured_at)
    
    # Check If-None-Match header for 304 Not Modified
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and validate_etag_match(if_none_match, etag):
        response.status_code = status.HTTP_304_NOT_MODIFIED
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    # Add aggressive caching for thumbnails with proper ETag
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return await image_service.serve_image_file(
        latest_image.id, size_variant="thumbnail"
    )


# IMPLEMENTED: ETag strategy improved - now uses image.id + image.captured_at for proper cache validation
# Current 5-minute cache is reasonable for latest images
@router.get("/cameras/{camera_id}/latest-image/small")
@handle_exceptions("serve camera latest image small")
async def serve_camera_latest_image_small(
    request: Request,
    response: Response,
    image_service: ImageServiceDep,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Serve latest image small variant for a camera (800×600 medium quality)"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_IMAGES_FOUND
        )

    # Generate ETag based on image ID and captured timestamp for better cache validation
    etag = generate_composite_etag(latest_image.id, latest_image.captured_at)
    
    # Check If-None-Match header for 304 Not Modified
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and validate_etag_match(if_none_match, etag):
        response.status_code = status.HTTP_304_NOT_MODIFIED
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    # Add caching for small images with improved ETag
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return await image_service.serve_image_file(latest_image.id, size_variant="small")


# IMPLEMENTED: ETag strategy improved - now uses image.id + image.captured_at for proper cache validation
# Current 1-minute cache is good for full resolution latest images
@router.get("/cameras/{camera_id}/latest-image/full")
@handle_exceptions("serve camera latest image full")
async def serve_camera_latest_image_full(
    request: Request,
    response: Response,
    image_service: ImageServiceDep,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Serve latest image full resolution for a camera"""

    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_IMAGES_FOUND
        )

    # Generate ETag based on image ID and captured timestamp for cache validation
    etag = generate_composite_etag(latest_image.id, latest_image.captured_at)
    
    # Check If-None-Match header for 304 Not Modified
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and validate_etag_match(if_none_match, etag):
        response.status_code = status.HTTP_304_NOT_MODIFIED
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=60, s-maxage=60"  # 1 minute
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    # Add caching for full images with proper ETag
    response.headers["Cache-Control"] = "public, max-age=60, s-maxage=60"  # 1 minute
    response.headers["ETag"] = etag

    return await image_service.serve_image_file(latest_image.id, size_variant="full")


# IMPLEMENTED: ETag based on image.id + image.captured_at for proper cache validation
# Downloads can be cached briefly since they're the same file
@router.get("/cameras/{camera_id}/latest-image/download")
@handle_exceptions("download camera latest image")
async def download_camera_latest_image(
    response: Response,
    image_service: ImageServiceDep,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """Download latest image with proper filename for a camera"""

    # Validate camera exists
    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "Camera"
    )

    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_IMAGES_FOUND
        )

    # Generate ETag based on image ID and captured timestamp for cache validation
    etag = generate_composite_etag(latest_image.id, latest_image.captured_at)

    # Add caching for downloads with proper ETag
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    # Use the existing serve_image_file but with download disposition
    # Get the file serving data
    serving_data = await image_service.prepare_image_for_serving(
        latest_image.id, "full"
    )
    if not serving_data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=serving_data.get("error", "Image file not found"),
        )

    file_path = serving_data["file_path"]

    # Create clean filename with camera name and timestamp
    timestamp = latest_image.captured_at.strftime("%Y%m%d_%H%M%S")
    filename = clean_filename(
        f"{camera.name}_day{latest_image.day_number}_{timestamp}.jpg"
    )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=serving_data.get("media_type", "image/jpeg"),
    )


# IMPLEMENTED: ETag + 15 minute cache (statistics change slowly)
# ETag based on camera image count + last image captured_at
@router.get("/cameras/{camera_id}/statistics", response_model=ImageStatisticsResponse)
@handle_exceptions("get camera image statistics")
async def get_camera_image_statistics(
    response: Response,
    image_service: ImageServiceDep,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
):
    """
    Get comprehensive image statistics for a camera.

    Moved from /images/camera/{camera_id}/statistics to better REST architecture.
    Includes total image counts, corruption statistics, file size metrics,
    and quality assessment data.
    """
    # Validate camera exists
    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "Camera"
    )

    stats = await image_service.calculate_image_statistics(camera_id=camera_id)
    if not stats or "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found or no images available",
        )

    # Generate ETag based on camera's last update and image count
    etag = generate_composite_etag(
        camera.id, camera.updated_at, stats.get("total_images", 0)
    )

    # Add longer cache for statistics (they change slowly)
    response.headers["Cache-Control"] = (
        "public, max-age=900, s-maxage=900"  # 15 minutes
    )
    response.headers["ETag"] = etag

    return ImageStatisticsResponse(
        message="Camera image statistics retrieved successfully",
        data=stats,
        camera_id=camera_id,
    )
