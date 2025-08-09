# backend/app/services/corruption_pipeline/services/evaluation_service.py
"""
Corruption Evaluation Service

Core business logic for corruption detection and image quality evaluation.
Consolidates evaluation logic from multiple corruption services with improved
architecture and standardized interfaces.

Responsibilities:
- Image quality analysis and scoring
- Fast and heavy detection coordination
- Score calculation and threshold evaluation
- Retry decision logic
- Degraded mode evaluation
- Audit trail management
"""

from typing import Optional

from ....constants import (  # DEFAULT_CORRUPTION_RETRY_ENABLED,  # Unused; DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,  # Unused
    CORRUPTION_CRITICAL_THRESHOLD,
    DEFAULT_CORRUPTION_FALLBACK_SCORE,
)
from ....database.core import AsyncDatabase, SyncDatabase
from ....database.corruption_operations import (
    CorruptionOperations,
    SyncCorruptionOperations,
)
from ....enums import LoggerName, LogSource
from ....models.corruption_model import (
    CorruptionEvaluationResult,
)
from ....services.logger import LogEmoji, get_service_logger
from ..detectors import (
    CorruptionScoreCalculator,
    FastCorruptionDetector,
    HeavyCorruptionDetector,
)
from ..exceptions import (
    CameraHealthError,
    CorruptionDetectionError,
    CorruptionEvaluationError,
    CorruptionSettingsError,
    DegradedModeError,
)
from ..models.corruption_responses import (
    CameraHealthDetails,
    RetryDecision,
)

logger = get_service_logger(LoggerName.CORRUPTION_PIPELINE, LogSource.PIPELINE)


class CorruptionEvaluationService:
    """
    Async corruption evaluation service for API endpoints.

    Provides high-level business logic for corruption detection
    with clean interfaces and proper error handling.
    """

    def __init__(self, db: AsyncDatabase, db_ops=None):
        """Initialize with injected dependencies"""
        self.db = db
        self.db_ops = db_ops or self._get_default_operations()

        # Initialize detectors with default config
        self.fast_detector = FastCorruptionDetector()
        self.heavy_detector = HeavyCorruptionDetector()
        self.score_calculator = CorruptionScoreCalculator()

    def _get_default_operations(self):
        """Fallback to get CorruptionOperations singleton"""
        # This is a sync method in an async class, use direct instantiation
        from ....database.corruption_operations import CorruptionOperations
        return CorruptionOperations(self.db)

    async def evaluate_image_quality(
        self,
        image_path: str,
        camera_id: int,
        image_id: Optional[int] = None,
        capture_attempt: int = 1,
    ) -> CorruptionEvaluationResult:
        """
        Evaluate image quality with complete corruption detection pipeline.

        Args:
            image_path: Path to the image file
            camera_id: ID of the camera that captured the image
            image_id: Optional image ID for logging
            capture_attempt: Capture attempt number for retry logic

        Returns:
            CorruptionEvaluationResult with evaluation details
        """
        try:
            # Service Layer Boundary Pattern - Get raw dictionaries from database layer
            settings_dict = await self.db_ops.get_corruption_settings()

            # Service processes raw dictionaries internally
            if not settings_dict.get("is_enabled", True):
                return CorruptionEvaluationResult(
                    is_valid=True,
                    corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                    action_taken="accepted",
                    detection_disabled=True,
                )

            # Get camera-specific settings - process as raw dictionary
            camera_settings_dict = await self.db_ops.get_camera_corruption_settings(
                camera_id
            )
            heavy_detection_enabled = camera_settings_dict.get(
                "corruption_detection_heavy", False
            )

            # Get camera degraded mode status - process as raw dictionary
            camera_metadata_dict = await self.db_ops.get_camera_corruption_metadata(
                camera_id
            )
            is_degraded = camera_metadata_dict["degraded_mode_active"]
            consecutive_failures = camera_metadata_dict[
                "consecutive_corruption_failures"
            ]

            # Perform fast detection - detectors return dictionaries
            fast_result_dict = self.fast_detector.detect(image_path)

            # Perform heavy detection if enabled and not in degraded mode
            heavy_result_dict = None
            if heavy_detection_enabled and not is_degraded:
                heavy_result_dict = self.heavy_detector.detect(image_path)

            # Calculate final score using raw dictionary data
            heavy_score = (
                heavy_result_dict["corruption_score"] if heavy_result_dict else None
            )
            score_result = self.score_calculator.calculate_final_score(
                fast_score=fast_result_dict["corruption_score"],
                heavy_score=heavy_score,
                health_degraded=is_degraded,
                consecutive_failures=consecutive_failures,
            )

            # Determine if image is valid
            is_valid = not score_result.is_corrupted
            action_taken = "saved" if is_valid else "discarded"

            # TODO: Create SSE event for corruption detection result
            # Should use SSEEventsOperations.create_event() with EVENT_CORRUPTION_DETECTED

            # Service Layer Boundary Pattern - Convert to typed object at boundary
            return CorruptionEvaluationResult(
                is_valid=is_valid,
                corruption_score=int(score_result.final_score),
                fast_score=int(fast_result_dict["corruption_score"]),
                heavy_score=(
                    int(heavy_result_dict["corruption_score"])
                    if heavy_result_dict and heavy_result_dict.get("is_available", True)
                    else None
                ),
                action_taken=action_taken,
                detection_disabled=False,
                processing_time_ms=fast_result_dict["detection_time_ms"]
                + (
                    heavy_result_dict["detection_time_ms"] if heavy_result_dict else 0.0
                ),
                failed_checks=fast_result_dict["failed_checks"]
                + (heavy_result_dict["failed_checks"] if heavy_result_dict else []),
            )

        except CorruptionSettingsError as e:
            logger.error(f"Corruption settings error for {image_path}", exception=e)
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="settings_error",
                detection_disabled=False,
                error=str(e),
            )
        except CorruptionDetectionError as e:
            logger.error(f"Corruption detection error for {image_path}", exception=e)
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="detection_error",
                detection_disabled=False,
                error=str(e),
            )
        except CorruptionEvaluationError as e:
            logger.error(f"Corruption evaluation error for {image_path}", exception=e)
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="evaluation_error",
                detection_disabled=False,
                error=str(e),
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error evaluating image quality for {image_path}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            # Return safe fallback result
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="error",
                detection_disabled=False,
                error=str(e),
            )

    async def should_retry_capture(
        self,
        evaluation_result: CorruptionEvaluationResult,
        camera_id: int,
        current_attempt: int,
        max_attempts: int = 3,
    ) -> RetryDecision:
        """
        Determine if a failed capture should be retried.

        Args:
            evaluation_result: Result from initial evaluation
            camera_id: ID of the camera
            current_attempt: Current capture attempt number
            max_attempts: Maximum allowed retry attempts

        Returns:
            Dictionary with retry decision
        """
        try:
            # Don't retry if image is valid
            if evaluation_result.is_valid:
                return RetryDecision(
                    should_retry=False,
                    reason="Image is valid, no retry needed",
                    retry_count=current_attempt,
                    max_retries=max_attempts,
                    next_retry_delay_ms=0,
                )

            # Don't retry if max attempts reached
            if current_attempt >= max_attempts:
                return RetryDecision(
                    should_retry=False,
                    reason=f"Maximum retry attempts ({max_attempts}) reached",
                    retry_count=current_attempt,
                    max_retries=max_attempts,
                    next_retry_delay_ms=0,
                )

            # Service Layer Boundary Pattern - Process raw dictionary from database
            settings_dict = await self.db_ops.get_corruption_settings()
            retry_enabled = settings_dict.get("retry_enabled", True)

            if not retry_enabled:
                return RetryDecision(
                    should_retry=False,
                    reason="Corruption retry is disabled in settings",
                    retry_count=current_attempt,
                    max_retries=max_attempts,
                    next_retry_delay_ms=0,
                )

            # Don't retry if score is critically bad (likely real corruption)
            if evaluation_result.corruption_score >= CORRUPTION_CRITICAL_THRESHOLD:
                return RetryDecision(
                    should_retry=False,
                    reason=f"Corruption score too high ({evaluation_result.corruption_score}) for retry",
                    retry_count=current_attempt,
                    max_retries=max_attempts,
                    next_retry_delay_ms=0,
                )

            # Check camera degraded mode - process raw dictionary
            camera_metadata_dict = await self.db_ops.get_camera_corruption_metadata(
                camera_id
            )
            is_degraded = camera_metadata_dict["degraded_mode_active"]

            if is_degraded:
                return RetryDecision(
                    should_retry=False,
                    reason="Camera is in degraded mode, skipping retry",
                    retry_count=current_attempt,
                    max_retries=max_attempts,
                    next_retry_delay_ms=0,
                )

            # Allow retry for borderline cases
            return RetryDecision(
                should_retry=True,
                reason=f"Retry attempt {current_attempt + 1}/{max_attempts} for borderline corruption",
                retry_count=current_attempt,
                max_retries=max_attempts,
                next_retry_delay_ms=1000,  # 1 second delay
            )

        except CorruptionSettingsError as e:
            logger.error(
                f"Corruption settings error for camera {camera_id} retry decision",
                exception=e,
            )
            return RetryDecision(
                should_retry=False,
                reason=f"Settings error: {str(e)}",
                retry_count=current_attempt,
                max_retries=max_attempts,
                next_retry_delay_ms=0,
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error determining retry for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return RetryDecision(
                should_retry=False,
                reason=f"Error in retry logic: {str(e)}",
                retry_count=current_attempt,
                max_retries=max_attempts,
                next_retry_delay_ms=0,
            )

    async def assess_camera_health(self, camera_id: int) -> CameraHealthDetails:
        """
        Assess camera health based on corruption detection metrics.

        Args:
            camera_id: ID of the camera to assess

        Returns:
            CameraHealthDetails with health assessment results
        """
        try:
            # Service Layer Boundary Pattern - Get raw dictionaries from database layer
            metadata_dict = await self.db_ops.get_camera_corruption_metadata(camera_id)

            # Get recent corruption statistics
            stats = await self.db_ops.get_corruption_stats(camera_id=camera_id)

            # Service processes raw dictionaries internally
            is_degraded = metadata_dict["degraded_mode_active"]
            consecutive_failures = metadata_dict["consecutive_corruption_failures"]

            # Calculate health score
            health_score = 100.0
            issues = []
            recommendations = []

            # Degraded mode penalty
            if is_degraded:
                penalty = 30.0
                health_score -= penalty
                issues.append("Camera is in degraded mode - quality detection limited")
                recommendations.append(
                    "Investigate camera feed quality and connection stability"
                )

            # Consecutive failures penalty
            if consecutive_failures > 5:
                penalty = min(consecutive_failures * 2.0, 25.0)
                health_score -= penalty
                issues.append(
                    f"High consecutive corruption failures: {consecutive_failures}"
                )
                recommendations.append(
                    "Check camera feed stability and image quality settings"
                )

            # Average corruption score penalty
            if stats.avg_corruption_score > 70.0:
                penalty = (stats.avg_corruption_score - 70.0) / 3.0
                health_score -= penalty
                issues.append(
                    f"High average corruption score: {stats.avg_corruption_score:.1f}"
                )
                recommendations.append(
                    "Review camera positioning, lens cleanliness, and lighting conditions"
                )

            # Recent detection failures
            recent_corruption_rate = 0.0
            if stats.total_detections > 10:
                recent_corruption_rate = stats.images_discarded / stats.total_detections
                if recent_corruption_rate > 0.3:  # More than 30% corrupted
                    penalty = 15.0
                    health_score -= penalty
                    issues.append(f"High corruption rate: {recent_corruption_rate:.1%}")
                    recommendations.append(
                        "Investigate image quality issues or adjust detection thresholds"
                    )

            # Ensure health score doesn't go below 0
            health_score = max(0.0, health_score)

            # Determine health status
            if health_score >= 80.0:
                status = "healthy"
            elif health_score >= 60.0:
                status = "monitoring"
            elif health_score >= 40.0:
                status = "degraded"
            else:
                status = "critical"

            # Add general recommendations based on status
            if status in ["degraded", "critical"]:
                recommendations.append(
                    "Consider temporary camera maintenance or replacement"
                )
                recommendations.append(
                    "Review camera feed configuration and network stability"
                )
            elif status == "monitoring":
                recommendations.append(
                    "Monitor camera closely for any further degradation"
                )

            # Service Layer Boundary Pattern - Convert to typed object at boundary
            return CameraHealthDetails(
                camera_id=camera_id,
                health_score=health_score,
                status=status,
                recent_corruption_rate=recent_corruption_rate,
                consecutive_failures=consecutive_failures,
                degraded_mode_active=is_degraded,
                issues=issues,
                recommendations=recommendations,
                last_assessment=None,  # Could be set to current timestamp if needed
            )

        except CameraHealthError as e:
            logger.error(
                f"Camera health assessment error for camera {camera_id}", exception=e
            )
            raise
        except CorruptionEvaluationError as e:
            logger.error(
                f"Corruption evaluation error during health assessment for camera {camera_id}",
                exception=e,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error assessing camera {camera_id} health: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            raise CameraHealthError(
                f"Failed to assess camera {camera_id} health: {str(e)}"
            ) from e

    async def check_degraded_mode_trigger(self, camera_id: int) -> bool:
        """
        Check if a camera should enter degraded mode based on failure patterns.

        Args:
            camera_id: ID of the camera to check

        Returns:
            True if camera should enter degraded mode
        """
        try:
            # Service Layer Boundary Pattern - Process raw dictionary from database
            settings_dict = await self.db_ops.get_corruption_settings()
            consecutive_threshold = settings_dict.get(
                "degraded_mode_failure_threshold", 5
            )

            # Get camera failure statistics - process raw dictionary
            metadata_dict = await self.db_ops.get_camera_corruption_metadata(camera_id)
            consecutive_failures = metadata_dict["consecutive_corruption_failures"]

            # Check consecutive failures threshold
            if consecutive_failures >= consecutive_threshold:
                logger.warning(
                    f"Camera {camera_id} should enter degraded mode: {consecutive_failures} consecutive failures",
                    emoji=LogEmoji.WARNING,
                )
                return True

            # Additional checks for failure percentage in time window could be added here
            # based on the existing logic in database operations

            return False

        except DegradedModeError as e:
            logger.error(
                f"Degraded mode operation error for camera {camera_id}", exception=e
            )
            return False
        except CorruptionSettingsError as e:
            logger.error(
                f"Corruption settings error during degraded mode check for camera {camera_id}",
                exception=e,
            )
            return False
        except CorruptionEvaluationError as e:
            logger.error(
                f"Corruption evaluation error during degraded mode check for camera {camera_id}",
                exception=e,
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error checking degraded mode trigger for camera {camera_id}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            return False


class SyncCorruptionEvaluationService:
    """
    Sync corruption evaluation service for worker processes.

    Provides the same evaluation logic as the async version but
    with synchronous database operations for worker processes.
    """

    def __init__(self, db: SyncDatabase, corruption_ops=None):
        """Initialize with sync database instance and optional injected Operations"""
        self.db = db
        self.db_ops = corruption_ops or self._get_default_corruption_ops()
        
        # Initialize detectors with default config
        self.fast_detector = FastCorruptionDetector()
        self.heavy_detector = HeavyCorruptionDetector()
        self.score_calculator = CorruptionScoreCalculator()
        
    def _get_default_corruption_ops(self):
        """Fallback to get SyncCorruptionOperations singleton"""
        from ....dependencies.specialized import get_sync_corruption_operations
        return get_sync_corruption_operations()

    def evaluate_captured_image(
        self,
        camera_id: int,
        file_path: str,
        timelapse_id: Optional[int] = None,
        capture_attempt: int = 1,
    ) -> CorruptionEvaluationResult:
        """
        Evaluate a captured image for corruption (sync version).

        Args:
            camera_id: Camera ID
            file_path: Path to captured image file
            timelapse_id: Optional timelapse ID
            capture_attempt: Capture attempt number

        Returns:
            CorruptionEvaluationResult model instance
        """
        try:
            # Service Layer Boundary Pattern - Process raw dictionary from database
            settings_dict = self.db_ops.get_corruption_settings()
            is_enabled = settings_dict.get("is_enabled", True)

            if not is_enabled:
                return CorruptionEvaluationResult(
                    is_valid=True,
                    corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                    action_taken="accepted",
                    detection_disabled=True,
                )

            # Get camera-specific settings - process raw dictionary
            camera_settings_dict = self.db_ops.get_camera_corruption_settings(camera_id)
            heavy_detection_enabled = camera_settings_dict.get(
                "corruption_detection_heavy", False
            )

            # Perform fast detection - detector returns dictionary
            fast_result_dict = self.fast_detector.detect(file_path)

            # Perform heavy detection if enabled
            heavy_result_dict = None
            if heavy_detection_enabled:
                heavy_result_dict = self.heavy_detector.detect(file_path)

            # Calculate final score using raw dictionary data
            heavy_score = (
                heavy_result_dict["corruption_score"] if heavy_result_dict else None
            )
            score_result = self.score_calculator.calculate_final_score(
                fast_score=fast_result_dict["corruption_score"],
                heavy_score=heavy_score,
            )

            # Determine if image is valid
            is_valid = not score_result.is_corrupted
            action_taken = "saved" if is_valid else "discarded"

            # Log the evaluation - database layer expects raw data
            self.db_ops.log_corruption_detection(
                camera_id=camera_id,
                image_id=None,  # Will be set by caller if needed
                corruption_score=int(score_result.final_score),
                fast_score=int(fast_result_dict["corruption_score"]),
                heavy_score=(
                    int(heavy_result_dict["corruption_score"])
                    if heavy_result_dict and heavy_result_dict.get("is_available", True)
                    else None
                ),
                detection_details={
                    "fast_detection": fast_result_dict,
                    "heavy_detection": heavy_result_dict,
                    "score_calculation": score_result.to_dict(),
                    "timelapse_id": timelapse_id,
                    "capture_attempt": capture_attempt,
                },
                action_taken=action_taken,
                processing_time_ms=int(
                    fast_result_dict["detection_time_ms"]
                    + (
                        heavy_result_dict["detection_time_ms"]
                        if heavy_result_dict
                        else 0.0
                    )
                ),
            )

            # Update camera corruption statistics
            self.db_ops.update_camera_corruption_stats(
                camera_id=camera_id,
                _corruption_score=int(score_result.final_score),
                is_valid=is_valid,
            )

            # Service Layer Boundary Pattern - Return typed object at boundary
            return CorruptionEvaluationResult(
                is_valid=is_valid,
                corruption_score=int(score_result.final_score),
                fast_score=int(fast_result_dict["corruption_score"]),
                heavy_score=(
                    int(heavy_result_dict["corruption_score"])
                    if heavy_result_dict and heavy_result_dict.get("is_available", True)
                    else None
                ),
                action_taken=action_taken,
                detection_disabled=False,
                processing_time_ms=fast_result_dict["detection_time_ms"]
                + (
                    heavy_result_dict["detection_time_ms"] if heavy_result_dict else 0.0
                ),
                failed_checks=fast_result_dict["failed_checks"]
                + (heavy_result_dict["failed_checks"] if heavy_result_dict else []),
            )

        except CorruptionSettingsError as e:
            logger.error(f"Corruption settings error for {file_path}", exception=e)
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="settings_error",
                detection_disabled=False,
                error=str(e),
            )
        except CorruptionDetectionError as e:
            logger.error(f"Corruption detection error for {file_path}", exception=e)
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="detection_error",
                detection_disabled=False,
                error=str(e),
            )
        except CorruptionEvaluationError as e:
            logger.error(f"Corruption evaluation error for {file_path}", exception=e)
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="evaluation_error",
                detection_disabled=False,
                error=str(e),
            )
        except Exception as e:
            logger.error(
                f"Unexpected error evaluating captured image {file_path}: {e}",
                exception=e,
                emoji=LogEmoji.FAILED,
            )
            # Return safe fallback result
            return CorruptionEvaluationResult(
                is_valid=False,
                corruption_score=100,
                action_taken="error",
                detection_disabled=False,
                error=str(e),
            )

    def evaluate_image_quality(
        self,
        image_path: str,
        camera_id: int,
        image_id: Optional[int] = None,
        capture_attempt: int = 1,
    ) -> CorruptionEvaluationResult:
        """
        Evaluate image quality (sync version matching async interface).

        Args:
            image_path: Path to the image file
            camera_id: ID of the camera that captured the image
            image_id: Optional image ID for logging
            capture_attempt: Capture attempt number for retry logic

        Returns:
            CorruptionEvaluationResult with evaluation details
        """
        return self.evaluate_captured_image(
            camera_id=camera_id,
            file_path=image_path,
            timelapse_id=image_id,  # Use image_id as timelapse_id for compatibility
            capture_attempt=capture_attempt,
        )

    def evaluate_with_retry(
        self,
        camera_id: int,
        file_path: str,
        timelapse_id: Optional[int] = None,
        max_attempts: int = 3,
    ) -> CorruptionEvaluationResult:
        """
        Evaluate image with automatic retry logic.

        Args:
            camera_id: Camera ID
            file_path: Path to image file
            timelapse_id: Optional timelapse ID
            max_attempts: Maximum retry attempts

        Returns:
            Final CorruptionEvaluationResult after all attempts
        """
        last_result = None

        for attempt in range(1, max_attempts + 1):
            result = self.evaluate_captured_image(
                camera_id=camera_id,
                file_path=file_path,
                timelapse_id=timelapse_id,
                capture_attempt=attempt,
            )

            # If image is valid or this is the last attempt, return result
            if result.is_valid or attempt == max_attempts:
                return result

            # Check if we should retry
            if result.corruption_score >= CORRUPTION_CRITICAL_THRESHOLD:
                # Don't retry for critically corrupted images
                return result

            last_result = result
            logger.info(
                f"Retrying capture for camera {camera_id}, attempt {attempt + 1}/{max_attempts}",
                emoji=LogEmoji.TASK,
            )

        return last_result or CorruptionEvaluationResult(
            is_valid=False,
            corruption_score=100,
            action_taken="failed",
            detection_disabled=False,
            error="All retry attempts failed",
        )
