# backend/app/dependencies.py
"""
Modern Dependency Injection System for Timelapser v4.

Clean, organized dependency injection using factory patterns and proper service registry.
Eliminates the 485-line mess of repetitive code from the original implementation.

Architecture:
- Factory patterns for common service types
- ServiceRegistry for proper singleton management
- Organized by service category
- Type-safe dependency injection
- Clean separation of concerns
"""

# Re-export all dependency functions and type annotations from organized modules
from .dependencies.database import get_async_database, get_sync_database
from .dependencies.async_services import (
    get_camera_service,
    get_video_service,
    get_timelapse_service,
    get_image_service,
    get_settings_service,
    get_weather_manager,
    get_statistics_service,
    get_logger_service,
    get_health_service,
    get_admin_service,
    get_overlay_service,
    get_overlay_job_service,
)
from .dependencies.sync_services import (
    get_sync_settings_service,
    get_sync_video_service,
    get_rtsp_service,
)
from .dependencies.scheduling import (
    get_time_window_service,
    get_scheduling_service,
    get_job_queue_service,
    get_sync_time_window_service,
    get_sync_scheduling_service,
    get_sync_job_queue_service,
    get_scheduler_service,
)
from .dependencies.pipelines import (
    get_thumbnail_pipeline,
    get_corruption_pipeline,
    get_video_pipeline,
    get_async_video_pipeline,
    get_video_job_service,
    get_overlay_integration_service,
)
from .dependencies.workflow import (
    get_async_rtsp_service,
    get_workflow_orchestrator_service,
)
from .dependencies.specialized import (
    get_scheduled_job_operations,
)
from .dependencies.global_state import (
    set_scheduler_worker,
    get_scheduler_worker,
    clear_settings_service_instances,
)

# Import all type annotations explicitly to avoid F403/F405 warnings
from .dependencies.type_annotations import (
    # Database
    AsyncDatabaseDep,
    SyncDatabaseDep,
    # Async Services
    CameraServiceDep,
    VideoServiceDep,
    TimelapseServiceDep,
    ImageServiceDep,
    SettingsServiceDep,
    WeatherManagerDep,
    StatisticsServiceDep,
    LoggerServiceDep,
    HealthServiceDep,
    AdminServiceDep,
    OverlayServiceDep,
    OverlayJobServiceDep,
    # Sync Services
    SyncSettingsServiceDep,
    SyncVideoServiceDep,
    RTSPServiceDep,
    # Workflow
    AsyncRTSPServiceDep,
    WorkflowOrchestratorServiceDep,
    # Scheduling
    TimeWindowServiceDep,
    SyncTimeWindowServiceDep,
    SchedulingServiceDep,
    SyncSchedulingServiceDep,
    JobQueueServiceDep,
    SyncJobQueueServiceDep,
    SchedulerServiceDep,
    # Pipelines
    ThumbnailPipelineDep,
    CorruptionPipelineDep,
    VideoPipelineDep,
    AsyncVideoPipelineDep,
    VideoJobServiceDep,
    OverlayIntegrationServiceDep,
    # Specialized
    ScheduledJobOperationsDep,
)

__all__ = [
    # Database
    "get_async_database",
    "get_sync_database",
    # Async Services
    "get_camera_service",
    "get_video_service",
    "get_timelapse_service",
    "get_image_service",
    "get_settings_service",
    "get_weather_manager",
    "get_statistics_service",
    "get_logger_service",
    "get_health_service",
    "get_admin_service",
    "get_overlay_service",
    "get_overlay_job_service",
    # Sync Services
    "get_sync_settings_service",
    "get_sync_video_service",
    "get_rtsp_service",
    # Scheduling
    "get_time_window_service",
    "get_scheduling_service",
    "get_job_queue_service",
    "get_sync_time_window_service",
    "get_sync_scheduling_service",
    "get_sync_job_queue_service",
    "get_scheduler_service",
    # Pipelines
    "get_thumbnail_pipeline",
    "get_corruption_pipeline",
    "get_video_pipeline",
    "get_async_video_pipeline",
    "get_video_job_service",
    "get_overlay_integration_service",
    # Workflow
    "get_async_rtsp_service",
    "get_workflow_orchestrator_service",
    # Specialized
    "get_scheduled_job_operations",
    # Global State
    "set_scheduler_worker",
    "get_scheduler_worker",
    "clear_settings_service_instances",
    # Type Annotations
    "AsyncDatabaseDep",
    "SyncDatabaseDep",
    "CameraServiceDep",
    "VideoServiceDep",
    "TimelapseServiceDep",
    "ImageServiceDep",
    "SettingsServiceDep",
    "WeatherManagerDep",
    "StatisticsServiceDep",
    "LoggerServiceDep",
    "HealthServiceDep",
    "AdminServiceDep",
    "OverlayServiceDep",
    "OverlayJobServiceDep",
    "SyncSettingsServiceDep",
    "SyncVideoServiceDep",
    "RTSPServiceDep",
    "AsyncRTSPServiceDep",
    "WorkflowOrchestratorServiceDep",
    "TimeWindowServiceDep",
    "SyncTimeWindowServiceDep",
    "SchedulingServiceDep",
    "SyncSchedulingServiceDep",
    "JobQueueServiceDep",
    "SyncJobQueueServiceDep",
    "SchedulerServiceDep",
    "ThumbnailPipelineDep",
    "CorruptionPipelineDep",
    "VideoPipelineDep",
    "AsyncVideoPipelineDep",
    "VideoJobServiceDep",
    "OverlayIntegrationServiceDep",
    "ScheduledJobOperationsDep",
]
