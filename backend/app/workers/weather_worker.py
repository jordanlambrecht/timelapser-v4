"""
Weather worker for Timelapser v4.

Handles weather data refresh and management for sunrise/sunset calculations.
"""

from datetime import datetime
from typing import Optional, Dict, Any, cast, Callable
from zoneinfo import ZoneInfo

from .base_worker import BaseWorker
from .utils.worker_status_builder import WorkerStatusBuilder
from ..services.logger import get_service_logger
from ..enums import LoggerName, LogSource, LogEmoji, WorkerType
from .models.weather_responses import (
    WeatherData,
    WeatherStatus,
    WeatherHealthStatus,
    WeatherWorkerStatus,
)
from ..services.weather_workflow_service import WeatherWorkflowService
from .exceptions import (
    ServiceUnavailableError,
    WeatherDataError,
    WeatherApiError,
    WeatherConfigurationError,
    WorkerInitializationError,
)
from ..utils.time_utils import utc_now
from ..services.weather.service import WeatherManager
from ..models.weather_model import OpenWeatherApiData
from ..database.sse_events_operations import (
    SyncSSEEventsOperations,
    SSEEventsOperations,
)
from ..services.settings_service import SyncSettingsService, SettingsService
from ..utils.time_utils import get_timezone_from_cache_sync
from ..enums import SSEPriority
from ..constants import (
    WEATHER_REFRESH_MISSING_SETTINGS,
    WEATHER_REFRESH_SKIPPED_DISABLED,
    EVENT_WEATHER_UPDATED,
    SSE_SOURCE_WORKER,
    WEATHER_DATA_STALE_THRESHOLD_HOURS,
    UNKNOWN_ERROR_MESSAGE,
)
from .constants import (
    SECONDS_PER_HOUR,
    WEATHER_STALENESS_CHECK_HOURS,
)

weather_logger = get_service_logger(LoggerName.WEATHER_WORKER, LogSource.WORKER)


class WeatherWorker(BaseWorker):
    """
    Worker responsible for weather data refresh and management.

    Handles:
    - Hourly weather data refresh from OpenWeather API
    - Weather data caching in weather_data table
    - Sunrise/sunset calculation for time windows
    - Weather API failure tracking and recovery
    """

    def __init__(
        self,
        weather_manager: WeatherManager,
        settings_service: SyncSettingsService,
        sse_ops: SyncSSEEventsOperations,
        async_settings_service: SettingsService,
        async_sse_ops: SSEEventsOperations,
    ):
        """
        Initialize weather worker with injected dependencies.

        Args:
            weather_manager: Weather management service
            settings_service: Settings operations service
            sse_ops: Server-sent events operations
            async_settings_service: Async settings service for performance
            async_sse_ops: Async SSE operations for performance

        Raises:
            WorkerInitializationError: If required dependencies are missing
        """
        # Validate required dependencies
        if not weather_manager:
            raise WorkerInitializationError("WeatherManager is required")
        if not settings_service:
            raise WorkerInitializationError("SyncSettingsService is required")
        if not sse_ops:
            raise WorkerInitializationError("SyncSSEEventsOperations is required")
        if not async_settings_service:
            raise WorkerInitializationError("SettingsService is required")
        if not async_sse_ops:
            raise WorkerInitializationError("SSEEventsOperations is required")

        super().__init__("WeatherWorker")
        self.weather_manager = weather_manager
        self.settings_service = settings_service
        self.async_settings_service = async_settings_service
        self.sse_ops = sse_ops
        self.async_sse_ops = async_sse_ops

        # Initialize workflow service for Service Layer Boundary Pattern
        self.weather_service = WeatherWorkflowService()

    async def initialize(self) -> None:
        """Initialize weather worker resources."""
        weather_logger.info(
            "Initialized weather worker", store_in_db=False, emoji=LogEmoji.SYSTEM
        )

    async def cleanup(self) -> None:
        """Cleanup weather worker resources."""
        weather_logger.info(
            "Cleaned up weather worker", store_in_db=False, emoji=LogEmoji.SYSTEM
        )

    async def refresh_weather_data(self, force_refresh: bool = False) -> None:
        """Refresh weather data if needed and weather is enabled."""
        weather_logger.info(
            f"Weather refresh triggered (force_refresh={force_refresh})",
            emoji=LogEmoji.SYSTEM,
        )
        try:
            # Check if weather functionality is enabled
            settings_dict = await self.async_settings_service.get_all_settings()
            weather_logger.debug(
                f"Retrieved settings dict with {len(settings_dict)} keys"
            )

            # Service Layer Boundary Pattern - Convert to typed settings using workflow service
            weather_settings = self.weather_service.get_weather_settings(settings_dict)

            weather_logger.debug(
                f"Weather enabled: {weather_settings.weather_enabled}",
                emoji=LogEmoji.SYSTEM,
            )
            if not weather_settings.weather_enabled:
                weather_logger.debug(WEATHER_REFRESH_SKIPPED_DISABLED)
                return

            # Check if we have required settings
            weather_logger.debug(
                f"Location configured - lat: {weather_settings.latitude}, "
                f"lng: {weather_settings.longitude}"
            )

            # Get API key securely through settings service
            api_key = await self.async_settings_service.get_openweather_api_key()
            api_key_status = "configured" if api_key else "missing"
            weather_logger.debug(
                f"API key status: {api_key_status}", emoji=LogEmoji.API
            )

            if not all(
                [weather_settings.latitude, weather_settings.longitude, api_key]
            ):
                weather_logger.warning(WEATHER_REFRESH_MISSING_SETTINGS)
                return

            # Type narrowing - at this point we know api_key is not None
            assert api_key is not None, "api_key should not be None after validation"

            should_refresh = force_refresh

            if not force_refresh:
                # Check if weather data is stale using the new weather_data table
                latest_weather = self.weather_manager.weather_ops.get_latest_weather()

                if latest_weather:
                    # Convert to typed weather data
                    cached_weather_data = WeatherData.from_dict(latest_weather)
                    # Check if weather data is fresh (within the last hour)
                    weather_date = cached_weather_data.date_fetched
                    if weather_date:
                        try:
                            # Convert to datetime if needed
                            if isinstance(weather_date, str):
                                # Handle ISO format strings
                                weather_datetime = datetime.fromisoformat(
                                    cast(str, weather_date).replace("Z", "+00:00")
                                )
                            elif isinstance(weather_date, datetime):
                                weather_datetime = weather_date
                            else:
                                # Invalid format, treat as stale
                                weather_datetime = None

                            if weather_datetime:
                                # Calculate hours since last refresh using timezone-aware comparison
                                try:
                                    # Get timezone-aware current time using cached approach
                                    timezone_str = get_timezone_from_cache_sync(
                                        self.settings_service
                                    )
                                    tz = ZoneInfo(timezone_str)
                                    now = datetime.now(tz)

                                    # Convert weather_datetime to the same timezone if needed
                                    if weather_datetime.tzinfo is None:
                                        # If weather datetime has no timezone, assume it's in the same timezone
                                        weather_datetime = weather_datetime.replace(
                                            tzinfo=tz
                                        )
                                    else:
                                        # Convert to the configured timezone for comparison
                                        weather_datetime = weather_datetime.astimezone(
                                            tz
                                        )

                                    hours_since_refresh = (
                                        now - weather_datetime
                                    ).total_seconds() / SECONDS_PER_HOUR

                                    # Check if data is fresh (less than 1 hour old)
                                    if (
                                        hours_since_refresh
                                        < WEATHER_STALENESS_CHECK_HOURS
                                    ):
                                        weather_logger.debug(
                                            f"Weather data is current "
                                            f"({hours_since_refresh:.1f}h old), skipping refresh"
                                        )
                                        return
                                    else:
                                        weather_logger.info(
                                            f"Weather data is stale "
                                            f"({hours_since_refresh:.1f}h old), refreshing..."
                                        )
                                        should_refresh = True
                                except Exception as tz_e:
                                    weather_logger.warning(
                                        f"Failed to get timezone for comparison: {tz_e}"
                                    )
                                    # Fallback to naive datetime comparison
                                    now = utc_now()
                                    if weather_datetime.tzinfo is not None:
                                        weather_datetime = weather_datetime.replace(
                                            tzinfo=None
                                        )

                                    hours_since_refresh = (
                                        now - weather_datetime
                                    ).total_seconds() / SECONDS_PER_HOUR

                                    if (
                                        hours_since_refresh
                                        < WEATHER_STALENESS_CHECK_HOURS
                                    ):
                                        weather_logger.debug(
                                            f"Weather data is current "
                                            f"({hours_since_refresh:.1f}h old, fallback), "
                                            f"skipping refresh"
                                        )
                                        return
                                    else:
                                        weather_logger.info(
                                            f"Weather data is stale "
                                            f"({hours_since_refresh:.1f}h old, fallback), "
                                            f"refreshing..."
                                        )
                                        should_refresh = True

                        except Exception as e:
                            weather_logger.warning(
                                f"Failed to parse weather date for staleness check: {e}"
                            )
                            # If we can't parse the date, assume it's stale and refresh
                            should_refresh = True
                else:
                    # No weather data found, need to refresh
                    weather_logger.info(
                        "No weather data found, refreshing...", store_in_db=False
                    )
                    should_refresh = True

            if should_refresh:
                weather_logger.info(
                    "Refreshing weather data...", store_in_db=True, emoji=LogEmoji.API
                )

                # Call the async weather refresh method directly with plain text API key
                weather_logger.info(
                    f"Calling weather manager refresh with API key: "
                    f"{'***' + api_key[-4:] if len(api_key) > 4 else '***'}",
                    emoji=LogEmoji.API,
                )
                weather_data: Optional[OpenWeatherApiData] = (
                    await self.weather_manager.refresh_weather_if_needed(
                        api_key, force=force_refresh
                    )
                )

                if weather_data:
                    weather_logger.info(
                        f"Weather data refreshed successfully: "
                        f"{weather_data.temperature}°C, {weather_data.description}",
                        emoji=LogEmoji.SUCCESS,
                    )

                    # Broadcast weather update event
                    try:
                        event_id = await self.async_sse_ops.create_event(
                            EVENT_WEATHER_UPDATED,
                            {
                                "temperature": weather_data.temperature,
                                "icon": weather_data.icon,
                                "description": weather_data.description,
                                "date_fetched": (weather_data.date_fetched.isoformat()),
                            },
                            SSEPriority.NORMAL,
                            SSE_SOURCE_WORKER,
                        )
                        if event_id:
                            weather_logger.debug(
                                f"Created weather update SSE event with ID: {event_id}"
                            )
                        else:
                            weather_logger.warning(
                                "SSE event creation returned no ID", store_in_db=False
                            )
                    except ServiceUnavailableError as e:
                        weather_logger.error(
                            "SSE service unavailable for weather update event", e
                        )
                    except Exception as e:
                        weather_logger.warning(
                            f"Failed to create weather update SSE event: {e}"
                        )
                else:
                    weather_logger.warning(
                        "Failed to refresh weather data - "
                        "no data returned from weather manager"
                    )

        except WeatherConfigurationError as e:
            weather_logger.error(
                f"Weather configuration error during refresh: {e}", store_in_db=False
            )
        except WeatherApiError as e:
            weather_logger.error(
                f"Weather API error during refresh: {e}", store_in_db=False
            )
        except ServiceUnavailableError as e:
            weather_logger.error(
                f"Required service unavailable for weather refresh: {e}",
                store_in_db=False,
            )
        except Exception as e:
            weather_logger.warning(
                f"Unexpected error refreshing weather data: {e}", store_in_db=False
            )

    async def get_current_weather_status(self) -> Optional[dict]:
        """
        Get current weather status for monitoring.

        Returns:
            Optional[dict]: Current weather data or None if unavailable
        """
        try:
            latest_weather = self.weather_manager.weather_ops.get_latest_weather()

            if not latest_weather:
                return None

            # Convert to typed weather data
            weather_data = WeatherData.from_dict(latest_weather)

            # Return comprehensive status information
            return {
                "temperature": weather_data.temperature,
                "icon": weather_data.icon,
                "description": weather_data.description,
                "date_fetched": weather_data.date_fetched,
                "sunrise_timestamp": weather_data.sunrise_timestamp,
                "sunset_timestamp": weather_data.sunset_timestamp,
                "api_key_valid": weather_data.api_key_valid,
                "api_failing": weather_data.api_failing,
            }

        except WeatherDataError as e:
            weather_logger.error(
                f"Weather data error getting current status: {e}", store_in_db=False
            )
            return None
        except ServiceUnavailableError as e:
            weather_logger.error(
                f"Service unavailable getting current weather status: {e}"
            )
            return None
        except Exception as e:
            weather_logger.warning(
                f"Unexpected error getting current weather status: {e}"
            )
            return None

    async def check_weather_health(self) -> Dict[str, Any]:
        """
        Check weather system health status.

        Returns:
            Dict[str, Any]: Health status information
        """
        try:
            health_status = {
                "weather_enabled": False,
                "api_key_configured": False,
                "location_configured": False,
                "data_current": False,
                "api_failing": False,
                "last_update": None,
                "errors": [],
            }

            # Check basic configuration
            settings_dict = await self.async_settings_service.get_all_settings()

            # Service Layer Boundary Pattern - Convert to typed settings using workflow service
            weather_settings = self.weather_service.get_weather_settings(settings_dict)

            # Check API key
            api_key = await self.async_settings_service.get_openweather_api_key()
            weather_settings.api_key_configured = bool(api_key)

            # Update health status using typed settings
            health_status["weather_enabled"] = weather_settings.weather_enabled
            health_status["api_key_configured"] = weather_settings.api_key_configured
            health_status["location_configured"] = (
                weather_settings.is_location_configured
            )

            # Check recent data
            weather_status = await self.get_current_weather_status()
            if weather_status:
                # Convert to typed weather status
                weather_status_typed = WeatherStatus.from_dict(weather_status)
                health_status["last_update"] = weather_status_typed.date_fetched
                health_status["api_failing"] = weather_status_typed.api_failing

                # Check if data is current (within last 25 hours)
                if weather_status_typed.date_fetched:
                    try:
                        last_update = weather_status_typed.date_fetched
                        if isinstance(last_update, str):
                            last_update = datetime.fromisoformat(
                                cast(str, last_update).replace("Z", "+00:00")
                            )
                        elif isinstance(last_update, datetime):
                            pass  # Already datetime
                        else:
                            last_update = None

                        if last_update:
                            hours_since_update = (
                                utc_now() - last_update.replace(tzinfo=None)
                            ).total_seconds() / SECONDS_PER_HOUR
                            health_status["data_current"] = (
                                hours_since_update <= WEATHER_DATA_STALE_THRESHOLD_HOURS
                            )

                    except Exception as e:
                        health_status["errors"].append(f"Date parsing error: {e}")

            return health_status

        except WeatherConfigurationError as e:
            weather_logger.error(
                f"Weather configuration error during health check: {e}"
            )
            return {
                "weather_enabled": False,
                "api_key_configured": False,
                "location_configured": False,
                "data_current": False,
                "api_failing": True,
                "last_update": None,
                "errors": [f"Configuration error: {str(e)}"],
            }
        except ServiceUnavailableError as e:
            weather_logger.error(
                f"Service unavailable during weather health check: {e}"
            )
            return {
                "weather_enabled": False,
                "api_key_configured": False,
                "location_configured": False,
                "data_current": False,
                "api_failing": True,
                "last_update": None,
                "errors": [f"Service unavailable: {str(e)}"],
            }
        except Exception as e:
            weather_logger.warning(f"Unexpected error checking weather health: {e}")
            return {
                "weather_enabled": False,
                "api_key_configured": False,
                "location_configured": False,
                "data_current": False,
                "api_failing": True,
                "last_update": None,
                "errors": [f"Unexpected error: {str(e)}"],
            }

    def _run_async_in_status(
        self,
        async_func: Callable,
        fallback_value: Any = None,
        operation_name: str = "async operation",
    ) -> Any:
        """
        Standard async-to-sync bridging for status methods.

        Safely runs async functions within synchronous status methods with
        proper error handling and logging.
        """
        try:
            import asyncio

            return asyncio.run(async_func())
        except Exception as e:
            weather_logger.debug(
                f"Async {operation_name} failed in status method: {e}",
                store_in_db=False,
            )
            return fallback_value

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive weather worker status using explicit status pattern.

        Returns:
            Dict[str, Any]: Complete weather worker status information
        """
        try:
            # Build explicit base status - no super() calls
            base_status = WorkerStatusBuilder.build_base_status(
                name=self.name,
                running=self.running,
                worker_type=WorkerType.WEATHER_WORKER.value,
            )

            # Get current weather status using async bridging
            current_weather = self._run_async_in_status(
                self.get_current_weather_status,
                fallback_value=None,
                operation_name="get_current_weather_status",
            )

            # Get health status using async bridging
            health_status = self._run_async_in_status(
                self.check_weather_health,
                fallback_value=None,
                operation_name="check_weather_health",
            )

            # Convert to typed responses using models
            health_status_typed = None
            if health_status:
                health_status_typed = WeatherHealthStatus.from_dict(health_status)

            current_weather_typed = None
            if current_weather:
                current_weather_typed = WeatherStatus.from_dict(current_weather)

            # Get service-specific status
            service_status = self.weather_service.get_worker_status(
                weather_manager=self.weather_manager,
                health_status=health_status_typed,
                current_weather=current_weather_typed,
            )

            # Convert to WeatherWorkerStatus model for validation and consistency
            merged_status = WorkerStatusBuilder.merge_service_status(
                base_status, service_status
            )
            weather_worker_status = WeatherWorkerStatus.from_dict(merged_status)

            # Return as dict for compatibility
            return weather_worker_status.__dict__

        except Exception as e:
            # Return standardized error status
            error_status = WorkerStatusBuilder.build_error_status(
                name=self.name,
                worker_type=WorkerType.WEATHER_WORKER.value,
                error_type="unexpected",
                error_message=str(e) or UNKNOWN_ERROR_MESSAGE,
            )
            return error_status

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status for worker management system compatibility.

        This method provides simple binary health information separate
        from the detailed status reporting in get_status().
        """
        return WorkerStatusBuilder.build_simple_health_status(
            running=self.running,
            worker_type=WorkerType.WEATHER_WORKER.value,
            additional_checks={
                "weather_manager_available": self.weather_manager is not None,
                "settings_service_available": self.settings_service is not None,
                "sse_ops_available": self.sse_ops is not None,
            },
        )
