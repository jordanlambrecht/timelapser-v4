# backend/app/services/video_pipeline/__init__.py
"""
Video Pipeline Factory - Simplified Architecture

Factory pattern implementation for simplified video generation pipeline.
Creates 3 core services with dependency injection.
"""

from typing import Optional
from loguru import logger

from ...database.core import SyncDatabase
from .video_workflow_service import VideoWorkflowService
from .video_job_service import VideoJobService
from .overlay_integration_service import OverlayIntegrationService
from ..log_service import SyncLogService


def create_video_pipeline(
    db: Optional[SyncDatabase] = None, log_service: Optional[SyncLogService] = None
) -> VideoWorkflowService:
    """
    Factory function to create simplified video pipeline with dependency injection.

    Creates all required services in proper dependency order and returns a fully
    configured VideoWorkflowService ready for video generation operations.

    Args:
        db: Optional SyncDatabase instance (creates new if not provided)
        log_service: Optional SyncLogService for audit trail and structured logging

    Returns:
        VideoWorkflowService with all dependencies injected
    """
    try:
        logger.info("🏭 Creating simplified video pipeline...")

        # Step 1: Create shared database instance if not provided
        if db is None:
            db = SyncDatabase()
            logger.debug("Created new database instance for video pipeline")

        # Step 2: Create business services (simplified architecture)
        logger.debug("Initializing video pipeline services...")

        job_service = VideoJobService(db)
        logger.debug("✅ VideoJobService created")

        overlay_service = OverlayIntegrationService(db)
        logger.debug("✅ OverlayIntegrationService created")

        # Create log service if not provided
        if log_service is None:
            log_service = SyncLogService(db)
            logger.debug("✅ SyncLogService created")
        else:
            logger.debug("✅ SyncLogService provided via dependency injection")

        # Step 3: Create main workflow service (consolidated orchestrator)
        workflow_service = VideoWorkflowService(
            db=db,
            job_service=job_service,
            overlay_service=overlay_service,
            log_service=log_service,
        )
        logger.debug("✅ VideoWorkflowService created with all dependencies")

        logger.info("✅ Simplified video pipeline created successfully")
        return workflow_service

    except Exception as e:
        logger.error(f"❌ Failed to create video pipeline: {e}")
        raise


def create_video_job_service(db: SyncDatabase) -> VideoJobService:
    """
    Factory function to create video job service.

    Args:
        db: SyncDatabase instance

    Returns:
        Configured VideoJobService instance
    """
    try:
        logger.debug("Creating video job service...")
        return VideoJobService(db)
    except Exception as e:
        logger.error(f"Failed to create video job service: {e}")
        raise


def create_overlay_integration_service(db: SyncDatabase) -> OverlayIntegrationService:
    """
    Factory function to create overlay integration service.

    Args:
        db: SyncDatabase instance

    Returns:
        Configured OverlayIntegrationService instance
    """
    try:
        logger.debug("Creating overlay integration service...")
        return OverlayIntegrationService(db)
    except Exception as e:
        logger.error(f"Failed to create overlay integration service: {e}")
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
        logger.error(f"Video pipeline health check failed: {e}")
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
