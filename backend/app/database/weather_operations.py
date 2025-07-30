"""Database operations for weather data."""

from datetime import datetime
from typing import Dict, Any, Optional

from .core import AsyncDatabase, SyncDatabase
from ..utils.cache_manager import cache, cached_response, generate_timestamp_etag
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.time_utils import utc_now


class WeatherQueryBuilder:
    """Centralized query builder for weather operations."""

    @staticmethod
    def build_latest_weather_query():
        """Build optimized query for latest weather data."""
        return """
            SELECT * FROM weather_data
            WHERE single_row_enforcer = 1
        """

    @staticmethod
    def build_weather_upsert_query():
        """Build optimized upsert query for weather data."""
        return """
            INSERT INTO weather_data (
                single_row_enforcer,
                weather_date_fetched,
                current_temp,
                current_weather_icon,
                current_weather_description,
                sunrise_timestamp,
                sunset_timestamp,
                api_key_valid,
                api_failing,
                error_response_code,
                last_error_message,
                consecutive_failures
            ) VALUES (
                1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0
            )
            ON CONFLICT (single_row_enforcer) DO UPDATE SET
                weather_date_fetched = EXCLUDED.weather_date_fetched,
                current_temp = EXCLUDED.current_temp,
                current_weather_icon = EXCLUDED.current_weather_icon,
                current_weather_description = EXCLUDED.current_weather_description,
                sunrise_timestamp = EXCLUDED.sunrise_timestamp,
                sunset_timestamp = EXCLUDED.sunset_timestamp,
                api_key_valid = EXCLUDED.api_key_valid,
                api_failing = EXCLUDED.api_failing,
                error_response_code = EXCLUDED.error_response_code,
                last_error_message = EXCLUDED.last_error_message,
                consecutive_failures = CASE 
                    WHEN EXCLUDED.api_failing = true AND weather_data.api_failing = true 
                    THEN weather_data.consecutive_failures + 1
                    ELSE 0
                END,
                updated_at = %s
            RETURNING id
        """

    @staticmethod
    def build_weather_failure_update_query():
        """Build optimized query for weather failure updates."""
        return """
            UPDATE weather_data
            SET
                api_key_valid = false,
                error_response_code = %s,
                last_error_message = %s,
                consecutive_failures = consecutive_failures + 1,
                api_failing = (consecutive_failures + 1) >= 4,
                updated_at = %s
            WHERE single_row_enforcer = 1
        """

    @staticmethod
    def build_weather_for_hour_query():
        """Build optimized query for weather data by hour."""
        return """
            SELECT * FROM weather_data
            WHERE weather_date_fetched >= %s
            AND weather_date_fetched < %s + INTERVAL '1 hour'
            AND api_key_valid = true
            ORDER BY weather_date_fetched DESC
            LIMIT 1
        """

    @staticmethod
    def build_fallback_weather_query():
        """Build optimized fallback query for most recent valid weather data."""
        return """
            SELECT * FROM weather_data
            WHERE api_key_valid = true
            ORDER BY weather_date_fetched DESC
            LIMIT 1
        """


class WeatherOperations:
    """Async operations for weather data table."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_weather_caches(
        self, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to weather data using sophisticated cache system."""
        # Weather data is single-row, so clear all weather-related caches
        cache_patterns = [
            "weather:get_latest_weather",
            "weather:get_weather_for_hour",
        ]

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

        # Use ETag-aware invalidation if timestamp provided
        if updated_at:
            etag = generate_timestamp_etag(updated_at)
            await self.cache_invalidation.invalidate_with_etag_validation(
                "weather:metadata", etag
            )

    @cached_response(ttl_seconds=60, key_prefix="weather")
    async def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the current weather data (single row)."""
        # Use optimized query builder
        query = WeatherQueryBuilder.build_latest_weather_query()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def insert_weather_data(
        self,
        weather_date_fetched: datetime,
        current_temp: Optional[float] = None,
        current_weather_icon: Optional[str] = None,
        current_weather_description: Optional[str] = None,
        sunrise_timestamp: Optional[datetime] = None,
        sunset_timestamp: Optional[datetime] = None,
        api_key_valid: bool = True,
        api_failing: bool = False,
        error_response_code: Optional[int] = None,
        last_error_message: Optional[str] = None,
    ) -> int:
        """Upsert weather data - maintains single row in table."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Use optimized query builder and centralized time management
                query = WeatherQueryBuilder.build_weather_upsert_query()
                now = utc_now()

                await cur.execute(
                    query,
                    (
                        weather_date_fetched,
                        current_temp,
                        current_weather_icon,
                        current_weather_description,
                        sunrise_timestamp,
                        sunset_timestamp,
                        api_key_valid,
                        api_failing,
                        error_response_code,
                        last_error_message,
                        now,
                    ),
                )
                row = await cur.fetchone()
                if row:
                    weather_id = row["id"]

                    # Clear related caches after successful upsert
                    await self._clear_weather_caches(updated_at=now)

                    return weather_id
                else:
                    raise Exception("No row returned from weather data upsert")

    async def update_weather_failure(
        self,
        error_response_code: Optional[int] = None,
        last_error_message: Optional[str] = None,
    ) -> None:
        """Update weather data with failure information."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Use optimized query builder and centralized time management
                query = WeatherQueryBuilder.build_weather_failure_update_query()
                now = utc_now()

                await cur.execute(
                    query,
                    (error_response_code, last_error_message, now),
                )

                # Clear related caches after successful failure update
                await self._clear_weather_caches(updated_at=now)

    @cached_response(ttl_seconds=300, key_prefix="weather")
    async def get_weather_for_hour(
        self, target_datetime: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific hour."""
        # Round down to the hour
        hour_start = target_datetime.replace(minute=0, second=0, microsecond=0)

        # Use optimized query builders
        query = WeatherQueryBuilder.build_weather_for_hour_query()
        fallback_query = WeatherQueryBuilder.build_fallback_weather_query()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (hour_start, hour_start))
                row = await cur.fetchone()

                # If no data for this hour, get the most recent valid data
                if not row:
                    await cur.execute(fallback_query)
                    row = await cur.fetchone()

                return dict(row) if row else None


class SyncWeatherOperations:
    """Sync operations for weather data table."""

    def __init__(self, db: SyncDatabase) -> None:
        self.db = db

    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the current weather data (single row)."""
        # Use optimized query builder
        query = WeatherQueryBuilder.build_latest_weather_query()

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                return dict(row) if row else None

    def insert_weather_data(
        self,
        weather_date_fetched: datetime,
        current_temp: Optional[float] = None,
        current_weather_icon: Optional[str] = None,
        current_weather_description: Optional[str] = None,
        sunrise_timestamp: Optional[datetime] = None,
        sunset_timestamp: Optional[datetime] = None,
        api_key_valid: bool = True,
        api_failing: bool = False,
        error_response_code: Optional[int] = None,
        last_error_message: Optional[str] = None,
    ) -> int:
        """Upsert weather data - maintains single row in table."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Use optimized query builder and centralized time management
                query = WeatherQueryBuilder.build_weather_upsert_query()
                now = utc_now()

                cur.execute(
                    query,
                    (
                        weather_date_fetched,
                        current_temp,
                        current_weather_icon,
                        current_weather_description,
                        sunrise_timestamp,
                        sunset_timestamp,
                        api_key_valid,
                        api_failing,
                        error_response_code,
                        last_error_message,
                        now,
                    ),
                )
                row = cur.fetchone()
                if row:
                    weather_id = row["id"]
                    return weather_id
                else:
                    raise Exception("No row returned from weather data upsert")

    def update_weather_failure(
        self,
        error_response_code: Optional[int] = None,
        last_error_message: Optional[str] = None,
    ) -> None:
        """Update weather data with failure information."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Use optimized query builder and centralized time management
                query = WeatherQueryBuilder.build_weather_failure_update_query()
                cur.execute(
                    query,
                    (error_response_code, last_error_message, utc_now()),
                )

    def get_weather_for_hour(
        self, target_datetime: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific hour."""
        # Round down to the hour
        hour_start = target_datetime.replace(minute=0, second=0, microsecond=0)

        # Use optimized query builders
        query = WeatherQueryBuilder.build_weather_for_hour_query()
        fallback_query = WeatherQueryBuilder.build_fallback_weather_query()

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (hour_start, hour_start))
                row = cur.fetchone()

                # If no data for this hour, get the most recent valid data
                if not row:
                    cur.execute(fallback_query)
                    row = cur.fetchone()

                return dict(row) if row else None
