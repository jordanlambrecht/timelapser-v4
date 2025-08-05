# backend/app/dependencies/sync_services.py
"""
Sync service dependencies using the factory pattern.

These services are primarily used by background workers and tasks
that need synchronous database operations.
"""

from typing import TYPE_CHECKING

from .base import SyncServiceFactory
from .registry import register_singleton_factory, get_singleton_service
from ..database import sync_db, async_db

if TYPE_CHECKING:
    from ..services.settings_service import SyncSettingsService
    from ..services.video_service import SyncVideoService
    from ..services.capture_pipeline.rtsp_service import RTSPService


# Sync Settings Service Factory (Singleton)
def _create_sync_settings_service():
    """Factory for creating SyncSettingsService."""
    from ..services.settings_service import SyncSettingsService

    return SyncSettingsService(sync_db)


register_singleton_factory("sync_settings_service", _create_sync_settings_service)


def get_sync_settings_service() -> "SyncSettingsService":
    """Get SyncSettingsService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_settings_service")


# Sync Video Service Factory
def get_sync_video_service() -> "SyncVideoService":
    """Get SyncVideoService with sync database dependency injection."""
    factory = SyncServiceFactory(
        service_module="app.services.video_service", service_class="SyncVideoService"
    )
    return factory.get_service()


# RTSP Service Factory
def get_rtsp_service() -> "RTSPService":
    """Get RTSPService with sync database dependency injection."""
    from ..services.capture_pipeline.rtsp_service import RTSPService

    sync_settings_service = get_sync_settings_service()
    return RTSPService(sync_db, async_db, sync_settings_service)
