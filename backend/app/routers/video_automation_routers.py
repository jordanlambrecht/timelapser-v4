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
from ..models.shared_models import (
    VideoAutomationMode,
    VideoGenerationMode,
    VideoGenerationSettingsOptional,
    VideoAutomationSettingsOptional,
    GenerationSchedule,
    MilestoneConfig,
)

from ..dependencies import (
    VideoAutomationServiceDep,
    CameraServiceDep,
    TimelapseServiceDep,
)
from ..database import async_db
from ..models.video_model import VideoGenerationJob
from ..models.camera_model import CameraUpdate
from ..models.timelapse_model import TimelapseUpdate

# Router and validation helpers
from ..utils.router_helpers import (
    handle_exceptions,
    create_success_response,
    validate_entity_exists,
)

# Video settings business logic
from ..utils.video_helpers import VideoSettingsHelper

# Response formatting
from ..utils.response_helpers import ResponseFormatter

from ..utils.timezone_utils import get_timezone_aware_timestamp_async, utc_now
from ..constants import (
    HEALTH_STATUSES,
    VIDEO_GENERATION_MODES,
    MIN_FPS,
    MAX_FPS,
    DEFAULT_FPS,
)

router = APIRouter(prefix="/video-automation", tags=["video-automation"])


# Use shared models for settings responses and updates
class CameraAutomationSettings(
    VideoAutomationSettingsOptional, VideoGenerationSettingsOptional
):
    camera_id: int


class TimelapseAutomationSettings(
    VideoAutomationSettingsOptional, VideoGenerationSettingsOptional
):
    timelapse_id: int


class AutomationSettingsUpdate(
    VideoAutomationSettingsOptional, VideoGenerationSettingsOptional
):
    pass


# Use VideoGenerationJobWithDetails as the response model for job queue endpoints
from ..models.shared_models import VideoGenerationJobWithDetails


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


@router.get("/queue", response_model=List[VideoGenerationJobWithDetails])
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
            VideoGenerationJobWithDetails(
                id=job.id,
                timelapse_id=job.timelapse_id,
                trigger_type=job.trigger_type,
                status=job.status,
                # priority field removed; not present in model
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


@router.get("/camera/{camera_id}/settings", response_model=CameraAutomationSettings)
@handle_exceptions("get camera automation settings")
async def get_camera_automation_settings(
    camera_id: int, camera_service: CameraServiceDep
):
    """Get automation settings for a camera"""
    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "camera"
    )

    # Use VideoSettingsHelper for settings inheritance if needed (here just pass camera settings)
    effective_settings = VideoSettingsHelper.get_effective_video_settings(
        timelapse_settings=None, camera_settings=camera
    )

    return CameraAutomationSettings(
        camera_id=camera_id,
        **{
            k: effective_settings.get(k)
            for k in CameraAutomationSettings.model_fields
            if k != "camera_id"
        },
    )


@router.put("/camera/{camera_id}/settings")
@handle_exceptions("update camera automation settings")
async def update_camera_automation_settings(
    camera_id: int, settings: AutomationSettingsUpdate, camera_service: CameraServiceDep
):
    """Update automation settings for a camera"""
    # Verify camera exists
    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, camera_id, "camera"
    )

    update_data = settings.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        return ResponseFormatter.success("No settings to update", camera_id=camera_id)

    # Validate settings using VideoSettingsHelper
    is_valid, error = VideoSettingsHelper.validate_video_settings(update_data)
    if not is_valid:
        return ResponseFormatter.error(
            f"Invalid settings: {error}", error_code="invalid_settings"
        )

    try:
        camera_update = CameraUpdate(**update_data)
        updated_camera = await camera_service.update_camera(camera_id, camera_update)
        return ResponseFormatter.success(
            "Camera automation settings updated successfully",
            camera_id=camera_id,
            updated_fields=list(update_data.keys()),
        )
    except Exception as e:
        logger.error(f"Failed to update camera {camera_id} automation settings: {e}")
        return ResponseFormatter.error(
            "Failed to update automation settings", error_code="update_failed"
        )


@router.get(
    "/timelapse/{timelapse_id}/settings", response_model=TimelapseAutomationSettings
)
@handle_exceptions("get timelapse automation settings")
async def get_timelapse_automation_settings(
    timelapse_id: int, timelapse_service: TimelapseServiceDep
):
    """Get automation settings for a timelapse (including inherited camera settings)"""
    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    # Inherit settings: timelapse overrides camera
    camera_id = getattr(timelapse, "camera_id", None)
    camera = None
    if (
        camera_id is not None
        and hasattr(timelapse_service, "camera_service")
        and timelapse_service.camera_service
    ):
        camera = await timelapse_service.camera_service.get_camera_by_id(camera_id)
    effective_settings = VideoSettingsHelper.get_effective_video_settings(
        timelapse_settings=timelapse, camera_settings=camera
    )

    return TimelapseAutomationSettings(
        timelapse_id=timelapse_id,
        **{
            k: effective_settings.get(k)
            for k in TimelapseAutomationSettings.model_fields
            if k != "timelapse_id"
        },
    )


@router.put("/timelapse/{timelapse_id}/settings")
@handle_exceptions("update timelapse automation settings")
async def update_timelapse_automation_settings(
    timelapse_id: int,
    settings: AutomationSettingsUpdate,
    timelapse_service: TimelapseServiceDep,
):
    """Update automation settings for a timelapse"""
    # Verify timelapse exists
    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    update_data = settings.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        return ResponseFormatter.success(
            "No settings to update", timelapse_id=timelapse_id
        )

    # Validate settings using VideoSettingsHelper
    is_valid, error = VideoSettingsHelper.validate_video_settings(update_data)
    if not is_valid:
        return ResponseFormatter.error(
            f"Invalid settings: {error}", error_code="invalid_settings"
        )

    try:
        timelapse_update = TimelapseUpdate(**update_data)
        updated_timelapse = await timelapse_service.update_timelapse(
            timelapse_id, timelapse_update
        )
        return ResponseFormatter.success(
            "Timelapse automation settings updated successfully",
            timelapse_id=timelapse_id,
            updated_fields=list(update_data.keys()),
        )
    except Exception as e:
        logger.error(
            f"Failed to update timelapse {timelapse_id} automation settings: {e}"
        )
        return ResponseFormatter.error(
            "Failed to update automation settings", error_code="update_failed"
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
# TODO: job cancellation will be needed in the future, it should be implemented in the VideoQueue class first


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

        # Use HEALTH_STATUSES for status values
        health_status = HEALTH_STATUSES[0]  # 'healthy'
        if total_jobs > 0:
            failure_rate = failed_jobs / total_jobs
            if failure_rate > 0.5:
                health_status = HEALTH_STATUSES[1]  # 'degraded'
            elif failure_rate > 0.8:
                health_status = HEALTH_STATUSES[2]  # 'unhealthy'

        if processing_jobs > automation_stats.get("max_concurrent", 3):
            health_status = "overloaded"  # Not in HEALTH_STATUSES, but used for clarity

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
