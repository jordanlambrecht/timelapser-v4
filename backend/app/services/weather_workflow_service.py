# backend/app/services/weather_workflow_service.py
"""
Weather workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for weather operations.
Converts raw data to typed objects at the service boundary.
"""

from typing import Any, Dict, Optional

from ..constants import (
    BOOLEAN_TRUE_STRING,
    DEFAULT_WEATHER_ENABLED,
    SETTING_KEY_WEATHER_ENABLED,
)
from ..enums import LoggerName, LogSource, WorkerType
from ..models.health_model import HealthStatus
from ..services.logger import get_service_logger
from ..workers.models.weather_responses import (
    WeatherHealthStatus,
    WeatherSettings,
    WeatherStatus,
    WeatherWorkerStatus,
)

weather_service_logger = get_service_logger(LoggerName.WEATHER_WORKER, LogSource.WORKER)


class WeatherWorkflowService:
    """
    Service layer for weather operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern.
    """

    def __init__(self):
        """Initialize weather workflow service."""
        pass

    def get_weather_settings(self, settings_dict: Dict[str, Any]) -> WeatherSettings:
        """
        Convert raw settings dictionary to typed WeatherSettings at service boundary.

        Args:
            settings_dict: Raw settings dictionary from settings service

        Returns:
            WeatherSettings: Typed settings object for clean worker access
        """
        # Service guarantees these keys exist, no defensive .get() calls needed
        return WeatherSettings.from_dict(
            {
                "weather_enabled": (
                    settings_dict.get(
                        SETTING_KEY_WEATHER_ENABLED, DEFAULT_WEATHER_ENABLED
                    ).lower()
                    == BOOLEAN_TRUE_STRING
                ),
                "latitude": settings_dict.get("latitude"),
                "longitude": settings_dict.get("longitude"),
                "api_key_configured": True,  # Will be validated separately
            }
        )

    def get_worker_status(
        self,
        weather_manager: Any,
        health_status: Optional[WeatherHealthStatus],
        current_weather: Optional[WeatherStatus],
    ) -> WeatherWorkerStatus:
        """
        Convert raw service status to typed WeatherWorkerStatus at service boundary.

        Args:
            weather_manager: Weather manager instance
            health_status: Current health status (typed object)
            current_weather: Current weather data (typed object)

        Returns:
            WeatherWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status using .value for explicit access
        manager_status = (
            HealthStatus.HEALTHY.value
            if weather_manager
            else HealthStatus.UNREACHABLE.value
        )

        # Extract data from typed objects (no .get() calls needed)
        api_key_configured = (
            health_status.api_key_configured if health_status else False
        )
        location_configured = (
            health_status.location_configured if health_status else False
        )
        weather_enabled = health_status.weather_enabled if health_status else False
        data_current = health_status.data_current if health_status else False
        api_failing = health_status.api_failing if health_status else True
        last_update = health_status.last_update if health_status else None

        # Extract current weather data
        current_temp = current_weather.temperature if current_weather else None
        current_desc = current_weather.description if current_weather else None

        # Return typed object at service boundary
        return WeatherWorkerStatus(
            worker_type=WorkerType.WEATHER_WORKER.value,
            weather_manager_status=manager_status,
            api_key_configured=api_key_configured,
            location_configured=location_configured,
            weather_enabled=weather_enabled,
            data_current=data_current,
            api_failing=api_failing,
            last_successful_update=last_update,
            current_temperature=current_temp,
            current_description=current_desc,
        )
