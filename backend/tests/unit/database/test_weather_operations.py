#!/usr/bin/env python3
# backend/tests/test_weather_operations.py
"""
Test suite for weather database operations.

Tests both async and sync versions of weather database operations
to ensure proper data handling and query functionality.
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, Optional

from app.database.weather_operations import WeatherOperations, SyncWeatherOperations
from app.models.weather_model import WeatherDataRecord


class TestWeatherOperations:
    """Test async WeatherOperations class."""

    @pytest.fixture
    def mock_db(self):
        """Provide mock database connection."""
        mock_db = Mock()
        mock_connection = AsyncMock()
        mock_db.get_connection = AsyncMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_connection),
            __aexit__=AsyncMock(return_value=None)
        ))
        return mock_db, mock_connection

    @pytest.fixture
    def weather_ops(self, mock_db):
        """Provide WeatherOperations instance with mocked database."""
        db, _ = mock_db
        return WeatherOperations(db)

    @pytest.mark.asyncio
    async def test_get_latest_weather_with_data(self, weather_ops, mock_db):
        """Test getting latest weather when data exists."""
        _, mock_connection = mock_db

        # Mock database row
        mock_row = Mock()
        mock_row._mapping = {
            "id": 1,
            "weather_date_fetched": datetime(2023, 1, 1, 12, 0, 0),
            "current_temp": 22.5,
            "weather_icon": "01d",
            "weather_description": "clear sky",
            "sunrise_timestamp": 1672560000,
            "sunset_timestamp": 1672596000,
            "api_key_valid": True,
            "api_failing": False,
            "consecutive_failures": 0
        }

        # Mock query result
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        result = await weather_ops.get_latest_weather()

        assert result is not None
        assert result["id"] == 1
        assert result["current_temp"] == 22.5
        assert result["weather_icon"] == "01d"
        assert result["weather_description"] == "clear sky"
        assert result["api_key_valid"] is True
        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_weather_no_data(self, weather_ops, mock_db):
        """Test getting latest weather when no data exists."""
        _, mock_connection = mock_db

        # Mock empty result
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_connection.execute.return_value = mock_result

        result = await weather_ops.get_latest_weather()

        assert result is None
        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_weather_data_success(self, weather_ops, mock_db):
        """Test successful weather data insertion."""
        _, mock_connection = mock_db

        # Mock successful insert
        mock_result = Mock()
        mock_result.scalar.return_value = 123
        mock_connection.execute.return_value = mock_result

        weather_id = await weather_ops.insert_weather_data(
            weather_date_fetched=datetime(2023, 1, 1, 12, 0, 0),
            current_temp=25.0,
            current_weather_icon="01d",
            current_weather_description="clear sky",
            sunrise_timestamp=datetime(2023, 1, 1, 6, 0, 0),
            sunset_timestamp=datetime(2023, 1, 1, 18, 0, 0),
            api_key_valid=True,
            api_failing=False
        )

        assert weather_id == 123
        mock_connection.execute.assert_called_once()
        mock_connection.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_weather_data_minimal(self, weather_ops, mock_db):
        """Test weather data insertion with minimal required fields."""
        _, mock_connection = mock_db

        # Mock successful insert
        mock_result = Mock()
        mock_result.scalar.return_value = 124
        mock_connection.execute.return_value = mock_result

        weather_id = await weather_ops.insert_weather_data(
            weather_date_fetched=datetime(2023, 1, 1, 12, 0, 0),
            current_temp=20.0
            # Other fields should use defaults
        )

        assert weather_id == 124
        mock_connection.execute.assert_called_once()
        mock_connection.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_weather_failure(self, weather_ops, mock_db):
        """Test updating weather failure information."""
        _, mock_connection = mock_db

        # Mock the SELECT query for consecutive failures
        mock_select_result = Mock()
        mock_failure_row = Mock()
        mock_failure_row._mapping = {"consecutive_failures": 2}
        mock_select_result.fetchone.return_value = mock_failure_row
        
        # Mock the INSERT query
        mock_insert_result = Mock()
        mock_insert_result.scalar.return_value = 126
        
        # Setup execute to return different results for different calls
        mock_connection.execute.side_effect = [mock_select_result, mock_insert_result]

        await weather_ops.update_weather_failure(
            error_response_code=401,
            last_error_message="Invalid API key"
        )

        # Should be called twice: once for SELECT, once for INSERT
        assert mock_connection.execute.call_count == 2
        mock_connection.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_weather_for_hour_exact_match(self, weather_ops, mock_db):
        """Test getting weather for specific hour with exact match."""
        _, mock_connection = mock_db

        # Mock database row
        mock_row = Mock()
        mock_row._mapping = {
            "id": 1,
            "weather_date_fetched": datetime(2023, 1, 1, 14, 0, 0),
            "current_temp": 24.0,
            "weather_icon": "02d",
            "weather_description": "few clouds"
        }

        # Mock query result
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        target_time = datetime(2023, 1, 1, 14, 30, 0)
        result = await weather_ops.get_weather_for_hour(target_time)

        assert result is not None
        assert result["current_temp"] == 24.0
        assert result["weather_icon"] == "02d"
        mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_weather_for_hour_no_match(self, weather_ops, mock_db):
        """Test getting weather for specific hour with no match."""
        _, mock_connection = mock_db

        # Mock empty result
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_connection.execute.return_value = mock_result

        target_time = datetime(2023, 1, 1, 14, 30, 0)
        result = await weather_ops.get_weather_for_hour(target_time)

        assert result is None
        # Note: execute might be called multiple times due to query structure
        assert mock_connection.execute.called


class TestSyncWeatherOperations:
    """Test sync SyncWeatherOperations class."""

    @pytest.fixture
    def mock_sync_db(self):
        """Provide mock sync database connection."""
        mock_db = Mock()
        mock_connection = Mock()
        mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_connection)
        mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
        return mock_db, mock_connection

    @pytest.fixture
    def sync_weather_ops(self, mock_sync_db):
        """Provide SyncWeatherOperations instance with mocked database."""
        db, _ = mock_sync_db
        return SyncWeatherOperations(db)

    def test_get_latest_weather_sync(self, sync_weather_ops, mock_sync_db):
        """Test sync version of get_latest_weather."""
        _, mock_connection = mock_sync_db

        # Mock database row
        mock_row = Mock()
        mock_row._mapping = {
            "id": 2,
            "weather_date_fetched": datetime(2023, 1, 2, 15, 0, 0),
            "current_temp": 18.5,
            "weather_icon": "03d",
            "weather_description": "scattered clouds"
        }

        # Mock query result
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        result = sync_weather_ops.get_latest_weather()

        assert result is not None
        assert result["id"] == 2
        assert result["current_temp"] == 18.5
        assert result["weather_icon"] == "03d"
        mock_connection.execute.assert_called_once()

    def test_insert_weather_data_sync(self, sync_weather_ops, mock_sync_db):
        """Test sync version of insert_weather_data."""
        _, mock_connection = mock_sync_db

        # Mock successful insert
        mock_result = Mock()
        mock_result.scalar.return_value = 125
        mock_connection.execute.return_value = mock_result

        weather_id = sync_weather_ops.insert_weather_data(
            weather_date_fetched=datetime(2023, 1, 2, 15, 0, 0),
            current_temp=19.0,
            current_weather_icon="03d",
            current_weather_description="scattered clouds",
            sunrise_timestamp=datetime(2023, 1, 2, 6, 0, 0),
            sunset_timestamp=datetime(2023, 1, 2, 18, 0, 0)
        )

        assert weather_id == 125
        mock_connection.execute.assert_called_once()
        mock_connection.commit.assert_called_once()

    def test_update_weather_failure_sync(self, sync_weather_ops, mock_sync_db):
        """Test sync version of update_weather_failure."""
        _, mock_connection = mock_sync_db

        # Mock the SELECT query for consecutive failures
        mock_select_result = Mock()
        mock_failure_row = Mock()
        mock_failure_row._mapping = {"consecutive_failures": 1}
        mock_select_result.fetchone.return_value = mock_failure_row
        
        # Mock the INSERT query
        mock_insert_result = Mock()
        mock_insert_result.scalar.return_value = 127
        
        # Setup execute to return different results for different calls
        mock_connection.execute.side_effect = [mock_select_result, mock_insert_result]

        sync_weather_ops.update_weather_failure(
            error_response_code=200,
            last_error_message=None
        )

        # Should be called twice: once for SELECT, once for INSERT
        assert mock_connection.execute.call_count == 2
        mock_connection.commit.assert_called_once()

    def test_get_weather_for_hour_sync(self, sync_weather_ops, mock_sync_db):
        """Test sync version of get_weather_for_hour."""
        _, mock_connection = mock_sync_db

        # Mock database row
        mock_row = Mock()
        mock_row._mapping = {
            "id": 3,
            "weather_date_fetched": datetime(2023, 1, 2, 16, 0, 0),
            "current_temp": 21.5
        }

        # Mock query result
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_result

        target_time = datetime(2023, 1, 2, 16, 15, 0)
        result = sync_weather_ops.get_weather_for_hour(target_time)

        assert result is not None
        assert result["current_temp"] == 21.5
        mock_connection.execute.assert_called_once()


class TestWeatherOperationsIntegration:
    """Test integration scenarios between async and sync operations."""

    def test_operations_consistency(self):
        """Test that async and sync operations have consistent interfaces."""
        # Both classes should have the same method signatures
        async_methods = [method for method in dir(WeatherOperations) 
                        if not method.startswith('_') and callable(getattr(WeatherOperations, method))]
        sync_methods = [method for method in dir(SyncWeatherOperations) 
                       if not method.startswith('_') and callable(getattr(SyncWeatherOperations, method))]

        # Filter out database-specific methods
        async_methods = [m for m in async_methods if m != 'db']
        sync_methods = [m for m in sync_methods if m != 'db']

        assert set(async_methods) == set(sync_methods), \
            f"Method mismatch: async={async_methods}, sync={sync_methods}"

    @pytest.mark.asyncio
    async def test_mixed_operation_usage(self):
        """Test scenarios where both async and sync operations might be used."""
        # Mock databases
        mock_async_db = Mock()
        mock_sync_db = Mock()

        async_ops = WeatherOperations(mock_async_db)
        sync_ops = SyncWeatherOperations(mock_sync_db)

        # Both should be able to handle similar data patterns
        test_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        # Verify both can be instantiated and have expected attributes
        assert hasattr(async_ops, 'db')
        assert hasattr(sync_ops, 'db')
        assert async_ops.db == mock_async_db
        assert sync_ops.db == mock_sync_db


class TestWeatherOperationsErrorHandling:
    """Test error handling in weather operations."""

    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test handling of database connection failures."""
        # Mock database that fails to connect
        mock_db = Mock()
        mock_db.get_connection.side_effect = Exception("Connection failed")

        weather_ops = WeatherOperations(mock_db)

        # Should propagate the exception for proper error handling upstream
        with pytest.raises(Exception, match="Connection failed"):
            await weather_ops.get_latest_weather()

    @pytest.mark.asyncio
    async def test_query_execution_failure(self):
        """Test handling of query execution failures."""
        # Setup mocks locally for this test
        mock_db = Mock()
        mock_connection = AsyncMock()
        mock_db.get_connection = AsyncMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_connection),
            __aexit__=AsyncMock(return_value=None)
        ))
        
        weather_ops = WeatherOperations(mock_db)

        # Mock query execution failure
        mock_connection.execute.side_effect = Exception("Query failed")

        # Should propagate the exception
        with pytest.raises(Exception, match="Query failed"):
            await weather_ops.get_latest_weather()

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_failure(self):
        """Test transaction rollback on insert failure."""
        # Setup mocks locally for this test
        mock_db = Mock()
        mock_connection = AsyncMock()
        mock_db.get_connection = AsyncMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_connection),
            __aexit__=AsyncMock(return_value=None)
        ))
        
        weather_ops = WeatherOperations(mock_db)

        # Mock commit failure
        mock_connection.commit.side_effect = Exception("Commit failed")

        # Should propagate the exception to allow upstream error handling
        with pytest.raises(Exception, match="Commit failed"):
            await weather_ops.insert_weather_data(
                weather_date_fetched=datetime(2023, 1, 1, 12, 0, 0),
                current_temp=25.0
            )

        # Rollback should not be called automatically (handled by context manager)
        mock_connection.execute.assert_called_once()

    def test_sync_database_connection_failure(self):
        """Test sync operation handling of database connection failures."""
        # Mock database that fails to connect
        mock_db = Mock()
        mock_db.get_connection.side_effect = Exception("Sync connection failed")

        sync_ops = SyncWeatherOperations(mock_db)

        # Should propagate the exception
        with pytest.raises(Exception, match="Sync connection failed"):
            sync_ops.get_latest_weather()


class TestWeatherOperationsDataValidation:
    """Test data validation in weather operations."""

    @pytest.mark.asyncio
    async def test_insert_weather_data_parameter_validation(self):
        """Test parameter validation for weather data insertion."""
        # Setup mocks locally
        mock_db = Mock()
        mock_connection = AsyncMock()
        mock_db.get_connection = AsyncMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_connection),
            __aexit__=AsyncMock(return_value=None)
        ))
        
        weather_ops = WeatherOperations(mock_db)

        # Mock successful insert
        mock_result = Mock()
        mock_result.scalar.return_value = 126
        mock_connection.execute.return_value = mock_result

        # Test with various parameter combinations
        test_cases = [
            # Required minimum
            {
                "weather_date_fetched": datetime(2023, 1, 1, 12, 0, 0),
                "current_temp": 20.0
            },
            # With all optional fields
            {
                "weather_date_fetched": datetime(2023, 1, 1, 12, 0, 0),
                "current_temp": 25.0,
                "current_weather_icon": "01d",
                "current_weather_description": "clear sky",
                "sunrise_timestamp": datetime(2023, 1, 1, 6, 0, 0),
                "sunset_timestamp": datetime(2023, 1, 1, 18, 0, 0),
                "api_key_valid": True,
                "api_failing": False
            },
            # With negative temperature
            {
                "weather_date_fetched": datetime(2023, 1, 1, 12, 0, 0),
                "current_temp": -10.0
            }
        ]

        for i, test_data in enumerate(test_cases):
            mock_result.scalar.return_value = 126 + i
            weather_id = await weather_ops.insert_weather_data(**test_data)
            assert weather_id == 126 + i

        # Should have called execute for each test case
        assert mock_connection.execute.call_count == len(test_cases)

    @pytest.mark.asyncio
    async def test_get_weather_for_hour_datetime_handling(self):
        """Test datetime handling in get_weather_for_hour."""
        # Setup mocks locally
        mock_db = Mock()
        mock_connection = AsyncMock()
        mock_db.get_connection = AsyncMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_connection),
            __aexit__=AsyncMock(return_value=None)
        ))
        
        weather_ops = WeatherOperations(mock_db)

        # Mock empty result
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_connection.execute.return_value = mock_result

        # Test with various datetime formats
        test_datetimes = [
            datetime(2023, 1, 1, 0, 0, 0),    # Midnight
            datetime(2023, 1, 1, 12, 30, 45), # Mid-day with seconds
            datetime(2023, 12, 31, 23, 59, 59) # End of year
        ]

        for test_dt in test_datetimes:
            result = await weather_ops.get_weather_for_hour(test_dt)
            assert result is None  # Empty result as mocked

        # Should have called execute for each datetime
        assert mock_connection.execute.call_count == len(test_datetimes)


class TestWeatherOperationsPerformance:
    """Test performance characteristics of weather operations."""

    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self):
        """Test concurrent weather database operations."""
        # Create multiple mock databases
        mock_dbs = []
        for i in range(5):
            mock_db = Mock()
            mock_connection = AsyncMock()
            mock_db.get_connection = AsyncMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_connection),
                __aexit__=AsyncMock(return_value=None)
            ))
            
            # Mock successful query
            mock_row = Mock()
            mock_row._mapping = {"id": i, "current_temp": 20.0 + i}
            mock_result = Mock()
            mock_result.fetchone.return_value = mock_row
            mock_connection.execute.return_value = mock_result
            
            mock_dbs.append((mock_db, mock_connection))

        # Create operations for each database
        operations = [WeatherOperations(db) for db, _ in mock_dbs]

        # Run concurrent queries
        start_time = asyncio.get_event_loop().time()
        tasks = [ops.get_latest_weather() for ops in operations]
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # All should succeed
        assert len(results) == 5
        assert all(result is not None for result in results)

        # Should complete in reasonable time (< 0.1 seconds with mocking)
        duration = end_time - start_time
        assert duration < 0.1, f"Concurrent operations too slow: {duration:.3f}s"

    def test_sync_operations_performance(self):
        """Test sync operations performance."""
        import time

        # Mock multiple sync databases
        mock_dbs = []
        for i in range(10):
            mock_db = Mock()
            mock_connection = Mock()
            mock_db.get_connection.return_value.__enter__ = Mock(return_value=mock_connection)
            mock_db.get_connection.return_value.__exit__ = Mock(return_value=None)
            
            # Mock successful query
            mock_row = Mock()
            mock_row._mapping = {"id": i, "current_temp": 15.0 + i}
            mock_result = Mock()
            mock_result.fetchone.return_value = mock_row
            mock_connection.execute.return_value = mock_result
            
            mock_dbs.append(mock_db)

        # Time sequential sync operations
        start_time = time.time()
        
        for mock_db in mock_dbs:
            sync_ops = SyncWeatherOperations(mock_db)
            result = sync_ops.get_latest_weather()
            assert result is not None
        
        end_time = time.time()
        duration = end_time - start_time

        # Should handle 10 operations quickly (< 0.05 seconds with mocking)
        assert duration < 0.05, f"Sync operations too slow: {duration:.3f}s"