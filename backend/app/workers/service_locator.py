# backend/app/workers/service_locator.py
"""
Service Locator for Worker Dependencies

Simplified dependency injection pattern that replaces the complex worker factory.
Provides centralized service management with lazy initialization and clear interfaces.
"""

from typing import Dict, Any, TypeVar
from functools import lru_cache

from ..database.core import AsyncDatabase, SyncDatabase
from ..services.settings_service import SyncSettingsService, SettingsService
from ..services.image_service import SyncImageService
from ..services.timelapse_service import SyncTimelapseService, TimelapseService
from ..services.camera_service import CameraService
from ..services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
from ..services.overlay_pipeline.overlay_pipeline import OverlayPipeline
from ..services.weather.service import WeatherManager
from ..database.weather_operations import SyncWeatherOperations
from ..database.sse_events_operations import (
    SyncSSEEventsOperations,
    SSEEventsOperations,
)
from ..services.overlay_pipeline.services.job_service import SyncOverlayJobService
from ..services.thumbnail_pipeline.services.job_service import SyncThumbnailJobService
from ..services.capture_pipeline.workflow_orchestrator_service import (
    WorkflowOrchestratorService,
)
from ..services.capture_pipeline.job_coordination_service import JobCoordinationService
from ..services.capture_pipeline.rtsp_service import RTSPService
from ..services.corruption_pipeline.services.evaluation_service import (
    SyncCorruptionEvaluationService,
)
from ..services.camera_service import SyncCameraService
from ..enums import LoggerName, LogEmoji
from ..services.logger import get_service_logger


from .thumbnail_worker import ThumbnailWorker
from .overlay_worker import OverlayWorker
from .cleanup_worker import CleanupWorker
from .weather_worker import WeatherWorker
from .video_worker import VideoWorker
from .capture_worker import CaptureWorker

T = TypeVar("T")


class ServiceLocator:
    """
    Service locator for worker dependencies.

    Replaces the complex worker factory with a centralized service registry
    that provides lazy initialization and clear dependency management.
    """

    def __init__(self, sync_db: SyncDatabase, async_db: AsyncDatabase):
        """Initialize service locator with database connections."""
        self.sync_db = sync_db
        self.async_db = async_db
        self._services: Dict[str, Any] = {}
        self._logger = get_service_logger(LoggerName.SYSTEM)

    @lru_cache(maxsize=None)
    def get_sync_settings_service(self) -> SyncSettingsService:
        """Get sync settings service (cached)."""
        return SyncSettingsService(self.sync_db)

    @lru_cache(maxsize=None)
    def get_async_settings_service(self) -> SettingsService:
        """Get async settings service (cached)."""
        return SettingsService(self.async_db)

    @lru_cache(maxsize=None)
    def get_sync_image_service(self) -> SyncImageService:
        """Get sync image service (cached)."""
        return SyncImageService(self.sync_db)

    @lru_cache(maxsize=None)
    def get_sync_timelapse_service(self) -> SyncTimelapseService:
        """Get sync timelapse service (cached)."""
        return SyncTimelapseService(self.sync_db)

    @lru_cache(maxsize=None)
    def get_async_timelapse_service(self) -> TimelapseService:
        """Get async timelapse service (cached)."""
        return TimelapseService(self.async_db)

    @lru_cache(maxsize=None)
    def get_camera_service(self) -> CameraService:
        """Get camera service (cached)."""
        return CameraService(
            db=self.async_db,
            sync_db=self.sync_db,
            settings_service=self.get_async_settings_service(),
        )

    @lru_cache(maxsize=None)
    def get_weather_manager(self) -> WeatherManager:
        """Get weather manager (cached)."""
        weather_ops = SyncWeatherOperations(self.sync_db)
        settings_service = self.get_sync_settings_service()
        return WeatherManager(weather_ops, settings_service)

    @lru_cache(maxsize=None)
    def get_sync_sse_operations(self) -> SyncSSEEventsOperations:
        """Get sync SSE operations (cached)."""
        return SyncSSEEventsOperations(self.sync_db)

    @lru_cache(maxsize=None)
    def get_async_sse_operations(self) -> SSEEventsOperations:
        """Get async SSE operations (cached)."""
        return SSEEventsOperations(self.async_db)

    @lru_cache(maxsize=None)
    def get_thumbnail_pipeline(self) -> ThumbnailPipeline:
        """Get thumbnail pipeline (cached)."""
        return ThumbnailPipeline(
            database=self.sync_db,
            async_database=self.async_db,
            settings_service=self.get_sync_settings_service(),
            image_service=self.get_sync_image_service(),
        )

    @lru_cache(maxsize=None)
    def get_overlay_pipeline(self) -> OverlayPipeline:
        """Get overlay pipeline (cached)."""
        return OverlayPipeline(
            database=self.sync_db,
            async_database=self.async_db,
            settings_service=self.get_sync_settings_service(),
            sse_ops=self.get_sync_sse_operations(),
        )

    @lru_cache(maxsize=None)
    def get_thumbnail_job_service(self) -> SyncThumbnailJobService:
        """Get thumbnail job service (cached)."""
        settings_service = self.get_sync_settings_service()
        return SyncThumbnailJobService(self.sync_db, settings_service)

    @lru_cache(maxsize=None)
    def get_overlay_job_service(self) -> SyncOverlayJobService:
        """Get overlay job service (cached)."""
        settings_service = self.get_sync_settings_service()
        return SyncOverlayJobService(self.sync_db, settings_service)

    @lru_cache(maxsize=None)
    def get_workflow_orchestrator(self) -> WorkflowOrchestratorService:
        """Get workflow orchestrator service (cached)."""
        return WorkflowOrchestratorService(
            db=self.sync_db,
            image_service=self.get_sync_image_service(),
            corruption_evaluation_service=SyncCorruptionEvaluationService(self.sync_db),
            camera_service=SyncCameraService(
                db=self.sync_db,
                async_db=self.async_db,
                settings_service=self.get_async_settings_service(),
            ),
            timelapse_service=self.get_sync_timelapse_service(),
            rtsp_service=RTSPService(
                db=self.sync_db,
                async_db=self.async_db,
                settings_service=self.get_async_settings_service(),
            ),
            job_coordinator=JobCoordinationService(
                db=self.sync_db,
                async_db=self.async_db,
                settings_service=self.get_async_settings_service(),
            ),
            sse_ops=self.get_sync_sse_operations(),
            weather_service=self.get_weather_manager(),
            settings_service=self.get_sync_settings_service(),
        )

    def create_capture_worker_dependencies(self) -> Dict[str, Any]:
        """Create dependencies for CaptureWorker."""
        return {
            "settings_service": self.get_sync_settings_service(),
            "camera_service": self.get_camera_service(),
            "timelapse_service": self.get_sync_timelapse_service(),
            "image_service": self.get_sync_image_service(),
            "weather_manager": self.get_weather_manager(),
            "thumbnail_job_service": self.get_thumbnail_job_service(),
            "overlay_job_service": self.get_overlay_job_service(),
        }

    def create_scheduler_worker_dependencies(self) -> Dict[str, Any]:
        """Create dependencies for SchedulerWorker."""
        return {
            "settings_service": self.get_sync_settings_service(),
            "async_settings_service": self.get_async_settings_service(),
            "timelapse_service": self.get_async_timelapse_service(),
            "camera_service": self.get_camera_service(),
            "weather_manager": self.get_weather_manager(),
        }

    def create_background_workers(self) -> Dict[str, Any]:
        """Create all background workers."""

        workers = {}

        try:
            # Thumbnail Worker
            workers["thumbnail"] = ThumbnailWorker(
                thumbnail_job_service=self.get_thumbnail_job_service(),
                thumbnail_pipeline=self.get_thumbnail_pipeline(),
                sse_ops=self.get_sync_sse_operations(),
            )

            # Overlay Worker
            workers["overlay"] = OverlayWorker(
                db=self.sync_db,
                settings_service=self.get_sync_settings_service(),
                weather_manager=self.get_weather_manager(),
            )

            # Cleanup Worker
            workers["cleanup"] = CleanupWorker(
                sync_db=self.sync_db,
                async_db=self.async_db,
                settings_service=self.get_sync_settings_service(),
            )

            # Weather Worker
            workers["weather"] = WeatherWorker(
                weather_manager=self.get_weather_manager(),
                sse_ops=self.get_sync_sse_operations(),
                settings_service=self.get_sync_settings_service(),
                async_settings_service=self.get_async_settings_service(),
                async_sse_ops=self.get_async_sse_operations(),
            )

            # Video Worker
            workers["video"] = VideoWorker(db=self.sync_db)

            # Capture Worker
            workers["capture"] = CaptureWorker(
                workflow_orchestrator=self.get_workflow_orchestrator(),
                async_timelapse_service=self.get_async_timelapse_service(),
                async_camera_service=self.get_camera_service(),
                weather_manager=self.get_weather_manager(),
                thumbnail_job_service=self.get_thumbnail_job_service(),
                overlay_job_service=self.get_overlay_job_service(),
            )

            self._logger.info(
                f"Created {len(workers)} background workers", emoji=LogEmoji.SUCCESS
            )

        except Exception as e:
            self._logger.error(f"Failed to create background workers: {e}")
            raise

        return workers

    def get_all_services(self) -> Dict[str, Any]:
        """Get all available services for diagnostic purposes."""
        return {
            "sync_settings_service": self.get_sync_settings_service(),
            "async_settings_service": self.get_async_settings_service(),
            "sync_image_service": self.get_sync_image_service(),
            "sync_timelapse_service": self.get_sync_timelapse_service(),
            "async_timelapse_service": self.get_async_timelapse_service(),
            "camera_service": self.get_camera_service(),
            "weather_manager": self.get_weather_manager(),
            "sync_sse_operations": self.get_sync_sse_operations(),
            "async_sse_operations": self.get_async_sse_operations(),
            "thumbnail_pipeline": self.get_thumbnail_pipeline(),
            "overlay_pipeline": self.get_overlay_pipeline(),
            "thumbnail_job_service": self.get_thumbnail_job_service(),
            "overlay_job_service": self.get_overlay_job_service(),
        }


def create_worker_ecosystem(
    sync_db: SyncDatabase, async_db: AsyncDatabase
) -> Dict[str, Any]:
    """
    Simplified worker ecosystem creation using service locator pattern.

    Replaces the complex 430-line factory with a clean, maintainable approach.
    """
    logger = get_service_logger(LoggerName.SYSTEM)
    logger.info(
        "🏗️ Creating worker ecosystem with service locator", emoji=LogEmoji.STARTUP
    )

    # Create service locator
    locator = ServiceLocator(sync_db, async_db)

    # Create workers
    background_workers = locator.create_background_workers()
    capture_deps = locator.create_capture_worker_dependencies()
    scheduler_deps = locator.create_scheduler_worker_dependencies()

    return {
        "background_workers": background_workers,
        "capture_worker_dependencies": capture_deps,
        "scheduler_worker_dependencies": scheduler_deps,
        "service_locator": locator,
    }
