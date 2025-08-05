# backend/app/dependencies/__init__.py
"""
Modern Dependency Injection System for Timelapser v4.

This package provides a clean, organized, and maintainable dependency injection
system that eliminates the repetitive patterns found in the original dependencies.py.

Architecture:
- BaseFactory: Common patterns for all dependency factories
- ServiceRegistry: Singleton management with proper lifecycle
- Specialized factories for different service types
- Auto-generated type annotations
- Centralized import management to avoid circular dependencies

Usage:
    from app.dependencies import get_camera_service, CameraServiceDep

    @router.get("/cameras")
    async def list_cameras(camera_service: CameraServiceDep):
        return await camera_service.get_all_cameras()
"""

# Import all the main dependency functions for backward compatibility
from .database import get_async_database, get_sync_database
from .async_services import (
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
from .sync_services import (
    get_sync_settings_service,
    get_sync_video_service,
    get_rtsp_service,
)
from .scheduling import (
    get_time_window_service,
    get_scheduling_service,
    get_job_queue_service,
    get_sync_time_window_service,
    get_sync_scheduling_service,
    get_sync_job_queue_service,
    get_scheduler_service,
)
from .pipelines import (
    get_thumbnail_pipeline,
    get_corruption_pipeline,
    get_video_pipeline,
    get_async_video_pipeline,
    get_video_job_service,
    get_overlay_integration_service,
)
from .workflow import (
    get_async_rtsp_service,
    get_workflow_orchestrator_service,
)
from .specialized import (
    get_scheduled_job_operations,
)
from .global_state import (
    set_scheduler_worker,
    get_scheduler_worker,
    clear_settings_service_instances,
)

from .type_annotations import (
    AsyncDatabaseDep,
    SyncDatabaseDep,
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
    SyncSettingsServiceDep,
    SyncVideoServiceDep,
    RTSPServiceDep,
    AsyncRTSPServiceDep,
    WorkflowOrchestratorServiceDep,
    TimeWindowServiceDep,
    SyncTimeWindowServiceDep,
    SchedulingServiceDep,
    SyncSchedulingServiceDep,
    JobQueueServiceDep,
    SyncJobQueueServiceDep,
    SchedulerServiceDep,
    ThumbnailPipelineDep,
    CorruptionPipelineDep,
    VideoPipelineDep,
    AsyncVideoPipelineDep,
    VideoJobServiceDep,
    OverlayIntegrationServiceDep,
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
    # Type annotations (imported from type_annotations.py)
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
    "ThumbnailPipelineDep",
    "CorruptionPipelineDep",
    "VideoPipelineDep",
    "AsyncVideoPipelineDep",
    "VideoJobServiceDep",
    "OverlayIntegrationServiceDep",
    "WorkflowOrchestratorServiceDep",
    "TimeWindowServiceDep",
    "SyncTimeWindowServiceDep",
    "SchedulingServiceDep",
    "SyncSchedulingServiceDep",
    "JobQueueServiceDep",
    "SyncJobQueueServiceDep",
    "SchedulerServiceDep",
    "ScheduledJobOperationsDep",
]
