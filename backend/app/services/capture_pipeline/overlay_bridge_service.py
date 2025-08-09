# backend/app/services/capture_pipeline/overlay_bridge_service.py
"""
Capture Pipeline Overlay Bridge Service

Bridge service for overlay generation operations, designed for future domain extraction.

🌉 BRIDGE PATTERN: Future Domain Extraction
This service provides a clean interface for overlay generation operations
while maintaining the ability to extract overlay functionality into its
own dedicated domain without breaking the capture pipeline.

🎯 SERVICE SCOPE: Overlay generation coordination
- Overlay generation orchestration
- Weather data integration for overlays
- Overlay settings and template management
- Overlay file path coordination
- Fallback overlay handling

🔮 FUTURE DOMAIN EXTRACTION:
When overlay functionality is extracted to its own domain:
- This bridge service will delegate to overlay/ domain
- Capture pipeline workflow remains unchanged
- Clean separation maintains architectural boundaries

📝 KEY ARCHITECTURAL BOUNDARIES:
- NO direct image file I/O (coordinates paths with workflow)
- NO RTSP operations (receives image data from workflow)
- NO database record updates (reports results to workflow)
- NO job coordination (reports status to workflow)

This bridge enables the capture pipeline to coordinate overlay generation
while preparing for future architectural evolution.
"""


from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ...services.settings_service import SyncSettingsService
    from ...services.weather.service import WeatherManager

from PIL import Image

from ...config import settings
from ...constants import (
    BOOLEAN_TRUE_STRING,
    DEFAULT_GENERATE_OVERLAYS,
    SETTING_KEY_GENERATE_OVERLAYS,
)
from ...database.core import SyncDatabase
from ...enums import LoggerName, LogSource
from ...models.overlay_model import OverlayConfiguration
from ...services.logger import get_service_logger
from ...services.overlay_pipeline import OverlayService
from ...services.overlay_pipeline.utils.overlay_helpers import (  # Used for overlay configuration validation
    OverlaySettingsResolver,
)
from ...services.overlay_pipeline.utils.overlay_utils import OverlayRenderer
from ...utils import file_helpers
from ...utils.time_utils import (  # Using timezone-aware system
    format_date_string,
    utc_now,
)
from .constants import (
    DEFAULT_OVERLAY_HEIGHT,
    DEFAULT_OVERLAY_WIDTH,
    MAX_OVERLAY_HEIGHT,
    MAX_OVERLAY_WIDTH,
    MIN_OVERLAY_HEIGHT,
    MIN_OVERLAY_WIDTH,
)

logger = get_service_logger(LoggerName.CAPTURE_PIPELINE, LogSource.PIPELINE)


class OverlayBridgeService:
    """
    Bridge service for overlay generation operations.

    Provides overlay generation coordination for the capture pipeline
    while maintaining clean interfaces for future domain extraction.

    Responsibilities:
    - Overlay generation orchestration
    - Weather data integration for overlay content
    - Overlay template and settings management
    - Overlay file path coordination
    - Fallback overlay creation when generation fails
    """

    def __init__(
        self,
        db: SyncDatabase,
        settings_service: Optional["SyncSettingsService"] = None,
        weather_manager: Optional["WeatherManager"] = None,
    ) -> None:
        """
        Initialize overlay bridge service.

        Args:
            db: Synchronized database connection
            settings_service: Optional settings service (uses singleton if None)
            weather_manager: Optional weather manager (uses singleton if None)
        """
        self.db = db

        # Use provided services or get singletons
        if settings_service is None:
            from ...dependencies.sync_services import get_sync_settings_service

            settings_service = get_sync_settings_service()
        if weather_manager is None:
            # Use singleton WeatherManager
            import asyncio
            from ...dependencies.async_services import get_weather_manager

            try:
                loop = asyncio.get_event_loop()
                weather_manager = loop.run_until_complete(get_weather_manager())
            except RuntimeError:
                # Use dependency injection singleton to prevent database connection multiplication
                from ...dependencies.sync_services import get_sync_weather_manager

                weather_manager = get_sync_weather_manager()

        self.settings_service = settings_service
        self.weather_manager = weather_manager
        # Use dependency injection to avoid creating OverlayService directly where possible
        # Note: OverlayService doesn't have a singleton factory yet due to complex dependencies
        self.overlay_service = OverlayService(
            db, self.settings_service, self.weather_manager
        )
        # Using injected Operations singletons
        from ...dependencies.specialized import (
            get_sync_overlay_operations,
            get_sync_image_operations,
        )

        self.overlay_ops = get_sync_overlay_operations()
        self.image_ops = get_sync_image_operations()

    def generate_overlay_for_image(
        self,
        image_id: int,
        timelapse_id: int,
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate overlay PNG for captured image.

        Coordinates complete overlay generation process including:
        1. Overlay settings retrieval
        2. Weather data integration
        3. Overlay template processing
        4. PNG generation and saving
        5. Fallback handling on failure

        Args:
            image_id: Database image record ID
            timelapse_id: Timelapse identifier for settings
            weather_data: Optional weather data for overlay content

        Returns:
            Overlay generation result with file path and status
        """
        try:
            logger.debug(f"🎨 Generating overlay for image {image_id}")

            # Check if overlays are enabled for this timelapse
            if not self.check_overlay_enabled(timelapse_id):
                return {
                    "success": False,
                    "reason": "overlays_disabled",
                    "overlay_path": None,
                }

            # Get image record to validate it exists
            image = self.image_ops.get_image_by_id(image_id)
            if not image:
                return {
                    "success": False,
                    "error": "Image not found",
                    "overlay_path": None,
                }

            # Use OverlayService for the actual generation
            success = self.overlay_service.generate_overlay_for_image(image_id)

            if success:
                # Get the overlay path that was created
                overlay_path = self._get_overlay_path_for_image(image)

                logger.info(f"✅ Overlay generated successfully: {overlay_path}")
                return {
                    "success": True,
                    "overlay_path": overlay_path,
                    "generation_method": "overlay_service",
                }
            else:
                logger.warning(f"❌ Overlay generation failed for image {image_id}")
                return {
                    "success": False,
                    "error": "Overlay generation failed",
                    "overlay_path": None,
                }

        except Exception as e:
            logger.error(f"Error generating overlay for image {image_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "overlay_path": None,
            }

    def check_overlay_enabled(self, timelapse_id: int) -> bool:
        """
        Check if overlays are enabled for timelapse.

        Determines whether overlay generation should be performed.

        Args:
            timelapse_id: Timelapse identifier

        Returns:
            True if overlays enabled, False otherwise
        """
        try:
            # Check global overlay setting

            overlay_enabled = self.settings_service.get_setting(
                SETTING_KEY_GENERATE_OVERLAYS, DEFAULT_GENERATE_OVERLAYS
            )

            if str(overlay_enabled).lower() != BOOLEAN_TRUE_STRING:
                return False

            # Check if timelapse has overlay configuration
            overlay_config = self.overlay_service.get_effective_overlay_config(
                timelapse_id
            )

            # Return True if config exists and is not empty
            return overlay_config is not None and bool(overlay_config)

        except Exception as e:
            logger.error(
                f"Error checking overlay enabled status for timelapse {timelapse_id}: {e}"
            )
            return False  # Fail safe - disable overlays on error

    def get_overlay_settings(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Get overlay settings for timelapse.

        Retrieves complete overlay configuration including templates,
        positioning, fonts, and content settings.

        Args:
            timelapse_id: Timelapse identifier

        Returns:
            Complete overlay settings dictionary
        """
        try:
            # Use OverlayService to get effective configuration
            config = self.overlay_service.get_effective_overlay_config(timelapse_id)

            if not config:
                return {}

            # Convert to dictionary format for bridge interface
            if hasattr(config, "model_dump"):
                return config.model_dump()
            elif hasattr(config, "dict"):
                return config.dict()
            else:
                return config if isinstance(config, dict) else {}

        except Exception as e:
            logger.error(
                f"Error getting overlay settings for timelapse {timelapse_id}: {e}"
            )
            return {}

    def generate_overlay_path(
        self, camera_id: int, timelapse_id: int, image_filename: str
    ) -> Optional[Path]:
        """
        Generate file path for overlay PNG.

        Creates standardized overlay file path following entity structure.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier
            image_filename: Base image filename for overlay naming

        Returns:
            Complete file path for overlay PNG
        """
        try:

            overlay_path = file_helpers.get_overlay_path_for_image(
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                image_path=image_filename,
            )
            return Path(overlay_path) if overlay_path else None

        except Exception as e:
            logger.error(f"Error generating overlay path: {e}")
            return None

    def create_overlay_content(
        self,
        timelapse_settings: Dict[str, Any],
        weather_data: Optional[Dict[str, Any]] = None,
        image_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create overlay content data.

        Assembles all data needed for overlay generation including
        weather information, timestamps, and custom text.

        Args:
            timelapse_settings: Timelapse overlay configuration
            weather_data: Weather information for overlay
            image_metadata: Image capture metadata

        Returns:
            Complete overlay content data
        """
        try:
            content_data = {
                "timestamp": (
                    image_metadata.get("captured_at") if image_metadata else None
                ),
                "frame_number": (
                    image_metadata.get("frame_number", 0) if image_metadata else 0
                ),
                "day_number": (
                    image_metadata.get("day_number", 0) if image_metadata else 0
                ),
                "timelapse_name": timelapse_settings.get("name", "Timelapse"),
                "custom_text": timelapse_settings.get("custom_text", ""),
            }

            # Add weather data if available
            if weather_data:
                content_data.update(
                    {
                        "temperature": weather_data.get("temperature"),
                        "weather_conditions": weather_data.get("conditions"),
                        "humidity": weather_data.get("humidity"),
                        "wind_speed": weather_data.get("wind_speed"),
                    }
                )

            return content_data

        except Exception as e:
            logger.error(f"Error creating overlay content: {e}")
            return {}

    def render_overlay_png(
        self,
        base_image_path: str,
        overlay_content: Dict[str, Any],
        overlay_settings: Dict[str, Any],
        output_path: Path,
    ) -> Dict[str, Any]:
        """
        Render overlay content to PNG file.

        Performs actual overlay generation using templates and content data.

        Args:
            base_image_path: Path to base image (camera capture)
            overlay_content: Overlay content data
            overlay_settings: Overlay configuration settings
            output_path: Target file path for PNG

        Returns:
            Rendering result with success status and metadata
        """
        try:
            # Delegate to overlay service for actual rendering
            # This bridge method coordinates the call but doesn't implement rendering

            # Convert overlay_settings dict to OverlayConfiguration if needed
            config = overlay_settings
            if isinstance(overlay_settings, dict):
                config = OverlayConfiguration(**overlay_settings)
            renderer = OverlayRenderer(config)
            success = renderer.render_overlay(
                base_image_path=base_image_path,
                context_data=overlay_content,
                output_path=str(output_path),
            )

            if success:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                return {
                    "success": True,
                    "output_path": str(output_path),
                    "file_size": file_size,
                    "content_items": len(overlay_settings.get("overlay_items", [])),
                }
            else:
                return {
                    "success": False,
                    "error": "Overlay rendering failed",
                    "output_path": str(output_path),
                }

        except Exception as e:
            logger.error(f"Error rendering overlay PNG: {e}")
            return {
                "success": False,
                "error": str(e),
                "output_path": str(output_path),
            }

    # Create fallback overlay when main overlay generation fails
    def create_fallback_overlay(
        self, output_path: Path, overlay_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create transparent fallback overlay on generation failure.

        Creates empty transparent PNG when overlay generation fails.

        Args:
            output_path: Target file path for fallback overlay
            overlay_settings: Overlay settings for dimensions

        Returns:
            Fallback creation result
        """
        try:

            # Get dimensions from settings or use defaults
            width, height = self.get_overlay_dimensions(overlay_settings)

            # Create transparent PNG
            transparent_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save transparent PNG
            transparent_image.save(output_path, "PNG")

            file_size = output_path.stat().st_size

            logger.info(f"Created fallback transparent overlay: {output_path}")

            return {
                "success": True,
                "fallback": True,
                "output_path": str(output_path),
                "file_size": file_size,
                "dimensions": (width, height),
            }

        except Exception as e:
            logger.error(f"Error creating fallback overlay: {e}")
            return {
                "success": False,
                "error": str(e),
                "output_path": str(output_path),
            }

    def validate_overlay_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate overlay settings configuration.

        Checks overlay settings for completeness and validity.

        Args:
            settings: Overlay settings to validate

        Returns:
            Validation result with status and error details
        """
        try:

            # Convert dict to OverlayConfiguration model for validation
            config = None
            if isinstance(settings, dict):
                try:
                    config = OverlayConfiguration(**settings)
                except Exception as e:
                    return {
                        "valid": False,
                        "issues": [f"Invalid configuration format: {str(e)}"],
                        "warnings": [],
                        "overlay_count": 0,
                    }
            elif isinstance(settings, OverlayConfiguration):
                config = settings

            # Use overlay helpers for validation
            validation_result = (
                OverlaySettingsResolver.validate_configuration_completeness(config)
            )

            return validation_result

        except Exception as e:
            logger.error(f"Error validating overlay settings: {e}")
            return {
                "valid": False,
                "issues": [f"Validation error: {str(e)}"],
                "warnings": [],
                "overlay_count": 0,
            }

    def get_weather_data_for_overlay(
        self, image_metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get weather data formatted for overlay use.

        Retrieves and formats weather data for overlay display.

        Args:
            image_metadata: Image metadata with timestamp information

        Returns:
            Formatted weather data for overlay, None if unavailable
        """
        try:
            # Extract timestamp from metadata
            timestamp = image_metadata.get("captured_at") or image_metadata.get(
                "timestamp"
            )
            if not timestamp:
                logger.debug("No timestamp in image metadata for weather lookup")
                return None

            # Use weather manager to get weather data for the timestamp
            # TODO: Implement get_weather_for_timestamp method in WeatherManager
            # For now, return None to indicate no weather data available
            weather_data = None

            if not weather_data:
                logger.debug(f"No weather data available for timestamp {timestamp}")
                return None

            # Format for overlay consumption
            return {
                "temperature": weather_data.get("temperature"),
                "conditions": weather_data.get("conditions"),
                "humidity": weather_data.get("humidity"),
                "wind_speed": weather_data.get("wind_speed"),
                "timestamp": timestamp,
            }

        except Exception as e:
            logger.error(f"Error getting weather data for overlay: {e}")
            return None

    def format_overlay_timestamp(
        self, timestamp: str, timezone_info: Dict[str, Any]
    ) -> str:
        """
        Format timestamp for overlay display.

        Formats capture timestamp according to overlay settings.

        Args:
            timestamp: Raw timestamp string
            timezone_info: Timezone configuration

        Returns:
            Formatted timestamp string for overlay
        """
        try:

            # Use time utilities for consistent formatting
            # Parse timestamp string to datetime if needed
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    # Fallback to current time if parsing fails
                    dt = utc_now()
            else:
                dt = timestamp if timestamp else utc_now()

            formatted_time = format_date_string(
                dt=dt,
                format_str=timezone_info.get("format", "%Y-%m-%d %H:%M:%S"),
            )

            return formatted_time

        except Exception as e:
            logger.error(f"Error formatting overlay timestamp: {e}")
            # Fallback to basic string representation
            return str(timestamp)

    def get_overlay_dimensions(
        self, overlay_settings: Dict[str, Any]
    ) -> Tuple[int, int]:
        """
        Get overlay image dimensions.

        Determines overlay PNG dimensions based on settings.

        Args:
            overlay_settings: Overlay configuration

        Returns:
            Tuple of (width, height) for overlay PNG
        """
        try:
            # Get dimensions from settings or use camera-based defaults
            width = overlay_settings.get("overlay_width")
            height = overlay_settings.get("overlay_height")

            # If not specified, use camera resolution or default
            if not width or not height:
                # Default to common HD dimensions for overlays
                width = width or DEFAULT_OVERLAY_WIDTH
                height = height or DEFAULT_OVERLAY_HEIGHT

            # Ensure minimum dimensions
            width = max(width, MIN_OVERLAY_WIDTH)
            height = max(height, MIN_OVERLAY_HEIGHT)

            # Ensure maximum dimensions for performance
            width = min(width, MAX_OVERLAY_WIDTH)
            height = min(height, MAX_OVERLAY_HEIGHT)

            return (int(width), int(height))

        except Exception as e:
            logger.error(f"Error getting overlay dimensions: {e}")
            # Return safe default dimensions
            return (DEFAULT_OVERLAY_WIDTH, DEFAULT_OVERLAY_HEIGHT)

    def cleanup_overlay_files(
        self, camera_id: int, days_to_keep: int = 30
    ) -> Dict[str, Any]:
        """
        Clean up old overlay files.

        Removes overlay files older than specified retention period.

        Args:
            camera_id: Camera identifier for targeted cleanup
            days_to_keep: Number of days to retain overlay files

        Returns:
            Cleanup result with file counts and status
        """
        try:

            cleaned_files = 0
            total_size_freed = 0
            cutoff_date = utc_now() - timedelta(days=days_to_keep)

            # Get base data directory from config

            data_directory = settings.data_directory
            camera_dir = Path(data_directory) / "cameras" / f"camera-{camera_id}"

            if not camera_dir.exists():
                return {
                    "success": True,
                    "cleaned_files": 0,
                    "size_freed_bytes": 0,
                    "message": "Camera directory not found",
                }

            # Find all overlay files in camera directory
            for timelapse_dir in camera_dir.glob("timelapses/timelapse-*/overlays"):
                if timelapse_dir.is_dir():
                    for overlay_file in timelapse_dir.glob("*.png"):
                        try:
                            file_stat = overlay_file.stat()
                            file_modified = datetime.fromtimestamp(
                                file_stat.st_mtime, tz=cutoff_date.tzinfo
                            )

                            if file_modified < cutoff_date:
                                file_size = file_stat.st_size
                                overlay_file.unlink()
                                cleaned_files += 1
                                total_size_freed += file_size

                        except Exception as e:
                            logger.warning(
                                f"Error cleaning overlay file {overlay_file}: {e}"
                            )

            logger.info(
                f"Cleaned {cleaned_files} overlay files for camera {camera_id}, freed {total_size_freed} bytes"
            )

            return {
                "success": True,
                "cleaned_files": cleaned_files,
                "size_freed_bytes": total_size_freed,
                "days_to_keep": days_to_keep,
                "camera_id": camera_id,
            }

        except Exception as e:
            logger.error(f"Error cleaning overlay files for camera {camera_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "cleaned_files": 0,
                "size_freed_bytes": 0,
            }

    def _bridge_to_overlay_service(self, operation: str, **kwargs) -> Any:
        """
        Internal bridge method to overlay service.

        Central coordination point for overlay service operations.
        Will be replaced with overlay domain calls during extraction.

        Args:
            operation: Overlay operation to perform
            **kwargs: Operation-specific arguments

        Returns:
            Operation result from overlay service
        """
        try:
            logger.debug(f"Bridging to overlay service: {operation}")

            if operation == "generate_overlay":
                image_id = kwargs.get("image_id")
                force_regenerate = kwargs.get("force_regenerate", False)
                # Validate image_id is a valid integer
                if image_id is not None and isinstance(image_id, int):
                    return self.overlay_service.generate_overlay_for_image(
                        image_id=image_id, force_regenerate=force_regenerate
                    )
                else:
                    logger.warning("Invalid image_id for generate_overlay operation")
                    return None

            # Handle overlay configuration retrieval
            elif operation == "get_effective_config":
                timelapse_id = kwargs.get("timelapse_id")
                # Validate timelapse_id is a valid integer
                if timelapse_id is not None and isinstance(timelapse_id, int):
                    return self.overlay_service.get_effective_overlay_config(
                        timelapse_id
                    )
                else:
                    logger.warning(
                        "Invalid timelapse_id for get_effective_config operation"
                    )
                    return None

            elif operation == "validate_config":
                config = kwargs.get("config")

                # Validate config is an OverlayConfiguration
                if config is not None and isinstance(config, OverlayConfiguration):
                    return OverlaySettingsResolver.validate_configuration_completeness(
                        config
                    )
                else:
                    logger.warning("Invalid config for validate_config operation")
                    return None

            else:
                logger.warning(f"Unknown overlay service operation: {operation}")
                return None

        except Exception as e:
            logger.error(f"Error bridging to overlay service ({operation}): {e}")
            return None

    def _ensure_overlay_directory(self, camera_id: int, timelapse_id: int) -> Path:
        """
        Ensure overlay directory exists for camera/timelapse.

        Creates overlay directory following entity-based structure.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier

        Returns:
            Path to overlay directory
        """
        try:
            data_directory = settings.data_directory

            # Create overlay directory path following entity structure
            # data/cameras/camera-{id}/timelapses/timelapse-{id}/overlays/
            overlay_dir = (
                Path(data_directory)
                / "cameras"
                / f"camera-{camera_id}"
                / "timelapses"
                / f"timelapse-{timelapse_id}"
                / "overlays"
            )

            # Ensure directory exists
            overlay_dir.mkdir(parents=True, exist_ok=True)

            return overlay_dir

        except Exception as e:
            logger.error(f"Error ensuring overlay directory: {e}")
            raise

    def _get_overlay_path_for_image(self, image) -> Optional[str]:
        """
        Get overlay path for a specific image.

        Helper method to determine the overlay file path for an image.

        Args:
            image: Image database record

        Returns:
            Overlay file path if it exists, None otherwise
        """
        try:
            overlay_path = file_helpers.get_overlay_path_for_image(
                camera_id=image.camera_id,
                timelapse_id=image.timelapse_id,
                image_path=Path(image.file_path).name,
            )

            # Check if the overlay file actually exists
            if overlay_path and Path(overlay_path).exists():
                return str(overlay_path)
            return None

        except Exception as e:
            logger.error(f"Error getting overlay path for image {image.id}: {e}")
            return None

    def _format_overlay_result(
        self, raw_result: Dict[str, Any], operation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format overlay operation result for workflow consumption.

        Standardizes overlay generation results for capture pipeline.

        Args:
            raw_result: Raw result from overlay generation
            operation_context: Context information for formatting

        Returns:
            Formatted result for workflow consumption
        """
        # Format overlay result for workflow consumption
        try:
            # Extract context information
            image_id = operation_context.get("image_id")
            timelapse_id = operation_context.get("timelapse_id")
            workflow_step = operation_context.get("workflow_step", "overlay_generation")

            # Base formatted result
            formatted_result = {
                "success": raw_result.get("success", False),
                "workflow_step": workflow_step,
                "image_id": image_id,
                "timelapse_id": timelapse_id,
                "timestamp": operation_context.get("timestamp"),
            }

            # Add success-specific data
            if raw_result.get("success", False):
                formatted_result.update(
                    {
                        "overlay_path": raw_result.get("overlay_path"),
                        "generation_method": raw_result.get(
                            "generation_method", "overlay_bridge"
                        ),
                        "file_size": raw_result.get("file_size"),
                        "content_items": raw_result.get("content_items", 0),
                    }
                )
            else:
                # Add error information
                formatted_result.update(
                    {
                        "error": raw_result.get("error"),
                        "reason": raw_result.get("reason"),
                        "retry_recommended": raw_result.get("retry_recommended", False),
                    }
                )

            # Add performance metadata if available
            if "processing_time_ms" in raw_result:
                formatted_result["processing_time_ms"] = raw_result[
                    "processing_time_ms"
                ]

            return formatted_result

        except Exception as e:
            logger.error(f"Error formatting overlay result: {e}")
            return {
                "success": False,
                "error": f"Result formatting error: {str(e)}",
                "workflow_step": "overlay_generation",
                "image_id": operation_context.get("image_id"),
                "timelapse_id": operation_context.get("timelapse_id"),
            }
