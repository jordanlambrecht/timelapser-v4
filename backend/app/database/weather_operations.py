"""Database operations for weather data."""

from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .core import AsyncDatabaseCore, SyncDatabaseCore
from ..exceptions import TimelapserError


class WeatherOperations:
    """Async operations for weather data table."""
    
    def __init__(self, db: AsyncDatabaseCore):
        self.db = db
    
    async def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weather data."""
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                text("""
                    SELECT * FROM weather_data 
                    ORDER BY weather_date_fetched DESC 
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
    
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
        last_error_message: Optional[str] = None
    ) -> int:
        """Insert new weather data record."""
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                text("""
                    INSERT INTO weather_data (
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
                        :weather_date_fetched,
                        :current_temp,
                        :current_weather_icon,
                        :current_weather_description,
                        :sunrise_timestamp,
                        :sunset_timestamp,
                        :api_key_valid,
                        :api_failing,
                        :error_response_code,
                        :last_error_message,
                        0
                    )
                    RETURNING id
                """),
                {
                    "weather_date_fetched": weather_date_fetched,
                    "current_temp": current_temp,
                    "current_weather_icon": current_weather_icon,
                    "current_weather_description": current_weather_description,
                    "sunrise_timestamp": sunrise_timestamp,
                    "sunset_timestamp": sunset_timestamp,
                    "api_key_valid": api_key_valid,
                    "api_failing": api_failing,
                    "error_response_code": error_response_code,
                    "last_error_message": last_error_message
                }
            )
            weather_id = result.scalar()
            await conn.commit()
            return weather_id
    
    async def update_weather_failure(
        self,
        error_response_code: Optional[int] = None,
        last_error_message: Optional[str] = None
    ) -> None:
        """Update weather data with failure information."""
        async with self.db.get_connection() as conn:
            # Get current consecutive failures
            result = await conn.execute(
                text("""
                    SELECT consecutive_failures 
                    FROM weather_data 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            current_failures = row._mapping["consecutive_failures"] if row else 0
            
            # Insert new failure record
            new_failures = current_failures + 1
            api_failing = new_failures >= 4  # Mark as failing after 4 consecutive failures
            
            await self.insert_weather_data(
                weather_date_fetched=datetime.utcnow(),
                api_key_valid=False,
                api_failing=api_failing,
                error_response_code=error_response_code,
                last_error_message=last_error_message
            )
    
    async def get_weather_for_hour(self, target_datetime: datetime) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific hour."""
        # Round down to the hour
        hour_start = target_datetime.replace(minute=0, second=0, microsecond=0)
        
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                text("""
                    SELECT * FROM weather_data 
                    WHERE weather_date_fetched >= :hour_start
                    AND weather_date_fetched < :hour_start + INTERVAL '1 hour'
                    AND api_key_valid = true
                    ORDER BY weather_date_fetched DESC
                    LIMIT 1
                """),
                {"hour_start": hour_start}
            )
            row = result.fetchone()
            
            # If no data for this hour, get the most recent valid data
            if not row:
                result = await conn.execute(
                    text("""
                        SELECT * FROM weather_data 
                        WHERE api_key_valid = true
                        ORDER BY weather_date_fetched DESC
                        LIMIT 1
                    """)
                )
                row = result.fetchone()
            
            return dict(row._mapping) if row else None


class SyncWeatherOperations:
    """Sync operations for weather data table."""
    
    def __init__(self, db: SyncDatabaseCore):
        self.db = db
    
    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        """Get the most recent weather data."""
        with self.db.get_connection() as conn:
            result = conn.execute(
                text("""
                    SELECT * FROM weather_data 
                    ORDER BY weather_date_fetched DESC 
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
    
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
        last_error_message: Optional[str] = None
    ) -> int:
        """Insert new weather data record."""
        with self.db.get_connection() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO weather_data (
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
                        :weather_date_fetched,
                        :current_temp,
                        :current_weather_icon,
                        :current_weather_description,
                        :sunrise_timestamp,
                        :sunset_timestamp,
                        :api_key_valid,
                        :api_failing,
                        :error_response_code,
                        :last_error_message,
                        0
                    )
                    RETURNING id
                """),
                {
                    "weather_date_fetched": weather_date_fetched,
                    "current_temp": current_temp,
                    "current_weather_icon": current_weather_icon,
                    "current_weather_description": current_weather_description,
                    "sunrise_timestamp": sunrise_timestamp,
                    "sunset_timestamp": sunset_timestamp,
                    "api_key_valid": api_key_valid,
                    "api_failing": api_failing,
                    "error_response_code": error_response_code,
                    "last_error_message": last_error_message
                }
            )
            weather_id = result.scalar()
            conn.commit()
            return weather_id
    
    def update_weather_failure(
        self,
        error_response_code: Optional[int] = None,
        last_error_message: Optional[str] = None
    ) -> None:
        """Update weather data with failure information."""
        with self.db.get_connection() as conn:
            # Get current consecutive failures
            result = conn.execute(
                text("""
                    SELECT consecutive_failures 
                    FROM weather_data 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            current_failures = row._mapping["consecutive_failures"] if row else 0
            
            # Insert new failure record
            new_failures = current_failures + 1
            api_failing = new_failures >= 4  # Mark as failing after 4 consecutive failures
            
            self.insert_weather_data(
                weather_date_fetched=datetime.utcnow(),
                api_key_valid=False,
                api_failing=api_failing,
                error_response_code=error_response_code,
                last_error_message=last_error_message
            )
    
    def get_weather_for_hour(self, target_datetime: datetime) -> Optional[Dict[str, Any]]:
        """Get weather data for a specific hour."""
        # Round down to the hour
        hour_start = target_datetime.replace(minute=0, second=0, microsecond=0)
        
        with self.db.get_connection() as conn:
            result = conn.execute(
                text("""
                    SELECT * FROM weather_data 
                    WHERE weather_date_fetched >= :hour_start
                    AND weather_date_fetched < :hour_start + INTERVAL '1 hour'
                    AND api_key_valid = true
                    ORDER BY weather_date_fetched DESC
                    LIMIT 1
                """),
                {"hour_start": hour_start}
            )
            row = result.fetchone()
            
            # If no data for this hour, get the most recent valid data
            if not row:
                result = conn.execute(
                    text("""
                        SELECT * FROM weather_data 
                        WHERE api_key_valid = true
                        ORDER BY weather_date_fetched DESC
                        LIMIT 1
                    """)
                )
                row = result.fetchone()
            
            return dict(row._mapping) if row else None