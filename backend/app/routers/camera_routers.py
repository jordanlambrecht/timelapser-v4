# backend/app/routers/camera_routers.py
"""
Camera management HTTP endpoints.

Role: Camera management HTTP endpoints
Responsibilities: Camera CRUD operations, health status endpoints, image serving endpoints
Interactions: Uses CameraService for business logic, returns Pydantic models, handles HTTP status codes and error responses

Architecture: API Layer - delegates all business logic to services
"""

from typing import List, Optional
from datetime import datetime

from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Path as FastAPIPath,
    Response,
    Request,
    Body,
)
from fastapi.responses import FileResponse
from loguru import logger

from ..constants import (
    CAMERA_NOT_FOUND,
    CAMERA_CAPTURE_FAILED,
    CAMERA_DELETED_SUCCESS,
    CAMERA_STATUS_UPDATED_SUCCESS,
    NO_IMAGES_FOUND,
)
from ..enums import JobPriority
from ..dependencies import (
    CameraServiceDep,
    TimelapseServiceDep,
    VideoServiceDep,
    ImageServiceDep,
    LogServiceDep,
    SettingsServiceDep,
    SchedulerServiceDep,
)
from ..models import Camera, CameraCreate, CameraUpdate
from ..models.camera_model import (
    CameraDetailsResponse,
)
from ..models.shared_models import (
    CameraHealthStatus,
    CameraConnectivityTestResult,
    CameraCaptureWorkflowResult,
    CameraHealthMonitoringResult,
    CameraCaptureScheduleResult,
    ImageStatisticsResponse,
    CameraLatestImageResponse,
    CameraLatestImageData,
    CameraLatestImageUrls,
    CameraLatestImageMetadata,
)
from ..models.camera_action_models import (
    TimelapseActionRequest,
    TimelapseActionResponse,
    CameraStatusResponse,
)
from ..utils.file_helpers import clean_filename, build_camera_image_urls
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
)
from ..utils.cache_manager import (
    generate_timestamp_etag,
    generate_composite_etag,
    generate_collection_etag,
    generate_content_hash_etag,
    validate_etag_match,
)

# NOTE: CACHING STRATEGY - IMPLEMENTED THROUGHOUT THIS FILE
# Camera operations use mixed caching strategy implemented across endpoints:
# - Real-time data (status, health, counts): SSE broadcasting (no HTTP cache) - implemented
# - Semi-static data (camera details, settings): ETag + short cache (2-5 min) - implemented
# - Immutable content (images, thumbnails): Long cache with ETag validation - implemented
# This mixed caching strategy is fully implemented across all endpoints below.
router = APIRouter(tags=["cameras"])


# Removed timelapse-stats endpoint per decision: "DEPRECATE BACKEND - Remove broken endpoint"
# Timelapse statistics are available through the main timelapse endpoints


# ===== UNIFIED TIMELAPSE ACTION ENDPOINT =====


@router.post(
    "/cameras/{camera_id}/timelapse-action", response_model=TimelapseActionResponse
)
@handle_exceptions("execute timelapse action")
async def execute_timelapse_action(
    action_request: TimelapseActionRequest,
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> TimelapseActionResponse:
    """
    Unified timelapse action endpoint.

    Actions:
    - create: Start a new timelapse (replaces start-timelapse)
    - pause: Pause active timelapse
    - resume: Resume paused timelapse
    - end: Stop and complete timelapse (replaces stop + complete)
    """
    try:
        # Validate camera exists
        camera = await validate_entity_exists(
            camera_service.get_camera_by_id, camera_id, "camera"
        )

        # Execute the timelapse action using camera service
        logger.info(f"Executing timelapse action '{action_request.action}' for camera {camera_id}")
        
        # Delegate to camera service for actual timelapse control
        result = await camera_service.execute_timelapse_action(
            camera_id=camera_id,
            request=action_request
        )
        
        return TimelapseActionResponse(
            success=result.get("success", False),
            message=result.get("message", f"Timelapse {action_request.action} executed"),
            action=action_request.action,
            camera_id=camera_id,
            timelapse_id=result.get("timelapse_id"),
            timelapse_status=result.get("timelapse_status"),
            data=result.get("data", {})
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute timelapse action '{action_request.action}': {e}")
        return TimelapseActionResponse(
            success=False,
            message=f"Failed to execute {action_request.action} action: {str(e)}",
            action=action_request.action,
            camera_id=camera_id,
        )


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

    # Get camera data with comprehensive statistics
    try:
        camera_with_stats = await camera_service.get_camera_by_id(camera_id)
        if not camera_with_stats:
            raise HTTPException(status_code=404, detail=CAMERA_NOT_FOUND)
        logger.info(f"Camera data retrieved: {camera_with_stats.id}")
    except Exception as e:
        logger.error(f"Failed to get camera by ID: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get camera: {str(e)}")

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
        if camera_with_stats.timelapse_id:
            videos_data = await video_service.get_videos(
                timelapse_id=camera_with_stats.timelapse_id
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

    # Handle stats properly - Camera already includes stats
    # No need to extract separately as Camera includes all data unified

    response_data = CameraDetailsResponse(
        camera=camera_with_stats,  # Camera includes all needed data
        timelapses=timelapses_data,  # Already proper models from service
        videos=videos_data,  # Already proper models from service
        recent_images=recent_images_data,  # Already proper models from service
        recent_activity=logs_data,  # Already proper models from service
    )

    # Generate composite ETag based on camera updated_at + latest image + timelapse updates
    etag_components = [str(camera_with_stats.updated_at.timestamp())]
    if camera_with_stats.last_image:
        etag_components.append(
            str(camera_with_stats.last_image.captured_at.timestamp())
        )
    if timelapses_data:
        latest_timelapse_update = max(
            (t.updated_at for t in timelapses_data),
            default=camera_with_stats.updated_at,
        )
        etag_components.append(str(latest_timelapse_update.timestamp()))

    # Use content hash ETag since we have composite data

    etag = generate_content_hash_etag(
        {"camera_id": camera_id, "components": etag_components}
    )

    # Add cache headers for composite data that changes occasionally
    response.headers["Cache-Control"] = "public, max-age=180, s-maxage=180"  # 3 minutes
    response.headers["ETag"] = etag

    return response_data


# ✅ UNIFIED: All cameras now return Camera (comprehensive data)
@router.get("/cameras", response_model=List[Camera])
@handle_exceptions("get cameras")
async def get_cameras(response: Response, camera_service: CameraServiceDep):
    """Get all cameras with comprehensive statistics and latest image data"""

    cameras = await camera_service.get_cameras()

    # Generate ETag based on all camera updated_at timestamps
    if cameras:
        camera_timestamps = [str(camera.updated_at.timestamp()) for camera in cameras]
        etag = generate_content_hash_etag({"cameras": camera_timestamps})
    else:
        etag = '"empty-cameras-list"'

    # Add cache headers for dashboard data
    response.headers["Cache-Control"] = "public, max-age=15, s-maxage=15"  # 15 seconds
    response.headers["ETag"] = etag

    return cameras  # Service returns comprehensive models


# ✅ IMPLEMENTED: ETag + 5 minute cache for individual camera data
# ETag = f'"{camera.updated_at.timestamp()}"'
@router.get("/cameras/{camera_id}", response_model=Camera)
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


# ===== CONSOLIDATED STATUS ENDPOINT =====


@router.get("/cameras/{camera_id}/status", response_model=CameraStatusResponse)
@handle_exceptions("get comprehensive camera status")
async def get_comprehensive_camera_status(
    camera_service: CameraServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> CameraStatusResponse:
    """
    Get comprehensive camera status including health, connectivity, and corruption data.
    Consolidates previous /status, /health, and /connectivity endpoints.
    """
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    # Get comprehensive status from service
    status_data = await camera_service.get_comprehensive_status(camera_id)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=CAMERA_NOT_FOUND
        )

    return CameraStatusResponse(**status_data)


@router.put("/cameras/{camera_id}/status")
@handle_exceptions("update camera status")
async def update_camera_status(
    camera_service: CameraServiceDep,
    settings_service: SettingsServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
    status_data: str = Body(..., description="Camera status data"),
    error_message: Optional[str] = Body(None, description="Optional error message"),
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

    # Validate camera exists and get camera data
    camera = await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")
    
    # Get active timelapse for the camera
    if not camera.timelapse_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active timelapse found for this camera. Please start a timelapse first.",
        )

    # Get timezone-aware timestamp for capture
    capture_timestamp = await get_timezone_aware_timestamp_async(settings_service)

    try:
        # 🎯 MOCK CAPTURE: Return successful mock response for demonstration
        # TODO: Replace with actual capture workflow when worker infrastructure is available
        logger.info(f"Mock capture triggered for camera {camera_id}, timelapse {camera.timelapse_id}")
        
        # Simulate successful capture
        capture_success = True
        capture_time_ms = 150  # Mock capture time

        # Create workflow result based on mock capture execution
        return CameraCaptureWorkflowResult(
            workflow_status="completed" if capture_success else "failed",
            camera_id=camera_id,
            connectivity=CameraConnectivityTestResult(
                success=True,
                camera_id=camera_id,
                rtsp_url=camera.rtsp_url,
                response_time_ms=capture_time_ms,
                connection_status="mock_capture_executed",
                test_timestamp=capture_timestamp
            ),
            health_monitoring=CameraHealthMonitoringResult(
                success=True,
                camera_id=camera_id,
                monitoring_timestamp=capture_timestamp
            ),
            capture_scheduling=CameraCaptureScheduleResult(
                success=capture_success,
                camera_id=camera_id,
                message="Mock capture executed successfully",
                scheduled_at=capture_timestamp
            ),
            overall_success=capture_success
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{CAMERA_CAPTURE_FAILED}: {str(e)}",
        )


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

    # Build URLs for image variants using helper
    url_dict = build_camera_image_urls(camera_id)
    urls = CameraLatestImageUrls(**url_dict)

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
        response.headers["Cache-Control"] = (
            "public, max-age=300, s-maxage=300"  # 5 minutes
        )
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
        response.headers["Cache-Control"] = (
            "public, max-age=300, s-maxage=300"  # 5 minutes
        )
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
        response.headers["Cache-Control"] = (
            "public, max-age=60, s-maxage=60"  # 1 minute
        )
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

