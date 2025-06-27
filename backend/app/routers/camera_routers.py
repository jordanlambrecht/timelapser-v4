# backend/app/routers/camera_routers.py
"""
Camera management HTTP endpoints.

Role: Camera management HTTP endpoints
Responsibilities: Camera CRUD operations, health status endpoints, image serving endpoints
Interactions: Uses CameraService for business logic, returns Pydantic models,handles HTTP status codes and error responses
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from ..dependencies import (
    CameraServiceDep,
    TimelapseServiceDep,
    VideoServiceDep,
    ImageServiceDep,
    LogServiceDep,
)
from ..models import Camera, CameraCreate, CameraUpdate
from ..models.camera_model import (
    CameraWithLastImage,
    CameraWithStats,
    CameraDetailsResponse,
)
from ..models.shared_models import CameraHealthStatus
from ..utils.router_helpers import handle_exceptions, create_success_response

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/{camera_id}/details", response_model=CameraDetailsResponse)
@handle_exceptions("get camera details")
async def get_camera_details(
    camera_id: int,
    camera_service: CameraServiceDep,
    timelapse_service: TimelapseServiceDep,
    video_service: VideoServiceDep,
    image_service: ImageServiceDep,
    log_service: LogServiceDep,
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
    # Get camera with proper model from service
    camera_data = await camera_service.get_camera_by_id(camera_id)

    if not camera_data:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Get camera with image for the response
    cameras_with_images = await camera_service.get_cameras_with_images()
    camera_with_image = next(
        (c for c in cameras_with_images if c.id == camera_id), None
    )

    if not camera_with_image:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Get additional data using proper service methods that return models
    (
        timelapses_data,
        videos_data,
        timelapse_stats,
        recent_images_data,
        logs_data,
    ) = await asyncio.gather(
        timelapse_service.get_timelapses_for_camera(camera_id),
        (
            video_service.get_videos(timelapse_id=camera_with_image.timelapse_id)
            if camera_with_image.timelapse_id
            else video_service.get_videos()
        ),
        timelapse_service.get_timelapse_statistics_for_camera(camera_id),
        image_service.get_images_for_camera(camera_id, limit=10),
        log_service.get_logs_for_camera(camera_id, limit=10),
    )

    # Construct the response using the proper models
    response = CameraDetailsResponse(
        camera=camera_with_image,  # Already proper model
        stats=camera_data.stats,  # Already proper CameraStats model
        timelapses=timelapses_data,  # Already proper models from service
        videos=videos_data,  # Already proper models from service
        recent_images=recent_images_data,  # Already proper models from service
        recent_activity=logs_data,  # Already proper models from service
    )

    return response


@router.get("/", response_model=List[CameraWithLastImage])
@handle_exceptions("get cameras")
async def get_cameras(camera_service: CameraServiceDep):
    """Get all cameras with their latest image"""
    cameras = await camera_service.get_cameras_with_images()
    return cameras  # No transform needed - service returns proper models


@router.get("/{camera_id}", response_model=CameraWithStats)
@handle_exceptions("get camera")
async def get_camera(camera_id: int, camera_service: CameraServiceDep):
    """Get a specific camera by ID"""
    camera = await camera_service.get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera  # No transform needed - service returns proper model


@router.post("/", response_model=Camera)
@handle_exceptions("create camera")
async def create_camera(camera: CameraCreate, camera_service: CameraServiceDep):
    """Create a new camera"""
    new_camera = await camera_service.create_camera(camera)
    return new_camera


@router.put("/{camera_id}", response_model=Camera)
@handle_exceptions("update camera")
async def update_camera(
    camera_id: int, camera: CameraUpdate, camera_service: CameraServiceDep
):
    """Update an existing camera"""
    updated_camera = await camera_service.update_camera(camera_id, camera)
    return updated_camera


@router.delete("/{camera_id}")
@handle_exceptions("delete camera")
async def delete_camera(camera_id: int, camera_service: CameraServiceDep):
    """Delete a camera"""
    success = await camera_service.delete_camera(camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="Camera not found")

    return create_success_response("Camera deleted successfully")


@router.put("/{camera_id}/status")
@handle_exceptions("update camera status")
async def update_camera_status(
    camera_id: int,
    status: str,
    camera_service: CameraServiceDep,
    error_message: Optional[str] = None,
):
    """Update camera status"""
    success = await camera_service.update_camera_status(
        camera_id, status, error_message
    )
    if not success:
        raise HTTPException(status_code=404, detail="Camera not found")

    return create_success_response("Camera status updated successfully")


@router.get("/{camera_id}/health", response_model=Optional[CameraHealthStatus])
@handle_exceptions("get camera health")
async def get_camera_health(camera_id: int, camera_service: CameraServiceDep):
    """Get camera health metrics"""
    health_status = await camera_service.get_camera_health_status(camera_id)
    if health_status is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return health_status


@router.put("/{camera_id}/health")
@handle_exceptions("update camera health")
async def update_camera_health(
    camera_id: int, health_data: dict, camera_service: CameraServiceDep
):
    """Update camera health metrics"""
    success = await camera_service.update_camera_health(camera_id, health_data)
    if not success:
        raise HTTPException(status_code=404, detail="Camera not found")

    return create_success_response("Camera health updated successfully")


@router.post("/{camera_id}/test-connection")
@handle_exceptions("test camera connection")
async def test_camera_connection(camera_id: int, camera_service: CameraServiceDep):
    """Test RTSP connection for a camera"""
    result = await camera_service.test_connectivity(camera_id)
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Connection test failed"),
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        }

    return create_success_response("Camera connection successful", data=result)


@router.post("/{camera_id}/capture")
@handle_exceptions("trigger manual capture")
async def trigger_manual_capture(camera_id: int, camera_service: CameraServiceDep):
    """Trigger manual image capture for a camera"""
    # Note: Using coordinate_capture_workflow which exists
    try:
        result = await camera_service.coordinate_capture_workflow(camera_id)
        return create_success_response(
            "Manual capture triggered successfully", result=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Manual capture failed: {str(e)}",
        )


@router.get("/{camera_id}/connectivity")
@handle_exceptions("get camera connectivity status")
async def get_camera_connectivity_status(
    camera_id: int, camera_service: CameraServiceDep
):
    """Get camera connectivity status and history"""
    # Using test_connectivity which exists instead of get_connectivity_status
    try:
        connectivity_result = await camera_service.test_connectivity(camera_id)
        return connectivity_result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connectivity status: {str(e)}",
        )


@router.get("/{camera_id}/images/latest")
@handle_exceptions("get camera latest image")
async def get_camera_latest_image(camera_id: int, image_service: ImageServiceDep):
    """Get the latest image for a camera"""
    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if latest_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No images found for camera"
        )

    return latest_image
