"""
Capture worker for Timelapser v4.

Handles image capture from RTSP cameras and health monitoring.
"""

import asyncio
from datetime import datetime, time

from .base_worker import BaseWorker
from ..models.camera_model import Camera
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_sync,
    get_timezone_aware_time_sync,
    parse_time_string,
    utc_now,
)
from ..constants import (
    DEFAULT_TIMEZONE,
    SETTING_KEY_GENERATE_THUMBNAILS,
    DEFAULT_GENERATE_THUMBNAILS,
    BOOLEAN_TRUE_STRING,
    CORRUPTION_ACTION_SAVED,
    EVENT_IMAGE_CAPTURED,
    DUMMY_API_KEY,
)
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..services.camera_service import SyncCameraService
from ..services.image_capture_service import ImageCaptureService
from ..services.timelapse_service import SyncTimelapseService
from ..services.settings_service import SyncSettingsService
from ..services.video_automation_service import VideoAutomationService
from ..services.weather.service import WeatherManager
from ..services.weather.service import OpenWeatherService


class CaptureWorker(BaseWorker):
    """
    Worker responsible for image capture and camera health monitoring.

    Handles:
    - Scheduled image capture from RTSP cameras
    - Camera connectivity and health monitoring
    - Time window validation for capture scheduling
    - Integration with corruption detection and video automation
    """

    def __init__(
        self,
        camera_service: SyncCameraService,
        image_capture_service: ImageCaptureService,
        timelapse_service: SyncTimelapseService,
        settings_service: SyncSettingsService,
        video_automation_service: VideoAutomationService,
        weather_manager: WeatherManager,
        sse_ops: SyncSSEEventsOperations,
    ):
        """
        Initialize capture worker with injected dependencies.

        Args:
            camera_service: Camera operations service
            image_capture_service: Image capture workflow service
            timelapse_service: Timelapse operations service
            settings_service: Settings operations service
            video_automation_service: Video automation service
            weather_manager: Weather manager for sun window calculations
            sse_ops: Server-sent events operations
        """
        super().__init__("CaptureWorker")
        self.camera_service = camera_service
        self.image_capture_service = image_capture_service
        self.timelapse_service = timelapse_service
        self.settings_service = settings_service
        self.video_automation_service = video_automation_service
        self.weather_manager = weather_manager
        self.sse_ops = sse_ops

    async def initialize(self) -> None:
        """Initialize capture worker resources."""
        self.log_info("Initialized capture worker")

    async def cleanup(self) -> None:
        """Cleanup capture worker resources."""
        self.log_info("Cleaned up capture worker")

    def _is_within_time_window(self, camera: Camera) -> bool:
        """Check if current time is within camera's capture window (regular or sun-based)."""
        try:
            # Check if camera uses custom time window (overrides global settings)
            # Note: custom_time_window fields may not exist in all Camera models
            if getattr(camera, "use_custom_time_window", False):
                start_time = getattr(camera, "custom_time_window_start", None)
                end_time = getattr(camera, "custom_time_window_end", None)

                if start_time and end_time:
                    return self._check_time_range(start_time, end_time)

            # Check camera's regular time window using Pydantic model fields
            if camera.use_time_window:
                start_time = camera.time_window_start
                end_time = camera.time_window_end

                if start_time and end_time:
                    return self._check_time_range(start_time, end_time)

            # Check if sunrise/sunset mode is enabled and weather data is available
            settings_dict = self.settings_service.get_all_settings()
            if settings_dict.get("sunrise_sunset_enabled", "false").lower() == "true":
                return self._check_sun_based_window(settings_dict)

            # No time restrictions - capture allowed
            return True

        except Exception as e:
            self.log_warning(
                f"Error checking time window for camera {camera.id if hasattr(camera, 'id') else 'unknown'}: {e}"
            )
            return True  # Default to allowing capture if check fails

    def _check_time_range(self, start_time_str: str, end_time_str: str) -> bool:
        """Check if current time is within the specified time range."""
        try:
            # If either time is None, allow capture (fail open)
            if not start_time_str or not end_time_str:
                self.log_warning(
                    f"Time window start or end is None: start={start_time_str}, end={end_time_str}"
                )
                return True

            # Convert string times to time objects if needed
            start_time = (
                parse_time_string(start_time_str)
                if isinstance(start_time_str, str)
                else start_time_str
            )
            end_time = (
                parse_time_string(end_time_str)
                if isinstance(end_time_str, str)
                else end_time_str
            )

            # If conversion failed, allow capture
            if not isinstance(start_time, time) or not isinstance(end_time, time):
                self.log_warning(
                    f"Start or end time is not a valid time object: start={start_time}, end={end_time}"
                )
                return True

            # Get current time in the configured timezone
            try:
                current_time = get_timezone_aware_time_sync(self.settings_service)
            except Exception:
                # Fallback to centralized timezone utility (AI-CONTEXT compliant)
                current_time = utc_now().time()

            # If current_time is not a time object, allow capture
            if not isinstance(current_time, time):
                self.log_warning(
                    f"Current time is not a valid time object: {current_time}"
                )
                return True

            # Handle overnight windows (e.g., 22:00 - 06:00)
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time

        except Exception as e:
            self.log_warning(
                f"Error parsing time range {start_time_str} - {end_time_str}: {e}"
            )
            return True

    def _check_sun_based_window(self, settings_dict: dict) -> bool:
        """Check if current time is within sunrise/sunset window."""
        try:
            # Get weather data from weather_data table using injected weather manager
            latest_weather = self.weather_manager.weather_ops.get_latest_weather()

            if not latest_weather:
                self.log_debug("No weather data available")
                return True  # Allow capture if no data

            sunrise_timestamp = latest_weather.get("sunrise_timestamp")
            sunset_timestamp = latest_weather.get("sunset_timestamp")

            if not sunrise_timestamp or not sunset_timestamp:
                self.log_debug("No sunrise/sunset data available")
                return True  # Allow capture if no data

            # Get offsets from settings
            try:
                sunrise_offset_minutes = int(
                    settings_dict.get("sunrise_offset_minutes", 0)
                )
            except (ValueError, TypeError):
                sunrise_offset_minutes = 0

            try:
                sunset_offset_minutes = int(
                    settings_dict.get("sunset_offset_minutes", 0)
                )
            except (ValueError, TypeError):
                sunset_offset_minutes = 0

            service = OpenWeatherService(
                api_key=DUMMY_API_KEY,
                latitude=0,
                longitude=0,
            )

            # Get timezone for sun window calculation
            timezone_str = settings_dict.get("timezone", DEFAULT_TIMEZONE)

            # Convert datetime objects to timestamps if needed
            if isinstance(sunrise_timestamp, datetime):
                sunrise_timestamp = int(sunrise_timestamp.timestamp())
            else:
                sunrise_timestamp = int(sunrise_timestamp)

            if isinstance(sunset_timestamp, datetime):
                sunset_timestamp = int(sunset_timestamp.timestamp())
            else:
                sunset_timestamp = int(sunset_timestamp)

            return service.is_within_sun_window(
                sunrise_timestamp=sunrise_timestamp,
                sunset_timestamp=sunset_timestamp,
                sunrise_offset_minutes=sunrise_offset_minutes,
                sunset_offset_minutes=sunset_offset_minutes,
                timezone_str=timezone_str,
            )

        except Exception as e:
            self.log_warning(f"Error checking sun-based window: {e}")
            return True  # Default to allowing capture if check fails

    async def capture_from_camera(self, camera_info: Camera):
        """
        Capture image from a single camera with comprehensive error handling.

        Args:
            camera_info: Camera model instance containing id, name, rtsp_url, etc.
        """
        # Use direct attribute access for Pydantic models
        camera_id = camera_info.id
        camera_name = camera_info.name

        try:
            # Check time window
            if not self._is_within_time_window(camera_info):
                self.log_debug(f"Camera {camera_name} outside time window, skipping")
                return

            # Validate camera_id is not None before proceeding
            if camera_id is None:
                self.log_error(f"Camera {camera_name} has no valid ID, skipping")
                return

            # Get active timelapse for this camera
            timelapse = await self.run_in_executor(
                self.timelapse_service.get_active_timelapse_for_camera, camera_id
            )
            if not timelapse:
                self.log_debug(f"No active timelapse for camera {camera_name}")
                return

            # Check thumbnail generation setting
            generate_thumbnails = await self.run_in_executor(
                lambda: (
                    self.settings_service.get_setting(SETTING_KEY_GENERATE_THUMBNAILS, DEFAULT_GENERATE_THUMBNAILS)
                    or DEFAULT_GENERATE_THUMBNAILS
                ).lower()
                == BOOLEAN_TRUE_STRING
            )

            self.log_info(
                f"Starting capture for camera {camera_id} ({camera_name}) [thumbnails: {'enabled' if generate_thumbnails else 'disabled'}]"
            )

            # Use ImageCaptureService for the complete capture workflow
            capture_result = await self.run_in_executor(
                self.image_capture_service.capture_and_process_image, camera_id
            )

            # Extract results from the service response
            success = capture_result.overall_success if capture_result else False
            message = (
                capture_result.error or "Capture completed"
                if capture_result
                else "Capture failed"
            )

            # For backward compatibility with corruption integration
            corruption_details = None
            if capture_result and hasattr(
                capture_result.health_monitoring, "corruption_score"
            ):
                corruption_details = {
                    "score": getattr(
                        capture_result.health_monitoring, "corruption_score", None
                    ),
                    "action_taken": CORRUPTION_ACTION_SAVED,
                    "detection_disabled": False,
                }

            # Log corruption detection results
            if corruption_details and not corruption_details.get("detection_disabled"):
                corruption_score = corruption_details.get("score", "N/A")
                action_taken = corruption_details.get("action_taken", "unknown")
                self.log_info(
                    f"Camera {camera_id} corruption check: score={corruption_score}, action={action_taken}"
                )

            if success:
                # Update camera connectivity
                if camera_id is not None:
                    await self.run_in_executor(
                        self.camera_service.update_camera_connectivity,
                        camera_id,
                        True,
                        None,
                    )

                # Get updated timelapse info for accurate image count
                updated_timelapse = await self.run_in_executor(
                    self.timelapse_service.get_active_timelapse_for_camera, camera_id
                )
                if updated_timelapse:
                    image_count = getattr(updated_timelapse, "image_count", 0)
                    self.log_info(f"Image captured, count: {image_count}")

                # Trigger per-capture video automation if enabled
                try:
                    automation_triggered = await self.run_in_executor(
                        self.video_automation_service.trigger_per_capture_generation,
                        camera_id,
                    )
                    if automation_triggered:
                        self.log_info(
                            f"Triggered per-capture video generation for camera {camera_id}"
                        )
                except Exception as e:
                    self.log_warning(
                        f"Failed to trigger per-capture automation for camera {camera_id}: {e}"
                    )

                # Broadcast image captured event
                event_data = {
                    "type": EVENT_IMAGE_CAPTURED,
                    "data": {
                        "camera_id": camera_id,
                        "image_count": (
                            getattr(updated_timelapse, "image_count", 0)
                            if updated_timelapse
                            else 0
                        ),
                    },
                    "timestamp": get_timezone_aware_timestamp_sync(
                        self.settings_service
                    ),
                }

                # Add corruption details if available
                if corruption_details and not corruption_details.get(
                    "detection_disabled"
                ):
                    event_data["data"]["corruption_score"] = corruption_details.get(
                        "score"
                    )
                    event_data["data"]["corruption_action"] = corruption_details.get(
                        "action_taken"
                    )

                await self.run_in_executor(
                    self.sse_ops.create_image_captured_event,
                    camera_id,
                    getattr(updated_timelapse, "id", 0) if updated_timelapse else 0,
                    (
                        getattr(updated_timelapse, "image_count", 0)
                        if updated_timelapse
                        else 0
                    ),
                    0,  # day_number - would need to be calculated from image data
                )

                self.log_info(f"Successfully captured and saved image: {message}")
            else:
                # Update camera connectivity as offline
                if camera_id is not None:
                    await self.run_in_executor(
                        self.camera_service.update_camera_connectivity,
                        camera_id,
                        False,
                        message,
                    )
                self.log_error(
                    f"Failed to capture from camera {camera_name}: {message}"
                )

        except Exception as e:
            if camera_id is not None:
                await self.run_in_executor(
                    self.camera_service.update_camera_connectivity,
                    camera_id,
                    False,
                    str(e),
                )
            self.log_error(f"Unexpected error capturing from camera {camera_name}", e)

    async def capture_all_running_cameras(self):
        """Capture images from all running cameras concurrently."""
        try:
            # Get cameras with running timelapses using proper service method
            cameras = await self.run_in_executor(
                self.camera_service.get_cameras_with_running_timelapses
            )

            if not cameras:
                self.log_debug("No cameras with running timelapses found")
                return

            self.log_info(
                f"Capturing from {len(cameras)} cameras with running timelapses"
            )

            # Use asyncio.gather for concurrent async captures
            tasks = [self.capture_from_camera(camera) for camera in cameras]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.log_error("Error in capture_all_running_cameras", e)

    async def check_camera_health(self):
        """
        Check and update camera health status based on RTSP connectivity.

        Performs comprehensive health monitoring for all active cameras:
        1. Retrieves all active cameras from database
        2. Tests RTSP connectivity without full image capture
        3. Updates database connectivity status for each camera
        4. Logs connectivity issues for monitoring and debugging
        """
        try:
            # Get all active cameras
            cameras = await self.run_in_executor(self.camera_service.get_active_cameras)

            if not cameras:
                self.log_debug("No active cameras found for health check")
                return

            self.log_info(f"Checking health for {len(cameras)} cameras")

            # Test connectivity for each camera
            for camera in cameras:
                camera_id = camera.id
                camera_name = camera.name

                try:
                    # Test RTSP connectivity using sync camera service
                    if camera_id is not None:
                        connectivity_result = await self.run_in_executor(
                            self.camera_service.test_connectivity, camera_id
                        )
                        success = connectivity_result.success
                        message = (
                            connectivity_result.error or "Connection test completed"
                        )
                    else:
                        success, message = False, "Camera ID is None"

                    if success:
                        if camera_id is not None:
                            await self.run_in_executor(
                                self.camera_service.update_camera_connectivity,
                                camera_id,
                                True,
                                None,
                            )
                        self.log_debug(f"Camera {camera_name} is online: {message}")
                    else:
                        if camera_id is not None:
                            await self.run_in_executor(
                                self.camera_service.update_camera_connectivity,
                                camera_id,
                                False,
                                message,
                            )
                        self.log_warning(f"Camera {camera_name} is offline: {message}")

                except Exception as e:
                    if camera_id is not None:
                        await self.run_in_executor(
                            self.camera_service.update_camera_connectivity,
                            camera_id,
                            False,
                            str(e),
                        )
                    self.log_error(f"Health check failed for camera {camera_name}", e)

        except Exception as e:
            self.log_error("Error in check_camera_health", e)
