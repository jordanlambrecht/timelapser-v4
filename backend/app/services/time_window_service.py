# backend/app/services/time_window_service.py

"""
Time Window Service for Timelapser V4

Business logic for camera operational time windows and scheduling constraints.
This service handles all time window related business rules and calculations.

Key Features:
- Calculate time window boundaries and durations
- Determine when cameras should be active
- Validate time window configurations
- Handle overnight time windows correctly

Business Rules:
- Time windows define when cameras should capture
- Overnight windows (22:00-06:00) are supported
- Windows are validated for logical consistency
- All calculations are timezone-aware
"""

import logging
from datetime import datetime, time, date, timedelta
from typing import Optional, Tuple

from ..utils.time_utils import (
    parse_time_string,
    create_time_delta,
)

logger = logging.getLogger(__name__)


class TimeWindowService:
    """
    Service for camera time window business logic.
    """

    @staticmethod
    def is_time_in_window(current_time: time, start_time: time, end_time: time) -> bool:
        """
        Check if current time is within the specified window.

        Business logic: Determines if cameras should be active based on
        configured operational time windows.

        Args:
            current_time: Time to check
            start_time: Window start time
            end_time: Window end time

        Returns:
            True if current time is within window
        """
        if start_time <= end_time:
            # Normal window (e.g., 06:00 - 18:00)
            return start_time <= current_time <= end_time
        else:
            # Overnight window (e.g., 22:00 - 06:00)
            return current_time >= start_time or current_time <= end_time

    @staticmethod
    def calculate_next_window_start(
        current_time: datetime, window_start: time, window_end: time
    ) -> datetime:
        """
        Calculate when the next time window starts.

        Business logic: Determines when cameras will next become active
        based on their configured time windows.

        Args:
            current_time: Current datetime
            window_start: Window start time
            window_end: Window end time

        Returns:
            Datetime when window next starts
        """
        current_date = current_time.date()
        current_time_only = current_time.time()

        # Create datetime for window start today
        window_start_today = datetime.combine(current_date, window_start)
        window_start_today = window_start_today.replace(tzinfo=current_time.tzinfo)

        if TimeWindowService.is_time_in_window(
            current_time_only, window_start, window_end
        ):
            # Currently in window, next start is tomorrow
            return window_start_today + create_time_delta(days=1)
        elif current_time_only < window_start:
            # Before today's window
            return window_start_today
        else:
            # After today's window
            return window_start_today + create_time_delta(days=1)

    @staticmethod
    def calculate_next_window_end(
        current_time: datetime, window_start: time, window_end: time
    ) -> datetime:
        """
        Calculate when the current/next time window ends.

        Business logic: Determines when cameras will next become inactive
        based on their configured time windows.

        Args:
            current_time: Current datetime
            window_start: Window start time
            window_end: Window end time

        Returns:
            Datetime when window ends
        """
        current_date = current_time.date()
        current_time_only = current_time.time()

        # Handle overnight windows
        if window_start > window_end:
            # Overnight window
            if current_time_only >= window_start:
                # Started today, ends tomorrow
                window_end_datetime = datetime.combine(
                    current_date + create_time_delta(days=1), window_end
                )
            else:
                # Started yesterday, ends today
                window_end_datetime = datetime.combine(current_date, window_end)
        else:
            # Normal window
            window_end_datetime = datetime.combine(current_date, window_end)

            # If we're past today's window, use tomorrow's
            if current_time_only > window_end:
                window_end_datetime += create_time_delta(days=1)

        return window_end_datetime.replace(tzinfo=current_time.tzinfo)

    @staticmethod
    def calculate_daily_window_duration(start_time: time, end_time: time) -> timedelta:
        """
        Calculate duration of a daily time window.

        Business logic: Determines how long cameras are active each day
        for capacity planning and capture count estimation.

        Args:
            start_time: Window start time
            end_time: Window end time

        Returns:
            Duration of the time window
        """
        if start_time <= end_time:
            # Normal window (e.g., 06:00 - 18:00)
            start_dt = datetime.combine(date.today(), start_time)
            end_dt = datetime.combine(date.today(), end_time)
            return end_dt - start_dt
        else:
            # Overnight window (e.g., 22:00 - 06:00)
            # Duration is: (24:00 - start_time) + (end_time - 00:00)
            midnight = time(0, 0, 0)
            end_of_day = time(23, 59, 59)

            start_dt = datetime.combine(date.today(), start_time)
            end_of_day_dt = datetime.combine(date.today(), end_of_day)
            start_of_day_dt = datetime.combine(date.today(), midnight)
            end_dt = datetime.combine(date.today(), end_time)

            duration1 = (
                end_of_day_dt - start_dt + timedelta(seconds=1)
            )  # Until end of day
            duration2 = end_dt - start_of_day_dt  # From start of day

            return duration1 + duration2

    @staticmethod
    def validate_time_window(start_time: str, end_time: str) -> Tuple[time, time]:
        """
        Validate and parse a time window configuration.

        Business rules:
        - Time strings must be in valid HH:MM or HH:MM:SS format
        - Both start and end times must be valid
        - Times can create overnight windows (start > end is allowed)

        Args:
            start_time: Start time string
            end_time: End time string

        Returns:
            Tuple of (start_time, end_time) objects (as time)

        Raises:
            ValueError: If time window configuration is invalid
        """
        start_dt = parse_time_string(start_time)
        end_dt = parse_time_string(end_time)
        if start_dt is None or end_dt is None:
            raise ValueError(f"Invalid time window: could not parse start or end time.")
        return start_dt.time(), end_dt.time()

    @staticmethod
    def get_window_status(
        current_time: datetime, window_start: Optional[time], window_end: Optional[time]
    ) -> dict:
        """
        Get comprehensive time window status for a camera.

        Business logic: Provides complete information about camera
        operational status and upcoming window changes.

        Args:
            current_time: Current datetime
            window_start: Window start time (None if no window)
            window_end: Window end time (None if no window)

        Returns:
            Dictionary with window status information:
            - is_active: Whether camera should be capturing now
            - next_start: When window will next start (if not active)
            - next_end: When window will next end (if active)
            - window_duration: Total daily window duration
        """
        status = {
            "is_active": True,
            "next_start": None,
            "next_end": None,
            "window_duration": None,
            "has_window": False,
        }

        # No time window configured
        if window_start is None or window_end is None:
            return status

        status["has_window"] = True
        current_time_only = current_time.time()

        # Check if currently in window
        status["is_active"] = TimeWindowService.is_time_in_window(
            current_time_only, window_start, window_end
        )

        # Calculate next transitions
        if status["is_active"]:
            status["next_end"] = TimeWindowService.calculate_next_window_end(
                current_time, window_start, window_end
            )
        else:
            status["next_start"] = TimeWindowService.calculate_next_window_start(
                current_time, window_start, window_end
            )

        # Calculate window duration
        status["window_duration"] = TimeWindowService.calculate_daily_window_duration(
            window_start, window_end
        )

        return status

    @staticmethod
    def calculate_active_time_in_period(
        start_date: date,
        end_date: date,
        window_start: Optional[time],
        window_end: Optional[time],
    ) -> timedelta:
        """
        Calculate total active time within a date range considering time windows.

        Business logic: Used for analytics and reporting to determine
        total operational time for cameras over specific periods.

        Args:
            start_date: Period start date
            end_date: Period end date
            window_start: Daily window start time
            window_end: Daily window end time

        Returns:
            Total active time duration
        """
        if window_start is None or window_end is None:
            # No time window restrictions - active 24/7
            total_days = (end_date - start_date).days + 1
            return create_time_delta(days=total_days)

        # Calculate daily window duration
        daily_duration = TimeWindowService.calculate_daily_window_duration(
            window_start, window_end
        )

        # Calculate number of days in period
        total_days = (end_date - start_date).days + 1

        return daily_duration * total_days

    @staticmethod
    def calculate_capture_count_for_duration(
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
    ) -> int:
        """
        Calculate expected number of captures for a given duration and time window.

        Business logic: Used for analytics, planning, and progress tracking
        to determine how many captures should occur in a given period.

        Args:
            start_time: Start of the period
            end_time: End of the period
            interval_seconds: Capture interval in seconds
            time_window_start: Optional daily time window start
            time_window_end: Optional daily time window end

        Returns:
            Expected number of captures
        """
        total_seconds = int((end_time - start_time).total_seconds())

        if time_window_start is None or time_window_end is None:
            # No time window restrictions
            return max(0, total_seconds // interval_seconds)

        # Calculate captures per day within time window
        window_duration = TimeWindowService.calculate_daily_window_duration(
            time_window_start, time_window_end
        )
        captures_per_day = window_duration.total_seconds() // interval_seconds

        # Calculate number of days
        total_days = (end_time.date() - start_time.date()).days + 1

        return max(0, int(captures_per_day * total_days))
