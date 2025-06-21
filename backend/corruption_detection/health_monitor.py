"""
Health Monitor - Camera Degradation Tracking

Monitors camera corruption patterns and manages degraded mode detection.
Implements the degraded mode triggers specified in the corruption detection system.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .models import CorruptionResult


@dataclass
class FailureStats:
    """Camera failure statistics for degraded mode detection"""

    consecutive_failures: int
    failures_in_time_window: int
    total_recent_captures: int
    failure_percentage: float
    last_degraded_at: Optional[datetime]
    is_degraded: bool


class HealthMonitor:
    """
    Monitors camera health and manages degraded mode detection.

    Implements three degraded mode triggers:
    1. Consecutive failures ≥ threshold (default: 10)
    2. Failures in time window ≥ threshold (default: 5 failures in 30 minutes)
    3. Failure percentage over recent captures ≥ threshold (default: >50% in 20 captures)
    """

    def __init__(self, sync_db):
        """Initialize health monitor with database connection"""
        self.sync_db = sync_db
        self.logger = logging.getLogger(__name__)

    def track_corruption_result(
        self, camera_id: int, result: CorruptionResult
    ) -> Dict[str, Any]:
        """
        Track a corruption detection result and check for degraded mode triggers

        Args:
            camera_id: ID of the camera
            result: CorruptionResult from corruption detection

        Returns:
            Dict containing health status changes and actions taken
        """
        try:
            # Log the corruption result
            self.sync_db.log_corruption_result(camera_id, result)

            # Update failure count based on result
            is_success = result.is_valid
            self.sync_db.update_camera_corruption_failure_count(camera_id, is_success)

            # Check if camera should enter degraded mode
            should_be_degraded = self.check_degraded_mode_triggers(camera_id)

            # Get current degraded status
            current_stats = self.sync_db.get_camera_corruption_failure_stats(camera_id)
            current_degraded = current_stats.get("degraded_mode_active", False)

            health_changes = {
                "degraded_mode_changed": False,
                "auto_disabled": False,
                "previous_degraded": current_degraded,
                "new_degraded": should_be_degraded,
                "consecutive_failures": current_stats.get(
                    "consecutive_corruption_failures", 0
                ),
            }

            # Handle degraded mode state changes
            if should_be_degraded and not current_degraded:
                # Entering degraded mode
                self.logger.warning(f"Camera {camera_id} entering degraded mode")
                self._enter_degraded_mode(camera_id)
                health_changes["degraded_mode_changed"] = True

                # Check if auto-disable is enabled
                if self.should_auto_disable_camera(camera_id):
                    self.logger.warning(
                        f"Auto-disabling camera {camera_id} due to persistent corruption"
                    )
                    self.sync_db.set_camera_degraded_mode(
                        camera_id, True, auto_disable=True
                    )
                    health_changes["auto_disabled"] = True

                    # Broadcast camera disabled event
                    self.sync_db.broadcast_event(
                        {
                            "type": "camera_status_changed",
                            "camera_id": camera_id,
                            "status": "disabled",
                            "reason": "persistent_corruption",
                            "consecutive_failures": health_changes[
                                "consecutive_failures"
                            ],
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                else:
                    self.sync_db.set_camera_degraded_mode(
                        camera_id, True, auto_disable=False
                    )

                # Broadcast degraded mode event
                self.sync_db.broadcast_event(
                    {
                        "type": "camera_degraded_mode_triggered",
                        "camera_id": camera_id,
                        "degraded_mode_active": True,
                        "consecutive_failures": health_changes["consecutive_failures"],
                        "auto_disabled": health_changes["auto_disabled"],
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            elif not should_be_degraded and current_degraded:
                # Exiting degraded mode (recovery)
                self.logger.info(f"Camera {camera_id} recovered from degraded mode")
                self._exit_degraded_mode(camera_id)
                health_changes["degraded_mode_changed"] = True

                # Broadcast recovery event
                self.sync_db.broadcast_event(
                    {
                        "type": "camera_corruption_reset",
                        "camera_id": camera_id,
                        "degraded_mode_active": False,
                        "recovered": True,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Broadcast high-severity corruption events
            if not result.is_valid and result.score < 30:
                self.sync_db.broadcast_event(
                    {
                        "type": "image_corruption_detected",
                        "camera_id": camera_id,
                        "corruption_score": result.score,
                        "action_taken": result.action_taken,
                        "severity": "high",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return health_changes

        except Exception as e:
            self.logger.error(
                f"Error tracking corruption result for camera {camera_id}: {e}"
            )
            return {"error": str(e)}

    def check_degraded_mode_triggers(self, camera_id: int) -> bool:
        """
        Check if camera should be in degraded mode based on failure patterns

        Returns:
            True if camera should be in degraded mode
        """
        try:
            # Get corruption settings
            settings = self.sync_db.get_corruption_settings()
            consecutive_threshold = settings.get(
                "corruption_degraded_consecutive_threshold", 10
            )
            time_window_minutes = settings.get(
                "corruption_degraded_time_window_minutes", 30
            )
            failure_percentage = settings.get(
                "corruption_degraded_failure_percentage", 50
            )

            # Get failure statistics
            stats = self.sync_db.get_camera_corruption_failure_stats(camera_id)

            # Trigger 1: Consecutive failures ≥ threshold
            consecutive_failures = stats.get("consecutive_corruption_failures", 0)
            if consecutive_failures >= consecutive_threshold:
                self.logger.debug(
                    f"Camera {camera_id}: Degraded trigger 1 - {consecutive_failures} consecutive failures (≥{consecutive_threshold})"
                )
                return True

            # Trigger 2: Failures in time window ≥ 5
            failures_in_window = self._get_failures_in_time_window(
                camera_id, time_window_minutes
            )
            if failures_in_window >= 5:
                self.logger.debug(
                    f"Camera {camera_id}: Degraded trigger 2 - {failures_in_window} failures in {time_window_minutes} minutes (≥5)"
                )
                return True

            # Trigger 3: >50% failures in last 20 captures
            recent_failure_rate = self._get_recent_failure_rate(camera_id, 20)
            if recent_failure_rate > (failure_percentage / 100.0):
                self.logger.debug(
                    f"Camera {camera_id}: Degraded trigger 3 - {recent_failure_rate*100:.1f}% failure rate (>{failure_percentage}%)"
                )
                return True

            return False

        except Exception as e:
            self.logger.error(
                f"Error checking degraded mode triggers for camera {camera_id}: {e}"
            )
            return False

    def should_auto_disable_camera(self, camera_id: int) -> bool:
        """Check if camera should be auto-disabled when entering degraded mode"""
        try:
            settings = self.sync_db.get_corruption_settings()
            return settings.get("corruption_auto_disable_degraded", False)
        except Exception as e:
            self.logger.error(f"Error checking auto-disable setting: {e}")
            return False

    def get_failure_statistics(self, camera_id: int) -> FailureStats:
        """Get comprehensive failure statistics for a camera"""
        try:
            stats = self.sync_db.get_camera_corruption_failure_stats(camera_id)

            consecutive_failures = stats.get("consecutive_corruption_failures", 0)
            degraded_mode = stats.get("degraded_mode_active", False)
            last_degraded = stats.get("last_degraded_at")

            # Get time window failures
            settings = self.sync_db.get_corruption_settings()
            time_window_minutes = settings.get(
                "corruption_degraded_time_window_minutes", 30
            )
            failures_in_window = self._get_failures_in_time_window(
                camera_id, time_window_minutes
            )

            # Get recent failure rate
            recent_failure_rate = self._get_recent_failure_rate(camera_id, 20)
            total_recent = 20  # We check last 20 captures for failure rate

            return FailureStats(
                consecutive_failures=consecutive_failures,
                failures_in_time_window=failures_in_window,
                total_recent_captures=total_recent,
                failure_percentage=recent_failure_rate * 100,
                last_degraded_at=last_degraded,
                is_degraded=degraded_mode,
            )

        except Exception as e:
            self.logger.error(
                f"Error getting failure statistics for camera {camera_id}: {e}"
            )
            return FailureStats(0, 0, 0, 0.0, None, False)

    def _enter_degraded_mode(self, camera_id: int):
        """Handle camera entering degraded mode"""
        self.logger.warning(f"Camera {camera_id} entering degraded mode")
        # Database update is handled by caller to control auto-disable logic

    def _exit_degraded_mode(self, camera_id: int):
        """Handle camera exiting degraded mode (recovery)"""
        self.logger.info(f"Camera {camera_id} exiting degraded mode - recovered")
        self.sync_db.set_camera_degraded_mode(camera_id, False, auto_disable=False)

    def _get_failures_in_time_window(self, camera_id: int, window_minutes: int) -> int:
        """Get number of corruption failures in the specified time window"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            return self.sync_db.get_corruption_failures_since(camera_id, cutoff_time)
        except Exception as e:
            self.logger.error(
                f"Error getting failures in time window for camera {camera_id}: {e}"
            )
            return 0

    def _get_recent_failure_rate(self, camera_id: int, capture_count: int) -> float:
        """Get failure rate over the last N captures (0.0 to 1.0)"""
        try:
            return self.sync_db.get_recent_corruption_failure_rate(
                camera_id, capture_count
            )
        except Exception as e:
            self.logger.error(
                f"Error getting recent failure rate for camera {camera_id}: {e}"
            )
            return 0.0

    def reset_degraded_mode(self, camera_id: int) -> bool:
        """
        Manually reset a camera's degraded mode (for admin/troubleshooting)

        Returns:
            True if reset was successful
        """
        try:
            self.logger.info(f"Manually resetting degraded mode for camera {camera_id}")
            self.sync_db.set_camera_degraded_mode(camera_id, False, auto_disable=False)

            # Reset consecutive failure count
            self.sync_db.reset_camera_corruption_failures(camera_id)

            # Broadcast reset event
            self.sync_db.broadcast_event(
                {
                    "type": "camera_corruption_reset",
                    "camera_id": camera_id,
                    "degraded_mode_active": False,
                    "manually_reset": True,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            return True

        except Exception as e:
            self.logger.error(
                f"Error resetting degraded mode for camera {camera_id}: {e}"
            )
            return False
