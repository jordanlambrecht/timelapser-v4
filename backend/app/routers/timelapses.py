# backend/app/routers/timelapses.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from loguru import logger

from ..database import async_db
from ..models import Timelapse, TimelapseCreate, TimelapseUpdate, TimelapseWithDetails
from ..video_calculations import preview_video_calculation, VideoGenerationSettings

router = APIRouter()


@router.get("/", response_model=List[TimelapseWithDetails])
async def get_timelapses(
    camera_id: Optional[int] = Query(None, description="Filter by camera ID")
):
    """Get all timelapses, optionally filtered by camera"""
    try:
        timelapses = await async_db.get_timelapses(camera_id=camera_id)
        return timelapses
    except Exception as e:
        logger.error(f"Error fetching timelapses: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch timelapses")


# NEW ENTITY-BASED ENDPOINTS

@router.post("/new", response_model=dict)
async def create_new_timelapse(timelapse_data: TimelapseCreate):
    """Create a new timelapse entity (entity-based model)"""
    try:
        # Build config from timelapse_data
        config = {
            "name": timelapse_data.name,
            "auto_stop_at": timelapse_data.auto_stop_at,
            "time_window_start": timelapse_data.time_window_start,
            "time_window_end": timelapse_data.time_window_end,
            "use_custom_time_window": timelapse_data.use_custom_time_window
        }

        timelapse_id = await async_db.create_new_timelapse(
            timelapse_data.camera_id, config
        )
        if not timelapse_id:
            raise HTTPException(
                status_code=500, detail="Failed to create new timelapse"
            )

        # Broadcast status change event
        async_db.notify_timelapse_status_changed(
            timelapse_data.camera_id, timelapse_id, "running"
        )

        logger.info(
            f"Created new timelapse {timelapse_id} for camera {timelapse_data.camera_id}"
        )
        return {"timelapse_id": timelapse_id, "status": "running"}
    except Exception as e:
        logger.error(f"Error creating new timelapse: {e}")
        raise HTTPException(status_code=500, detail="Failed to create new timelapse")


@router.put("/{timelapse_id}/status", response_model=dict)
async def update_timelapse_status_by_id(timelapse_id: int, update_data: TimelapseUpdate):
    """Update status of a specific timelapse (entity-based model)"""
    try:
        if not update_data.status:
            raise HTTPException(status_code=400, detail="Status is required")

        success = await async_db.update_timelapse_status(
            timelapse_id, update_data.status
        )
        if not success:
            raise HTTPException(status_code=404, detail="Timelapse not found")

        logger.info(
            f"Updated timelapse {timelapse_id} status to {update_data.status}"
        )
        return {"timelapse_id": timelapse_id, "status": update_data.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating timelapse {timelapse_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update timelapse")


@router.post("/{timelapse_id}/complete", response_model=dict)
async def complete_timelapse(timelapse_id: int, camera_id: int):
    """Complete a timelapse and clear active status (entity-based model)"""
    try:
        success = await async_db.complete_timelapse(camera_id, timelapse_id)
        if not success:
            raise HTTPException(status_code=404, detail="Timelapse not found")

        # Broadcast status change event
        async_db.notify_timelapse_status_changed(
            camera_id, timelapse_id, "completed"
        )

        logger.info(f"Completed timelapse {timelapse_id} for camera {camera_id}")
        return {"timelapse_id": timelapse_id, "status": "completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing timelapse {timelapse_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete timelapse")


# LEGACY ENDPOINTS (for backward compatibility)

@router.post("/", response_model=dict)
async def create_or_update_timelapse(timelapse_data: TimelapseCreate):
    """Create or update a timelapse for a camera (LEGACY - use /new for entity-based model)"""
    try:
        # Extract config from timelapse_data if provided
        config = None
        if (timelapse_data.name or timelapse_data.auto_stop_at or 
            timelapse_data.time_window_start or timelapse_data.use_custom_time_window):
            config = {
                "name": timelapse_data.name,
                "auto_stop_at": timelapse_data.auto_stop_at,
                "time_window_start": timelapse_data.time_window_start,
                "time_window_end": timelapse_data.time_window_end,
                "use_custom_time_window": timelapse_data.use_custom_time_window
            }

        timelapse_id = await async_db.create_or_update_timelapse(
            timelapse_data.camera_id, timelapse_data.status, config
        )
        if not timelapse_id:
            raise HTTPException(
                status_code=500, detail="Failed to create/update timelapse"
            )

        # Broadcast status change event
        async_db.notify_timelapse_status_changed(
            timelapse_data.camera_id, timelapse_id, timelapse_data.status
        )

        logger.info(
            f"Created/updated timelapse {timelapse_id} for camera {timelapse_data.camera_id} with status {timelapse_data.status}"
        )
        return {"timelapse_id": timelapse_id, "status": timelapse_data.status}
    except Exception as e:
        logger.error(f"Error creating/updating timelapse: {e}")
        raise HTTPException(status_code=500, detail="Failed to create/update timelapse")


@router.put("/{camera_id}", response_model=dict)
async def update_timelapse_status(camera_id: int, update_data: TimelapseUpdate):
    """Update timelapse status for a camera (LEGACY - use /{timelapse_id}/status for entity-based model)"""
    try:
        if not update_data.status:
            raise HTTPException(status_code=400, detail="Status is required")

        timelapse_id = await async_db.create_or_update_timelapse(
            camera_id, update_data.status, None  # No config for simple status updates
        )
        if not timelapse_id:
            raise HTTPException(status_code=500, detail="Failed to update timelapse")

        # Broadcast status change event
        async_db.notify_timelapse_status_changed(
            camera_id, timelapse_id, update_data.status
        )

        logger.info(
            f"Updated timelapse status for camera {camera_id} to {update_data.status}"
        )
        return {"timelapse_id": timelapse_id, "status": update_data.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating timelapse for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update timelapse")


@router.get("/{timelapse_id}/video-settings", response_model=dict)
async def get_timelapse_video_settings(timelapse_id: int):
    """Get video generation settings for a timelapse (with camera defaults as fallback)"""
    try:
        # Get timelapse details to find camera_id
        timelapses = await async_db.get_timelapses()
        timelapse = next((t for t in timelapses if t["id"] == timelapse_id), None)
        
        if not timelapse:
            raise HTTPException(status_code=404, detail="Timelapse not found")

        camera_id = timelapse["camera_id"]
        
        # Get effective settings
        settings = await async_db.get_effective_video_settings(camera_id, timelapse_id)
        
        return {
            "timelapse_id": timelapse_id,
            "camera_id": camera_id,
            "settings": settings
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching video settings for timelapse {timelapse_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch video settings")


@router.patch("/{timelapse_id}/video-settings", response_model=dict)
async def update_timelapse_video_settings(timelapse_id: int, settings: dict):
    """Update video generation settings for a timelapse"""
    try:
        # Validate timelapse exists
        timelapses = await async_db.get_timelapses()
        timelapse = next((t for t in timelapses if t["id"] == timelapse_id), None)
        
        if not timelapse:
            raise HTTPException(status_code=404, detail="Timelapse not found")

        # Update settings
        success = await async_db.update_timelapse_video_settings(timelapse_id, settings)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update video settings")

        logger.info(f"Updated video settings for timelapse {timelapse_id}")
        return {
            "timelapse_id": timelapse_id,
            "message": "Video settings updated successfully"
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating video settings for timelapse {timelapse_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update video settings")


@router.post("/{timelapse_id}/copy-camera-settings", response_model=dict)
async def copy_camera_video_settings_to_timelapse(timelapse_id: int):
    """Copy video generation settings from camera to timelapse (reset to defaults)"""
    try:
        # Get timelapse details to find camera_id
        timelapses = await async_db.get_timelapses()
        timelapse = next((t for t in timelapses if t["id"] == timelapse_id), None)
        
        if not timelapse:
            raise HTTPException(status_code=404, detail="Timelapse not found")

        camera_id = timelapse["camera_id"]
        
        # Copy settings from camera
        success = await async_db.copy_camera_video_settings_to_timelapse(camera_id, timelapse_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to copy camera settings")

        logger.info(f"Copied camera video settings to timelapse {timelapse_id}")
        return {
            "timelapse_id": timelapse_id,
            "camera_id": camera_id,
            "message": "Camera video settings copied successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying camera settings to timelapse {timelapse_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to copy camera settings")


@router.post("/{timelapse_id}/video-preview", response_model=dict)
async def preview_timelapse_video_generation(timelapse_id: int, settings: dict = None):
    """Preview video generation calculation for a timelapse"""
    try:
        # Get timelapse details to find camera_id and image count
        timelapses = await async_db.get_timelapses()
        timelapse = next((t for t in timelapses if t["id"] == timelapse_id), None)
        
        if not timelapse:
            raise HTTPException(status_code=404, detail="Timelapse not found")

        camera_id = timelapse["camera_id"]
        
        # Get images for this timelapse
        images = await async_db.get_timelapse_images(timelapse_id)
        total_images = len(images)

        # Use provided settings or get effective settings
        if settings:
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
        else:
            # Get effective settings for this timelapse
            effective_settings = await async_db.get_effective_video_settings(camera_id, timelapse_id)
            video_settings = VideoGenerationSettings(
                video_generation_mode=effective_settings.get("video_generation_mode", "standard"),
                standard_fps=effective_settings.get("standard_fps", 12),
                enable_time_limits=effective_settings.get("enable_time_limits", False),
                min_time_seconds=effective_settings.get("min_time_seconds"),
                max_time_seconds=effective_settings.get("max_time_seconds"),
                target_time_seconds=effective_settings.get("target_time_seconds"),
                fps_bounds_min=effective_settings.get("fps_bounds_min", 1),
                fps_bounds_max=effective_settings.get("fps_bounds_max", 60)
            )

        # Generate preview
        preview = preview_video_calculation(total_images, video_settings)
        
        return {
            "timelapse_id": timelapse_id,
            "camera_id": camera_id,
            "preview": preview
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating video preview for timelapse {timelapse_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate video preview")
