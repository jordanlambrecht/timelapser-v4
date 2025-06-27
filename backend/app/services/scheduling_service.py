# backend/app/services/scheduling_service.py
"""
Scheduling Service for Timelapser V4

Business logic for camera capture scheduling, intervals, and timing calculations.
This service handles all scheduling-related business rules and constraints.

Key Features:
- Calculate when next captures should occur
- Determine capture counts for durations
- Validate business constraints for capture intervals
- Apply scheduling logic with time windows

Business Rules:
- Minimum capture interval: 30 seconds
- Maximum capture interval: 24 hours
- Scheduling respects camera time windows
- Handles timezone-aware scheduling calculations
"""

import logging
from datetime import datetime, time
from typing import Optional, TYPE_CHECKING

from ..utils.time_utils import (
    create_time_delta,
)
from ..utils.timezone_utils import utc_now
from .time_window_service import TimeWindowService

if TYPE_CHECKING:
    from ..database import SyncDatabase, AsyncDatabase

logger = logging.getLogger(__name__)


class SchedulingService:
    """
    Service for camera capture scheduling business logic.
    """

    @staticmethod
    def calculate_next_capture_time(
        current_time: datetime,
        interval_seconds: int,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
    ) -> datetime:
        """
        Calculate next capture time considering interval and optional time window.

        Business logic: Determines when the next camera capture should occur
        based on the configured interval and any time window restrictions.

        Args:
            current_time: Current timezone-aware datetime
            interval_seconds: Capture interval in seconds
            start_time: Optional window start time
            end_time: Optional window end time

        Returns:
            Next capture datetime
        """
        # Calculate base next capture time
        next_capture = current_time + create_time_delta(seconds=interval_seconds)

        # If no time window, return the calculated time
        if start_time is None or end_time is None:
            return next_capture

        next_time = next_capture.time()

        # If next capture is within window, use it
        if TimeWindowService.is_time_in_window(next_time, start_time, end_time):
            return next_capture

        # Otherwise, move to next window start
        next_date = next_capture.date()

        # Create datetime for window start on the next capture date
        window_start = datetime.combine(next_date, start_time)
        window_start = window_start.replace(tzinfo=current_time.tzinfo)

        # If window start is in the past, move to next day
        if window_start <= current_time:
            window_start += create_time_delta(days=1)

        return window_start

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

        Business logic: Determines how many captures will occur during a specific
        timeframe, considering capture intervals and time window restrictions.

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

    @staticmethod
    def validate_capture_interval(interval_seconds: int) -> int:
        """
        Validate capture interval is within business constraints.

        Business rules:
        - Minimum interval: 30 seconds (prevents system overload)
        - Maximum interval: 24 hours (reasonable upper bound)

        Args:
            interval_seconds: Interval in seconds

        Returns:
            Validated interval

        Raises:
            ValueError: If interval violates business constraints
        """
        min_interval = 30  # 30 seconds minimum
        max_interval = 24 * 60 * 60  # 24 hours maximum

        if interval_seconds < min_interval:
            raise ValueError(
                f"Capture interval too short: minimum {min_interval} seconds"
            )

        if interval_seconds > max_interval:
            raise ValueError(
                f"Capture interval too long: maximum {max_interval} seconds"
            )

        return interval_seconds

    @staticmethod
    def calculate_next_capture_for_camera(
        camera_id: int,
        last_capture_time: Optional[datetime],
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        current_time: Optional[datetime] = None,
    ) -> datetime:
        """
        Calculate next capture time for a specific camera.

        Business logic: Combines last capture time, interval, and time windows
        to determine when this specific camera should capture next.

        Args:
            camera_id: Camera identifier
            last_capture_time: When camera last captured (None for first capture)
            interval_seconds: Camera's capture interval
            time_window_start: Camera's time window start
            time_window_end: Camera's time window end
            current_time: Current time (defaults to now)

        Returns:
            When camera should capture next
        """

        if current_time is None:
            current_time = utc_now()

        if last_capture_time is None:
            # First capture - check if we're in time window
            if time_window_start and time_window_end:
                current_time_only = current_time.time()
                if TimeWindowService.is_time_in_window(
                    current_time_only, time_window_start, time_window_end
                ):
                    return current_time
                else:
                    # Move to next window start
                    return SchedulingService.calculate_next_capture_time(
                        current_time, 0, time_window_start, time_window_end
                    )
            else:
                return current_time

        # Calculate next capture based on last capture
        return SchedulingService.calculate_next_capture_time(
            last_capture_time, interval_seconds, time_window_start, time_window_end
        )

    @staticmethod
    def is_capture_due(
        last_capture_time: Optional[datetime],
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        current_time: Optional[datetime] = None,
        grace_period_seconds: int = 5,
    ) -> bool:
        """
        Determine if a capture is due for a camera.

        Business logic: Checks if enough time has passed since last capture
        and if we're currently within any time window restrictions.

        Args:
            last_capture_time: When camera last captured
            interval_seconds: Camera's capture interval
            time_window_start: Camera's time window start
            time_window_end: Camera's time window end
            current_time: Current time (defaults to now)
            grace_period_seconds: Grace period for "due" determination

        Returns:
            True if capture is due
        """
        if current_time is None:
            current_time = utc_now()

        # Check time window first
        if time_window_start and time_window_end:
            current_time_only = current_time.time()
            if not TimeWindowService.is_time_in_window(
                current_time_only, time_window_start, time_window_end
            ):
                return False

        # If no last capture, capture is due
        if last_capture_time is None:
            return True

        # Check if interval has passed
        time_since_last = current_time - last_capture_time
        required_interval = create_time_delta(
            seconds=interval_seconds - grace_period_seconds
        )

        return time_since_last >= required_interval
