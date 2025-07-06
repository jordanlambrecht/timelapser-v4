"""Database operations for weather data."""

from datetime import datetime
from typing import Dict, Any, Optional

from .core import AsyncDatabaseCore, SyncDatabaseCore
from ..exceptions import TimelapserError


class WeatherOperations:
    """Async operations for weather data table."""

    def __init__(self, db: AsyncDatabaseCore):
        self.db = db

    async def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the current weather data (single row)."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM weather_data 
                    WHERE single_row_enforcer = 1
                """
                )
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
                await cur.execute(
                    """
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
                        updated_at = NOW()
                    RETURNING id
                """,
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
                    ),
                )
                row = await cur.fetchone()
                if row:
                    weather_id = row["id"]
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
                # Update existing row with failure info and increment consecutive failures
                await cur.execute(
                    """
                    UPDATE weather_data 
                    SET 
                        api_key_valid = false,
                        error_response_code = %s,
                        last_error_message = %s,
                        consecutive_failures = consecutive_failures + 1,
                        api_failing = (consecutive_failures + 1) >= 4,
                        updated_at = NOW()
                    WHERE single_row_enforcer = 1
                """,
                    (error_response_code, last_error_message),
                )
                await conn.commit()

    async def get_weather_for_hour(
        self, target_datetime: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get weather data (returns current weather since we only maintain one row)."""
        # With single-row table, we always return current weather
        # The target_datetime parameter is kept for backward compatibility
        return await self.get_latest_weather()


class SyncWeatherOperations:
    """Sync operations for weather data table."""

    def __init__(self, db: SyncDatabaseCore):
        self.db = db

    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the current weather data (single row)."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM weather_data 
                    WHERE single_row_enforcer = 1
                """
                )
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
                cur.execute(
                    """
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
                        updated_at = NOW()
                    RETURNING id
                """,
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
                # Update existing row with failure info and increment consecutive failures
                cur.execute(
                    """
                    UPDATE weather_data 
                    SET 
                        api_key_valid = false,
                        error_response_code = %s,
                        last_error_message = %s,
                        consecutive_failures = consecutive_failures + 1,
                        api_failing = (consecutive_failures + 1) >= 4,
                        updated_at = NOW()
                    WHERE single_row_enforcer = 1
                """,
                    (error_response_code, last_error_message),
                )
                conn.commit()

    def get_weather_for_hour(
        self, target_datetime: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific hour."""
        # Round down to the hour
        hour_start = target_datetime.replace(minute=0, second=0, microsecond=0)

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM weather_data 
                    WHERE weather_date_fetched >= %s
                    AND weather_date_fetched < %s + INTERVAL '1 hour'
                    AND api_key_valid = true
                    ORDER BY weather_date_fetched DESC
                    LIMIT 1
                """,
                    (hour_start, hour_start),
                )
                row = cur.fetchone()

                # If no data for this hour, get the most recent valid data
                if not row:
                    cur.execute(
                        """
                        SELECT * FROM weather_data 
                        WHERE api_key_valid = true
                        ORDER BY weather_date_fetched DESC
                        LIMIT 1
                    """
                    )
                    row = cur.fetchone()

                return dict(row) if row else None
