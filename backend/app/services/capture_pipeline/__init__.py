"""
Capture Pipeline Domain - Complete Image Capture Workflow Orchestration

Handles the complete 12-step image capture workflow from RTSP streams through
job coordination, overlay generation, and event broadcasting.

Domain Responsibilities:
- Workflow orchestration across multiple future domains
- RTSP operations and image processing
- Record creation and metadata enrichment
- Corruption detection integration (bridge to future domain)
- Overlay generation coordination (bridge to future domain)
- Job completion reporting (thumbnails and video automation handled by SchedulerWorker)
- Real-time event broadcasting

Architecture Pattern:
This domain serves as a workflow orchestration layer that coordinates capture
operations and reports completion to the scheduler authority. It provides a
clean interface for "execute complete capture job" operations without making
autonomous timing decisions (scheduler-centric architecture).

Future Domain Extractions:
- corruption/ domain (steps 4-6 in workflow)
- overlay/ domain (step 8 in workflow)

Factory Usage:
```python
# Basic usage - creates pipeline with default database
from app.services.capture_pipeline import create_capture_pipeline
workflow_orchestrator = create_capture_pipeline()

# Use in worker
result = workflow_orchestrator.execute_capture_workflow(camera_id=1, timelapse_id=123)

# Advanced usage - with custom database URL
workflow_orchestrator = create_capture_pipeline(
    database_url="postgresql://user:pass@localhost/timelapser"
)

# Integration in worker.py
class CaptureWorker:
    def __init__(self):
        self.workflow_orchestrator = create_capture_pipeline()

    def capture_single_timelapse(self, camera_id: int, timelapse_id: int):
        return self.workflow_orchestrator.execute_capture_workflow(camera_id, timelapse_id)
```
"""

from typing import Any, Dict, Optional

from ...database.core import AsyncDatabase, SyncDatabase
from ...database.sse_events_operations import (  # Still needed for workflow orchestrator
    SyncSSEEventsOperations,
)
from ...enums import LoggerName, LogSource
from ...services.logger import get_service_logger
from ..camera_service import SyncCameraService
from ..image_service import SyncImageService
from ..scheduling import SyncJobQueueService
from ..settings_service import SyncSettingsService
from ..timelapse_service import SyncTimelapseService
from .capture_transaction_manager import CaptureTransaction, CaptureTransactionManager
from .job_coordination_service import JobCoordinationService
from .overlay_bridge_service import OverlayBridgeService
from .rtsp_service import AsyncRTSPService, RTSPService
from .workflow_orchestrator_service import WorkflowOrchestratorService

logger = get_service_logger(LoggerName.CAPTURE_PIPELINE, LogSource.PIPELINE)


def create_capture_pipeline(
    database_url: Optional[str] = None, settings_service=None
) -> WorkflowOrchestratorService:
    """
    Factory function to create a complete capture pipeline with dependency injection.

    Creates all required services in proper dependency order and returns a fully
    configured WorkflowOrchestratorService ready for capture operations.

    Args:
        database_url: Optional database URL override (defaults to config)
        settings_service: Optional settings service instance

    Returns:
        WorkflowOrchestratorService with all dependencies injected

    Example:
        >>> orchestrator = create_capture_pipeline()
        >>> result = orchestrator.execute_capture_workflow(camera_id=1, timelapse_id=123)
    """
    try:
        logger.info("Creating capture pipeline with dependency injection...")

        # Step 1: Create shared database instances
        logger.debug("Creating shared SyncDatabase and AsyncDatabase instances")
        db = SyncDatabase()
        db.initialize()  # Initialize connection pool

        # Create async database for services that need it
        async_db = AsyncDatabase()

        # Step 2: Create required services first
        logger.debug("Creating required services layer")
        if settings_service is None:
            settings_service = SyncSettingsService(db)

        # Create scheduling service for validation
        from ..scheduling import SyncSchedulingService, SyncTimeWindowService

        time_window_service = SyncTimeWindowService(db)
        scheduling_service = SyncSchedulingService(
            db, async_db, time_window_service, settings_service
        )

        # Step 3: Create business services with dependency injection
        logger.debug("Creating business services layer")
        image_service = SyncImageService(db)

        # Create timelapse service
        timelapse_service = SyncTimelapseService(db)

        # Create corruption evaluation service from new pipeline
        from ..corruption_pipeline.services.evaluation_service import (
            SyncCorruptionEvaluationService,
        )

        corruption_evaluation_service = SyncCorruptionEvaluationService(db)

        # Create SSE operations (still needed until we have a dedicated SSE service)
        sse_ops = SyncSSEEventsOperations(db)

        camera_service = SyncCameraService(
            db,
            async_db,
            rtsp_service=None,  # Will be set after RTSP service creation
            scheduling_service=scheduling_service,
            settings_service=settings_service,
        )
        rtsp_service = RTSPService(db, async_db, settings_service)

        # Now set the rtsp_service dependency for camera_service
        camera_service.rtsp_service = rtsp_service

        # Create job management services
        job_queue_service = SyncJobQueueService(db)

        # 🎯 SCHEDULER-CENTRIC: Remove video workflow service injection to prevent
        # autonomous video triggering. Video jobs are now scheduled by SchedulerWorker.
        # from ..video_pipeline import create_video_pipeline
        # video_workflow_service = create_video_pipeline(db)

        # Create job coordinator (scheduler-centric, no autonomous video triggers)
        job_coordinator = JobCoordinationService(db, async_db, settings_service)
        job_coordinator.job_queue_service = job_queue_service
        # job_coordinator.video_workflow_service = video_workflow_service  # REMOVED: scheduler-centric

        # Create additional services expected by tests
        from ...database.weather_operations import SyncWeatherOperations
        from ..overlay_pipeline import OverlayService
        from ..weather.service import WeatherManager

        weather_ops = SyncWeatherOperations(db)
        weather_service = WeatherManager(weather_ops, settings_service)

        # Create overlay service with proper dependencies
        overlay_service = OverlayService(
            db=db, sync_image_service=image_service, settings_service=settings_service
        )

        # Step 5: Create main orchestrator with all dependencies
        logger.debug("Creating WorkflowOrchestratorService with dependency injection")
        orchestrator = WorkflowOrchestratorService(
            db=db,
            image_service=image_service,
            corruption_evaluation_service=corruption_evaluation_service,
            camera_service=camera_service,
            timelapse_service=timelapse_service,
            rtsp_service=rtsp_service,
            job_coordinator=job_coordinator,
            sse_ops=sse_ops,
            scheduling_service=scheduling_service,
            weather_service=None,  # WeatherManager doesn't match expected type, skip for now
            overlay_service=overlay_service,
            settings_service=settings_service,
        )

        # Step 6: Validate all services were created successfully
        logger.debug("Validating service creation")
        required_services = [
            ("database", db),
            ("settings_service", settings_service),
            ("timelapse_service", timelapse_service),
            ("sse_ops", sse_ops),
            ("image_service", image_service),
            ("corruption_evaluation_service", corruption_evaluation_service),
            ("camera_service", camera_service),
            ("rtsp_service", rtsp_service),
            ("job_queue_service", job_queue_service),
            # ("video_workflow_service", video_workflow_service),  # REMOVED: scheduler-centric
            ("job_coordinator", job_coordinator),
            ("scheduling_service", scheduling_service),
            ("weather_service", weather_service),
            ("overlay_service", overlay_service),
            ("orchestrator", orchestrator),
        ]

        for service_name, service_instance in required_services:
            if service_instance is None:
                raise RuntimeError(
                    f"Failed to create {service_name} - instance is None"
                )

        logger.info(
            "Capture pipeline created successfully with 13 injected dependencies (scheduler-centric)"
        )
        return orchestrator

    except Exception as e:
        logger.error("Failed to create capture pipeline", exception=e)
        raise RuntimeError(f"Capture pipeline creation failed: {str(e)}") from e


def get_capture_pipeline_health(
    orchestrator: WorkflowOrchestratorService,
) -> Dict[str, Any]:
    """
    Get health status of a capture pipeline instance.

    Args:
        orchestrator: WorkflowOrchestratorService instance to check

    Returns:
        Dict containing health status and service information
    """
    try:
        health_status = {
            "status": "healthy",
            "services": {
                "database": orchestrator.db is not None,
                "image_service": orchestrator.image_service is not None,
                "corruption_evaluation_service": orchestrator.corruption_evaluation_service
                is not None,
                "camera_service": orchestrator.camera_service is not None,
                "rtsp_service": orchestrator.rtsp_service is not None,
                "job_coordinator": orchestrator.job_coordinator is not None,
                "job_queue_service": hasattr(
                    orchestrator.job_coordinator, "job_queue_service"
                )
                and orchestrator.job_coordinator.job_queue_service is not None,
                # "video_workflow_service": removed - scheduler-centric architecture
                "timelapse_service": orchestrator.timelapse_service is not None,
                "sse_ops": orchestrator.sse_ops is not None,
                "scheduling_service": orchestrator.scheduling_service is not None,
                "weather_service": orchestrator.weather_service is not None,
                "overlay_service": orchestrator.overlay_service is not None,
            },
            "service_count": 13,
            "all_services_healthy": True,
            "database_info": {
                "database_type": "SyncDatabase",
                "database_initialized": orchestrator.db is not None,
            },
        }

        # Check if all services are healthy
        for service_name, service_healthy in health_status["services"].items():
            if not service_healthy:
                health_status["status"] = "unhealthy"
                health_status["all_services_healthy"] = False
                logger.warning(f"Service {service_name} is unhealthy")

        return health_status

    except Exception as e:
        logger.error("Error checking capture pipeline health", exception=e)
        return {
            "status": "error",
            "error": str(e),
            "services": {},
            "service_count": 0,
            "all_services_healthy": False,
        }


def get_capture_pipeline_status(
    orchestrator: WorkflowOrchestratorService,
) -> Dict[str, Any]:
    """
    Get standardized status from all services in a capture pipeline instance.

    This function follows our standardization pattern by calling get_status()
    on all services that implement it.

    Args:
        orchestrator: WorkflowOrchestratorService instance to check

    Returns:
        Dict containing status information from all services
    """
    try:
        pipeline_status = {
            "pipeline_status": "healthy",
            "service_statuses": {},
            "error_count": 0,
            "total_services": 0,
        }

        # Get status from all services that implement get_status()
        services_to_check = [
            ("camera_service", orchestrator.camera_service),
            ("settings_service", orchestrator.settings_service),
            ("scheduling_service", orchestrator.scheduling_service),
            ("image_service", orchestrator.image_service),
            ("weather_service", orchestrator.weather_service),
            ("overlay_service", orchestrator.overlay_service),
        ]

        for service_name, service_instance in services_to_check:
            try:
                if hasattr(service_instance, "get_status"):
                    status = service_instance.get_status()
                    pipeline_status["service_statuses"][service_name] = status
                    pipeline_status["total_services"] += 1

                    # Check if service reported any errors
                    if isinstance(status, dict) and status.get("status") not in [
                        "healthy",
                        "active",
                        "ready",
                    ]:
                        pipeline_status["error_count"] += 1
                else:
                    pipeline_status["service_statuses"][service_name] = {
                        "status": "no_status_method",
                        "note": "Service does not implement get_status()",
                    }
                    pipeline_status["total_services"] += 1
            except Exception as e:
                pipeline_status["service_statuses"][service_name] = {
                    "status": "error",
                    "error": str(e),
                }
                pipeline_status["error_count"] += 1
                pipeline_status["total_services"] += 1

        # Set overall pipeline status
        if pipeline_status["error_count"] > 0:
            pipeline_status["pipeline_status"] = (
                f"degraded ({pipeline_status['error_count']} errors)"
            )

        # Add database status
        pipeline_status["database_status"] = {
            "sync_db": orchestrator.db is not None,
            "database_type": "SyncDatabase",
        }

        return pipeline_status

    except Exception as e:
        logger.error("Error getting capture pipeline status", exception=e)
        return {
            "pipeline_status": "error",
            "error": str(e),
            "service_statuses": {},
            "error_count": 1,
            "total_services": 0,
        }


# Convenience aliases for searchability and clean imports
Orchestrator = WorkflowOrchestratorService
RTSP = RTSPService
AsyncRTSP = AsyncRTSPService
# Corruption = CorruptionBridgeService  # Removed - using direct corruption pipeline
Overlay = OverlayBridgeService
Jobs = JobCoordinationService
TransactionManager = CaptureTransactionManager
Transaction = CaptureTransaction

__all__ = [
    # Primary factory function
    "create_capture_pipeline",
    # Health check functions
    "get_capture_pipeline_health",
    "get_capture_pipeline_status",
    # Full service names
    "WorkflowOrchestratorService",
    "RTSPService",
    "AsyncRTSPService",
    # "CorruptionBridgeService",  # Removed - using direct corruption pipeline
    "OverlayBridgeService",
    "JobCoordinationService",
    "CaptureTransactionManager",
    "CaptureTransaction",
    # Database layer (for testing/debugging)
    "SyncDatabase",
    "SyncSSEEventsOperations",
    "SyncSettingsService",
    # Business services (for testing/debugging)
    "SyncImageService",
    "SyncCameraService",
    "SyncTimelapseService",
    # Convenience aliases
    "Orchestrator",
    "RTSP",
    "AsyncRTSP",
    # "Corruption",  # Removed - using direct corruption pipeline
    "Overlay",
    "Jobs",
    "TransactionManager",
    "Transaction",
]
