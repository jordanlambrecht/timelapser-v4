# backend/app/dependencies/type_annotations.py
"""
Auto-generated type annotations for FastAPI dependency injection.

This eliminates the 40+ repetitive type annotation definitions from the original
dependencies.py by using a standardized pattern generator.
"""

from typing import Annotated

from fastapi import Depends

# Direct imports for type annotations (to avoid string references)
from ..database.core import AsyncDatabase, SyncDatabase
from ..database.corruption_operations import CorruptionOperations
from ..database.overlay_job_operations import OverlayJobOperations
from ..database.scheduled_job_operations import ScheduledJobOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..database.thumbnail_job_operations import ThumbnailJobOperations
from ..services.admin_service import AdminService
from ..services.camera_service import CameraService
from ..services.capture_pipeline import AsyncRTSPService, WorkflowOrchestratorService
from ..services.capture_pipeline.rtsp_service import RTSPService
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
from ..services.scheduling.capture_timing_service import (
    CaptureTimingService,
    SyncCaptureTimingService,
)
from ..services.scheduling.job_queue_service import JobQueueService, SyncJobQueueService
from ..services.scheduling.scheduler_authority_service import SchedulerService
from ..services.scheduling.time_window_service import (
    SyncTimeWindowService,
    TimeWindowService,
)
from ..services.settings_service import SettingsService
from ..services.statistics_service import StatisticsService
from ..services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
from ..services.timelapse_service import TimelapseService
from ..services.video_pipeline.video_workflow_service import VideoWorkflowService
from ..services.video_service import SyncVideoService, VideoService
from ..services.weather.service import WeatherManager
from .async_services import (
    get_admin_service,
    get_camera_service,
    get_corruption_evaluation_service,
    get_corruption_health_service,
    get_corruption_statistics_service,
    get_health_service,
    get_image_service,
    get_logger_service,
    get_overlay_job_service,
    get_overlay_service,
    get_settings_service,
    get_statistics_service,
    get_timelapse_service,
    get_video_service,
    get_weather_manager,
)

# Import all dependency functions
from .database import get_async_database, get_sync_database
from .pipelines import (
    get_async_video_pipeline,
    get_corruption_pipeline,
    get_overlay_integration_service,
    get_thumbnail_pipeline,
    get_video_job_service,
    get_video_pipeline,
)
from .scheduling import (
    get_job_queue_service,
    get_scheduler_service,
    get_scheduling_service,
    get_sync_job_queue_service,
    get_sync_scheduling_service,
    get_sync_time_window_service,
    get_time_window_service,
)
from .specialized import (
    get_async_sse_events_operations,
    get_corruption_operations,
    get_overlay_job_operations,
    get_scheduled_job_operations,
    get_thumbnail_job_operations,
)
from .sync_services import (
    get_rtsp_service,
    get_sync_settings_service,
    get_sync_video_service,
)
from .workflow import (
    get_async_rtsp_service,
    get_workflow_orchestrator_service,
)

# Database Type Annotations
AsyncDatabaseDep = Annotated[AsyncDatabase, Depends(get_async_database)]
SyncDatabaseDep = Annotated[SyncDatabase, Depends(get_sync_database)]

# Async Service Type Annotations
CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]
VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]
TimelapseServiceDep = Annotated[TimelapseService, Depends(get_timelapse_service)]
ImageServiceDep = Annotated[ImageService, Depends(get_image_service)]
SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
WeatherManagerDep = Annotated[WeatherManager, Depends(get_weather_manager)]
StatisticsServiceDep = Annotated[StatisticsService, Depends(get_statistics_service)]
LoggerServiceDep = Annotated[LoggerService, Depends(get_logger_service)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
OverlayServiceDep = Annotated[AsyncOverlayService, Depends(get_overlay_service)]
OverlayJobServiceDep = Annotated[
    AsyncOverlayJobService, Depends(get_overlay_job_service)
]

# Corruption Service Type Annotations
CorruptionStatisticsServiceDep = Annotated[CorruptionStatisticsService, Depends(get_corruption_statistics_service)]
CorruptionHealthServiceDep = Annotated[CorruptionHealthService, Depends(get_corruption_health_service)]
CorruptionEvaluationServiceDep = Annotated[CorruptionEvaluationService, Depends(get_corruption_evaluation_service)]

# Sync Service Type Annotations
SyncSettingsServiceDep = Annotated[SettingsService, Depends(get_sync_settings_service)]
SyncVideoServiceDep = Annotated[SyncVideoService, Depends(get_sync_video_service)]
RTSPServiceDep = Annotated[RTSPService, Depends(get_rtsp_service)]

# Workflow Type Annotations
AsyncRTSPServiceDep = Annotated[AsyncRTSPService, Depends(get_async_rtsp_service)]
WorkflowOrchestratorServiceDep = Annotated[
    WorkflowOrchestratorService, Depends(get_workflow_orchestrator_service)
]

# Scheduling Type Annotations
TimeWindowServiceDep = Annotated[TimeWindowService, Depends(get_time_window_service)]
SyncTimeWindowServiceDep = Annotated[
    SyncTimeWindowService, Depends(get_sync_time_window_service)
]
SchedulingServiceDep = Annotated[CaptureTimingService, Depends(get_scheduling_service)]
SyncSchedulingServiceDep = Annotated[
    SyncCaptureTimingService, Depends(get_sync_scheduling_service)
]
JobQueueServiceDep = Annotated[JobQueueService, Depends(get_job_queue_service)]
SyncJobQueueServiceDep = Annotated[
    SyncJobQueueService, Depends(get_sync_job_queue_service)
]
SchedulerServiceDep = Annotated[SchedulerService, Depends(get_scheduler_service)]

# Pipeline Type Annotations
ThumbnailPipelineDep = Annotated[ThumbnailPipeline, Depends(get_thumbnail_pipeline)]
CorruptionPipelineDep = Annotated[object, Depends(get_corruption_pipeline)]
VideoPipelineDep = Annotated[VideoWorkflowService, Depends(get_video_pipeline)]
AsyncVideoPipelineDep = Annotated[
    VideoWorkflowService, Depends(get_async_video_pipeline)
]
VideoJobServiceDep = Annotated[object, Depends(get_video_job_service)]
OverlayIntegrationServiceDep = Annotated[
    object, Depends(get_overlay_integration_service)
]

# Specialized Type Annotations
CorruptionOperationsDep = Annotated[
    CorruptionOperations, Depends(get_corruption_operations)
]
OverlayJobOperationsDep = Annotated[
    OverlayJobOperations, Depends(get_overlay_job_operations)
]
ScheduledJobOperationsDep = Annotated[
    ScheduledJobOperations, Depends(get_scheduled_job_operations)
]
SSEEventsOperationsDep = Annotated[
    SSEEventsOperations, Depends(get_async_sse_events_operations)
]
ThumbnailJobOperationsDep = Annotated[
    ThumbnailJobOperations, Depends(get_thumbnail_job_operations)
]

# Export all type annotations
__all__ = [
    # Database
    "AsyncDatabaseDep",
    "SyncDatabaseDep",
    # Async Services
    "CameraServiceDep",
    "VideoServiceDep",
    "TimelapseServiceDep",
    "ImageServiceDep",
    "SettingsServiceDep",
    "WeatherManagerDep",
    "StatisticsServiceDep",
    "LoggerServiceDep",
    "HealthServiceDep",
    "AdminServiceDep",
    "OverlayServiceDep",
    "OverlayJobServiceDep",
    # Sync Services
    "SyncSettingsServiceDep",
    "SyncVideoServiceDep",
    "RTSPServiceDep",
    # Workflow
    "AsyncRTSPServiceDep",
    "WorkflowOrchestratorServiceDep",
    # Scheduling
    "TimeWindowServiceDep",
    "SyncTimeWindowServiceDep",
    "SchedulingServiceDep",
    "SyncSchedulingServiceDep",
    "JobQueueServiceDep",
    "SyncJobQueueServiceDep",
    "SchedulerServiceDep",
    # Pipelines
    "ThumbnailPipelineDep",
    "CorruptionPipelineDep",
    "VideoPipelineDep",
    "AsyncVideoPipelineDep",
    "VideoJobServiceDep",
    "OverlayIntegrationServiceDep",
    # Specialized
    "CorruptionOperationsDep",
    "OverlayJobOperationsDep",
    "SSEEventsOperationsDep",
    "ScheduledJobOperationsDep",
    "ThumbnailJobOperationsDep",
]
