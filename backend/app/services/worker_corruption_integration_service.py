"""
Worker Integration Service for Corruption Detection

Provides corruption detection integration for worker capture pipeline using
composition-based architecture following AI-CONTEXT principles.

Responsibilities:
- Corruption evaluation coordination
- Retry logic management
- Database operations via composition
- Settings management

Interactions:
- Uses SyncCorruptionOperations for database
- Calls corruption_detection_utils for analysis
- Integrates with worker capture pipeline
"""

from typing import Dict, Any, Optional, Tuple
from loguru import logger

from ..database.core import SyncDatabase
from ..database.corruption_operations import SyncCorruptionOperations
from ..database.settings_operations import SyncSettingsOperations
from ..models.corruption_model import (
    CorruptionEvaluationResult,
    CorruptionRetryResult,
    CorruptionLogEntry,
)
from ..utils.corruption_detection_utils import (
    detect_fast_corruption,
    detect_heavy_corruption,
    calculate_corruption_score,
    CorruptionScoreCalculator,
)
from ..utils.file_helpers import delete_file_safe
from ..utils.timezone_utils import get_timezone_aware_timestamp_sync
from ..constants import (
    DEFAULT_CORRUPTION_FALLBACK_SCORE,
    DEFAULT_CORRUPTION_RETRY_ENABLED,
)


class WorkerCorruptionIntegration:
    """
    Corruption detection integration for worker processes using composition pattern.
    
    This service coordinates corruption detection evaluation using dependency injection
    instead of direct database calls or global singleton patterns.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize with sync database instance and operations composition.
        
        Args:
            db: SyncDatabase instance for worker processes
        """
        self.db = db
        self.corruption_ops = SyncCorruptionOperations(db)
        self.settings_ops = SyncSettingsOperations(db)
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load corruption detection settings using operations layer."""
        try:
            settings = self.corruption_ops.get_corruption_settings()
            logger.info("Corruption detection settings loaded successfully")
            return settings
        except Exception as e:
            logger.error(f"Failed to load corruption settings: {e}")
            return {}

    def evaluate_captured_image(
        self, camera_id: int, file_path: str, timelapse_id: int
    ) -> CorruptionEvaluationResult:
        """
        Evaluate a captured image for corruption using Pydantic models.

        Args:
            camera_id: Camera ID
            file_path: Path to captured image file
            timelapse_id: Active timelapse ID

        Returns:
            CorruptionEvaluationResult model instance
        """
        try:
            # Check if corruption detection is enabled
            if not self.settings:
                return CorruptionEvaluationResult(
                    is_valid=True,
                    corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                    action_taken="accepted",
                    detection_disabled=True,
                )

            # Get per-camera corruption settings using operations layer
            camera_settings = self.corruption_ops.get_camera_corruption_settings(camera_id)
            heavy_detection_enabled = camera_settings.get("corruption_detection_heavy", False)

            # Run fast detection (always enabled)
            fast_result = detect_fast_corruption(file_path, config=self.settings)
            fast_score = fast_result.corruption_score

            # Run heavy detection if enabled for this camera
            heavy_score = None
            heavy_result = None
            
            if heavy_detection_enabled:
                heavy_result = detect_heavy_corruption(file_path, config=self.settings)
                heavy_score = heavy_result.corruption_score

            # Calculate final corruption score
            final_score = calculate_corruption_score(
                fast_score, heavy_score, config=self.settings
            )

            # Determine if image is valid
            calculator = CorruptionScoreCalculator(self.settings)
            is_valid = not calculator.is_corrupted(final_score)

            # Collect failed checks
            failed_checks = fast_result.failed_checks.copy()
            if heavy_result:
                failed_checks.extend(heavy_result.failed_checks)

            # Calculate total processing time
            total_processing_time = fast_result.processing_time_ms
            if heavy_result:
                total_processing_time += heavy_result.processing_time_ms

            # Create structured result using Pydantic model
            result = CorruptionEvaluationResult(
                is_valid=is_valid,
                corruption_score=final_score,
                action_taken="accepted" if is_valid else "flagged",
                fast_score=fast_score,
                heavy_score=heavy_score,
                failed_checks=failed_checks,
                processing_time_ms=total_processing_time,
            )

            # Log corruption detection result using operations layer
            log_entry = self.corruption_ops.log_corruption_detection(
                camera_id=camera_id,
                image_id=None,  # Will be set after database record creation
                corruption_score=result.corruption_score,
                fast_score=result.fast_score,
                heavy_score=result.heavy_score,
                detection_details={
                    "fast_failed_checks": fast_result.failed_checks,
                    "heavy_failed_checks": heavy_result.failed_checks if heavy_result else [],
                    "total_processing_time_ms": result.processing_time_ms,
                },
                action_taken=result.action_taken,
                processing_time_ms=int(result.processing_time_ms),
            )

            # Update camera corruption statistics using operations layer
            stats_updated = self.corruption_ops.update_camera_corruption_stats(
                camera_id=camera_id,
                corruption_score=result.corruption_score,
                is_valid=result.is_valid,
            )
            if not stats_updated:
                logger.warning(f"Failed to update corruption stats for camera {camera_id}")

            # Check for degraded mode trigger using operations layer
            if not result.is_valid:
                should_degrade = self.corruption_ops.check_degraded_mode_trigger(
                    camera_id, self.settings
                )
                if should_degrade:
                    self.corruption_ops.set_camera_degraded_mode(camera_id, True)
                    logger.warning(
                        f"Camera {camera_id} entered degraded mode due to corruption"
                    )

            return result

        except Exception as e:
            logger.error(f"Corruption evaluation failed for camera {camera_id}: {e}")
            # Return valid result with error if evaluation fails to avoid blocking captures
            return CorruptionEvaluationResult(
                is_valid=True,
                corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                action_taken="accepted",
                error=str(e),
            )

    def evaluate_with_retry(
        self, camera_id: int, rtsp_url: str, capture_func, timelapse_id: int
    ) -> CorruptionRetryResult:
        """
        Evaluate image with retry logic using Pydantic models.

        Args:
            camera_id: Camera ID
            rtsp_url: RTSP URL for retry capture
            capture_func: Function to call for image capture
            timelapse_id: Active timelapse ID

        Returns:
            CorruptionRetryResult model instance
        """
        try:
            # First capture attempt
            success, message, file_path = capture_func()

            if not success:
                return CorruptionRetryResult(
                    success=False,
                    message=message,
                    file_path=file_path,
                    evaluation_result=CorruptionEvaluationResult(
                        is_valid=False,
                        corruption_score=0,
                        action_taken="capture_failed",
                        error="Initial capture failed",
                    ),
                )

            # Evaluate for corruption
            evaluation_result = self.evaluate_captured_image(
                camera_id, file_path, timelapse_id
            )

            if evaluation_result.is_valid:
                return CorruptionRetryResult(
                    success=True,
                    message=message,
                    file_path=file_path,
                    evaluation_result=evaluation_result,
                )

            # Image is corrupted - check if retry is enabled
            auto_discard_enabled = self.settings.get("corruption_auto_discard_enabled", False)
            if not auto_discard_enabled:
                # Auto-discard is disabled, keep the image but flag it
                logger.warning(
                    f"Camera {camera_id}: Corrupted image kept (auto-discard disabled)"
                )
                return CorruptionRetryResult(
                    success=True,
                    message=f"{message} (flagged)",
                    file_path=file_path,
                    evaluation_result=evaluation_result,
                )

            # Auto-discard is enabled - try retry
            logger.info(
                f"Camera {camera_id}: Image corrupted (score: {evaluation_result.corruption_score}), attempting retry"
            )

            # Delete the corrupted image using file_helpers
            if not delete_file_safe(file_path):
                logger.warning(f"Failed to delete corrupted image {file_path}")

            # Attempt retry
            retry_success, retry_message, retry_file_path = capture_func()

            if not retry_success:
                return CorruptionRetryResult(
                    success=False,
                    message=f"Retry failed: {retry_message}",
                    file_path="",
                    evaluation_result=evaluation_result,
                    retry_attempted=True,
                )

            # Evaluate retry
            retry_evaluation_result = self.evaluate_captured_image(
                camera_id, retry_file_path, timelapse_id
            )

            if retry_evaluation_result.is_valid:
                logger.info(f"Camera {camera_id}: Retry successful")
                return CorruptionRetryResult(
                    success=True,
                    message=f"Retry successful: {retry_message}",
                    file_path=retry_file_path,
                    evaluation_result=retry_evaluation_result,
                    retry_attempted=True,
                )
            else:
                logger.warning(f"Camera {camera_id}: Retry also failed")
                # Keep the retry image but flag it
                return CorruptionRetryResult(
                    success=True,
                    message=f"Retry failed (flagged): {retry_message}",
                    file_path=retry_file_path,
                    evaluation_result=retry_evaluation_result,
                    retry_attempted=True,
                )

        except Exception as e:
            logger.error(f"Corruption evaluation with retry failed: {e}")
            # Return original capture result if corruption evaluation fails
            try:
                original_success, original_message, original_file_path = capture_func()
                return CorruptionRetryResult(
                    success=original_success,
                    message=original_message,
                    file_path=original_file_path,
                    evaluation_result=CorruptionEvaluationResult(
                        is_valid=True,
                        corruption_score=DEFAULT_CORRUPTION_FALLBACK_SCORE,
                        action_taken="accepted",
                        error=str(e),
                    ),
                )
            except Exception as capture_error:
                logger.error(f"Fallback capture also failed: {capture_error}")
                return CorruptionRetryResult(
                    success=False,
                    message=str(capture_error),
                    file_path="",
                    evaluation_result=CorruptionEvaluationResult(
                        is_valid=False,
                        corruption_score=0,
                        action_taken="failed",
                        error=str(e),
                    ),
                )

    def refresh_settings(self) -> bool:
        """
        Refresh corruption detection settings from database using operations layer.
        
        Returns:
            True if settings were refreshed successfully
        """
        try:
            self.settings = self.corruption_ops.get_corruption_settings()
            logger.debug("Corruption detection settings refreshed")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh corruption settings: {e}")
            return False

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get service health status for monitoring.
        
        Returns:
            Dictionary with service health metrics
        """
        try:
            health_data = {
                "service": "worker_corruption_integration",
                "status": "healthy",
                "settings_loaded": bool(self.settings),
                "timestamp": get_timezone_aware_timestamp_sync(self.settings_ops),
            }
            
            # Add settings count for health assessment
            if self.settings:
                health_data["settings_count"] = len(self.settings)
                health_data["auto_discard_enabled"] = self.settings.get(
                    "corruption_auto_discard_enabled", False
                )
            else:
                health_data["status"] = "degraded"
                health_data["error"] = "Settings not loaded"
            
            return health_data
            
        except Exception as e:
            logger.error(f"Worker corruption integration health check failed: {e}")
            return {
                "service": "worker_corruption_integration",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": get_timezone_aware_timestamp_sync(self.settings_ops),
            }


# Dependency injection pattern - no global singleton
def create_worker_corruption_integration(sync_db: SyncDatabase) -> WorkerCorruptionIntegration:
    """
    Create WorkerCorruptionIntegration instance using dependency injection.
    
    Args:
        sync_db: SyncDatabase instance
        
    Returns:
        WorkerCorruptionIntegration instance
    """
    return WorkerCorruptionIntegration(sync_db)