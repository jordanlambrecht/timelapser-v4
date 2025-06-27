# backend/app/routers/video_routers.py
"""
Video management and generation HTTP endpoints.

Role: Video management and generation HTTP endpoints
Responsibilities: Video metadata CRUD, manual video generation triggers, video file serving
Interactions: Uses VideoService for business logic, coordinates with VideoAutomationService
             for generation requests

NOTE: Some business logic remains in this router, specifically:
- Construction of job settings dict in the /generate endpoint
- Filename formatting/cleaning in the download endpoint
For full separation of concerns, move these to a service or helper.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from ..models.video_model import Progress, VideoGenerationStatus

from ..config import settings
from ..constants import (
    VIDEO_STATUSES,
    MIN_FPS,
    MAX_FPS,
    DEFAULT_FPS,
    VIDEO_QUALITIES,
)
from ..dependencies import (
    VideoServiceDep,
    SyncVideoServiceDep,
    VideoAutomationServiceDep,
)
from ..models import VideoCreate, VideoWithDetails
from ..utils.router_helpers import (
    handle_exceptions,
    create_success_response,
    create_error_response,
    validate_entity_exists,
)
from ..utils.video_helpers import VideoSettingsHelper
from ..utils.response_helpers import ResponseFormatter
from ..utils.time_utils import parse_iso_timestamp_safe
from ..utils.timezone_utils import format_filename_timestamp

router = APIRouter(prefix="/videos", tags=["videos"])


class VideoGenerationRequest(BaseModel):
    """Model for video generation request with input validation"""

    camera_id: int = Field(..., gt=0, description="Camera ID must be positive")
    video_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Video name"
    )

    @field_validator("video_name")
    @classmethod
    def validate_video_name(_cls, v: Optional[str]) -> Optional[str]:
        """Validate video name to prevent injection attacks"""
        if v is None:
            return v

        # Strip whitespace
        v = v.strip()
        if not v:
            return None

        # Only allow alphanumeric, spaces, hyphens, underscores, and dots
        if not re.match(r"^[a-zA-Z0-9\s\-_.]+$", v):
            raise ValueError(
                "Video name contains invalid characters. Only letters, numbers, spaces, hyphens, underscores, and dots are allowed."
            )

        # Prevent potential path traversal
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Video name cannot contain path separators or '..'")

        return v


from ..dependencies import CameraServiceDep, TimelapseServiceDep


@router.get("/", response_model=List[VideoWithDetails])
@handle_exceptions("get videos")
async def get_videos(
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
    return videos


@router.get("/{video_id}", response_model=VideoWithDetails)
@handle_exceptions("get video")
async def get_video(video_id: int, video_service: VideoServiceDep):
    """Get a specific video by ID"""
    video = await validate_entity_exists(
        video_service.get_video_by_id, video_id, "video"
    )
    return video


@router.post("/", response_model=dict)
@handle_exceptions("create video")
async def create_video(video_data: VideoCreate, video_service: VideoServiceDep):
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
        "status": "generating",
    }

    created_video = await video_service.create_video_record(prepared_data)

    logger.info(
        f"Created video generation request {created_video.id} for camera {video_data.camera_id}"
    )
    return ResponseFormatter.success(
        "Video generation request created",
        data={"video_id": created_video.id, "status": "generating"},
    )


@router.delete("/{video_id}")
@handle_exceptions("delete video")
async def delete_video(video_id: int, video_service: VideoServiceDep):
    """Delete a video"""
    # Check if video exists
    existing_video = await video_service.get_video_by_id(video_id)
    if not existing_video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete video
    success = await video_service.delete_video(video_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete video")

    logger.info(f"Deleted video {video_id}: {existing_video.name}")
    return create_success_response("Video deleted successfully")


@router.get("/{video_id}/download")
@handle_exceptions("download video")
async def download_video(video_id: int, video_service: VideoServiceDep):
    """Download a video file"""
    # Get video details
    video = await video_service.get_video_by_id(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.file_path or video.status != "completed":
        raise HTTPException(status_code=404, detail="Video file not available")

    # SECURITY: Validate file path before accessing using config-driven paths (AI-CONTEXT compliant)
    data_dir = Path(settings.data_directory)

    # Handle both absolute and relative paths
    file_path = video.file_path
    if Path(file_path).is_absolute():
        safe_path = Path(file_path)
    else:
        safe_path = data_dir / file_path

    # SECURITY: Ensure the resolved path is within allowed directories
    resolved_path = safe_path.resolve()
    resolved_data_dir = data_dir.resolve()

    if not str(resolved_path).startswith(str(resolved_data_dir)):
        logger.warning(f"Attempted path traversal attack: {file_path}")
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if file exists
    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    # Generate filename with timestamp
    video_name = video.name or f"video_{video_id}"

    # Clean video name for filename
    safe_video_name = "".join(
        c for c in video_name if c.isalnum() or c in (" ", "-", "_")
    ).rstrip()
    safe_video_name = safe_video_name.replace(" ", "_")

    # Add timestamp to filename using timezone-aware utilities
    if video.created_at:
        try:
            created_at = video.created_at
            if isinstance(created_at, str):
                # Use centralized timestamp parsing
                timestamp = parse_iso_timestamp_safe(created_at)
            elif hasattr(created_at, "strftime"):  # datetime object
                timestamp = created_at
            else:
                # Use simple UTC timestamp for routers
                timestamp = datetime.now(timezone.utc)

            filename = f"{safe_video_name}_{format_filename_timestamp(timestamp)}.mp4"
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing timestamp for video {video_id}: {e}")
            # Fallback to simple UTC timestamp
            fallback_timestamp = datetime.now(timezone.utc)
            filename = (
                f"{safe_video_name}_{format_filename_timestamp(fallback_timestamp)}.mp4"
            )
    else:
        # No timestamp available, use simple UTC timestamp
        current_timestamp = datetime.now(timezone.utc)
        filename = (
            f"{safe_video_name}_{format_filename_timestamp(current_timestamp)}.mp4"
        )

    # Return file for download
    return FileResponse(
        path=str(resolved_path),
        filename=filename,
        media_type="video/mp4",
    )


@router.post("/generate")
@handle_exceptions("generate video")
async def generate_video(
    request: VideoGenerationRequest,
    background_tasks: BackgroundTasks,
    video_automation_service: VideoAutomationServiceDep,
):
    """
    Manual video generation endpoint coordinating with VideoAutomationService
    """
    # Use automation service to add manual video generation job
    import asyncio

    loop = asyncio.get_event_loop()

    # Get active timelapse for camera - run sync method in executor

    # Use constants for FPS and quality
    video_fps = DEFAULT_FPS
    if VIDEO_QUALITIES and "medium" in VIDEO_QUALITIES:
        video_quality = "medium"
    elif VIDEO_QUALITIES:
        video_quality = VIDEO_QUALITIES[0]
    else:
        video_quality = "medium"

    try:
        job_id = await loop.run_in_executor(
            None,
            lambda: video_automation_service.queue.add_job(
                timelapse_id=request.camera_id,  # TODO: get actual timelapse_id
                trigger_type="manual",
                priority="high",
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
        generation_result = {"success": False, "error": str(e)}

    if not generation_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=generation_result.get(
                "error", "Failed to schedule video generation"
            ),
        )

    logger.info(
        f"Scheduled manual video generation for camera {request.camera_id}: {generation_result.get('job_id')}"
    )

    return create_success_response(
        "Video generation scheduled successfully",
        job_id=generation_result.get("job_id"),
        video_id=generation_result.get("video_id"),
        estimated_completion=generation_result.get("estimated_completion"),
        queue_position=generation_result.get("queue_position", 1),
    )


@router.get("/generation-queue")
@handle_exceptions("get video generation queue")
async def get_video_generation_queue(
    video_automation_service: VideoAutomationServiceDep,
):
    """Get current video generation queue status"""
    # Use automation service to get queue status - run sync method in executor
    import asyncio

    loop = asyncio.get_event_loop()
    queue_status = await loop.run_in_executor(
        None, video_automation_service.get_automation_stats
    )
    return queue_status


@router.get("/{video_id}/generation-status", response_model=VideoGenerationStatus)
@handle_exceptions("get video generation status")
async def get_video_generation_status(video_id: int, video_service: VideoServiceDep):
    """Get generation status for a specific video"""
    video = await video_service.get_video_by_id(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
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


@router.post("/{video_id}/cancel-generation")
@handle_exceptions("cancel video generation")
async def cancel_video_generation(video_id: int):
    """Cancel video generation for a specific video"""
    # TODO: Implement cancel_video_generation method in VideoAutomationService
    # For now, return a placeholder response
    cancel_result = {"success": False, "error": "Cancel generation not yet implemented"}
    if not cancel_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=cancel_result.get("error", "Failed to cancel video generation"),
        )

    return create_success_response(
        "Video generation cancelled successfully", video_id=video_id
    )
