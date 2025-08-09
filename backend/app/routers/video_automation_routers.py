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
from typing import List, Optional

# Third party imports
from fastapi import APIRouter, HTTPException

from ..constants import (
    DEFAULT_PAGE_SIZE,
    JOB_STATUS_LIST,
    MAX_PAGE_SIZE,
)
# Local application imports
from ..dependencies import (
    AsyncDatabaseDep,
    CameraServiceDep,
    SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: New scheduler dependency
    SettingsServiceDep,
    SSEEventsOperationsDep,
    TimelapseServiceDep,
    VideoPipelineDep,  # Still used by queue/stats endpoints
    VideoServiceDep,  # For queue statistics delegation
)

# Constants and enums for consistency
from ..enums import JobPriority, SSEEvent, SSEEventSource, SSEPriority
from ..models.shared_models import (
    ManualGenerationRequest,
    QueueStatsResponse,
    VideoAutomationMode,
    VideoAutomationSettingsOptional,
    VideoGenerationJobWithDetails,
    VideoGenerationSettingsOptional,
)
from ..models.timelapse_model import TimelapseUpdate

# Response formatting
from ..utils.response_helpers import ResponseFormatter

# Router and validation helpers
from ..utils.router_helpers import (
    handle_exceptions,
    run_sync_service_method,
    validate_entity_exists,
)

# Timezone utilities for proper time handling
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
)

# Video settings validation helpers
from ..utils.validation_helpers import (
    create_timelapse_automation_response,
    get_effective_automation_settings,
    validate_automation_mode_updates,
    validate_video_settings,
)

# NOTE: CACHING STRATEGY - MINIMAL CACHE + SSE
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

    # Add a concrete field to fix Pydantic model definition
    model_config = {"extra": "forbid"}


# Video automation request models moved to shared_models.py


# API Endpoints


@router.get(
    "/video-automation/queue", response_model=List[VideoGenerationJobWithDetails]
)
@handle_exceptions("get video generation queue")
async def get_video_generation_queue(
    video_pipeline: VideoPipelineDep,
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
    if status and status not in JOB_STATUS_LIST:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(JOB_STATUS_LIST)}",
        )

    # Validate limit
    if limit and (limit < 1 or limit > MAX_PAGE_SIZE):
        raise HTTPException(
            status_code=400, detail=f"Limit must be between 1 and {MAX_PAGE_SIZE}"
        )

    try:
        # Use async service call with executor - access job_service from video_pipeline
        if status:
            jobs = await run_sync_service_method(
                video_pipeline.job_service.get_jobs_by_status,
                status,
                limit or DEFAULT_PAGE_SIZE,
            )
        else:
            # Get all statuses if no specific status requested
            all_jobs = []
            for status_type in JOB_STATUS_LIST:
                status_jobs = await run_sync_service_method(
                    video_pipeline.job_service.get_jobs_by_status,
                    status_type,
                    limit or DEFAULT_PAGE_SIZE,
                )
                all_jobs.extend(status_jobs)
            jobs = all_jobs[:limit] if limit else all_jobs

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

    except Exception:
        # Let @handle_exceptions decorator handle logging
        raise HTTPException(
            status_code=500, detail="Failed to fetch video generation queue"
        )


@router.get("/video-automation/queue/stats", response_model=QueueStatsResponse)
@handle_exceptions("get queue statistics")
async def get_queue_stats(
    video_pipeline: VideoPipelineDep,
    video_service: VideoServiceDep,
    settings_service: SettingsServiceDep,
):
    """Get video generation queue statistics with health assessment"""
    try:
        # Delegate business logic to video service
        stats = await video_service.get_queue_statistics_with_health(video_pipeline)

        # Add timezone-aware timestamp
        timestamp = await get_timezone_aware_timestamp_async(settings_service)

        return QueueStatsResponse(
            total_jobs=stats["total_jobs"],
            pending_jobs=stats["pending_jobs"],
            processing_jobs=stats["processing_jobs"],
            completed_jobs=stats["completed_jobs"],
            failed_jobs=stats["failed_jobs"],
            queue_health=stats["queue_health"],
            timestamp=timestamp.isoformat(),
        )

    except Exception:
        # Let @handle_exceptions decorator handle logging
        raise HTTPException(status_code=500, detail="Failed to fetch queue statistics")


@router.post("/video-automation/generate/manual")
@handle_exceptions("trigger manual video generation")
async def trigger_manual_generation(
    request: ManualGenerationRequest,
    scheduler_service: SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: Use scheduler authority
    timelapse_service: TimelapseServiceDep,
    sse_ops: SSEEventsOperationsDep,
):
    """
    Manually trigger video generation for a timelapse.

    🎯 SCHEDULER-CENTRIC: Routes through scheduler authority instead of direct queue access.
    Enforces the "scheduler says jump" philosophy where ALL timing decisions go through scheduler.
    """
    # Validate timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, request.timelapse_id, "timelapse"
    )

    # Validate priority if provided
    if request.priority and request.priority not in JobPriority:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority. Must be one of: {', '.join([priority.value for priority in JobPriority])}",
        )

    try:
        # 🎯 SCHEDULER-CENTRIC: Route through scheduler authority instead of direct queue access
        result = await scheduler_service.schedule_immediate_video_generation(
            timelapse_id=request.timelapse_id,
            video_settings=request.settings,
            priority=request.priority or JobPriority.HIGH,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Scheduler failed to authorize video generation: {result.get('error', 'Unknown error')}",
            )

        # Create SSE event for real-time updates
        await sse_ops.create_event(
            event_type=SSEEvent.VIDEO_JOB_CREATED,
            event_data={
                "timelapse_id": request.timelapse_id,
                "trigger_type": VideoAutomationMode.MANUAL,
                "priority": request.priority or JobPriority.HIGH,
                "video_name": request.video_name,
                "scheduled_via": "scheduler_authority",
                "message": result.get("message"),
            },
            priority=SSEPriority.NORMAL,
            source=SSEEventSource.API,
        )

        return ResponseFormatter.success(
            "Video generation scheduled successfully through scheduler authority",
            data={
                "timelapse_id": request.timelapse_id,
                "trigger_type": VideoAutomationMode.MANUAL,
                "video_name": request.video_name,
                "scheduled_via": "scheduler_authority",
                "priority": request.priority or JobPriority.HIGH,
                "scheduler_message": result.get("message"),
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
        except Exception:
            # Could not fetch camera for inheritance - continue without it
            # Router layer should not do direct logging
            pass

    # Convert camera to dict if found
    camera_dict = camera.model_dump() if camera else None

    # Apply settings inheritance using helper function
    effective_settings = get_effective_automation_settings(
        timelapse_settings=timelapse_dict, camera_settings=camera_dict or {}
    )

    # Create response using helper function
    response_data = create_timelapse_automation_response(
        timelapse_id=timelapse_id,
        effective_settings=effective_settings,
        timelapse_model=timelapse,
    )

    return TimelapseAutomationSettings(**response_data)


@router.put("/video-automation/timelapse/{timelapse_id}/settings")
@handle_exceptions("update timelapse automation settings")
async def update_timelapse_automation_settings(
    timelapse_id: int,
    settings: AutomationSettingsUpdate,
    timelapse_service: TimelapseServiceDep,
    sse_ops: SSEEventsOperationsDep,
):
    """Update automation settings for a timelapse"""
    # Verify timelapse exists
    await validate_entity_exists(
        timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
    )

    update_data = settings.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        return ResponseFormatter.success(
            "No settings to update", data={"timelapse_id": timelapse_id}
        )

    # Validate automation modes using helper function
    mode_valid, mode_error = validate_automation_mode_updates(update_data)
    if not mode_valid:
        return ResponseFormatter.error(
            mode_error or "Invalid automation mode",
            error_code="invalid_automation_mode",
        )

    # Validate settings using validation helpers
    is_valid, error = validate_video_settings(update_data)
    if not is_valid:
        return ResponseFormatter.error(
            f"Invalid settings: {error or 'Unknown validation error'}",
            error_code="invalid_settings",
        )

    try:
        timelapse_update = TimelapseUpdate(**update_data)
        await timelapse_service.update_timelapse(timelapse_id, timelapse_update)

        # Create SSE event for real-time updates
        await sse_ops.create_event(
            event_type=SSEEvent.TIMELAPSE_SETTINGS_UPDATED,
            event_data={
                "timelapse_id": timelapse_id,
                "updated_fields": list(update_data.keys()),
                "settings": update_data,
            },
            priority=SSEPriority.NORMAL,
            source=SSEEventSource.API,
        )

        return ResponseFormatter.success(
            "Timelapse automation settings updated successfully",
            data={
                "timelapse_id": timelapse_id,
                "updated_fields": list(update_data.keys()),
            },
        )

    except Exception:
        # Let @handle_exceptions decorator handle logging
        return ResponseFormatter.error(
            "Failed to update automation settings", error_code="update_failed"
        )
