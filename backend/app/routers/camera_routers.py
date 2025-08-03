# backend/app/routers/camera_routers.py
"""
Camera management HTTP endpoints.

Role: Camera management HTTP endpoints
Responsibilities: Camera CRUD operations, health status endpoints, image serving endpoints
Interactions: Uses CameraService for business logic, returns Pydantic models, handles HTTP status codes and error responses

Architecture: API Layer - delegates all business logic to services
"""

import asyncio
from typing import List, Optional

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
)
from fastapi import Path as FastAPIPath
from fastapi import (
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse

from ..enums import LoggerName
from ..services.logger import get_service_logger


from ..constants import (
    CAMERA_CAPTURE_FAILED,
    CAMERA_DELETED_SUCCESS,
    CAMERA_NOT_FOUND,
    CAMERA_STATUS_UPDATED_SUCCESS,
    NO_IMAGES_FOUND,
)
from ..dependencies import (
    CameraServiceDep,
    ImageServiceDep,
    SettingsServiceDep,
)
from ..models import Camera, CameraCreate, CameraUpdate
from ..models.camera_action_models import (
    CameraStatusResponse,
    TimelapseActionRequest,
    TimelapseActionResponse,
)

# Removed: CameraDetailsResponse import - no longer needed after endpoint removal
from ..models.shared_models import (
    CameraCaptureScheduleResult,
    CameraCaptureWorkflowResult,
    CameraConnectivityTestResult,
    CameraHealthMonitoringResult,
    CameraLatestImageData,
    CameraLatestImageMetadata,
    CameraLatestImageResponse,
    CameraLatestImageUrls,
)
from ..utils.cache_manager import (
    generate_composite_etag,
    generate_content_hash_etag,
    generate_timestamp_etag,
    validate_etag_match,
)
from ..utils.file_helpers import build_camera_image_urls, clean_filename
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
)
from ..utils.time_utils import (
    format_filename_timestamp,
    get_timezone_aware_timestamp_async,
)

logger = get_service_logger(LoggerName.API)

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
        logger.info(
            f"Executing timelapse action '{action_request.action}' for camera {camera.name} (ID: {camera_id})",
            extra_context={
                "camera_id": camera_id,
                "camera_name": camera.name,
                "action": action_request.action,
                "operation": "execute_timelapse_action",
            },
        )

        # Delegate to camera service for actual timelapse control
        result = await camera_service.execute_timelapse_action(
            camera_id=camera_id, request=action_request
        )

        return TimelapseActionResponse(
            success=result.get("success", False),
            message=result.get(
                "message", f"Timelapse {action_request.action} executed"
            ),
            action=action_request.action,
            camera_id=camera_id,
            timelapse_id=result.get("timelapse_id"),
            timelapse_status=result.get("timelapse_status"),
            data=result.get("data", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to execute timelapse action '{action_request.action}'",
            exception=e,
            extra_context={
                "camera_id": camera_id,
                "action": action_request.action,
                "operation": "execute_timelapse_action",
                "error_type": type(e).__name__,
            },
        )
        return TimelapseActionResponse(
            success=False,
            message=f"Failed to execute {action_request.action} action: {str(e)}",
            action=action_request.action,
            camera_id=camera_id,
        )


# ✅ REMOVED: Deprecated camera details endpoint - replaced by separate lightweight endpoints
# Frontend now uses /cameras/{id} + lazy loading for /timelapses + /videos


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

    success = await camera_service.delete_camera(camera_to_delete.id)
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
    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "camera"
    )

    # Get active timelapse for the camera
    if not camera.timelapse_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active timelapse found for this camera. Please start a timelapse first.",
        )

    # Get timezone-aware timestamp for capture
    capture_timestamp = await get_timezone_aware_timestamp_async(settings_service)

    try:
        # 🎯 REAL CAPTURE: Execute actual capture workflow using WorkflowOrchestratorService
        logger.info(
            f"Real capture triggered for camera {camera_id}, timelapse {camera.timelapse_id}",
            extra_context={
                "camera_id": camera_id,
                "timelapse_id": camera.timelapse_id,
                "camera_name": camera.name,
                "operation": "trigger_manual_capture",
                "capture_type": "manual",
            },
        )

        # Get workflow orchestrator from dependencies
        from ..dependencies import get_workflow_orchestrator_service

        # Get the timelapse ID (we already validated it exists above)
        timelapse_id = camera.timelapse_id
        if not timelapse_id:
            # Fallback to active_timelapse_id if timelapse_id is somehow None
            timelapse_id = camera.active_timelapse_id
            if not timelapse_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No active timelapse ID found for capture",
                )

        # Execute real capture workflow in executor to handle sync service
        def execute_capture():
            workflow_orchestrator = get_workflow_orchestrator_service()
            return workflow_orchestrator.execute_capture_workflow(
                camera_id,
                timelapse_id,
                {"source": "manual_capture", "camera_name": camera.name},
            )

        capture_result = await asyncio.get_event_loop().run_in_executor(
            None, execute_capture
        )

        # Convert RTSPCaptureResult to CameraCaptureWorkflowResult
        return CameraCaptureWorkflowResult(
            workflow_status="completed" if capture_result.success else "failed",
            camera_id=camera_id,
            connectivity=CameraConnectivityTestResult(
                success=capture_result.success,
                camera_id=camera_id,
                rtsp_url=camera.rtsp_url,
                response_time_ms=None,
                connection_status=(
                    "capture_executed" if capture_result.success else "capture_failed"
                ),
                error=capture_result.error if not capture_result.success else None,
                test_timestamp=capture_timestamp,
            ),
            health_monitoring=CameraHealthMonitoringResult(
                success=capture_result.success,
                camera_id=camera_id,
                monitoring_timestamp=capture_timestamp,
                error=capture_result.error if not capture_result.success else None,
            ),
            capture_scheduling=CameraCaptureScheduleResult(
                success=capture_result.success,
                camera_id=camera_id,
                message=capture_result.message
                or (
                    "Real capture executed successfully"
                    if capture_result.success
                    else "Real capture failed"
                ),
                scheduled_at=capture_timestamp,
                error=capture_result.error if not capture_result.success else None,
            ),
            overall_success=capture_result.success,
            error=capture_result.error if not capture_result.success else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{CAMERA_CAPTURE_FAILED}: {str(e)}",
        )


#  DEPRECATED: Removed /cameras/{camera_id}/images/latest endpoint
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
    timestamp = format_filename_timestamp(latest_image.captured_at)
    filename = clean_filename(
        f"{camera.name}_day{latest_image.day_number}_{timestamp}.jpg"
    )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=serving_data.get("media_type", "image/jpeg"),
    )
