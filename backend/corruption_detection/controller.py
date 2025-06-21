"""
Corruption Controller - Central Orchestrator

Main interface for the corruption detection system. Coordinates
fast detection, heavy detection, scoring, retry logic, and health monitoring.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple

from .models import CorruptionResult
from .fast_detector import FastDetector, FastDetectionResult
from .heavy_detector import HeavyDetector
from .score_calculator import ScoreCalculator, CorruptionScore
from .health_monitor import HealthMonitor


class CorruptionController:
    """Central controller for corruption detection system"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, sync_db=None):
        """Initialize corruption controller with configuration and database connection"""
        self.config = config or self._get_default_config()
        self.fast_detector = FastDetector()
        self.heavy_detector = HeavyDetector()
        self.score_calculator = ScoreCalculator()
        self.health_monitor = HealthMonitor(sync_db) if sync_db else None
        self.logger = logging.getLogger(__name__)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for corruption controller"""
        return {
            "corruption_detection_enabled": True,
            "corruption_score_threshold": 70,
            "corruption_auto_discard_enabled": False,
            "heavy_detection_enabled": False,  # Phase 2
            "retry_enabled": True,
            "max_retries": 1,
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update configuration from database settings"""
        self.config.update(new_config)
        self.logger.debug(f"Updated corruption detection config: {self.config}")

    def evaluate_frame(
        self,
        frame,
        file_path: Optional[str] = None,
        camera_id: Optional[int] = None,
        heavy_detection_enabled: Optional[bool] = None,
    ) -> CorruptionResult:
        """
        Evaluate a captured frame for corruption

        Args:
            frame: numpy array from cv2.VideoCapture
            file_path: optional file path for size checks
            camera_id: camera ID for logging
            heavy_detection_enabled: override for per-camera heavy detection setting

        Returns:
            CorruptionResult with evaluation details
        """
        if not self.config.get("corruption_detection_enabled", True):
            return self._create_skipped_result()

        try:
            start_time = time.time()

            # Run fast detection (always enabled)
            fast_result = self.fast_detector.analyze_frame(frame, file_path)
            fast_time = time.time() - start_time

            # Run heavy detection if enabled
            heavy_result = None
            heavy_time = 0

            # Check if heavy detection should run
            should_run_heavy = heavy_detection_enabled
            if should_run_heavy is None:
                should_run_heavy = self.config.get("heavy_detection_enabled", False)

            if should_run_heavy:
                heavy_start = time.time()
                heavy_result = self.heavy_detector.analyze(frame)
                heavy_time = time.time() - heavy_start
                self.logger.debug(
                    f"Camera {camera_id}: Heavy detection completed in {heavy_time*1000:.1f}ms"
                )

            # Calculate corruption score with weighted combination
            corruption_score = self.score_calculator.calculate_combined_score(
                fast_result=fast_result,
                heavy_result=heavy_result,
                threshold=self.config.get("corruption_score_threshold", 70),
            )

            # Determine if image is acceptable
            is_valid = not corruption_score.is_corrupted
            action = "saved" if is_valid else "discarded"

            # Add timing information to details
            corruption_score.details.update(
                {
                    "fast_detection_time_ms": round(fast_time * 1000, 2),
                    "heavy_detection_time_ms": (
                        round(heavy_time * 1000, 2) if heavy_result else None
                    ),
                    "total_processing_time_ms": round(
                        (time.time() - start_time) * 1000, 2
                    ),
                    "heavy_detection_used": heavy_result is not None,
                }
            )

            result = CorruptionResult(
                is_valid=is_valid,
                score=corruption_score.final_score,
                action_taken=action,
                corruption_score=corruption_score,
                retry_attempted=False,
                retry_result=None,
            )

            # Log the evaluation
            self._log_evaluation(camera_id, result)

            return result

        except Exception as e:
            self.logger.error(
                f"Corruption evaluation failed for camera {camera_id}: {e}"
            )
            return self._create_error_result(str(e))

    def evaluate_with_retry(
        self,
        capture_func,
        file_path: Optional[str] = None,
        camera_id: Optional[int] = None,
        heavy_detection_enabled: Optional[bool] = None,
    ) -> CorruptionResult:
        """
        Evaluate frame with retry logic

        Args:
            capture_func: Function that captures a new frame
            file_path: file path for the captured image
            camera_id: camera ID for logging
            heavy_detection_enabled: override for per-camera heavy detection setting

        Returns:
            CorruptionResult with retry information
        """
        if not self.config.get("retry_enabled", True):
            # Just do single evaluation
            frame = capture_func()
            return self.evaluate_frame(
                frame, file_path, camera_id, heavy_detection_enabled
            )

        # First attempt
        frame = capture_func()
        first_result = self.evaluate_frame(
            frame, file_path, camera_id, heavy_detection_enabled
        )

        # If first attempt is valid, return it
        if first_result.is_valid:
            return first_result

        # If retry is not enabled for low scores, return first result
        max_retries = self.config.get("max_retries", 1)
        if max_retries <= 0:
            return first_result

        self.logger.info(
            f"Camera {camera_id}: First capture failed (score: {first_result.score}), attempting retry"
        )

        try:
            # Immediate retry
            retry_frame = capture_func()
            retry_result = self.evaluate_frame(
                retry_frame, file_path, camera_id, heavy_detection_enabled
            )

            # Update first result with retry information
            first_result.retry_attempted = True
            first_result.retry_result = retry_result

            # If retry succeeded, update action
            if retry_result.is_valid:
                first_result.action_taken = "retried_success"
                first_result.is_valid = True
                first_result.score = retry_result.score
                self.logger.info(
                    f"Camera {camera_id}: Retry successful (score: {retry_result.score})"
                )
            else:
                first_result.action_taken = "retried_failed"
                self.logger.warning(
                    f"Camera {camera_id}: Retry also failed (score: {retry_result.score})"
                )

            return first_result

        except Exception as e:
            self.logger.error(f"Retry failed for camera {camera_id}: {e}")
            first_result.retry_attempted = True
            first_result.action_taken = "retry_error"
            return first_result

    def _create_skipped_result(self) -> CorruptionResult:
        """Create result for when corruption detection is disabled"""
        return CorruptionResult(
            is_valid=True,
            score=100,
            action_taken="skipped_disabled",
            corruption_score=CorruptionScore(
                final_score=100,
                fast_score=100,
                heavy_score=None,
                is_corrupted=False,
                threshold_used=70,
                details={"detection_disabled": True},
            ),
            retry_attempted=False,
            retry_result=None,
        )

    def _create_error_result(self, error_message: str) -> CorruptionResult:
        """Create result for when evaluation fails"""
        return CorruptionResult(
            is_valid=True,  # Assume valid if detection fails
            score=100,
            action_taken="saved_with_error",
            corruption_score=CorruptionScore(
                final_score=100,
                fast_score=100,
                heavy_score=None,
                is_corrupted=False,
                threshold_used=70,
                details={"error": error_message},
            ),
            retry_attempted=False,
            retry_result=None,
        )

    def _log_evaluation(self, camera_id: Optional[int], result: CorruptionResult):
        """Log corruption evaluation result"""
        level = logging.WARNING if not result.is_valid else logging.DEBUG

        self.logger.log(
            level,
            f"Camera {camera_id}: Corruption evaluation - "
            f"Score: {result.score}/100, Action: {result.action_taken}, "
            f"Valid: {result.is_valid}",
        )

        if not result.is_valid:
            failed_checks = result.corruption_score.details.get(
                "fast_failed_checks", []
            )
            if failed_checks:
                self.logger.warning(
                    f"Camera {camera_id}: Failed checks: {', '.join(failed_checks)}"
                )
