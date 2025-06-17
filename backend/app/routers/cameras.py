# backend/app/routers/cameras.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, Response
from typing import List
from pathlib import Path
import os
from datetime import datetime
from loguru import logger

from ..database import async_db
from ..models import Camera, CameraCreate, CameraUpdate
from ..models.camera import (
    CameraWithLastImage,
    CameraWithStats,
    transform_camera_with_image_row,
    transform_camera_with_stats_row,
)
from ..video_calculations import preview_video_calculation, VideoGenerationSettings

router = APIRouter()


@router.get("/", response_model=List[CameraWithLastImage])
async def get_cameras():
    """Get all cameras with their last captured image data"""
    try:
        cameras = await async_db.get_cameras_with_images()
        return [transform_camera_with_image_row(camera) for camera in cameras]
    except Exception as e:
        logger.error(f"Error fetching cameras: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cameras")


@router.get("/{camera_id}", response_model=CameraWithLastImage)
async def get_camera(camera_id: int):
    """Get a specific camera by ID with its last captured image data"""
    try:
        camera = await async_db.get_camera_with_images_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        return transform_camera_with_image_row(camera)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch camera")


@router.post("/", response_model=CameraWithLastImage)
async def create_camera(camera_data: CameraCreate):
    """Create a new camera"""
    try:
        camera_id = await async_db.create_camera(camera_data.model_dump())
        if not camera_id:
            raise HTTPException(status_code=500, detail="Failed to create camera")

        # Fetch the created camera with images
        camera = await async_db.get_camera_with_images_by_id(camera_id)
        if not camera:
            raise HTTPException(
                status_code=500, detail="Camera created but could not be retrieved"
            )

        logger.info(f"Created camera {camera_id}: {camera_data.name}")
        return transform_camera_with_image_row(camera)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to create camera")


@router.put("/{camera_id}", response_model=CameraWithLastImage)
async def update_camera(camera_id: int, camera_data: CameraUpdate):
    """Update a camera"""
    try:
        # Check if camera exists
        existing_camera = await async_db.get_camera_by_id(camera_id)
        if not existing_camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Update camera
        success = await async_db.update_camera(
            camera_id, camera_data.model_dump(exclude_unset=True)
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update camera")

        # Fetch updated camera with images
        updated_camera = await async_db.get_camera_with_images_by_id(camera_id)
        if not updated_camera:
            raise HTTPException(
                status_code=500, detail="Camera updated but could not be retrieved"
            )

        logger.info(f"Updated camera {camera_id}")
        return transform_camera_with_image_row(updated_camera)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update camera")


@router.delete("/{camera_id}")
async def delete_camera(camera_id: int):
    """Delete a camera"""
    try:
        # Check if camera exists
        existing_camera = await async_db.get_camera_by_id(camera_id)
        if not existing_camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Delete camera
        success = await async_db.delete_camera(camera_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete camera")

        logger.info(f"Deleted camera {camera_id}: {existing_camera['name']}")
        return {"message": "Camera deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete camera")


@router.get("/{camera_id}/latest-capture")
async def get_latest_capture(camera_id: int):
    """Get the latest captured image for a camera"""
    return await _serve_camera_image(camera_id, "full")


@router.get("/{camera_id}/latest-thumbnail") 
async def get_latest_thumbnail(camera_id: int):
    """Get the latest thumbnail image for a camera"""
    return await _serve_camera_image(camera_id, "thumbnail")


@router.get("/{camera_id}/latest-small")
async def get_latest_small(camera_id: int):
    """Get the latest small image for a camera"""
    return await _serve_camera_image(camera_id, "small")


async def _serve_camera_image(camera_id: int, size: str = "full"):
    """Serve camera image in specified size (full, thumbnail, small)"""
    try:
        # Get the latest image for this camera using the LATERAL join approach
        image_data = await async_db.get_latest_image_for_camera(camera_id)

        if not image_data:
            raise HTTPException(
                status_code=404, detail="No images captured yet for this camera"
            )

        # Select the appropriate file path based on size
        if size == "thumbnail":
            file_path = image_data.get("thumbnail_path")
            if not file_path:
                # Fall back to full image if thumbnail not available
                file_path = image_data["file_path"]
                logger.debug(f"No thumbnail available for camera {camera_id}, serving full image")
        elif size == "small":
            file_path = image_data.get("small_path")
            if not file_path:
                # Fall back to full image if small not available
                file_path = image_data["file_path"]
                logger.debug(f"No small image available for camera {camera_id}, serving full image")
        else:
            # Default to full image
            file_path = image_data["file_path"]

        # Get project root regardless of path type for logging purposes
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        )

        # Handle both absolute and relative paths
        if not file_path.startswith("/"):
            # Relative path, make it absolute relative to project root
            # Go up three levels from backend/app/routers to reach project root
            full_path = os.path.join(project_root, file_path)
        else:
            full_path = file_path

        # Check if file exists
        if not os.path.exists(full_path):
            logger.error(f"Image file not found at calculated path: {full_path}")
            logger.error(f"Original relative path: {file_path}")
            logger.error(f"Project root calculated as: {project_root}")
            raise HTTPException(status_code=404, detail="Image file not found")

        # Read and return the image file
        try:
            with open(full_path, "rb") as f:
                image_data_bytes = f.read()

            # Format the Last-Modified header properly
            last_modified = ""
            if image_data.get("captured_at"):
                captured_at = image_data["captured_at"]
                if isinstance(captured_at, datetime):
                    # Format datetime as HTTP date string
                    last_modified = captured_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
                else:
                    # If it's already a string, use it directly
                    last_modified = str(captured_at)

            # Set cache control based on image size - thumbnails can be cached longer
            if size in ["thumbnail", "small"]:
                cache_control = "public, max-age=300"  # 5 minute cache for thumbnails
            else:
                cache_control = "no-cache, no-store, must-revalidate"  # No cache for full images

            return Response(
                content=image_data_bytes,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": cache_control,
                    "Pragma": "no-cache" if size == "full" else "public",
                    "Expires": "0" if size == "full" else "",
                    "Last-Modified": last_modified,
                    "Content-Length": str(len(image_data_bytes)),
                },
            )
        except Exception as file_error:
            logger.error(f"Error reading image file {file_path}: {file_error}")
            raise HTTPException(status_code=500, detail="Error reading image file")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest {size} image for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch latest {size} image")


@router.get("/stats/", response_model=List[CameraWithStats])
async def get_cameras_with_stats():
    """Get all cameras with their statistics and image details"""
    try:
        cameras_data = await async_db.get_cameras_with_stats()
        return [
            transform_camera_with_stats_row(camera, camera["stats"])
            for camera in cameras_data
        ]
    except Exception as e:
        logger.error(f"Error fetching cameras with stats: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch cameras with stats"
        )


@router.get("/stats/{camera_id}", response_model=CameraWithStats)
async def get_camera_with_stats(camera_id: int):
    """Get a specific camera with its statistics and image details"""
    try:
        camera_data = await async_db.get_camera_with_images_by_id(camera_id)
        if not camera_data:
            raise HTTPException(status_code=404, detail="Camera not found")

        stats = await async_db.get_camera_stats(camera_id)
        return transform_camera_with_stats_row(camera_data, stats)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching camera {camera_id} with stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch camera with stats")


@router.get("/{camera_id}/debug", response_model=dict)
async def debug_camera_transformation(camera_id: int):
    """Debug endpoint to see what's happening during camera transformation"""
    try:
        # Get raw camera data
        raw_camera = await async_db.get_camera_with_images_by_id(camera_id)
        if not raw_camera:
            raise HTTPException(status_code=404, detail="Camera not found")
            
        # Show the transformation steps
        camera_data = {
            k: v
            for k, v in raw_camera.items()
            if not k.startswith("last_image_") and not k.startswith("timelapse_")
        }
        
        # Add timelapse fields manually
        if "timelapse_status" in raw_camera:
            camera_data["timelapse_status"] = raw_camera["timelapse_status"]
        if "timelapse_id" in raw_camera:
            camera_data["timelapse_id"] = raw_camera["timelapse_id"]
            
        return {
            "raw_data": raw_camera,
            "filtered_data": camera_data,
            "has_video_fields": {
                "video_generation_mode": "video_generation_mode" in camera_data,
                "standard_fps": "standard_fps" in camera_data,
                "enable_time_limits": "enable_time_limits" in camera_data,
                "target_time_seconds": "target_time_seconds" in camera_data,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error debugging camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to debug camera")
async def get_camera_timelapse_stats(camera_id: int):
    """Get timelapse statistics for a camera (total vs current timelapse images)"""
    try:
        # Check if camera exists
        camera = await async_db.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Get timelapse statistics
        stats = await async_db.get_camera_timelapse_stats(camera_id)
        
        logger.debug(f"Fetched timelapse stats for camera {camera_id}: {stats}")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching timelapse stats for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch timelapse stats")


@router.post("/{camera_id}/capture-now", response_model=dict)
async def capture_now(camera_id: int):
    """Trigger an immediate capture for a camera"""
    try:
        # Check if camera exists and is online
        camera = await async_db.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        if camera.get("health_status") != "online":
            raise HTTPException(
                status_code=400, 
                detail=f"Camera is {camera.get('health_status', 'unknown')} and cannot capture images"
            )

        # Get active timelapse for this camera
        timelapses = await async_db.get_timelapses(camera_id=camera_id)
        active_timelapse = next((t for t in timelapses if t["status"] == "running"), None)
        
        if not active_timelapse:
            raise HTTPException(
                status_code=400, 
                detail="No active timelapse found for this camera. Start a timelapse first."
            )

        # Broadcast capture request event - the worker will handle the actual capture
        async_db.broadcast_event({
            "type": "capture_now_requested",
            "camera_id": camera_id,
            "timelapse_id": active_timelapse["id"],
            "timestamp": datetime.now().isoformat(),
        })

        logger.info(f"Capture now requested for camera {camera_id}")
        return {
            "message": "Capture request sent",
            "camera_id": camera_id,
            "timelapse_id": active_timelapse["id"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering capture for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger capture")


@router.get("/{camera_id}/video-settings", response_model=dict)
async def get_effective_video_settings(camera_id: int, timelapse_id: int = None):
    """Get effective video generation settings for a camera (with optional timelapse overrides)"""
    try:
        # Check if camera exists
        camera = await async_db.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Get effective settings
        settings = await async_db.get_effective_video_settings(camera_id, timelapse_id)
        
        return {
            "camera_id": camera_id,
            "timelapse_id": timelapse_id,
            "settings": settings
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching video settings for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch video settings")


@router.post("/{camera_id}/video-preview", response_model=dict)
async def preview_video_generation(camera_id: int, settings: dict, timelapse_id: int = None):
    """Preview video generation calculation with given settings and current image count"""
    try:
        # Check if camera exists
        camera = await async_db.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Get total images for calculation
        if timelapse_id:
            # Get images for specific timelapse
            images = await async_db.get_timelapse_images(timelapse_id)
            total_images = len(images)
        else:
            # Get total images for camera
            stats = await async_db.get_camera_timelapse_stats(camera_id)
            total_images = stats.get("total_images", 0)

        # Convert settings dict to VideoGenerationSettings
        video_settings = VideoGenerationSettings(
            video_generation_mode=settings.get("video_generation_mode", "standard"),
            standard_fps=settings.get("standard_fps", 12),
            enable_time_limits=settings.get("enable_time_limits", False),
            min_time_seconds=settings.get("min_time_seconds"),
            max_time_seconds=settings.get("max_time_seconds"),
            target_time_seconds=settings.get("target_time_seconds"),
            fps_bounds_min=settings.get("fps_bounds_min", 1),
            fps_bounds_max=settings.get("fps_bounds_max", 60)
        )

        # Generate preview
        preview = preview_video_calculation(total_images, video_settings)
        
        return {
            "camera_id": camera_id,
            "timelapse_id": timelapse_id,
            "preview": preview
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating video preview for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate video preview")
