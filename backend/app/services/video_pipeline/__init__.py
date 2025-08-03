# backend/app/services/video_pipeline/__init__.py
"""
Video Pipeline Factory - Simplified Architecture

Factory pattern implementation for simplified video generation pipeline.
Creates 3 core services with dependency injection.
"""

from typing import Optional
from ...services.logger import get_service_logger
from ...enums import LoggerName

logger = get_service_logger(LoggerName.VIDEO_PIPELINE)

from ...database.core import SyncDatabase
from .video_workflow_service import VideoWorkflowService
from .video_job_service import VideoJobService
from .overlay_integration_service import OverlayIntegrationService


def create_video_pipeline(
    db: Optional[SyncDatabase] = None, settings_service=None
) -> VideoWorkflowService:
    """
    Factory function to create simplified video pipeline with dependency injection.

    Creates all required services in proper dependency order and returns a fully
    configured VideoWorkflowService ready for video generation operations.

    Args:
        db: Optional SyncDatabase instance (creates new if not provided)
        settings_service: Optional settings service for configuration

    Returns:
        VideoWorkflowService with all dependencies injected
    """
    try:
        logger.info("Creating simplified video pipeline...")

        # Step 1: Create shared database instances if not provided
        if db is None:
            db = SyncDatabase()
            logger.debug("Created new database instance for video pipeline")

        # Create async database for services that need it
        from ...database.core import AsyncDatabase

        async_db = AsyncDatabase()

        # Create settings service if not provided
        if settings_service is None:
            from ...services.settings_service import SyncSettingsService

            settings_service = SyncSettingsService(db)
            logger.debug("Created settings service for video pipeline")

        # Step 2: Create business services (simplified architecture)
        logger.debug("Initializing video pipeline services...")

        job_service = VideoJobService(db, async_db, settings_service)
        logger.debug("VideoJobService created")

        overlay_service = OverlayIntegrationService(db)
        logger.debug("OverlayIntegrationService created")

        # Create video and timelapse services for workflow service
        from ...services.video_service import SyncVideoService
        from ...services.timelapse_service import SyncTimelapseService

        video_service = SyncVideoService(db, settings_service)
        timelapse_service = SyncTimelapseService(db)
        logger.debug("Video and timelapse services created")

        # Step 3: Create main workflow service (consolidated orchestrator)
        workflow_service = VideoWorkflowService(
            db=db,
            job_service=job_service,
            overlay_service=overlay_service,
            settings_service=settings_service,
            video_service=video_service,
            timelapse_service=timelapse_service,
        )
        logger.debug("VideoWorkflowService created with all dependencies")

        logger.info("Simplified video pipeline created successfully")
        return workflow_service

    except Exception as e:
        logger.error("Failed to create video pipeline", exception=e)
        raise


def create_video_job_service(
    db: SyncDatabase, async_db=None, settings_service=None
) -> VideoJobService:
    """
    Factory function to create video job service.

    Args:
        db: SyncDatabase instance
        async_db: Optional AsyncDatabase instance
        settings_service: Optional settings service

    Returns:
        Configured VideoJobService instance
    """
    try:
        logger.debug("Creating video job service...")

        # Create missing dependencies
        if async_db is None:
            from ...database.core import AsyncDatabase

            async_db = AsyncDatabase()

        if settings_service is None:
            from ...services.settings_service import SyncSettingsService

            settings_service = SyncSettingsService(db)

        return VideoJobService(db, async_db, settings_service)
    except Exception as e:
        logger.error("Failed to create video job service", exception=e)
        raise


def create_overlay_integration_service(db: SyncDatabase) -> OverlayIntegrationService:
    """
    Factory function to create overlay integration service.

    Args:
        db: SyncDatabase instance

    Returns:
        OverlayIntegrationService: Configured overlay integration service
    """
    try:
        logger.debug("Creating overlay integration service")
        return OverlayIntegrationService(db)
    except Exception as e:
        logger.error("Failed to create overlay integration service", exception=e)
        raise


# Service health check helper
def get_video_pipeline_health(workflow_service: VideoWorkflowService) -> dict:
    """
    Get comprehensive health status of video pipeline.

    Args:
        workflow_service: VideoWorkflowService instance

    Returns:
        Dict containing detailed health metrics
    """
    try:
        # Get service health from main workflow service
        workflow_health = workflow_service.get_workflow_health()

        # Get job service health
        job_health = workflow_service.job_service.get_service_health()

        # Get overlay service health
        overlay_health = workflow_service.overlay_service.get_service_health()

        # Determine overall health
        all_healthy = all(
            [
                workflow_health.get("status") == "healthy",
                job_health.get("status") == "healthy",
                overlay_health.get("status")
                in ["healthy", "degraded"],  # Overlay can be degraded
            ]
        )

        return {
            "service": "video_pipeline",
            "status": "healthy" if all_healthy else "unhealthy",
            "services": {
                "workflow_service": workflow_health,
                "job_service": job_health,
                "overlay_service": overlay_health,
            },
            "service_count": 3,
            "architecture": "simplified_3_service",
            "error": None if all_healthy else "One or more services unhealthy",
        }

    except Exception as e:
        logger.error("Video pipeline health check failed", exception=e)
        return {
            "service": "video_pipeline",
            "status": "unhealthy",
            "error": str(e),
        }


# Export main factory function and services
__all__ = [
    "create_video_pipeline",
    "create_video_job_service",
    "create_overlay_integration_service",
    "get_video_pipeline_health",
    "VideoWorkflowService",
    "VideoJobService",
    "OverlayIntegrationService",
]

# Service count for monitoring
VIDEO_PIPELINE_SERVICE_COUNT = 3
