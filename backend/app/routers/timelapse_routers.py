# backend/app/routers/timelapse_routers.py
"""
Timelapse entity management HTTP endpoints.

Role: Timelapse entity management HTTP endpoints
Responsibilities: Timelapse lifecycle operations (start/pause/stop/complete), entity CRUD, progress tracking
Interactions: Uses TimelapseService for business logic, broadcasts SSE events for real-time updates
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Path, status, Depends
from loguru import logger

from ..database import async_db
from ..dependencies import TimelapseServiceDep
from ..models.timelapse_model import (
    Timelapse,
    TimelapseCreate,
    TimelapseUpdate,
    TimelapseWithDetails,
)
from ..models.shared_models import TimelapseStatistics
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter
from ..utils.timezone_utils import get_timezone_from_db_async

router = APIRouter(prefix="/timelapses", tags=["timelapses"])


# Helper function to reduce timezone fetching duplication
async def get_current_timezone() -> str:
    """Get current timezone setting from database with caching."""
    return await get_timezone_from_db_async(async_db)


# Pydantic validation for timelapse IDs
def valid_timelapse_id(timelapse_id: int = Path(..., ge=1, description="Timelapse ID")):
    """Validate timelapse ID using Pydantic Path validation."""
    return timelapse_id


@router.post("/", response_model=Timelapse, status_code=status.HTTP_201_CREATED)
@handle_exceptions("create timelapse")
async def create_timelapse(
    timelapse_data: TimelapseCreate,
    camera_id: int = Query(..., ge=1, description="Camera ID to create timelapse for"),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Create a new timelapse for a camera.

    Creates a new timelapse entity with proper timezone-aware timestamps
    and inherits settings from the parent camera.
    """
    # Validate camera_id matches the one in timelapse_data
    if timelapse_data.camera_id != camera_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera ID in URL must match camera ID in request body",
        )

    # Get timezone for proper timestamp handling
    timezone_str = await get_current_timezone()

    try:
        new_timelapse = await timelapse_service.create_new_timelapse(
            camera_id, timelapse_data
        )
        logger.info(
            f"Created timelapse {new_timelapse.id} for camera {camera_id} in timezone {timezone_str}"
        )
        return new_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., camera not found, invalid settings)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create timelapse for camera {camera_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while creating timelapse",
        )


@router.get("/", response_model=List[TimelapseWithDetails])
@handle_exceptions("get timelapses")
async def get_timelapses(
    timelapse_service: TimelapseServiceDep = Depends(),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID", ge=1),
):
    """
    Get timelapses with optional filtering.

    Returns timelapses with timezone-aware timestamps and proper metadata.
    """
    # Get timezone for proper timestamp formatting in logs
    timezone_str = await get_current_timezone()

    try:
        timelapses = await timelapse_service.get_timelapses(camera_id=camera_id)

        logger.debug(f"Retrieved {len(timelapses)} timelapses (camera_id={camera_id})")
        return timelapses

    except Exception as e:
        logger.error(f"Failed to retrieve timelapses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapses",
        )


@router.get("/{timelapse_id}", response_model=TimelapseWithDetails)
@handle_exceptions("get timelapse")
async def get_timelapse(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Get a specific timelapse by ID.

    Returns detailed timelapse information including camera metadata
    and timezone-aware timestamps.
    """
    try:
        timelapse = await timelapse_service.get_timelapse_by_id(timelapse_id)
        if not timelapse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )
        return timelapse

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapse",
        )


@router.put("/{timelapse_id}", response_model=Timelapse)
@handle_exceptions("update timelapse")
async def update_timelapse(
    timelapse_data: TimelapseUpdate,
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Update a timelapse configuration.

    Allows updating of timelapse settings, time windows, and video generation parameters.
    Changes are applied with timezone-aware timestamp tracking.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_current_timezone()

    try:
        updated_timelapse = await timelapse_service.update_timelapse(
            timelapse_id, timelapse_data
        )
        if not updated_timelapse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        logger.info(f"Updated timelapse {timelapse_id} in timezone {timezone_str}")
        return updated_timelapse

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update timelapse",
        )


@router.delete("/{timelapse_id}", status_code=status.HTTP_200_OK)
@handle_exceptions("delete timelapse")
async def delete_timelapse(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Delete a timelapse and all associated data.

    WARNING: This permanently removes the timelapse, its images, and generated videos.
    """
    try:
        success = await timelapse_service.delete_timelapse(timelapse_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        logger.info(f"Deleted timelapse {timelapse_id}")
        return ResponseFormatter.success(
            message=f"Timelapse {timelapse_id} deleted successfully",
            timelapse_id=timelapse_id,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle business logic errors (e.g., cannot delete running timelapse)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete timelapse",
        )


@router.post(
    "/{timelapse_id}/start", response_model=Timelapse, status_code=status.HTTP_200_OK
)
@handle_exceptions("start timelapse")
async def start_timelapse(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Start a timelapse recording session.

    Transitions the timelapse to 'running' status and begins image capture
    according to the configured schedule and time windows.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_current_timezone()

    try:
        updated_timelapse = await timelapse_service.start_timelapse(timelapse_id)
        logger.info(f"Started timelapse {timelapse_id} in timezone {timezone_str}")
        return updated_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse already running, invalid state)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        logger.error(f"Failed to start timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start timelapse",
        )


@router.post(
    "/{timelapse_id}/pause", response_model=Timelapse, status_code=status.HTTP_200_OK
)
@handle_exceptions("pause timelapse")
async def pause_timelapse(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Pause a running timelapse.

    Temporarily stops image capture while preserving the ability to resume.
    The timelapse can be restarted later from where it left off.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_current_timezone()

    try:
        updated_timelapse = await timelapse_service.pause_timelapse(timelapse_id)
        logger.info(f"Paused timelapse {timelapse_id} in timezone {timezone_str}")
        return updated_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse not running)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        logger.error(f"Failed to pause timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause timelapse",
        )


@router.post(
    "/{timelapse_id}/stop", response_model=Timelapse, status_code=status.HTTP_200_OK
)
@handle_exceptions("stop timelapse")
async def stop_timelapse(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Stop a timelapse recording session.

    Stops image capture and transitions to 'stopped' status.
    The timelapse can be resumed or completed from this state.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_current_timezone()

    try:
        updated_timelapse = await timelapse_service.stop_timelapse(timelapse_id)
        logger.info(f"Stopped timelapse {timelapse_id} in timezone {timezone_str}")
        return updated_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse not running)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        logger.error(f"Failed to stop timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop timelapse",
        )


@router.post(
    "/{timelapse_id}/complete", response_model=Timelapse, status_code=status.HTTP_200_OK
)
@handle_exceptions("complete timelapse")
async def complete_timelapse(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Complete a timelapse and mark as finished.

    Marks the timelapse as 'completed', making it a permanent historical record.
    Completed timelapses cannot be resumed but can be used for video generation.
    """
    # Get timezone for proper timestamp handling
    timezone_str = await get_current_timezone()

    try:
        completed_timelapse = await timelapse_service.complete_timelapse(timelapse_id)
        logger.info(f"Completed timelapse {timelapse_id} in timezone {timezone_str}")
        return completed_timelapse

    except ValueError as e:
        # Handle business logic errors (e.g., timelapse already completed)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timelapse with ID {timelapse_id} not found",
        )
    except Exception as e:
        logger.error(f"Failed to complete timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete timelapse",
        )


@router.get("/{timelapse_id}/statistics", response_model=TimelapseStatistics)
@handle_exceptions("get timelapse statistics")
async def get_timelapse_statistics(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Get comprehensive statistics for a specific timelapse.

    Returns capture rates, image counts, duration statistics.
    """
    try:
        stats = await timelapse_service.get_timelapse_statistics(timelapse_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )
        return stats

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to get statistics for timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapse statistics",
        )


@router.get("/{timelapse_id}/progress", response_model=TimelapseWithDetails)
@handle_exceptions("get timelapse progress")
async def get_timelapse_progress(
    timelapse_id: int = Depends(valid_timelapse_id),
    timelapse_service: TimelapseServiceDep = Depends(),
):
    """
    Get real-time progress tracking data for a timelapse.

    Returns current capture status, day progression, time remaining estimates,
    and capture rate analysis with timezone-aware calculations.
    """
    try:
        timelapse = await timelapse_service.get_timelapse_by_id(timelapse_id)
        if not timelapse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Timelapse with ID {timelapse_id} not found",
            )

        # Return the complete timelapse details as progress information
        return timelapse

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to get progress for timelapse {timelapse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timelapse progress",
        )


# NOTE: Additional endpoints like images, video-settings, day-numbers, etc.
# will be added when the corresponding service methods are implemented
