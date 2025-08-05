"""
Typed response models for corruption pipeline operations.

These models provide type-safe attributes and compile-time safety
for corruption detection operations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class FastDetectionResult:
    """Result from fast corruption detection."""

    is_corrupted: bool
    corruption_score: float
    detection_time_ms: float
    confidence_level: float
    detected_issues: List[str]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class HeavyDetectionResult:
    """Result from heavy corruption detection."""

    is_corrupted: bool
    corruption_score: float
    detection_time_ms: float
    confidence_level: float
    detailed_analysis: Dict[str, Any]
    detected_issues: List[str]
    quality_metrics: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CorruptionSettings:
    """System-wide corruption detection settings."""

    enabled: bool
    fast_detection_enabled: bool
    heavy_detection_enabled: bool
    corruption_threshold: float
    retry_enabled: bool
    degraded_mode_enabled: bool
    failure_threshold: int


@dataclass
class CameraCorruptionSettings:
    """Camera-specific corruption detection settings."""

    camera_id: int
    enabled: bool
    threshold: float
    fast_detection_enabled: bool
    heavy_detection_enabled: bool
    retry_enabled: bool
    degraded_mode_enabled: bool
    failure_threshold: int


@dataclass
class CameraCorruptionMetadata:
    """Camera corruption detection metadata and status."""

    camera_id: int
    total_images: int
    corrupted_images: int
    corruption_rate: float
    consecutive_failures: int
    degraded_mode_active: bool
    last_corruption_detected: Optional[datetime] = None
    last_successful_detection: Optional[datetime] = None
    health_score: float = 1.0


@dataclass
class ScoreCalculationData:
    """Data for corruption score calculation."""

    fast_score: float
    heavy_score: Optional[float]
    fast_weight: float
    heavy_weight: float
    combined_score: float
    threshold: float
    is_corrupted: bool
    calculation_method: str


@dataclass
class RetryDecision:
    """Decision data for corruption detection retry logic."""

    should_retry: bool
    retry_count: int
    max_retries: int
    reason: str
    next_retry_delay_ms: int
    degraded_mode_triggered: bool = False


@dataclass
class CameraHealthDetails:
    """Detailed camera health information."""

    camera_id: int
    health_score: float
    status: str
    recent_corruption_rate: float
    consecutive_failures: int
    degraded_mode_active: bool
    issues: List[str]
    recommendations: List[str]
    last_assessment: Optional[datetime] = None


@dataclass
class TimelapseQualityStats:
    """Timelapse quality statistics."""

    timelapse_id: int
    total_images: int
    corrupted_images: int
    corruption_rate: float
    average_quality_score: float
    quality_trend: str
    last_analysis: Optional[datetime] = None


@dataclass
class CameraFailureStats:
    """Camera failure statistics."""

    camera_id: int
    failure_count_24h: int
    failure_count_7d: int
    failure_count_30d: int
    failure_rate_24h: float
    failure_rate_7d: float
    failure_rate_30d: float
    most_common_failure_type: Optional[str] = None
    last_failure: Optional[datetime] = None


# Statistics Response Models
@dataclass
class DetectionStatsData:
    """Detection statistics data."""

    total_detections: int
    images_saved: int
    images_discarded: int
    images_retried: int
    detection_efficiency_percent: float
    discard_rate_percent: float


@dataclass
class QualityMetricsData:
    """Quality metrics data."""

    avg_corruption_score: float
    min_corruption_score: float
    max_corruption_score: float


@dataclass
class PerformanceMetricsData:
    """Performance metrics data."""

    avg_processing_time_ms: float


@dataclass
class HealthMetricsData:
    """Health metrics data."""

    consecutive_failures: int
    lifetime_glitch_count: int
    degraded_mode_active: bool
    last_degraded_at: Optional[datetime]


@dataclass
class CameraSettingsData:
    """Camera settings data."""

    heavy_detection_enabled: bool


@dataclass
class CameraStatisticsResponse:
    """Camera statistics response model."""

    camera_id: int
    detection_stats: DetectionStatsData
    quality_metrics: QualityMetricsData
    performance_metrics: PerformanceMetricsData
    health_metrics: HealthMetricsData
    settings: CameraSettingsData
    most_recent_detection: Optional[datetime]
    generated_at: datetime


@dataclass
class TimelapseStatisticsResponse:
    """Timelapse statistics response model."""

    timelapse_id: int
    image_stats: Dict[str, Any]  # Can be refined further if needed
    quality_metrics: Dict[str, float]  # Can be refined further if needed
    generated_at: datetime
