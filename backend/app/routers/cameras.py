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


@router.post("/", response_model=Camera)
async def create_camera(camera_data: CameraCreate):
    """Create a new camera"""
    try:
        camera_id = await async_db.create_camera(camera_data.model_dump())
        if not camera_id:
            raise HTTPException(status_code=500, detail="Failed to create camera")

        # Fetch the created camera
        camera = await async_db.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(
                status_code=500, detail="Camera created but could not be retrieved"
            )

        logger.info(f"Created camera {camera_id}: {camera_data.name}")
        return camera
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to create camera")


@router.put("/{camera_id}", response_model=Camera)
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

        # Fetch updated camera
        updated_camera = await async_db.get_camera_by_id(camera_id)
        if not updated_camera:
            raise HTTPException(
                status_code=500, detail="Camera updated but could not be retrieved"
            )

        logger.info(f"Updated camera {camera_id}")
        return updated_camera
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
    try:
        # Get the latest image for this camera using the LATERAL join approach
        image_data = await async_db.get_latest_image_for_camera(camera_id)

        if not image_data:
            raise HTTPException(
                status_code=404, detail="No images captured yet for this camera"
            )

        # Get the image file path
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

            return Response(
                content=image_data_bytes,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
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
        logger.error(f"Error fetching latest capture for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch latest capture")


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


@router.get("/{camera_id}/timelapse-stats", response_model=dict)
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
