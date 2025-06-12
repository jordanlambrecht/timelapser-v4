from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from loguru import logger

from ..database import async_db
from ..models import Timelapse, TimelapseCreate, TimelapseUpdate, TimelapseWithDetails

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


@router.post("/", response_model=dict)
async def create_or_update_timelapse(timelapse_data: TimelapseCreate):
    """Create or update a timelapse for a camera"""
    try:
        timelapse_id = await async_db.create_or_update_timelapse(
            timelapse_data.camera_id, timelapse_data.status
        )
        if not timelapse_id:
            raise HTTPException(
                status_code=500, detail="Failed to create/update timelapse"
            )

        logger.info(
            f"Created/updated timelapse {timelapse_id} for camera {timelapse_data.camera_id}"
        )
        return {"timelapse_id": timelapse_id, "status": timelapse_data.status}
    except Exception as e:
        logger.error(f"Error creating/updating timelapse: {e}")
        raise HTTPException(status_code=500, detail="Failed to create/update timelapse")


@router.put("/{camera_id}", response_model=dict)
async def update_timelapse_status(camera_id: int, update_data: TimelapseUpdate):
    """Update timelapse status for a camera"""
    try:
        if not update_data.status:
            raise HTTPException(status_code=400, detail="Status is required")

        timelapse_id = await async_db.create_or_update_timelapse(
            camera_id, update_data.status
        )
        if not timelapse_id:
            raise HTTPException(status_code=500, detail="Failed to update timelapse")

        logger.info(
            f"Updated timelapse status for camera {camera_id} to {update_data.status}"
        )
        return {"timelapse_id": timelapse_id, "status": update_data.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating timelapse for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update timelapse")
