# Per-camera corruption settings model for DB operations (used in camera_operations.py)
from pydantic import BaseModel
from typing import Optional

class CorruptionSettingsModel(BaseModel):
    corruption_detection_heavy: bool
    lifetime_glitch_count: int
    consecutive_corruption_failures: int
    degraded_mode_active: bool
# backend/app/models/corruption_model.py
"""
Pydantic Models for Corruption Detection System

Type-safe models for corruption detection data structures,
following Timelapser's existing architectural patterns.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class CorruptionSettings(BaseModel):
    """Global corruption detection settings"""

    corruption_detection_enabled: bool = True
    corruption_score_threshold: int = Field(default=70, ge=0, le=100)
    corruption_auto_discard_enabled: bool = False
    corruption_auto_disable_degraded: bool = False
    corruption_degraded_consecutive_threshold: int = Field(default=10, ge=1)
    corruption_degraded_time_window_minutes: int = Field(default=30, ge=5)
    corruption_degraded_failure_percentage: int = Field(default=50, ge=10, le=100)


class CameraCorruptionSettings(BaseModel):
    """Per-camera corruption detection settings"""

    corruption_detection_heavy: bool = False


class CorruptionLogEntry(BaseModel):
    """Database model for corruption log entries"""

    id: Optional[int] = None
    camera_id: int
    image_id: Optional[int] = None
    corruption_score: int = Field(ge=0, le=100)
    fast_score: Optional[int] = Field(default=None, ge=0, le=100)
    heavy_score: Optional[int] = Field(default=None, ge=0, le=100)
    detection_details: Dict[str, Any]
    action_taken: str
    processing_time_ms: Optional[int] = None
    created_at: Optional[datetime] = None


# Paginated corruption logs response model
class CorruptionLogsPage(BaseModel):
    logs: List[CorruptionLogEntry]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class CorruptionStats(BaseModel):
    """Corruption statistics for cameras and timelapses"""

    lifetime_glitch_count: int = 0
    recent_average_score: float = 100.0
    consecutive_corruption_failures: int = 0
    degraded_mode_active: bool = False
    last_degraded_at: Optional[datetime] = None


class CameraWithCorruption(BaseModel):
    """Camera model enhanced with corruption detection fields"""

    id: int
    name: str
    rtsp_url: str
    enabled: bool
    health_status: str

    # Corruption detection fields
    lifetime_glitch_count: int = 0
    consecutive_corruption_failures: int = 0
    corruption_detection_heavy: bool = False
    degraded_mode_active: bool = False
    last_degraded_at: Optional[datetime] = None


class ImageWithCorruption(BaseModel):
    """Image model enhanced with corruption detection fields"""

    id: int
    camera_id: int
    timelapse_id: Optional[int] = None
    file_path: str
    captured_at: datetime
    day_number: int

    # Corruption detection fields
    corruption_score: int = Field(default=100, ge=0, le=100)
    is_flagged: bool = False
    corruption_details: Optional[Dict[str, Any]] = None


class TimelapseWithCorruption(BaseModel):
    """Timelapse model enhanced with corruption detection fields"""

    id: int
    camera_id: int
    name: str
    status: str
    start_date: datetime

    # Corruption detection fields
    glitch_count: int = 0
    total_corruption_score: int = 0


class CorruptionDetectionRequest(BaseModel):
    """Request model for corruption detection API"""

    camera_id: int
    enable_heavy_detection: Optional[bool] = None
    custom_threshold: Optional[int] = Field(default=None, ge=0, le=100)


class CorruptionDetectionResponse(BaseModel):
    """Response model for corruption detection API"""

    camera_id: int
    is_valid: bool
    corruption_score: int = Field(ge=0, le=100)
    action_taken: str
    retry_attempted: bool
    processing_time_ms: float
    details: Dict[str, Any]


class CorruptionSystemStats(BaseModel):
    """System-wide corruption detection statistics"""

    total_cameras: int
    cameras_healthy: int
    cameras_monitoring: int
    cameras_degraded: int
    images_flagged_today: int
    images_flagged_week: int
    storage_saved_mb: float
    avg_processing_overhead_ms: float
    system_health_score: int = Field(ge=0, le=100)


class CorruptionHealthUpdate(BaseModel):
    """Model for corruption health status updates"""

    camera_id: int
    consecutive_failures: int
    degraded_mode_active: bool
    last_failure_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class CorruptionEventData(BaseModel):
    """SSE event data for corruption detection"""

    camera_id: int
    corruption_score: int
    is_corrupted: bool
    action_taken: str
    failed_checks: List[str]
    processing_time_ms: float


class CorruptionAnalysisStats(BaseModel):
    """Comprehensive corruption detection statistics"""

    total_detections: int = 0
    images_saved: int = 0
    images_discarded: int = 0
    images_retried: int = 0
    avg_corruption_score: float = 100.0
    min_corruption_score: int = 100
    max_corruption_score: int = 100
    avg_processing_time_ms: float = 0.0
    unique_cameras: int = 0
    most_recent_detection: Optional[datetime] = None


# API Response Models


class CorruptionStatsResponse(BaseModel):
    """Response for corruption statistics endpoint"""

    camera_stats: CorruptionStats
    recent_issues: List[Dict[str, Any]]
    quality_trend: List[Dict[str, Any]]


class CorruptionHistoryResponse(BaseModel):
    """Response for corruption history endpoint"""

    logs: List[CorruptionLogEntry]
    total_count: int
    page: int
    limit: int


class CorruptionSettingsResponse(BaseModel):
    """Response for corruption settings endpoint"""

    global_settings: CorruptionSettings
    camera_settings: Dict[int, CameraCorruptionSettings]
