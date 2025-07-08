# backend/app/dependencies.py
"""
FastAPI Dependencies for Dependency Injection

Provides proper dependency injection for services following the target architecture.
All services receive database instances via dependency injection using FastAPI's Depends system.
"""

from typing import Annotated
from fastapi import Depends

from .database import async_db, sync_db
from .database.core import AsyncDatabase, SyncDatabase
from .services.camera_service import CameraService
from .services.video_service import VideoService, SyncVideoService
from .services.video_automation_service import VideoAutomationService
from .services.timelapse_service import TimelapseService
from .services.image_service import ImageService
from .services.thumbnail_service import ThumbnailService
from .services.corruption_service import CorruptionService
from .services.settings_service import SettingsService
from .services.statistics_service import StatisticsService
from .services.log_service import LogService
from .services.health_service import HealthService

from .database.thumbnail_job_operations import ThumbnailJobOperations
from .database.sse_events_operations import SSEEventsOperations
from .database.image_operations import AsyncImageOperations


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
    return CameraService(async_db, settings_service)


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


async def get_thumbnail_service() -> ThumbnailService:
    """Get ThumbnailService with async database dependency injection"""

    thumbnail_job_ops = ThumbnailJobOperations(async_db)
    sse_operations = SSEEventsOperations(async_db)
    image_operations = AsyncImageOperations(async_db)
    settings_service = SettingsService(async_db)

    return ThumbnailService(
        thumbnail_job_ops,
        sse_operations,
        image_operations=image_operations,
        settings_service=settings_service,
    )


async def get_corruption_service() -> CorruptionService:
    """Get CorruptionService with async database dependency injection"""
    return CorruptionService(async_db)


async def get_settings_service() -> SettingsService:
    """Get SettingsService with async database dependency injection"""
    return SettingsService(async_db)


async def get_statistics_service() -> StatisticsService:
    """Get StatisticsService with async database dependency injection"""
    return StatisticsService(async_db)


async def get_log_service() -> LogService:
    """Get LogService with async database dependency injection"""
    return LogService(async_db)


async def get_health_service() -> HealthService:
    """Get HealthService with async database dependency injection"""
    return HealthService(async_db)


# Sync Service Dependencies (for background tasks and worker processes)
def get_sync_video_service() -> SyncVideoService:
    """Get SyncVideoService with sync database dependency injection"""
    return SyncVideoService(sync_db)


async def get_video_automation_service() -> VideoAutomationService:
    """Get VideoAutomationService with sync database dependency injection"""
    return VideoAutomationService(sync_db)


def get_sync_video_automation_service() -> VideoAutomationService:
    """Get VideoAutomationService with sync database dependency injection"""
    return VideoAutomationService(sync_db)


# Type Annotations for Easy Usage
AsyncDatabaseDep = Annotated[AsyncDatabase, Depends(get_async_database)]
SyncDatabaseDep = Annotated[SyncDatabase, Depends(get_sync_database)]

# Service type annotations
CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]
VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]
TimelapseServiceDep = Annotated[TimelapseService, Depends(get_timelapse_service)]
ImageServiceDep = Annotated[ImageService, Depends(get_image_service)]
ThumbnailServiceDep = Annotated[ThumbnailService, Depends(get_thumbnail_service)]
CorruptionServiceDep = Annotated[CorruptionService, Depends(get_corruption_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]
LogServiceDep = Annotated[LogService, Depends(get_log_service)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]

# Video automation service dependencies
VideoAutomationServiceDep = Annotated[
    VideoAutomationService, Depends(get_video_automation_service)
]

# Sync service dependencies
SyncVideoServiceDep = Annotated[SyncVideoService, Depends(get_sync_video_service)]
SyncVideoAutomationServiceDep = Annotated[
    VideoAutomationService, Depends(get_sync_video_automation_service)
]
