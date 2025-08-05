"""
Typed response models for weather worker operations.

These models replace defensive dictionary access with type-safe attributes,
eliminating the need for .get() calls and providing compile-time safety.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class WeatherData:
    """Current weather data information."""

    temperature: Optional[float] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    date_fetched: Optional[datetime] = None
    sunrise_timestamp: Optional[datetime] = None
    sunset_timestamp: Optional[datetime] = None
    api_key_valid: bool = True
    api_failing: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeatherData":
        """Create WeatherData instance from dictionary."""
        return cls(
            temperature=data.get("current_temp"),
            icon=data.get("current_weather_icon"),
            description=data.get("current_weather_description"),
            date_fetched=data.get("weather_date_fetched"),
            sunrise_timestamp=data.get("sunrise_timestamp"),
            sunset_timestamp=data.get("sunset_timestamp"),
            api_key_valid=data.get("api_key_valid", True),
            api_failing=data.get("api_failing", False),
        )


@dataclass
class WeatherStatus:
    """Weather status information for API responses."""

    temperature: Optional[float] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    date_fetched: Optional[datetime] = None
    sunrise_timestamp: Optional[datetime] = None
    sunset_timestamp: Optional[datetime] = None
    api_key_valid: bool = True
    api_failing: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeatherStatus":
        """Create WeatherStatus instance from dictionary."""
        return cls(
            temperature=data.get("temperature"),
            icon=data.get("icon"),
            description=data.get("description"),
            date_fetched=data.get("date_fetched"),
            sunrise_timestamp=data.get("sunrise_timestamp"),
            sunset_timestamp=data.get("sunset_timestamp"),
            api_key_valid=data.get("api_key_valid", True),
            api_failing=data.get("api_failing", False),
        )


@dataclass
class WeatherHealthStatus:
    """Weather service health status."""

    weather_enabled: bool
    api_key_configured: bool
    location_configured: bool
    data_current: bool
    api_failing: bool
    last_update: Optional[datetime] = None
    errors: Optional[List[str]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeatherHealthStatus":
        """Create WeatherHealthStatus instance from dictionary."""
        return cls(
            weather_enabled=data.get("weather_enabled", False),
            api_key_configured=data.get("api_key_configured", False),
            location_configured=data.get("location_configured", False),
            data_current=data.get("data_current", False),
            api_failing=data.get("api_failing", True),
            last_update=data.get("last_update"),
            errors=data.get("errors", []),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if weather service is healthy."""
        return (
            self.weather_enabled
            and self.api_key_configured
            and self.location_configured
            and not self.api_failing
            and len(self.errors or []) == 0
        )

    @property
    def is_configured(self) -> bool:
        """Check if weather service is properly configured."""
        return self.api_key_configured and self.location_configured


@dataclass
class WeatherSettings:
    """Weather configuration settings."""

    weather_enabled: bool
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    api_key_configured: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeatherSettings":
        """Create WeatherSettings instance from dictionary."""
        return cls(
            weather_enabled=data.get("weather_enabled", False),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            api_key_configured=bool(data.get("api_key_configured", False)),
        )

    @property
    def is_location_configured(self) -> bool:
        """Check if location is properly configured."""
        return bool(self.latitude and self.longitude)

    @property
    def is_fully_configured(self) -> bool:
        """Check if weather is fully configured."""
        return (
            self.weather_enabled
            and self.api_key_configured
            and self.is_location_configured
        )


@dataclass
class WeatherWorkerStatus:
    """Comprehensive weather worker status."""

    worker_type: str
    weather_manager_status: str
    api_key_configured: bool
    location_configured: bool
    weather_enabled: bool
    data_current: bool
    api_failing: bool
    last_successful_update: Optional[datetime] = None
    current_temperature: Optional[float] = None
    current_description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeatherWorkerStatus":
        """Create WeatherWorkerStatus from dictionary for backward compatibility."""
        return cls(
            worker_type=data.get("worker_type", ""),
            weather_manager_status=data.get("weather_manager_status", ""),
            api_key_configured=data.get("api_key_configured", False),
            location_configured=data.get("location_configured", False),
            weather_enabled=data.get("weather_enabled", False),
            data_current=data.get("data_current", False),
            api_failing=data.get("api_failing", False),
            last_successful_update=data.get("last_successful_update"),
            current_temperature=data.get("current_temperature"),
            current_description=data.get("current_description"),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if weather worker is healthy."""
        return (
            self.weather_manager_status == "healthy"
            and self.weather_enabled
            and self.api_key_configured
            and self.location_configured
            and not self.api_failing
        )

    @property
    def is_configured(self) -> bool:
        """Check if weather service is properly configured."""
        return self.api_key_configured and self.location_configured

    @property
    def has_recent_data(self) -> bool:
        """Check if weather data is recent (within last hour)."""
        if not self.last_successful_update:
            return False
        from datetime import timedelta
        from ...utils.time_utils import utc_now

        return (utc_now() - self.last_successful_update) < timedelta(hours=1)
