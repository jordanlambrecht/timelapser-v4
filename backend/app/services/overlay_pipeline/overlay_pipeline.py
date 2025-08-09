# backend/app/services/overlay_pipeline/overlay_pipeline.py
"""
Main Overlay Pipeline Class

Provides unified interface for all overlay generation functionality
with proper dependency injection following the established pattern.
"""

from typing import Any, Dict, Optional

from ...config import settings
from ...database.core import AsyncDatabase, SyncDatabase
from ...enums import LogEmoji, LoggerName, LogSource
from ...models.health_model import HealthStatus
from ...services.logger import get_service_logger
from ...utils.time_utils import utc_timestamp
from ..image_service import ImageService, SyncImageService
from .services import (
    AsyncOverlayJobService,
    OverlayIntegrationService,  # Re-enabled
    OverlayPresetService,
    OverlayTemplateService,
    SyncOverlayIntegrationService,  # Re-enabled
    SyncOverlayJobService,
    SyncOverlayPresetService,
    SyncOverlayTemplateService,
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

    def _initialize_sync_services(self):
        """Initialize sync services for worker processes."""
        if not self.database:
            return

        try:
            # Use dependency injection to prevent cascade multiplication
            from ...dependencies.sync_services import get_sync_overlay_job_service
            from ...dependencies.pipelines import get_sync_overlay_integration_service
            
            try:
                # Use singletons where available to prevent database connection multiplication
                self.sync_job_service = get_sync_overlay_job_service()
                
                # Fallback to direct instantiation for services not yet fully in DI system
                # Use dependency injection singletons to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_overlay_preset_service, get_sync_overlay_template_service
                self.sync_preset_service = get_sync_overlay_preset_service()
                self.sync_template_service = get_sync_overlay_template_service()
                
                # Use DI singleton for image service to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_image_service
                sync_image_service = get_sync_image_service()

                # Use singleton integration service if available
                self.sync_integration_service = get_sync_overlay_integration_service()
            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to use DI for overlay services, falling back to direct instantiation: {e}")
                # Fallback to direct instantiation if DI not available
                self.sync_job_service = SyncOverlayJobService(
                    self.database, self.settings_service
                )
                # Use dependency injection singletons to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_overlay_preset_service, get_sync_overlay_template_service
                self.sync_preset_service = get_sync_overlay_preset_service()
                self.sync_template_service = get_sync_overlay_template_service()
                
                # Use DI singleton for image service to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_image_service
                sync_image_service = get_sync_image_service()
                # Use singleton integration service to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_overlay_integration_service
                self.sync_integration_service = get_sync_overlay_integration_service()
            logger.debug(
                "Overlay pipeline sync services initialized", emoji=LogEmoji.SUCCESS
            )
        except Exception as e:
            logger.error(f"Failed to initialize overlay pipeline sync services: {e}")
            raise

    def _initialize_async_services(self):
        """Initialize async services for API endpoints."""
        if not self.async_database:
            return

        try:
            # Use dependency injection where available to prevent cascade multiplication
            from ...dependencies.async_services import get_overlay_job_service
            
            try:
                # Services that don't require settings_service (create first)
                # Use sync equivalents since this is a sync constructor  
                from ...dependencies.sync_services import get_sync_overlay_preset_service, get_sync_overlay_template_service
                self.preset_service = get_sync_overlay_preset_service()
                self.template_service = get_sync_overlay_template_service()

                # Services that require settings_service - use DI where available
                if self.settings_service:
                    # TODO: Fix async DI - cannot await in non-async method
                    # For now, use direct instantiation
                    self.job_service = AsyncOverlayJobService(
                        self.async_database, self.settings_service
                    )

                    # Use sync equivalent since this is a sync constructor
                    from ...dependencies.sync_services import get_sync_image_service
                    image_service = get_sync_image_service()

                    # Use sync equivalent since this is a sync constructor
                    from ...dependencies.sync_services import get_sync_overlay_integration_service
                    self.integration_service = get_sync_overlay_integration_service()
                else:
                    logger.warning(
                        "Cannot initialize overlay services requiring settings_service - service not provided"
                    )
            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to use DI for async overlay services, falling back to direct instantiation: {e}")
                # Fallback to direct instantiation if DI not available
                self.preset_service = OverlayPresetService(self.async_database)
                self.template_service = OverlayTemplateService(self.async_database)
                if self.settings_service:
                    self.job_service = AsyncOverlayJobService(
                        self.async_database, self.settings_service
                    )
                    # Use sync equivalent since this is a sync constructor
                    from ...dependencies.sync_services import get_sync_image_service
                    image_service = get_sync_image_service()
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

            logger.debug(
                "Overlay pipeline async services initialized", emoji=LogEmoji.SUCCESS
            )
        except Exception as e:
            logger.error(f"Failed to initialize overlay pipeline async services: {e}")
            raise

    def _require_service(
        self, service_attr: str, service_name: str, requires_settings: bool = True
    ):
        """
        Generic service validator to reduce code duplication.

        Args:
            service_attr: Attribute name of the service (e.g., 'job_service')
            service_name: Human-readable service name for error messages
            requires_settings: Whether this service requires settings_service

        Returns:
            The required service instance

        Raises:
            ValueError: If service is not available or requirements not met
        """
        if not hasattr(self, service_attr) or not getattr(self, service_attr):
            requirements = []
            if service_attr.startswith("sync_"):
                requirements.append("database")
            else:
                requirements.append("async_database")

            if requires_settings:
                requirements.append("settings_service")

            requirements_str = " and ".join(requirements)
            raise ValueError(
                f"{service_name} is required for this operation. "
                f"Ensure OverlayPipeline was initialized with {requirements_str}."
            )
        return getattr(self, service_attr)

    def _require_job_service(self):
        """Ensure job service is available for operations."""
        return self._require_service("job_service", "AsyncOverlayJobService")

    def _require_integration_service(self):
        """Ensure integration service is available for operations."""
        return self._require_service("integration_service", "OverlayIntegrationService")

    def _require_sync_job_service(self):
        """Ensure sync job service is available for operations."""
        return self._require_service("sync_job_service", "SyncOverlayJobService")

    def _require_sync_integration_service(self):
        """Ensure sync integration service is available for operations."""
        return self._require_service(
            "sync_integration_service", "SyncOverlayIntegrationService"
        )

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

    def process_overlay_queue(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Process pending overlay jobs from the queue.

        Args:
            batch_size: Number of jobs to process in this batch (uses config default if not provided)

        Returns:
            Processing results with success/failure counts
        """
        if batch_size is None:
            batch_size = settings.overlay_processing_batch_size
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
                    logger.error(f"Failed to process overlay job {job.id}: {e}")

            return {"processed": processed, "succeeded": succeeded, "failed": failed}

        except Exception as e:
            logger.error(f"Failed to process overlay queue: {e}")
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
                        f"Failed to collect integration service statistics: {e}"
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
            logger.error(f"Failed to collect comprehensive overlay statistics: {e}")
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

            # Check service availability - guaranteed by this service
            services = statistics["services"]  # Service boundary guarantee
            total_services = len(services)
            available_services = len(
                [s for s in services.values() if s["status"] == "available"]
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
            if (
                "job_service" in services
                and services["job_service"]["status"] == "available"
            ):
                job_service = services["job_service"]
                if "statistics" in job_service:
                    job_stats = job_service["statistics"]
                    if job_stats:
                        # Service boundary guarantee - no defensive .get() needed
                        completed = (
                            job_stats["completed_jobs_24h"]
                            if "completed_jobs_24h" in job_stats
                            else 0
                        )
                        failed = (
                            job_stats["failed_jobs_24h"]
                            if "failed_jobs_24h" in job_stats
                            else 0
                        )
                        total_processed = completed + failed

                        if total_processed > 0:
                            success_rate = (completed / total_processed) * 100
                            metrics["efficiency_score"] = round(success_rate, 2)

                        # Determine throughput status using configured thresholds
                        if completed > settings.overlay_high_throughput_threshold:
                            metrics["throughput_status"] = "high"
                        elif completed > settings.overlay_moderate_throughput_threshold:
                            metrics["throughput_status"] = "moderate"
                        else:
                            metrics["throughput_status"] = "low"

            return metrics

        except Exception as e:
            logger.warning(f"Failed to calculate pipeline metrics: {e}")
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
                if job_health["status"] not in [
                    HealthStatus.HEALTHY,
                    HealthStatus.DEGRADED,
                ]:
                    all_services_healthy = False
                if job_health["status"] == HealthStatus.UNHEALTHY:
                    critical_services_healthy = False
            except Exception as e:
                logger.error(f"Failed to get job service health: {e}")
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
                if integration_health["status"] not in [
                    HealthStatus.HEALTHY,
                    HealthStatus.DEGRADED,
                ]:
                    all_services_healthy = False
                if integration_health["status"] == HealthStatus.UNHEALTHY:
                    critical_services_healthy = False
            except Exception as e:
                logger.error(f"Failed to get integration service health: {e}")
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
                preset_healthy = hasattr(pipeline.sync_preset_service, "overlay_ops")
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
                logger.warning(f"Preset service degraded: {e}")
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
                    pipeline.sync_template_service, "overlay_ops"
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
                logger.warning(f"Template service degraded: {e}")
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
        logger.error(f"Failed to get overlay pipeline health: {e}")

        return {
            "service": "overlay_pipeline",
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
            "timestamp": utc_timestamp(),
        }
