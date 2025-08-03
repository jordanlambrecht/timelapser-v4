# backend/app/models/statistics_model.py
"""
Pydantic models for system health and statistics data.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class SystemOverviewModel(BaseModel):
    """Model for system overview metadata"""

    total_entities: int
    active_operations: int
    system_status: str
    last_updated: str


class EnhancedDashboardStatsModel(BaseModel):
    """Enhanced dashboard model with system overview, storage data, quality trends, camera performance, and health score"""

    camera: "CameraStatsModel"
    timelapse: "TimelapseStatsModel"
    image: "ImageStatsModel"
    video: "VideoStatsModel"
    automation: "AutomationStatsModel"
    recent_activity: "RecentActivityModel"
    system_overview: SystemOverviewModel
    storage: "StorageStatsModel"
    quality_trends: List["QualityTrendDataPoint"]
    camera_performance: List["CameraPerformanceModel"]
    health_score: "SystemHealthScoreModel"


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


class AutomationStatsModel(BaseModel):
    total_jobs: int
    pending_jobs: int
    processing_jobs: int
    completed_jobs: int
    failed_jobs: int
    queue_health: str


class RecentActivityModel(BaseModel):
    captures_last_hour: int
    captures_last_24h: int


class DashboardStatsModel(BaseModel):
    camera: CameraStatsModel
    timelapse: TimelapseStatsModel
    image: ImageStatsModel
    video: VideoStatsModel
    automation: AutomationStatsModel
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

    @field_validator("last_capture_at", mode="before")
    @classmethod
    def convert_datetime_to_string(cls, v):
        """Convert datetime objects to ISO string format"""
        if v is None:
            return v
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, str):
            return v
        return str(v)


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


# Rebuild models to resolve forward references
EnhancedDashboardStatsModel.model_rebuild()
