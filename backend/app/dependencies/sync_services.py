# backend/app/dependencies/sync_services.py
"""
Sync service dependencies using the factory pattern.

These services are primarily used by background workers and tasks
that need synchronous database operations.
"""

from typing import TYPE_CHECKING

from ..database import async_db, sync_db
from .base import SyncServiceFactory
from .registry import get_singleton_service, register_singleton_factory

if TYPE_CHECKING:
    from ..services.camera_service import SyncCameraService
    from ..services.capture_pipeline.job_coordination_service import JobCoordinationService
    from ..services.capture_pipeline.rtsp_service import RTSPService
    from ..services.capture_pipeline.workflow_orchestrator_service import WorkflowOrchestratorService
    from ..services.corruption_pipeline.services.evaluation_service import SyncCorruptionEvaluationService
    from ..services.image_service import SyncImageService
    from ..services.overlay_pipeline.services.job_service import SyncOverlayJobService
    from ..services.scheduling.capture_timing_service import SyncCaptureTimingService
    from ..services.scheduling.time_window_service import SyncTimeWindowService
    from ..services.settings_service import SyncSettingsService
    from ..services.thumbnail_pipeline.services.job_service import SyncThumbnailJobService
    from ..services.timelapse_service import SyncTimelapseService
    from ..services.video_service import SyncVideoService


# Sync Settings Service Factory (Singleton)
def _create_sync_settings_service():
    """Factory for creating SyncSettingsService."""
    from ..services.settings_service import SyncSettingsService
    from .specialized import get_sync_settings_operations
    from ..services.weather.api_key_service import SyncAPIKeyService

    settings_ops = get_sync_settings_operations()
    # SyncAPIKeyService now uses singleton Operations in fallback methods
    api_key_service = SyncAPIKeyService(sync_db)

    return SyncSettingsService(sync_db, settings_ops, api_key_service)


register_singleton_factory("sync_settings_service", _create_sync_settings_service)


def get_sync_settings_service() -> "SyncSettingsService":
    """Get SyncSettingsService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_settings_service")


# Sync Video Service Factory (Singleton)
def _create_sync_video_service():
    """Factory for creating SyncVideoService."""
    from ..services.video_service import SyncVideoService
    from .specialized import get_sync_video_operations, get_sync_sse_events_operations
    
    video_ops = get_sync_video_operations()
    sse_ops = get_sync_sse_events_operations()
    settings_service = get_sync_settings_service()
    
    return SyncVideoService(sync_db, settings_service, video_ops, sse_ops)


register_singleton_factory("sync_video_service", _create_sync_video_service)


def get_sync_video_service() -> "SyncVideoService":
    """Get SyncVideoService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_video_service")


# Sync Image Service Factory (Singleton)
def _create_sync_image_service():
    """Factory for creating SyncImageService."""
    from ..services.image_service import SyncImageService
    from .specialized import get_sync_image_operations
    
    image_ops = get_sync_image_operations()
    return SyncImageService(sync_db, image_ops)


register_singleton_factory("sync_image_service", _create_sync_image_service)


def get_sync_image_service() -> "SyncImageService":
    """Get SyncImageService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_image_service")


# RTSP Service Factory (Singleton)
def _create_rtsp_service():
    """Factory for creating RTSPService."""
    from ..services.capture_pipeline.rtsp_service import RTSPService

    sync_settings_service = get_sync_settings_service()
    return RTSPService(sync_db, async_db, sync_settings_service)


register_singleton_factory("rtsp_service", _create_rtsp_service)


def get_rtsp_service() -> "RTSPService":
    """Get RTSPService with sync database dependency injection (singleton)."""
    return get_singleton_service("rtsp_service")


# Sync Corruption Evaluation Service Factory (Singleton)
def _create_sync_corruption_evaluation_service():
    """Factory for creating SyncCorruptionEvaluationService."""
    from ..services.corruption_pipeline.services.evaluation_service import SyncCorruptionEvaluationService
    return SyncCorruptionEvaluationService(sync_db)


register_singleton_factory("sync_corruption_evaluation_service", _create_sync_corruption_evaluation_service)


def get_sync_corruption_evaluation_service():
    """Get SyncCorruptionEvaluationService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_corruption_evaluation_service")


# Sync Camera Service Factory (Singleton) 
def _create_sync_camera_service():
    """Factory for creating SyncCameraService."""
    from ..services.camera_service import SyncCameraService
    from ..database import async_db
    settings_service = get_sync_settings_service()
    return SyncCameraService(
        db=sync_db,
        async_db=async_db, 
        settings_service=settings_service,
    )


register_singleton_factory("sync_camera_service", _create_sync_camera_service)


def get_sync_camera_service():
    """Get SyncCameraService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_camera_service")


# Job Coordination Service Factory (Singleton)
def _create_job_coordination_service():
    """Factory for creating JobCoordinationService.""" 
    from ..services.capture_pipeline.job_coordination_service import JobCoordinationService
    from ..database import async_db
    settings_service = get_sync_settings_service()
    return JobCoordinationService(
        db=sync_db,
        async_db=async_db,
        settings_service=settings_service,
    )


register_singleton_factory("job_coordination_service", _create_job_coordination_service)


def get_job_coordination_service():
    """Get JobCoordinationService with sync database dependency injection (singleton)."""
    return get_singleton_service("job_coordination_service")


# Sync Timelapse Service Factory (Singleton)
def _create_sync_timelapse_service():
    """Factory for creating SyncTimelapseService."""
    from ..services.timelapse_service import SyncTimelapseService
    from .specialized import get_sync_timelapse_operations
    
    timelapse_ops = get_sync_timelapse_operations()
    return SyncTimelapseService(sync_db, timelapse_ops)


register_singleton_factory("sync_timelapse_service", _create_sync_timelapse_service)


def get_sync_timelapse_service():
    """Get SyncTimelapseService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_timelapse_service")


# Sync Thumbnail Job Service Factory (Singleton)
def _create_sync_thumbnail_job_service():
    """Factory for creating SyncThumbnailJobService."""
    from ..services.thumbnail_pipeline.services.job_service import SyncThumbnailJobService
    from .specialized import get_sync_thumbnail_job_operations
    settings_service = get_sync_settings_service()
    thumbnail_job_ops = get_sync_thumbnail_job_operations()
    return SyncThumbnailJobService(sync_db, settings_service, thumbnail_job_ops)


register_singleton_factory("sync_thumbnail_job_service", _create_sync_thumbnail_job_service)


def get_sync_thumbnail_job_service():
    """Get SyncThumbnailJobService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_thumbnail_job_service")


# Sync Overlay Job Service Factory (Singleton)
def _create_sync_overlay_job_service():
    """Factory for creating SyncOverlayJobService."""
    from ..services.overlay_pipeline.services.job_service import SyncOverlayJobService
    settings_service = get_sync_settings_service()
    return SyncOverlayJobService(sync_db, settings_service)


register_singleton_factory("sync_overlay_job_service", _create_sync_overlay_job_service)


def get_sync_overlay_job_service():
    """Get SyncOverlayJobService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_overlay_job_service")


# Sync Overlay Service Factory (Singleton)
def _create_sync_overlay_service():
    """Factory for creating sync OverlayService."""
    from ..services.overlay_pipeline import OverlayService
    settings_service = get_sync_settings_service()
    image_service = get_sync_image_service()
    return OverlayService(
        db=sync_db,
        sync_image_service=image_service,
        settings_service=settings_service
    )


register_singleton_factory("sync_overlay_service", _create_sync_overlay_service)


def get_sync_overlay_service():
    """Get sync OverlayService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_overlay_service")


# Sync Time Window Service Factory (Singleton)
def _create_sync_time_window_service():
    """Factory for creating SyncTimeWindowService."""
    from ..services.scheduling.time_window_service import SyncTimeWindowService
    settings_service = get_sync_settings_service()
    return SyncTimeWindowService(
        db=sync_db,
        settings_service=settings_service,
    )


register_singleton_factory("sync_time_window_service", _create_sync_time_window_service)


def get_sync_time_window_service():
    """Get SyncTimeWindowService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_time_window_service")


# Sync Capture Timing Service Factory (Singleton)
def _create_sync_capture_timing_service():
    """Factory for creating SyncCaptureTimingService."""
    from ..services.scheduling.capture_timing_service import SyncCaptureTimingService
    from ..database import async_db
    settings_service = get_sync_settings_service()
    time_window_service = get_sync_time_window_service()
    return SyncCaptureTimingService(
        db=sync_db,
        async_db=async_db,
        time_window_service=time_window_service,
        settings_service=settings_service,
    )


register_singleton_factory("sync_capture_timing_service", _create_sync_capture_timing_service)


def get_sync_capture_timing_service():
    """Get SyncCaptureTimingService with sync database dependency injection (singleton)."""
    return get_singleton_service("sync_capture_timing_service")


# Workflow Orchestrator Service Factory (Singleton)
def _create_workflow_orchestrator_service():
    """Factory for creating WorkflowOrchestratorService using singleton dependencies."""
    from ..services.capture_pipeline.workflow_orchestrator_service import WorkflowOrchestratorService
    from ..database.sse_events_operations import SyncSSEEventsOperations
    from ..database import async_db
    
    # Use singleton services instead of creating new instances
    settings_service = get_sync_settings_service()
    image_service = get_sync_image_service()
    corruption_evaluation_service = get_sync_corruption_evaluation_service()
    camera_service = get_sync_camera_service()
    timelapse_service = get_sync_timelapse_service()
    rtsp_service = get_rtsp_service()
    job_coordinator = get_job_coordination_service()
    time_window_service = get_sync_time_window_service()
    scheduling_service = get_sync_capture_timing_service()
    
    # SSE operations - use singleton
    from .specialized import get_sync_sse_events_operations
    sse_ops = get_sync_sse_events_operations()
    
    # Weather service - use async singleton
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        from .async_services import get_weather_manager
        weather_service = loop.run_until_complete(get_weather_manager())
    except RuntimeError:
        # Fallback for sync contexts
        from ..services.weather.service import WeatherManager
        from .specialized import get_sync_weather_operations
        weather_ops = get_sync_weather_operations()
        weather_service = WeatherManager(weather_ops, settings_service)
    
    # Overlay service - use singleton
    overlay_service = get_sync_overlay_service()
    
    return WorkflowOrchestratorService(
        db=sync_db,
        image_service=image_service,
        corruption_evaluation_service=corruption_evaluation_service,
        camera_service=camera_service,
        timelapse_service=timelapse_service,
        rtsp_service=rtsp_service,
        job_coordinator=job_coordinator,
        sse_ops=sse_ops,
        scheduling_service=scheduling_service,
        weather_service=weather_service,
        overlay_service=overlay_service,
        settings_service=settings_service,
    )


register_singleton_factory("workflow_orchestrator_service", _create_workflow_orchestrator_service)


def get_workflow_orchestrator_service():
    """Get WorkflowOrchestratorService with all singleton dependencies (singleton)."""
    return get_singleton_service("workflow_orchestrator_service")
