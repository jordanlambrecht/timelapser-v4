# backend/app/dependencies.py
"""
FastAPI Dependencies for Dependency Injection

Provides proper dependency injection for services following the target architecture.
All services receive database instances via dependency injection using FastAPI's Depends system.
"""

from typing import Annotated, TYPE_CHECKING
from fastapi import Depends

# Basic imports that don't cause circular dependencies
from .database import async_db, sync_db
from .database.core import AsyncDatabase, SyncDatabase

# Factory function imports (safe - no circular dependencies)
from .services.corruption_pipeline import create_corruption_pipeline
from .services.capture_pipeline import create_capture_pipeline
from .services.capture_pipeline.rtsp_service import RTSPService
from .services.video_pipeline import (
    create_video_pipeline,
    create_video_job_service,
    create_overlay_integration_service,
)

# Database operations imports (safe - no circular dependencies)
from .database.weather_operations import SyncWeatherOperations
from .database.scheduled_job_operations import ScheduledJobOperations

# Use TYPE_CHECKING for imports that might cause circular dependencies
if TYPE_CHECKING:
    from .services.video_pipeline.video_workflow_service import VideoWorkflowService
    from .services.camera_service import CameraService
    from .services.video_service import VideoService, SyncVideoService
    from .services.timelapse_service import TimelapseService
    from .services.image_service import ImageService
    from .services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
    from .services.capture_pipeline import WorkflowOrchestratorService
    from .services.settings_service import SettingsService, SyncSettingsService
    from .services.statistics_service import StatisticsService
    from .services.logger.logger_service import LoggerService
    from .services.weather.service import WeatherManager
    from .services.health_service import HealthService
    from .services.admin_service import AdminService
    from .services.overlay_pipeline import AsyncOverlayService
    from .services.overlay_pipeline.services.job_service import AsyncOverlayJobService
    from .services.scheduling.capture_timing_service import (
        CaptureTimingService,
        SyncCaptureTimingService,
    )
    from .services.scheduling.time_window_service import (
        TimeWindowService,
        SyncTimeWindowService,
    )
    from .services.scheduling.job_queue_service import (
        JobQueueService,
        SyncJobQueueService,
    )
    from .services.scheduling.scheduler_authority_service import SchedulerService
    from .database.thumbnail_job_operations import ThumbnailJobOperations
    from .database.overlay_job_operations import OverlayJobOperations
    from .database.sse_events_operations import SSEEventsOperations
    from .database.image_operations import AsyncImageOperations

# Global scheduler worker instance (set by main worker on startup)
_scheduler_worker_instance = None

# Global settings service instances (singleton pattern for performance)
_async_settings_service_instance = None
_sync_settings_service_instance = None

# NOTE: Service class imports are kept inline within functions to avoid circular dependencies
# Services often import each other, so delaying imports until runtime prevents import cycles


def set_scheduler_worker(scheduler_worker):
    """Set the global scheduler worker instance (called by main worker)"""
    global _scheduler_worker_instance
    _scheduler_worker_instance = scheduler_worker


def get_scheduler_worker():
    """Get the global scheduler worker instance"""
    global _scheduler_worker_instance
    return _scheduler_worker_instance


def clear_settings_service_instances():
    """Clear singleton settings service instances (for testing/restart)"""
    global _async_settings_service_instance, _sync_settings_service_instance
    _async_settings_service_instance = None
    _sync_settings_service_instance = None


# Database Dependencies
async def get_async_database() -> AsyncDatabase:
    """Get async database instance"""
    return async_db


def get_sync_database() -> SyncDatabase:
    """Get sync database instance"""
    return sync_db


# Async Service Dependencies
async def get_camera_service():
    """Get CameraService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.camera_service import CameraService

    # Use singleton settings service
    settings_service = await get_settings_service()
    # Create async RTSP service for connectivity testing
    async_rtsp_service = await get_async_rtsp_service()
    # Create scheduling service for capture scheduling
    scheduling_service = await get_scheduling_service()
    # Create scheduler authority service for immediate captures
    try:
        scheduler_authority_service = await get_scheduler_service()
    except RuntimeError:
        # SchedulerWorker not initialized yet - will be None
        scheduler_authority_service = None

    return CameraService(
        async_db,
        sync_db=sync_db,
        settings_service=settings_service,
        rtsp_service=async_rtsp_service,
        scheduling_service=scheduling_service,
        scheduler_authority_service=scheduler_authority_service,
    )


async def get_video_service():
    """Get VideoService with async and sync database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.video_service import VideoService

    settings_service = await get_settings_service()
    return VideoService(async_db, sync_db=sync_db, settings_service=settings_service)


async def get_timelapse_service():
    """Get TimelapseService with async database dependency injection"""
    # Inline imports to avoid circular dependencies
    from .services.timelapse_service import TimelapseService
    from .services.health_service import HealthService
    from .services.image_service import ImageService
    from .services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline

    # Use singleton settings service
    settings_service = await get_settings_service()
    health_service = HealthService(async_db)
    image_service = ImageService(async_db, settings_service)
    thumbnail_pipeline = ThumbnailPipeline(async_database=async_db)
    return TimelapseService(
        async_db,
        image_service=image_service,
        settings_service=settings_service,
        thumbnail_pipeline=thumbnail_pipeline,
    )


async def get_image_service():
    """Get ImageService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.image_service import ImageService

    # Use singleton settings service
    settings_service = await get_settings_service()
    return ImageService(async_db, settings_service)


async def get_thumbnail_pipeline():
    """Get ThumbnailPipeline with database and settings service dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline

    # Use singleton sync settings service
    settings_service = get_sync_settings_service()
    return ThumbnailPipeline(database=sync_db, settings_service=settings_service)


async def get_corruption_pipeline():
    """Get CorruptionPipeline with async database dependency injection"""
    return create_corruption_pipeline(async_database=async_db)


def get_rtsp_service():
    """Get RTSPService with sync database dependency injection"""
    # Use singleton sync settings service
    sync_settings_service = get_sync_settings_service()
    return RTSPService(sync_db, async_db, sync_settings_service)


async def get_async_rtsp_service():
    """Get capture pipeline AsyncRTSPService with wrapped sync RTSP service"""
    # Inline import to avoid circular dependencies
    from .services.capture_pipeline import AsyncRTSPService

    sync_rtsp_service = get_rtsp_service()
    return AsyncRTSPService(sync_rtsp_service)


def get_workflow_orchestrator_service():
    """Get WorkflowOrchestratorService with complete dependency injection through factory pattern"""
    return create_capture_pipeline()


async def get_settings_service():
    """Get SettingsService with async database dependency injection (singleton pattern)"""
    global _async_settings_service_instance
    if _async_settings_service_instance is None:
        # Inline import to avoid circular dependencies
        from .services.settings_service import SettingsService

        _async_settings_service_instance = SettingsService(async_db)
    return _async_settings_service_instance


def get_sync_settings_service():
    """Get SyncSettingsService with sync database dependency injection (singleton pattern)"""
    global _sync_settings_service_instance
    if _sync_settings_service_instance is None:
        # Inline import to avoid circular dependencies
        from .services.settings_service import SyncSettingsService

        _sync_settings_service_instance = SyncSettingsService(sync_db)
    return _sync_settings_service_instance


async def get_weather_manager():
    """Get WeatherManager with database and settings service dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.weather.service import WeatherManager

    # Use singleton async settings service
    settings_service = await get_settings_service()
    weather_operations = SyncWeatherOperations(sync_db)
    return WeatherManager(weather_operations, settings_service)


async def get_statistics_service():
    """Get StatisticsService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.statistics_service import StatisticsService

    return StatisticsService(async_db)


# get_log_service removed - use get_logger_service instead
async def get_logger_service():
    """Get LoggerService with async and sync database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.logger.logger_service import LoggerService

    return LoggerService(
        async_db=async_db,
        sync_db=sync_db,
        enable_console=True,
        enable_file_logging=True,
        enable_sse_broadcasting=True,
        enable_batching=True,  # Enable batching by default for performance
    )


async def get_health_service():
    """Get HealthService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.health_service import HealthService

    return HealthService(async_db)


async def get_admin_service():
    """Get AdminService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.admin_service import AdminService

    # AdminService needs ScheduledJobOperations, not raw database
    scheduled_job_ops = ScheduledJobOperations(async_db)
    return AdminService(scheduled_job_ops)


async def get_time_window_service():
    """Get TimeWindowService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.scheduling.time_window_service import TimeWindowService

    settings_service = await get_settings_service()
    return TimeWindowService(async_db, settings_service)


async def get_scheduling_service():
    """Get CaptureTimingService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.scheduling.capture_timing_service import CaptureTimingService

    time_window_service = await get_time_window_service()
    settings_service = await get_settings_service()
    return CaptureTimingService(async_db, time_window_service, settings_service)


async def get_job_queue_service():
    """Get JobQueueService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.scheduling.job_queue_service import JobQueueService

    return JobQueueService(async_db)


# Sync Service Dependencies (for background tasks and worker processes)
def get_sync_video_service():
    """Get SyncVideoService with sync database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.video_service import SyncVideoService

    # Use singleton sync settings service
    sync_settings_service = get_sync_settings_service()
    return SyncVideoService(sync_db, sync_settings_service)


# REMOVED: Video automation service dependencies - Using video pipeline instead
# async def get_video_automation_service():
#     """Get VideoAutomationService with sync database dependency injection"""
#     return VideoAutomationService(sync_db)
#
# def get_sync_video_automation_service():
#     """Get VideoAutomationService with sync database dependency injection"""
#     return VideoAutomationService(sync_db)


def get_sync_time_window_service():
    """Get SyncTimeWindowService with sync database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.scheduling.time_window_service import SyncTimeWindowService

    # Use singleton sync settings service
    sync_settings_service = get_sync_settings_service()
    return SyncTimeWindowService(sync_db, sync_settings_service)


def get_sync_scheduling_service():
    """Get SyncCaptureTimingService with sync database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.scheduling.capture_timing_service import SyncCaptureTimingService

    sync_time_window_service = get_sync_time_window_service()
    # Use singleton sync settings service
    sync_settings_service = get_sync_settings_service()
    return SyncCaptureTimingService(
        sync_db, async_db, sync_time_window_service, sync_settings_service
    )


def get_sync_job_queue_service():
    """Get SyncJobQueueService with sync database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.scheduling.job_queue_service import SyncJobQueueService

    return SyncJobQueueService(sync_db)


# Video Pipeline Dependencies (New Architecture)
def get_video_pipeline():
    """Get complete video pipeline with factory pattern dependency injection"""
    return create_video_pipeline(sync_db)


async def get_async_video_pipeline():
    """Get video pipeline for async operations (using sync db for consistency)"""
    return create_video_pipeline(sync_db)


def get_video_job_service():
    """Get VideoJobService with sync database dependency injection"""
    return create_video_job_service(sync_db)


def get_overlay_integration_service():
    """Get OverlayIntegrationService with sync database dependency injection"""
    return create_overlay_integration_service(sync_db)


async def get_scheduler_service():
    """
    Get SchedulerService with dependency injection.

    This service coordinates the timing and execution of scheduled tasks.
    It uses the scheduler worker for task execution.
    """
    # Inline import to avoid circular dependencies
    from .services.scheduling.scheduler_authority_service import SchedulerService

    scheduler_worker = get_scheduler_worker()
    if scheduler_worker is None:
        raise RuntimeError("SchedulerWorker not initialized")

    return SchedulerService(scheduler_worker)


async def get_overlay_service():
    """Get AsyncOverlayService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.overlay_pipeline import AsyncOverlayService

    # Use singleton async settings service
    settings_service = await get_settings_service()
    return AsyncOverlayService(async_db, settings_service)


async def get_overlay_job_service():
    """Get AsyncOverlayJobService with async database dependency injection"""
    # Inline import to avoid circular dependencies
    from .services.overlay_pipeline.services.job_service import AsyncOverlayJobService

    return AsyncOverlayJobService(async_db)


async def get_scheduled_job_operations():
    """Get ScheduledJobOperations with async database dependency injection"""
    return ScheduledJobOperations(async_db)


# Type Annotations for Easy Usage
AsyncDatabaseDep = Annotated[AsyncDatabase, Depends(get_async_database)]
SyncDatabaseDep = Annotated[SyncDatabase, Depends(get_sync_database)]

# Service type annotations
CameraServiceDep = Annotated["CameraService", Depends(get_camera_service)]
VideoServiceDep = Annotated["VideoService", Depends(get_video_service)]
TimelapseServiceDep = Annotated["TimelapseService", Depends(get_timelapse_service)]
ImageServiceDep = Annotated["ImageService", Depends(get_image_service)]
ThumbnailPipelineDep = Annotated["ThumbnailPipeline", Depends(get_thumbnail_pipeline)]
CorruptionPipelineDep = Annotated[object, Depends(get_corruption_pipeline)]
RTSPServiceDep = Annotated[object, Depends(get_rtsp_service)]
AsyncRTSPServiceDep = Annotated[object, Depends(get_async_rtsp_service)]
WorkflowOrchestratorServiceDep = Annotated[
    "WorkflowOrchestratorService", Depends(get_workflow_orchestrator_service)
]
SettingsServiceDep = Annotated["SettingsService", Depends(get_settings_service)]
WeatherManagerDep = Annotated["WeatherManager", Depends(get_weather_manager)]
StatisticsServiceDep = Annotated["StatisticsService", Depends(get_statistics_service)]
LoggerServiceDep = Annotated["LoggerService", Depends(get_logger_service)]
HealthServiceDep = Annotated["HealthService", Depends(get_health_service)]
AdminServiceDep = Annotated["AdminService", Depends(get_admin_service)]
TimeWindowServiceDep = Annotated["TimeWindowService", Depends(get_time_window_service)]
SyncTimeWindowServiceDep = Annotated[
    "SyncTimeWindowService", Depends(get_sync_time_window_service)
]
SchedulingServiceDep = Annotated[
    "CaptureTimingService", Depends(get_scheduling_service)
]
SyncSchedulingServiceDep = Annotated[
    "SyncCaptureTimingService", Depends(get_sync_scheduling_service)
]
JobQueueServiceDep = Annotated["JobQueueService", Depends(get_job_queue_service)]
SyncJobQueueServiceDep = Annotated[
    "SyncJobQueueService", Depends(get_sync_job_queue_service)
]
SchedulerServiceDep = Annotated["SchedulerService", Depends(get_scheduler_service)]


# REMOVED: Video automation service dependencies - Using video pipeline instead
# VideoAutomationServiceDep = Annotated[VideoAutomationService, Depends(get_video_automation_service)]
# SyncVideoAutomationServiceDep = Annotated[VideoAutomationService, Depends(get_sync_video_automation_service)]

# Sync service dependencies
SyncVideoServiceDep = Annotated["SyncVideoService", Depends(get_sync_video_service)]

# Overlay service dependencies
OverlayServiceDep = Annotated["AsyncOverlayService", Depends(get_overlay_service)]
OverlayJobServiceDep = Annotated[
    "AsyncOverlayJobService", Depends(get_overlay_job_service)
]
ScheduledJobOperationsDep = Annotated[
    "ScheduledJobOperations", Depends(get_scheduled_job_operations)
]

# Video Pipeline Dependencies (New Architecture)
VideoPipelineDep = Annotated["VideoWorkflowService", Depends(get_video_pipeline)]
AsyncVideoPipelineDep = Annotated[object, Depends(get_async_video_pipeline)]
VideoJobServiceDep = Annotated[object, Depends(get_video_job_service)]
OverlayIntegrationServiceDep = Annotated[
    object, Depends(get_overlay_integration_service)
]
