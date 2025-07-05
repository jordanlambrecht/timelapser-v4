# backend/app/routers/video_routers.py
"""
Video management and generation HTTP endpoints.

Role: Video management and generation HTTP endpoints
Responsibilities: Video metadata CRUD, manual video generation triggers, video file serving
Interactions: Uses VideoService for business logic, coordinates with VideoAutomationService
             for generation requests
"""

# Standard library imports
import re
from typing import List, Optional

# Third party imports
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, status, Response
from pydantic import BaseModel, Field, field_validator

# Local application imports
from ..config import settings
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
    generate_timestamp_etag
)
from ..constants import (
    VIDEO_STATUSES,
    MIN_FPS,
    MAX_FPS,
    DEFAULT_FPS,
    VIDEO_QUALITIES,
    VIDEO_JOB_PRIORITIES,
    VIDEO_JOB_STATUSES,
    ALLOWED_VIDEO_EXTENSIONS,
    VIDEO_NOT_FOUND,
    VIDEO_GENERATION_FAILED,
    FILE_NOT_FOUND,
    FILE_ACCESS_DENIED,
    OPERATION_SUCCESS,
    CACHE_CONTROL_PUBLIC,
)
from ..dependencies import (
    VideoServiceDep,
    SyncVideoServiceDep,
    VideoAutomationServiceDep,
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
from ..utils.video_helpers import VideoSettingsHelper
from ..utils.response_helpers import ResponseFormatter
from ..utils.file_helpers import (
    validate_file_path,
    create_file_response,
    clean_filename,
)
from ..utils.timezone_utils import parse_iso_timestamp_safe
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    format_filename_timestamp,
)

# TODO: CACHING STRATEGY - OPTIMAL MIXED APPROACH (EXCELLENT IMPLEMENTATION)
# Video operations use optimal caching strategy perfectly aligned with content types:
# - Video files: Long cache + ETag - immutable large files, massive bandwidth savings
# - Video metadata: ETag + cache - changes occasionally when videos created/deleted
# - Real-time operations: SSE broadcasting - generation triggers, queue monitoring
# - Queue/status: SSE or very short cache - critical real-time operational monitoring
# Individual endpoint TODOs are exceptionally well-defined throughout this file.
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
    videos = await video_service.get_videos(timelapse_id=timelapse_id)
    
    # Generate ETag based on videos collection data
    if videos:
        etag = generate_collection_etag([v.created_at for v in videos])
    else:
        etag = generate_content_hash_etag(f"empty-videos-{camera_id}-{timelapse_id}")
    
    # Add moderate cache for video list
    response.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"  # 10 minutes
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


# TODO: Good SSE broadcasting - no HTTP caching needed for POST operations
@router.post("/videos", response_model=dict)
@handle_exceptions("create video")
async def create_video(
    video_data: VideoCreate,
    video_service: VideoServiceDep,
    settings_service: SettingsServiceDep,
):
    """Create a new video generation request"""
    # Use VideoSettingsHelper to validate and apply settings
    is_valid, error = VideoSettingsHelper.validate_video_settings(video_data.settings)
    if not is_valid:
        return ResponseFormatter.error(
            "Invalid video settings", details={"error": error}
        )

    prepared_data = {
        "camera_id": video_data.camera_id,
        "name": video_data.name,
        "settings": video_data.settings,
        "status": (
            VIDEO_STATUSES[0] if VIDEO_STATUSES else "pending"
        ),  # Use first status from constants
    }

    created_video = await video_service.create_video_record(prepared_data)

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Video generation request created",
        data={"video_id": created_video.id, "status": prepared_data["status"]},
    )


# TODO: Good SSE broadcasting - no HTTP caching needed for DELETE operations
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

    if not video.file_path or video.status != "completed":
        raise HTTPException(status_code=404, detail=FILE_NOT_FOUND)

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


# TODO: Good SSE broadcasting - no HTTP caching needed for video generation triggers. SSE needs to be moved to services layer
@router.post("/videos/generate")
@handle_exceptions("generate video")
async def generate_video(
    request: VideoGenerationRequest,
    background_tasks: BackgroundTasks,
    video_automation_service: VideoAutomationServiceDep,
    camera_service: CameraServiceDep,
    timelapse_service: TimelapseServiceDep,
    health_service: HealthServiceDep,
    settings_service: SettingsServiceDep,
):
    """Manual video generation endpoint coordinating with VideoAutomationService"""
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

    # Use constants for FPS, quality, and priority instead of hardcoded values
    video_fps = DEFAULT_FPS
    video_quality = (
        VIDEO_QUALITIES[1] if len(VIDEO_QUALITIES) > 1 else VIDEO_QUALITIES[0]
    )
    job_priority = (
        VIDEO_JOB_PRIORITIES[2] if len(VIDEO_JOB_PRIORITIES) > 2 else "high"
    )  # "high" priority for manual

    try:
        job_id = await loop.run_in_executor(
            None,
            lambda: video_automation_service.queue.add_job(
                timelapse_id=active_timelapse.id,  # Clean Pydantic model access
                trigger_type="manual",
                priority=job_priority,
                settings={
                    "video_name": request.video_name,
                    "framerate": video_fps,
                    "quality": video_quality,
                },
            ),
        )
        generation_result = (
            {"success": True, "job_id": job_id}
            if job_id
            else {"success": False, "error": "Failed to create job"}
        )
    except Exception as e:
        # Let @handle_exceptions decorator handle logging
        generation_result = {"success": False, "error": str(e)}

    if not generation_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=generation_result.get("error", VIDEO_GENERATION_FAILED),
        )

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Video generation scheduled successfully",
        data={
            "job_id": generation_result.get("job_id"),
            "video_id": generation_result.get("video_id"),
            "estimated_completion": generation_result.get("estimated_completion"),
            "queue_position": generation_result.get("queue_position", 1),
        },
    )


# TODO: Replace with SSE in services layer - queue status changes frequently and users need real-time updates
# Use very short cache (30 seconds max) or preferably SSE events
@router.get("/videos/generation-queue")
@handle_exceptions("get video generation queue")
async def get_video_generation_queue(
    video_automation_service: VideoAutomationServiceDep,
    health_service: HealthServiceDep,
):
    """Get current video generation queue status with health monitoring"""
    import asyncio

    loop = asyncio.get_event_loop()

    try:
        # Get queue status
        queue_status = await loop.run_in_executor(
            None, video_automation_service.get_automation_stats
        )

        # Add health check for video queue
        health_status = await health_service.get_detailed_health()

        # Enhance response with health information
        enhanced_status = {
            **queue_status,
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


# TODO: Replace with SSE in services layer- generation status changes frequently during processing
# Remove HTTP caching, use SSE events for real-time progress updates
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


# TODO: No caching needed - cancellation is immediate action
# Add SSE broadcasting when cancel functionality is implemented
@router.post("/videos/{video_id}/cancel-generation")
@handle_exceptions("cancel video generation")
async def cancel_video_generation(
    video_id: int,
    video_service: VideoServiceDep,
    video_automation_service: VideoAutomationServiceDep,
):
    """Cancel video generation for a specific video"""
    # Validate video exists first
    video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )

    # Check if video is in a cancellable state
    cancellable_statuses = ["pending", "processing"]  # Use appropriate statuses
    if video.status not in cancellable_statuses:
        return ResponseFormatter.error(
            f"Cannot cancel video generation. Video status is '{video.status}'",
            error_code="INVALID_STATUS_FOR_CANCELLATION",
            details={
                "current_status": video.status,
                "cancellable_statuses": cancellable_statuses,
            },
        )

    # TODO: Implement cancel_video_generation method in VideoAutomationService
    # For now, return a placeholder response with proper structure
    # Let @handle_exceptions decorator handle logging if needed

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Cancel generation feature not yet implemented",
    )
