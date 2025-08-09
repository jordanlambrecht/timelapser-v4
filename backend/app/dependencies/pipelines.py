# backend/app/dependencies/pipelines.py
"""
Pipeline service dependencies using the factory pattern.

These services handle various processing pipelines like thumbnails,
corruption detection, and video generation.
"""

from typing import TYPE_CHECKING

from ..database import async_db, sync_db
from .base import PipelineFactory

if TYPE_CHECKING:
    from ..services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
    from ..services.video_pipeline.video_workflow_service import VideoWorkflowService


# Thumbnail Pipeline Factory (Singleton)
def _create_thumbnail_pipeline() -> "ThumbnailPipeline":
    """Factory for creating ThumbnailPipeline."""
    from ..services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
    from .sync_services import get_sync_settings_service

    settings_service = get_sync_settings_service()
    from .sync_services import get_sync_image_service

    image_service = get_sync_image_service()
    # timelapse_service removed to break circular dependency

    return ThumbnailPipeline(
        database=sync_db,
        settings_service=settings_service,
        image_service=image_service,
        # timelapse_service removed - pipeline uses database operations directly
    )


from .registry import register_singleton_factory, get_singleton_service
register_singleton_factory("thumbnail_pipeline", _create_thumbnail_pipeline)


async def get_thumbnail_pipeline() -> "ThumbnailPipeline":
    """Get ThumbnailPipeline singleton with database and settings service dependency injection."""
    return get_singleton_service("thumbnail_pipeline")


# Corruption Pipeline Factory (Singleton)
def _create_corruption_pipeline():
    """Factory for creating CorruptionPipeline."""
    from ..services.corruption_pipeline import create_corruption_pipeline
    return create_corruption_pipeline(async_database=async_db)


register_singleton_factory("corruption_pipeline", _create_corruption_pipeline)


async def get_corruption_pipeline():
    """Get CorruptionPipeline singleton with async database dependency injection."""
    return get_singleton_service("corruption_pipeline")


# Video Pipeline Factory (Singleton)
def _create_video_pipeline() -> "VideoWorkflowService":
    """Factory for creating VideoWorkflowService."""
    from ..services.video_pipeline import create_video_pipeline
    return create_video_pipeline(sync_db=sync_db)


register_singleton_factory("video_pipeline", _create_video_pipeline)


def get_video_pipeline() -> "VideoWorkflowService":
    """Get VideoWorkflowService singleton with sync database dependency injection."""
    return get_singleton_service("video_pipeline")


async def get_async_video_pipeline() -> "VideoWorkflowService":
    """Get VideoWorkflowService singleton for async operations (same instance as sync)."""
    return get_singleton_service("video_pipeline")


# Video Job Service Factory (Singleton)
def _create_video_job_service():
    """Factory for creating VideoJobService."""
    from ..services.video_pipeline import create_video_job_service
    return create_video_job_service(sync_db=sync_db)


register_singleton_factory("video_job_service", _create_video_job_service)


def get_video_job_service():
    """Get VideoJobService singleton with sync database dependency injection."""
    return get_singleton_service("video_job_service")


# Overlay Integration Service Factory (Singleton)
def _create_overlay_integration_service():
    """Factory for creating OverlayIntegrationService."""
    from ..services.video_pipeline import create_overlay_integration_service
    return create_overlay_integration_service(sync_db=sync_db)


register_singleton_factory("overlay_integration_service", _create_overlay_integration_service)


def get_overlay_integration_service():
    """Get OverlayIntegrationService singleton with sync database dependency injection."""
    return get_singleton_service("overlay_integration_service")
