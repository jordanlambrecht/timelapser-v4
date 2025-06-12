from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from loguru import logger

from ..database import async_db
from ..models import Video, VideoCreate, VideoUpdate, VideoWithDetails

router = APIRouter()


@router.get("/", response_model=List[VideoWithDetails])
async def get_videos(
    camera_id: Optional[int] = Query(None, description="Filter by camera ID")
):
    """Get all videos, optionally filtered by camera"""
    try:
        videos = await async_db.get_videos(camera_id=camera_id)
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
