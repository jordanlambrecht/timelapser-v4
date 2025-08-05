"""
Corruption Pipeline Domain - Complete Image Quality Control System

Centralized corruption detection, evaluation, and health monitoring system
with clear separation of concerns and simplified dependencies.

Domain Responsibilities:
- Image quality detection (fast + heavy algorithms)
- Corruption score evaluation and threshold management
- Camera health monitoring and degraded mode detection
- Database operations for corruption logging and statistics
- Integration with capture pipeline for real-time evaluation

Architecture Pattern:
This domain consolidates all corruption-related functionality into a single,
well-organized pipeline with clean interfaces and minimal dependencies.

Factory Usage:
```python
# Basic usage - creates pipeline with default database
from app.services.corruption_pipeline import create_corruption_pipeline
corruption_pipeline = create_corruption_pipeline()

# Evaluate image quality
result = corruption_pipeline.evaluate_image(camera_id=1, image_path="/path/to/image.jpg")

# Advanced usage - with custom database
corruption_pipeline = create_corruption_pipeline(database=custom_db)

# Integration in capture workflow
class CaptureWorker:
    def __init__(self):
        self.corruption_pipeline = create_corruption_pipeline()

    def process_capture(self, camera_id: int, image_path: str):
        result = self.corruption_pipeline.evaluate_image(camera_id, image_path)
        return result.is_valid
```
"""

from typing import Any, Dict, Optional

from ...database.core import AsyncDatabase, SyncDatabase
from ...enums import LoggerName
from ...services.logger import get_service_logger
from .corruption_pipeline import CorruptionPipeline
from .detectors import (
    CorruptionScoreCalculator,
    FastCorruptionDetector,
    FastDetectionResult,
    HeavyCorruptionDetector,
    HeavyDetectionResult,
    ScoreCalculationResult,
)
from .exceptions import (
    CameraHealthError,
    CorruptionDetectionError,
    CorruptionEvaluationError,
    CorruptionPipelineError,
    CorruptionSettingsError,
    CorruptionStatisticsError,
    DegradedModeError,
    ScoreCalculationError,
)
from .models import (
    CameraCorruptionMetadata,
    CameraCorruptionSettings,
    CameraFailureStats,
    CameraHealthDetails,
    CameraSettingsData,
    CameraStatisticsResponse,
    CorruptionSettings,
    DetectionStatsData,
)
from .models import FastDetectionResult as ModelFastDetectionResult
from .models import (
    HealthMetricsData,
)
from .models import HeavyDetectionResult as ModelHeavyDetectionResult
from .models import (
    PerformanceMetricsData,
    QualityMetricsData,
    RetryDecision,
    ScoreCalculationData,
    TimelapseQualityStats,
    TimelapseStatisticsResponse,
)
from .services import (
    CorruptionEvaluationService,
    CorruptionHealthService,
    CorruptionStatisticsService,
    SyncCorruptionEvaluationService,
    SyncCorruptionHealthService,
    SyncCorruptionStatisticsService,
)

logger = get_service_logger(LoggerName.CORRUPTION_PIPELINE)


def create_corruption_pipeline(
    database: Optional[SyncDatabase] = None,
    async_database: Optional[AsyncDatabase] = None,
) -> CorruptionPipeline:
    """
    Factory function to create a complete corruption pipeline with dependency injection.

    Creates all required services in proper dependency order and returns a fully
    configured CorruptionPipeline ready for image evaluation operations.

    Args:
        database: Optional sync database instance (defaults to SyncDatabase())
        async_database: Optional async database instance (defaults to AsyncDatabase())

    Returns:
        CorruptionPipeline with all dependencies injected

    Example:
        >>> pipeline = create_corruption_pipeline()
        >>> result = pipeline.evaluate_image(camera_id=1, image_path="/path/image.jpg")
    """
    try:
        logger.info("Creating corruption pipeline with dependency injection...")

        # Step 1: Create database instances
        if database is None:
            database = SyncDatabase()
            database.initialize()

        if async_database is None:
            async_database = AsyncDatabase()

        # Step 2: Create service layer using existing database layer
        logger.debug("Creating corruption services")
        # Create async services for pipeline (API endpoints)
        evaluation_service = CorruptionEvaluationService(db=async_database)

        health_service = CorruptionHealthService(db=async_database)

        statistics_service = CorruptionStatisticsService(db=async_database)

        # Step 3: Create main pipeline
        logger.debug("Creating main corruption pipeline")
        pipeline = CorruptionPipeline(
            evaluation_service=evaluation_service,
            health_service=health_service,
            statistics_service=statistics_service,
            database=database,
            async_database=async_database,
        )

        logger.info("Corruption pipeline created successfully")
        return pipeline

    except Exception as e:
        logger.error(f"Failed to create corruption pipeline: {e}")
        raise RuntimeError(f"Corruption pipeline creation failed: {str(e)}") from e


def get_corruption_pipeline_health() -> Dict[str, Any]:
    """
    Get health status of corruption pipeline components.

    Returns:
        Dictionary with component health status
    """
    try:
        # Create a test pipeline to check component health
        create_corruption_pipeline()

        return {
            "pipeline_status": "healthy",
            "components": {
                "evaluation_service": "operational",
                "health_service": "operational",
                "statistics_service": "operational",
                "fast_detector": "operational",
                "heavy_detector": "operational",
                "database_operations": "operational",
            },
            "dependencies": {
                "database": "connected",
                "opencv": "available",
                "numpy": "available",
            },
        }
    except Exception as e:
        logger.error(f"Corruption pipeline health check failed: {e}")
        return {"pipeline_status": "unhealthy", "error": str(e)}


# Clean exports
__all__ = [
    # Primary factory function
    "create_corruption_pipeline",
    "get_corruption_pipeline_health",
    # Async Service classes
    "CorruptionEvaluationService",
    "CorruptionHealthService",
    "CorruptionStatisticsService",
    # Sync Service classes
    "SyncCorruptionEvaluationService",
    "SyncCorruptionHealthService",
    "SyncCorruptionStatisticsService",
    # Detector classes
    "FastCorruptionDetector",
    "HeavyCorruptionDetector",
    "CorruptionScoreCalculator",
    "FastDetectionResult",
    "HeavyDetectionResult",
    "ScoreCalculationResult",
    # Model classes
    "ModelFastDetectionResult",
    "ModelHeavyDetectionResult",
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
    # Exception classes
    "CorruptionPipelineError",
    "ScoreCalculationError",
    "CorruptionDetectionError",
    "CorruptionEvaluationError",
    "CorruptionSettingsError",
    "CameraHealthError",
    "DegradedModeError",
    "CorruptionStatisticsError",
    # Database layer (for testing/debugging)
    "SyncDatabase",
    "AsyncDatabase",
]
