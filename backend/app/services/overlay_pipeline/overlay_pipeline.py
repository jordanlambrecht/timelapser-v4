# backend/app/services/overlay_pipeline/overlay_pipeline.py
"""
Main Overlay Pipeline Class

Provides unified interface for all overlay generation functionality
with proper dependency injection following the established pattern.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ...database.core import AsyncDatabase, SyncDatabase
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
        weather_manager=None,
        sse_ops=None,
    ):
        """
        Initialize overlay pipeline.

        Args:
            database: Sync database instance (for creating sync services)
            async_database: Async database instance (for async services)
            settings_service: Settings service for configuration access
            weather_manager: Weather manager for weather overlay data
            sse_ops: SSE events operations for real-time notifications
        """
        self.database = database
        self.async_database = async_database
        self.settings_service = settings_service
        self.weather_manager = weather_manager
        self.sse_ops = sse_ops

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
            self.sync_integration_service = SyncOverlayIntegrationService(
                self.database, self.settings_service, self.weather_manager, self.sse_ops
            )
            logger.debug("✅ Overlay pipeline sync services initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize overlay pipeline sync services: {e}")
            raise

    def _initialize_async_services(self):
        """Initialize async services for API endpoints."""
        if not self.async_database:
            return

        try:
            self.job_service = AsyncOverlayJobService(
                self.async_database, self.settings_service
            )
            self.preset_service = OverlayPresetService(self.async_database)
            self.template_service = OverlayTemplateService(self.async_database)
            self.integration_service = OverlayIntegrationService(
                self.async_database, self.settings_service
            )
            logger.debug("✅ Overlay pipeline async services initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize overlay pipeline async services: {e}")
            raise

# Generators removed - using OverlayRenderer directly

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
        if not self.sync_integration_service:
            logger.error("Sync integration service not available for overlay generation")
            return False

        return self.sync_integration_service.generate_overlay_for_image(
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
        if not self.integration_service:
            logger.error("Async integration service not available for overlay generation")
            return False

        return await self.integration_service.generate_overlay_for_image(
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
        if not self.sync_job_service:
            logger.error("Sync job service not available for queue processing")
            return {"processed": 0, "succeeded": 0, "failed": 0}

        try:
            pending_jobs = self.sync_job_service.get_pending_jobs(batch_size)
            processed = 0
            succeeded = 0
            failed = 0

            for job in pending_jobs:
                processed += 1
                self.sync_job_service.mark_job_processing(job.id)

                try:
                    result = self.generate_overlay_for_image(job.image_id)
                    if result:
                        self.sync_job_service.mark_job_completed(job.id)
                        succeeded += 1
                    else:
                        self.sync_job_service.mark_job_failed(job.id, "Generation failed")
                        failed += 1
                except Exception as e:
                    self.sync_job_service.mark_job_failed(job.id, str(e))
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
            logger.info("📊 Collecting comprehensive overlay pipeline statistics")
            
            statistics = {
                "pipeline": "overlay_generation",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {}
            }
            
            # Get job service statistics
            if hasattr(self, 'sync_job_service') and self.sync_job_service:
                try:
                    job_stats = self.sync_job_service.get_job_statistics()
                    statistics["services"]["job_service"] = {
                        "status": "available",
                        "statistics": job_stats.model_dump() if job_stats else None
                    }
                    logger.debug("📊 Job service statistics collected")
                except Exception as e:
                    statistics["services"]["job_service"] = {
                        "status": "error", 
                        "error": str(e)
                    }
                    logger.warning(f"⚠️ Failed to collect job service statistics: {e}")
            
            # Get integration service statistics  
            if hasattr(self, 'sync_integration_service') and self.sync_integration_service:
                try:
                    integration_stats = self.sync_integration_service.get_overlay_generation_statistics()
                    statistics["services"]["integration_service"] = {
                        "status": "available",
                        "statistics": integration_stats
                    }
                    logger.debug("📊 Integration service statistics collected")
                except Exception as e:
                    statistics["services"]["integration_service"] = {
                        "status": "error",
                        "error": str(e)
                    }
                    logger.warning(f"⚠️ Failed to collect integration service statistics: {e}")
            
            # Calculate pipeline-level metrics
            pipeline_metrics = self._calculate_pipeline_metrics(statistics)
            statistics["pipeline_metrics"] = pipeline_metrics
            
            logger.info("📊 Comprehensive overlay pipeline statistics collected successfully")
            return statistics
            
        except Exception as e:
            logger.error(f"❌ Failed to collect comprehensive overlay statistics: {e}")
            return {
                "pipeline": "overlay_generation",
                "timestamp": datetime.utcnow().isoformat(), 
                "status": "error",
                "error": str(e)
            }

    def _calculate_pipeline_metrics(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate high-level pipeline performance metrics."""
        try:
            metrics = {
                "overall_health": "unknown",
                "throughput_status": "unknown", 
                "efficiency_score": 0,
                "service_availability": {}
            }
            
            # Check service availability
            services = statistics.get("services", {})
            total_services = len(services)
            available_services = len([s for s in services.values() if s.get("status") == "available"])
            
            if total_services > 0:
                availability_pct = (available_services / total_services) * 100
                metrics["service_availability"] = {
                    "total_services": total_services,
                    "available_services": available_services,
                    "availability_percentage": round(availability_pct, 2)
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
            logger.warning(f"⚠️ Failed to calculate pipeline metrics: {e}")
            return {"error": str(e)}


def create_overlay_pipeline(
    async_database: AsyncDatabase,
    settings_service=None,
    weather_manager=None,
) -> OverlayPipeline:
    """
    Factory function to create async overlay pipeline for API endpoints.

    Args:
        async_database: Async database instance
        settings_service: Settings service for configuration
        weather_manager: Weather manager for weather overlays

    Returns:
        OverlayPipeline instance with async services
    """
    return OverlayPipeline(
        async_database=async_database,
        settings_service=settings_service,
        weather_manager=weather_manager,
    )


def create_sync_overlay_pipeline(
    database: SyncDatabase,
    settings_service=None,
    weather_manager=None,
    sse_ops=None,
) -> OverlayPipeline:
    """
    Factory function to create sync overlay pipeline for worker processes.

    Args:
        database: Sync database instance
        settings_service: Settings service for configuration
        weather_manager: Weather manager for weather overlays
        sse_ops: SSE events operations for real-time notifications

    Returns:
        OverlayPipeline instance with sync services
    """
    return OverlayPipeline(
        database=database,
        settings_service=settings_service,
        weather_manager=weather_manager,
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
        logger.debug("🩺 Checking overlay pipeline health")
        
        service_health = {}
        all_services_healthy = True
        critical_services_healthy = True
        
        # Check sync services health if available
        if hasattr(pipeline, 'sync_job_service') and pipeline.sync_job_service:
            try:
                job_health = pipeline.sync_job_service.get_service_health()
                service_health["job_service"] = job_health
                if job_health.get("status") not in ["healthy", "degraded"]:
                    all_services_healthy = False
                if job_health.get("status") == "unhealthy":
                    critical_services_healthy = False
            except Exception as e:
                logger.error(f"❌ Failed to get job service health: {e}")
                service_health["job_service"] = {"status": "error", "error": str(e)}
                all_services_healthy = False
                critical_services_healthy = False
        
        if hasattr(pipeline, 'sync_integration_service') and pipeline.sync_integration_service:
            try:
                integration_health = pipeline.sync_integration_service.get_service_health()
                service_health["integration_service"] = integration_health  
                if integration_health.get("status") not in ["healthy", "degraded"]:
                    all_services_healthy = False
                if integration_health.get("status") == "unhealthy":
                    critical_services_healthy = False
            except Exception as e:
                logger.error(f"❌ Failed to get integration service health: {e}")
                service_health["integration_service"] = {"status": "error", "error": str(e)}
                all_services_healthy = False
                critical_services_healthy = False
                
        # Check preset service health (non-critical)
        if hasattr(pipeline, 'sync_preset_service') and pipeline.sync_preset_service:
            try:
                # Basic connectivity check for preset service
                preset_healthy = hasattr(pipeline.sync_preset_service, 'preset_ops')
                service_health["preset_service"] = {
                    "status": "healthy" if preset_healthy else "degraded"
                }
                if not preset_healthy:
                    all_services_healthy = False
            except Exception as e:
                logger.warning(f"⚠️ Preset service degraded: {e}")
                service_health["preset_service"] = {"status": "degraded", "error": str(e)}
                all_services_healthy = False
                
        # Check template service health (non-critical)
        if hasattr(pipeline, 'sync_template_service') and pipeline.sync_template_service:
            try:
                # Basic connectivity check for template service
                template_healthy = hasattr(pipeline.sync_template_service, 'template_ops')
                service_health["template_service"] = {
                    "status": "healthy" if template_healthy else "degraded"
                }
                if not template_healthy:
                    all_services_healthy = False
            except Exception as e:
                logger.warning(f"⚠️ Template service degraded: {e}")
                service_health["template_service"] = {"status": "degraded", "error": str(e)}
                all_services_healthy = False
        
        # Determine overall health status
        if critical_services_healthy and all_services_healthy:
            overall_status = "healthy"
        elif critical_services_healthy:
            overall_status = "degraded"  # Non-critical services have issues
        else:
            overall_status = "unhealthy"  # Critical services have issues
            
        from ...utils.time_utils import utc_now
        
        health_data = {
            "service": "overlay_pipeline",
            "status": overall_status,
            "services": service_health,
            "service_count": len(service_health),
            "architecture": "4_service_pipeline" if len(service_health) >= 4 else f"{len(service_health)}_service_pipeline",
            "critical_services_healthy": critical_services_healthy,
            "all_services_healthy": all_services_healthy,
            "timestamp": utc_now().isoformat(),
            "error": None if critical_services_healthy else "One or more critical services unhealthy"
        }
        
        logger.debug(f"🩺 Overlay pipeline health: {overall_status}")
        return health_data
        
    except Exception as e:
        logger.error(f"❌ Failed to get overlay pipeline health: {e}")
        from ...utils.time_utils import utc_now
        return {
            "service": "overlay_pipeline",
            "status": "unhealthy",
            "error": str(e), 
            "timestamp": utc_now().isoformat()
        }