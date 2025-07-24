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

from typing import Optional, Dict, Any
from loguru import logger

# Import database layer
from ...database.core import SyncDatabase
from ...database.camera_operations import SyncCameraOperations
from ...database.timelapse_operations import SyncTimelapseOperations
from ...database.sse_events_operations import SyncSSEEventsOperations

# Import business services  
from ..image_service import SyncImageService
# Old corruption service import removed - using new pipeline
from ..camera_service import SyncCameraService
from ..settings_service import SyncSettingsService
from ..scheduling import SyncJobQueueService

# Main service imports with descriptive names
from .workflow_orchestrator_service import WorkflowOrchestratorService
from .rtsp_service import RTSPService, AsyncRTSPService
# Corruption bridge service removed - using direct corruption pipeline integration
from .overlay_bridge_service import OverlayBridgeService
from .job_coordination_service import JobCoordinationService
from .capture_transaction_manager import CaptureTransactionManager, CaptureTransaction


def create_capture_pipeline(
    database_url: Optional[str] = None,
    settings_service = None
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
        logger.info("🏭 Creating capture pipeline with dependency injection...")
        
        # Step 1: Create shared database instance
        logger.debug("📊 Creating shared SyncDatabase instance")
        db = SyncDatabase()
        db.initialize()  # Initialize connection pool
        
        # Step 2: Create required services first
        logger.debug("🛠️ Creating required services layer")
        if settings_service is None:
            settings_service = SyncSettingsService(db)
        
        # Create scheduling service for validation
        from ..scheduling import SyncTimeWindowService
        from ..scheduling import SyncSchedulingService
        time_window_service = SyncTimeWindowService(db)
        scheduling_service = SyncSchedulingService(db, time_window_service)
        
        # Step 3: Create database operations (require database only)
        logger.debug("🗄️ Creating database operations layer")
        camera_ops = SyncCameraOperations(db)
        timelapse_ops = SyncTimelapseOperations(db)  
        sse_ops = SyncSSEEventsOperations(db)
        
        # Step 4: Create business services (may have service dependencies)
        logger.debug("🔧 Creating business services layer")
        image_service = SyncImageService(db)
        
        # Create corruption evaluation service from new pipeline
        from ..corruption_pipeline.services.evaluation_service import SyncCorruptionEvaluationService
        corruption_evaluation_service = SyncCorruptionEvaluationService(db)
        
        camera_service = SyncCameraService(db)
        rtsp_service = RTSPService(db)
        
        # Create job management services
        job_queue_service = SyncJobQueueService(db)
        
        # 🎯 SCHEDULER-CENTRIC: Remove video workflow service injection to prevent
        # autonomous video triggering. Video jobs are now scheduled by SchedulerWorker.
        # from ..video_pipeline import create_video_pipeline
        # video_workflow_service = create_video_pipeline(db)
        
        # Create job coordinator (scheduler-centric, no autonomous video triggers)
        job_coordinator = JobCoordinationService(db)
        job_coordinator.job_queue_service = job_queue_service
        # job_coordinator.video_workflow_service = video_workflow_service  # REMOVED: scheduler-centric
        
        # Create additional services expected by tests
        from ..weather.service import WeatherManager
        from ..overlay_pipeline import OverlayService
        from ...database.weather_operations import SyncWeatherOperations
        
        weather_ops = SyncWeatherOperations(db)
        weather_service = WeatherManager(weather_ops, settings_service)
        overlay_service = OverlayService(db)
        
        # Step 5: Create main orchestrator with all dependencies
        logger.debug("🎼 Creating WorkflowOrchestratorService with dependency injection")
        orchestrator = WorkflowOrchestratorService(
            db=db,
            image_service=image_service,
            corruption_evaluation_service=corruption_evaluation_service,
            camera_service=camera_service,
            rtsp_service=rtsp_service,
            job_coordinator=job_coordinator,
            camera_ops=camera_ops,
            timelapse_ops=timelapse_ops,
            sse_ops=sse_ops,
            scheduling_service=scheduling_service,
            weather_service=weather_service,
            overlay_service=overlay_service,
        )
        
        # Step 6: Validate all services were created successfully
        logger.debug("🔍 Validating service creation")
        required_services = [
            ("database", db),
            ("settings_service", settings_service),
            ("camera_ops", camera_ops),
            ("timelapse_ops", timelapse_ops),
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
                raise RuntimeError(f"Failed to create {service_name} - instance is None")
        
        logger.info("✅ Capture pipeline created successfully with 13 injected dependencies (scheduler-centric)")
        return orchestrator
        
    except Exception as e:
        logger.error(f"❌ Failed to create capture pipeline: {e}")
        raise RuntimeError(f"Capture pipeline creation failed: {str(e)}") from e


def get_capture_pipeline_health(orchestrator: WorkflowOrchestratorService) -> Dict[str, Any]:
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
                "corruption_evaluation_service": orchestrator.corruption_evaluation_service is not None,
                "camera_service": orchestrator.camera_service is not None,
                "rtsp_service": orchestrator.rtsp_service is not None,
                "job_coordinator": orchestrator.job_coordinator is not None,
                "job_queue_service": hasattr(orchestrator.job_coordinator, 'job_queue_service') and orchestrator.job_coordinator.job_queue_service is not None,
                # "video_workflow_service": removed - scheduler-centric architecture
                "camera_ops": orchestrator.camera_ops is not None,
                "timelapse_ops": orchestrator.timelapse_ops is not None,
                "sse_ops": orchestrator.sse_ops is not None,
                "scheduling_service": orchestrator.scheduling_service is not None,
                "weather_service": orchestrator.weather_service is not None,
                "overlay_service": orchestrator.overlay_service is not None,
            },
            "service_count": 13,
            "all_services_healthy": True,
            "database_info": {
                "database_type": "SyncDatabase",
                "database_initialized": orchestrator.db is not None
            }
        }
        
        # Check if all services are healthy
        for service_name, service_healthy in health_status["services"].items():
            if not service_healthy:
                health_status["status"] = "unhealthy"
                health_status["all_services_healthy"] = False
                logger.warning(f"Service {service_name} is unhealthy")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error checking capture pipeline health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "services": {},
            "service_count": 0,
            "all_services_healthy": False
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
    # Health check function
    "get_capture_pipeline_health",
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
    "SyncCameraOperations",
    "SyncTimelapseOperations", 
    "SyncSSEEventsOperations",
    "SyncSettingsService",
    # Business services (for testing/debugging)
    "SyncImageService",
    # "SyncCorruptionService",  # Removed - using corruption pipeline services
    "SyncCameraService",
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
