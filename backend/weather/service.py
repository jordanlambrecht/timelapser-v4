"""
OpenWeather API Service for Timelapser v4

This module provides weather data integration using the OpenWeather API.
It handles:
- Daily weather data caching
- Sunrise/sunset time calculation
- API key validation
- Time window calculations with sun-based offsets

Features:
- Automatic daily refresh of weather data
- Configurable location via lat/lng
- Sunrise/sunset time calculation with custom offsets
- Temperature and weather condition tracking
- Graceful error handling and fallbacks

Authors: Timelapser Development Team
Version: 4.0
License: Private
"""

import requests
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from loguru import logger
import json
from dataclasses import dataclass


@dataclass
class WeatherData:
    """Weather data container"""

    temperature: int
    icon: str
    description: str
    sunrise_timestamp: int
    sunset_timestamp: int
    date_fetched: date


@dataclass
class TimeWindow:
    """Time window container for sun-based capture limits"""

    start_time: time
    end_time: time
    is_overnight: bool


class OpenWeatherService:
    """
    OpenWeather API service for weather data and sunrise/sunset calculations.

    This service provides weather information and sun-based time calculations
    for camera time windows. It caches weather data daily to minimize API calls.
    """

    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

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

    def validate_api_key(self) -> Tuple[bool, str]:
        """
        Validate API key by making a test request.

        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            params = {
                "lat": self.latitude,
                "lon": self.longitude,
                "appid": self.api_key,
                "units": "metric",
            }

            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code == 200:
                return True, "API key is valid"
            elif response.status_code == 401:
                return False, "Invalid API key"
            elif response.status_code == 404:
                return False, "Invalid location coordinates"
            else:
                return False, f"API error: {response.status_code}"

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeather API validation error: {e}")
            return False, f"Connection error: {str(e)}"

    def fetch_current_weather(self) -> Optional[WeatherData]:
        """
        Fetch current weather data from OpenWeather API.

        Returns:
            Optional[WeatherData]: Weather data or None if failed
        """
        try:
            params = {
                "lat": self.latitude,
                "lon": self.longitude,
                "appid": self.api_key,
                "units": "metric",
            }

            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Extract weather information
            weather = data["weather"][0]  # Take first weather condition
            main = data["main"]
            sys = data["sys"]

            return WeatherData(
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
    ) -> TimeWindow:
        """
        Calculate time window based on sunrise/sunset with offsets.

        Args:
            sunrise_timestamp: Unix timestamp of sunrise
            sunset_timestamp: Unix timestamp of sunset
            sunrise_offset_minutes: Minutes to offset sunrise (+ = later, - = earlier)
            sunset_offset_minutes: Minutes to offset sunset (+ = later, - = earlier)

        Returns:
            TimeWindow: Calculated time window
        """
        # Convert timestamps to local time
        sunrise_dt = datetime.fromtimestamp(sunrise_timestamp)
        sunset_dt = datetime.fromtimestamp(sunset_timestamp)

        # Apply offsets
        start_dt = sunrise_dt + timedelta(minutes=sunrise_offset_minutes)
        end_dt = sunset_dt + timedelta(minutes=sunset_offset_minutes)

        start_time = start_dt.time()
        end_time = end_dt.time()

        # Check if window spans midnight
        is_overnight = start_time > end_time

        return TimeWindow(
            start_time=start_time, end_time=end_time, is_overnight=is_overnight
        )

    def is_within_sun_window(
        self,
        sunrise_timestamp: int,
        sunset_timestamp: int,
        sunrise_offset_minutes: int = 0,
        sunset_offset_minutes: int = 0,
        check_time: Optional[datetime] = None,
    ) -> bool:
        """
        Check if current time (or specified time) is within sun-based window.

        Args:
            sunrise_timestamp: Unix timestamp of sunrise
            sunset_timestamp: Unix timestamp of sunset
            sunrise_offset_minutes: Minutes to offset sunrise
            sunset_offset_minutes: Minutes to offset sunset
            check_time: Time to check (defaults to now)

        Returns:
            bool: True if within window
        """
        if check_time is None:
            check_time = datetime.now()

        window = self.calculate_sun_time_window(
            sunrise_timestamp,
            sunset_timestamp,
            sunrise_offset_minutes,
            sunset_offset_minutes,
        )

        current_time = check_time.time()

        if window.is_overnight:
            # Overnight window (e.g., sunset at 18:00, sunrise at 06:00 + offsets)
            return current_time >= window.start_time or current_time <= window.end_time
        else:
            # Normal window (e.g., sunrise at 06:00, sunset at 18:00 + offsets)
            return window.start_time <= current_time <= window.end_time

    @staticmethod
    def format_time_window(window: TimeWindow) -> Tuple[str, str]:
        """
        Format time window for database storage.

        Args:
            window: TimeWindow object

        Returns:
            Tuple[str, str]: (start_time_str, end_time_str) in HH:MM:SS format
        """
        start_str = window.start_time.strftime("%H:%M:%S")
        end_str = window.end_time.strftime("%H:%M:%S")
        return start_str, end_str


class WeatherManager:
    """
    Weather manager that handles database integration and caching.

    This class coordinates between the OpenWeather service and the database,
    handling daily weather refresh and settings management.

    NOTE: This service correctly uses the key-value settings table structure.
    Settings are stored as rows (key, value) pairs, NOT as individual columns.
    This is the proper database design pattern for flexible configuration.
    """

    def __init__(self, db_instance):
        """
        Initialize weather manager.

        Args:
            db_instance: Database instance (sync or async)
        """
        self.db = db_instance

    async def get_weather_settings(self) -> Dict[str, Any]:
        """Get weather-related settings from database"""
        try:
            # Defensive check to ensure we have a proper database instance
            if not hasattr(self.db, "get_settings_dict"):
                logger.error("Database instance does not have get_settings_dict method")
                return {}

            # Try to determine if this is an async database by checking the method
            import inspect

            get_settings_method = getattr(self.db, "get_settings_dict")

            if inspect.iscoroutinefunction(get_settings_method):
                # Async database method
                settings_dict = await self.db.get_settings_dict()
            else:
                # Sync database method
                settings_dict = self.db.get_settings_dict()

            # Ensure settings_dict is a dictionary
            if not isinstance(settings_dict, dict):
                logger.error(
                    f"Expected dict from get_settings_dict, got {type(settings_dict)}"
                )
                return {}

            return {
                "enabled": settings_dict.get("weather_enabled", "false").lower()
                == "true",
                "sunrise_sunset_enabled": settings_dict.get(
                    "sunrise_sunset_enabled", "false"
                ).lower()
                == "true",
                "api_key": settings_dict.get("openweather_api_key", ""),
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
                "sunrise_offset_minutes": int(
                    settings_dict.get("sunrise_offset_minutes", "0")
                ),
                "sunset_offset_minutes": int(
                    settings_dict.get("sunset_offset_minutes", "0")
                ),
                "current_temp": (
                    int(settings_dict.get("current_temp", "0"))
                    if settings_dict.get("current_temp")
                    else None
                ),
                "current_weather_icon": settings_dict.get("current_weather_icon", ""),
                "current_weather_description": settings_dict.get(
                    "current_weather_description", ""
                ),
                "weather_date_fetched": settings_dict.get("weather_date_fetched", ""),
                "sunrise_timestamp": (
                    int(settings_dict.get("sunrise_timestamp", "0"))
                    if settings_dict.get("sunrise_timestamp")
                    else None
                ),
                "sunset_timestamp": (
                    int(settings_dict.get("sunset_timestamp", "0"))
                    if settings_dict.get("sunset_timestamp")
                    else None
                ),
            }
        except Exception as e:
            logger.error(f"Failed to get weather settings: {e}")
            return {}

    async def update_weather_cache(self, weather_data: WeatherData) -> bool:
        """Update cached weather data in database"""
        try:
            # Defensive check to ensure we have a proper database instance
            if not hasattr(self.db, "create_or_update_setting"):
                logger.error(
                    "Database instance does not have create_or_update_setting method"
                )
                return False

            updates = [
                ("current_temp", str(weather_data.temperature)),
                ("current_weather_icon", weather_data.icon),
                ("current_weather_description", weather_data.description),
                ("weather_date_fetched", weather_data.date_fetched.isoformat()),
                ("sunrise_timestamp", str(weather_data.sunrise_timestamp)),
                ("sunset_timestamp", str(weather_data.sunset_timestamp)),
            ]

            # Try to determine if this is an async database by checking the method
            import inspect

            create_or_update_method = getattr(self.db, "create_or_update_setting")

            for key, value in updates:
                if inspect.iscoroutinefunction(create_or_update_method):
                    # Async database method
                    await self.db.create_or_update_setting(key, value)
                else:
                    # Sync database method
                    self.db.create_or_update_setting(key, value)

            logger.info(
                f"Updated weather cache: {weather_data.temperature}°C, {weather_data.description}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update weather cache: {e}")
            return False

    async def refresh_weather_if_needed(self, api_key: str) -> Optional[WeatherData]:
        """
        Refresh weather data if it's stale (not from today).

        Args:
            api_key: Decrypted OpenWeather API key

        Returns:
            Optional[WeatherData]: Current weather data or None if failed
        """
        try:
            settings = await self.get_weather_settings()

            # Check if we have location configured
            if not settings.get("latitude") or not settings.get("longitude"):
                logger.warning("Weather refresh skipped: Location not configured")
                return None

            # Check if weather data is from today
            today = date.today().isoformat()
            if settings.get("weather_date_fetched") == today:
                # Data is current, return cached data
                if all(
                    settings.get(key)
                    for key in [
                        "current_temp",
                        "current_weather_icon",
                        "sunrise_timestamp",
                        "sunset_timestamp",
                    ]
                ):
                    return WeatherData(
                        temperature=settings["current_temp"],
                        icon=settings["current_weather_icon"],
                        description=settings["current_weather_description"],
                        sunrise_timestamp=settings["sunrise_timestamp"],
                        sunset_timestamp=settings["sunset_timestamp"],
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
                return None

        except Exception as e:
            logger.error(f"Error refreshing weather data: {e}")
            return None

    async def get_current_sun_window(self) -> Optional[TimeWindow]:
        """
        Get current sun-based time window.

        Returns:
            Optional[TimeWindow]: Current time window or None if not configured
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

            return service.calculate_sun_time_window(
                sunrise_timestamp=settings["sunrise_timestamp"],
                sunset_timestamp=settings["sunset_timestamp"],
                sunrise_offset_minutes=settings.get("sunrise_offset_minutes", 0),
                sunset_offset_minutes=settings.get("sunset_offset_minutes", 0),
            )

        except Exception as e:
            logger.error(f"Error calculating sun window: {e}")
            return None
