# backend/app/services/corruption_pipeline/models/__init__.py
"""
Corruption Pipeline Models

Typed models for corruption detection responses and data structures.
"""

from .corruption_responses import (
    CameraCorruptionMetadata,
    CameraCorruptionSettings,
    CameraFailureStats,
    CameraHealthDetails,
    CameraSettingsData,
    CameraStatisticsResponse,
    CorruptionSettings,
    DetectionStatsData,
    FastDetectionResult,
    HealthMetricsData,
    HeavyDetectionResult,
    PerformanceMetricsData,
    QualityMetricsData,
    RetryDecision,
    ScoreCalculationData,
    TimelapseQualityStats,
    TimelapseStatisticsResponse,
)

__all__ = [
    "FastDetectionResult",
    "HeavyDetectionResult",
    "CorruptionSettings",
    "CameraCorruptionSettings",
    "CameraCorruptionMetadata",
    "ScoreCalculationData",
    "RetryDecision",
    "CameraHealthDetails",
    "TimelapseQualityStats",
    "CameraFailureStats",
    "DetectionStatsData",
    "QualityMetricsData",
    "PerformanceMetricsData",
    "HealthMetricsData",
    "CameraSettingsData",
    "CameraStatisticsResponse",
    "TimelapseStatisticsResponse",
]
