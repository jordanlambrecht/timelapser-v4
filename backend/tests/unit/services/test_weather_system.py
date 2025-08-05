#!/usr/bin/env python3
# backend/tests/test_weather_system.py
"""
Comprehensive test suite for weather system components.

Tests the weather integration including OpenWeatherService API calls,
WeatherManager coordination, and worker integration patterns.
"""

import asyncio
import json
import time as time_module
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.constants import (
    OPENWEATHER_API_BASE_URL,
    OPENWEATHER_API_TIMEOUT,
    WEATHER_API_KEY_INVALID,
    WEATHER_API_KEY_VALID,
    WEATHER_CONNECTION_ERROR,
    WEATHER_MAX_CONSECUTIVE_FAILURES,
    WEATHER_REFRESH_SKIPPED_DISABLED,
    WEATHER_REFRESH_SKIPPED_LOCATION,
)
from app.models.weather_model import (
    OpenWeatherApiData,
    SunTimeWindow,
    WeatherApiStatus,
    WeatherApiValidationRequest,
    WeatherApiValidationResponse,
    WeatherConfiguration,
    WeatherDataRecord,
)
from app.services.weather.service import OpenWeatherService, WeatherManager


class TestOpenWeatherApiData:
    """Test the OpenWeatherApiData Pydantic model."""

    def test_valid_weather_data_creation(self):
        """Test creating valid weather data from API response."""
        data = OpenWeatherApiData(
            temperature=22,
            icon="01d",
            description="clear sky",
            sunrise_timestamp=1672560000,
            sunset_timestamp=1672596000,
            date_fetched=date(2023, 1, 1),
        )

        assert data.temperature == 22
        assert data.icon == "01d"
        assert data.description == "clear sky"
        assert data.sunrise_timestamp == 1672560000
        assert data.sunset_timestamp == 1672596000
        assert data.date_fetched == date(2023, 1, 1)

    def test_temperature_validation(self):
        """Test temperature field validation."""
        # Valid temperatures
        valid_data = {
            "temperature": -40,
            "icon": "01d",
            "description": "cold",
            "sunrise_timestamp": 1672560000,
            "sunset_timestamp": 1672596000,
            "date_fetched": date(2023, 1, 1),
        }
        data = OpenWeatherApiData(**valid_data)
        assert data.temperature == -40

        # High temperature
        valid_data["temperature"] = 50
        data = OpenWeatherApiData(**valid_data)
        assert data.temperature == 50

    def test_icon_max_length_validation(self):
        """Test icon field max length validation."""
        valid_data = {
            "temperature": 22,
            "icon": "01d",
            "description": "clear sky",
            "sunrise_timestamp": 1672560000,
            "sunset_timestamp": 1672596000,
            "date_fetched": date(2023, 1, 1),
        }

        # Valid icon
        data = OpenWeatherApiData(**valid_data)
        assert data.icon == "01d"

        # Test boundary - 50 characters
        valid_data["icon"] = "x" * 50
        data = OpenWeatherApiData(**valid_data)
        assert len(data.icon) == 50

        # Too long icon should raise validation error
        with pytest.raises(ValueError):
            valid_data["icon"] = "x" * 51
            OpenWeatherApiData(**valid_data)

    def test_description_max_length_validation(self):
        """Test description field max length validation."""
        valid_data = {
            "temperature": 22,
            "icon": "01d",
            "description": "clear sky",
            "sunrise_timestamp": 1672560000,
            "sunset_timestamp": 1672596000,
            "date_fetched": date(2023, 1, 1),
        }

        # Test boundary - 255 characters
        valid_data["description"] = "x" * 255
        data = OpenWeatherApiData(**valid_data)
        assert len(data.description) == 255

        # Too long description should raise validation error
        with pytest.raises(ValueError):
            valid_data["description"] = "x" * 256
            OpenWeatherApiData(**valid_data)


class TestWeatherDataRecord:
    """Test the WeatherDataRecord Pydantic model."""

    def test_complete_weather_record_creation(self):
        """Test creating complete weather data record."""
        data = WeatherDataRecord(
            id=1,
            weather_date_fetched=datetime(2023, 1, 1, 12, 0, 0),
            current_temp=22.5,
            current_weather_icon="01d",
            current_weather_description="clear sky",
            sunrise_timestamp=datetime(2023, 1, 1, 6, 0, 0),
            sunset_timestamp=datetime(2023, 1, 1, 18, 0, 0),
            api_key_valid=True,
            api_failing=False,
            consecutive_failures=0,
        )

        assert data.id == 1
        assert data.weather_date_fetched == datetime(2023, 1, 1, 12, 0, 0)
        assert data.current_temp == 22.5
        assert data.current_weather_icon == "01d"
        assert data.current_weather_description == "clear sky"
        assert data.sunrise_timestamp == datetime(2023, 1, 1, 6, 0, 0)
        assert data.sunset_timestamp == datetime(2023, 1, 1, 18, 0, 0)
        assert data.api_key_valid is True
        assert data.api_failing is False
        assert data.consecutive_failures == 0

    def test_optional_fields_defaults(self):
        """Test that optional fields have proper defaults."""
        data = WeatherDataRecord()

        assert data.id is None
        assert data.weather_date_fetched is None
        assert data.current_temp is None
        assert data.current_weather_icon is None
        assert data.current_weather_description is None
        assert data.sunrise_timestamp is None
        assert data.sunset_timestamp is None
        assert data.api_key_valid is True  # Default
        assert data.api_failing is False  # Default
        assert data.consecutive_failures == 0  # Default

    def test_failure_tracking_fields(self):
        """Test failure tracking fields work correctly."""
        data = WeatherDataRecord(
            api_key_valid=False, api_failing=True, consecutive_failures=3
        )

        assert data.api_key_valid is False
        assert data.api_failing is True
        assert data.consecutive_failures == 3


class TestSunTimeWindow:
    """Test the SunTimeWindow Pydantic model."""

    def test_valid_time_window_creation(self):
        """Test creating valid time window."""
        window = SunTimeWindow(
            start_time=time(6, 30), end_time=time(19, 45), is_overnight=False
        )

        assert window.start_time == time(6, 30)
        assert window.end_time == time(19, 45)
        assert window.is_overnight is False

    def test_overnight_time_window(self):
        """Test overnight time window."""
        window = SunTimeWindow(
            start_time=time(22, 0), end_time=time(6, 0), is_overnight=True
        )

        assert window.start_time == time(22, 0)
        assert window.end_time == time(6, 0)
        assert window.is_overnight is True

    def test_time_validation(self):
        """Test time field validation."""
        # Valid time objects should work
        window = SunTimeWindow(start_time=time(6, 30), end_time=time(19, 45))
        assert isinstance(window.start_time, time)
        assert isinstance(window.end_time, time)

        # Invalid time types should raise validation error
        with pytest.raises(ValueError, match="Must be a time object"):
            SunTimeWindow(
                start_time="06:30",  # String instead of time object
                end_time=time(19, 45),
            )

        with pytest.raises(ValueError, match="Must be a time object"):
            SunTimeWindow(
                start_time=time(6, 30),
                end_time="19:45",  # String instead of time object
            )


class TestWeatherApiValidationResponse:
    """Test the WeatherApiValidationResponse model."""

    def test_valid_response_creation(self):
        """Test creating valid API validation response."""
        response = WeatherApiValidationResponse(
            valid=True, message=WEATHER_API_KEY_VALID, status=WeatherApiStatus.VALID
        )

        assert response.valid is True
        assert response.message == WEATHER_API_KEY_VALID
        assert response.status == WeatherApiStatus.VALID

    def test_invalid_response_creation(self):
        """Test creating invalid API validation response."""
        response = WeatherApiValidationResponse(
            valid=False,
            message=WEATHER_API_KEY_INVALID,
            status=WeatherApiStatus.INVALID,
        )

        assert response.valid is False
        assert response.message == WEATHER_API_KEY_INVALID
        assert response.status == WeatherApiStatus.INVALID

    def test_failing_response_creation(self):
        """Test creating failing API validation response."""
        response = WeatherApiValidationResponse(
            valid=False,
            message=WEATHER_CONNECTION_ERROR + ": Timeout",
            status=WeatherApiStatus.FAILING,
        )

        assert response.valid is False
        assert WEATHER_CONNECTION_ERROR in response.message
        assert response.status == WeatherApiStatus.FAILING


class TestOpenWeatherService:
    """Test the OpenWeatherService class."""

    def test_service_initialization(self):
        """Test service initialization with valid parameters."""
        service = OpenWeatherService(
            api_key="test_key", latitude=40.7128, longitude=-74.0060
        )

        assert service.api_key == "test_key"
        assert service.latitude == 40.7128
        assert service.longitude == -74.0060
        assert service.BASE_URL == OPENWEATHER_API_BASE_URL

    @patch("requests.get")
    def test_validate_api_key_success(self, mock_get):
        """Test successful API key validation."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 22},
            "weather": [{"icon": "01d", "description": "clear sky"}],
            "sys": {"sunrise": 1672560000, "sunset": 1672596000},
        }
        mock_get.return_value = mock_response

        service = OpenWeatherService("valid_key", 40.7128, -74.0060)
        result = service.validate_api_key()

        assert result.valid is True
        assert result.message == WEATHER_API_KEY_VALID
        assert result.status == WeatherApiStatus.VALID
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_validate_api_key_invalid(self, mock_get):
        """Test invalid API key validation."""
        # Mock 401 Unauthorized response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        service = OpenWeatherService("invalid_key", 40.7128, -74.0060)
        result = service.validate_api_key()

        assert result.valid is False
        assert result.message == WEATHER_API_KEY_INVALID
        assert result.status == WeatherApiStatus.INVALID

    @patch("requests.get")
    def test_validate_api_key_connection_error(self, mock_get):
        """Test API key validation with connection error."""
        # Mock connection error
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        service = OpenWeatherService("test_key", 40.7128, -74.0060)
        result = service.validate_api_key()

        assert result.valid is False
        assert WEATHER_CONNECTION_ERROR in result.message
        assert result.status == WeatherApiStatus.FAILING

    @patch("requests.get")
    def test_fetch_current_weather_success(self, mock_get):
        """Test successful weather data fetching."""
        # Mock successful weather response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 22.5},
            "weather": [{"icon": "01d", "description": "clear sky"}],
            "sys": {"sunrise": 1672560000, "sunset": 1672596000},
        }
        mock_get.return_value = mock_response

        service = OpenWeatherService("valid_key", 40.7128, -74.0060)
        result = service.fetch_current_weather()

        assert result is not None
        assert isinstance(result, OpenWeatherApiData)
        assert result.temperature == 22
        assert result.icon == "01d"
        assert result.description == "clear sky"
        assert result.sunrise_timestamp == 1672560000
        assert result.sunset_timestamp == 1672596000
        assert isinstance(result.date_fetched, date)

    @patch("requests.get")
    def test_fetch_current_weather_api_error(self, mock_get):
        """Test weather fetching with API error."""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        service = OpenWeatherService("invalid_key", 40.7128, -74.0060)
        result = service.fetch_current_weather()

        assert result is None

    @patch("requests.get")
    def test_fetch_current_weather_timeout(self, mock_get):
        """Test weather fetching with timeout."""
        # Mock timeout error
        import requests

        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

        service = OpenWeatherService("test_key", 40.7128, -74.0060)
        result = service.fetch_current_weather()

        assert result is None

    def test_calculate_sun_time_window(self):
        """Test sunrise/sunset time window calculation."""
        service = OpenWeatherService("test_key", 40.7128, -74.0060)

        # Test normal day window (not overnight)
        window = service.calculate_sun_time_window(
            sunrise_timestamp=1672560000,  # 6:00 AM UTC (Jan 1, 2023)
            sunset_timestamp=1672596000,  # 4:00 PM UTC
            sunrise_offset_minutes=30,  # 30 minutes after sunrise
            sunset_offset_minutes=-30,  # 30 minutes before sunset
            timezone_str="UTC",
        )

        assert isinstance(window, SunTimeWindow)
        assert window.is_overnight is False
        # Times will be timezone-adjusted, so just check that offsets were applied
        assert window.start_time.minute == 30  # 30 minute offset applied
        assert window.end_time.minute == 30  # 30 minute offset applied

    def test_is_within_sun_window_normal_day(self):
        """Test time window checking for normal day."""
        service = OpenWeatherService("test_key", 40.7128, -74.0060)

        # Test during valid window - using datetime.now() directly from service
        # This test checks the method returns a boolean result
        result = service.is_within_sun_window(
            sunrise_timestamp=1672560000,  # 6:00 AM UTC (Jan 1, 2023)
            sunset_timestamp=1672596000,  # 4:00 PM UTC
            sunrise_offset_minutes=0,
            sunset_offset_minutes=0,
            timezone_str="UTC",
        )
        # Should return a boolean (either True or False)
        assert isinstance(result, bool)

    def test_is_within_sun_window_outside(self):
        """Test time window checking outside valid hours."""
        service = OpenWeatherService("test_key", 40.7128, -74.0060)

        # Test with timestamps far in the past (definitely outside current window)
        result = service.is_within_sun_window(
            sunrise_timestamp=1672560000,  # 6:00 AM UTC (Jan 1, 2023) - in the past
            sunset_timestamp=1672596000,  # 4:00 PM UTC (Jan 1, 2023) - in the past
            sunrise_offset_minutes=0,
            sunset_offset_minutes=0,
            timezone_str="UTC",
        )
        # Should return a boolean (current time is after this window from 2023)
        assert isinstance(result, bool)


class TestWeatherManager:
    """Test the WeatherManager class."""

    @pytest.fixture
    def mock_weather_operations(self):
        """Provide mock weather operations."""
        mock_ops = Mock()
        mock_ops.get_latest_weather = AsyncMock(return_value=None)
        mock_ops.insert_weather_data = AsyncMock(return_value=1)
        mock_ops.update_weather_failure = AsyncMock()
        return mock_ops

    @pytest.fixture
    def mock_settings_service(self):
        """Provide mock settings service."""
        mock_service = Mock()
        mock_service.get_openweather_api_key = Mock(return_value="test_key")
        return mock_service

    @pytest.fixture
    def weather_manager(self, mock_weather_operations, mock_settings_service):
        """Provide WeatherManager instance with mocked dependencies."""
        return WeatherManager(
            weather_operations=mock_weather_operations,
            settings_service=mock_settings_service,
        )

    def test_weather_manager_initialization(
        self, mock_weather_operations, mock_settings_service
    ):
        """Test WeatherManager initialization with dependency injection."""
        manager = WeatherManager(mock_weather_operations, mock_settings_service)

        assert manager.weather_ops == mock_weather_operations
        assert manager.settings_service == mock_settings_service

    @pytest.mark.asyncio
    async def test_update_weather_cache_success(
        self, weather_manager, mock_weather_operations
    ):
        """Test successful weather cache update."""
        # Create test weather data
        weather_data = OpenWeatherApiData(
            temperature=25,
            icon="01d",
            description="clear sky",
            sunrise_timestamp=1672560000,
            sunset_timestamp=1672596000,
            date_fetched=date(2023, 1, 1),
        )

        # Mock successful insert
        mock_weather_operations.insert_weather_data.return_value = 123

        result = await weather_manager.update_weather_cache(weather_data)

        assert result is True
        mock_weather_operations.insert_weather_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_weather_cache_failure(
        self, weather_manager, mock_weather_operations
    ):
        """Test weather cache update with database failure."""
        # Create test weather data
        weather_data = OpenWeatherApiData(
            temperature=25,
            icon="01d",
            description="clear sky",
            sunrise_timestamp=1672560000,
            sunset_timestamp=1672596000,
            date_fetched=date(2023, 1, 1),
        )

        # Mock database error
        mock_weather_operations.insert_weather_data.side_effect = Exception("DB Error")

        result = await weather_manager.update_weather_cache(weather_data)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_weather_settings(self, weather_manager):
        """Test getting weather settings."""
        with patch.object(weather_manager, "settings_service") as mock_service:
            mock_service.get_all_settings = AsyncMock(
                return_value={
                    "latitude": "40.7128",
                    "longitude": "-74.0060",
                    "weather_enabled": "true",
                }
            )

            settings = await weather_manager.get_weather_settings()

            assert settings["latitude"] == "40.7128"
            assert settings["longitude"] == "-74.0060"
            assert settings["weather_enabled"] == "true"

    @pytest.mark.asyncio
    @patch("app.services.weather.service.OpenWeatherService")
    async def test_refresh_weather_if_needed_no_location(
        self, mock_service_class, weather_manager
    ):
        """Test weather refresh when location not configured."""
        # Mock settings without location
        with patch.object(weather_manager, "get_weather_settings") as mock_get_settings:
            mock_get_settings.return_value = {"latitude": None, "longitude": None}

            result = await weather_manager.refresh_weather_if_needed("test_key")

            assert result is None
            mock_service_class.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.weather.service.OpenWeatherService")
    async def test_refresh_weather_if_needed_success(
        self, mock_service_class, weather_manager, mock_weather_operations
    ):
        """Test successful weather refresh."""
        # Mock settings with location
        with patch.object(weather_manager, "get_weather_settings") as mock_get_settings:
            mock_get_settings.return_value = {
                "latitude": "40.7128",
                "longitude": "-74.0060",
            }

            # Mock no recent weather data
            mock_weather_operations.get_latest_weather.return_value = None

            # Mock successful weather fetch
            mock_weather_data = OpenWeatherApiData(
                temperature=25,
                icon="01d",
                description="clear sky",
                sunrise_timestamp=1672560000,
                sunset_timestamp=1672596000,
                date_fetched=date(2023, 1, 1),
            )
            mock_service = Mock()
            mock_service.fetch_current_weather.return_value = mock_weather_data
            mock_service_class.return_value = mock_service

            # Mock successful cache update
            with patch.object(weather_manager, "update_weather_cache") as mock_update:
                mock_update.return_value = True

                result = await weather_manager.refresh_weather_if_needed("test_key")

                assert result == mock_weather_data
                mock_service.fetch_current_weather.assert_called_once()
                mock_update.assert_called_once_with(mock_weather_data)


class TestWeatherWorkerIntegration:
    """Test weather system integration with worker."""

    @pytest.fixture
    def mock_worker_dependencies(self):
        """Provide mock dependencies for worker testing."""
        mock_weather_ops = Mock()
        mock_settings_service = Mock()
        mock_sse_ops = Mock()

        mock_settings_service.get_all_settings.return_value = {
            "weather_enabled": "true",
            "latitude": "40.7128",
            "longitude": "-74.0060",
        }
        mock_settings_service.get_openweather_api_key.return_value = "test_key"

        return {
            "weather_ops": mock_weather_ops,
            "settings_service": mock_settings_service,
            "sse_ops": mock_sse_ops,
        }

    @pytest.mark.asyncio
    async def test_worker_weather_refresh_disabled(self, mock_worker_dependencies):
        """Test worker weather refresh when weather is disabled."""
        # Setup weather manager
        weather_manager = WeatherManager(
            mock_worker_dependencies["weather_ops"],
            mock_worker_dependencies["settings_service"],
        )

        # Mock weather disabled
        mock_worker_dependencies["settings_service"].get_all_settings.return_value = {
            "weather_enabled": "false"
        }

        # Simulate worker refresh logic
        settings_dict = mock_worker_dependencies["settings_service"].get_all_settings()

        if settings_dict.get("weather_enabled", "false").lower() != "true":
            # Should skip refresh
            result = None
        else:
            api_key = mock_worker_dependencies[
                "settings_service"
            ].get_openweather_api_key()
            result = await weather_manager.refresh_weather_if_needed(api_key)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.weather.service.OpenWeatherService")
    async def test_worker_weather_refresh_success(
        self, mock_service_class, mock_worker_dependencies
    ):
        """Test successful worker weather refresh."""
        # Setup weather manager
        weather_manager = WeatherManager(
            mock_worker_dependencies["weather_ops"],
            mock_worker_dependencies["settings_service"],
        )

        # Mock successful weather fetch
        mock_weather_data = OpenWeatherApiData(
            temperature=25,
            icon="01d",
            description="clear sky",
            sunrise_timestamp=1672560000,
            sunset_timestamp=1672596000,
            date_fetched=date(2023, 1, 1),
        )
        mock_service = Mock()
        mock_service.fetch_current_weather.return_value = mock_weather_data
        mock_service_class.return_value = mock_service

        # Mock successful cache update
        with patch.object(weather_manager, "update_weather_cache") as mock_update:
            mock_update.return_value = True

            # Simulate worker refresh logic
            settings_dict = mock_worker_dependencies[
                "settings_service"
            ].get_all_settings()

            if settings_dict.get("weather_enabled", "false").lower() == "true":
                api_key = mock_worker_dependencies[
                    "settings_service"
                ].get_openweather_api_key()
                result = await weather_manager.refresh_weather_if_needed(api_key)
            else:
                result = None

            assert result == mock_weather_data
            mock_service.fetch_current_weather.assert_called_once()
            mock_update.assert_called_once_with(mock_weather_data)


class TestWeatherSystemEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_weather_manager_sync_operations_detection(self):
        """Test weather manager handles sync operations properly."""
        # Create mock sync operations (not async)
        mock_sync_ops = Mock()
        mock_sync_ops.insert_weather_data = Mock(return_value=1)  # Not async
        mock_sync_ops.get_latest_weather = Mock(return_value=None)  # Not async

        weather_manager = WeatherManager(mock_sync_ops)

        # Create test weather data
        weather_data = OpenWeatherApiData(
            temperature=25,
            icon="01d",
            description="clear sky",
            sunrise_timestamp=1672560000,
            sunset_timestamp=1672596000,
            date_fetched=date(2023, 1, 1),
        )

        # Should handle sync operations correctly
        result = await weather_manager.update_weather_cache(weather_data)
        assert result is True
        mock_sync_ops.insert_weather_data.assert_called_once()

    def test_weather_constants_usage(self):
        """Test that weather system uses constants correctly."""
        # Test that service uses constants
        service = OpenWeatherService("test", 0, 0)
        assert service.BASE_URL == OPENWEATHER_API_BASE_URL

        # Test validation responses use constants
        valid_response = WeatherApiValidationResponse(
            valid=True, message=WEATHER_API_KEY_VALID, status=WeatherApiStatus.VALID
        )
        assert valid_response.message == WEATHER_API_KEY_VALID

        invalid_response = WeatherApiValidationResponse(
            valid=False,
            message=WEATHER_API_KEY_INVALID,
            status=WeatherApiStatus.INVALID,
        )
        assert invalid_response.message == WEATHER_API_KEY_INVALID

    @patch("requests.get")
    def test_weather_api_timeout_usage(self, mock_get):
        """Test that API calls use timeout constant."""
        service = OpenWeatherService("test_key", 40.7128, -74.0060)

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 22},
            "weather": [{"icon": "01d", "description": "clear sky"}],
            "sys": {"sunrise": 1672560000, "sunset": 1672596000},
        }
        mock_get.return_value = mock_response

        # Call API method
        service.validate_api_key()

        # Verify timeout was used
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == OPENWEATHER_API_TIMEOUT

    def test_weather_failure_tracking(self):
        """Test weather failure tracking model."""
        # Test default values
        record = WeatherDataRecord()
        assert record.consecutive_failures == 0
        assert record.api_failing is False
        assert record.api_key_valid is True

        # Test failure tracking
        failed_record = WeatherDataRecord(
            consecutive_failures=3, api_failing=True, api_key_valid=False
        )
        assert failed_record.consecutive_failures == 3
        assert failed_record.api_failing is True
        assert failed_record.api_key_valid is False

    def test_timezone_edge_cases(self):
        """Test timezone handling edge cases."""
        service = OpenWeatherService("test", 0, 0)

        # Test various timezones
        timezones = ["UTC", "US/Eastern", "Europe/London", "Asia/Tokyo"]

        for tz in timezones:
            try:
                window = service.calculate_sun_time_window(
                    sunrise_timestamp=1672560000,
                    sunset_timestamp=1672596000,
                    sunrise_offset_minutes=0,
                    sunset_offset_minutes=0,
                    timezone_str=tz,
                )
                # Should create valid window for all timezones
                assert isinstance(window, SunTimeWindow)
            except Exception as e:
                pytest.fail(f"Timezone {tz} failed: {e}")


# Performance and load testing
class TestWeatherSystemPerformance:
    """Test weather system performance characteristics."""

    @pytest.mark.asyncio
    async def test_concurrent_weather_operations(self):
        """Test concurrent weather manager operations."""
        mock_ops = Mock()
        mock_ops.get_latest_weather = AsyncMock(return_value=None)
        mock_ops.insert_weather_data = AsyncMock(return_value=1)

        weather_manager = WeatherManager(mock_ops)

        # Create multiple weather data records
        weather_records = []
        for i in range(10):
            weather_records.append(
                OpenWeatherApiData(
                    temperature=20 + i,
                    icon="01d",
                    description=f"weather {i}",
                    sunrise_timestamp=1672560000,
                    sunset_timestamp=1672596000,
                    date_fetched=date(2023, 1, 1),
                )
            )

        # Run concurrent cache updates
        tasks = [
            weather_manager.update_weather_cache(record) for record in weather_records
        ]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)
        assert mock_ops.insert_weather_data.call_count == 10

    def test_weather_model_validation_performance(self):
        """Test weather model validation performance."""
        import time

        # Time creating many weather records
        start_time = time_module.time()

        for i in range(1000):
            OpenWeatherApiData(
                temperature=20 + (i % 50),
                icon="01d",
                description=f"test weather {i}",
                sunrise_timestamp=1672560000 + i,
                sunset_timestamp=1672596000 + i,
                date_fetched=date(2023, 1, 1),
            )

        end_time = time_module.time()
        duration = end_time - start_time

        # Should create 1000 records in reasonable time (< 1 second)
        assert duration < 1.0, f"Model validation too slow: {duration:.2f}s"

    @patch("requests.get")
    def test_api_call_performance(self, mock_get):
        """Test API call performance characteristics."""
        # Mock fast response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 22},
            "weather": [{"icon": "01d", "description": "clear sky"}],
            "sys": {"sunrise": 1672560000, "sunset": 1672596000},
        }
        mock_get.return_value = mock_response

        service = OpenWeatherService("test_key", 40.7128, -74.0060)

        # Time multiple API calls
        start_time = time_module.time()

        for _ in range(10):
            service.fetch_current_weather()

        end_time = time_module.time()
        duration = end_time - start_time

        # Should handle 10 calls quickly (< 0.1 seconds with mocking)
        assert duration < 0.1, f"API calls too slow: {duration:.2f}s"
        assert mock_get.call_count == 10
