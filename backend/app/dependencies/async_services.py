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
    from ..services.corruption_pipeline.services import (
        CorruptionEvaluationService,
        CorruptionHealthService, 
        CorruptionStatisticsService,
    )
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
    from .specialized import get_settings_operations, get_async_sse_events_operations
    from ..services.weather.api_key_service import APIKeyService

    settings_ops = await get_settings_operations()
    sse_ops = await get_async_sse_events_operations()
    # APIKeyService now uses singleton Operations in fallback methods
    api_key_service = APIKeyService(async_db)

    return SettingsService(async_db, settings_ops, sse_ops, api_key_service)


register_singleton_factory("async_settings_service", _create_settings_service)


async def get_settings_service() -> "SettingsService":
    """Get SettingsService with async database dependency injection (singleton)."""
    return await get_async_singleton_service("async_settings_service")


# Camera Service Factory (Singleton)
async def _create_camera_service():
    """Factory for creating CameraService."""
    from ..services.camera_service import CameraService
    from .scheduling import get_scheduler_service, get_scheduling_service
    from .workflow import get_async_rtsp_service
    from .specialized import get_camera_operations, get_timelapse_operations, get_async_sse_events_operations

    settings_service = await get_settings_service()
    async_rtsp_service = await get_async_rtsp_service()
    scheduling_service = await get_scheduling_service()
    
    # Get injected Operations
    camera_ops = await get_camera_operations()
    timelapse_ops = await get_timelapse_operations()
    sse_ops = await get_async_sse_events_operations()

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
        camera_ops=camera_ops,
        timelapse_ops=timelapse_ops,
        sse_ops=sse_ops,
        rtsp_service=async_rtsp_service,
        scheduling_service=scheduling_service,
        scheduler_authority_service=scheduler_authority_service,
    )


register_singleton_factory("camera_service", _create_camera_service)


async def get_camera_service() -> "CameraService":
    """Get CameraService singleton with complete dependency injection."""
    return await get_async_singleton_service("camera_service")


# Video Service Factory (Singleton)
async def _create_video_service():
    """Factory for creating VideoService."""
    from ..services.video_service import VideoService
    from ..database import sync_db
    from .specialized import get_video_operations, get_async_sse_events_operations

    video_ops = await get_video_operations()
    sse_ops = await get_async_sse_events_operations()
    settings_service = await get_settings_service()

    return VideoService(async_db, sync_db, settings_service, video_ops, sse_ops)


register_singleton_factory("video_service", _create_video_service)


async def get_video_service() -> "VideoService":
    """Get VideoService singleton with async and sync database dependency injection."""
    return await get_async_singleton_service("video_service")


# Timelapse Service Factory (Singleton)
async def _create_timelapse_service():
    """Factory for creating TimelapseService."""
    from ..services.timelapse_service import TimelapseService
    from .specialized import get_timelapse_operations, get_async_sse_events_operations

    timelapse_ops = await get_timelapse_operations()
    sse_ops = await get_async_sse_events_operations()
    settings_service = await get_settings_service()
    image_service = await get_image_service()

    # Get thumbnail pipeline singleton to break circular dependency
    thumbnail_pipeline = await get_thumbnail_pipeline()

    return TimelapseService(
        async_db,
        timelapse_ops=timelapse_ops,
        sse_ops=sse_ops,
        image_service=image_service,
        settings_service=settings_service,
        thumbnail_pipeline=thumbnail_pipeline,
    )


register_singleton_factory("timelapse_service", _create_timelapse_service)


async def get_timelapse_service() -> "TimelapseService":
    """Get TimelapseService singleton with complex dependency chain."""
    return await get_async_singleton_service("timelapse_service")


# Image Service Factory (Singleton)
async def _create_image_service():
    """Factory for creating ImageService."""
    from ..services.image_service import ImageService
    from .specialized import get_image_operations, get_async_sse_events_operations

    settings_service = await get_settings_service()
    image_ops = await get_image_operations()
    sse_ops = await get_async_sse_events_operations()
    
    return ImageService(db=async_db, settings_service=settings_service, image_ops=image_ops, sse_ops=sse_ops)


register_singleton_factory("image_service", _create_image_service)


async def get_image_service() -> "ImageService":
    """Get ImageService singleton with async database dependency injection."""
    return await get_async_singleton_service("image_service")


# Weather Manager Factory (Singleton)
async def _create_weather_manager():
    """Factory for creating WeatherManager."""
    from ..services.weather.service import WeatherManager
    from .specialized import get_sync_weather_operations

    settings_service = await get_settings_service()
    weather_operations = get_sync_weather_operations()
    return WeatherManager(weather_operations, settings_service)


register_singleton_factory("weather_manager", _create_weather_manager)


async def get_weather_manager() -> "WeatherManager":
    """Get WeatherManager singleton with database and settings service dependency injection."""
    return await get_async_singleton_service("weather_manager")


# Statistics Service Factory (Singleton)
async def _create_statistics_service():
    """Factory for creating StatisticsService."""
    from ..services.statistics_service import StatisticsService
    from .specialized import get_statistics_operations
    
    stats_ops = await get_statistics_operations()
    settings_service = await get_settings_service()
    return StatisticsService(async_db, stats_ops, settings_service)


register_singleton_factory("statistics_service", _create_statistics_service)


async def get_statistics_service() -> "StatisticsService":
    """Get StatisticsService singleton with async database dependency injection."""
    return await get_async_singleton_service("statistics_service")


# Logger Service Factory (Singleton)
async def _create_logger_service():
    """Factory for creating LoggerService."""
    from ..database import sync_db
    from ..services.logger.logger_service import LoggerService
    from .specialized import get_log_operations, get_sync_log_operations, get_async_sse_events_operations, get_sync_sse_events_operations

    # Get all Operations singletons
    async_log_ops = await get_log_operations()
    sync_log_ops = get_sync_log_operations()
    sse_ops = await get_async_sse_events_operations()
    sync_sse_ops = get_sync_sse_events_operations()

    return LoggerService(
        async_db=async_db,
        sync_db=sync_db,
        async_log_ops=async_log_ops,
        sync_log_ops=sync_log_ops,
        sse_ops=sse_ops,
        sync_sse_ops=sync_sse_ops,
        enable_console=True,
        enable_file_logging=True,
        enable_sse_broadcasting=True,
        enable_batching=True,
    )


register_singleton_factory("logger_service", _create_logger_service)


async def get_logger_service() -> "LoggerService":
    """Get LoggerService singleton with async and sync database dependency injection."""
    return await get_async_singleton_service("logger_service")


# Health Service Factory (Singleton)
async def _create_health_service():
    """Factory for creating HealthService."""
    from ..services.health_service import HealthService
    from .specialized import get_health_operations, get_statistics_operations
    
    health_ops = await get_health_operations()
    stats_ops = await get_statistics_operations()
    return HealthService(async_db, health_ops, stats_ops)


register_singleton_factory("health_service", _create_health_service)


async def get_health_service() -> "HealthService":
    """Get HealthService singleton with async database dependency injection."""
    return await get_async_singleton_service("health_service")


# Admin Service Factory (Singleton)
async def _create_admin_service():
    """Factory for creating AdminService."""
    from ..services.admin_service import AdminService
    from .specialized import get_scheduled_job_operations

    scheduled_job_ops = await get_scheduled_job_operations()
    return AdminService(scheduled_job_ops)


register_singleton_factory("admin_service", _create_admin_service)


async def get_admin_service() -> "AdminService":
    """Get AdminService singleton with scheduled job operations dependency injection."""
    return await get_async_singleton_service("admin_service")


# Overlay Service Factory (Singleton)
async def _create_overlay_service():
    """Factory for creating AsyncOverlayService."""
    # Import the service directly since it has a non-standard constructor
    from ..services.overlay_pipeline import AsyncOverlayService
    from ..database import async_db

    # The AsyncOverlayService (OverlayIntegrationService) expects 'db' not 'async_db'
    settings_service = await get_settings_service()
    return AsyncOverlayService(
        db=async_db,  # Pass as 'db' parameter
        settings_service=settings_service,
    )


register_singleton_factory("async_overlay_service", _create_overlay_service)


async def get_overlay_service() -> "AsyncOverlayService":
    """Get AsyncOverlayService singleton with async database dependency injection."""
    return await get_async_singleton_service("async_overlay_service")


# Overlay Job Service Factory
async def get_overlay_job_service() -> "AsyncOverlayJobService":
    """Get AsyncOverlayJobService with async database dependency injection."""
    factory = AsyncServiceFactory(
        service_module="app.services.overlay_pipeline.services.job_service",
        service_class="AsyncOverlayJobService",
        needs_settings=False,
    )
    return await factory.get_service()


# Corruption Services Factories (Singletons)
async def _create_corruption_statistics_service():
    """Factory for creating CorruptionStatisticsService."""
    from ..services.corruption_pipeline.services import CorruptionStatisticsService
    return CorruptionStatisticsService(async_db)


async def _create_corruption_health_service():
    """Factory for creating CorruptionHealthService."""
    from ..services.corruption_pipeline.services import CorruptionHealthService
    return CorruptionHealthService(async_db)


async def _create_corruption_evaluation_service():
    """Factory for creating CorruptionEvaluationService."""
    from ..services.corruption_pipeline.services import CorruptionEvaluationService
    return CorruptionEvaluationService(async_db)


register_singleton_factory("corruption_statistics_service", _create_corruption_statistics_service)
register_singleton_factory("corruption_health_service", _create_corruption_health_service) 
register_singleton_factory("corruption_evaluation_service", _create_corruption_evaluation_service)


async def get_corruption_statistics_service() -> "CorruptionStatisticsService":
    """Get CorruptionStatisticsService singleton with async database dependency injection."""
    return await get_async_singleton_service("corruption_statistics_service")


async def get_corruption_health_service() -> "CorruptionHealthService":
    """Get CorruptionHealthService singleton with async database dependency injection."""
    return await get_async_singleton_service("corruption_health_service")


async def get_corruption_evaluation_service() -> "CorruptionEvaluationService":
    """Get CorruptionEvaluationService singleton with async database dependency injection."""
    return await get_async_singleton_service("corruption_evaluation_service")
