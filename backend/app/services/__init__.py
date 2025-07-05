"""
Services module for Timelapser v4.

This module contains all business logic services that coordinate between
the data layer and API layer. Services handle complex operations and
orchestrate multiple database operations following composition pattern.

Available Services:
- CameraService: Camera lifecycle and health management
- VideoService: Video metadata and generation coordination
- VideoAutomationService: Automated video generation workflows
- TimelapseService: Timelapse entity lifecycle management
- ImageService: Image metadata and serving
- ImageCaptureService: RTSP image capture coordination
- CorruptionService: Image quality analysis
- SettingsService: System configuration management
- StatisticsService: System-wide metrics aggregation
- HealthService: System health monitoring
- LogService: Application logging
- SchedulingService: Task scheduling coordination
- TimeWindowService: Time window calculations
- WorkerCorruptionIntegrationService: Worker process corruption integration
- RTSPCaptureService: High-level RTSP capture orchestration

Subdirectory Services:
- CorruptionDetection: Advanced corruption analysis (in corruption_detection/)
- WeatherService: Weather data integration (in weather/)
"""

# Core business logic services
from .camera_service import CameraService, SyncCameraService
from .video_service import VideoService, SyncVideoService
from .video_automation_service import VideoAutomationService
from .timelapse_service import TimelapseService
from .image_service import ImageService
from .image_capture_service import ImageCaptureService
from .corruption_service import CorruptionService
from .settings_service import SettingsService, SyncSettingsService
from .statistics_service import StatisticsService, SyncStatisticsService
from .health_service import HealthService
from .log_service import LogService
from .scheduling_service import SchedulingService
from .time_window_service import TimeWindowService

from .rtsp_capture_service import RTSPCaptureService

# Service aliases for backward compatibility
image_capture = ImageCaptureService
video_automation = VideoAutomationService

__all__ = [
    # Core services
    "CameraService",
    "SyncCameraService",
    "VideoService",
    "SyncVideoService",
    "VideoAutomationService",
    "TimelapseService",
    "ImageService",
    "ImageCaptureService",
    "CorruptionService",
    "SettingsService",
    "SyncSettingsService",
    "StatisticsService",
    "SyncStatisticsService",
    "HealthService",
    "LogService",
    "SchedulingService",
    "TimeWindowService",
    "RTSPCaptureService",
    # Aliases
    "image_capture",
    "video_automation",
]
