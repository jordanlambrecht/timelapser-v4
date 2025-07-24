"""
Weather worker for Timelapser v4.

Handles weather data refresh and management for sunrise/sunset calculations.
"""

from datetime import datetime
from typing import Optional, TypedDict, Dict, Any
from zoneinfo import ZoneInfo

from .base_worker import BaseWorker, WorkerErrorResponse
from ..services.weather.service import WeatherManager
from ..models.weather_model import OpenWeatherApiData
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..services.settings_service import SyncSettingsService
from ..utils.time_utils import get_timezone_from_settings
from ..enums import SSEPriority
from ..constants import (
    WEATHER_REFRESH_MISSING_SETTINGS,
    WEATHER_REFRESH_SKIPPED_DISABLED,
    SETTING_KEY_WEATHER_ENABLED,
    DEFAULT_WEATHER_ENABLED,
    BOOLEAN_TRUE_STRING,
    DATE_STRING_LENGTH,
    EVENT_WEATHER_UPDATED,
    SSE_SOURCE_WORKER,
    WEATHER_DATA_STALE_THRESHOLD_HOURS,
    DEFAULT_TIMEZONE,
)


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
    ):
        """
        Initialize weather worker with injected dependencies.

        Args:
            weather_manager: Weather management service
            settings_service: Settings operations service
            sse_ops: Server-sent events operations
        """
        super().__init__("WeatherWorker")
        self.weather_manager = weather_manager
        self.settings_service = settings_service
        self.sse_ops = sse_ops

    async def initialize(self) -> None:
        """Initialize weather worker resources."""
        self.log_info("Initialized weather worker")

    async def cleanup(self) -> None:
        """Cleanup weather worker resources."""
        self.log_info("Cleaned up weather worker")

    async def refresh_weather_data(self, force_refresh: bool = False) -> None:
        """Refresh weather data if needed and weather is enabled."""
        self.log_info(f"🌤️ Weather refresh triggered (force_refresh={force_refresh})")
        try:
            # Check if weather functionality is enabled
            settings_dict = await self.run_in_executor(
                self.settings_service.get_all_settings
            )
            self.log_debug(f"Retrieved settings dict with {len(settings_dict)} keys")

            weather_enabled = (
                settings_dict.get(
                    SETTING_KEY_WEATHER_ENABLED, DEFAULT_WEATHER_ENABLED
                ).lower()
                == BOOLEAN_TRUE_STRING
            )
            self.log_debug(f"Weather enabled: {weather_enabled}")
            if not weather_enabled:
                self.log_debug(WEATHER_REFRESH_SKIPPED_DISABLED)
                return

            # Check if we have required settings
            latitude = settings_dict.get("latitude")
            longitude = settings_dict.get("longitude")
            self.log_debug(f"Location configured - lat: {latitude}, lng: {longitude}")

            # Get API key securely through settings service
            api_key = await self.run_in_executor(
                self.settings_service.get_openweather_api_key
            )
            api_key_status = "configured" if api_key else "missing"
            self.log_debug(f"API key status: {api_key_status}")

            if not all([latitude, longitude, api_key]):
                self.log_warning(WEATHER_REFRESH_MISSING_SETTINGS)
                return

            # Type narrowing - at this point we know api_key is not None
            assert api_key is not None, "api_key should not be None after validation"

            should_refresh = force_refresh

            if not force_refresh:
                # Check if weather data is stale using the new weather_data table
                latest_weather = self.weather_manager.weather_ops.get_latest_weather()

                if latest_weather:
                    # Check if weather data is fresh (within the last hour)
                    weather_date = latest_weather.get("weather_date_fetched")
                    if weather_date:
                        try:
                            # Convert to datetime if needed
                            if isinstance(weather_date, str):
                                # Handle ISO format strings
                                weather_datetime = datetime.fromisoformat(
                                    weather_date.replace("Z", "+00:00")
                                )
                            elif isinstance(weather_date, datetime):
                                weather_datetime = weather_date
                            else:
                                # Invalid format, treat as stale
                                weather_datetime = None

                            if weather_datetime:
                                # Calculate hours since last refresh using timezone-aware comparison
                                try:
                                    # Get timezone-aware current time
                                    timezone_str = get_timezone_from_settings(
                                        settings_dict
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
                                    ).total_seconds() / 3600

                                    # Check if data is fresh (less than 1 hour old)
                                    if hours_since_refresh < 1.0:
                                        self.log_debug(
                                            f"Weather data is current ({hours_since_refresh:.1f}h old), skipping refresh"
                                        )
                                        return
                                    else:
                                        self.log_info(
                                            f"Weather data is stale ({hours_since_refresh:.1f}h old), refreshing..."
                                        )
                                        should_refresh = True
                                except Exception as tz_e:
                                    self.log_warning(
                                        f"Failed to get timezone for comparison: {tz_e}"
                                    )
                                    # Fallback to naive datetime comparison
                                    now = datetime.now()
                                    if weather_datetime.tzinfo is not None:
                                        weather_datetime = weather_datetime.replace(
                                            tzinfo=None
                                        )

                                    hours_since_refresh = (
                                        now - weather_datetime
                                    ).total_seconds() / 3600

                                    if hours_since_refresh < 1.0:
                                        self.log_debug(
                                            f"Weather data is current ({hours_since_refresh:.1f}h old, fallback), skipping refresh"
                                        )
                                        return
                                    else:
                                        self.log_info(
                                            f"Weather data is stale ({hours_since_refresh:.1f}h old, fallback), refreshing..."
                                        )
                                        should_refresh = True

                        except Exception as e:
                            self.log_warning(
                                f"Failed to parse weather date for staleness check: {e}"
                            )
                            # If we can't parse the date, assume it's stale and refresh
                            should_refresh = True
                else:
                    # No weather data found, need to refresh
                    self.log_info("No weather data found, refreshing...")
                    should_refresh = True

            if should_refresh:
                self.log_info("Refreshing weather data...")

                # Call the async weather refresh method directly with plain text API key
                self.log_info(
                    f"🌡️ Calling weather manager refresh with API key: {'***' + api_key[-4:] if len(api_key) > 4 else '***'}"
                )
                weather_data: Optional[OpenWeatherApiData] = (
                    await self.weather_manager.refresh_weather_if_needed(
                        api_key, force=force_refresh
                    )
                )

                if weather_data:
                    self.log_info(
                        f"✅ Weather data refreshed successfully: {weather_data.temperature}°C, {weather_data.description}"
                    )

                    # Broadcast weather update event
                    try:
                        event_id = await self.run_in_executor(
                            self.sse_ops.create_event,
                            EVENT_WEATHER_UPDATED,
                            {
                                "temperature": weather_data.temperature,
                                "icon": weather_data.icon,
                                "description": weather_data.description,
                                "date_fetched": weather_data.date_fetched.isoformat(),
                            },
                            SSEPriority.NORMAL,
                            SSE_SOURCE_WORKER,
                        )
                        if event_id:
                            self.log_debug(
                                f"Created weather update SSE event with ID: {event_id}"
                            )
                        else:
                            self.log_warning("SSE event creation returned no ID")
                    except Exception as e:
                        self.log_error("Failed to create weather update SSE event", e)
                else:
                    self.log_warning(
                        "❌ Failed to refresh weather data - no data returned from weather manager"
                    )

        except Exception as e:
            self.log_error("💥 Error refreshing weather data", e)

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

            return {
                "temperature": latest_weather.get("current_temp"),
                "icon": latest_weather.get("current_weather_icon"),
                "description": latest_weather.get("current_weather_description"),
                "date_fetched": latest_weather.get("weather_date_fetched"),
                "sunrise_timestamp": latest_weather.get("sunrise_timestamp"),
                "sunset_timestamp": latest_weather.get("sunset_timestamp"),
                "api_key_valid": latest_weather.get("api_key_valid", True),
                "api_failing": latest_weather.get("api_failing", False),
            }

        except Exception as e:
            self.log_error("Error getting current weather status", e)
            return None

    async def check_weather_health(self) -> dict:
        """
        Check weather system health status.

        Returns:
            dict: Health status information
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
            settings_dict = await self.run_in_executor(
                self.settings_service.get_all_settings
            )

            health_status["weather_enabled"] = (
                settings_dict.get(
                    SETTING_KEY_WEATHER_ENABLED, DEFAULT_WEATHER_ENABLED
                ).lower()
                == BOOLEAN_TRUE_STRING
            )

            # Check API key
            api_key = await self.run_in_executor(
                self.settings_service.get_openweather_api_key
            )
            health_status["api_key_configured"] = bool(api_key)

            # Check location
            latitude = settings_dict.get("latitude")
            longitude = settings_dict.get("longitude")
            health_status["location_configured"] = bool(latitude and longitude)

            # Check recent data
            weather_status = await self.get_current_weather_status()
            if weather_status:
                health_status["last_update"] = weather_status.get("date_fetched")
                health_status["api_failing"] = weather_status.get("api_failing", False)

                # Check if data is current (within last 25 hours)
                if weather_status.get("date_fetched"):
                    try:
                        last_update = weather_status["date_fetched"]
                        if isinstance(last_update, str):
                            last_update = datetime.fromisoformat(
                                last_update.replace("Z", "+00:00")
                            )
                        elif isinstance(last_update, datetime):
                            pass  # Already datetime
                        else:
                            last_update = None

                        if last_update:
                            hours_since_update = (
                                datetime.now() - last_update.replace(tzinfo=None)
                            ).total_seconds() / 3600
                            health_status["data_current"] = (
                                hours_since_update <= WEATHER_DATA_STALE_THRESHOLD_HOURS
                            )

                    except Exception as e:
                        health_status["errors"].append(f"Date parsing error: {e}")

            return health_status

        except Exception as e:
            self.log_error("Error checking weather health", e)
            return {
                "weather_enabled": False,
                "api_key_configured": False,
                "location_configured": False,
                "data_current": False,
                "api_failing": True,
                "last_update": None,
                "errors": [str(e)],
            }

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive weather worker status (STANDARDIZED METHOD NAME).

        Returns:
            Dict[str, Any]: Complete weather worker status information
        """
        # Get base status from BaseWorker
        base_status = super().get_status()

        try:
            # Get current weather status
            current_weather = None
            try:
                import asyncio

                current_weather = asyncio.run(self.get_current_weather_status())
            except Exception as e:
                self.log_debug(f"Could not get current weather status: {e}")

            # Get health status
            health_status = None
            try:
                import asyncio

                health_status = asyncio.run(self.check_weather_health())
            except Exception as e:
                self.log_debug(f"Could not get weather health status: {e}")

            # Add weather-specific status information
            base_status.update(
                {
                    "worker_type": "WeatherWorker",
                    # Service health status
                    "weather_manager_status": (
                        "healthy" if self.weather_manager else "unavailable"
                    ),
                    "settings_service_status": (
                        "healthy" if self.settings_service else "unavailable"
                    ),
                    "sse_ops_status": "healthy" if self.sse_ops else "unavailable",
                    # Weather functionality status
                    "weather_enabled": (
                        health_status.get("weather_enabled", False)
                        if health_status
                        else False
                    ),
                    "api_key_configured": (
                        health_status.get("api_key_configured", False)
                        if health_status
                        else False
                    ),
                    "location_configured": (
                        health_status.get("location_configured", False)
                        if health_status
                        else False
                    ),
                    "data_current": (
                        health_status.get("data_current", False)
                        if health_status
                        else False
                    ),
                    "api_failing": (
                        health_status.get("api_failing", True)
                        if health_status
                        else True
                    ),
                    # Current weather data
                    "current_temperature": (
                        current_weather.get("temperature") if current_weather else None
                    ),
                    "current_description": (
                        current_weather.get("description") if current_weather else None
                    ),
                    "last_weather_update": (
                        current_weather.get("date_fetched") if current_weather else None
                    ),
                    # Overall health
                    "weather_system_healthy": (
                        all(
                            [
                                self.weather_manager is not None,
                                self.settings_service is not None,
                                self.sse_ops is not None,
                                (
                                    health_status.get("weather_enabled", False)
                                    if health_status
                                    else False
                                ),
                                (
                                    health_status.get("api_key_configured", False)
                                    if health_status
                                    else False
                                ),
                                (
                                    health_status.get("location_configured", False)
                                    if health_status
                                    else False
                                ),
                            ]
                        )
                        if health_status
                        else False
                    ),
                }
            )

        except Exception as e:
            self.log_error("Error getting weather worker status", e)
            base_status.update(
                {
                    "worker_type": "WeatherWorker",
                    "weather_manager_status": (
                        "healthy" if self.weather_manager else "unavailable"
                    ),
                    "settings_service_status": (
                        "healthy" if self.settings_service else "unavailable"
                    ),
                    "sse_ops_status": "healthy" if self.sse_ops else "unavailable",
                    "weather_system_healthy": False,
                    "status_error": str(e),
                }
            )

        return base_status
