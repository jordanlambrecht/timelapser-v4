# backend/app/models/statistics_model.py
"""
Pydantic models for system health and statistics data.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CameraStatsModel(BaseModel):
    total_cameras: int
    enabled_cameras: int
    degraded_cameras: int
    cameras_with_heavy_detection: int


class TimelapseStatsModel(BaseModel):
    total_timelapses: int
    running_timelapses: int
    paused_timelapses: int
    completed_timelapses: int


class ImageStatsModel(BaseModel):
    total_images: int
    images_today: int
    flagged_images: int
    avg_quality_score: float
    total_storage_bytes: int


class VideoStatsModel(BaseModel):
    total_videos: int
    completed_videos: int
    processing_videos: int
    canceled_videos: int
    failed_videos: int
    total_file_size: int
    avg_duration: float


class RecentActivityModel(BaseModel):
    captures_last_hour: int
    captures_last_24h: int


class DashboardStatsModel(BaseModel):
    camera: CameraStatsModel
    timelapse: TimelapseStatsModel
    image: ImageStatsModel
    video: VideoStatsModel
    recent_activity: RecentActivityModel


class CameraPerformanceModel(BaseModel):
    id: int
    name: str
    enabled: bool
    degraded_mode_active: bool
    lifetime_glitch_count: int
    consecutive_corruption_failures: int
    total_images: int
    images_today: int
    images_week: int
    flagged_images: int
    avg_quality_score: float
    last_capture_at: Optional[str]
    total_videos: int
    total_storage_bytes: Optional[int]


class QualityTrendDataPoint(BaseModel):
    hour: str
    avg_quality_score: float
    image_count: int
    flagged_count: int


class StorageStatsModel(BaseModel):
    total_image_storage: Optional[int]
    total_video_storage: Optional[int]
    total_images: int
    total_videos: int
    avg_image_size: Optional[float]
    avg_video_size: Optional[float]


class SystemHealthScoreModel(BaseModel):
    overall_health_score: float
    camera_health_score: float
    quality_health_score: float
    activity_health_score: float
    component_details: dict
