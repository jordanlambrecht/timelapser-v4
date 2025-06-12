from fastapi import APIRouter, HTTPException, Depends
from typing import List
from loguru import logger

from ..database import async_db
from ..models import Camera, CameraCreate, CameraUpdate, CameraWithTimelapse

router = APIRouter()


@router.get("/", response_model=List[CameraWithTimelapse])
async def get_cameras():
    """Get all cameras with timelapse status"""
    try:
        cameras = await async_db.get_cameras()
        return cameras
    except Exception as e:
        logger.error(f"Error fetching cameras: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch cameras")


@router.get("/{camera_id}", response_model=CameraWithTimelapse)
async def get_camera(camera_id: int):
    """Get a specific camera by ID"""
    try:
        camera = await async_db.get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        return camera
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
            raise HTTPException(status_code=500, detail="Camera created but could not be retrieved")
            
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
        success = await async_db.update_camera(camera_id, camera_data.model_dump(exclude_unset=True))
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update camera")
            
        # Fetch updated camera
        updated_camera = await async_db.get_camera_by_id(camera_id)
        if not updated_camera:
            raise HTTPException(status_code=500, detail="Camera updated but could not be retrieved")
            
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
