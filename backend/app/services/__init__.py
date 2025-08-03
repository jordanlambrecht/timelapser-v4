"""
Services module for Timelapser v4.

This module contains all business logic services that coordinate between
the data layer and API layer. Services handle complex operations and
orchestrate multiple database operations following composition pattern.

Available Services:
- CameraService: Camera lifecycle and health management
- VideoService: Video metadata and generation coordination (LEGACY)
- VideoAutomationService: Automated video generation workflows (LEGACY)
- VideoPipeline: New unified video generation pipeline (3-service architecture)
- TimelapseService: Timelapse entity lifecycle management
- ImageService: Image metadata and serving
- RTSPService: Unified RTSP capture operations (capture pipeline)
- WorkflowOrchestratorService: Complete 12-step capture workflow orchestration
- CorruptionService: Image quality analysis
- SettingsService: System configuration management
- StatisticsService: System-wide metrics aggregation
- HealthService: System health monitoring
- LogService: Application logging
- SchedulingService: Task scheduling coordination
- TimeWindowService: Time window calculations
- WorkerCorruptionIntegrationService: Worker process corruption integration
# Note: RTSPCaptureService and ImageCaptureService consolidated into RTSPService

Subdirectory Services:
- CorruptionDetection: Advanced corruption analysis (in corruption_detection/)
- WeatherService: Weather data integration (in weather/)
"""

# Core business logic services
from .camera_service import CameraService, SyncCameraService
from .capture_pipeline import AsyncRTSPService, RTSPService, WorkflowOrchestratorService
from .health_service import HealthService
from .image_service import ImageService

# LogService removed - use LoggerService from logger.logger_service instead
from .scheduling import (
    JobQueueService,
    SchedulerService,
    SchedulingService,
    SyncJobQueueService,
    SyncSchedulingService,
    SyncTimeWindowService,
    TimeWindowService,
)

# from .corruption_service import CorruptionService  # Replaced by corruption_pipeline
from .settings_service import SettingsService, SyncSettingsService
from .statistics_service import StatisticsService, SyncStatisticsService
from .timelapse_service import TimelapseService

# from .video_service import VideoService, SyncVideoService  # REMOVED: Use video_pipeline instead
# from .video_automation_service import VideoAutomationService  # REMOVED: Use video_pipeline instead
from .video_pipeline import create_video_pipeline  # NEW: Unified video pipeline

# Note: RTSPCaptureService and ImageCaptureService have been consolidated into RTSPService

# Service aliases for backward compatibility
rtsp_service = RTSPService
# video_automation = VideoAutomationService  # REMOVED: Use video_pipeline instead

__all__ = [
    # Core services
    "CameraService",
    "SyncCameraService",
    # "VideoService",  # REMOVED: Use video_pipeline instead
    # "SyncVideoService",  # REMOVED: Use video_pipeline instead
    # "VideoAutomationService",  # REMOVED: Use video_pipeline instead
    "create_video_pipeline",  # NEW: Unified video pipeline
    "TimelapseService",
    "ImageService",
    "RTSPService",
    "AsyncRTSPService",
    "WorkflowOrchestratorService",
    # "CorruptionService",  # Replaced by corruption_pipeline
    "SettingsService",
    "SyncSettingsService",
    "StatisticsService",
    "SyncStatisticsService",
    "HealthService",
    # "LogService",  # REMOVED: Use LoggerService from logger.logger_service instead
    "SchedulingService",
    "SyncSchedulingService",
    "TimeWindowService",
    "SyncTimeWindowService",
    "SchedulerService",
    "JobQueueService",
    "SyncJobQueueService",
    # Aliases
    "rtsp_service",
    # "video_automation",  # REMOVED: Use video_pipeline instead
]
