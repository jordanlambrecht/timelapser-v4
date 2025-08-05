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


# Thumbnail Pipeline Factory
async def get_thumbnail_pipeline() -> "ThumbnailPipeline":
    """Get ThumbnailPipeline with database and settings service dependency injection."""
    from ..services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
    from .sync_services import get_sync_settings_service

    settings_service = get_sync_settings_service()
    return ThumbnailPipeline(database=sync_db, settings_service=settings_service)


# Corruption Pipeline Factory
async def get_corruption_pipeline():
    """Get CorruptionPipeline with async database dependency injection."""
    factory = PipelineFactory(
        factory_module="app.services.corruption_pipeline",
        factory_function="create_corruption_pipeline",
        factory_args={"async_database": async_db},
    )
    return factory.get_service()


# Video Pipeline Factory (Sync)
def get_video_pipeline() -> "VideoWorkflowService":
    """Get complete video pipeline with factory pattern dependency injection."""
    factory = PipelineFactory(
        factory_module="app.services.video_pipeline",
        factory_function="create_video_pipeline",
        factory_args={"sync_db": sync_db},
    )
    return factory.get_service()


# Video Pipeline Factory (Async)
async def get_async_video_pipeline() -> "VideoWorkflowService":
    """Get video pipeline for async operations (using sync db for consistency)."""
    factory = PipelineFactory(
        factory_module="app.services.video_pipeline",
        factory_function="create_video_pipeline",
        factory_args={"sync_db": sync_db},
    )
    return factory.get_service()


# Video Job Service Factory
def get_video_job_service():
    """Get VideoJobService with sync database dependency injection."""
    factory = PipelineFactory(
        factory_module="app.services.video_pipeline",
        factory_function="create_video_job_service",
        factory_args={"sync_db": sync_db},
    )
    return factory.get_service()


# Overlay Integration Service Factory
def get_overlay_integration_service():
    """Get OverlayIntegrationService with sync database dependency injection."""
    factory = PipelineFactory(
        factory_module="app.services.video_pipeline",
        factory_function="create_overlay_integration_service",
        factory_args={"sync_db": sync_db},
    )
    return factory.get_service()
