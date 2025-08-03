# backend/app/services/overlay_pipeline/overlay_pipeline.py
"""
Main Overlay Pipeline Class

Provides unified interface for all overlay generation functionality
with proper dependency injection following the established pattern.
"""

from typing import Optional, Dict, Any

from ...models.health_model import HealthStatus

from ...database.core import AsyncDatabase, SyncDatabase
from ...enums import LogSource, LoggerName, LogEmoji
from ...services.logger import get_service_logger
from ...utils.time_utils import utc_timestamp
from .services import (
    SyncOverlayJobService,
    AsyncOverlayJobService,
    SyncOverlayPresetService,
    OverlayPresetService,
    SyncOverlayTemplateService,
    OverlayTemplateService,
    SyncOverlayIntegrationService,
    OverlayIntegrationService,
)

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)

# Generators removed - using existing OverlayRenderer instead


class OverlayPipeline:
    """
    Main overlay generation pipeline providing unified access to all
    overlay functionality with proper dependency injection.
    """

    def __init__(
        self,
        database: Optional[SyncDatabase] = None,
        async_database: Optional[AsyncDatabase] = None,
        settings_service=None,
        sse_ops=None,
    ):
        """
        Initialize overlay pipeline with strict dependency injection.

        Args:
            database: Sync database instance (for creating sync services)
            async_database: Async database instance (for async services)
            settings_service: Settings service for configuration access (required for production)
            sse_ops: SSE events operations for real-time notifications (optional)
        """
        self.database = database
        self.async_database = async_database
        self.settings_service = settings_service
        self.sse_ops = sse_ops

        # Validate that we have the necessary dependencies for production use
        if not settings_service:
            logger.warning(
                "OverlayPipeline instantiated without settings_service - should only happen in tests"
            )

        # Initialize services
        if database:
            self._initialize_sync_services()
        if async_database:
            self._initialize_async_services()

        # Generators removed - using OverlayRenderer directly in integration service
        """
        Initialize overlay pipeline with strict dependency injection.

        Args:
            database: Sync database instance (for creating sync services)
            async_database: Async database instance (for async services)
            settings_service: Settings service for configuration access (required for production)
            sse_ops: SSE events operations for real-time notifications (required for production)
            
        Note:
            Weather data is read from stored image records (weather_temperature, weather_conditions, etc.)
            rather than making live API calls to weather services.
        """
        self.database = database
        self.async_database = async_database
        self.settings_service = settings_service
        self.sse_ops = sse_ops

        # Validate that we have the necessary dependencies for production use
        if not settings_service:
            logger.warning(
                "OverlayPipeline instantiated without settings_service - should only happen in tests"
            )

        # Initialize services
        if database:
            self._initialize_sync_services()
        if async_database:
            self._initialize_async_services()

        # Generators removed - using OverlayRenderer directly in integration service

    def _initialize_sync_services(self):
        """Initialize sync services for worker processes."""
        if not self.database:
            return

        try:
            self.sync_job_service = SyncOverlayJobService(
                self.database, self.settings_service
            )
            self.sync_preset_service = SyncOverlayPresetService(self.database)
            self.sync_template_service = SyncOverlayTemplateService(self.database)
            # Create SyncImageService for integration service
            from ...services.image_service import SyncImageService

            sync_image_service = SyncImageService(self.database)

            self.sync_integration_service = SyncOverlayIntegrationService(
                self.database,
                sync_image_service,
                self.settings_service,
                self.sync_preset_service,
                self.sync_job_service,
            )
            logger.debug(
                "Overlay pipeline sync services initialized", emoji=LogEmoji.SUCCESS
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize overlay pipeline sync services: {e}", exception=e
            )
            raise

    def _initialize_async_services(self):
        """Initialize async services for API endpoints."""
        if not self.async_database:
            return

        try:
            # Services that require settings_service
            if self.settings_service:
                self.job_service = AsyncOverlayJobService(
                    self.async_database, self.settings_service
                )
                # Create ImageService for async integration service
                from ...services.image_service import ImageService

                image_service = ImageService(self.async_database, self.settings_service)

                self.integration_service = OverlayIntegrationService(
                    self.async_database,
                    self.settings_service,
                    None,
                    self.preset_service,
                    image_service,
                )
            else:
                logger.warning(
                    "Cannot initialize overlay services requiring settings_service - service not provided"
                )

            # Services that don't require settings_service
            self.preset_service = OverlayPresetService(self.async_database)
            self.template_service = OverlayTemplateService(self.async_database)

            logger.debug(
                "Overlay pipeline async services initialized", emoji=LogEmoji.SUCCESS
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize overlay pipeline async services: {e}",
                exception=e,
            )
            raise

    def _require_job_service(self):
        """Ensure job service is available for operations."""
        if not hasattr(self, "job_service") or not self.job_service:
            raise ValueError(
                "AsyncOverlayJobService is required for this operation. "
                "Ensure OverlayPipeline was initialized with settings_service."
            )
        return self.job_service

    def _require_integration_service(self):
        """Ensure integration service is available for operations."""
        if not hasattr(self, "integration_service") or not self.integration_service:
            raise ValueError(
                "OverlayIntegrationService is required for this operation. "
                "Ensure OverlayPipeline was initialized with settings_service."
            )
        return self.integration_service

    def _require_sync_job_service(self):
        """Ensure sync job service is available for operations."""
        if not hasattr(self, "sync_job_service") or not self.sync_job_service:
            raise ValueError(
                "SyncOverlayJobService is required for this operation. "
                "Ensure OverlayPipeline was initialized with database and settings_service."
            )
        return self.sync_job_service

    def _require_sync_integration_service(self):
        """Ensure sync integration service is available for operations."""
        if (
            not hasattr(self, "sync_integration_service")
            or not self.sync_integration_service
        ):
            raise ValueError(
                "SyncOverlayIntegrationService is required for this operation. "
                "Ensure OverlayPipeline was initialized with database and settings_service."
            )
        return self.sync_integration_service

    def generate_overlay_for_image(
        self, image_id: int, force_regenerate: bool = False
    ) -> bool:
        """
        Generate overlay for a specific image using sync services.

        Args:
            image_id: ID of the image to generate overlay for
            force_regenerate: Whether to regenerate even if overlay exists

        Returns:
            True if overlay was successfully generated
        """
        sync_integration_service = self._require_sync_integration_service()
        return sync_integration_service.generate_overlay_for_image(
            image_id, force_regenerate
        )

    async def generate_overlay_for_image_async(
        self, image_id: int, force_regenerate: bool = False
    ) -> bool:
        """
        Generate overlay for a specific image using async services.

        Args:
            image_id: ID of the image to generate overlay for
            force_regenerate: Whether to regenerate even if overlay exists

        Returns:
            True if overlay was successfully generated
        """
        integration_service = self._require_integration_service()
        return await integration_service.generate_overlay_for_image(
            image_id, force_regenerate
        )

    def process_overlay_queue(self, batch_size: int = 5) -> Dict[str, Any]:
        """
        Process pending overlay jobs from the queue.

        Args:
            batch_size: Number of jobs to process in this batch

        Returns:
            Processing results with success/failure counts
        """
        sync_job_service = self._require_sync_job_service()

        try:
            pending_jobs = sync_job_service.get_pending_jobs(batch_size)
            processed = 0
            succeeded = 0
            failed = 0

            for job in pending_jobs:
                processed += 1
                sync_job_service.mark_job_processing(job.id)

                try:
                    result = self.generate_overlay_for_image(job.image_id)
                    if result:
                        sync_job_service.mark_job_completed(job.id)
                        succeeded += 1
                    else:
                        sync_job_service.mark_job_failed(job.id, "Generation failed")
                        failed += 1
                except Exception as e:
                    sync_job_service.mark_job_failed(job.id, str(e))
                    failed += 1
                    logger.error(
                        f"Failed to process overlay job {job.id}: {e}",
                        exception=e,
                    )

            return {"processed": processed, "succeeded": succeeded, "failed": failed}

        except Exception as e:
            logger.error(
                f"Failed to process overlay queue: {e}",
                exception=e,
            )
            return {"processed": 0, "succeeded": 0, "failed": 0}

    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive overlay generation statistics from all services.

        Returns:
            Dict containing detailed metrics from job service, integration service, and pipeline
        """
        try:
            logger.info(
                "Collecting comprehensive overlay pipeline statistics",
                emoji=LogEmoji.CHART,
            )

            statistics = {
                "pipeline": "overlay_generation",
                "timestamp": utc_timestamp(),
                "services": {},
            }

            # Get job service statistics
            if hasattr(self, "sync_job_service") and self.sync_job_service:
                try:
                    job_stats = self.sync_job_service.get_job_statistics()
                    statistics["services"]["job_service"] = {
                        "status": "available",
                        "statistics": job_stats.model_dump() if job_stats else None,
                    }
                    logger.debug(
                        "Job service statistics collected", emoji=LogEmoji.CHART
                    )
                except Exception as e:
                    statistics["services"]["job_service"] = {
                        "status": "error",
                        "error": str(e),
                    }
                    logger.warning(
                        f"Failed to collect job service statistics: {e}",
                    )

            # Get integration service statistics
            if (
                hasattr(self, "sync_integration_service")
                and self.sync_integration_service
            ):
                try:
                    integration_stats = (
                        self.sync_integration_service.get_overlay_generation_statistics()
                    )
                    statistics["services"]["integration_service"] = {
                        "status": "available",
                        "statistics": integration_stats,
                    }
                    logger.debug(
                        "Integration service statistics collected",
                        emoji=LogEmoji.CHART,
                    )
                except Exception as e:
                    statistics["services"]["integration_service"] = {
                        "status": "error",
                        "error": str(e),
                    }
                    logger.warning(
                        f"Failed to collect integration service statistics: {e}",
                        exception=e,
                    )

            # Calculate pipeline-level metrics
            pipeline_metrics = self._calculate_pipeline_metrics(statistics)
            statistics["pipeline_metrics"] = pipeline_metrics

            logger.info(
                "Comprehensive overlay pipeline statistics collected successfully",
                emoji=LogEmoji.CHART,
            )
            return statistics

        except Exception as e:
            logger.error(
                f"Failed to collect comprehensive overlay statistics: {e}",
                exception=e,
            )
            return {
                "pipeline": "overlay_generation",
                "timestamp": utc_timestamp(),
                "status": "error",
                "error": str(e),
            }

    def _calculate_pipeline_metrics(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate high-level pipeline performance metrics."""
        try:
            metrics = {
                "overall_health": "unknown",
                "throughput_status": "unknown",
                "efficiency_score": 0,
                "service_availability": {},
            }

            # Check service availability
            services = statistics.get("services", {})
            total_services = len(services)
            available_services = len(
                [s for s in services.values() if s.get("status") == "available"]
            )

            if total_services > 0:
                availability_pct = (available_services / total_services) * 100
                metrics["service_availability"] = {
                    "total_services": total_services,
                    "available_services": available_services,
                    "availability_percentage": round(availability_pct, 2),
                }

                # Determine overall health based on service availability
                if availability_pct == 100:
                    metrics["overall_health"] = "healthy"
                elif availability_pct >= 50:
                    metrics["overall_health"] = "degraded"
                else:
                    metrics["overall_health"] = "unhealthy"

            # Calculate efficiency score from job statistics if available
            job_service = services.get("job_service", {})
            if job_service.get("status") == "available":
                job_stats = job_service.get("statistics", {})
                if job_stats:
                    completed = job_stats.get("completed_jobs_24h", 0)
                    failed = job_stats.get("failed_jobs_24h", 0)
                    total_processed = completed + failed

                    if total_processed > 0:
                        success_rate = (completed / total_processed) * 100
                        metrics["efficiency_score"] = round(success_rate, 2)

                        # Determine throughput status
                        if completed > 100:  # High volume
                            metrics["throughput_status"] = "high"
                        elif completed > 10:  # Moderate volume
                            metrics["throughput_status"] = "moderate"
                        else:  # Low volume
                            metrics["throughput_status"] = "low"

            return metrics

        except Exception as e:
            logger.warning(
                f"Failed to calculate pipeline metrics: {e}",
                exception=e,
            )
            return {"error": str(e)}


def create_overlay_pipeline(
    async_database: AsyncDatabase,
    settings_service=None,
) -> OverlayPipeline:
    """
    Factory function to create async overlay pipeline for API endpoints.

    For production use, services should be provided for proper dependency injection.

    Args:
        async_database: Async database instance (required)
        settings_service: Settings service for configuration (recommended for production)

    Returns:
        OverlayPipeline instance with async services
    """
    return OverlayPipeline(
        async_database=async_database,
        settings_service=settings_service,
    )


def create_sync_overlay_pipeline(
    database: SyncDatabase,
    settings_service=None,
    sse_ops=None,
) -> OverlayPipeline:
    """
    Factory function to create sync overlay pipeline for worker processes.

    For production use, services should be provided for proper dependency injection.

    Args:
        database: Sync database instance (required)
        settings_service: Settings service for configuration (recommended for production)
        sse_ops: SSE events operations for real-time notifications (optional)

    Returns:
        OverlayPipeline instance with sync services
    """
    return OverlayPipeline(
        database=database,
        settings_service=settings_service,
        sse_ops=sse_ops,
    )


def get_overlay_pipeline_health(pipeline: OverlayPipeline) -> Dict[str, Any]:
    """
    Get comprehensive health status of overlay pipeline.

    Args:
        pipeline: OverlayPipeline instance to check

    Returns:
        Dict containing detailed health metrics for monitoring
    """
    try:
        logger.debug(
            "Checking overlay pipeline health",
            emoji=LogEmoji.HEALTH,
        )

        service_health = {}
        all_services_healthy = True
        critical_services_healthy = True

        # Check sync services health if available
        if hasattr(pipeline, "sync_job_service") and pipeline.sync_job_service:
            try:
                job_health = pipeline.sync_job_service.get_service_health()
                service_health["job_service"] = job_health
                if job_health.get("status") not in [
                    HealthStatus.HEALTHY,
                    HealthStatus.DEGRADED,
                ]:
                    all_services_healthy = False
                if job_health.get("status") == HealthStatus.UNHEALTHY:
                    critical_services_healthy = False
            except Exception as e:
                logger.error(
                    f"Failed to get job service health: {e}",
                    exception=e,
                )
                service_health["job_service"] = {
                    "status": HealthStatus.ERROR,
                    "error": str(e),
                }
                all_services_healthy = False
                critical_services_healthy = False

        if (
            hasattr(pipeline, "sync_integration_service")
            and pipeline.sync_integration_service
        ):
            try:
                integration_health = (
                    pipeline.sync_integration_service.get_service_health()
                )
                service_health["integration_service"] = integration_health
                if integration_health.get("status") not in [
                    HealthStatus.HEALTHY,
                    HealthStatus.DEGRADED,
                ]:
                    all_services_healthy = False
                if integration_health.get("status") == HealthStatus.UNHEALTHY:
                    critical_services_healthy = False
            except Exception as e:
                logger.error(
                    f"Failed to get integration service health: {e}",
                    exception=e,
                )
                service_health["integration_service"] = {
                    "status": HealthStatus.ERROR,
                    "error": str(e),
                }
                all_services_healthy = False
                critical_services_healthy = False

        # Check preset service health (non-critical)
        if hasattr(pipeline, "sync_preset_service") and pipeline.sync_preset_service:
            try:
                # Basic connectivity check for preset service
                preset_healthy = hasattr(pipeline.sync_preset_service, "preset_ops")
                service_health["preset_service"] = {
                    "status": (
                        HealthStatus.HEALTHY
                        if preset_healthy
                        else HealthStatus.DEGRADED
                    )
                }
                if not preset_healthy:
                    all_services_healthy = False
            except Exception as e:
                logger.warning(
                    f"Preset service degraded: {e}",
                    exception=e,
                )
                service_health["preset_service"] = {
                    "status": HealthStatus.DEGRADED,
                    "error": str(e),
                }
                all_services_healthy = False

        # Check template service health (non-critical)
        if (
            hasattr(pipeline, "sync_template_service")
            and pipeline.sync_template_service
        ):
            try:
                # Basic connectivity check for template service
                template_healthy = hasattr(
                    pipeline.sync_template_service, "template_ops"
                )
                service_health["template_service"] = {
                    "status": (
                        HealthStatus.HEALTHY
                        if template_healthy
                        else HealthStatus.DEGRADED
                    )
                }
                if not template_healthy:
                    all_services_healthy = False
            except Exception as e:
                logger.warning(
                    f"Template service degraded: {e}",
                    exception=e,
                )
                service_health["template_service"] = {
                    "status": HealthStatus.DEGRADED,
                    "error": str(e),
                }
                all_services_healthy = False

        # Determine overall health status
        if critical_services_healthy and all_services_healthy:
            overall_status = HealthStatus.HEALTHY
        elif critical_services_healthy:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY

        health_data = {
            "service": "overlay_pipeline",
            "status": overall_status,
            "services": service_health,
            "service_count": len(service_health),
            "architecture": (
                "4_service_pipeline"
                if len(service_health) >= 4
                else f"{len(service_health)}_service_pipeline"
            ),
            "critical_services_healthy": critical_services_healthy,
            "all_services_healthy": all_services_healthy,
            "timestamp": utc_timestamp(),
            "error": (
                None
                if critical_services_healthy
                else "One or more critical services unhealthy"
            ),
        }

        logger.debug(
            f"Overlay pipeline health: {overall_status}", emoji=LogEmoji.HEALTH
        )
        return health_data

    except Exception as e:
        logger.error(f"Failed to get overlay pipeline health: {e}", exception=e)

        return {
            "service": "overlay_pipeline",
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
            "timestamp": utc_timestamp(),
        }
