"""
OpenWeather API Service for Timelapser v4

This module provides weather data integration using the OpenWeather API.
It handles:
- Hourly weather data caching
- Sunrise/sunset time calculation
- API key validation
- Time window calculations with sun-based offsets

Features:
- Automatic hourly refresh of weather data
- Configurable location via lat/lng
- Sunrise/sunset time calculation with custom offsets
- Temperature and weather condition tracking
- Graceful error handling and fallbacks
- Dependency injection for database operations

Authors: Timelapser Development Team
Version: 4.0
License: Private
"""

import traceback
import requests
import inspect
import json
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from loguru import logger
from zoneinfo import ZoneInfo

from ...database import sync_db
from ...database.sse_events_operations import SyncSSEEventsOperations
from ...enums import SSEPriority


# Import centralized time utilities (AI-CONTEXT compliant)
from ...utils.time_utils import (
    create_timezone_aware_datetime,
    utc_now,
    get_timezone_from_settings,
)

# Import new weather models
from ...models.weather_model import (
    OpenWeatherApiData,
    SunTimeWindow,
    WeatherDataRecord,
    WeatherConfiguration,
    WeatherApiValidationResponse,
    WeatherRefreshResult,
    WeatherApiStatus,
)

# Import weather constants
from ...constants import (
    EVENT_WEATHER_UPDATED,
    OPENWEATHER_API_BASE_URL,
    OPENWEATHER_API_TIMEOUT,
    OPENWEATHER_API_UNITS,
    WEATHER_MAX_CONSECUTIVE_FAILURES,
    WEATHER_API_KEY_VALID,
    WEATHER_API_KEY_INVALID,
    WEATHER_LOCATION_INVALID,
    WEATHER_CONNECTION_ERROR,
    WEATHER_REFRESH_SKIPPED_LOCATION,
)

# Import conversion utilities
from ...utils.conversion_utils import safe_int


class OpenWeatherService:
    """
    OpenWeather API service for weather data and sunrise/sunset calculations.

    This service provides weather information and sun-based time calculations
    for camera time windows. It fetches weather data hourly to provide current data.
    """

    BASE_URL = OPENWEATHER_API_BASE_URL

    def __init__(self, api_key: str, latitude: float, longitude: float):
        """
        Initialize OpenWeather service.

        Args:
            api_key: OpenWeather API key
            latitude: Location latitude (-90 to 90)
            longitude: Location longitude (-180 to 180)
        """
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude

    def validate_api_key(self) -> WeatherApiValidationResponse:
        """
        Validate API key by making a test request.

        Returns:
            WeatherApiValidationResponse: Validation result with status
        """
        try:
            params = {
                "lat": self.latitude,
                "lon": self.longitude,
                "appid": self.api_key,
                "units": OPENWEATHER_API_UNITS,
            }

            response = requests.get(
                self.BASE_URL, params=params, timeout=OPENWEATHER_API_TIMEOUT
            )

            if response.status_code == 200:
                return WeatherApiValidationResponse(
                    valid=True,
                    message=WEATHER_API_KEY_VALID,
                    status=WeatherApiStatus.VALID,
                )
            elif response.status_code == 401:
                return WeatherApiValidationResponse(
                    valid=False,
                    message=WEATHER_API_KEY_INVALID,
                    status=WeatherApiStatus.INVALID,
                )
            elif response.status_code == 404:
                return WeatherApiValidationResponse(
                    valid=False,
                    message=WEATHER_LOCATION_INVALID,
                    status=WeatherApiStatus.INVALID,
                )
            else:
                return WeatherApiValidationResponse(
                    valid=False,
                    message=f"API error: {response.status_code}",
                    status=WeatherApiStatus.FAILING,
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeather API validation error: {e}")
            return WeatherApiValidationResponse(
                valid=False,
                message=f"{WEATHER_CONNECTION_ERROR}: {str(e)}",
                status=WeatherApiStatus.FAILING,
            )

    def fetch_current_weather(self) -> Optional[OpenWeatherApiData]:
        """
        Fetch current weather data from OpenWeather API.

        Returns:
            Optional[OpenWeatherApiData]: Weather data or None if failed
        """
        try:
            params = {
                "lat": self.latitude,
                "lon": self.longitude,
                "appid": self.api_key,
                "units": OPENWEATHER_API_UNITS,
            }

            response = requests.get(
                self.BASE_URL, params=params, timeout=OPENWEATHER_API_TIMEOUT
            )
            response.raise_for_status()

            data = response.json()

            # Extract weather information
            weather = data["weather"][0]  # Take first weather condition
            main = data["main"]
            sys = data["sys"]

            return OpenWeatherApiData(
                temperature=round(main["temp"]),
                icon=weather["icon"],
                description=weather["description"],
                sunrise_timestamp=sys["sunrise"],
                sunset_timestamp=sys["sunset"],
                date_fetched=date.today(),
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeather API request error: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"OpenWeather API response parsing error: {e}")
            return None

    def calculate_sun_time_window(
        self,
        sunrise_timestamp: int,
        sunset_timestamp: int,
        sunrise_offset_minutes: int = 0,
        sunset_offset_minutes: int = 0,
        timezone_str: str = "UTC",
    ) -> SunTimeWindow:
        """
        Calculate time window based on sunrise/sunset with offsets.

        Args:
            sunrise_timestamp: Unix timestamp of sunrise
            sunset_timestamp: Unix timestamp of sunset
            sunrise_offset_minutes: Minutes to offset sunrise (+ = later, - = earlier)
            sunset_offset_minutes: Minutes to offset sunset (+ = later, - = earlier)
            timezone_str: Timezone for calculations (defaults to UTC)

        Returns:
            SunTimeWindow: Calculated time window
        """
        # Convert timestamps to timezone-aware datetime

        try:
            tz = ZoneInfo(timezone_str)
            sunrise_dt = datetime.fromtimestamp(sunrise_timestamp, tz=tz)
            sunset_dt = datetime.fromtimestamp(sunset_timestamp, tz=tz)
        except Exception:
            # Fallback to UTC if timezone is invalid
            tz = ZoneInfo("UTC")
            sunrise_dt = datetime.fromtimestamp(sunrise_timestamp, tz=tz)
            sunset_dt = datetime.fromtimestamp(sunset_timestamp, tz=tz)

        # Apply offsets
        start_dt = sunrise_dt + timedelta(minutes=sunrise_offset_minutes)
        end_dt = sunset_dt + timedelta(minutes=sunset_offset_minutes)

        start_time = start_dt.time()
        end_time = end_dt.time()

        # Check if window spans midnight
        is_overnight = start_time > end_time

        return SunTimeWindow(
            start_time=start_time, end_time=end_time, is_overnight=is_overnight
        )

    def is_within_sun_window(
        self,
        sunrise_timestamp: int,
        sunset_timestamp: int,
        sunrise_offset_minutes: int = 0,
        sunset_offset_minutes: int = 0,
        check_time: Optional[datetime] = None,
        timezone_str: str = "UTC",
    ) -> bool:
        """
        Check if current time (or specified time) is within sun-based window.

        Args:
            sunrise_timestamp: Unix timestamp of sunrise
            sunset_timestamp: Unix timestamp of sunset
            sunrise_offset_minutes: Minutes to offset sunrise
            sunset_offset_minutes: Minutes to offset sunset
            check_time: Time to check (defaults to now in configured timezone)
            timezone_str: Timezone for calculations (defaults to UTC)

        Returns:
            bool: True if within window
        """
        # Get current time in configured timezone if not provided
        if check_time is None:

            try:
                # Use centralized timezone utility (AI-CONTEXT compliant)
                check_time = create_timezone_aware_datetime(timezone_str)
            except Exception:
                # Fallback to centralized UTC utility (AI-CONTEXT compliant)
                check_time = utc_now()

        window = self.calculate_sun_time_window(
            sunrise_timestamp,
            sunset_timestamp,
            sunrise_offset_minutes,
            sunset_offset_minutes,
            timezone_str,
        )

        current_time = check_time.time()

        if window.is_overnight:
            # Overnight window (e.g., sunset at 18:00, sunrise at 06:00 + offsets)
            return current_time >= window.start_time or current_time <= window.end_time
        else:
            # Normal window (e.g., sunrise at 06:00, sunset at 18:00 + offsets)
            return window.start_time <= current_time <= window.end_time

    @staticmethod
    def format_time_window(window: SunTimeWindow) -> Tuple[str, str]:
        """
        Format time window for database storage.

        Args:
            window: SunTimeWindow object

        Returns:
            Tuple[str, str]: (start_time_str, end_time_str) in HH:MM:SS format
        """
        start_str = window.start_time.strftime("%H:%M:%S")
        end_str = window.end_time.strftime("%H:%M:%S")
        return start_str, end_str


class WeatherManager:
    """
    Weather manager that handles weather data coordination and caching.

    This class coordinates between the OpenWeather service and weather operations,
    handling hourly weather refresh and settings management.

    Architecture:
    - Uses dependency injection for database operations
    - Coordinates weather data fetching and storage
    - Handles API failures and error tracking
    - No direct database access (follows service layer patterns)
    """

    def __init__(self, weather_operations, settings_service=None):
        """
        Initialize weather manager with injected dependencies.

        Args:
            weather_operations: Weather database operations instance (async or sync)
            settings_service: Settings service for secure API key retrieval
        """
        self.weather_ops = weather_operations
        self.settings_service = settings_service

    async def get_weather_settings(self) -> Dict[str, Any]:
        """Get weather-related settings from database"""
        try:
            # If we have a settings service, use it for proper settings access
            if self.settings_service:
                try:

                    # Check if settings service has async or sync get_all_settings
                    get_all_method = getattr(self.settings_service, "get_all_settings")

                    if inspect.iscoroutinefunction(get_all_method):
                        # Async settings service
                        settings_dict = await self.settings_service.get_all_settings()
                    else:
                        # Sync settings service
                        settings_dict = self.settings_service.get_all_settings()

                except Exception as e:
                    logger.warning(f"Failed to get settings from settings service: {e}")
                    # Fallback to direct database access
                    return await self._get_settings_from_db()
            else:
                # No settings service, use direct database access
                return await self._get_settings_from_db()

            # Ensure settings_dict is a dictionary
            if not isinstance(settings_dict, dict):
                logger.error(
                    f"Expected dict from settings service, got {type(settings_dict)}"
                )
                return {}

            # Get API key securely through settings service if available
            api_key = ""
            if self.settings_service and hasattr(
                self.settings_service, "get_openweather_api_key"
            ):
                try:
                    # Check if the API key method is async or sync
                    api_key_method = getattr(
                        self.settings_service, "get_openweather_api_key"
                    )
                    if inspect.iscoroutinefunction(api_key_method):
                        # Async method
                        api_key = (
                            await self.settings_service.get_openweather_api_key() or ""
                        )
                    else:
                        # Sync method
                        api_key = self.settings_service.get_openweather_api_key() or ""
                except Exception as e:
                    logger.warning(f"Failed to get API key from settings service: {e}")
                    # Fallback to direct settings access
                    api_key = settings_dict.get("openweather_api_key", "")
            else:
                # Fallback to direct settings access
                api_key = settings_dict.get("openweather_api_key", "")

            return {
                "enabled": settings_dict.get("weather_enabled", "false").lower()
                == "true",
                "sunrise_sunset_enabled": settings_dict.get(
                    "sunrise_sunset_enabled", "false"
                ).lower()
                == "true",
                "api_key": api_key,
                "latitude": (
                    float(settings_dict.get("latitude", "0"))
                    if settings_dict.get("latitude")
                    else None
                ),
                "longitude": (
                    float(settings_dict.get("longitude", "0"))
                    if settings_dict.get("longitude")
                    else None
                ),
                "sunrise_offset_minutes": safe_int(
                    settings_dict.get("sunrise_offset_minutes", "0"), 0
                ),
                "sunset_offset_minutes": safe_int(
                    settings_dict.get("sunset_offset_minutes", "0"), 0
                ),
                "current_temp": safe_int(settings_dict.get("current_temp", ""), None),
                "current_weather_icon": settings_dict.get("current_weather_icon", ""),
                "current_weather_description": settings_dict.get(
                    "current_weather_description", ""
                ),
                "weather_date_fetched": settings_dict.get("weather_date_fetched", ""),
                "sunrise_timestamp": safe_int(
                    settings_dict.get("sunrise_timestamp", ""), None
                ),
                "sunset_timestamp": safe_int(
                    settings_dict.get("sunset_timestamp", ""), None
                ),
            }
        except Exception as e:
            logger.error(f"Failed to get weather settings: {e}")
            return {}

    async def update_weather_cache(self, weather_data: OpenWeatherApiData) -> bool:
        """Update cached weather data in weather table"""
        try:
            # Get timezone setting for proper timestamp
            if self.settings_service:
                try:
                    get_all_method = getattr(self.settings_service, "get_all_settings")
                    if inspect.iscoroutinefunction(get_all_method):
                        settings_dict = await self.settings_service.get_all_settings()
                    else:
                        settings_dict = self.settings_service.get_all_settings()
                except Exception as e:
                    logger.warning(f"Failed to get timezone from settings service: {e}")
                    settings_dict = await self._get_settings_from_db()
            else:
                settings_dict = await self._get_settings_from_db()

            # Get timezone and create timezone-aware timestamp
            timezone_str = get_timezone_from_settings(settings_dict)

            # Convert weather data for weather table storage
            # Use current timestamp in configured timezone to show when data was actually fetched
            weather_date_fetched = create_timezone_aware_datetime(timezone_str)
            sunrise_timestamp = (
                datetime.fromtimestamp(weather_data.sunrise_timestamp)
                if weather_data.sunrise_timestamp
                else None
            )
            sunset_timestamp = (
                datetime.fromtimestamp(weather_data.sunset_timestamp)
                if weather_data.sunset_timestamp
                else None
            )

            # Use injected weather operations
            if hasattr(self.weather_ops, "insert_weather_data"):
                # Check if it's async method
                if inspect.iscoroutinefunction(self.weather_ops.insert_weather_data):
                    weather_id = await self.weather_ops.insert_weather_data(
                        weather_date_fetched=weather_date_fetched,
                        current_temp=float(weather_data.temperature),
                        current_weather_icon=weather_data.icon,
                        current_weather_description=weather_data.description,
                        sunrise_timestamp=sunrise_timestamp,
                        sunset_timestamp=sunset_timestamp,
                        api_key_valid=True,
                        api_failing=False,
                    )
                else:
                    # Sync method
                    weather_id = self.weather_ops.insert_weather_data(
                        weather_date_fetched=weather_date_fetched,
                        current_temp=float(weather_data.temperature),
                        current_weather_icon=weather_data.icon,
                        current_weather_description=weather_data.description,
                        sunrise_timestamp=sunrise_timestamp,
                        sunset_timestamp=sunset_timestamp,
                        api_key_valid=True,
                        api_failing=False,
                    )
            else:
                raise AttributeError(
                    "Weather operations instance missing insert_weather_data method"
                )

            # Check if weather data was successfully inserted
            if not weather_id:
                raise Exception(
                    "Failed to insert weather data - no ID returned from database operation"
                )

            logger.info(
                f"Updated weather cache in weather table (ID: {weather_id}): {weather_data.temperature}°C, {weather_data.description}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update weather cache: {e}")
            return False

    async def record_weather_failure(
        self, error_code: Optional[int] = None, error_message: Optional[str] = None
    ) -> bool:
        """Record weather API failure in weather table"""
        try:
            # Use injected weather operations
            if hasattr(self.weather_ops, "update_weather_failure"):
                # Check if it's async method
                if inspect.iscoroutinefunction(self.weather_ops.update_weather_failure):
                    await self.weather_ops.update_weather_failure(
                        error_response_code=error_code, last_error_message=error_message
                    )
                else:
                    # Sync method
                    self.weather_ops.update_weather_failure(
                        error_response_code=error_code, last_error_message=error_message
                    )
            else:
                raise AttributeError(
                    "Weather operations instance missing update_weather_failure method"
                )

            logger.warning(
                f"Recorded weather API failure: {error_code} - {error_message}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to record weather failure: {e}")
            return False

    async def refresh_weather_if_needed(
        self, api_key: str, force: bool = False
    ) -> Optional[OpenWeatherApiData]:
        """
        Refresh weather data if it's stale (not from today) or force refresh.

        Args:
            api_key: Decrypted OpenWeather API key
            force: Force refresh even if data is current

        Returns:
            Optional[OpenWeatherApiData]: Current weather data or None if failed
        """
        try:
            settings = await self.get_weather_settings()

            # Check if we have location configured
            if not settings.get("latitude") or not settings.get("longitude"):
                logger.warning(WEATHER_REFRESH_SKIPPED_LOCATION)
                return None

            # Check if weather data is from today by checking weather_data table
            # Use injected weather operations
            if hasattr(self.weather_ops, "get_latest_weather"):
                # Check if it's async method
                if inspect.iscoroutinefunction(self.weather_ops.get_latest_weather):
                    latest_weather = await self.weather_ops.get_latest_weather()
                else:
                    # Sync method
                    latest_weather = self.weather_ops.get_latest_weather()
            else:
                raise AttributeError(
                    "Weather operations instance missing get_latest_weather method"
                )

            # Get today's date in timezone
            if self.settings_service:
                try:
                    get_all_method = getattr(self.settings_service, "get_all_settings")
                    if inspect.iscoroutinefunction(get_all_method):
                        settings_dict = await self.settings_service.get_all_settings()
                    else:
                        settings_dict = self.settings_service.get_all_settings()
                except Exception as e:
                    logger.warning(f"Failed to get timezone from settings service: {e}")
                    settings_dict = await self._get_settings_from_db()
            else:
                settings_dict = await self._get_settings_from_db()

            # Get today's date in the configured timezone
            timezone_str = get_timezone_from_settings(settings_dict)
            try:

                tz = ZoneInfo(timezone_str)
                today = datetime.now(tz).date().isoformat()
            except Exception as e:
                logger.warning(f"Failed to get timezone aware date: {e}")
                today = datetime.now().date().isoformat()

            # Check if we have current weather data
            if latest_weather and latest_weather.get("weather_date_fetched"):
                weather_date = latest_weather["weather_date_fetched"]
                if isinstance(weather_date, datetime):
                    weather_date_str = weather_date.date().isoformat()
                else:
                    weather_date_str = str(weather_date)

                if weather_date_str == today and not force:
                    # Data is current and not forcing refresh, return cached data
                    if all(
                        latest_weather.get(key)
                        for key in [
                            "current_temp",
                            "current_weather_icon",
                            "sunrise_timestamp",
                            "sunset_timestamp",
                        ]
                    ):
                        sunrise_ts = latest_weather["sunrise_timestamp"]
                        sunset_ts = latest_weather["sunset_timestamp"]

                        # Convert datetime objects to timestamps if needed
                        sunrise_timestamp = (
                            int(sunrise_ts.timestamp())
                            if isinstance(sunrise_ts, datetime)
                            else int(sunrise_ts)
                        )
                        sunset_timestamp = (
                            int(sunset_ts.timestamp())
                            if isinstance(sunset_ts, datetime)
                            else int(sunset_ts)
                        )

                        return OpenWeatherApiData(
                            temperature=int(latest_weather["current_temp"]),
                            icon=latest_weather["current_weather_icon"],
                            description=latest_weather["current_weather_description"]
                            or "",
                            sunrise_timestamp=sunrise_timestamp,
                            sunset_timestamp=sunset_timestamp,
                            date_fetched=date.today(),
                        )

            # Data is stale or missing, fetch new data
            service = OpenWeatherService(
                api_key=api_key,
                latitude=settings["latitude"],
                longitude=settings["longitude"],
            )

            weather_data = service.fetch_current_weather()
            if weather_data:
                await self.update_weather_cache(weather_data)
                return weather_data
            else:
                logger.error("Failed to fetch weather data from OpenWeather API")
                await self.record_weather_failure(
                    error_message="Failed to fetch weather data from OpenWeather API"
                )
                return None

        except Exception as e:
            logger.error(f"Error refreshing weather data: {e}")
            await self.record_weather_failure(error_message=str(e))
            return None

    async def get_current_sun_window(self) -> Optional[SunTimeWindow]:
        """
        Get current sun-based time window.

        Returns:
            Optional[SunTimeWindow]: Current time window or None if not configured
        """
        try:
            settings = await self.get_weather_settings()

            if not settings.get("sunrise_sunset_enabled"):
                return None

            if not settings.get("sunrise_timestamp") or not settings.get(
                "sunset_timestamp"
            ):
                logger.warning(
                    "Sun window requested but sunrise/sunset data not available"
                )
                return None

            service = OpenWeatherService(
                api_key="dummy",  # Not needed for time calculations
                latitude=0,
                longitude=0,
            )

            # Get timezone setting for calculations
            if self.settings_service:
                try:
                    get_all_method = getattr(self.settings_service, "get_all_settings")
                    if inspect.iscoroutinefunction(get_all_method):
                        settings_dict = await self.settings_service.get_all_settings()
                    else:
                        settings_dict = self.settings_service.get_all_settings()
                except Exception as e:
                    logger.warning(f"Failed to get timezone from settings service: {e}")
                    settings_dict = await self._get_settings_from_db()
            else:
                settings_dict = await self._get_settings_from_db()

            timezone_str = settings_dict.get("timezone", "UTC")

            return service.calculate_sun_time_window(
                sunrise_timestamp=settings["sunrise_timestamp"],
                sunset_timestamp=settings["sunset_timestamp"],
                sunrise_offset_minutes=settings.get("sunrise_offset_minutes", 0),
                sunset_offset_minutes=settings.get("sunset_offset_minutes", 0),
                timezone_str=timezone_str,
            )

        except Exception as e:
            logger.error(f"Error calculating sun window: {e}")
            return None

    async def _get_settings_from_db(self) -> Dict[str, Any]:
        """Fallback method to get settings directly from database"""
        try:
            # If we have a settings service, use it as fallback
            if self.settings_service:
                get_all_method = getattr(self.settings_service, "get_all_settings")
                if inspect.iscoroutinefunction(get_all_method):
                    return await self.settings_service.get_all_settings()
                else:
                    return self.settings_service.get_all_settings()
            else:
                logger.error(
                    "No settings service available for fallback settings access"
                )
                return {}

        except Exception as e:
            logger.error(f"Failed to get settings from database: {e}")
            return {}

    async def get_weather_data_for_settings(
        self, settings_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get weather data formatted for settings response.

        Args:
            settings_dict: Current settings dictionary to enhance

        Returns:
            Enhanced settings dictionary with weather data
        """
        # Get latest weather data from weather table
        weather_data = self.weather_ops.get_latest_weather()

        if weather_data:
            # Convert weather timestamp to configured timezone for display
            weather_date_fetched = weather_data.get("weather_date_fetched")
            if weather_date_fetched:

                # Get configured timezone
                timezone_str = get_timezone_from_settings(settings_dict)

                # Convert UTC timestamp to configured timezone
                try:
                    if isinstance(weather_date_fetched, str):
                        # Parse string to datetime if needed

                        weather_date_fetched = datetime.fromisoformat(
                            weather_date_fetched.replace("Z", "+00:00")
                        )

                    # Convert to configured timezone
                    tz = ZoneInfo(timezone_str)
                    local_time = weather_date_fetched.astimezone(tz)
                    settings_dict["weather_date_fetched"] = local_time.isoformat()
                except Exception as e:
                    logger.warning(
                        f"Failed to convert weather timestamp to timezone {timezone_str}: {e}"
                    )
                    # Fallback to original timestamp with safe conversion
                    settings_dict["weather_date_fetched"] = str(weather_date_fetched)
            else:
                settings_dict["weather_date_fetched"] = ""

            # Add other weather data to settings dict for backward compatibility
            settings_dict["current_temp"] = (
                str(weather_data.get("current_temp", ""))
                if weather_data.get("current_temp") is not None
                else ""
            )
            settings_dict["current_weather_icon"] = weather_data.get(
                "current_weather_icon", ""
            )
            settings_dict["current_weather_description"] = weather_data.get(
                "current_weather_description", ""
            )
            sunrise_ts = weather_data.get("sunrise_timestamp")
            settings_dict["sunrise_timestamp"] = (
                sunrise_ts.isoformat()
                if sunrise_ts and hasattr(sunrise_ts, "isoformat")
                else str(sunrise_ts) if sunrise_ts else ""
            )

            sunset_ts = weather_data.get("sunset_timestamp")
            settings_dict["sunset_timestamp"] = (
                sunset_ts.isoformat()
                if sunset_ts and hasattr(sunset_ts, "isoformat")
                else str(sunset_ts) if sunset_ts else ""
            )

        return settings_dict

    async def manual_weather_refresh(self) -> WeatherRefreshResult:
        """
        Perform manual weather data refresh with comprehensive error handling.

        Returns:
            WeatherRefreshResult with success status and data
        """
        # Get weather settings
        settings_dict = await self.get_weather_settings()

        # Check if weather is enabled
        weather_enabled = (
            settings_dict.get("weather_enabled", "false").lower() == "true"
        )
        if not weather_enabled:
            return WeatherRefreshResult(
                success=False,
                message="Weather integration is disabled",
                weather_data=None,
                error_code=None,
            )

        # Check required settings
        latitude = settings_dict.get("latitude")
        longitude = settings_dict.get("longitude")

        # Get API key securely through settings service
        api_key = None
        if self.settings_service:
            api_key = await self.settings_service.get_openweather_api_key()

        if not all([latitude, longitude, api_key]):
            return WeatherRefreshResult(
                success=False,
                message="Missing required weather settings (latitude, longitude, or API key)",
                error_code=None,
                weather_data=None,
            )

        # Convert to float with error handling
        try:
            if latitude is None or longitude is None:
                raise ValueError("Latitude or longitude is None")
            lat_float = float(latitude)
            lon_float = float(longitude)
        except (ValueError, TypeError) as e:
            return WeatherRefreshResult(
                success=False,
                message=f"Invalid latitude or longitude values: {e}",
                weather_data=None,
                error_code=None,
            )

        try:
            masked_api_key = (
                f"***{api_key[-4:]}" if api_key and len(api_key) > 4 else "***"
            )
            logger.info(
                f"Attempting manual weather refresh with API key: {masked_api_key}"
            )
            logger.info(f"Latitude: {latitude}, Longitude: {longitude}")

            # Create OpenWeather service directly for testing
            ow_service = OpenWeatherService(api_key or "", lat_float, lon_float)

            # Test API connection
            logger.info("Testing OpenWeather API connection...")
            weather_data = ow_service.fetch_current_weather()
            logger.info(f"Direct API call result: {weather_data is not None}")

            if weather_data:
                # Try to save to database using weather manager
                logger.info("Attempting to save weather data...")
                cache_success = await self.update_weather_cache(weather_data)
                logger.info(f"Cache update success: {cache_success}")

                # Create SSE event for manual weather refresh
                await self._create_weather_update_sse_event(weather_data, "api")

                return WeatherRefreshResult(
                    success=True,
                    error_code=None,
                    weather_data=weather_data,
                    message="Weather data refreshed successfully",
                )
            else:
                return WeatherRefreshResult(
                    success=False,
                    message="Failed to refresh weather data",
                    weather_data=None,
                    error_code=None,
                )

        except Exception as e:

            logger.error(f"Weather refresh error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return WeatherRefreshResult(
                success=False,
                message=f"Weather refresh failed: {str(e)}",
                weather_data=None,
                error_code=None,
            )

    async def _create_weather_update_sse_event(
        self, weather_data: OpenWeatherApiData, source: str = "worker"
    ):
        """
        Create SSE event for weather updates.

        Args:
            weather_data: Weather data to broadcast
            source: Source of the update (worker, api, etc.)
        """
        try:

            sse_ops = SyncSSEEventsOperations(sync_db)
            event_id = sse_ops.create_event(
                EVENT_WEATHER_UPDATED,
                {
                    "temperature": weather_data.temperature,
                    "icon": weather_data.icon,
                    "description": weather_data.description,
                    "date_fetched": (
                        weather_data.date_fetched.isoformat()
                        if hasattr(weather_data.date_fetched, "isoformat")
                        else str(weather_data.date_fetched)
                    ),
                },
                SSEPriority.NORMAL,
                source,  # Source is passed parameter
            )
            logger.info(f"Created weather update SSE event with ID: {event_id}")
        except Exception as e:
            logger.error(f"Failed to create weather update SSE event: {e}")
