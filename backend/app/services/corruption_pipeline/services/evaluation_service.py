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

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

from ....database.core import AsyncDatabase, SyncDatabase
from ....models.corruption_model import (
    CorruptionEvaluationResult,
    CorruptionLogEntry,
)
from ....constants import (
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
    DEFAULT_CORRUPTION_FALLBACK_SCORE,
    DEFAULT_CORRUPTION_RETRY_ENABLED,
    DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
    CORRUPTION_CRITICAL_THRESHOLD,
)

from ..detectors import (
    FastCorruptionDetector,
    HeavyCorruptionDetector,
    CorruptionScoreCalculator,
)
from ....database.corruption_operations import (
    CorruptionOperations,
    SyncCorruptionOperations,
)


class CorruptionEvaluationService:
    """
    Async corruption evaluation service for API endpoints.

    Provides high-level business logic for corruption detection
    with clean interfaces and proper error handling.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance"""
        self.db = db
        self.db_ops = CorruptionOperations(db)

        # Initialize detectors with default config
        self.fast_detector = FastCorruptionDetector()
        self.heavy_detector = HeavyCorruptionDetector()
        self.score_calculator = CorruptionScoreCalculator()

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
            # Check if corruption detection is enabled
            settings = await self.db_ops.get_corruption_settings()
            if not settings.get("detection_enabled", True):
                return CorruptionEvaluationResult(
                    is_valid=True,
                    corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                    action_taken="accepted",
                    detection_disabled=True,
                )

            # Get camera-specific settings
            camera_settings = await self.db_ops.get_camera_corruption_settings(
                camera_id
            )
            heavy_detection_enabled = camera_settings.get(
                "corruption_detection_heavy", False
            )

            # Get camera degraded mode status
            camera_metadata = await self.db_ops.get_camera_corruption_metadata(
                camera_id
            )
            is_degraded = camera_metadata.get("degraded_mode_active", False)
            consecutive_failures = camera_metadata.get(
                "consecutive_corruption_failures", 0
            )

            # Perform fast detection
            fast_result = self.fast_detector.detect(image_path)

            # Perform heavy detection if enabled and not in degraded mode
            heavy_result = None
            if heavy_detection_enabled and not is_degraded:
                heavy_result = self.heavy_detector.detect(image_path)

            # Calculate final score
            score_result = self.score_calculator.calculate_final_score(
                fast_score=fast_result.get("corruption_score", 100.0),
                heavy_score=(
                    heavy_result.get("corruption_score")
                    if heavy_result and heavy_result.get("corruption_score") is not None
                    else None
                ),
                health_degraded=is_degraded,
                consecutive_failures=consecutive_failures,
            )

            # Determine if image is valid
            is_valid = not score_result.is_corrupted
            action_taken = "saved" if is_valid else "discarded"

            # TODO: Create SSE event for corruption detection result
            # Should use SSEEventsOperations.create_event() with EVENT_CORRUPTION_DETECTED
            
            # Create evaluation result
            evaluation_result = CorruptionEvaluationResult(
                is_valid=is_valid,
                corruption_score=int(score_result.final_score),
                fast_score=int(fast_result.get("corruption_score", 100.0)),
                heavy_score=int(heavy_result.get("corruption_score", 0)) if heavy_result and heavy_result.get("corruption_score") is not None else None,
                action_taken=action_taken,
                detection_disabled=False,
                processing_time_ms=fast_result.get("detection_time_ms", 0.0)
                + (heavy_result.get("detection_time_ms", 0.0) if heavy_result else 0.0),
                failed_checks=fast_result.get("failed_checks", [])
                + (heavy_result.get("failed_checks", []) if heavy_result else []),
            )

            return evaluation_result

        except Exception as e:
            logger.error(f"Error evaluating image quality for {image_path}: {e}")
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
    ) -> Dict[str, Any]:
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
                return {
                    "should_retry": False,
                    "reason": "Image is valid, no retry needed",
                }

            # Don't retry if max attempts reached
            if current_attempt >= max_attempts:
                return {
                    "should_retry": False,
                    "reason": f"Maximum retry attempts ({max_attempts}) reached",
                }

            # Check if retry is enabled in settings
            settings = await self.db_ops.get_corruption_settings()
            retry_enabled = settings.get(
                "retry_enabled", DEFAULT_CORRUPTION_RETRY_ENABLED
            )

            if not retry_enabled:
                return {
                    "should_retry": False,
                    "reason": "Corruption retry is disabled in settings",
                }

            # Don't retry if score is critically bad (likely real corruption)
            if evaluation_result.corruption_score >= CORRUPTION_CRITICAL_THRESHOLD:
                return {
                    "should_retry": False,
                    "reason": f"Corruption score too high ({evaluation_result.corruption_score}) for retry",
                }

            # Check camera degraded mode
            camera_metadata = await self.db_ops.get_camera_corruption_metadata(
                camera_id
            )
            if camera_metadata.get("degraded_mode_active", False):
                return {
                    "should_retry": False,
                    "reason": "Camera is in degraded mode, skipping retry",
                }

            # Allow retry for borderline cases
            return {
                "should_retry": True,
                "reason": f"Retry attempt {current_attempt + 1}/{max_attempts} for borderline corruption",
            }

        except Exception as e:
            logger.error(f"Error determining retry for camera {camera_id}: {e}")
            return {"should_retry": False, "reason": f"Error in retry logic: {str(e)}"}

    async def assess_camera_health(self, camera_id: int) -> Dict[str, Any]:
        """
        Assess camera health based on corruption detection metrics.

        Args:
            camera_id: ID of the camera to assess

        Returns:
            Dictionary with health assessment results
        """
        try:
            # Get camera corruption metadata
            metadata = await self.db_ops.get_camera_corruption_metadata(camera_id)

            # Get recent corruption statistics
            stats = await self.db_ops.get_corruption_stats(camera_id=camera_id)

            # Calculate health score
            health_score = 100.0
            penalties = []

            # Degraded mode penalty
            if metadata.get("degraded_mode_active", False):
                penalty = 30.0
                health_score -= penalty
                penalties.append(f"Degraded mode active (-{penalty})")

            # Consecutive failures penalty
            consecutive_failures = metadata.get("consecutive_corruption_failures", 0)
            if consecutive_failures > 5:
                penalty = min(consecutive_failures * 2.0, 25.0)
                health_score -= penalty
                penalties.append(
                    f"Consecutive failures: {consecutive_failures} (-{penalty})"
                )

            # Average corruption score penalty
            if stats.avg_corruption_score > 70.0:
                penalty = (stats.avg_corruption_score - 70.0) / 3.0
                health_score -= penalty
                penalties.append(
                    f"High avg corruption score: {stats.avg_corruption_score:.1f} (-{penalty:.1f})"
                )

            # Recent detection failures
            if (
                stats.images_discarded > stats.images_saved
                and stats.total_detections > 10
            ):
                penalty = 15.0
                health_score -= penalty
                penalties.append(f"More discarded than saved images (-{penalty})")

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

            return {
                "camera_id": camera_id,
                "health_score": health_score,
                "health_status": status,
                "degraded_mode_active": metadata.get("degraded_mode_active", False),
                "consecutive_failures": consecutive_failures,
                "lifetime_glitch_count": metadata.get("lifetime_glitch_count", 0),
                "recent_stats": {
                    "total_detections": stats.total_detections,
                    "images_saved": stats.images_saved,
                    "images_discarded": stats.images_discarded,
                    "avg_corruption_score": stats.avg_corruption_score,
                },
                "penalties": penalties,
                "last_degraded_at": metadata.get("last_degraded_at"),
            }

        except Exception as e:
            logger.error(f"Error assessing camera {camera_id} health: {e}")
            raise

    async def check_degraded_mode_trigger(self, camera_id: int) -> bool:
        """
        Check if a camera should enter degraded mode based on failure patterns.

        Args:
            camera_id: ID of the camera to check

        Returns:
            True if camera should enter degraded mode
        """
        try:
            # Get corruption settings for degraded mode thresholds
            settings = await self.db_ops.get_corruption_settings()

            # Get camera failure statistics
            metadata = await self.db_ops.get_camera_corruption_metadata(camera_id)

            # Check consecutive failures threshold
            consecutive_threshold = settings.get(
                "degraded_mode_failure_threshold",
                DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
            )
            consecutive_failures = metadata.get("consecutive_corruption_failures", 0)

            if consecutive_failures >= consecutive_threshold:
                logger.warning(
                    f"Camera {camera_id} should enter degraded mode: {consecutive_failures} consecutive failures"
                )
                return True

            # Additional checks for failure percentage in time window could be added here
            # based on the existing logic in database operations

            return False

        except Exception as e:
            logger.error(
                f"Error checking degraded mode trigger for camera {camera_id}: {e}"
            )
            return False


class SyncCorruptionEvaluationService:
    """
    Sync corruption evaluation service for worker processes.

    Provides the same evaluation logic as the async version but
    with synchronous database operations for worker processes.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance"""
        self.db = db
        self.db_ops = SyncCorruptionOperations(db)

        # Initialize detectors with default config
        self.fast_detector = FastCorruptionDetector()
        self.heavy_detector = HeavyCorruptionDetector()
        self.score_calculator = CorruptionScoreCalculator()

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
            # Check if corruption detection is enabled
            settings = self.db_ops.get_corruption_settings()
            if not settings.get("detection_enabled", True):
                return CorruptionEvaluationResult(
                    is_valid=True,
                    corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                    action_taken="accepted",
                    detection_disabled=True,
                )

            # Get camera-specific settings
            camera_settings = self.db_ops.get_camera_corruption_settings(camera_id)
            heavy_detection_enabled = camera_settings.get(
                "corruption_detection_heavy", False
            )

            # Perform fast detection
            fast_result = self.fast_detector.detect(file_path)

            # Perform heavy detection if enabled
            heavy_result = None
            if heavy_detection_enabled:
                heavy_result = self.heavy_detector.detect(file_path)

            # Calculate final score
            score_result = self.score_calculator.calculate_final_score(
                fast_score=fast_result.get("corruption_score", 100.0),
                heavy_score=(
                    heavy_result.get("corruption_score")
                    if heavy_result and heavy_result.get("corruption_score") is not None
                    else None
                ),
            )

            # Determine if image is valid
            is_valid = not score_result.is_corrupted
            action_taken = "saved" if is_valid else "discarded"

            # Log the evaluation
            log_entry = self.db_ops.log_corruption_detection(
                camera_id=camera_id,
                image_id=None,  # Will be set by caller if needed
                corruption_score=int(score_result.final_score),
                fast_score=int(fast_result.get("corruption_score", 100.0)),
                heavy_score=int(heavy_result.get("corruption_score", 0)) if heavy_result and heavy_result.get("corruption_score") is not None else None,
                detection_details={
                    "fast_detection": fast_result,
                    "heavy_detection": heavy_result,
                    "score_calculation": score_result.to_dict(),
                    "timelapse_id": timelapse_id,
                    "capture_attempt": capture_attempt,
                },
                action_taken=action_taken,
                processing_time_ms=int(
                    fast_result.get("detection_time_ms", 0.0)
                    + (
                        heavy_result.get("detection_time_ms", 0.0)
                        if heavy_result
                        else 0.0
                    )
                ),
            )

            # Update camera corruption statistics
            self.db_ops.update_camera_corruption_stats(
                camera_id=camera_id,
                corruption_score=int(score_result.final_score),
                is_valid=is_valid,
            )

            return CorruptionEvaluationResult(
                is_valid=is_valid,
                corruption_score=int(score_result.final_score),
                fast_score=int(fast_result.get("corruption_score", 100.0)),
                heavy_score=int(heavy_result.get("corruption_score", 0)) if heavy_result and heavy_result.get("corruption_score") is not None else None,
                action_taken=action_taken,
                detection_disabled=False,
                processing_time_ms=fast_result.get("detection_time_ms", 0.0)
                + (heavy_result.get("detection_time_ms", 0.0) if heavy_result else 0.0),
                failed_checks=fast_result.get("failed_checks", [])
                + (heavy_result.get("failed_checks", []) if heavy_result else []),
            )

        except Exception as e:
            logger.error(f"Error evaluating captured image {file_path}: {e}")
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
                f"Retrying capture for camera {camera_id}, attempt {attempt + 1}/{max_attempts}"
            )

        return last_result or CorruptionEvaluationResult(
            is_valid=False,
            corruption_score=100,
            action_taken="failed",
            detection_disabled=False,
            error="All retry attempts failed",
        )
