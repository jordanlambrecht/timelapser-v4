# backend/app/routers/videos.py
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Optional
from loguru import logger
from pydantic import BaseModel, Field, field_validator
import re
import os
from pathlib import Path
from datetime import datetime

from ..database import async_db, sync_db
from ..models import Video, VideoCreate, VideoUpdate, VideoWithDetails
from ..config import settings

router = APIRouter()


@router.get("/", response_model=List[VideoWithDetails])
async def get_videos(
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    timelapse_id: Optional[int] = Query(None, description="Filter by timelapse ID"),
):
    """Get all videos, optionally filtered by camera or timelapse"""
    try:
        videos = await async_db.get_videos(
            camera_id=camera_id, timelapse_id=timelapse_id
        )
        return videos
    except Exception as e:
        logger.error(f"Error fetching videos: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch videos")


@router.get("/{video_id}", response_model=VideoWithDetails)
async def get_video(video_id: int):
    """Get a specific video by ID"""
    try:
        video = await async_db.get_video_by_id(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return video
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch video")


@router.post("/", response_model=dict)
async def create_video(video_data: VideoCreate):
    """Create a new video generation request"""
    try:
        video_id = await async_db.create_video_record(
            video_data.camera_id, video_data.name, video_data.settings
        )
        if not video_id:
            raise HTTPException(status_code=500, detail="Failed to create video")

        logger.info(
            f"Created video generation request {video_id} for camera {video_data.camera_id}"
        )
        return {"video_id": video_id, "status": "generating"}
    except Exception as e:
        logger.error(f"Error creating video: {e}")
        raise HTTPException(status_code=500, detail="Failed to create video")


@router.delete("/{video_id}")
async def delete_video(video_id: int):
    """Delete a video"""
    try:
        # Check if video exists
        existing_video = await async_db.get_video_by_id(video_id)
        if not existing_video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Delete video
        success = await async_db.delete_video(video_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete video")

        logger.info(f"Deleted video {video_id}: {existing_video['name']}")
        return {"message": "Video deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete video")


@router.get("/{video_id}/download")
async def download_video(video_id: int):
    """Download a video file"""
    try:
        # Get video details
        video = await async_db.get_video_by_id(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        if not video.get("file_path") or video.get("status") != "completed":
            raise HTTPException(status_code=404, detail="Video file not available")

        # SECURITY: Validate file path before accessing
        project_root = Path(__file__).parent.parent.parent.parent
        data_dir = project_root / "data"

        # Handle both absolute and relative paths
        file_path = video["file_path"]
        if Path(file_path).is_absolute():
            safe_path = Path(file_path)
        else:
            safe_path = project_root / file_path

        # SECURITY: Ensure the resolved path is within allowed directories
        resolved_path = safe_path.resolve()
        resolved_data_dir = data_dir.resolve()

        if not (
            str(resolved_path).startswith(str(resolved_data_dir))
            or str(resolved_path).startswith(str(project_root.resolve()))
        ):
            logger.warning(f"Attempted path traversal attack: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if file exists
        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found on disk")

        # Generate filename with timestamp
        video_name = video.get("name", f"video_{video_id}")

        # Clean video name for filename
        safe_video_name = "".join(
            c for c in video_name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_video_name = safe_video_name.replace(" ", "_")

        # Add timestamp to filename
        if video.get("created_at"):
            try:
                created_at = video["created_at"]
                if isinstance(created_at, str):
                    # Handle different timestamp formats
                    if created_at.endswith("Z"):
                        created_at = created_at.replace("Z", "+00:00")
                    timestamp = datetime.fromisoformat(created_at)
                elif hasattr(created_at, "strftime"):  # datetime object
                    timestamp = created_at
                else:
                    timestamp = datetime.now()

                filename = (
                    f"{safe_video_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.mp4"
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing timestamp for video {video_id}: {e}")
                # Fallback to current timestamp
                filename = (
                    f"{safe_video_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                )
        else:
            # No timestamp available, use current time
            filename = (
                f"{safe_video_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )

        # Return file for download
        return FileResponse(
            path=str(resolved_path),
            filename=filename,
            media_type="video/mp4",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download video")


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


def generate_video_background_task(
    timelapse_id: int,
    camera_id: int,
    camera_name: str,
    video_name: Optional[str] = None,
):
    """Background task to generate video safely using direct Python calls"""
    try:
        # Import video generator
        from video_generator import VideoGenerator
        from ..config import settings
        import os

        # Create video generator with sync database
        sync_db.initialize()
        generator = VideoGenerator(sync_db)

        # Use secure output directory from settings
        output_directory = os.path.join(settings.data_directory, "videos")
        os.makedirs(output_directory, exist_ok=True)

        # Generate video safely - no shell execution
        success, message, video_id = (
            generator.generate_video_from_timelapse_with_overlays(
                timelapse_id=timelapse_id,
                output_directory=output_directory,
                video_name=video_name,
                framerate=30,
                quality="medium",
            )
        )

        logger.info(
            f"Video generation completed: success={success}, message={message}, video_id={video_id}"
        )

    except Exception as e:
        logger.error(f"Background video generation failed: {e}")
        # Update video status to failed if we have a video record
        try:
            with sync_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE videos SET status = 'failed' WHERE camera_id = %s AND status = 'generating' ORDER BY created_at DESC LIMIT 1",
                        (camera_id,),
                    )
                    conn.commit()
        except Exception as update_error:
            logger.error(f"Failed to update video status: {update_error}")
    finally:
        # Clean up database connection
        try:
            sync_db.close()
        except:
            pass


@router.post("/generate")
async def generate_video(
    request: VideoGenerationRequest, background_tasks: BackgroundTasks
):
    """
    Secure video generation endpoint that validates input and runs generation safely
    """
    try:
        # Validate camera exists and get details
        camera = await async_db.get_camera_by_id(request.camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Get active timelapse for this camera
        timelapses = await async_db.get_timelapses(camera_id=request.camera_id)
        active_timelapse = None
        for timelapse in timelapses:
            if timelapse.get("status") == "running":
                active_timelapse = timelapse
                break

        if not active_timelapse:
            raise HTTPException(
                status_code=400,
                detail="No active timelapse found for this camera. Start a timelapse first.",
            )

        # Generate safe video name if not provided
        safe_camera_name = re.sub(r"[^a-zA-Z0-9\-_]", "_", camera["name"])
        if not request.video_name:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_name = f"{safe_camera_name}_timelapse_{timestamp}"
        else:
            video_name = request.video_name

        # Create video record
        video_id = await async_db.create_video_record(
            camera_id=request.camera_id,
            name=video_name,
            settings={"framerate": 30, "quality": "medium"},
        )

        if not video_id:
            raise HTTPException(status_code=500, detail="Failed to create video record")

        # Start background video generation task - NO SHELL EXECUTION
        background_tasks.add_task(
            generate_video_background_task,
            timelapse_id=active_timelapse["id"],
            camera_id=request.camera_id,
            camera_name=safe_camera_name,
            video_name=video_name,
        )

        logger.info(
            f"Started video generation for camera {request.camera_id}, timelapse {active_timelapse['id']}"
        )

        return {
            "success": True,
            "message": "Video generation started",
            "video_id": video_id,
            "video_name": video_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting video generation: {e}")
        raise HTTPException(status_code=500, detail="Failed to start video generation")
