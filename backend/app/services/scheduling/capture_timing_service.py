# backend/app/services/scheduling/capture_timing_service.py
"""
Capture Timing Service - Composition-based architecture.

This service handles camera capture timing calculations using dependency injection
for database operations, providing type-safe Pydantic model interfaces.

Business logic for camera capture timing, intervals, and scheduling calculations.
This service handles all timing-related business rules and constraints.

Key Features:
- Calculate when next captures should occur
- Determine capture counts for durations
- Validate business constraints for capture intervals
- Apply timing logic with time windows
- SSE broadcasting for timing events
- Frontend settings integration

Business Rules:
- Minimum capture interval: configurable via settings
- Maximum capture interval: configurable via settings
- Timing respects camera time windows
- Handles timezone-aware timing calculations
"""

from datetime import datetime, time
from typing import TYPE_CHECKING, Optional

from ...enums import LoggerName, LogSource
from ...services.logger import get_service_logger


from ...constants import (
    CAMERA_HEALTH_OFFLINE,
    DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS,
    MAX_CAPTURE_INTERVAL_SECONDS,
    MIN_CAPTURE_INTERVAL_SECONDS,
)
from ...database.core import AsyncDatabase, SyncDatabase
from ...models.shared_models import (
    CaptureCountEstimate,
    CaptureDueCheckResult,
    CaptureReadinessValidationResult,
    CaptureValidationResult,
    NextCaptureResult,
)
from ...utils.time_utils import (
    create_time_delta,
    format_time_object_for_display,
    get_safe_capture_time,
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
    get_timezone_from_cache_async,
)
from .time_window_service import SyncTimeWindowService, TimeWindowService

if TYPE_CHECKING:
    pass

logger = get_service_logger(LoggerName.SCHEDULING_SERVICE, LogSource.SCHEDULER)


class CaptureTimingService:
    """
    Camera capture timing business logic using composition pattern.

    Responsibilities:
    - Next capture time calculations
    - Capture due determination
    - Interval validation with configurable constraints
    - Capture count estimation
    - SSE broadcasting for timing events

    Interactions:
    - Uses SettingsOperations for configuration
    - Uses TimeWindowService for time window logic
    - Broadcasts timing events via SSE
    """

    def __init__(
        self,
        db: AsyncDatabase,
        time_window_service: TimeWindowService,
        settings_service,
    ):
        """
        Initialize CaptureTimingService with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            time_window_service: TimeWindowService for time window logic
            settings_service: SettingsService for configuration access
        """
        self.db = db
        self.time_window_service = time_window_service
        self.settings_service = settings_service

    async def _get_timing_settings(self) -> dict:
        """Get timing settings from database using proper operations layer."""
        try:
            min_interval = await self.settings_service.get_setting(
                "min_capture_interval_seconds"
            )
            max_interval = await self.settings_service.get_setting(
                "max_capture_interval_seconds"
            )
            grace_period = await self.settings_service.get_setting(
                "capture_grace_period_seconds"
            )

            # Safe int conversions with defaults
            min_interval_seconds = MIN_CAPTURE_INTERVAL_SECONDS
            if min_interval:
                try:
                    min_interval_seconds = int(min_interval)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid min_capture_interval_seconds '{min_interval}', using default {MIN_CAPTURE_INTERVAL_SECONDS}"
                    )

            max_interval_seconds = MAX_CAPTURE_INTERVAL_SECONDS
            if max_interval:
                try:
                    max_interval_seconds = int(max_interval)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid max_capture_interval_seconds '{max_interval}', using default {MAX_CAPTURE_INTERVAL_SECONDS}"
                    )

            grace_period_seconds = DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS
            if grace_period:
                try:
                    grace_period_seconds = int(grace_period)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid capture_grace_period_seconds '{grace_period}', using default {DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS}"
                    )

            return {
                "min_interval_seconds": min_interval_seconds,
                "max_interval_seconds": max_interval_seconds,
                "grace_period_seconds": grace_period_seconds,
            }
        except Exception as e:
            logger.warning(f"Failed to get timing settings, using defaults: {e}")
            return {
                "min_interval_seconds": MIN_CAPTURE_INTERVAL_SECONDS,
                "max_interval_seconds": MAX_CAPTURE_INTERVAL_SECONDS,
                "grace_period_seconds": DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS,
            }

    async def calculate_next_capture_time(
        self,
        current_time: datetime,
        interval_seconds: int,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
    ) -> datetime:
        """
        Calculate next capture time considering interval, time windows, and DST transitions.

        Business logic: Determines when the next camera capture should occur
        based on the configured interval and any time window restrictions.

        DST Safety: Automatically adjusts for daylight saving time transitions
        to prevent captures during non-existent times or duplicate captures.

        Args:
            current_time: Current timezone-aware datetime
            interval_seconds: Capture interval in seconds
            start_time: Optional window start time
            end_time: Optional window end time

        Returns:
            Next capture datetime (safe for DST transitions)
        """
        # Calculate base next capture time
        next_capture = current_time + create_time_delta(seconds=interval_seconds)

        # Check for DST transitions and get safe capture time
        try:
            timezone_str = await get_timezone_from_cache_async(self.settings_service)
            safe_capture_time = get_safe_capture_time(next_capture, timezone_str)
            if safe_capture_time:
                next_capture = safe_capture_time
        except Exception:
            # If DST check fails, proceed with original time
            pass

        # If no time window, return the calculated time
        if start_time is None or end_time is None:
            return next_capture

        next_time = next_capture.time()
        if self.time_window_service.is_time_in_window(next_time, start_time, end_time):
            return next_capture

        # Otherwise, move to next window start
        next_date = next_capture.date()

        # Create datetime for window start on the next capture date
        window_start = datetime.combine(next_date, start_time)
        window_start = window_start.replace(tzinfo=current_time.tzinfo)
        return window_start

    async def calculate_capture_count_for_duration(
        self,
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
    ) -> CaptureCountEstimate:
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
            CaptureCountEstimate with detailed calculation results
        """
        total_seconds = int((end_time - start_time).total_seconds())

        if time_window_start is None or time_window_end is None:
            # No time window restrictions
            estimated_captures = max(0, total_seconds // interval_seconds)
            return CaptureCountEstimate(
                start_time=start_time,
                end_time=end_time,
                interval_seconds=interval_seconds,
                estimated_captures=estimated_captures,
                total_period_seconds=total_seconds,
                window_restricted=False,
            )

        # Calculate captures per day within time window
        window_duration = self.time_window_service.calculate_daily_window_duration(
            time_window_start, time_window_end
        )
        captures_per_day = window_duration.total_seconds() // interval_seconds

        # Calculate number of days
        total_days = (end_time.date() - start_time.date()).days + 1
        estimated_captures = max(0, int(captures_per_day * total_days))

        return CaptureCountEstimate(
            start_time=start_time,
            end_time=end_time,
            interval_seconds=interval_seconds,
            estimated_captures=estimated_captures,
            total_period_seconds=total_seconds,
            time_window_start=(
                format_time_object_for_display(time_window_start)
                if time_window_start
                else None
            ),
            time_window_end=(
                format_time_object_for_display(time_window_end)
                if time_window_end
                else None
            ),
            window_restricted=True,
            captures_per_day=float(captures_per_day),
        )

    async def validate_capture_interval(
        self, interval_seconds: int
    ) -> CaptureValidationResult:
        """
        Validate capture interval is within business constraints.

        Uses configurable business rules from frontend settings:
        - Minimum interval: configurable (prevents system overload)
        - Maximum interval: configurable (reasonable upper bound)

        Args:
            interval_seconds: Interval in seconds

        Returns:
            CaptureValidationResult with validation details
        """
        settings = await self._get_timing_settings()
        min_interval = settings["min_interval_seconds"]
        max_interval = settings["max_interval_seconds"]

        validation_error = None
        is_valid = True

        if interval_seconds < min_interval:
            validation_error = (
                f"Capture interval too short: minimum {min_interval} seconds"
            )
            is_valid = False
        elif interval_seconds > max_interval:
            validation_error = (
                f"Capture interval too long: maximum {max_interval} seconds"
            )
            is_valid = False

        return CaptureValidationResult(
            original_interval_seconds=interval_seconds,
            validated_interval_seconds=interval_seconds if is_valid else min_interval,
            is_valid=is_valid,
            validation_error=validation_error,
            adjusted=not is_valid,
        )

    async def calculate_next_capture_for_camera(
        self,
        camera_id: int,
        last_capture_time: Optional[datetime],
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        current_time: Optional[datetime] = None,
    ) -> NextCaptureResult:
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
            NextCaptureResult with detailed calculation results
        """
        if current_time is None:
            current_time = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

        if last_capture_time is None:
            # First capture - check if we're in time window
            if time_window_start and time_window_end:
                current_time_only = current_time.time()
                if self.time_window_service.is_time_in_window(
                    current_time_only, time_window_start, time_window_end
                ):
                    next_capture_time = current_time
                else:
                    # Move to next window start
                    next_capture_time = await self.calculate_next_capture_time(
                        current_time, 0, time_window_start, time_window_end
                    )
            else:
                next_capture_time = current_time
        else:
            # Calculate next capture based on last capture
            next_capture_time = await self.calculate_next_capture_time(
                last_capture_time, interval_seconds, time_window_start, time_window_end
            )

        # Calculate time until next capture
        time_until_next_seconds = max(
            0, int((next_capture_time - current_time).total_seconds())
        )

        # Check if capture is due now
        is_due = await self._is_capture_due_internal(
            last_capture_time,
            interval_seconds,
            time_window_start,
            time_window_end,
            current_time,
        )

        result = NextCaptureResult(
            camera_id=camera_id,
            next_capture_time=next_capture_time,
            last_capture_time=last_capture_time,
            interval_seconds=interval_seconds,
            time_window_start=(
                format_time_object_for_display(time_window_start)
                if time_window_start
                else None
            ),
            time_window_end=(
                format_time_object_for_display(time_window_end)
                if time_window_end
                else None
            ),
            is_due=is_due,
            time_until_next_seconds=time_until_next_seconds,
        )

        # SSE broadcasting handled by dedicated service layer (removed from core business logic)

        return result

    async def _is_capture_due_internal(
        self,
        last_capture_time: Optional[datetime],
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Internal helper for capture due determination."""
        if current_time is None:
            current_time = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

        settings = await self._get_timing_settings()
        grace_period_seconds = settings["grace_period_seconds"]

        # Check time window first
        if time_window_start and time_window_end:
            current_time_only = current_time.time()
            if not self.time_window_service.is_time_in_window(
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

    async def is_capture_due(
        self,
        camera_id: int,
        last_capture_time: Optional[datetime],
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        current_time: Optional[datetime] = None,
    ) -> CaptureDueCheckResult:
        """
        Determine if a capture is due for a camera.

        Business logic: Checks if enough time has passed since last capture
        and if we're currently within any time window restrictions.

        Args:
            camera_id: Camera identifier
            last_capture_time: When camera last captured
            interval_seconds: Camera's capture interval
            time_window_start: Camera's time window start
            time_window_end: Camera's time window end
            current_time: Current time (defaults to now)

        Returns:
            CaptureDueCheckResult with detailed due check results
        """
        if current_time is None:
            current_time = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

        settings = await self._get_timing_settings()
        grace_period_seconds = settings["grace_period_seconds"]

        is_due = await self._is_capture_due_internal(
            last_capture_time,
            interval_seconds,
            time_window_start,
            time_window_end,
            current_time,
        )

        # Calculate next capture time
        next_capture_time = await self.calculate_next_capture_time(
            last_capture_time or current_time,
            interval_seconds,
            time_window_start,
            time_window_end,
        )

        # Calculate time since last capture
        time_since_last_seconds = None
        reason = None

        if last_capture_time is None:
            reason = (
                "First capture - due immediately"
                if is_due
                else "First capture - waiting for time window"
            )
        else:
            if last_capture_time is not None:
                time_since_last_seconds = int(
                    (current_time - last_capture_time).total_seconds()
                )
            else:
                time_since_last_seconds = None
            if not is_due:
                if time_window_start and time_window_end:
                    current_time_only = current_time.time()
                    if not self.time_window_service.is_time_in_window(
                        current_time_only, time_window_start, time_window_end
                    ):
                        reason = "Outside time window"
                    else:
                        reason = f"Interval not reached (need {interval_seconds - grace_period_seconds}s)"
                else:
                    reason = f"Interval not reached (need {interval_seconds - grace_period_seconds}s)"
            else:
                reason = "Capture is due"

        result = CaptureDueCheckResult(
            camera_id=camera_id,
            is_due=is_due,
            last_capture_time=last_capture_time,
            next_capture_time=next_capture_time,
            interval_seconds=interval_seconds,
            grace_period_seconds=grace_period_seconds,
            time_since_last_seconds=time_since_last_seconds,
            reason=reason,
        )

        # SSE broadcasting handled by dedicated service layer (removed from core business logic)

        return result


class SyncCaptureTimingService:
    """
    Sync capture timing service for worker processes using composition pattern.

    This service orchestrates timing-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(
        self,
        db: SyncDatabase,
        async_db: AsyncDatabase,
        time_window_service: SyncTimeWindowService,
        settings_service,
    ):
        """
        Initialize SyncCaptureTimingService with sync database instance.

        Args:
            db: SyncDatabase instance
            async_db: AsyncDatabase instance (required for some operations)
            time_window_service: SyncTimeWindowService for time window logic
            settings_service: SyncSettingsService for configuration access
        """
        self.db = db
        self.async_db = async_db
        self.time_window_service = time_window_service
        self.settings_service = settings_service

    def _get_timing_settings(self) -> dict:
        """Get timing settings from database using proper operations layer (sync version)."""
        try:
            min_interval = self.settings_service.get_setting(
                "min_capture_interval_seconds"
            )
            max_interval = self.settings_service.get_setting(
                "max_capture_interval_seconds"
            )
            grace_period = self.settings_service.get_setting(
                "capture_grace_period_seconds"
            )

            return {
                "min_interval_seconds": (
                    int(min_interval) if min_interval else MIN_CAPTURE_INTERVAL_SECONDS
                ),
                "max_interval_seconds": (
                    int(max_interval) if max_interval else MAX_CAPTURE_INTERVAL_SECONDS
                ),
                "grace_period_seconds": (
                    int(grace_period)
                    if grace_period
                    else DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS
                ),
            }
        except Exception as e:
            logger.warning(f"Failed to get timing settings, using defaults: {e}")
            return {
                "min_interval_seconds": MIN_CAPTURE_INTERVAL_SECONDS,
                "max_interval_seconds": MAX_CAPTURE_INTERVAL_SECONDS,
                "grace_period_seconds": DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS,
            }

    def validate_capture_interval(self, interval_seconds: int) -> int:
        """
        Validate capture interval is within business constraints (sync version).

        Args:
            interval_seconds: Interval in seconds

        Returns:
            Validated interval

        Raises:
            ValueError: If interval violates business constraints
        """
        settings = self._get_timing_settings()
        min_interval = settings["min_interval_seconds"]
        max_interval = settings["max_interval_seconds"]

        if interval_seconds < min_interval:
            raise ValueError(
                f"Capture interval too short: minimum {min_interval} seconds"
            )
        if interval_seconds > max_interval:
            raise ValueError(
                f"Capture interval too long: maximum {max_interval} seconds"
            )
        return interval_seconds

    def is_capture_due(
        self,
        last_capture_time: Optional[datetime],
        interval_seconds: int,
        time_window_start: Optional[time] = None,
        time_window_end: Optional[time] = None,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Determine if a capture is due for a camera (sync version).

        Args:
            last_capture_time: When camera last captured
            interval_seconds: Camera's capture interval
            time_window_start: Camera's time window start
            time_window_end: Camera's time window end
            current_time: Current time (defaults to now)

        Returns:
            True if capture is due
        """
        if current_time is None:
            current_time = get_timezone_aware_timestamp_sync(self.settings_service)

        settings = self._get_timing_settings()
        grace_period_seconds = settings["grace_period_seconds"]

        # Check time window first
        if time_window_start and time_window_end:
            current_time_only = current_time.time()
            if not self.time_window_service.is_time_in_window(
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

    def calculate_next_capture_time(
        self,
        current_time: datetime,
        interval_seconds: int,
    ) -> datetime:
        """
        Calculate next capture time for sync operations.

        Args:
            current_time: Current datetime
            interval_seconds: Capture interval in seconds

        Returns:
            Next capture datetime
        """
        return current_time + create_time_delta(seconds=interval_seconds)

    def validate_capture_readiness(
        self, camera_id: int, timelapse_id: int
    ) -> CaptureReadinessValidationResult:
        """
        Comprehensive validation for capture readiness - implements scheduler trust model.

        This method performs ALL validation checks so that workers can trust scheduler
        decisions and skip redundant validation.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier

        Returns:
            CaptureValidationResult with validation status and details
        """
        try:
            # Import here to avoid circular imports
            from ...database.camera_operations import SyncCameraOperations
            from ...database.timelapse_operations import SyncTimelapseOperations

            camera_ops = SyncCameraOperations(self.db, self.async_db)
            timelapse_ops = SyncTimelapseOperations(self.db)

            # Step 0: Extract camera_id from timelapse if camera_id=0 (scheduler convenience)
            if camera_id == 0:
                timelapse = timelapse_ops.get_timelapse_by_id(timelapse_id)
                if not timelapse:
                    return CaptureReadinessValidationResult(
                        valid=False,
                        error=f"Timelapse {timelapse_id} not found (needed to extract camera_id)",
                        error_type="timelapse_not_found",
                    )
                camera_id = timelapse.camera_id

            # Step 1: Validate camera exists and is enabled
            camera = camera_ops.get_camera_by_id(camera_id)
            if not camera:
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Camera {camera_id} not found",
                    error_type="camera_not_found",
                )

            if camera.status != "active":
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Camera {camera_id} is disabled (status: {camera.status})",
                    error_type="camera_disabled",
                )

            # Step 2: Validate camera health status
            if camera.health_status == CAMERA_HEALTH_OFFLINE:
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Camera {camera_id} is offline",
                    error_type="camera_offline",
                )

            # Step 3: Validate timelapse exists and is active
            timelapse = timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Timelapse {timelapse_id} not found",
                    error_type="timelapse_not_found",
                )

            if timelapse.status not in ["running", "active"]:
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Timelapse {timelapse_id} is not active (status: {timelapse.status})",
                    error_type="timelapse_not_active",
                )

            # Step 4: Validate capture timing (is capture due?)
            current_time = get_timezone_aware_timestamp_sync(self.settings_service)

            # Get last capture time for this camera
            last_capture_time = camera.last_capture_at
            capture_interval = timelapse.capture_interval_seconds

            # Convert time window strings to time objects
            time_window_start = None
            time_window_end = None
            if timelapse.time_window_start:
                try:
                    hour, minute = map(int, timelapse.time_window_start.split(":"))
                    time_window_start = time(hour, minute)
                except (ValueError, AttributeError):
                    logger.warning(
                        f"Invalid time_window_start format: {timelapse.time_window_start}"
                    )

            if timelapse.time_window_end:
                try:
                    hour, minute = map(int, timelapse.time_window_end.split(":"))
                    time_window_end = time(hour, minute)
                except (ValueError, AttributeError):
                    logger.warning(
                        f"Invalid time_window_end format: {timelapse.time_window_end}"
                    )

            if last_capture_time and not self.is_capture_due(
                last_capture_time=last_capture_time,
                interval_seconds=capture_interval,
                time_window_start=time_window_start,
                time_window_end=time_window_end,
                current_time=current_time,
            ):
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Capture not due yet for camera {camera_id}",
                    error_type="capture_not_due",
                )

            # Step 5: Validate time window constraints
            if not self.time_window_service.is_within_time_window(
                current_time=current_time,
                window_start=timelapse.time_window_start,
                window_end=timelapse.time_window_end,
            ):
                return CaptureReadinessValidationResult(
                    valid=False,
                    error=f"Current time outside camera {camera_id} time window",
                    error_type="outside_time_window",
                )

            # All validation passed
            return CaptureReadinessValidationResult(
                valid=True,
                camera=camera,
                timelapse=timelapse,
                next_capture_time=self.calculate_next_capture_time(
                    current_time=current_time, interval_seconds=capture_interval
                ),
            )

        except Exception as e:
            logger.error(
                f"Error validating capture readiness for camera {camera_id}: {e}"
            )
            return CaptureReadinessValidationResult(
                valid=False,
                error=f"Validation error: {str(e)}",
                error_type="validation_error",
            )


# Backwards compatibility aliases
SchedulingService = CaptureTimingService
SyncSchedulingService = SyncCaptureTimingService
