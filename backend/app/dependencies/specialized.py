# backend/app/dependencies/specialized.py
"""
Specialized service dependencies that don't fit into other categories.

These are typically database operations or other specialized services.
"""

from typing import TYPE_CHECKING

from ..database import async_db, sync_db
from .registry import get_singleton_service, register_singleton_factory

if TYPE_CHECKING:
    from ..database.camera_operations import AsyncCameraOperations, SyncCameraOperations
    from ..database.corruption_operations import (
        CorruptionOperations,
        SyncCorruptionOperations,
    )
    from ..database.health_operations import HealthOperations, SyncHealthOperations
    from ..database.image_operations import ImageOperations, SyncImageOperations
    from ..database.log_operations import LogOperations, SyncLogOperations
    from ..database.overlay_job_operations import (
        OverlayJobOperations,
        SyncOverlayJobOperations,
    )
    from ..database.overlay_operations import OverlayOperations, SyncOverlayOperations
    from ..database.recovery_operations import (
        RecoveryOperations,
        SyncRecoveryOperations,
    )
    from ..database.scheduled_job_operations import ScheduledJobOperations
    from ..database.settings_operations import (
        SettingsOperations,
        SyncSettingsOperations,
    )
    from ..database.sse_events_operations import (
        SSEEventsOperations,
        SyncSSEEventsOperations,
    )
    from ..database.statistics_operations import (
        StatisticsOperations,
        SyncStatisticsOperations,
    )
    from ..database.thumbnail_job_operations import (
        ThumbnailJobOperations,
        SyncThumbnailJobOperations,
    )
    from ..database.timelapse_operations import (
        TimelapseOperations,
        SyncTimelapseOperations,
    )
    from ..database.video_operations import VideoOperations, SyncVideoOperations
    from ..database.weather_operations import SyncWeatherOperations


# Scheduled Job Operations Factory (Singleton)
def _create_scheduled_job_operations():
    """Factory for creating ScheduledJobOperations."""
    from ..database.scheduled_job_operations import ScheduledJobOperations

    return ScheduledJobOperations(async_db)


register_singleton_factory("scheduled_job_operations", _create_scheduled_job_operations)


async def get_scheduled_job_operations() -> "ScheduledJobOperations":
    """Get ScheduledJobOperations singleton with async database dependency injection."""
    return get_singleton_service("scheduled_job_operations")


# Sync SSE Events Operations Factory (Singleton)
def _create_sync_sse_events_operations():
    """Factory for creating SyncSSEEventsOperations."""
    from ..database.sse_events_operations import SyncSSEEventsOperations

    return SyncSSEEventsOperations(sync_db)


register_singleton_factory(
    "sync_sse_events_operations", _create_sync_sse_events_operations
)


def get_sync_sse_events_operations() -> "SyncSSEEventsOperations":
    """Get SyncSSEEventsOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_sse_events_operations")


# Async SSE Events Operations Factory (Singleton)
def _create_async_sse_events_operations():
    """Factory for creating SSEEventsOperations."""
    from ..database.sse_events_operations import SSEEventsOperations

    return SSEEventsOperations(async_db)


register_singleton_factory(
    "async_sse_events_operations", _create_async_sse_events_operations
)


async def get_async_sse_events_operations() -> "SSEEventsOperations":
    """Get SSEEventsOperations singleton with async database dependency injection."""
    return get_singleton_service("async_sse_events_operations")


# Sync Weather Operations Factory (Singleton)
def _create_sync_weather_operations():
    """Factory for creating SyncWeatherOperations."""
    from ..database.weather_operations import SyncWeatherOperations

    return SyncWeatherOperations(sync_db)


register_singleton_factory("sync_weather_operations", _create_sync_weather_operations)


def get_sync_weather_operations() -> "SyncWeatherOperations":
    """Get SyncWeatherOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_weather_operations")


# Video Operations Factory (Singleton)
def _create_video_operations():
    """Factory for creating VideoOperations."""
    from ..database.video_operations import VideoOperations

    return VideoOperations(async_db)


def _create_sync_video_operations():
    """Factory for creating SyncVideoOperations."""
    from ..database.video_operations import SyncVideoOperations

    return SyncVideoOperations(sync_db)


register_singleton_factory("video_operations", _create_video_operations)
register_singleton_factory("sync_video_operations", _create_sync_video_operations)


async def get_video_operations() -> "VideoOperations":
    """Get VideoOperations singleton with async database dependency injection."""
    return get_singleton_service("video_operations")


def get_sync_video_operations() -> "SyncVideoOperations":
    """Get SyncVideoOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_video_operations")


# Timelapse Operations Factory (Singleton)
def _create_timelapse_operations():
    """Factory for creating TimelapseOperations."""
    from ..database.timelapse_operations import TimelapseOperations

    return TimelapseOperations(async_db)


def _create_sync_timelapse_operations():
    """Factory for creating SyncTimelapseOperations."""
    from ..database.timelapse_operations import SyncTimelapseOperations

    return SyncTimelapseOperations(sync_db)


register_singleton_factory("timelapse_operations", _create_timelapse_operations)
register_singleton_factory(
    "sync_timelapse_operations", _create_sync_timelapse_operations
)


async def get_timelapse_operations() -> "TimelapseOperations":
    """Get TimelapseOperations singleton with async database dependency injection."""
    return get_singleton_service("timelapse_operations")


def get_sync_timelapse_operations() -> "SyncTimelapseOperations":
    """Get SyncTimelapseOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_timelapse_operations")


# Image Operations Factory (Singleton)
def _create_image_operations():
    """Factory for creating ImageOperations."""
    from ..database.image_operations import ImageOperations

    return ImageOperations(async_db)


def _create_sync_image_operations():
    """Factory for creating SyncImageOperations."""
    from ..database.image_operations import SyncImageOperations

    return SyncImageOperations(sync_db)


register_singleton_factory("image_operations", _create_image_operations)
register_singleton_factory("sync_image_operations", _create_sync_image_operations)


async def get_image_operations() -> "ImageOperations":
    """Get ImageOperations singleton with async database dependency injection."""
    return get_singleton_service("image_operations")


def get_sync_image_operations() -> "SyncImageOperations":
    """Get SyncImageOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_image_operations")


# Settings Operations Factory (Singleton)
def _create_settings_operations():
    """Factory for creating SettingsOperations."""
    from ..database.settings_operations import SettingsOperations

    return SettingsOperations(async_db)


def _create_sync_settings_operations():
    """Factory for creating SyncSettingsOperations."""
    from ..database.settings_operations import SyncSettingsOperations

    return SyncSettingsOperations(sync_db)


register_singleton_factory("settings_operations", _create_settings_operations)
register_singleton_factory("sync_settings_operations", _create_sync_settings_operations)


async def get_settings_operations() -> "SettingsOperations":
    """Get SettingsOperations singleton with async database dependency injection."""
    return get_singleton_service("settings_operations")


def get_sync_settings_operations() -> "SyncSettingsOperations":
    """Get SyncSettingsOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_settings_operations")


# Statistics Operations Factory (Singleton)
def _create_statistics_operations():
    """Factory for creating StatisticsOperations."""
    from ..database.statistics_operations import StatisticsOperations

    return StatisticsOperations(async_db)


def _create_sync_statistics_operations():
    """Factory for creating SyncStatisticsOperations."""
    from ..database.statistics_operations import SyncStatisticsOperations

    return SyncStatisticsOperations(sync_db)


register_singleton_factory("statistics_operations", _create_statistics_operations)
register_singleton_factory(
    "sync_statistics_operations", _create_sync_statistics_operations
)


async def get_statistics_operations() -> "StatisticsOperations":
    """Get StatisticsOperations singleton with async database dependency injection."""
    return get_singleton_service("statistics_operations")


def get_sync_statistics_operations() -> "SyncStatisticsOperations":
    """Get SyncStatisticsOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_statistics_operations")


# Camera Operations Factory (Singleton)
def _create_camera_operations():
    """Factory for creating AsyncCameraOperations."""
    from ..database.camera_operations import AsyncCameraOperations

    # Note: CameraOperations will need to be refactored to not require settings_service in constructor
    # For now, pass None and let the operations handle it internally
    return AsyncCameraOperations(async_db, None)


def _create_sync_camera_operations():
    """Factory for creating SyncCameraOperations."""
    from ..database.camera_operations import SyncCameraOperations

    return SyncCameraOperations(sync_db, async_db)


register_singleton_factory("camera_operations", _create_camera_operations)
register_singleton_factory("sync_camera_operations", _create_sync_camera_operations)


async def get_camera_operations() -> "AsyncCameraOperations":
    """Get AsyncCameraOperations singleton with async database dependency injection."""
    return get_singleton_service("camera_operations")


def get_sync_camera_operations() -> "SyncCameraOperations":
    """Get SyncCameraOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_camera_operations")


# Corruption Operations Factory (Singleton)
def _create_corruption_operations():
    """Factory for creating CorruptionOperations."""
    from ..database.corruption_operations import CorruptionOperations

    return CorruptionOperations(async_db)


def _create_sync_corruption_operations():
    """Factory for creating SyncCorruptionOperations."""
    from ..database.corruption_operations import SyncCorruptionOperations

    return SyncCorruptionOperations(sync_db)


register_singleton_factory("corruption_operations", _create_corruption_operations)
register_singleton_factory(
    "sync_corruption_operations", _create_sync_corruption_operations
)


async def get_corruption_operations() -> "CorruptionOperations":
    """Get CorruptionOperations singleton with async database dependency injection."""
    return get_singleton_service("corruption_operations")


def get_sync_corruption_operations() -> "SyncCorruptionOperations":
    """Get SyncCorruptionOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_corruption_operations")


# Health Operations Factory (Singleton)
def _create_health_operations():
    """Factory for creating HealthOperations."""
    from ..database.health_operations import HealthOperations

    return HealthOperations(async_db)


def _create_sync_health_operations():
    """Factory for creating SyncHealthOperations."""
    from ..database.health_operations import SyncHealthOperations

    return SyncHealthOperations(sync_db)


register_singleton_factory("health_operations", _create_health_operations)
register_singleton_factory("sync_health_operations", _create_sync_health_operations)


async def get_health_operations() -> "HealthOperations":
    """Get HealthOperations singleton with async database dependency injection."""
    return get_singleton_service("health_operations")


def get_sync_health_operations() -> "SyncHealthOperations":
    """Get SyncHealthOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_health_operations")


# Log Operations Factory (Singleton)
def _create_log_operations():
    """Factory for creating LogOperations."""
    from ..database.log_operations import LogOperations

    return LogOperations(async_db)


def _create_sync_log_operations():
    """Factory for creating SyncLogOperations."""
    from ..database.log_operations import SyncLogOperations

    return SyncLogOperations(sync_db)


register_singleton_factory("log_operations", _create_log_operations)
register_singleton_factory("sync_log_operations", _create_sync_log_operations)


async def get_log_operations() -> "LogOperations":
    """Get LogOperations singleton with async database dependency injection."""
    return get_singleton_service("log_operations")


def get_sync_log_operations() -> "SyncLogOperations":
    """Get SyncLogOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_log_operations")


# Overlay Operations Factory (Singleton)
def _create_overlay_operations():
    """Factory for creating OverlayOperations."""
    from ..database.overlay_operations import OverlayOperations

    return OverlayOperations(async_db)


def _create_sync_overlay_operations():
    """Factory for creating SyncOverlayOperations."""
    from ..database.overlay_operations import SyncOverlayOperations

    return SyncOverlayOperations(sync_db)


register_singleton_factory("overlay_operations", _create_overlay_operations)
register_singleton_factory("sync_overlay_operations", _create_sync_overlay_operations)


async def get_overlay_operations() -> "OverlayOperations":
    """Get OverlayOperations singleton with async database dependency injection."""
    return get_singleton_service("overlay_operations")


def get_sync_overlay_operations() -> "SyncOverlayOperations":
    """Get SyncOverlayOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_overlay_operations")


# Overlay Job Operations Factory (Singleton)
def _create_overlay_job_operations():
    """Factory for creating OverlayJobOperations."""
    from ..database.overlay_job_operations import OverlayJobOperations

    return OverlayJobOperations(async_db)


def _create_sync_overlay_job_operations():
    """Factory for creating SyncOverlayJobOperations."""
    from ..database.overlay_job_operations import SyncOverlayJobOperations

    return SyncOverlayJobOperations(sync_db)


register_singleton_factory("overlay_job_operations", _create_overlay_job_operations)
register_singleton_factory(
    "sync_overlay_job_operations", _create_sync_overlay_job_operations
)


async def get_overlay_job_operations() -> "OverlayJobOperations":
    """Get OverlayJobOperations singleton with async database dependency injection."""
    return get_singleton_service("overlay_job_operations")


def get_sync_overlay_job_operations() -> "SyncOverlayJobOperations":
    """Get SyncOverlayJobOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_overlay_job_operations")


# Recovery Operations Factory (Singleton)
def _create_recovery_operations():
    """Factory for creating RecoveryOperations."""
    from ..database.recovery_operations import RecoveryOperations

    return RecoveryOperations(async_db)


def _create_sync_recovery_operations():
    """Factory for creating SyncRecoveryOperations."""
    from ..database.recovery_operations import SyncRecoveryOperations

    return SyncRecoveryOperations(sync_db)


register_singleton_factory("recovery_operations", _create_recovery_operations)
register_singleton_factory("sync_recovery_operations", _create_sync_recovery_operations)


async def get_recovery_operations() -> "RecoveryOperations":
    """Get RecoveryOperations singleton with async database dependency injection."""
    return get_singleton_service("recovery_operations")


def get_sync_recovery_operations() -> "SyncRecoveryOperations":
    """Get SyncRecoveryOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_recovery_operations")


# Thumbnail Job Operations Factory (Singleton)
def _create_thumbnail_job_operations():
    """Factory for creating ThumbnailJobOperations."""
    from ..database.thumbnail_job_operations import ThumbnailJobOperations

    return ThumbnailJobOperations(async_db)


def _create_sync_thumbnail_job_operations():
    """Factory for creating SyncThumbnailJobOperations."""
    from ..database.thumbnail_job_operations import SyncThumbnailJobOperations

    return SyncThumbnailJobOperations(sync_db)


register_singleton_factory("thumbnail_job_operations", _create_thumbnail_job_operations)
register_singleton_factory(
    "sync_thumbnail_job_operations", _create_sync_thumbnail_job_operations
)


async def get_thumbnail_job_operations() -> "ThumbnailJobOperations":
    """Get ThumbnailJobOperations singleton with async database dependency injection."""
    return get_singleton_service("thumbnail_job_operations")


def get_sync_thumbnail_job_operations() -> "SyncThumbnailJobOperations":
    """Get SyncThumbnailJobOperations singleton with sync database dependency injection."""
    return get_singleton_service("sync_thumbnail_job_operations")
