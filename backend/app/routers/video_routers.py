# backend/app/routers/video_routers.py
"""
Video management and generation HTTP endpoints.

Role: Video management and generation HTTP endpoints
Responsibilities: Video metadata CRUD, manual video generation triggers, video file serving
Interactions: Uses VideoService for business logic, coordinates with VideoAutomationService
            for generation requests
"""

# Standard library imports
import asyncio
import re
from typing import List, Optional

# Third party imports
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, status, Response
from pydantic import BaseModel, Field, field_validator
from ..services.logger import get_service_logger
from ..enums import LogSource, LoggerName

logger = get_service_logger(LoggerName.API, LogSource.API)

from ..services.video_pipeline.constants import (
    ERROR_VIDEO_FILE_NOT_FOUND,
    ERROR_VIDEO_GENERATION_FAILED,
)

# Local application imports
from ..config import settings
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
)
from ..constants import (
    JOB_PRIORITY,
    JOB_STATUS,
    DEFAULT_FPS,
    VIDEO_QUALITIES,
)
from ..enums import SSEPriority
from ..dependencies import (
    VideoPipelineDep,  # For video generation workflow
    VideoServiceDep,  # For video CRUD operations
    SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: For timing operations
    CameraServiceDep,
    TimelapseServiceDep,
    SettingsServiceDep,
    HealthServiceDep,
    AsyncDatabaseDep,
)
from ..models import VideoCreate, VideoWithDetails
from ..models.video_model import Progress, VideoGenerationStatus
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
    get_active_timelapse_for_camera,
)
from ..utils.validation_helpers import (
    create_default_video_settings,
    validate_video_settings,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.file_helpers import (
    validate_file_path,
    create_file_response,
    clean_filename,
)
from ..utils.time_utils import parse_iso_timestamp_safe
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    format_filename_timestamp,
)

# NOTE: CACHING STRATEGY - OPTIMAL MIXED APPROACH (EXCELLENT IMPLEMENTATION)
# Video operations use optimal caching strategy perfectly aligned with content types:
# - Video files: Long cache + ETag - immutable large files, massive bandwidth savings
# - Video metadata: ETag + cache - changes occasionally when videos created/deleted
# - Real-time operations: SSE broadcasting - generation triggers, queue monitoring
# - Queue/status: SSE or very short cache - critical real-time operational monitoring
# Individual endpoint caching strategies are well-defined throughout this file.
router = APIRouter(tags=["videos"])


class VideoGenerationRequest(BaseModel):
    """Model for video generation request with input validation"""

    camera_id: int = Field(..., gt=0, description="Camera ID must be positive")
    video_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Video name"
    )

    @field_validator("video_name")
    @classmethod
    def validate_video_name(_cls, v: Optional[str]) -> Optional[str]:
        """Validate video name using centralized helper"""
        if v is None:
            return v

        # Use centralized filename cleaning from file_helpers
        cleaned = clean_filename(v.strip()) if v.strip() else None

        if not cleaned:
            return None

        # Additional validation for video names
        if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            raise ValueError("Video name cannot contain path separators or '..'")

        return cleaned


# IMPLEMENTED: ETag + 10 minute cache (video list changes when videos created/deleted)
# ETag based on latest video created_at timestamp + video count
@router.get("/videos", response_model=List[VideoWithDetails])
@handle_exceptions("get videos")
async def get_videos(
    response: Response,
    video_service: VideoServiceDep,
    camera_service: CameraServiceDep,
    timelapse_service: TimelapseServiceDep,
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    timelapse_id: Optional[int] = Query(None, description="Filter by timelapse ID"),
):
    """Get all videos, optionally filtered by camera or timelapse"""
    if camera_id:
        await validate_entity_exists(
            camera_service.get_camera_by_id, camera_id, "camera"
        )
    if timelapse_id:
        await validate_entity_exists(
            timelapse_service.get_timelapse_by_id, timelapse_id, "timelapse"
        )
    if camera_id and timelapse_id:
        videos = await video_service.get_videos_by_timelapse(timelapse_id)
    elif camera_id:
        videos = await video_service.get_videos_by_camera(camera_id)
    elif timelapse_id:
        videos = await video_service.get_videos_by_timelapse(timelapse_id)
    else:
        videos = await video_service.get_videos()

    # Generate ETag based on videos collection data
    if videos:
        etag = generate_collection_etag([v.created_at for v in videos])
    else:
        etag = generate_content_hash_etag(f"empty-videos-{camera_id}-{timelapse_id}")

    # Add moderate cache for video list
    response.headers["Cache-Control"] = (
        "public, max-age=600, s-maxage=600"  # 10 minutes
    )
    response.headers["ETag"] = etag

    return videos


# IMPLEMENTED: ETag + long cache (video metadata never changes after creation)
# ETag = f'"{video.id}-{video.updated_at.timestamp()}"'
@router.get("/videos/{video_id}", response_model=VideoWithDetails)
@handle_exceptions("get video")
async def get_video(response: Response, video_id: int, video_service: VideoServiceDep):
    """Get a specific video by ID"""
    video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )

    # Generate ETag based on video ID and created timestamp (videos are immutable after creation)
    etag = generate_composite_etag(video.id, video.created_at)

    # Add long cache for video metadata (immutable after creation)
    response.headers["Cache-Control"] = "public, max-age=3600, s-maxage=3600"  # 1 hour
    response.headers["ETag"] = etag

    return video


# NOTE: No HTTP caching needed for POST operations
@router.post("/videos", response_model=dict)
@handle_exceptions("create video")
async def create_video(
    video_data: VideoCreate,
    video_service: VideoServiceDep,
    settings_service: SettingsServiceDep,
):
    """Create a new video generation request"""
    # Use validation helpers to validate settings
    is_valid, error = validate_video_settings(video_data.settings)
    if not is_valid:
        return ResponseFormatter.error(
            "Invalid video settings", details={"error": error}
        )

    # Create video record using VideoService (handles CRUD operations)
    created_video = await video_service.create_video_record(video_data)

    # Handle case where video creation fails
    if not created_video:
        return ResponseFormatter.error(
            "Failed to create video record", error_code="VIDEO_CREATION_FAILED"
        )

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Video generation request created",
        data={"video_id": created_video.id, "status": created_video.status},
    )


# NOTE: Good SSE broadcasting - no HTTP caching needed for DELETE operations
@router.delete("/videos/{video_id}")
@handle_exceptions("delete video")
async def delete_video(
    video_id: int,
    video_service: VideoServiceDep,
    settings_service: SettingsServiceDep,
):
    """Delete a video"""
    # Check if video exists using validate_entity_exists
    existing_video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )

    # Delete video
    success = await video_service.delete_video(video_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete video")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success("Video deleted successfully")


# IMPLEMENTED: long cache + ETag for immutable video files
# Cache-Control: public, max-age=31536000, immutable + ETag based on video.id + file_size
@router.get("/videos/{video_id}/download")
@handle_exceptions("download video")
async def download_video(
    response: Response,
    video_id: int,
    video_service: VideoServiceDep,
    settings_service: SettingsServiceDep,
):
    """Download a video file"""
    # Get video details using validate_entity_exists (now properly typed)
    video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )

    if not video.file_path or video.status != JOB_STATUS.COMPLETED:
        raise HTTPException(status_code=404, detail=ERROR_VIDEO_FILE_NOT_FOUND)

    # Generate ETag based on video ID and file size for immutable content cache validation
    etag = generate_content_hash_etag(f"{video.id}-{video.file_size}")

    # Add aggressive cache for immutable video files
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # 1 year
    response.headers["ETag"] = etag

    # Use file_helpers for secure path validation and file serving
    try:
        validated_path = validate_file_path(
            video.file_path, base_directory=settings.data_directory, must_exist=True
        )
    except HTTPException:
        # file_helpers already raises appropriate HTTPException
        raise

    # Generate safe filename using centralized utilities
    safe_video_name = clean_filename(video.name or f"video_{video.id}")

    # Add timestamp to filename using timezone-aware utilities
    if video.created_at:
        try:
            # Parse timestamp safely using time_utils
            if isinstance(video.created_at, str):
                parsed_timestamp = parse_iso_timestamp_safe(video.created_at)
            else:  # datetime object
                parsed_timestamp = video.created_at

            # Get timezone-aware timestamp using settings service
            timezone_aware_timestamp = await get_timezone_aware_timestamp_async(
                settings_service
            )

            # Use format_filename_timestamp for consistent formatting
            timestamp_str = format_filename_timestamp(timezone_aware_timestamp)
            filename = f"{safe_video_name}_{timestamp_str}.mp4"
        except Exception:
            # Fallback filename without timestamp if timestamp processing fails
            filename = f"{safe_video_name}.mp4"
    else:
        # No timestamp available
        filename = f"{safe_video_name}.mp4"

    # Use file_helpers for secure file response
    return create_file_response(
        file_path=validated_path, filename=filename, media_type="video/mp4"
    )


# NOTE: Good SSE broadcasting - no HTTP caching needed for video generation triggers
# SSE broadcasting should be handled by service layer (proper architecture)
@router.post("/videos/generate")
@handle_exceptions("generate video")
async def generate_video(
    request: VideoGenerationRequest,
    background_tasks: BackgroundTasks,
    scheduler_service: SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: Use scheduler authority
    video_pipeline: VideoPipelineDep,
    camera_service: CameraServiceDep,
    timelapse_service: TimelapseServiceDep,
    health_service: HealthServiceDep,
    settings_service: SettingsServiceDep,
):
    """
    🎯 SCHEDULER-CENTRIC: Manual video generation endpoint using scheduler authority.

    ALL timing operations must flow through SchedulerWorker. This ensures proper
    coordination and prevents conflicts with other video generation jobs.
    """
    import asyncio

    # Validate camera exists and is accessible
    camera = await validate_entity_exists(
        camera_service.get_camera_by_id, request.camera_id, "camera"
    )

    # Get active timelapse for the camera using router helpers
    active_timelapse = await get_active_timelapse_for_camera(
        timelapse_service, request.camera_id
    )

    # Check system health before starting video generation
    health_status = await health_service.get_detailed_health()
    if health_status.status == "unhealthy":
        raise HTTPException(
            status_code=503,
            detail="System is unhealthy, video generation temporarily unavailable",
        )

    loop = asyncio.get_event_loop()

    try:
        # 🎯 SCHEDULER-CENTRIC: Route video generation through scheduler authority
        # Delegate settings construction to validation helpers
        video_settings = create_default_video_settings(
            video_name=request.video_name, generation_type="manual"
        )

        generation_result = await scheduler_service.schedule_immediate_video_generation(
            timelapse_id=active_timelapse.id,
            video_settings=video_settings,
            priority="high",  # Manual generation gets high priority
        )

    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        generation_result = {"success": False, "error": str(e)}

    if not generation_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=generation_result.get("error", ERROR_VIDEO_GENERATION_FAILED),
        )

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Video generation scheduled successfully through scheduler authority",
        data={
            "scheduled_via": "scheduler_authority",
            "timelapse_id": active_timelapse.id,
            "video_name": request.video_name,
            "scheduler_message": generation_result.get("message"),
            "estimated_completion": generation_result.get("estimated_completion"),
            "queue_position": generation_result.get("queue_position", 1),
        },
    )


# NOTE: Queue status endpoint - consider SSE in services layer for real-time updates
# Currently uses very short cache as queue status changes frequently
@router.get("/videos/generation-queue")
@handle_exceptions("get video generation queue")
async def get_video_generation_queue(
    video_pipeline: VideoPipelineDep,
    health_service: HealthServiceDep,
):
    """Get current video generation queue status with health monitoring"""

    loop = asyncio.get_event_loop()

    try:
        # Get queue status from job service and processing status from workflow service
        queue_status = await loop.run_in_executor(
            None, video_pipeline.job_service.get_queue_status
        )
        processing_status = await loop.run_in_executor(
            None, video_pipeline.get_processing_status
        )

        # Combine both statuses for comprehensive automation stats
        combined_status = {**queue_status, **processing_status}

        # Add health check for video queue
        health_status = await health_service.get_detailed_health()

        # Enhance response with health information
        enhanced_status = {
            **combined_status,
            "system_health": health_status.status,
            "warnings": health_status.warnings,
        }

        return ResponseFormatter.success(
            "Video generation queue status retrieved", data=enhanced_status
        )

    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        return ResponseFormatter.error(
            "Failed to retrieve queue status",
            error_code="QUEUE_STATUS_ERROR",
            details={"error": str(e)},
        )


# NOTE: Generation status endpoint - consider SSE in services layer for real-time updates
# Status changes frequently during video processing, SSE would provide better UX
@router.get(
    "/videos/{video_id}/generation-status", response_model=VideoGenerationStatus
)
@handle_exceptions("get video generation status")
async def get_video_generation_status(video_id: int, video_service: VideoServiceDep):
    """Get generation status for a specific video"""
    video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )

    progress = Progress(
        image_count=video.image_count,
        file_size=video.file_size,
        duration_seconds=video.duration_seconds,
    )
    generation_status = VideoGenerationStatus(
        video_id=video.id,
        status=video.status,
        job_id=video.job_id,
        trigger_type=video.trigger_type,
        created_at=video.created_at,
        updated_at=video.updated_at,
        progress=progress,
    )
    return generation_status


# NOTE: No caching needed - cancellation is immediate action
# SSE broadcasting will be added when cancel functionality is implemented
@router.post("/videos/{video_id}/cancel-generation")
@handle_exceptions("cancel video generation")
async def cancel_video_generation(
    video_id: int,
    video_service: VideoServiceDep,
    scheduler_service: SchedulerServiceDep,  # 🎯 SCHEDULER-CENTRIC: Use scheduler authority
):
    """
    🎯 SCHEDULER-CENTRIC: Cancel video generation through scheduler authority.

    ALL timing operations must flow through SchedulerWorker. This ensures proper
    coordination and prevents conflicts with other video generation operations.
    """
    # Validate video exists first
    video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )

    # Check if video has an associated job_id
    if not video.job_id:
        return ResponseFormatter.error(
            "Cannot cancel video generation. No associated job found for this video.",
            error_code="NO_JOB_ASSOCIATED",
            details={
                "video_id": video_id,
                "video_status": video.status,
            },
        )

    # Check if video is in a cancellable state (based on video status)
    cancellable_video_statuses = [
        "generating"
    ]  # Only generating videos can be cancelled
    if video.status not in cancellable_video_statuses:
        return ResponseFormatter.error(
            f"Cannot cancel video generation. Video status is '{video.status}'",
            error_code="INVALID_STATUS_FOR_CANCELLATION",
            details={
                "current_status": video.status,
                "cancellable_statuses": cancellable_video_statuses,
            },
        )

    # 🎯 SCHEDULER-CENTRIC: Route cancellation through scheduler authority
    try:
        cancellation_result = await scheduler_service.schedule_immediate_video_cancellation(
            video_id=video_id,
            job_id=str(video.job_id),
            priority=SSEPriority.CRITICAL,  # Cancellations are critical user requests
        )

        if not cancellation_result.get("success"):
            return ResponseFormatter.error(
                f"Scheduler failed to authorize video cancellation: {cancellation_result.get('error', 'Unknown error')}",
                error_code="SCHEDULER_CANCELLATION_FAILED",
                details={
                    "video_id": video_id,
                    "job_id": video.job_id,
                    "scheduler_error": cancellation_result.get("error"),
                },
            )

        return ResponseFormatter.success(
            "Video generation cancellation scheduled successfully through scheduler authority",
            data={
                "video_id": video_id,
                "job_id": video.job_id,
                "scheduled_via": "scheduler_authority",
                "priority": SSEPriority.CRITICAL,
                "scheduler_message": cancellation_result.get("message"),
                "cancellation_status": "scheduled",
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error cancelling video generation: {e}")
        return ResponseFormatter.error(
            "An unexpected error occurred while cancelling video generation",
            error_code="INTERNAL_ERROR",
            details={"error": str(e)},
        )
