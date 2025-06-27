# backend/app/routers/video_automation_routers.py
"""
Video Automation API Router

Provides endpoints for managing automated video generation:
- Camera and timelapse automation configuration
- Video generation job queue management
- Manual trigger endpoints
- Automation statistics and monitoring

Follows AI-CONTEXT patterns:
- Settings inheritance (camera defaults → timelapse overrides)
- Timezone-aware scheduling
- SSE event broadcasting
- Proper error handling
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger
from pydantic import BaseModel, Field

from ..dependencies import (
    VideoAutomationServiceDep,
    CameraServiceDep,
    TimelapseServiceDep,
)
from ..database import async_db
from ..models.video_model import VideoGenerationJob
from ..models.camera_model import CameraUpdate
from ..models.timelapse_model import TimelapseUpdate
from ..utils.router_helpers import handle_exceptions, create_success_response
from ..utils.timezone_utils import get_timezone_aware_timestamp_async, utc_now

router = APIRouter(prefix="/video-automation", tags=["video-automation"])


class VideoGenerationJobResponse(BaseModel):
    """Response model for video generation job"""

    id: int
    timelapse_id: int
    trigger_type: Optional[str] = None
    status: str
    priority: Optional[str] = None
    created_at: str  # ISO format string
    settings: Optional[Dict[str, Any]] = None
    camera_name: Optional[str] = None
    timelapse_name: Optional[str] = None


class AutomationSettingsUpdate(BaseModel):
    """Model for updating automation settings"""

    video_automation_mode: Optional[str] = Field(
        None, description="Automation mode: manual, per_capture, scheduled, milestone"
    )
    generation_schedule: Optional[Dict[str, Any]] = Field(
        None, description="Schedule configuration for scheduled mode"
    )
    milestone_config: Optional[Dict[str, Any]] = Field(
        None, description="Milestone configuration for milestone mode"
    )
    video_generation_mode: Optional[str] = Field(
        None, description="Video generation mode: standard, target"
    )
    standard_fps: Optional[int] = Field(
        None, ge=1, le=120, description="Standard FPS for video generation"
    )
    enable_time_limits: Optional[bool] = Field(
        None, description="Enable time limit constraints"
    )
    min_time_seconds: Optional[int] = Field(
        None, ge=1, description="Minimum video duration in seconds"
    )
    max_time_seconds: Optional[int] = Field(
        None, ge=1, description="Maximum video duration in seconds"
    )
    target_time_seconds: Optional[int] = Field(
        None, ge=1, description="Target video duration in seconds"
    )
    fps_bounds_min: Optional[int] = Field(
        None, ge=1, le=120, description="Minimum FPS bound"
    )
    fps_bounds_max: Optional[int] = Field(
        None, ge=1, le=120, description="Maximum FPS bound"
    )


class ManualGenerationRequest(BaseModel):
    """Model for manual video generation request"""

    timelapse_id: int = Field(
        ..., description="ID of the timelapse to generate video from"
    )
    video_name: Optional[str] = Field(None, description="Optional custom video name")
    settings: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Custom video generation settings"
    )


async def _run_sync_in_executor(func, *args):
    """Helper to run sync functions in executor with consistent error handling"""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)
    except Exception as e:
        logger.error(f"Error running {func.__name__} in executor: {e}")
        raise


@router.get("/queue", response_model=List[VideoGenerationJobResponse])
@handle_exceptions("get video generation queue")
async def get_video_generation_queue(
    video_automation_service: VideoAutomationServiceDep,
    status: Optional[str] = None,
    limit: Optional[int] = 50,
):
    """Get current video generation job queue"""
    # Use the correct method name from VideoQueue class
    jobs = await _run_sync_in_executor(
        video_automation_service.queue.get_queue_jobs, status, limit
    )

    # Convert to response model format
    response_jobs = []
    for job in jobs:
        response_jobs.append(
            VideoGenerationJobResponse(
                id=job.id,
                timelapse_id=job.timelapse_id,
                trigger_type=job.trigger_type,
                status=job.status,
                priority=getattr(job, "priority", None),
                created_at=job.created_at.isoformat(),
                settings=job.settings,
                camera_name=getattr(job, "camera_name", None),
                timelapse_name=getattr(job, "timelapse_name", None),
            )
        )

    return response_jobs


@router.get("/queue/stats")
@handle_exceptions("get queue statistics")
async def get_queue_stats(video_automation_service: VideoAutomationServiceDep):
    """Get video generation queue statistics"""
    stats = await _run_sync_in_executor(video_automation_service.get_automation_stats)

    # Add timezone-aware timestamp using the imported async_db
    timestamp = await get_timezone_aware_timestamp_async(async_db)

    return {"statistics": stats, "timestamp": timestamp.isoformat()}


@router.post("/generate/manual")
@handle_exceptions("trigger manual video generation")
async def trigger_manual_generation(
    request: ManualGenerationRequest,
    video_automation_service: VideoAutomationServiceDep,
):
    """Manually trigger video generation for a timelapse"""
    try:
        job_id = await _run_sync_in_executor(
            video_automation_service.queue.add_job,
            request.timelapse_id,
            "manual",
            "high",
            request.settings,
        )

        if job_id:
            return create_success_response(
                "Video generation job created successfully",
                job_id=job_id,
                timelapse_id=request.timelapse_id,
                trigger_type="manual",
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to create video generation job"
            )

    except Exception as e:
        logger.error(f"Error creating manual video generation job: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create video generation job: {str(e)}"
        )


@router.get("/camera/{camera_id}/settings")
@handle_exceptions("get camera automation settings")
async def get_camera_automation_settings(
    camera_id: int, camera_service: CameraServiceDep
):
    """Get automation settings for a camera"""
    camera = await camera_service.get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    return {
        "camera_id": camera_id,
        "video_automation_mode": getattr(camera, "video_automation_mode", None),
        "generation_schedule": getattr(camera, "generation_schedule", None),
        "milestone_config": getattr(camera, "milestone_config", None),
        "video_generation_mode": getattr(camera, "video_generation_mode", None),
        "standard_fps": getattr(camera, "standard_fps", None),
        "enable_time_limits": getattr(camera, "enable_time_limits", None),
        "min_time_seconds": getattr(camera, "min_time_seconds", None),
        "max_time_seconds": getattr(camera, "max_time_seconds", None),
        "target_time_seconds": getattr(camera, "target_time_seconds", None),
        "fps_bounds_min": getattr(camera, "fps_bounds_min", None),
        "fps_bounds_max": getattr(camera, "fps_bounds_max", None),
    }


@router.put("/camera/{camera_id}/settings")
@handle_exceptions("update camera automation settings")
async def update_camera_automation_settings(
    camera_id: int, settings: AutomationSettingsUpdate, camera_service: CameraServiceDep
):
    """Update automation settings for a camera"""
    # Verify camera exists
    camera = await camera_service.get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Convert settings to update data, excluding None values
    update_data = settings.model_dump(exclude_unset=True, exclude_none=True)

    if not update_data:
        return create_success_response("No settings to update", camera_id=camera_id)

    # Use the existing camera update method with the converted data
    try:
        camera_update = CameraUpdate(**update_data)
        updated_camera = await camera_service.update_camera(camera_id, camera_update)

        return create_success_response(
            "Camera automation settings updated successfully",
            camera_id=camera_id,
            updated_fields=list(update_data.keys()),
        )
    except Exception as e:
        logger.error(f"Failed to update camera {camera_id} automation settings: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update automation settings"
        )


@router.get("/timelapse/{timelapse_id}/settings")
@handle_exceptions("get timelapse automation settings")
async def get_timelapse_automation_settings(
    timelapse_id: int, timelapse_service: TimelapseServiceDep
):
    """Get automation settings for a timelapse (including inherited camera settings)"""
    timelapse = await timelapse_service.get_timelapse_by_id(timelapse_id)
    if not timelapse:
        raise HTTPException(status_code=404, detail="Timelapse not found")

    return {
        "timelapse_id": timelapse_id,
        "video_automation_mode": getattr(timelapse, "video_automation_mode", None),
        "generation_schedule": getattr(timelapse, "generation_schedule", None),
        "milestone_config": getattr(timelapse, "milestone_config", None),
        "video_generation_mode": getattr(timelapse, "video_generation_mode", None),
        "standard_fps": getattr(timelapse, "standard_fps", None),
        "enable_time_limits": getattr(timelapse, "enable_time_limits", None),
        "min_time_seconds": getattr(timelapse, "min_time_seconds", None),
        "max_time_seconds": getattr(timelapse, "max_time_seconds", None),
        "target_time_seconds": getattr(timelapse, "target_time_seconds", None),
        "fps_bounds_min": getattr(timelapse, "fps_bounds_min", None),
        "fps_bounds_max": getattr(timelapse, "fps_bounds_max", None),
    }


@router.put("/timelapse/{timelapse_id}/settings")
@handle_exceptions("update timelapse automation settings")
async def update_timelapse_automation_settings(
    timelapse_id: int,
    settings: AutomationSettingsUpdate,
    timelapse_service: TimelapseServiceDep,
):
    """Update automation settings for a timelapse"""
    # Verify timelapse exists
    timelapse = await timelapse_service.get_timelapse_by_id(timelapse_id)
    if not timelapse:
        raise HTTPException(status_code=404, detail="Timelapse not found")

    # Convert settings to update data, excluding None values
    update_data = settings.model_dump(exclude_unset=True, exclude_none=True)

    if not update_data:
        return create_success_response(
            "No settings to update", timelapse_id=timelapse_id
        )

    # Use the existing timelapse update method with the converted data
    try:
        timelapse_update = TimelapseUpdate(**update_data)
        updated_timelapse = await timelapse_service.update_timelapse(
            timelapse_id, timelapse_update
        )

        return create_success_response(
            "Timelapse automation settings updated successfully",
            timelapse_id=timelapse_id,
            updated_fields=list(update_data.keys()),
        )
    except Exception as e:
        logger.error(
            f"Failed to update timelapse {timelapse_id} automation settings: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to update automation settings"
        )


@router.get("/statistics")
@handle_exceptions("get automation statistics")
async def get_automation_statistics(
    video_automation_service: VideoAutomationServiceDep,
):
    """Get comprehensive automation statistics"""
    stats = await _run_sync_in_executor(video_automation_service.get_automation_stats)

    # Add timezone-aware timestamp using the imported async_db
    timestamp = await get_timezone_aware_timestamp_async(async_db)

    return {"statistics": stats, "timestamp": timestamp.isoformat()}


@router.post("/process-queue")
@handle_exceptions("process automation queue")
async def process_automation_queue(
    background_tasks: BackgroundTasks,
    video_automation_service: VideoAutomationServiceDep,
):
    """Manually trigger processing of the automation queue"""

    async def run_queue_processing():
        """Background task to process the automation queue"""
        await _run_sync_in_executor(
            video_automation_service.process_automation_triggers
        )

    background_tasks.add_task(run_queue_processing)

    # Fixed: Remove duplicate "message" parameter
    return create_success_response(
        "Queue processing triggered",
        status="started",
        background_task="automation_queue_processing",
    )


# Note: Removed cancel_job and get_job endpoints since these methods don't exist in VideoQueue class
# If job cancellation is needed in the future, it should be implemented in the VideoQueue class first


@router.get("/health")
@handle_exceptions("get automation health")
async def get_automation_health(video_automation_service: VideoAutomationServiceDep):
    """Get automation system health status"""
    try:
        # Get queue status for health check
        queue_stats = await _run_sync_in_executor(
            video_automation_service.queue.get_queue_status
        )

        # Get general automation stats
        automation_stats = await _run_sync_in_executor(
            video_automation_service.get_automation_stats
        )

        # Add timezone-aware timestamp using the imported async_db
        timestamp = await get_timezone_aware_timestamp_async(async_db)

        # Determine health status
        total_jobs = sum(queue_stats.values())
        failed_jobs = queue_stats.get("failed", 0)
        processing_jobs = queue_stats.get("processing", 0)

        health_status = "healthy"
        if total_jobs > 0:
            failure_rate = failed_jobs / total_jobs
            if failure_rate > 0.5:  # More than 50% failure rate
                health_status = "degraded"
            elif failure_rate > 0.8:  # More than 80% failure rate
                health_status = "unhealthy"

        if processing_jobs > automation_stats.get("max_concurrent", 3):
            health_status = "overloaded"

        return {
            "health_status": health_status,
            "queue_stats": queue_stats,
            "automation_stats": automation_stats,
            "checked_at": timestamp.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking automation health: {e}")
        # Fallback timestamp without dependency injection
        return {
            "health_status": "unknown",
            "error": str(e),
            "checked_at": utc_now().isoformat(),
        }
