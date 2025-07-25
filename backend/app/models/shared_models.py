# backend/app/models/shared_models.py
"""
Shared model components to eliminate duplication across models.
"""

from typing import Optional, Dict, Any, Literal, List, TYPE_CHECKING
from enum import Enum
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .image_model import Image
    
from ..enums import (
    VideoAutomationMode, 
    VideoGenerationMode, 
    VideoQuality,
    ThumbnailJobPriority,
    ThumbnailJobStatus,
    ThumbnailJobType,
    JobPriority
)


class ImageStatisticsResponse(BaseModel):
    """Response model for image statistics endpoints"""

    message: str
    data: Optional[Dict[str, Any]] = None
    camera_id: Optional[int] = None
    timelapse_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class BulkDownloadResponse(BaseModel):
    """Response model for bulk image download endpoint"""

    requested_images: int
    included_images: int
    filename: str
    total_size: Optional[int] = None
    zip_data: Optional[bytes] = None
    model_config = ConfigDict(from_attributes=True)


class PaginatedImagesResponse(BaseModel):
    """Response model for paginated images endpoints"""

    images: List["Image"] = Field(
        ..., description="List of images for the current page"
    )
    total: int = Field(..., description="Total number of images matching the filters")
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(
        ..., description="Whether there are more pages after this one"
    )
    has_previous: bool = Field(
        ..., description="Whether there are pages before this one"
    )

    model_config = ConfigDict(from_attributes=True)


class ThumbnailRegenerationResponse(BaseModel):
    """Response model for thumbnail regeneration endpoint"""

    success: bool
    regenerated: int = 0
    failed: int = 0
    errors: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)




class ImageCapturedEvent(BaseModel):
    """Event data for image captured SSE events"""

    camera_id: int = Field(..., description="ID of the camera that captured the image")
    image_id: Optional[int] = Field(None, description="ID of the captured image")
    image_path: Optional[str] = Field(None, description="Path to the captured image")

    model_config = ConfigDict(from_attributes=True)


class VideoGenerationSettings(BaseModel):
    """Shared video generation settings to eliminate duplication"""

    video_generation_mode: VideoGenerationMode = Field(
        default=VideoGenerationMode.STANDARD, description="Video generation mode"
    )
    standard_fps: int = Field(
        default=12, ge=1, le=120, description="Standard FPS for video generation"
    )
    enable_time_limits: bool = Field(
        default=False, description="Enable time limits for standard FPS mode"
    )
    min_time_seconds: Optional[int] = Field(
        None, ge=1, description="Minimum video duration in seconds"
    )
    max_time_seconds: Optional[int] = Field(
        None, ge=1, description="Maximum video duration in seconds"
    )
    target_time_seconds: Optional[int] = Field(
        None, ge=1, description="Target video duration in seconds"
    )
    fps_bounds_min: int = Field(
        default=1, ge=1, le=60, description="Minimum FPS bound for target mode"
    )
    fps_bounds_max: int = Field(
        default=60, ge=1, le=120, description="Maximum FPS bound for target mode"
    )


class VideoGenerationSettingsOptional(BaseModel):
    """Optional version for updates and overrides"""

    video_generation_mode: Optional[VideoGenerationMode] = None
    standard_fps: Optional[int] = Field(None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: Optional[int] = Field(None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(None, ge=1, le=120)


class VideoAutomationSettings(BaseModel):
    """Shared video automation settings"""

    video_automation_mode: VideoAutomationMode = Field(
        default=VideoAutomationMode.MANUAL,
        description="Video generation automation mode",
    )
    generation_schedule: Optional["GenerationSchedule"] = Field(
        None, description="Schedule configuration for scheduled mode"
    )
    milestone_config: Optional["MilestoneConfig"] = Field(
        None, description="Milestone configuration for milestone mode"
    )


class VideoAutomationSettingsOptional(BaseModel):
    """Optional version for updates"""

    video_automation_mode: Optional[VideoAutomationMode] = None
    generation_schedule: Optional["GenerationSchedule"] = None
    milestone_config: Optional["MilestoneConfig"] = None


class CorruptionDetectionSettings(BaseModel):
    """Shared corruption detection settings"""

    corruption_detection_heavy: bool = Field(
        default=False,
        description="Enable advanced computer vision corruption detection",
    )
    # Add corruption fields that should be in main models
    corruption_score: int = Field(
        default=100, ge=0, le=100, description="Corruption score (100 = perfect)"
    )
    is_flagged: bool = Field(
        default=False, description="Whether image is flagged as corrupted"
    )
    lifetime_glitch_count: int = Field(
        default=0, description="Total corruption incidents"
    )
    consecutive_corruption_failures: int = Field(
        default=0, description="Current consecutive corruption failures"
    )


class CorruptionDetectionSettingsOptional(BaseModel):
    """Optional version for updates"""

    corruption_detection_heavy: Optional[bool] = None
    corruption_score: Optional[int] = Field(None, ge=0, le=100)
    is_flagged: Optional[bool] = None


class BaseStats(BaseModel):
    """Base statistics model to reduce duplication"""

    total_images: int = 0
    last_24h_images: int = 0
    success_rate_percent: Optional[float] = None
    storage_used_mb: Optional[float] = None


class CameraHealthStatus(BaseModel):
    """Camera health status model"""

    lifetime_glitch_count: int = 0
    consecutive_corruption_failures: int = 0
    degraded_mode_active: bool = False
    last_degraded_at: Optional[datetime] = None
    corruption_detection_heavy: bool = False
    corruption_logs_count: int = 0
    avg_corruption_score: Optional[float] = None


class TimelapseStatistics(BaseModel):
    """Timelapse statistics model"""

    total_images: int = 0
    total_videos: int = 0
    first_capture_at: Optional[datetime] = None
    last_capture_at: Optional[datetime] = None
    avg_quality_score: Optional[float] = None
    flagged_images: int = 0
    total_storage_bytes: Optional[int] = None
    total_video_storage_bytes: Optional[int] = None


class TimelapseLibraryStatistics(BaseModel):
    """Global statistics for the timelapse library"""

    total_timelapses: int = 0
    starred_count: int = 0
    active_count: int = 0
    total_images: int = 0
    total_storage_bytes: int = 0
    oldest_timelapse_date: Optional[datetime] = None


class CameraStatistics(BaseModel):
    """Extended camera statistics model"""

    total_timelapses: int = 0
    total_images: int = 0
    total_videos: int = 0
    last_capture_at: Optional[datetime] = None
    first_capture_at: Optional[datetime] = None
    avg_quality_score: Optional[float] = None
    flagged_images: int = 0


class VideoGenerationJob(BaseModel):
    """Video generation job model"""

    id: int
    timelapse_id: int
    trigger_type: str
    priority: JobPriority = Field(
        default=JobPriority.MEDIUM, description="Job priority (low, medium, high)"
    )
    status: str = "pending"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    video_path: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class VideoGenerationJobWithDetails(VideoGenerationJob):
    """Video generation job with additional context"""

    timelapse_name: Optional[str] = None
    camera_name: Optional[str] = None
    camera_id: Optional[int] = None


class VideoGenerationJobCreate(BaseModel):
    """Model for creating video generation jobs"""

    timelapse_id: int
    trigger_type: str = "manual"
    settings: Optional[Dict[str, Any]] = None


class VideoStatistics(BaseModel):
    """Video statistics model"""

    total_videos: int = 0
    total_size_bytes: Optional[int] = None
    avg_duration_seconds: Optional[float] = None
    avg_fps: Optional[float] = None
    latest_video_at: Optional[datetime] = None


class TimelapseForCleanup(BaseModel):
    """Timelapse model for cleanup operations"""

    id: int
    camera_id: int
    name: str
    description: Optional[str] = None
    status: str
    completed_at: Optional[datetime] = None
    camera_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelapseVideoSettings(BaseModel):
    """Timelapse video generation settings model"""

    video_generation_mode: VideoGenerationMode = VideoGenerationMode.STANDARD
    standard_fps: int = 12
    enable_time_limits: bool = False
    min_time_seconds: Optional[int] = None
    max_time_seconds: Optional[int] = None
    target_time_seconds: Optional[int] = None
    fps_bounds_min: int = 1
    fps_bounds_max: int = 60

    model_config = ConfigDict(from_attributes=True)


# Timelapse scheduling and automation models
class GenerationSchedule(BaseModel):
    """Generation schedule configuration"""

    type: Literal["daily", "weekly", "custom"] = "daily"
    time: str = "18:00"  # HH:MM format
    timezone: str = "UTC"
    enabled: bool = True
    model_config = ConfigDict(from_attributes=True)


class MilestoneConfig(BaseModel):
    """Milestone-based generation configuration"""

    thresholds: List[int] = Field(default_factory=lambda: [100, 500, 1000])
    enabled: bool = True
    reset_on_completion: bool = False
    model_config = ConfigDict(from_attributes=True)


class CorruptionSettings(BaseModel):
    """Global corruption detection settings model"""

    corruption_detection_enabled: bool = True
    corruption_score_threshold: int = Field(default=70, ge=0, le=100)
    corruption_auto_discard_enabled: bool = False
    corruption_auto_disable_degraded: bool = False
    corruption_degraded_consecutive_threshold: int = Field(default=10, ge=1)
    corruption_degraded_time_window_minutes: int = Field(default=30, ge=1)
    corruption_degraded_failure_percentage: int = Field(default=50, ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)


class ThumbnailGenerationResult(BaseModel):
    """Result of thumbnail generation operation"""

    success: bool
    image_id: int
    timelapse_id: Optional[int] = None
    thumbnail_path: Optional[str] = None
    small_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_size: Optional[int] = None
    error: Optional[str] = None
    processing_time_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ThumbnailRegenerationStatus(BaseModel):
    """Status of thumbnail regeneration process"""

    active: bool = False
    progress: int = 0  # Percentage 0-100
    total: int = 0  # Frontend expects "total"
    completed: int = 0  # Frontend expects "completed"
    errors: int = 0  # Frontend expects "errors"
    current_image_id: Optional[int] = None
    current_image: Optional[str] = None  # Frontend expects "current_image"
    estimated_time_remaining_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    status_message: str = "idle"

    model_config = ConfigDict(from_attributes=True)


class ThumbnailStatistics(BaseModel):
    """Comprehensive thumbnail statistics"""

    total_images: int = 0
    images_with_thumbnails: int = 0
    images_with_small: int = 0
    images_without_thumbnails: int = 0
    thumbnail_coverage_percentage: float = 0.0
    total_thumbnail_storage_mb: float = 0.0
    total_small_storage_mb: float = 0.0
    avg_thumbnail_size_kb: float = 0.0
    avg_small_size_kb: float = 0.0
    last_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ThumbnailOperationResponse(BaseModel):
    """Standard response for thumbnail operations"""

    success: bool
    message: str
    operation: str  # 'generate', 'regenerate', 'cleanup', etc.
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Camera Service Operation Result Models
class CameraHealthMonitoringResult(BaseModel):
    """Result of camera health monitoring operation"""

    success: bool
    camera_id: int
    basic_health: Optional[CameraHealthStatus] = None
    corruption_analysis: Optional[Dict[str, Any]] = None
    monitoring_timestamp: datetime
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CameraCaptureScheduleResult(BaseModel):
    """Result of camera capture scheduling operation"""

    success: bool
    camera_id: int
    scheduled_at: Optional[datetime] = None
    next_capture_at: Optional[datetime] = None
    message: str = "Capture scheduled successfully"
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CameraConnectivityTestResult(BaseModel):
    """Result of camera RTSP connectivity test"""

    success: bool
    camera_id: int
    rtsp_url: str
    response_time_ms: Optional[float] = None
    connection_status: str = "unknown"
    error: Optional[str] = None
    test_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class CameraCaptureWorkflowResult(BaseModel):
    """Result of complete camera capture workflow"""

    workflow_status: str  # "completed", "failed", "partial"
    camera_id: int
    connectivity: CameraConnectivityTestResult
    health_monitoring: CameraHealthMonitoringResult
    capture_scheduling: CameraCaptureScheduleResult
    overall_success: bool
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CameraLatestImageUrls(BaseModel):
    """URLs for different variants of camera's latest image"""

    full: str = Field(..., description="URL for full resolution image")
    small: str = Field(..., description="URL for small/medium image (800x600)")
    thumbnail: str = Field(..., description="URL for thumbnail image (200x150)")
    download: str = Field(
        ..., description="URL for downloading image with proper filename"
    )

    model_config = ConfigDict(from_attributes=True)


class CameraLatestImageMetadata(BaseModel):
    """Metadata about camera's latest image variants"""

    camera_id: int = Field(..., description="ID of the camera")
    has_thumbnail: bool = Field(..., description="Whether thumbnail variant exists")
    has_small: bool = Field(..., description="Whether small variant exists")
    thumbnail_size: Optional[int] = Field(
        None, description="Thumbnail file size in bytes"
    )
    small_size: Optional[int] = Field(
        None, description="Small variant file size in bytes"
    )

    model_config = ConfigDict(from_attributes=True)


class CameraLatestImageData(BaseModel):
    """Core data for camera's latest image"""

    image_id: int = Field(..., description="ID of the latest image")
    captured_at: str = Field(..., description="ISO timestamp when image was captured")
    day_number: int = Field(..., description="Day number in timelapse sequence")
    timelapse_id: Optional[int] = Field(None, description="ID of associated timelapse")
    file_size: Optional[int] = Field(None, description="Original file size in bytes")
    corruption_score: int = Field(..., description="Image quality score (0-100)")
    is_flagged: bool = Field(..., description="Whether image is flagged as corrupted")
    urls: CameraLatestImageUrls = Field(..., description="URLs for image variants")
    metadata: CameraLatestImageMetadata = Field(..., description="Additional metadata")

    model_config = ConfigDict(from_attributes=True)


class CameraLatestImageResponse(BaseModel):
    """Standardized response for camera latest image metadata endpoint"""

    success: bool = Field(True, description="Whether the request succeeded")
    message: str = Field(..., description="Response message")
    data: CameraLatestImageData = Field(..., description="Latest image data")

    model_config = ConfigDict(from_attributes=True)


# Additional models for RTSPService (consolidated RTSP operations)
class RTSPCaptureResult(BaseModel):
    """Result of RTSP image capture operation"""

    success: bool
    message: Optional[str] = None
    image_id: Optional[int] = None
    image_path: Optional[str] = None
    file_size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CorruptionDetectionResult(BaseModel):
    """Result of corruption detection analysis"""

    success: bool
    camera_id: int
    image_path: str
    quality_score: Optional[int] = None
    is_corrupted: Optional[bool] = None
    action_taken: Optional[str] = None
    detection_details: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[int] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BulkCaptureResult(BaseModel):
    """Result of bulk capture operation for multiple cameras"""

    total_cameras: int
    successful_captures: int
    failed_captures: int
    capture_results: List[Dict[str, Any]] = []
    processing_time_ms: Optional[int] = None
    message: str

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# SCHEDULING MODELS
# ====================================================================


class NextCaptureResult(BaseModel):
    """Result of next capture time calculation"""

    camera_id: int
    next_capture_time: datetime
    last_capture_time: Optional[datetime] = None
    interval_seconds: int
    time_window_start: Optional[str] = None  # HH:MM:SS format
    time_window_end: Optional[str] = None  # HH:MM:SS format
    is_due: bool
    time_until_next_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class CaptureValidationResult(BaseModel):
    """Result of capture interval validation"""

    original_interval_seconds: int
    validated_interval_seconds: int
    is_valid: bool
    validation_error: Optional[str] = None
    adjusted: bool = False

    model_config = ConfigDict(from_attributes=True)


class CaptureReadinessValidationResult(BaseModel):
    """Result of comprehensive capture readiness validation for scheduler trust model"""

    valid: bool
    error: Optional[str] = None
    error_type: Optional[str] = None
    camera: Optional[Any] = None  # Camera model instance
    timelapse: Optional[Any] = None  # Timelapse model instance
    next_capture_time: Optional[datetime] = None
    # Direct fields for backward compatibility with tests
    camera_id: Optional[int] = None
    timelapse_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    def __init__(self, **data):
        """Initialize with backward compatibility for camera_id/timelapse_id."""
        # If camera_id/timelapse_id are provided but camera/timelapse objects aren't,
        # create simple objects with id attributes
        if data.get("camera_id") is not None and data.get("camera") is None:
            # Create a simple object with id attribute
            camera_id = data["camera_id"]
            data["camera"] = type("Camera", (), {"id": camera_id})()

        if data.get("timelapse_id") is not None and data.get("timelapse") is None:
            # Create a simple object with id attribute
            timelapse_id = data["timelapse_id"]
            data["timelapse"] = type("Timelapse", (), {"id": timelapse_id})()

        super().__init__(**data)

        # Set direct fields from objects if they exist
        if self.camera and hasattr(self.camera, "id"):
            self.camera_id = self.camera.id
        if self.timelapse and hasattr(self.timelapse, "id"):
            self.timelapse_id = self.timelapse.id


class CaptureDueCheckResult(BaseModel):
    """Result of capture due check"""

    camera_id: int
    is_due: bool
    last_capture_time: Optional[datetime] = None
    next_capture_time: Optional[datetime] = None
    interval_seconds: int
    grace_period_seconds: int
    time_since_last_seconds: Optional[int] = None
    reason: Optional[str] = None  # Why capture is/isn't due

    model_config = ConfigDict(from_attributes=True)


class CaptureCountEstimate(BaseModel):
    """Estimate of capture count for a time period"""

    start_time: datetime
    end_time: datetime
    interval_seconds: int
    estimated_captures: int
    total_period_seconds: int
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    window_restricted: bool = False
    captures_per_day: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# TIME WINDOW MODELS
# ====================================================================


class TimeWindowStatus(BaseModel):
    """Time window operational status model"""

    is_active: bool = Field(..., description="Whether camera should be capturing now")
    has_window: bool = Field(..., description="Whether time window is configured")
    next_start: Optional[datetime] = Field(
        default=None, description="When window will next start"
    )
    next_end: Optional[datetime] = Field(
        default=None, description="When window will next end"
    )
    window_duration: Optional[int] = Field(
        default=None, description="Daily window duration in seconds"
    )
    current_time: datetime = Field(..., description="Current timestamp")

    model_config = ConfigDict(from_attributes=True)


class TimeWindowValidationResult(BaseModel):
    """Time window validation result model"""

    is_valid: bool = Field(
        ..., description="Whether the time window configuration is valid"
    )
    start_time: Optional[str] = Field(
        default=None, description="Validated start time (HH:MM:SS)"
    )
    end_time: Optional[str] = Field(
        default=None, description="Validated end time (HH:MM:SS)"
    )
    error_message: Optional[str] = Field(
        default=None, description="Validation error message if invalid"
    )
    is_overnight: bool = Field(
        default=False, description="Whether this is an overnight window"
    )
    duration_seconds: Optional[int] = Field(
        default=None, description="Window duration in seconds"
    )

    model_config = ConfigDict(from_attributes=True)


class TimeWindowCalculationRequest(BaseModel):
    """Request model for time window calculations"""

    current_time: datetime = Field(..., description="Current datetime for calculations")
    window_start: Optional[str] = Field(
        default=None, description="Window start time (HH:MM:SS)"
    )
    window_end: Optional[str] = Field(
        default=None, description="Window end time (HH:MM:SS)"
    )

    model_config = ConfigDict(from_attributes=True)


class CaptureCountEstimateRequest(BaseModel):
    """Request model for capture count estimation"""

    start_time: datetime = Field(..., description="Period start time")
    end_time: datetime = Field(..., description="Period end time")
    interval_seconds: int = Field(..., ge=1, description="Capture interval in seconds")
    time_window_start: Optional[str] = Field(
        default=None, description="Daily window start (HH:MM:SS)"
    )
    time_window_end: Optional[str] = Field(
        default=None, description="Daily window end (HH:MM:SS)"
    )

    model_config = ConfigDict(from_attributes=True)


class ActiveTimePeriodRequest(BaseModel):
    """Request model for active time calculation"""

    start_date: date = Field(..., description="Period start date")
    end_date: date = Field(..., description="Period end date")
    window_start: Optional[str] = Field(
        default=None, description="Daily window start (HH:MM:SS)"
    )
    window_end: Optional[str] = Field(
        default=None, description="Daily window end (HH:MM:SS)"
    )

    model_config = ConfigDict(from_attributes=True)


class ActiveTimePeriodResult(BaseModel):
    """Result model for active time calculation"""

    total_days: int = Field(..., description="Total days in period")
    active_duration_seconds: int = Field(
        ..., description="Total active time in seconds"
    )
    daily_window_seconds: Optional[int] = Field(
        default=None, description="Daily window duration in seconds"
    )
    has_time_restrictions: bool = Field(
        ..., description="Whether time window restrictions apply"
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# THUMBNAIL VERIFICATION MODELS
# ====================================================================


class ThumbnailVerificationResult(BaseModel):
    """Result of thumbnail file verification for a single image"""

    image_id: int
    camera_id: int
    timelapse_id: Optional[int] = None
    thumbnail_exists: bool = False
    small_exists: bool = False
    thumbnail_path: Optional[str] = None
    small_path: Optional[str] = None
    thumbnail_size_bytes: Optional[int] = None
    small_size_bytes: Optional[int] = None
    missing_files: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    verified_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ThumbnailVerificationSummary(BaseModel):
    """Summary of bulk thumbnail verification results"""

    total_images_checked: int = 0
    images_with_thumbnails: int = 0
    images_with_small: int = 0
    images_missing_thumbnails: int = 0
    images_missing_small: int = 0
    images_missing_both: int = 0
    total_missing_files: int = 0
    verification_errors: int = 0
    total_thumbnail_size_mb: float = 0.0
    total_small_size_mb: float = 0.0
    verification_started_at: datetime
    verification_completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ThumbnailRepairRequest(BaseModel):
    """Request model for thumbnail repair operations"""

    image_ids: Optional[List[int]] = None  # Specific images to repair
    camera_ids: Optional[List[int]] = None  # All images from specific cameras
    timelapse_ids: Optional[List[int]] = None  # All images from specific timelapses
    repair_missing_thumbnails: bool = True
    repair_missing_small: bool = True
    priority: JobPriority = Field(default=JobPriority.MEDIUM, description="Job priority for repair jobs")
    force_regenerate: bool = False  # Regenerate even if files exist

    model_config = ConfigDict(from_attributes=True)


class ThumbnailRepairResult(BaseModel):
    """Result of thumbnail repair operations"""

    success: bool
    repair_jobs_queued: int = 0
    images_processed: int = 0
    errors: List[str] = Field(default_factory=list)
    repair_started_at: datetime
    estimated_completion_time: Optional[datetime] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# ORPHANED FILE REPAIR MODELS
# ====================================================================


class OrphanedFileResult(BaseModel):
    """Result of orphaned file analysis for a single file"""

    file_path: str = Field(..., description="Full path to the orphaned file")
    file_type: str = Field(..., description="Type of file: thumbnail or small")
    file_size_bytes: int = Field(..., description="Size of the file in bytes")
    camera_id: Optional[int] = Field(
        None, description="Camera ID extracted from directory structure"
    )
    timelapse_id: Optional[int] = Field(
        None, description="Timelapse ID extracted from directory structure"
    )
    potential_image_id: Optional[int] = Field(
        None, description="Best guess image ID match"
    )
    structure_type: str = Field(
        ..., description="File structure type: legacy or timelapse"
    )
    match_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in the match (0.0-1.0)"
    )
    timestamp_extracted: Optional[datetime] = Field(
        None, description="Timestamp extracted from filename if possible"
    )
    can_repair: bool = Field(
        default=False, description="Whether this file can be automatically repaired"
    )
    repair_reason: Optional[str] = Field(
        None, description="Reason why file can/cannot be repaired"
    )
    error: Optional[str] = Field(None, description="Any error in processing this file")
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When this file was analyzed"
    )

    model_config = ConfigDict(from_attributes=True)


class OrphanedFileScanSummary(BaseModel):
    """Summary of orphaned file filesystem scan results"""

    total_files_scanned: int = 0
    orphaned_files_found: int = 0
    matched_files: int = 0
    unmatched_files: int = 0
    repair_candidates: int = 0
    legacy_structure_files: int = 0
    timelapse_structure_files: int = 0
    total_orphaned_size_mb: float = 0.0
    scan_started_at: datetime
    scan_completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    directories_scanned: int = 0
    scan_errors: int = 0

    model_config = ConfigDict(from_attributes=True)


class OrphanFileRepairRequest(BaseModel):
    """Request model for orphaned file repair operations"""

    file_paths: Optional[List[str]] = Field(
        None, description="Specific orphaned files to repair"
    )
    camera_ids: Optional[List[int]] = Field(
        None, description="Repair orphaned files for specific cameras"
    )
    timelapse_ids: Optional[List[int]] = Field(
        None, description="Repair orphaned files for specific timelapses"
    )
    structure_type: Optional[str] = Field(
        None,
        description="Only repair files from specific structure: legacy or timelapse",
    )
    min_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum match confidence for automatic repair",
    )
    repair_action: str = Field(
        default="update_database",
        description="Repair action: update_database or queue_regeneration",
    )
    force_repair: bool = Field(
        default=False, description="Force repair even for low confidence matches"
    )
    delete_unmatched: bool = Field(
        default=False, description="Delete orphaned files that cannot be matched"
    )

    model_config = ConfigDict(from_attributes=True)


class OrphanFileRepairResult(BaseModel):
    """Result of orphaned file repair operations"""

    success: bool
    files_processed: int = 0
    files_repaired: int = 0
    database_updates: int = 0
    regeneration_jobs_queued: int = 0
    files_deleted: int = 0
    files_skipped: int = 0
    errors: List[str] = Field(default_factory=list)
    repair_started_at: datetime
    repair_completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    storage_recovered_mb: float = 0.0
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# THUMBNAIL JOB MODELS
# ====================================================================


class ThumbnailGenerationJobCreate(BaseModel):
    """Model for creating thumbnail generation jobs"""

    image_id: int = Field(..., description="ID of the image to generate thumbnails for")
    priority: ThumbnailJobPriority = Field(
        default=ThumbnailJobPriority.MEDIUM,
        description="Job priority: high, medium, low",
    )
    status: ThumbnailJobStatus = Field(
        default=ThumbnailJobStatus.PENDING, description="Initial job status"
    )
    job_type: ThumbnailJobType = Field(
        default=ThumbnailJobType.SINGLE, description="Job type: single, bulk"
    )

    model_config = ConfigDict(from_attributes=True)


class ThumbnailGenerationJob(BaseModel):
    """Complete thumbnail generation job model"""

    id: int
    image_id: int
    priority: ThumbnailJobPriority
    status: ThumbnailJobStatus
    job_type: ThumbnailJobType
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    retry_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ThumbnailJobStatistics(BaseModel):
    """Statistics for thumbnail job queue monitoring"""

    total_jobs_24h: int = 0
    pending_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs_24h: int = 0
    failed_jobs_24h: int = 0
    cancelled_jobs_24h: int = 0
    avg_processing_time_ms: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class BulkThumbnailRequest(BaseModel):
    """Request model for bulk thumbnail generation"""

    image_ids: List[int] = Field(
        ..., description="List of image IDs to generate thumbnails for"
    )
    priority: ThumbnailJobPriority = Field(
        default=ThumbnailJobPriority.MEDIUM, description="Job priority for all images"
    )

    model_config = ConfigDict(from_attributes=True)


class BulkThumbnailResponse(BaseModel):
    """Response model for bulk thumbnail generation"""

    total_requested: int = Field(..., description="Total number of images requested")
    jobs_created: int = Field(
        default=0, description="Number of jobs successfully created"
    )
    jobs_failed: int = Field(
        default=0, description="Number of jobs that failed to create"
    )
    created_job_ids: List[int] = Field(
        default_factory=list, description="IDs of successfully created jobs"
    )
    failed_image_ids: List[int] = Field(
        default_factory=list, description="IDs of images that failed to queue"
    )

    model_config = ConfigDict(from_attributes=True)
