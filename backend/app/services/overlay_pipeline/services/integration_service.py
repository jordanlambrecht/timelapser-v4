# backend/app/services/overlay_pipeline/services/integration_service.py
"""
Overlay Integration Service - Main service coordinating overlay generation with other systems.

Migrated from proven overlay_service.py logic to use existing OverlayRenderer
instead of custom generators.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ....enums import (
    LogEmoji,
    LoggerName,
    LogSource,
    OverlayJobPriority,
)
from ....models.image_model import Image as ImageModel
from ....models.overlay_model import (
    GlobalSettings,
    OverlayConfiguration,
    OverlayJobStatistics,
    OverlayPreviewRequest,
    OverlayPreviewResponse,
    TimelapseOverlay,
)

from ....services.logger import get_service_logger
from ....utils.file_helpers import (
    ensure_directory_exists,
    get_overlay_path_for_image,
    validate_file_path,
)
from ....utils.time_utils import (
    format_filename_timestamp,
    get_timezone_aware_timestamp_string_sync,
    get_timezone_aware_timestamp_sync,
    utc_now,
    utc_timestamp,
)
from ..utils.overlay_utils import (
    OverlayRenderer,
    validate_overlay_configuration,
)
from .job_service import SyncOverlayJobService
from .preset_service import SyncOverlayPresetService

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class SyncOverlayIntegrationService:
    """
    Synchronous integration service coordinating overlay generation.
    Main business logic layer for overlay system integration.

    Uses proven logic migrated from original overlay_service.py.
    """

    def __init__(
        self,
        db,
        sync_image_service,
        settings_service=None,
        overlay_preset_service=None,
        overlay_job_service=None,
    ):
        """
        Initialize with sync database and required services.

        Args:
            db: Sync database instance
            sync_image_service: Required SyncImageService instance (injected)
            settings_service: Settings service for configuration (optional)
            overlay_preset_service: Overlay preset service (optional, will create if not provided)
            overlay_job_service: Overlay job service (optional, will create if not provided)
        """
        self.db = db
        self.sync_image_service = sync_image_service  # Always injected, never created
        self.settings_service = settings_service

        # Initialize services (inject or create)
        self.overlay_preset_service = (
            overlay_preset_service or SyncOverlayPresetService(db)
        )
        self.overlay_job_service = overlay_job_service or SyncOverlayJobService(
            db, settings_service
        )

        # Add overlay operations for timelapse overlay access
        # Using injected SyncOverlayOperations singleton
        from ....dependencies.specialized import get_sync_overlay_operations

        self.overlay_ops = get_sync_overlay_operations()

    def generate_overlay_for_image(
        self, image_id: int, force_regenerate: bool = False
    ) -> bool:
        """
        Generate overlay for a specific image.

        Args:
            image_id: ID of the image to generate overlay for
            force_regenerate: Whether to regenerate even if overlay already exists

        Returns:
            True if overlay was successfully generated
        """
        try:
            logger.info(
                f"Starting overlay generation for image {image_id}",
                emoji=LogEmoji.PROCESSING,
            )

            # Get image details
            image = self.sync_image_service.get_image_by_id(image_id)
            if not image:
                logger.error(f"Image {image_id} not found for overlay generation")
                return False

            # Check if overlay already exists and force_regenerate is False
            if not force_regenerate and image.has_valid_overlay:
                logger.debug(
                    f"Overlay already exists for image {image_id}, skipping",
                    emoji=LogEmoji.SUCCESS,
                )
                # Skip SSE event for routine skips to reduce noise
                return True

            # Get timelapse overlay configuration
            timelapse_overlay = (
                self.overlay_ops.get_timelapse_overlay(image.timelapse_id)
                if image.timelapse_id
                else None
            )
            if not timelapse_overlay or not timelapse_overlay.enabled:
                logger.debug(
                    f"No overlay configuration found for timelapse {image.timelapse_id}"
                )
                # Skip SSE event for configuration issues to reduce noise
                return False

            # Resolve effective configuration
            logger.debug(
                "Resolving effective overlay configuration", emoji=LogEmoji.PROCESSING
            )
            effective_config = self._get_effective_overlay_config_for_timelapse(
                timelapse_overlay
            )

            # Validate configuration
            if not effective_config or not validate_overlay_configuration(
                effective_config
            ):
                logger.warning(f"Invalid overlay configuration for image {image_id}")
                return False

            # Generate overlay
            logger.debug("Rendering overlay for image", emoji=LogEmoji.PROCESSING)
            success = (
                self._render_overlay_for_image(image, effective_config)
                if effective_config
                else False
            )

            if success:
                # Update image record with overlay path
                overlay_path = self._get_overlay_path(image)
                # Use timezone-aware timestamp if settings service available
                overlay_updated_at = (
                    get_timezone_aware_timestamp_sync(self.settings_service)
                    if self.settings_service
                    else utc_now()
                )

                self.sync_image_service.update_image_overlay_status(
                    image_id=image_id,
                    overlay_path=str(overlay_path),
                    has_valid_overlay=True,
                    overlay_updated_at=overlay_updated_at,
                )

                logger.info(
                    f"Successfully generated overlay for image {image_id}",
                    emoji=LogEmoji.SUCCESS,
                )
            else:
                logger.error(f"Failed to render overlay for image {image_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to generate overlay for image {image_id}: {e}")
            return False

    def generate_preview_overlay(
        self, request: OverlayPreviewRequest
    ) -> OverlayPreviewResponse:
        """
        Generate overlay preview for UI display.

        Args:
            request: Preview generation request with camera and configuration

        Returns:
            Preview response with generated image paths
        """
        try:
            logger.info(
                f"🎨 Starting overlay preview generation for camera {request.camera_id}"
            )

            # Capture test image from camera
            test_image_path = self._capture_test_image(request.camera_id)
            if not test_image_path:
                error_msg = "Failed to capture test image from camera"
                logger.error(f"{error_msg} for camera {request.camera_id}")
                return OverlayPreviewResponse(
                    image_path="",
                    test_image_path="",
                    success=False,
                    error_message=error_msg,
                )

            # Validate configuration
            if not validate_overlay_configuration(request.overlay_config):
                error_msg = "Invalid overlay configuration"
                logger.warning(f"⚠️ {error_msg} for camera {request.camera_id}")
                return OverlayPreviewResponse(
                    image_path="",
                    test_image_path=str(test_image_path),
                    success=False,
                    error_message=error_msg,
                )

            # Generate preview overlay
            logger.debug("Rendering preview overlay", emoji=LogEmoji.OVERLAY)
            preview_path = self._generate_preview_overlay(
                test_image_path, request.overlay_config
            )

            if preview_path:
                logger.info(
                    f"Successfully generated overlay preview for camera {request.camera_id}",
                    emoji=LogEmoji.SUCCESS,
                )
                return OverlayPreviewResponse(
                    image_path=str(preview_path),
                    test_image_path=str(test_image_path),
                    success=True,
                    error_message=None,
                )
            else:
                error_msg = "Failed to generate overlay preview"
                logger.error(f"{error_msg} for camera {request.camera_id}")
                return OverlayPreviewResponse(
                    image_path="",
                    test_image_path=str(test_image_path),
                    success=False,
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to generate overlay preview: {error_msg}")
            return OverlayPreviewResponse(
                image_path="",
                test_image_path="",
                success=False,
                error_message=error_msg,
            )

    def generate_overlay_for_multiple_images(
        self, image_ids: List[int], force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate overlays for multiple images.

        Args:
            image_ids: List of image IDs to generate overlays for
            force_regenerate: Whether to regenerate even if overlay already exists

        Returns:
            Dictionary with success/failure counts and details
        """
        try:
            logger.info(
                f"🎨 Starting batch overlay generation for {len(image_ids)} images"
            )

            results = {
                "total_images": len(image_ids),
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "errors": [],
            }

            for image_id in image_ids:
                try:
                    success = self.generate_overlay_for_image(
                        image_id, force_regenerate
                    )
                    if success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(
                            f"Failed to generate overlay for image {image_id}"
                        )

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(
                        f"Error processing image {image_id}: {str(e)}"
                    )
                    logger.error(
                        f"Error in batch overlay generation for image {image_id}: {e}"
                    )

            logger.info(
                f"Batch overlay generation completed: "
                f"{results['successful']} successful, {results['failed']} failed",
                emoji=LogEmoji.SUCCESS,
            )

            return results

        except Exception as e:
            logger.error(f"Failed batch overlay generation: {e}")
            return {
                "total_images": len(image_ids),
                "successful": 0,
                "failed": len(image_ids),
                "skipped": 0,
                "errors": [f"Batch operation failed: {str(e)}"],
            }

    def queue_overlay_jobs_for_images(
        self,
        image_ids: List[int],
        priority: OverlayJobPriority = OverlayJobPriority.MEDIUM,
    ) -> Dict[str, Any]:
        """
        Queue overlay generation jobs for multiple images.

        Args:
            image_ids: List of image IDs to queue jobs for
            priority: Job priority ("high", "medium", "low")

        Returns:
            Dictionary with job creation results
        """
        try:

            logger.info(
                f"Queuing overlay jobs for {len(image_ids)} images",
                emoji=LogEmoji.QUEUE,
            )

            results = {
                "total_images": len(image_ids),
                "jobs_created": 0,
                "failed": 0,
                "job_ids": [],
                "errors": [],
            }

            for image_id in image_ids:
                try:
                    # Create job using overlay job operations
                    job = self.overlay_job_service.queue_job(
                        image_id=image_id, priority=OverlayJobPriority(priority)
                    )
                    if job:
                        results["jobs_created"] += 1
                        results["job_ids"].append(job.id)
                    else:
                        results["failed"] += 1
                        results["errors"].append(
                            f"Failed to create job for image {image_id}"
                        )

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(
                        f"Error creating job for image {image_id}: {str(e)}"
                    )
                    logger.error(f"Error queuing job for image {image_id}: {e}")

            logger.info(
                f"Job queuing completed: "
                f"{results['jobs_created']} jobs created, {results['failed']} failed",
                emoji=LogEmoji.SUCCESS,
            )

            return results

        except Exception as e:
            logger.error(f"Failed to queue overlay jobs: {e}")
            return {
                "total_images": len(image_ids),
                "jobs_created": 0,
                "failed": len(image_ids),
                "job_ids": [],
                "errors": [f"Job queuing failed: {str(e)}"],
            }

    def get_effective_overlay_config(
        self, timelapse_id: int
    ) -> Optional[OverlayConfiguration]:
        """
        Get the effective overlay configuration for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Effective overlay configuration or None if no configuration exists
        """
        try:
            # Get timelapse overlay configuration
            timelapse_overlay = self.overlay_ops.get_timelapse_overlay(timelapse_id)
            if not timelapse_overlay:
                return None

            # Resolve effective configuration
            return self._get_effective_overlay_config_for_timelapse(timelapse_overlay)

        except Exception as e:
            logger.error(
                f"Failed to get effective overlay config for timelapse {timelapse_id}: {e}"
            )
            return None

    def _render_overlay_for_image(
        self, image: ImageModel, config: OverlayConfiguration
    ) -> bool:
        """Render overlay for a specific image using the provided configuration."""

        try:
            # Get image file path
            image_path = Path(image.file_path)
            if not image_path.exists():
                logger.error(f"Image file not found: {image.file_path}")
                return False

            # Get overlay output path
            overlay_path = self._get_overlay_path(image)
            ensure_directory_exists(str(overlay_path.parent))

            # Create overlay context
            context_data = self._create_image_context(image)

            # Render overlay using proven OverlayRenderer
            renderer = OverlayRenderer(config)
            success = renderer.render_overlay(
                base_image_path=str(image_path),
                output_path=str(overlay_path),
                context_data=context_data,
            )

            return success

        except Exception as e:
            logger.error(f"Failed to render overlay for image {image.id}: {e}")
            return False

    def _generate_preview_overlay(
        self, test_image_path: Path, config: OverlayConfiguration
    ) -> Optional[Path]:
        """Generate preview overlay on test image."""

        try:
            # Create mock context for preview using timezone-aware timestamp
            preview_timestamp = (
                get_timezone_aware_timestamp_sync(self.settings_service)
                if self.settings_service
                else utc_now()
            )

            # Create preview output path
            preview_dir = test_image_path.parent / "previews"
            ensure_directory_exists(str(preview_dir))

            # Use timezone-aware timestamp string for filename if available
            if self.settings_service:
                timestamp_str = get_timezone_aware_timestamp_string_sync(
                    self.settings_service
                )
                # Extract just the datetime part for filename (remove timezone info)
                timestamp_str = (
                    timestamp_str.replace(":", "")
                    .replace("-", "")
                    .replace(" ", "_")[:15]
                )
                preview_filename = f"preview_{timestamp_str}.png"
            else:
                preview_filename = f"preview_{format_filename_timestamp(preview_timestamp, self.settings_service)}.png"

            preview_path = preview_dir / preview_filename
            context_data = {
                "timestamp": preview_timestamp,
                "frame_number": 123,
                "day_number": 5,
                "timelapse_name": "Preview Timelapse",
                "temperature": 72,
                "weather_conditions": "Partly Cloudy",
            }

            # Render overlay using proven OverlayRenderer
            renderer = OverlayRenderer(config)
            success = renderer.render_overlay(
                base_image_path=str(test_image_path),
                output_path=str(preview_path),
                context_data=context_data,
            )

            return preview_path if success else None

        except Exception as e:
            logger.error(f"Failed to generate preview overlay: {e}")
            return None

    def _capture_test_image(self, camera_id: int) -> Optional[Path]:
        """Capture a test image from the camera for preview generation."""

        try:
            # For sync overlay service, use the most recent image from the camera
            # This avoids the need for async RTSP capture in sync context

            # Get images for this camera and use the most recent one
            camera_images = self.sync_image_service.get_images_for_camera(camera_id)
            recent_image = camera_images[0] if camera_images else None

            if recent_image and recent_image.file_path:
                # Use the most recent captured image as test image
                image_path = validate_file_path(
                    recent_image.file_path,
                    base_directory=None,  # Use default data directory
                    must_exist=True,
                )
                logger.info(
                    f"Using recent image as test image for camera {camera_id}: {image_path}"
                )
                return image_path
            else:
                # If no recent image available, create a placeholder for overlay preview
                # This can happen when camera hasn't captured any images yet
                logger.warning(
                    f"No recent images found for camera {camera_id}, cannot generate overlay preview"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to get test image from camera {camera_id}: {e}")
            return None

    def _get_overlay_path(self, image: ImageModel) -> Path:
        """Get the output path for overlay image."""

        # Use shared utility for consistent path generation
        base_dir = None
        if self.settings_service:
            base_dir = self.settings_service.get_setting("data_directory", None)

        return get_overlay_path_for_image(
            image_path=image.file_path,
            camera_id=image.camera_id,
            timelapse_id=image.timelapse_id or 0,
            base_directory=base_dir,
        )

    def _create_image_context(self, image: ImageModel) -> Dict[str, Any]:
        """Create context data for overlay rendering from image metadata."""

        try:
            # Create context with actual model objects and complete data
            context_data = {
                # Pass actual image model object
                "image": image,
                "image_id": image.id,
                "camera_id": image.camera_id,
                "timelapse_id": image.timelapse_id,
                "file_path": image.file_path,
                "timestamp": image.captured_at,
                "frame_number": getattr(image, "frame_number", 0),
                # Timelapse info (will be populated by renderer if timelapse object available)
                "timelapse_name": f"Timelapse {image.timelapse_id}",
                "day_number": 1,  # This would be calculated from timelapse start date
                # Settings service for timezone handling in generators
                "settings_service": self.settings_service,
            }

            # Add weather data if available from image's historical weather
            if (
                hasattr(image, "weather_temperature")
                and image.weather_temperature is not None
            ):
                # Use historical weather data stored with the image
                context_data.update(
                    {
                        "temperature": image.weather_temperature,
                        "weather_conditions": image.weather_conditions or "",
                        "temperature_unit": "F",  # Default, could be from settings
                    }
                )
                logger.debug(
                    f"Using historical weather data for image {image.id}: temp={image.weather_temperature}"
                )
            # Weather data from image's stored weather fields (captured at image time)
            if image.weather_temperature is not None or image.weather_conditions:
                context_data.update(
                    {
                        "temperature": image.weather_temperature,
                        "weather_conditions": image.weather_conditions or "",
                        "weather_icon": image.weather_icon or "",
                        "temperature_unit": "C",  # Image weather is stored in Celsius
                        "weather_fetched_at": image.weather_fetched_at,
                    }
                )
                logger.debug(
                    f"Using stored weather data for image {image.id} from {image.weather_fetched_at}"
                )

            return context_data

        except Exception as e:
            logger.error(f"Failed to create image context for overlay: {e}")
            # Return minimal context with timezone-aware fallback if possible
            fallback_timestamp = image.captured_at or (
                get_timezone_aware_timestamp_sync(self.settings_service)
                if self.settings_service
                else utc_now()
            )
            return {
                "timestamp": fallback_timestamp,
                "frame_number": 0,
                "timelapse_name": "Timelapse",
                "day_number": 1,
            }

    def _get_effective_overlay_config_for_timelapse(
        self, timelapse_overlay: TimelapseOverlay
    ) -> Optional[OverlayConfiguration]:
        """
        Get the effective overlay configuration for a timelapse overlay.

        This method handles the new preset structure directly without adapters.
        It merges preset configurations with timelapse-specific overrides.

        Args:
            timelapse_overlay: The timelapse overlay configuration

        Returns:
            Effective overlay configuration or None if invalid
        """
        try:
            # Start with the timelapse's own overlay configuration
            base_config = timelapse_overlay.overlay_config

            # If a preset is specified, use preset as base and apply timelapse overrides
            if timelapse_overlay.preset_id:
                preset = self.overlay_preset_service.get_preset_by_id(
                    timelapse_overlay.preset_id
                )
                if preset and preset.overlay_config:
                    # Use preset configuration as base
                    preset_config = preset.overlay_config

                    # Create merged configuration
                    merged_items = list(preset_config.overlay_items)

                    # Apply timelapse-specific item overrides by adding new items
                    if base_config and base_config.overlay_items:
                        # Create dict for quick lookup by id
                        merged_dict = {item.id: item for item in merged_items}

                        # Add or override items from timelapse config
                        for item in base_config.overlay_items:
                            merged_dict[item.id] = item

                        merged_items = list(merged_dict.values())

                    # Apply timelapse-specific global setting overrides
                    merged_global_settings = preset_config.global_settings
                    if base_config and base_config.global_settings:
                        # Override global settings with timelapse-specific values
                        global_settings_dict = merged_global_settings.model_dump()
                        timelapse_global_dict = base_config.global_settings.model_dump()

                        # Only override non-default values from timelapse config
                        for key, value in timelapse_global_dict.items():
                            if value is not None:
                                global_settings_dict[key] = value

                        merged_global_settings = GlobalSettings(**global_settings_dict)

                    # Create final merged configuration
                    return OverlayConfiguration(
                        overlay_items=merged_items,
                        global_settings=merged_global_settings,
                    )
                else:
                    logger.warning(
                        f"Preset {timelapse_overlay.preset_id} not found, using timelapse config only"
                    )

            # Return timelapse configuration if no preset or preset not found
            return base_config if base_config else None

        except Exception as e:
            logger.error(
                "Failed to resolve effective overlay configuration", exception=e
            )
            return None

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of overlay integration service.

        Returns:
            Dict containing detailed health metrics for monitoring
        """
        try:
            logger.debug("🩺 Checking overlay integration service health")

            # Check database connectivity
            db_healthy = False
            db_error = None
            try:
                # Test database connection with a simple query
                all_presets = self.overlay_preset_service.get_all_presets()
                test_result = len(all_presets) is not None if all_presets else False
                db_healthy = test_result
                logger.debug(
                    f"Database connectivity: {'✅ healthy' if db_healthy else 'unhealthy'}",
                    emoji=LogEmoji.DATABASE,
                )
            except Exception as e:
                db_error = str(e)
                logger.error(
                    f"Database connectivity failed: {e}", emoji=LogEmoji.DATABASE
                )

            # Check settings service
            settings_healthy = True
            settings_error = None
            if self.settings_service:
                try:
                    # Test settings access
                    test_setting = self.settings_service.get_setting(
                        "data_directory", None
                    )
                    settings_healthy = test_setting is not None
                    logger.debug(
                        f"Settings service: {'✅ healthy' if settings_healthy else 'unhealthy'}",
                        emoji=LogEmoji.SYSTEM,
                    )
                except Exception as e:
                    settings_healthy = False
                    settings_error = str(e)
                    logger.error(f"Settings service failed: {e}", emoji=LogEmoji.SYSTEM)
            else:
                logger.debug(
                    "Settings service: ⚪ not configured", emoji=LogEmoji.SYSTEM
                )

            # Note: Weather data comes from image records, no separate weather manager needed

            # Check SSE operations
            # Determine overall health status
            # Core requirement: database must be healthy
            # Settings service is recommended but not critical
            critical_healthy = db_healthy
            optional_healthy = settings_healthy

            if critical_healthy and optional_healthy:
                overall_status = "healthy"
            elif critical_healthy:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"

            health_data = {
                "service": "overlay_integration_service",
                "status": overall_status,
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "error": db_error,
                },
                "settings_service": {
                    "status": (
                        "healthy"
                        if settings_healthy
                        else (
                            "unhealthy" if self.settings_service else "not_configured"
                        )
                    ),
                    "error": settings_error,
                },
                "weather_data": {
                    "status": "configured",  # Weather data comes from image records
                    "source": "image_records",
                    "note": "Weather data read from stored image weather fields",
                },
                "timestamp": utc_timestamp(),
                "critical_services_healthy": critical_healthy,
                "optional_services_healthy": optional_healthy,
            }

            logger.debug(f"🩺 Overlay integration service health: {overall_status}")
            return health_data

        except Exception as e:
            logger.error(f"Failed to get overlay integration service health: {e}")
            return {
                "service": "overlay_integration_service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": utc_timestamp(),
            }

    def get_overlay_generation_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive overlay generation statistics for monitoring and performance analysis.

        Returns:
            Dict containing detailed overlay generation metrics
        """
        try:
            logger.debug("📊 Collecting overlay generation statistics")

            # Get basic job queue statistics
            job_stats = None
            try:
                # Use job operations directly for sync context
                job_stats = self.overlay_job_service.get_job_statistics()
            except Exception as e:
                logger.warning(f"⚠️ Failed to get job statistics: {e}")

            # Get image overlay statistics from database
            overlay_image_stats = self._get_image_overlay_stats()

            # Get timelapse overlay configuration statistics
            timelapse_config_stats = self._get_timelapse_config_stats()

            # Calculate success rates and performance metrics
            performance_metrics = self._calculate_performance_metrics(
                job_stats, overlay_image_stats
            )

            comprehensive_stats = {
                "service": "overlay_generation_statistics",
                "timestamp": utc_timestamp(),
                "job_queue": job_stats.model_dump() if job_stats else None,
                "image_overlays": overlay_image_stats,
                "timelapse_configurations": timelapse_config_stats,
                "performance_metrics": performance_metrics,
                "collection_status": "success",
            }

            logger.debug(
                "Overlay generation statistics collected successfully",
                emoji=LogEmoji.CHART,
            )
            return comprehensive_stats

        except Exception as e:
            logger.error(f"Failed to collect overlay generation statistics: {e}")

            return {
                "service": "overlay_generation_statistics",
                "timestamp": utc_timestamp(),
                "collection_status": "error",
                "error": str(e),
            }

    def _get_image_overlay_stats(self) -> Dict[str, Any]:
        """Get statistics about images with overlays."""
        try:
            logger.debug("Collecting image overlay statistics", emoji=LogEmoji.CHART)

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get overlay coverage statistics
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) as total_images,
                            COUNT(*) FILTER (WHERE has_valid_overlay = true) as images_with_overlay,
                            COUNT(*) FILTER (WHERE has_valid_overlay = true AND overlay_updated_at > NOW() - INTERVAL '24 hours') as overlays_generated_24h,
                            COUNT(*) FILTER (WHERE has_valid_overlay = true AND overlay_updated_at > NOW() - INTERVAL '7 days') as overlays_generated_7d,
                            COUNT(*) FILTER (WHERE captured_at > NOW() - INTERVAL '24 hours') as images_captured_24h,
                            AVG(CASE WHEN has_valid_overlay = true AND overlay_updated_at IS NOT NULL AND captured_at IS NOT NULL
                                THEN EXTRACT(EPOCH FROM (overlay_updated_at - captured_at)) * 1000
                                ELSE NULL END) as avg_overlay_delay_ms
                        FROM images
                        WHERE captured_at > NOW() - INTERVAL '30 days'
                    """
                    )

                    row = cur.fetchone()
                    if row:
                        stats_dict = dict(row)

                        total_images = int(stats_dict.get("total_images", 0))
                        images_with_overlay = int(
                            stats_dict.get("images_with_overlay", 0)
                        )

                        # Calculate overlay coverage percentage
                        overlay_coverage_pct = (
                            (images_with_overlay / total_images * 100)
                            if total_images > 0
                            else 0
                        )

                        return {
                            "total_images_30d": total_images,
                            "images_with_overlay": images_with_overlay,
                            "overlay_coverage_percentage": round(
                                overlay_coverage_pct, 2
                            ),
                            "overlays_generated_24h": int(
                                stats_dict.get("overlays_generated_24h", 0)
                            ),
                            "overlays_generated_7d": int(
                                stats_dict.get("overlays_generated_7d", 0)
                            ),
                            "images_captured_24h": int(
                                stats_dict.get("images_captured_24h", 0)
                            ),
                            "avg_overlay_delay_ms": int(
                                stats_dict.get("avg_overlay_delay_ms", 0) or 0
                            ),
                        }

            return {"error": "No data available"}

        except Exception as e:
            logger.warning(f"Failed to collect image overlay statistics: {e}")
            return {"error": str(e)}

    def _get_timelapse_config_stats(self) -> Dict[str, Any]:
        """Get statistics about timelapse overlay configurations."""
        try:
            logger.debug("📊 Collecting timelapse configuration statistics")

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get timelapse overlay configuration statistics
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) as total_timelapses,
                            COUNT(*) FILTER (WHERE enabled = true) as enabled_configurations,
                            COUNT(*) FILTER (WHERE preset_id IS NOT NULL) as timelapses_using_presets,
                            COUNT(DISTINCT preset_id) FILTER (WHERE preset_id IS NOT NULL) as unique_presets_used,
                            COUNT(*) FILTER (WHERE enabled = true AND updated_at > NOW() - INTERVAL '7 days') as configurations_updated_7d
                        FROM timelapse_overlays
                    """
                    )

                    row = cur.fetchone()
                    if row:
                        stats_dict = dict(row)

                        total_timelapses = int(stats_dict.get("total_timelapses", 0))
                        enabled_configs = int(
                            stats_dict.get("enabled_configurations", 0)
                        )

                        # Calculate configuration adoption percentage
                        config_adoption_pct = (
                            (enabled_configs / total_timelapses * 100)
                            if total_timelapses > 0
                            else 0
                        )

                        return {
                            "total_timelapse_configs": total_timelapses,
                            "enabled_configurations": enabled_configs,
                            "configuration_adoption_percentage": round(
                                config_adoption_pct, 2
                            ),
                            "timelapses_using_presets": int(
                                stats_dict.get("timelapses_using_presets", 0)
                            ),
                            "unique_presets_used": int(
                                stats_dict.get("unique_presets_used", 0)
                            ),
                            "configurations_updated_7d": int(
                                stats_dict.get("configurations_updated_7d", 0)
                            ),
                        }

            return {"error": "No data available"}

        except Exception as e:
            logger.warning(f"Failed to collect timelapse configuration statistics: {e}")
            return {"error": str(e)}

    def _calculate_performance_metrics(
        self, job_stats: Optional[OverlayJobStatistics], image_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate derived performance metrics from collected statistics."""
        try:
            logger.debug("Calculating performance metrics", emoji=LogEmoji.CHART)

            metrics = {}

            if job_stats:
                # Calculate success rate
                total_completed = (
                    job_stats.completed_jobs_24h + job_stats.failed_jobs_24h
                )
                if total_completed > 0:
                    success_rate = (
                        job_stats.completed_jobs_24h / total_completed
                    ) * 100
                    metrics["success_rate_24h_percentage"] = round(success_rate, 2)
                else:
                    metrics["success_rate_24h_percentage"] = 0

                # Calculate queue efficiency
                total_jobs = (
                    job_stats.pending_jobs + job_stats.processing_jobs + total_completed
                )
                if total_jobs > 0:
                    queue_efficiency = (job_stats.completed_jobs_24h / total_jobs) * 100
                    metrics["queue_efficiency_percentage"] = round(queue_efficiency, 2)
                else:
                    metrics["queue_efficiency_percentage"] = 0

                # Processing speed metrics
                metrics["avg_processing_time_seconds"] = round(
                    job_stats.avg_processing_time_ms / 1000, 2
                )

                # Queue backlog health
                if job_stats.pending_jobs == 0:
                    metrics["queue_backlog_status"] = "healthy"
                elif job_stats.pending_jobs < 10:
                    metrics["queue_backlog_status"] = "moderate"
                else:
                    metrics["queue_backlog_status"] = "high"

            # Image processing metrics
            if isinstance(image_stats, dict) and "error" not in image_stats:
                images_captured = image_stats.get("images_captured_24h", 0)
                overlays_generated = image_stats.get("overlays_generated_24h", 0)

                if images_captured > 0:
                    overlay_generation_rate = (
                        overlays_generated / images_captured
                    ) * 100
                    metrics["overlay_generation_rate_24h_percentage"] = round(
                        overlay_generation_rate, 2
                    )
                else:
                    metrics["overlay_generation_rate_24h_percentage"] = 0

                # Overlay delay performance
                avg_delay = image_stats.get("avg_overlay_delay_ms", 0)
                if avg_delay < 5000:  # Less than 5 seconds
                    metrics["overlay_delay_performance"] = "excellent"
                elif avg_delay < 30000:  # Less than 30 seconds
                    metrics["overlay_delay_performance"] = "good"
                elif avg_delay < 120000:  # Less than 2 minutes
                    metrics["overlay_delay_performance"] = "acceptable"
                else:
                    metrics["overlay_delay_performance"] = "slow"

            return metrics

        except Exception as e:
            logger.warning(f"⚠️ Failed to calculate performance metrics: {e}")
            return {"error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of the sync overlay integration service.

        Returns:
            Dict containing service health and operational status
        """
        try:
            return {
                "service": "sync_overlay_integration_service",
                "database": {
                    "connected": self.db is not None,
                    "healthy": True if self.db else False,
                },
                "settings_service": {
                    "configured": self.settings_service is not None,
                    "healthy": True if self.settings_service else False,
                },
                "overlay_operations": {
                    "configured": self.overlay_ops is not None,
                    "healthy": True if self.overlay_ops else False,
                },
                "image_service": {
                    "configured": self.sync_image_service is not None,
                    "healthy": True if self.sync_image_service else False,
                },
                "job_operations": {
                    "configured": self.overlay_job_service is not None,
                    "healthy": True if self.overlay_job_service else False,
                },
                "status": "healthy",
                "timestamp": utc_timestamp(),
            }
        except Exception as e:
            logger.error(f"Failed to get sync overlay integration service status: {e}")
            return {
                "service": "sync_overlay_integration_service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": utc_timestamp(),
            }
