# backend/app/routers/camera_routers.py
import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import ValidationError

from ..database import async_db
from ..models import Camera, CameraCreate, CameraUpdate
from ..models.camera_model import (
    CameraWithLastImage,
    CameraWithStats,
    CameraDetailsResponse,
    LogForCamera,
    ImageForCamera,
)
from ..models.shared_models import CameraHealthStatus, CameraStatistics
from ..services.camera_service import CameraService
from ..services.timelapse_service import TimelapseService
from ..services.video_service import VideoService
from ..services.image_service import ImageService
from ..services.log_service import LogService
from ..services.video_calculation_service import (
    preview_video_calculation,
    VideoGenerationSettings,
)

router = APIRouter()

# Use composition-based database instance
camera_service = CameraService(async_db)
timelapse_service = TimelapseService(async_db)
video_service = VideoService(async_db)
image_service = ImageService(async_db)
log_service = LogService(async_db)


@router.get("/{camera_id}/details", response_model=CameraDetailsResponse)
async def get_camera_details(camera_id: int):
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
    try:
        # Get camera with proper model from service
        camera_data = await camera_service.get_camera_by_id(camera_id)
        
        if not camera_data:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        # Get camera with image for the response
        cameras_with_images = await camera_service.get_cameras_with_images()
        camera_with_image = next(
            (c for c in cameras_with_images if c.id == camera_id), 
            None
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
            video_service.get_videos(timelapse_id=camera_with_image.timelapse_id) if camera_with_image.timelapse_id else video_service.get_videos(),
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

    except Exception as e:
        logger.error(f"Error getting camera details for {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[CameraWithLastImage])
async def get_cameras():
    """Get all cameras with their latest image"""
    try:
        cameras = await camera_service.get_cameras_with_images()
        return cameras  # No transform needed - service returns proper models
    except Exception as e:
        logger.error(f"Error getting cameras: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{camera_id}", response_model=CameraWithStats)
async def get_camera(camera_id: int):
    """Get a specific camera by ID"""
    try:
        camera = await camera_service.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        return camera  # No transform needed - service returns proper model
    except Exception as e:
        logger.error(f"Error getting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Camera)
async def create_camera(camera: CameraCreate):
    """Create a new camera"""
    try:
        camera_data = camera.model_dump()
        new_camera = await camera_service.create_camera(camera_data)
        return new_camera
    except Exception as e:
        logger.error(f"Error creating camera: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{camera_id}", response_model=Camera)
async def update_camera(camera_id: int, camera: CameraUpdate):
    """Update an existing camera"""
    try:
        camera_data = camera.model_dump(exclude_unset=True)
        updated_camera = await camera_service.update_camera(camera_id, camera_data)
        return updated_camera
    except Exception as e:
        logger.error(f"Error updating camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{camera_id}")
async def delete_camera(camera_id: int):
    """Delete a camera"""
    try:
        success = await camera_service.delete_camera(camera_id)
        if not success:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        return {"message": "Camera deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{camera_id}/status")
async def update_camera_status(
    camera_id: int, 
    status: str, 
    error_message: Optional[str] = None
):
    """Update camera status"""
    try:
        success = await camera_service.update_camera_status(camera_id, status, error_message)
        if not success:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        return {"message": "Camera status updated successfully"}
    except Exception as e:
        logger.error(f"Error updating camera status {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{camera_id}/health", response_model=Optional[CameraHealthStatus])
async def get_camera_health(camera_id: int):
    """Get camera health metrics"""
    try:
        health_status = await camera_service.get_camera_health_status(camera_id)
        if health_status is None:
            raise HTTPException(status_code=404, detail="Camera not found")
        return health_status
    except Exception as e:
        logger.error(f"Error getting camera health {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{camera_id}/health")
async def update_camera_health(camera_id: int, health_data: dict):
    """Update camera health metrics"""
    try:
        success = await camera_service.update_camera_health(camera_id, health_data)
        if not success:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        return {"message": "Camera health updated successfully"}
    except Exception as e:
        logger.error(f"Error updating camera health {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
