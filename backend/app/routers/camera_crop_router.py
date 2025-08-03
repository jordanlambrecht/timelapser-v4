# backend/app/routers/camera_crop_router.py
"""
Camera Crop/Rotation Router

API endpoints for camera crop, rotation, and aspect ratio settings.
Provides REST interface for crop configuration and testing.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from ..services.logger import get_service_logger
from ..enums import LoggerName

logger = get_service_logger(LoggerName.API)

from ..dependencies import CameraServiceDep, AsyncRTSPServiceDep
from ..models.camera_model import (
    CropRotationSettings,
    CropRotationUpdate,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import handle_exceptions
from ..exceptions import CameraNotFoundError, RTSPConnectionError

router = APIRouter(prefix="/api/cameras", tags=["camera-crop"])


@router.get("/{camera_id}/crop-settings", response_model=Dict[str, Any])
@handle_exceptions("get camera crop settings")
async def get_camera_crop_settings(
    camera_id: int, camera_service: CameraServiceDep
):
    """
    Get crop/rotation settings for a camera.

    Returns the current crop, rotation, and aspect ratio settings,
    or null if no custom settings are configured.
    """
    try:
        settings = await camera_service.get_crop_settings(camera_id)

        if settings is None:
            return ResponseFormatter.success(
                data=None,
                message="No crop/rotation settings configured for this camera",
            )

        return ResponseFormatter.success(
            data=settings.model_dump(),
            message="Crop/rotation settings retrieved successfully",
        )

    except CameraNotFoundError:
        raise HTTPException(status_code=404, detail="Camera not found")


@router.put("/{camera_id}/crop-settings", response_model=Dict[str, Any])
@handle_exceptions("update camera crop settings")
async def update_camera_crop_settings(
    camera_id: int,
    settings_update: CropRotationUpdate,
    camera_service: CameraServiceDep,
):
    """
    Update crop/rotation settings for a camera.

    Creates or updates the crop, rotation, and aspect ratio settings.
    Automatically enables crop/rotation processing when settings are provided.
    """
    try:
        updated_settings = await camera_service.update_crop_settings(
            camera_id, settings_update
        )

        return ResponseFormatter.success(
            data=updated_settings.model_dump(),
            message="Crop/rotation settings updated successfully",
        )

    except CameraNotFoundError:
        raise HTTPException(status_code=404, detail="Camera not found")


@router.delete("/{camera_id}/crop-settings", response_model=Dict[str, Any])
@handle_exceptions("disable camera crop settings")
async def disable_camera_crop_settings(
    camera_id: int, camera_service: CameraServiceDep
):
    """
    Disable crop/rotation settings for a camera.

    Clears all crop/rotation settings and disables processing.
    Camera will return to using original frames without any modifications.
    """
    try:
        success = await camera_service.disable_crop_settings(camera_id)

        return ResponseFormatter.success(
            data={"disabled": success},
            message="Crop/rotation settings disabled successfully",
        )

    except CameraNotFoundError:
        raise HTTPException(status_code=404, detail="Camera not found")


@router.get("/{camera_id}/source-resolution", response_model=Dict[str, Any])
@handle_exceptions("get camera source resolution")
async def get_camera_source_resolution(
    camera_id: int, camera_service: CameraServiceDep
):
    """
    Get the detected source resolution for a camera.

    Returns the original camera resolution before any crop/rotation processing.
    """
    try:
        resolution = await camera_service.get_source_resolution(camera_id)

        if resolution is None:
            return ResponseFormatter.success(
                data=None, message="No source resolution detected for this camera"
            )

        return ResponseFormatter.success(
            data=resolution.model_dump(),
            message="Source resolution retrieved successfully",
        )

    except CameraNotFoundError:
        raise HTTPException(status_code=404, detail="Camera not found")


@router.post("/{camera_id}/detect-resolution", response_model=Dict[str, Any])
@handle_exceptions("detect camera source resolution")
async def detect_camera_source_resolution(
    camera_id: int, 
    camera_service: CameraServiceDep,
    rtsp_service: AsyncRTSPServiceDep
):
    """
    Detect and store the source resolution for a camera.

    Captures a frame from the camera to determine the original resolution
    before any processing. Useful for setting up crop boundaries.
    """
    try:
        # Use RTSPService for capture operation
        resolution = await rtsp_service.detect_source_resolution(camera_id)

        if resolution is None:
            return ResponseFormatter.error(
                message="Failed to detect camera resolution. Check camera connection.",
                status_code=500,
            )

        # Store the resolution using CameraService
        # Note: The RTSPService already handles detection, we may want to store it separately
        
        return ResponseFormatter.success(
            data=resolution.model_dump(),
            message=f"Source resolution detected: {resolution.width}x{resolution.height}",
        )

    except CameraNotFoundError:
        raise HTTPException(status_code=404, detail="Camera not found")
    except RTSPConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to camera for resolution detection",
        )


@router.post("/{camera_id}/test-crop-settings", response_model=Dict[str, Any])
@handle_exceptions("test camera crop settings")
async def test_camera_crop_settings(
    camera_id: int,
    settings: CropRotationSettings,
    rtsp_service: AsyncRTSPServiceDep,
):
    """
    Test crop/rotation settings by processing a live frame.

    Captures a frame from the camera and applies the provided settings
    to show the resulting processed resolution. Useful for validating
    settings before saving them.
    """
    try:
        # Use RTSPService for capture and processing operation
        result = await rtsp_service.test_crop_settings(camera_id, settings)

        if result is None:
            return ResponseFormatter.error(
                message="Failed to test crop settings. Check camera connection.",
                status_code=500,
            )

        width, height = result
        return ResponseFormatter.success(
            data={
                "processed_width": width,
                "processed_height": height,
                "settings_tested": settings.model_dump(),
            },
            message=f"Crop settings test successful: {width}x{height}",
        )

    except CameraNotFoundError:
        raise HTTPException(status_code=404, detail="Camera not found")
    except RTSPConnectionError:
        raise HTTPException(
            status_code=503, detail="Unable to connect to camera for testing"
        )
