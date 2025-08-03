# backend/app/services/scheduling/time_window_service.py

"""
Time Window Service - Composition-based architecture.

This service handles camera operational time windows and scheduling constraints
using dependency injection for database operations, providing type-safe
Pydantic model interfaces.

Business logic for camera time window management, validation, and status tracking.
This service handles all time window related business rules and calculations.

Key Features:
- Calculate time window boundaries and durations
- Determine when cameras should be active
- Validate time window configurations with Pydantic models
- Handle overnight time windows correctly
- Structured Pydantic model responses
- Frontend settings integration for configurable behavior

Business Rules:
- Time windows define when cameras should capture
- Overnight windows (22:00-06:00) are supported
- Windows are validated for logical consistency
- All calculations are timezone-aware
- Configurable grace periods and validation timeouts
"""

from datetime import datetime, time, date, timedelta
from typing import Optional, Tuple, TYPE_CHECKING
from ...services.logger import get_service_logger
from ...enums import LoggerName

logger = get_service_logger(LoggerName.SCHEDULING_SERVICE)

from ...database.core import AsyncDatabase, SyncDatabase

if TYPE_CHECKING:
    pass  # No TYPE_CHECKING imports needed
from ...models.shared_models import (
    TimeWindowStatus,
    TimeWindowValidationResult,
    TimeWindowCalculationRequest,
    CaptureCountEstimateRequest,
    ActiveTimePeriodRequest,
    ActiveTimePeriodResult,
)
from ...utils.time_utils import (
    parse_time_string,
    create_time_delta,
)
from ...constants import (
    DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS,
    DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS,
    EVENT_TIME_WINDOW_VALIDATED,
    EVENT_TIME_WINDOW_STATUS_CALCULATED,
    EVENT_CAPTURE_COUNT_ESTIMATED,
)


class TimeWindowService:
    """
    Camera time window business logic using composition pattern.

    Responsibilities:
    - Time window status calculations
    - Window boundary and duration calculations
    - Time window validation with Pydantic models
    - Frontend settings integration
    - Structured data responses with Pydantic models

    Interactions:
    - Uses injected SettingsService for configuration
    - Provides structured Pydantic model responses
    - Integrates with frontend configurable settings
    """

    def __init__(self, db: AsyncDatabase, settings_service=None):
        """
        Initialize TimeWindowService with async database instance and settings service.

        Args:
            db: AsyncDatabase instance
            settings_service: Optional SettingsService instance for dependency injection
        """
        self.db = db
        self.settings_service = settings_service

    async def _get_setting(self, key: str):
        """Helper method to get settings through proper dependency injection."""
        if self.settings_service:
            return await self.settings_service.get_setting(key)
        else:
            # Log warning when settings service is not available
            logger.warning(f"Settings service not available for key: {key}")
            return None

    async def _get_time_window_settings(self) -> dict:
        """Get time window settings from database using proper operations layer."""
        try:
            # Use helper method for consistent settings access
            validation_timeout = await self._get_setting(
                "time_window_validation_timeout_seconds"
            )
            grace_period = await self._get_setting(
                "time_window_grace_period_seconds"
            )

            return {
                "validation_timeout_seconds": (
                    int(validation_timeout)
                    if validation_timeout
                    else DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS
                ),
                "grace_period_seconds": (
                    int(grace_period)
                    if grace_period
                    else DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS
                ),
            }
        except Exception as e:
            logger.warning(f"Failed to get time window settings, using defaults: {e}")
            return {
                "validation_timeout_seconds": DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS,
                "grace_period_seconds": DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS,
            }

    def _combine_datetime_with_timezone(
        self, current_time: datetime, target_time: time
    ) -> datetime:
        """
        Helper method to combine date and time with timezone preservation.
        Eliminates code duplication in window calculations.
        """
        combined = datetime.combine(current_time.date(), target_time)
        return combined.replace(tzinfo=current_time.tzinfo)

    def is_time_in_window(
        self, current_time: time, start_time: time, end_time: time
    ) -> bool:
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
        # Overnight window (e.g., 22:00 - 06:00)
        return current_time >= start_time or current_time <= end_time

    async def calculate_next_window_start(
        self,
        current_time: datetime,
        window_start: time,
        window_end: time,
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
        current_time_only = current_time.time()

        # Create datetime for window start today using helper method
        window_start_today = self._combine_datetime_with_timezone(
            current_time, window_start
        )

        if self.is_time_in_window(current_time_only, window_start, window_end):
            # Currently in window, next start is tomorrow
            return window_start_today + create_time_delta(days=1)
        elif current_time_only < window_start:
            # Before today's window
            return window_start_today
        else:
            # After today's window
            return window_start_today + create_time_delta(days=1)

    async def calculate_next_window_end(
        self,
        current_time: datetime,
        window_start: time,
        window_end: time,
    ) -> datetime:
        """
        Calculate when the current/next time window ends.
        """
        current_time_only = current_time.time()
        window_end_today = self._combine_datetime_with_timezone(
            current_time, window_end
        )

        if window_start <= window_end:
            # Normal window
            if current_time_only <= window_end:
                return window_end_today
            else:
                return window_end_today + create_time_delta(days=1)
        else:
            # Overnight window
            if current_time_only <= window_end:
                return window_end_today
            elif current_time_only >= window_start:
                return window_end_today + create_time_delta(days=1)
            else:
                return window_end_today

    def calculate_daily_window_duration(
        self, start_time: time, end_time: time
    ) -> timedelta:
        """
        Calculate the duration of a daily time window.

        Args:
            start_time: Window start time
            end_time: Window end time

        Returns:
            Duration as timedelta
        """
        if start_time <= end_time:
            # Normal window
            return datetime.combine(date.min, end_time) - datetime.combine(
                date.min, start_time
            )
        # Overnight window
        return (
            datetime.combine(date.min, time.max)
            - datetime.combine(date.min, start_time)
            + datetime.combine(date.min, end_time)
            - datetime.combine(date.min, time.min)
            + timedelta(seconds=1)
        )

    async def validate_time_window(
        self, start_time: str, end_time: str
    ) -> TimeWindowValidationResult:
        """
        Validate and parse a time window configuration using Pydantic models.

        Business rules:
        - Time strings must be in valid HH:MM or HH:MM:SS format
        - Both start and end times must be valid
        - Times can create overnight windows (start > end is allowed)

        Args:
            start_time: Start time string
            end_time: End time string

        Returns:
            TimeWindowValidationResult with validation details
        """
        try:
            start_dt = parse_time_string(start_time)
            end_dt = parse_time_string(end_time)

            if start_dt is None or end_dt is None:
                result = TimeWindowValidationResult(
                    is_valid=False,
                    error_message="Invalid time format. Use HH:MM or HH:MM:SS format.",
                )
            else:
                start_time_obj = start_dt.time()
                end_time_obj = end_dt.time()
                is_overnight = start_time_obj > end_time_obj
                duration = self.calculate_daily_window_duration(
                    start_time_obj, end_time_obj
                )

                result = TimeWindowValidationResult(
                    is_valid=True,
                    start_time=start_time_obj.strftime("%H:%M:%S"),
                    end_time=end_time_obj.strftime("%H:%M:%S"),
                    is_overnight=is_overnight,
                    duration_seconds=int(duration.total_seconds()),
                )

            # Broadcast SSE event for successful validation
            # SSE broadcasting removed - now handled in router layer

            return result

        except Exception as e:
            logger.error(f"Time window validation failed: {e}")
            return TimeWindowValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
            )

    async def get_window_status(
        self,
        request: TimeWindowCalculationRequest,
    ) -> TimeWindowStatus:
        """
        Get comprehensive time window status for a camera using Pydantic models.

        Business logic: Provides complete information about camera
        operational status and upcoming window changes.

        Args:
            request: TimeWindowCalculationRequest with calculation parameters

        Returns:
            TimeWindowStatus with complete window information
        """
        try:
            current_time = request.current_time
            window_start_str = request.window_start
            window_end_str = request.window_end

            # No time window configured
            if not window_start_str or not window_end_str:
                return TimeWindowStatus(
                    is_active=True,
                    has_window=False,
                    current_time=current_time,
                )

            # Parse time window
            validation_result = await self.validate_time_window(
                window_start_str, window_end_str
            )
            if not validation_result.is_valid:
                logger.error(
                    f"Invalid time window configuration: {validation_result.error_message}"
                )
                return TimeWindowStatus(
                    is_active=False,
                    has_window=False,
                    current_time=current_time,
                )

            # Parse validated time objects
            if not validation_result.start_time or not validation_result.end_time:
                logger.error("Missing time values in validation result")
                return TimeWindowStatus(
                    is_active=False,
                    has_window=False,
                    current_time=current_time,
                )

            window_start = datetime.strptime(
                validation_result.start_time, "%H:%M:%S"
            ).time()
            window_end = datetime.strptime(
                validation_result.end_time, "%H:%M:%S"
            ).time()

            current_time_only = current_time.time()

            # Check if currently in window
            is_active = self.is_time_in_window(
                current_time_only, window_start, window_end
            )

            # Calculate next transitions
            next_start = None
            next_end = None

            if is_active:
                next_end = await self.calculate_next_window_end(
                    current_time, window_start, window_end
                )
            else:
                next_start = await self.calculate_next_window_start(
                    current_time, window_start, window_end
                )

            status_result = TimeWindowStatus(
                is_active=is_active,
                has_window=True,
                next_start=next_start,
                next_end=next_end,
                window_duration=validation_result.duration_seconds,
                current_time=current_time,
            )

            # SSE broadcasting removed - now handled in router layer

            return status_result

        except Exception as e:
            logger.error(f"Failed to get window status: {e}")
            return TimeWindowStatus(
                is_active=False,
                has_window=False,
                current_time=request.current_time,
            )

    async def get_window_status_simple(
        self,
        current_time: datetime,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
    ) -> TimeWindowStatus:
        """
        Convenience method for get_window_status with individual parameters.

        Args:
            current_time: Current datetime
            window_start: Window start time string (HH:MM:SS)
            window_end: Window end time string (HH:MM:SS)

        Returns:
            TimeWindowStatus with window information
        """
        request = TimeWindowCalculationRequest(
            current_time=current_time,
            window_start=window_start,
            window_end=window_end,
        )
        return await self.get_window_status(request)

    async def calculate_active_time_in_period(
        self,
        request: ActiveTimePeriodRequest,
    ) -> ActiveTimePeriodResult:
        """
        Calculate total active time within a date range considering time windows.

        Business logic: Used for analytics and reporting to determine
        total operational time for cameras over specific periods.

        Args:
            request: ActiveTimePeriodRequest with calculation parameters

        Returns:
            ActiveTimePeriodResult with detailed calculation results
        """
        try:
            start_date = request.start_date
            end_date = request.end_date
            window_start_str = request.window_start
            window_end_str = request.window_end

            total_days = (end_date - start_date).days + 1

            if not window_start_str or not window_end_str:
                # No time window restrictions - active 24/7
                total_seconds = total_days * 24 * 3600
                return ActiveTimePeriodResult(
                    total_days=total_days,
                    active_duration_seconds=total_seconds,
                    has_time_restrictions=False,
                )

            # Validate and parse time window
            validation_result = await self.validate_time_window(
                window_start_str, window_end_str
            )
            if not validation_result.is_valid:
                logger.error(
                    f"Invalid time window for active time calculation: {validation_result.error_message}"
                )
                return ActiveTimePeriodResult(
                    total_days=total_days,
                    active_duration_seconds=0,
                    has_time_restrictions=True,
                )

            daily_window_seconds = validation_result.duration_seconds or 0
            total_active_seconds = daily_window_seconds * total_days

            return ActiveTimePeriodResult(
                total_days=total_days,
                active_duration_seconds=total_active_seconds,
                daily_window_seconds=daily_window_seconds,
                has_time_restrictions=True,
            )

        except Exception as e:
            logger.error(f"Failed to calculate active time in period: {e}")
            return ActiveTimePeriodResult(
                total_days=0,
                active_duration_seconds=0,
                has_time_restrictions=False,
            )

    async def calculate_active_time_in_period_simple(
        self,
        start_date: date,
        end_date: date,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
    ) -> ActiveTimePeriodResult:
        """
        Convenience method for calculate_active_time_in_period with individual parameters.

        Args:
            start_date: Period start date
            end_date: Period end date
            window_start: Daily window start (HH:MM:SS)
            window_end: Daily window end (HH:MM:SS)

        Returns:
            ActiveTimePeriodResult with calculation details
        """
        request = ActiveTimePeriodRequest(
            start_date=start_date,
            end_date=end_date,
            window_start=window_start,
            window_end=window_end,
        )
        return await self.calculate_active_time_in_period(request)

    async def calculate_capture_count_for_duration(
        self,
        request: CaptureCountEstimateRequest,
    ) -> int:
        """
        Calculate expected number of captures for a given duration and time window.

        Business logic: Used for analytics, planning, and progress tracking
        to determine how many captures should occur in a given period.

        Args:
            request: CaptureCountEstimateRequest with calculation parameters

        Returns:
            Expected number of captures
        """
        try:
            start_time = request.start_time
            end_time = request.end_time
            interval_seconds = request.interval_seconds
            time_window_start = request.time_window_start
            time_window_end = request.time_window_end

            total_seconds = int((end_time - start_time).total_seconds())

            if not time_window_start or not time_window_end:
                # No time window restrictions
                return max(0, total_seconds // interval_seconds)

            # Validate time window
            validation_result = await self.validate_time_window(
                time_window_start, time_window_end
            )
            if not validation_result.is_valid:
                logger.error(
                    f"Invalid time window for capture count calculation: {validation_result.error_message}"
                )
                return 0

            # Calculate captures per day within time window
            window_duration_seconds = validation_result.duration_seconds or 0
            captures_per_day = window_duration_seconds // interval_seconds

            # Calculate number of days
            total_days = (end_time.date() - start_time.date()).days + 1
            estimated_captures = max(0, int(captures_per_day * total_days))

            # SSE broadcasting removed - now handled in router layer

            return estimated_captures

        except Exception as e:
            logger.error(f"Failed to calculate capture count: {e}")
            return 0

    async def calculate_capture_count_for_duration_simple(
        self,
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int,
        time_window_start: Optional[str] = None,
        time_window_end: Optional[str] = None,
    ) -> int:
        """
        Convenience method for calculate_capture_count_for_duration with individual parameters.

        Args:
            start_time: Period start time
            end_time: Period end time
            interval_seconds: Capture interval in seconds
            time_window_start: Daily window start (HH:MM:SS)
            time_window_end: Daily window end (HH:MM:SS)

        Returns:
            Expected number of captures
        """
        request = CaptureCountEstimateRequest(
            start_time=start_time,
            end_time=end_time,
            interval_seconds=interval_seconds,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
        )
        return await self.calculate_capture_count_for_duration(request)

    async def is_within_time_window(
        self,
        current_time: datetime,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
    ) -> bool:
        """
        Check if current time is within the camera's operational time window.

        This method provides the interface expected by SchedulingService for
        comprehensive capture readiness validation.

        Args:
            current_time: Current datetime to check
            window_start: Window start time string (HH:MM:SS format)
            window_end: Window end time string (HH:MM:SS format)

        Returns:
            True if current time is within the operational window, False otherwise
        """
        try:
            # No time window configured - always within window
            if not window_start or not window_end:
                return True

            # Validate and parse time window
            validation_result = await self.validate_time_window(
                window_start, window_end
            )
            if not validation_result.is_valid:
                logger.warning(
                    f"Invalid time window configuration: {validation_result.error_message}"
                )
                return False

            # Parse validated time objects
            if not validation_result.start_time or not validation_result.end_time:
                return False

            start_time_obj = datetime.strptime(
                validation_result.start_time, "%H:%M:%S"
            ).time()
            end_time_obj = datetime.strptime(
                validation_result.end_time, "%H:%M:%S"
            ).time()

            # Use the core time-in-window logic
            return self.is_time_in_window(
                current_time.time(), start_time_obj, end_time_obj
            )

        except Exception as e:
            logger.error(f"Failed to check time window status: {e}")
            return False


class SyncTimeWindowService:
    """
    Sync time window service for worker processes using composition pattern.

    This service provides time window functionality for worker processes
    that require synchronous database operations.
    """

    def __init__(self, db: SyncDatabase, settings_service=None):
        """
        Initialize SyncTimeWindowService with sync database instance and settings service.

        Args:
            db: SyncDatabase instance
            settings_service: Optional SyncSettingsService instance for dependency injection
        """
        self.db = db
        self.settings_service = settings_service

    def _get_setting(self, key: str):
        """Helper method to get settings through proper dependency injection (sync version)."""
        if self.settings_service:
            return self.settings_service.get_setting(key)
        else:
            # Log warning when settings service is not available
            logger.warning(f"Settings service not available for key: {key}")
            return None

    def _get_time_window_settings(self) -> dict:
        """Get time window settings from database using proper operations layer (sync version)."""
        try:
            # Use helper method for consistent settings access
            validation_timeout = self._get_setting(
                "time_window_validation_timeout_seconds"
            )
            grace_period = self._get_setting(
                "time_window_grace_period_seconds"
            )

            return {
                "validation_timeout_seconds": (
                    int(validation_timeout)
                    if validation_timeout
                    else DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS
                ),
                "grace_period_seconds": (
                    int(grace_period)
                    if grace_period
                    else DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS
                ),
            }
        except Exception as e:
            logger.warning(f"Failed to get time window settings, using defaults: {e}")
            return {
                "validation_timeout_seconds": DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS,
                "grace_period_seconds": DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS,
            }

    def is_time_in_window(
        self, current_time: time, start_time: time, end_time: time
    ) -> bool:
        """
        Check if current time is within the specified window (sync version).

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
        # Overnight window (e.g., 22:00 - 06:00)
        return current_time >= start_time or current_time <= end_time

    def calculate_daily_window_duration(
        self, start_time: time, end_time: time
    ) -> timedelta:
        """
        Calculate the duration of a daily time window (sync version).

        Args:
            start_time: Window start time
            end_time: Window end time

        Returns:
            Duration as timedelta
        """
        if start_time <= end_time:
            # Normal window
            return datetime.combine(date.min, end_time) - datetime.combine(
                date.min, start_time
            )
        # Overnight window
        return (
            datetime.combine(date.min, time.max)
            - datetime.combine(date.min, start_time)
            + datetime.combine(date.min, end_time)
            - datetime.combine(date.min, time.min)
            + timedelta(seconds=1)
        )

    def validate_time_window(self, start_time: str, end_time: str) -> Tuple[time, time]:
        """
        Validate and parse a time window configuration (sync version).

        Args:
            start_time: Start time string
            end_time: End time string

        Returns:
            Tuple of (start_time, end_time) objects

        Raises:
            ValueError: If time window configuration is invalid
        """
        start_dt = parse_time_string(start_time)
        end_dt = parse_time_string(end_time)
        if start_dt is None or end_dt is None:
            raise ValueError(f"Invalid time window: could not parse start or end time.")
        return start_dt.time(), end_dt.time()

    def calculate_next_window_start(
        self,
        current_time: datetime,
        window_start: time,
        window_end: time,
    ) -> datetime:
        """
        Calculate when the next time window starts (sync version).
        """
        current_time_only = current_time.time()

        # Create datetime for window start today
        window_start_today = datetime.combine(current_time.date(), window_start)
        window_start_today = window_start_today.replace(tzinfo=current_time.tzinfo)

        if self.is_time_in_window(current_time_only, window_start, window_end):
            # Currently in window, next start is tomorrow
            return window_start_today + create_time_delta(days=1)
        elif current_time_only < window_start:
            # Before today's window
            return window_start_today
        else:
            # After today's window
            return window_start_today + create_time_delta(days=1)

    def calculate_next_window_end(
        self,
        current_time: datetime,
        window_start: time,
        window_end: time,
    ) -> datetime:
        """
        Calculate when the current/next time window ends (sync version).
        """
        current_time_only = current_time.time()
        window_end_today = datetime.combine(current_time.date(), window_end)
        window_end_today = window_end_today.replace(tzinfo=current_time.tzinfo)

        if window_start <= window_end:
            # Normal window
            if current_time_only <= window_end:
                return window_end_today
            else:
                return window_end_today + create_time_delta(days=1)
        else:
            # Overnight window
            if current_time_only <= window_end:
                return window_end_today
            elif current_time_only >= window_start:
                return window_end_today + create_time_delta(days=1)
            else:
                return window_end_today

    def get_window_status_simple(
        self,
        current_time: datetime,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
    ) -> dict:
        """
        Get time window status (sync version) returning dictionary for compatibility.

        Args:
            current_time: Current datetime
            window_start: Window start time string (HH:MM:SS)
            window_end: Window end time string (HH:MM:SS)

        Returns:
            Dictionary with window status information
        """
        status = {
            "is_active": True,
            "next_start": None,
            "next_end": None,
            "window_duration": None,
            "has_window": False,
        }

        # No time window configured
        if not window_start or not window_end:
            return status

        try:
            window_start_time, window_end_time = self.validate_time_window(
                window_start, window_end
            )

            status["has_window"] = True
            current_time_only = current_time.time()

            # Check if currently in window
            status["is_active"] = self.is_time_in_window(
                current_time_only, window_start_time, window_end_time
            )

            # Calculate next transitions
            if status["is_active"]:
                status["next_end"] = self.calculate_next_window_end(
                    current_time, window_start_time, window_end_time
                )
            else:
                status["next_start"] = self.calculate_next_window_start(
                    current_time, window_start_time, window_end_time
                )

            # Calculate window duration
            duration = self.calculate_daily_window_duration(
                window_start_time, window_end_time
            )
            status["window_duration"] = int(duration.total_seconds())

            # Broadcast SSE event for window status calculation (sync)
            # SSE broadcasting removed - now handled in router layer

            return status

        except Exception as e:
            logger.error(f"Failed to get window status (sync): {e}")
            return {
                "is_active": False,
                "has_window": False,
                "next_start": None,
                "next_end": None,
                "window_duration": None,
            }

    def calculate_capture_count_for_duration(
        self,
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int,
        time_window_start: Optional[str] = None,
        time_window_end: Optional[str] = None,
    ) -> int:
        """
        Calculate expected number of captures for a given duration and time window (sync version).
        """
        try:
            total_seconds = int((end_time - start_time).total_seconds())

            if not time_window_start or not time_window_end:
                # No time window restrictions
                return max(0, total_seconds // interval_seconds)

            # Validate time window
            window_start_time, window_end_time = self.validate_time_window(
                time_window_start, time_window_end
            )

            # Calculate captures per day within time window
            duration = self.calculate_daily_window_duration(
                window_start_time, window_end_time
            )
            window_duration_seconds = int(duration.total_seconds())
            captures_per_day = window_duration_seconds // interval_seconds

            # Calculate number of days
            total_days = (end_time.date() - start_time.date()).days + 1
            estimated_captures = max(0, int(captures_per_day * total_days))

            # Broadcast SSE event for capture count estimation (sync)
            # SSE broadcasting removed - now handled in router layer

            return estimated_captures

        except Exception as e:
            logger.error(f"Failed to calculate capture count (sync): {e}")
            return 0

    def is_within_time_window(
        self,
        current_time: datetime,
        window_start: Optional[str] = None,
        window_end: Optional[str] = None,
    ) -> bool:
        """
        Check if current time is within the camera's operational time window (sync version).

        This method provides the interface expected by SyncSchedulingService for
        comprehensive capture readiness validation.

        Args:
            current_time: Current datetime to check
            window_start: Window start time string (HH:MM:SS format)
            window_end: Window end time string (HH:MM:SS format)

        Returns:
            True if current time is within the operational window, False otherwise
        """
        try:
            # No time window configured - always within window
            if not window_start or not window_end:
                return True

            # Validate and parse time window
            start_time_obj, end_time_obj = self.validate_time_window(
                window_start, window_end
            )

            # Use the core time-in-window logic
            return self.is_time_in_window(
                current_time.time(), start_time_obj, end_time_obj
            )

        except Exception as e:
            logger.error(f"Failed to check time window status (sync): {e}")
            return False


# Backwards compatibility aliases
TimeWindowService = TimeWindowService
SyncTimeWindowService = SyncTimeWindowService
