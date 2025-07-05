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
- AsyncDatabaseDep for dependency injection
"""

# Standard library imports
from typing import List, Optional, Dict, Any

# Third party imports
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field



# Local application imports
from ..dependencies import (
    AsyncDatabaseDep,
    SettingsServiceDep,
    VideoAutomationServiceDep,
    CameraServiceDep,
    TimelapseServiceDep,
)
from ..models.shared_models import (
    VideoAutomationMode,
    VideoGenerationMode,
    VideoGenerationSettingsOptional,
    VideoAutomationSettingsOptional,
    GenerationSchedule,
    MilestoneConfig,
    VideoGenerationJobWithDetails,
)

from ..models.timelapse_model import TimelapseUpdate

# Router and validation helpers
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
    run_sync_service_method,
)

# Response formatting
from ..utils.response_helpers import ResponseFormatter
from ..database.sse_events_operations import SSEEventsOperations

# Video settings business logic
from ..utils.video_helpers import VideoSettingsHelper

# Timezone utilities for proper time handling
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_string_async,
)

# Constants for consistency
from ..constants import (
    VIDEO_AUTOMATION_MODES,
    VIDEO_GENERATION_MODES,
    VIDEO_JOB_STATUSES,
    VIDEO_JOB_PRIORITIES,
    VIDEO_QUEUE_WARNING_THRESHOLD,
    VIDEO_QUEUE_ERROR_THRESHOLD,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)

# TODO: CACHING STRATEGY - MINIMAL CACHE + SSE
# Video automation is critical operational monitoring requiring real-time updates:
# - Queue/stats: Very short cache (30-60 seconds max) or SSE broadcasting
# - Settings: ETag + 5-10 min cache - configuration changes occasionally
# - Manual triggers: No cache + SSE broadcasting (already implemented)
# Queue monitoring is essential for video generation pipeline management.
router = APIRouter(tags=["video-automation"])


# Request/Response Models
# CameraAutomationSettings removed - camera-level automation deprecated


class TimelapseAutomationSettings(
    VideoAutomationSettingsOptional, VideoGenerationSettingsOptional
):
    """Timelapse automation settings response model"""

    timelapse_id: int


class AutomationSettingsUpdate(
    VideoAutomationSettingsOptional, VideoGenerationSettingsOptional
):
    """Automation settings update request model"""

    pass


class ManualGenerationRequest(BaseModel):
    """Manual video generation request model"""

    timelapse_id: int = Field(
        ..., description="ID of the timelapse to generate video from"
    )
    video_name: Optional[str] = Field(None, description="Optional custom video name")
    priority: Optional[str] = Field(
        "high",
        description=f"Job priority. Must be one of: {', '.join(VIDEO_JOB_PRIORITIES)}",
    )
    settings: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Custom video generation settings"
    )


class QueueStatsResponse(BaseModel):
    """Video generation queue statistics response model"""

    total_jobs: int
    pending_jobs: int
    processing_jobs: int
    completed_jobs: int
    failed_jobs: int
    queue_health: str
    timestamp: str


# API Endpoints

@router.get(
    "/video-automation/queue", response_model=List[VideoGenerationJobWithDetails]
)
@handle_exceptions("get video generation queue")
async def get_video_generation_queue(
    video_automation_service: VideoAutomationServiceDep,
    db: AsyncDatabaseDep,
    status: Optional[str] = None,
    limit: Optional[int] = DEFAULT_PAGE_SIZE,
):
    """
    Get current video generation job queue

    Args:
        status: Optional filter by job status
        limit: Maximum number of jobs to return
    """
    # Validate status if provided
    if status and status not in VIDEO_JOB_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VIDEO_JOB_STATUSES)}",
        )

    # Validate limit
    if limit and (limit < 1 or limit > MAX_PAGE_SIZE):
        raise HTTPException(
            status_code=400, detail=f"Limit must be between 1 and {MAX_PAGE_SIZE}"
        )

    try:
        # Use async service call with executor
        jobs = await run_sync_service_method(
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
                    created_at=job.created_at.isoformat(),
                    settings=job.settings or {},
                    camera_name=getattr(job, "camera_name", None),
                    timelapse_name=getattr(job, "timelapse_name", None),
                )
            )

        return response_jobs

    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        raise HTTPException(
            status_code=500, detail="Failed to fetch video generation queue"
        )




@router.get("/video-automation/queue/stats", response_model=QueueStatsResponse)
@handle_exceptions("get queue statistics")
async def get_queue_stats(
    video_automation_service: VideoAutomationServiceDep,
    db: AsyncDatabaseDep,
):
    """Get video generation queue statistics"""
    try:
        # Get queue statistics
        stats = await run_sync_service_method(
            video_automation_service.get_automation_stats
        )

        # Add timezone-aware timestamp
        timestamp = await get_timezone_aware_timestamp_async(db)

        # Determine queue health
        total_jobs = stats.get("total_jobs", 0)
        pending_jobs = stats.get("pending_jobs", 0)

        if pending_jobs >= VIDEO_QUEUE_ERROR_THRESHOLD:
            queue_health = "unhealthy"
        elif pending_jobs >= VIDEO_QUEUE_WARNING_THRESHOLD:
            queue_health = "degraded"
        else:
            queue_health = "healthy"

        return QueueStatsResponse(
            total_jobs=total_jobs,
            pending_jobs=pending_jobs,
            processing_jobs=stats.get("processing_jobs", 0),
            completed_jobs=stats.get("completed_jobs", 0),
            failed_jobs=stats.get("failed_jobs", 0),
            queue_health=queue_health,
            timestamp=timestamp.isoformat(),
        )

    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        raise HTTPException(status_code=500, detail="Failed to fetch queue statistics")




@router.post("/video-automation/generate/manual")
@handle_exceptions("trigger manual video generation")
async def trigger_manual_generation(
    request: ManualGenerationRequest,
    video_automation_service: VideoAutomationServiceDep,
    timelapse_service: TimelapseServiceDep,
    settings_service: SettingsServiceDep,
    db: AsyncDatabaseDep,
):
    """Manually trigger video generation for a timelapse"""
    # Validate timelapse exists
    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, request.timelapse_id, "timelapse"
    )

    # Validate priority if provided
    if request.priority and request.priority not in VIDEO_JOB_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority. Must be one of: {', '.join(VIDEO_JOB_PRIORITIES)}",
        )

    try:
        # Create video generation job using the queue
        job_id = await run_sync_service_method(
            video_automation_service.queue.add_job,
            request.timelapse_id,
            "manual",
            request.priority or "high",
            request.settings,
        )

        # Create SSE event for real-time updates
        sse_ops = SSEEventsOperations(db)
        await sse_ops.create_event(
            event_type="video_generation_job_created",
            event_data={
                "job_id": job_id,
                "timelapse_id": request.timelapse_id,
                "trigger_type": "manual",
                "priority": request.priority or "high",
                "video_name": request.video_name,
            },
            priority="normal",
            source="api"
        )

        return ResponseFormatter.success(
            "Video generation job created successfully",
            data={
                "job_id": job_id,
                "timelapse_id": request.timelapse_id,
                "trigger_type": "manual",
                "video_name": request.video_name,
            },
        )

    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        raise HTTPException(
            status_code=500, detail=f"Failed to create video generation job: {str(e)}"
        )


# Camera-level automation settings removed per architecture decision:
# Automation settings should only exist at timelapse level for cleaner design


@router.get(
    "/video-automation/timelapse/{timelapse_id}/settings",
    response_model=TimelapseAutomationSettings,
)
@handle_exceptions("get timelapse automation settings")
async def get_timelapse_automation_settings(
    timelapse_id: int,
    timelapse_service: TimelapseServiceDep,
    camera_service: CameraServiceDep,
):
    """Get automation settings for a timelapse (including inherited camera settings)"""
    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    # Convert Pydantic model to dict for VideoSettingsHelper
    timelapse_dict = timelapse.model_dump()

    # Get camera settings for inheritance
    camera = None
    if timelapse.camera_id:
        try:
            camera = await camera_service.get_camera_by_id(timelapse.camera_id)
        except Exception as e:
            # Could not fetch camera for inheritance - continue without it
            # Router layer should not do direct logging
            pass

    # Convert camera to dict if found
    camera_dict = camera.model_dump() if camera else None

    # Apply settings inheritance
    effective_settings = VideoSettingsHelper.get_effective_video_settings(
        timelapse_settings=timelapse_dict, camera_settings=camera_dict
    )

    return TimelapseAutomationSettings(
        timelapse_id=timelapse_id,
        **{
            k: effective_settings.get(k) or getattr(timelapse, k, None)
            for k in TimelapseAutomationSettings.model_fields
            if k != "timelapse_id"
        },
    )


@router.put("/video-automation/timelapse/{timelapse_id}/settings")
@handle_exceptions("update timelapse automation settings")
async def update_timelapse_automation_settings(
    timelapse_id: int,
    settings: AutomationSettingsUpdate,
    timelapse_service: TimelapseServiceDep,
    db: AsyncDatabaseDep,
):
    """Update automation settings for a timelapse"""
    # Verify timelapse exists
    timelapse = await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    update_data = settings.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        return ResponseFormatter.success(
            "No settings to update", data={"timelapse_id": timelapse_id}
        )

    # Validate automation modes using constants
    if "video_automation_mode" in update_data:
        if update_data["video_automation_mode"] not in VIDEO_AUTOMATION_MODES:
            return ResponseFormatter.error(
                f"Invalid automation mode. Must be one of: {', '.join(VIDEO_AUTOMATION_MODES)}",
                error_code="invalid_automation_mode",
            )

    if "video_generation_mode" in update_data:
        if update_data["video_generation_mode"] not in VIDEO_GENERATION_MODES:
            return ResponseFormatter.error(
                f"Invalid generation mode. Must be one of: {', '.join(VIDEO_GENERATION_MODES)}",
                error_code="invalid_generation_mode",
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

        # Create SSE event for real-time updates
        sse_ops = SSEEventsOperations(db)
        await sse_ops.create_event(
            event_type="timelapse_automation_settings_updated",
            event_data={
                "timelapse_id": timelapse_id,
                "updated_fields": list(update_data.keys()),
                "settings": update_data,
            },
            priority="normal",
            source="api"
        )

        return ResponseFormatter.success(
            "Timelapse automation settings updated successfully",
            data={
                "timelapse_id": timelapse_id,
                "updated_fields": list(update_data.keys()),
            },
        )

    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        return ResponseFormatter.error(
            "Failed to update automation settings", error_code="update_failed"
        )
