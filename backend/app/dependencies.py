# backend/app/dependencies.py
"""
FastAPI Dependencies for Dependency Injection

Provides proper dependency injection for services following the target architecture.
All services receive database instances via dependency injection using FastAPI's Depends system.
"""

from typing import Annotated
from fastapi import Depends

from backend.app.services.video_pipeline.video_workflow_service import (
    VideoWorkflowService,
)

from .database import async_db, sync_db
from .database.core import AsyncDatabase, SyncDatabase
from .services.camera_service import CameraService
from .services.video_service import VideoService, SyncVideoService

# from .services.video_automation_service import VideoAutomationService  # REMOVED: Using video pipeline
from .services.timelapse_service import TimelapseService
from .services.image_service import ImageService
from .services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
from .services.corruption_pipeline import create_corruption_pipeline
from .services.capture_pipeline import (
    create_capture_pipeline,
    WorkflowOrchestratorService,
    AsyncRTSPService,
)
from .services.settings_service import SettingsService
from .services.statistics_service import StatisticsService
from .services.log_service import LogService
from .services.weather.service import WeatherManager
from .services.health_service import HealthService
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
from .services.scheduling.job_queue_service import JobQueueService, SyncJobQueueService
from .services.scheduling.scheduler_authority_service import SchedulerService
from .services.video_pipeline import create_video_pipeline

from .database.thumbnail_job_operations import ThumbnailJobOperations
from .database.overlay_job_operations import OverlayJobOperations
from .database.sse_events_operations import SSEEventsOperations
from .database.image_operations import AsyncImageOperations

# Global scheduler worker instance (set by main worker on startup)
_scheduler_worker_instance = None


def set_scheduler_worker(scheduler_worker):
    """Set the global scheduler worker instance (called by main worker)"""
    global _scheduler_worker_instance
    _scheduler_worker_instance = scheduler_worker


def get_scheduler_worker():
    """Get the global scheduler worker instance"""
    global _scheduler_worker_instance
    return _scheduler_worker_instance


# Database Dependencies
async def get_async_database() -> AsyncDatabase:
    """Get async database instance"""
    return async_db


def get_sync_database() -> SyncDatabase:
    """Get sync database instance"""
    return sync_db


# Async Service Dependencies
async def get_camera_service() -> CameraService:
    """Get CameraService with async database dependency injection"""
    # Create settings service instance for camera service dependency
    settings_service = SettingsService(async_db)
    # Create async RTSP service for connectivity testing
    async_rtsp_service = await get_async_rtsp_service()
    # Create scheduling service for capture scheduling
    scheduling_service = await get_scheduling_service()
    return CameraService(
        async_db,
        settings_service,
        rtsp_service=async_rtsp_service,
        scheduling_service=scheduling_service,
    )


async def get_video_service() -> VideoService:
    """Get VideoService with async database dependency injection"""
    return VideoService(async_db)


async def get_timelapse_service() -> TimelapseService:
    """Get TimelapseService with async database dependency injection"""
    # Create service dependencies
    settings_service = SettingsService(async_db)
    image_service = ImageService(async_db, settings_service)
    return TimelapseService(
        async_db, image_service=image_service, settings_service=settings_service
    )


async def get_image_service() -> ImageService:
    """Get ImageService with async database dependency injection"""
    settings_service = SettingsService(async_db)
    return ImageService(async_db, settings_service)


async def get_thumbnail_pipeline() -> ThumbnailPipeline:
    """Get ThumbnailPipeline with async database dependency injection"""
    return ThumbnailPipeline(database=sync_db)


async def get_corruption_pipeline():
    """Get CorruptionPipeline with async database dependency injection"""
    return create_corruption_pipeline(async_database=async_db)


def get_rtsp_service():
    """Get RTSPService with sync database dependency injection"""
    from .services.capture_pipeline.rtsp_service import RTSPService

    return RTSPService(sync_db)


async def get_async_rtsp_service() -> AsyncRTSPService:
    """Get capture pipeline AsyncRTSPService with wrapped sync RTSP service"""
    sync_rtsp_service = get_rtsp_service()
    return AsyncRTSPService(sync_rtsp_service)


def get_workflow_orchestrator_service() -> WorkflowOrchestratorService:
    """Get WorkflowOrchestratorService with complete dependency injection through factory pattern"""
    return create_capture_pipeline()


async def get_settings_service() -> SettingsService:
    """Get SettingsService with async database dependency injection"""
    return SettingsService(async_db)


async def get_weather_manager():
    """Get WeatherManager with database and settings service dependency injection"""
    from .database.weather_operations import SyncWeatherOperations

    settings_service = SettingsService(async_db)
    weather_operations = SyncWeatherOperations(sync_db)
    return WeatherManager(weather_operations, settings_service)


async def get_statistics_service() -> StatisticsService:
    """Get StatisticsService with async database dependency injection"""
    return StatisticsService(async_db)


async def get_log_service() -> LogService:
    """Get LogService with async database dependency injection"""
    return LogService(async_db)


async def get_health_service() -> HealthService:
    """Get HealthService with async database dependency injection"""
    return HealthService(async_db)


async def get_time_window_service() -> TimeWindowService:
    """Get TimeWindowService with async database dependency injection"""
    return TimeWindowService(async_db)


async def get_scheduling_service() -> CaptureTimingService:
    """Get CaptureTimingService with async database dependency injection"""
    time_window_service = await get_time_window_service()
    return CaptureTimingService(async_db, time_window_service)


async def get_job_queue_service() -> JobQueueService:
    """Get JobQueueService with async database dependency injection"""
    return JobQueueService(async_db)


# Sync Service Dependencies (for background tasks and worker processes)
def get_sync_video_service() -> SyncVideoService:
    """Get SyncVideoService with sync database dependency injection"""
    return SyncVideoService(sync_db)


# async def get_video_automation_service() -> VideoAutomationService:  # REMOVED: Using video pipeline
#     """Get VideoAutomationService with sync database dependency injection"""
#     return VideoAutomationService(sync_db)


# def get_sync_video_automation_service() -> VideoAutomationService:  # REMOVED: Using video pipeline
#     """Get VideoAutomationService with sync database dependency injection"""
#     return VideoAutomationService(sync_db)


def get_sync_time_window_service() -> SyncTimeWindowService:
    """Get SyncTimeWindowService with sync database dependency injection"""
    return SyncTimeWindowService(sync_db)


def get_sync_scheduling_service() -> SyncCaptureTimingService:
    """Get SyncCaptureTimingService with sync database dependency injection"""
    sync_time_window_service = get_sync_time_window_service()
    return SyncCaptureTimingService(sync_db, sync_time_window_service)


def get_sync_job_queue_service() -> SyncJobQueueService:
    """Get SyncJobQueueService with sync database dependency injection"""
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
    from .services.video_pipeline import create_video_job_service

    return create_video_job_service(sync_db)


def get_overlay_integration_service():
    """Get OverlayIntegrationService with sync database dependency injection"""
    from .services.video_pipeline import create_overlay_integration_service

    return create_overlay_integration_service(sync_db)


async def get_scheduler_service() -> SchedulerService:
    """
    Get SchedulerService (SchedulerAuthorityService) with dependency injection.

    Provides async interface to the SchedulerWorker for timing coordination.
    The SchedulerWorker instance is set by the main worker on startup.
    """
    scheduler_worker = get_scheduler_worker()
    if scheduler_worker is None:
        raise RuntimeError(
            "SchedulerWorker not initialized. Ensure main worker is running."
        )

    # Create dependencies for scheduler authority service
    settings_service = SettingsService(async_db)
    timing_service = await get_scheduling_service()

    return SchedulerService(
        scheduler_worker=scheduler_worker,
        async_db=async_db,
        settings_service=settings_service,
        timing_service=timing_service,
    )


async def get_overlay_service() -> AsyncOverlayService:
    """Get AsyncOverlayService with async database dependency injection"""
    settings_service = SettingsService(async_db)
    return AsyncOverlayService(async_db, settings_service)


async def get_overlay_job_service() -> AsyncOverlayJobService:
    """Get AsyncOverlayJobService with async database dependency injection"""
    settings_service = SettingsService(async_db)
    return AsyncOverlayJobService(async_db, settings_service)


# Type Annotations for Easy Usage
AsyncDatabaseDep = Annotated[AsyncDatabase, Depends(get_async_database)]
SyncDatabaseDep = Annotated[SyncDatabase, Depends(get_sync_database)]

# Service type annotations
CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]
VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]
TimelapseServiceDep = Annotated[TimelapseService, Depends(get_timelapse_service)]
ImageServiceDep = Annotated[ImageService, Depends(get_image_service)]
ThumbnailPipelineDep = Annotated[ThumbnailPipeline, Depends(get_thumbnail_pipeline)]
CorruptionPipelineDep = Annotated[object, Depends(get_corruption_pipeline)]
RTSPServiceDep = Annotated[object, Depends(get_rtsp_service)]
AsyncRTSPServiceDep = Annotated[AsyncRTSPService, Depends(get_async_rtsp_service)]
WorkflowOrchestratorServiceDep = Annotated[
    WorkflowOrchestratorService, Depends(get_workflow_orchestrator_service)
]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
WeatherManagerDep = Annotated[WeatherManager, Depends(get_weather_manager)]
StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]
LogServiceDep = Annotated[LogService, Depends(get_log_service)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
TimeWindowServiceDep = Annotated[TimeWindowService, Depends(get_time_window_service)]
SyncTimeWindowServiceDep = Annotated[
    SyncTimeWindowService, Depends(get_sync_time_window_service)
]
SchedulingServiceDep = Annotated[CaptureTimingService, Depends(get_scheduling_service)]
SyncSchedulingServiceDep = Annotated[
    SyncCaptureTimingService, Depends(get_sync_scheduling_service)
]
JobQueueServiceDep = Annotated[JobQueueService, Depends(get_job_queue_service)]
SyncJobQueueServiceDep = Annotated[
    SyncJobQueueService, Depends(get_sync_job_queue_service)
]
SchedulerServiceDep = Annotated[SchedulerService, Depends(get_scheduler_service)]


# Video automation service dependencies - REMOVED: Using video pipeline
# VideoAutomationServiceDep = Annotated[
#     VideoAutomationService, Depends(get_video_automation_service)
# ]

# Sync service dependencies
SyncVideoServiceDep = Annotated[SyncVideoService, Depends(get_sync_video_service)]
# SyncVideoAutomationServiceDep = Annotated[
#     VideoAutomationService, Depends(get_sync_video_automation_service)
# ]

# Overlay service dependencies
OverlayServiceDep = Annotated[AsyncOverlayService, Depends(get_overlay_service)]
OverlayJobServiceDep = Annotated[
    AsyncOverlayJobService, Depends(get_overlay_job_service)
]

# Video Pipeline Dependencies (New Architecture)
VideoPipelineDep = Annotated[VideoWorkflowService, Depends(get_video_pipeline)]
AsyncVideoPipelineDep = Annotated[object, Depends(get_async_video_pipeline)]
VideoJobServiceDep = Annotated[object, Depends(get_video_job_service)]
OverlayIntegrationServiceDep = Annotated[
    object, Depends(get_overlay_integration_service)
]
