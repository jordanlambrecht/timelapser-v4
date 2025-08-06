# backend/app/dependencies/async_services.py
"""
Async service dependencies using the factory pattern.

This eliminates the massive duplication from the original dependencies.py
by using standardized factory patterns for common service types.
"""

from typing import TYPE_CHECKING

from ..database import async_db
from .base import AsyncServiceFactory
from .registry import get_async_singleton_service, register_singleton_factory

if TYPE_CHECKING:
    from ..services.admin_service import AdminService
    from ..services.camera_service import CameraService
    from ..services.health_service import HealthService
    from ..services.image_service import ImageService
    from ..services.logger.logger_service import LoggerService
    from ..services.overlay_pipeline import AsyncOverlayService
    from ..services.overlay_pipeline.services.job_service import AsyncOverlayJobService
    from ..services.settings_service import SettingsService
    from ..services.statistics_service import StatisticsService
    from ..services.timelapse_service import TimelapseService
    from ..services.video_service import VideoService
    from ..services.weather.service import WeatherManager


# Settings Service Factory (Singleton)
async def _create_settings_service():
    """Factory for creating SettingsService."""
    from ..services.settings_service import SettingsService

    return SettingsService(async_db)


register_singleton_factory("async_settings_service", _create_settings_service)


async def get_settings_service() -> "SettingsService":
    """Get SettingsService with async database dependency injection (singleton)."""
    return await get_async_singleton_service("async_settings_service")


# Camera Service Factory
async def get_camera_service() -> "CameraService":
    """Get CameraService with complete dependency injection."""
    from ..services.camera_service import CameraService
    from .scheduling import get_scheduler_service, get_scheduling_service
    from .workflow import get_async_rtsp_service

    settings_service = await get_settings_service()
    async_rtsp_service = await get_async_rtsp_service()
    scheduling_service = await get_scheduling_service()

    # SchedulerWorker might not be initialized yet
    try:
        scheduler_authority_service = await get_scheduler_service()
    except RuntimeError:
        scheduler_authority_service = None

    from ..database import sync_db

    return CameraService(
        async_db,
        sync_db=sync_db,
        settings_service=settings_service,
        rtsp_service=async_rtsp_service,
        scheduling_service=scheduling_service,
        scheduler_authority_service=scheduler_authority_service,
    )


# Video Service Factory
async def get_video_service() -> "VideoService":
    """Get VideoService with async and sync database dependency injection."""
    factory = AsyncServiceFactory(
        service_module="app.services.video_service",
        service_class="VideoService",
        needs_sync_db=True,
    )
    return await factory.get_service()


# Timelapse Service Factory
async def get_timelapse_service() -> "TimelapseService":
    """Get TimelapseService with complex dependency chain."""
    from ..services.image_service import ImageService
    from ..services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
    from ..services.timelapse_service import TimelapseService

    settings_service = await get_settings_service()
    image_service = ImageService(async_db, settings_service)
    thumbnail_pipeline = ThumbnailPipeline(async_database=async_db)

    return TimelapseService(
        async_db,
        image_service=image_service,
        settings_service=settings_service,
        thumbnail_pipeline=thumbnail_pipeline,
    )


# Image Service Factory
async def get_image_service() -> "ImageService":
    """Get ImageService with async database dependency injection."""
    from ..services.image_service import ImageService

    settings_service = await get_settings_service()
    return ImageService(db=async_db, settings_service=settings_service)


# Weather Manager Factory
async def get_weather_manager() -> "WeatherManager":
    """Get WeatherManager with database and settings service dependency injection."""
    from ..database import sync_db
    from ..database.weather_operations import SyncWeatherOperations
    from ..services.weather.service import WeatherManager

    settings_service = await get_settings_service()
    weather_operations = SyncWeatherOperations(sync_db)
    return WeatherManager(weather_operations, settings_service)


# Statistics Service Factory
async def get_statistics_service() -> "StatisticsService":
    """Get StatisticsService with async database dependency injection."""
    from ..services.statistics_service import StatisticsService

    return StatisticsService(async_db)


# Logger Service Factory
async def get_logger_service() -> "LoggerService":
    """Get LoggerService with async and sync database dependency injection."""
    from ..database import sync_db
    from ..services.logger.logger_service import LoggerService

    return LoggerService(
        async_db=async_db,
        sync_db=sync_db,
        enable_console=True,
        enable_file_logging=True,
        enable_sse_broadcasting=True,
        enable_batching=True,
    )


# Health Service Factory
async def get_health_service() -> "HealthService":
    """Get HealthService with async database dependency injection."""
    factory = AsyncServiceFactory(
        service_module="app.services.health_service",
        service_class="HealthService",
        needs_settings=False,
    )
    return await factory.get_service()


# Admin Service Factory
async def get_admin_service() -> "AdminService":
    """Get AdminService with scheduled job operations dependency injection."""
    from ..database.scheduled_job_operations import ScheduledJobOperations
    from ..services.admin_service import AdminService

    scheduled_job_ops = ScheduledJobOperations(async_db)
    return AdminService(scheduled_job_ops)


# Overlay Service Factory
async def get_overlay_service() -> "AsyncOverlayService":
    """Get AsyncOverlayService with async database dependency injection."""
    factory = AsyncServiceFactory(
        service_module="app.services.overlay_pipeline",
        service_class="AsyncOverlayService",
    )
    return await factory.get_service()


# Overlay Job Service Factory
async def get_overlay_job_service() -> "AsyncOverlayJobService":
    """Get AsyncOverlayJobService with async database dependency injection."""
    factory = AsyncServiceFactory(
        service_module="app.services.overlay_pipeline.services.job_service",
        service_class="AsyncOverlayJobService",
        needs_settings=False,
    )
    return await factory.get_service()
