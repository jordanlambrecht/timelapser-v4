# backend/app/services/corruption_service.py
"""
Corruption Detection Service Layer

This service handles business logic for corruption detection, providing a clean interface
between the API layer and the database operations.

Following AI-CONTEXT architectural patterns:
- Composition pattern with dependency injection
- Timezone-aware operations
- SSE event broadcasting
- Structured logging
- Proper Pydantic model usage
"""

import tempfile
import os
import cv2
from typing import List, Dict, Optional, Any
from loguru import logger

from ..database import AsyncDatabase, SyncDatabase
from ..database.corruption_operations import (
    CorruptionOperations,
    SyncCorruptionOperations,
)
from ..database.settings_operations import SettingsOperations
from ..models.corruption_model import (
    CorruptionTestResponse,
    CameraHealthAssessment,
    CorruptionLogsPage,
    CorruptionLogEntry,
    CameraWithCorruption,
    CorruptionAnalysisStats,
)
from ..utils import timezone_utils
from ..utils.corruption_detection_utils import (
    detect_fast_corruption,
    detect_heavy_corruption,
    calculate_corruption_score,
    CorruptionScoreCalculator,
)
from ..constants import (
    CORRUPTION_CRITICAL_THRESHOLD,
    CORRUPTION_FAST_CRITICAL_THRESHOLD,
    CORRUPTION_HEAVY_CRITICAL_THRESHOLD,
    HEALTH_DEGRADED_MODE_PENALTY,
    HEALTH_CONSECUTIVE_FAILURES_HIGH_THRESHOLD,
    HEALTH_CONSECUTIVE_FAILURES_HIGH_PENALTY,
    HEALTH_CONSECUTIVE_FAILURES_MEDIUM_THRESHOLD,
    HEALTH_CONSECUTIVE_FAILURES_MEDIUM_PENALTY,
    HEALTH_POOR_QUALITY_THRESHOLD,
    HEALTH_POOR_QUALITY_PENALTY,
    HEALTH_AVERAGE_QUALITY_THRESHOLD,
    HEALTH_AVERAGE_QUALITY_PENALTY,
    HEALTH_HIGH_DETECTION_THRESHOLD,
    HEALTH_HIGH_DETECTION_PENALTY,
    DEFAULT_CORRUPTION_TEST_THRESHOLD,
    DEFAULT_AUTO_DISCARD_THRESHOLD,
    DEFAULT_FAST_WEIGHT,
    DEFAULT_HEAVY_WEIGHT,
    DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
    DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS,
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
)


class CorruptionService:
    """
    Image quality analysis business logic.

    Responsibilities:
    - Quality scoring algorithms
    - Degraded mode logic
    - Audit trail management
    - Camera health assessment
    - Auto-discard decisions

    Interactions:
    - Uses CorruptionOperations for database
    - Coordinates with CameraService for health updates
    - Provides quality data to ImageCaptureService
    """

    def __init__(self, db: AsyncDatabase, camera_service=None):
        """
        Initialize with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            camera_service: Optional CameraService for health coordination
        """
        self.db = db
        self.operations = CorruptionOperations(db)
        self.settings_ops = SettingsOperations(db)
        self.camera_service = camera_service

    async def get_system_corruption_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive system-wide corruption detection statistics.

        Returns:
            Dictionary containing system statistics and health metrics
        """
        try:
            # Get basic corruption stats
            stats = await self.operations.get_corruption_stats()

            # Get degraded cameras count
            degraded_cameras = await self.operations.get_degraded_cameras()
            degraded_count = len(degraded_cameras)

            # Calculate additional metrics
            total_cameras = await self.operations.get_total_cameras_count()
            healthy_cameras = total_cameras - degraded_count

            # Get recent activity
            recent_detections = await self.operations.get_recent_detections_count()

            return {
                "total_cameras": total_cameras,
                "healthy_cameras": healthy_cameras,
                "cameras_monitoring": total_cameras,
                "degraded_cameras": degraded_count,
                "images_flagged_today": recent_detections["today"],
                "images_flagged_week": recent_detections["week"],
                "storage_saved_mb": 0.0,
                "avg_processing_overhead_ms": stats.avg_processing_time_ms,
                "recent_average_score": stats.avg_corruption_score,
                "lifetime_glitch_count": stats.total_detections,
            }

        except Exception as e:
            logger.error(f"Error getting system corruption stats: {e}")
            raise

    async def get_camera_corruption_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get corruption statistics for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing camera-specific corruption statistics
        """
        try:
            stats = await self.operations.get_corruption_stats(camera_id=camera_id)

            # Use operations method instead of direct database access
            camera_data = await self._get_camera_corruption_metadata(camera_id)

            return {
                "lifetime_glitch_count": camera_data["lifetime_glitch_count"] or 0,
                "recent_average_score": stats.avg_corruption_score,
                "consecutive_corruption_failures": camera_data[
                    "consecutive_corruption_failures"
                ]
                or 0,
                "degraded_mode_active": camera_data["degraded_mode_active"] or False,
                "last_degraded_at": camera_data["last_degraded_at"],
                "total_detections": stats.total_detections,
                "images_saved": stats.images_saved,
                "images_discarded": stats.images_discarded,
                "avg_processing_time_ms": stats.avg_processing_time_ms,
            }

        except Exception as e:
            logger.error(f"Error getting camera {camera_id} corruption stats: {e}")
            raise

    async def get_corruption_logs(
        self,
        camera_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
    ) -> CorruptionLogsPage:
        """
        Get corruption detection logs with filtering and pagination.

        Args:
            camera_id: Optional camera ID to filter by
            page: Page number (1-based)
            page_size: Number of logs per page
            min_score: Optional minimum corruption score filter
            max_score: Optional maximum corruption score filter

        Returns:
            CorruptionLogsPage containing logs and pagination metadata
        """
        try:
            return await self.operations.get_corruption_logs(
                camera_id=camera_id,
                page=page,
                page_size=page_size,
                min_score=min_score,
                max_score=max_score,
            )

        except Exception as e:
            logger.error(f"Error getting corruption logs: {e}")
            raise

    async def get_camera_corruption_history(
        self, camera_id: int, hours: int = 24
    ) -> List[CorruptionLogEntry]:
        """
        Get corruption detection history for a camera.

        Args:
            camera_id: ID of the camera
            hours: Number of hours of history to retrieve

        Returns:
            List of CorruptionLogEntry models
        """
        try:
            return await self.operations.get_camera_corruption_history(
                camera_id=camera_id, hours=hours
            )

        except Exception as e:
            logger.error(f"Error getting camera {camera_id} corruption history: {e}")
            raise

    async def get_degraded_cameras(self) -> List[CameraWithCorruption]:
        """
        Get all cameras currently in degraded mode.

        Returns:
            List of CameraWithCorruption models
        """
        try:
            return await self.operations.get_degraded_cameras()

        except Exception as e:
            logger.error(f"Error getting degraded cameras: {e}")
            raise

    async def reset_camera_degraded_mode(self, camera_id: int) -> bool:
        """
        Reset degraded mode for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful
        """
        try:
            success = await self.operations.reset_camera_degraded_mode(camera_id)

            if success:
                logger.info(f"Reset degraded mode for camera {camera_id}")

                # SSE broadcasting handled by higher-level service layer
            else:
                logger.warning(f"Failed to reset degraded mode for camera {camera_id}")

            return success

        except Exception as e:
            logger.error(f"Error resetting degraded mode for camera {camera_id}: {e}")
            raise

    async def get_corruption_settings(self) -> Dict[str, Any]:
        """
        Get corruption detection settings.

        Returns:
            Dictionary containing corruption settings
        """
        try:
            return await self.operations.get_corruption_settings()
        except Exception as e:
            logger.error(f"Error getting corruption settings: {e}")
            raise

    async def update_corruption_settings(
        self, settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update corruption detection settings.

        Args:
            settings: Dictionary containing corruption settings to update

        Returns:
            Dictionary containing updated corruption settings
        """
        try:
            await self.operations.update_corruption_settings(settings)
            return await self.operations.get_corruption_settings()
        except Exception as e:
            logger.error(f"Error updating corruption settings: {e}")
            raise

    async def get_camera_corruption_settings(self, camera_id: int) -> Dict[str, Any]:
        """
        Get camera-specific corruption settings.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing camera corruption settings
        """
        try:
            return await self.operations.get_camera_corruption_settings(camera_id)
        except Exception as e:
            logger.error(f"Error getting camera {camera_id} corruption settings: {e}")
            raise

    async def analyze_image_quality(
        self, image_id: int, image_path: str
    ) -> Dict[str, Any]:
        """
        Analyze image quality using corruption detection algorithms.

        Args:
            image_id: ID of the image to analyze
            image_path: Path to the image file

        Returns:
            Quality analysis results including scores and decision
        """
        try:
            start_time = await timezone_utils.get_timezone_aware_timestamp_async(
                self.db
            )

            # Get corruption settings for configuration
            settings = await self.get_corruption_settings()

            # Run fast detection (always enabled)
            fast_result = detect_fast_corruption(image_path, config=settings)
            fast_score = fast_result.corruption_score

            # Get camera settings to determine if heavy detection is enabled
            camera_id = await self._get_camera_id_for_image(image_id)
            heavy_score = None
            heavy_result = None

            if camera_id:
                camera_settings = await self.get_camera_corruption_settings(camera_id)
                heavy_detection_enabled = camera_settings.get(
                    "corruption_detection_heavy", False
                )

                if heavy_detection_enabled:
                    heavy_result = detect_heavy_corruption(image_path, config=settings)
                    heavy_score = heavy_result.corruption_score

            # Calculate final corruption score
            final_score = calculate_corruption_score(
                fast_score, heavy_score, config=settings
            )

            # Calculate processing time
            end_time = await timezone_utils.get_timezone_aware_timestamp_async(
                self.settings_ops
            )
            processing_time = (end_time - start_time).total_seconds() * 1000

            # Determine if image is valid (not corrupted)
            calculator = CorruptionScoreCalculator(settings)
            is_valid = not calculator.is_corrupted(final_score)

            # Make auto-discard decision
            discard_decision = await self.make_auto_discard_decision(
                camera_id=camera_id,
                corruption_score=final_score,
                fast_score=fast_score,
                heavy_score=heavy_score,
            )

            result = {
                "success": True,
                "quality_score": final_score,
                "fast_score": fast_score,
                "heavy_score": heavy_score,
                "is_valid": is_valid,
                "auto_discard": discard_decision["should_discard"],
                "discard_reason": discard_decision.get("reason"),
                "action_taken": "flagged" if not is_valid else "accepted",
                "processing_time_ms": processing_time,
                "detection_details": {
                    "fast_result": fast_result.to_dict() if fast_result else None,
                    "heavy_result": heavy_result.to_dict() if heavy_result else None,
                    "calculation_details": calculator.get_calculation_details(),
                },
            }

            # SSE broadcasting handled by higher-level service layer

            return result

        except Exception as e:
            logger.error(f"Image quality analysis failed for image {image_id}: {e}")
            return {"success": False, "error": str(e)}

    async def make_auto_discard_decision(
        self,
        camera_id: Optional[int],
        corruption_score: float,
        fast_score: float,
        heavy_score: Optional[float],
    ) -> Dict[str, Any]:
        """
        Make auto-discard decision based on quality scores and settings.

        Args:
            camera_id: ID of the camera
            corruption_score: Final corruption score
            fast_score: Fast detection score
            heavy_score: Heavy detection score (if available)

        Returns:
            Auto-discard decision results
        """
        try:
            # Get corruption settings for decision thresholds
            global_settings = await self.get_corruption_settings()
            discard_threshold = global_settings.get(
                "corruption_discard_threshold", DEFAULT_CORRUPTION_DISCARD_THRESHOLD
            )

            # Basic threshold check
            should_discard = corruption_score >= discard_threshold
            discard_reason = None

            if should_discard:
                if corruption_score >= CORRUPTION_CRITICAL_THRESHOLD:
                    discard_reason = "critical_corruption_detected"
                elif corruption_score >= discard_threshold:
                    discard_reason = "threshold_exceeded"

                # Additional checks for specific patterns
                if fast_score >= CORRUPTION_FAST_CRITICAL_THRESHOLD:
                    discard_reason = "fast_detection_critical"
                elif heavy_score and heavy_score >= CORRUPTION_HEAVY_CRITICAL_THRESHOLD:
                    discard_reason = "heavy_detection_critical"

            # Log the decision for audit trail
            if camera_id:
                await self.operations.log_discard_decision(
                    camera_id, corruption_score, should_discard, discard_reason
                )

            return {
                "should_discard": should_discard,
                "reason": discard_reason,
                "threshold_used": discard_threshold,
                "score_analysis": {
                    "final_score": corruption_score,
                    "fast_score": fast_score,
                    "heavy_score": heavy_score,
                },
            }

        except Exception as e:
            logger.error(f"Auto-discard decision failed for camera {camera_id}: {e}")
            return {"should_discard": False, "error": str(e)}

    async def assess_camera_health(self, camera_id: int) -> CameraHealthAssessment:
        """
        Assess camera health based on corruption detection history.

        Args:
            camera_id: ID of the camera to assess

        Returns:
            CameraHealthAssessment model with assessment results
        """
        try:
            # Get recent corruption statistics
            recent_stats = await self.get_camera_corruption_stats(camera_id)
            recent_history = await self.get_camera_corruption_history(
                camera_id, hours=24
            )

            # Calculate health metrics
            health_score = 100
            health_issues = []
            recommendations = []

            # Check degraded mode status
            if recent_stats["degraded_mode_active"]:
                health_score -= HEALTH_DEGRADED_MODE_PENALTY
                health_issues.append("Camera is in degraded mode")
                recommendations.append("Investigate camera feed quality")

            # Check consecutive failures
            consecutive_failures = recent_stats["consecutive_corruption_failures"] or 0
            if consecutive_failures > HEALTH_CONSECUTIVE_FAILURES_HIGH_THRESHOLD:
                health_score -= HEALTH_CONSECUTIVE_FAILURES_HIGH_PENALTY
                health_issues.append(
                    f"{consecutive_failures} consecutive corruption failures"
                )
                recommendations.append("Check camera network connectivity")
            elif consecutive_failures > HEALTH_CONSECUTIVE_FAILURES_MEDIUM_THRESHOLD:
                health_score -= HEALTH_CONSECUTIVE_FAILURES_MEDIUM_PENALTY
                health_issues.append(
                    f"{consecutive_failures} recent corruption failures"
                )

            # Check recent average score
            avg_score = recent_stats["recent_average_score"] or 100
            if avg_score < HEALTH_POOR_QUALITY_THRESHOLD:
                health_score -= HEALTH_POOR_QUALITY_PENALTY
                health_issues.append("Poor recent image quality scores")
                recommendations.append("Check camera lens and positioning")
            elif avg_score < HEALTH_AVERAGE_QUALITY_THRESHOLD:
                health_score -= HEALTH_AVERAGE_QUALITY_PENALTY
                health_issues.append("Below-average image quality")

            # Check detection frequency
            recent_detections = len(recent_history)
            if (
                recent_detections > HEALTH_HIGH_DETECTION_THRESHOLD
            ):  # High detection frequency in 24h
                health_score -= HEALTH_HIGH_DETECTION_PENALTY
                health_issues.append("High corruption detection frequency")
                recommendations.append("Monitor camera environmental conditions")

            # Ensure health score doesn't go below 0
            health_score = max(0, health_score)

            # Determine health status
            if health_score >= 80:
                health_status = "healthy"
            elif health_score >= 60:
                health_status = "warning"
            elif health_score >= 30:
                health_status = "degraded"
            else:
                health_status = "critical"

            # Use timezone-aware timestamp
            assessment_timestamp = (
                await timezone_utils.get_timezone_aware_timestamp_async(
                    self.settings_ops
                )
            )

            # Coordinate with camera service for health updates
            if self.camera_service:
                await self.camera_service.update_camera_health(
                    camera_id,
                    {
                        "corruption_health_score": health_score,
                        "corruption_health_status": health_status,
                        "last_corruption_assessment": assessment_timestamp,
                    },
                )

            assessment_result = CameraHealthAssessment(
                camera_id=camera_id,
                health_score=health_score,
                health_status=health_status,
                issues=health_issues,
                recommendations=recommendations,
                assessment_timestamp=assessment_timestamp,
                metrics={
                    "consecutive_failures": consecutive_failures,
                    "avg_quality_score": avg_score,
                    "recent_detections_24h": recent_detections,
                    "degraded_mode_active": recent_stats["degraded_mode_active"]
                    or False,
                },
            )

            # SSE broadcasting handled by higher-level service layer

            logger.info(
                f"Camera {camera_id} health assessment: {health_status} (score: {health_score})"
            )
            return assessment_result

        except Exception as e:
            logger.error(f"Camera health assessment failed for camera {camera_id}: {e}")
            # Return error assessment with timezone-aware timestamp
            error_timestamp = await timezone_utils.get_timezone_aware_timestamp_async(
                self.db
            )
            return CameraHealthAssessment(
                camera_id=camera_id,
                health_score=0,
                health_status="error",
                issues=[f"Assessment failed: {str(e)}"],
                recommendations=["Check system logs and camera connectivity"],
                assessment_timestamp=error_timestamp,
                metrics={},
            )

    async def get_timelapse_quality_statistics(
        self, timelapse_id: int
    ) -> Dict[str, Any]:
        """
        Get quality statistics for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Quality statistics for the timelapse
        """
        try:
            return await self.operations.get_timelapse_quality_statistics(timelapse_id)
        except Exception as e:
            logger.error(
                f"Error getting timelapse {timelapse_id} quality statistics: {e}"
            )
            return {"error": str(e)}

    async def get_camera_quality_statistics(self, camera_id: int) -> Dict[str, Any]:
        """
        Get quality statistics for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Quality statistics for the camera
        """
        try:
            return await self.operations.get_camera_quality_statistics(camera_id)
        except Exception as e:
            logger.error(f"Error getting camera {camera_id} quality statistics: {e}")
            return {"error": str(e)}

    async def get_overall_quality_statistics(self) -> Dict[str, Any]:
        """
        Get overall system quality statistics.

        Returns:
            Overall quality statistics
        """
        try:
            return await self.operations.get_overall_quality_statistics()
        except Exception as e:
            logger.error(f"Error getting overall quality statistics: {e}")
            return {"error": str(e)}

    async def test_image_corruption(
        self, image_data: bytes, filename: str
    ) -> CorruptionTestResponse:
        """
        Test uploaded image for corruption detection without saving to database.

        Args:
            image_data: Raw image bytes from upload
            filename: Original filename for logging

        Returns:
            CorruptionTestResponse with corruption analysis results
        """
        temp_file_path = None
        try:
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name

            # Get corruption settings for configuration
            settings = await self.get_corruption_settings()

            # Run fast detection (always enabled)
            fast_result = detect_fast_corruption(temp_file_path, config=settings)
            fast_score = fast_result.corruption_score

            # Run heavy detection (for testing purposes, always enable)
            heavy_result = detect_heavy_corruption(temp_file_path, config=settings)
            heavy_score = heavy_result.corruption_score

            # Calculate final corruption score
            final_score = calculate_corruption_score(
                fast_score, heavy_score, config=settings
            )

            # Determine if image is corrupted
            calculator = CorruptionScoreCalculator(settings)
            is_corrupted = calculator.is_corrupted(final_score)
            should_auto_discard = calculator.should_auto_discard(final_score)

            # Get image basic info
            image = cv2.imread(temp_file_path)
            height, width = image.shape[:2] if image is not None else (0, 0)

            return CorruptionTestResponse(
                filename=filename,
                file_size_bytes=len(image_data),
                image_dimensions={"width": width, "height": height},
                corruption_analysis={
                    "final_score": final_score,
                    "is_corrupted": is_corrupted,
                    "should_auto_discard": should_auto_discard,
                    "fast_detection": {
                        "score": fast_score,
                        "failed_checks": fast_result.failed_checks,
                        "processing_time_ms": fast_result.processing_time_ms,
                        "details": fast_result.details,
                    },
                    "heavy_detection": {
                        "score": heavy_score,
                        "failed_checks": heavy_result.failed_checks,
                        "processing_time_ms": heavy_result.processing_time_ms,
                        "details": heavy_result.details,
                    },
                },
                recommendation={
                    "action": (
                        "discard"
                        if should_auto_discard
                        else "accept" if not is_corrupted else "review"
                    ),
                    "reason": (
                        "Image quality is below auto-discard threshold"
                        if should_auto_discard
                        else (
                            "Image appears corrupted"
                            if is_corrupted
                            else "Image quality is acceptable"
                        )
                    ),
                },
                settings_used={
                    "corruption_threshold": settings.get(
                        "corruption_threshold", DEFAULT_CORRUPTION_TEST_THRESHOLD
                    ),
                    "auto_discard_threshold": settings.get(
                        "auto_discard_threshold", DEFAULT_AUTO_DISCARD_THRESHOLD
                    ),
                    "fast_weight": settings.get("fast_weight", DEFAULT_FAST_WEIGHT),
                    "heavy_weight": settings.get("heavy_weight", DEFAULT_HEAVY_WEIGHT),
                },
            )

        except Exception as e:
            logger.error(f"Error testing image corruption for {filename}: {e}")
            return CorruptionTestResponse(
                filename=filename,
                file_size_bytes=len(image_data),
                image_dimensions={"width": 0, "height": 0},
                corruption_analysis={
                    "final_score": 100,
                    "is_corrupted": True,
                    "analysis_failed": True,
                },
                recommendation={
                    "action": "discard",
                    "reason": "Analysis failed due to error",
                },
                settings_used={},
                error=str(e),
            )

        finally:
            # Cleanup temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError as e:
                    logger.warning(
                        f"Failed to cleanup temporary file {temp_file_path}: {e}"
                    )

    async def _get_camera_id_for_image(self, image_id: int) -> Optional[int]:
        """Get camera ID for a given image using operations method."""
        try:
            return await self.operations.get_camera_id_for_image(image_id)
        except Exception as e:
            logger.error(f"Error getting camera ID for image {image_id}: {e}")
            return None

    async def _get_camera_corruption_metadata(self, camera_id: int) -> Dict[str, Any]:
        """Get camera corruption metadata using operations method."""
        try:
            return await self.operations.get_camera_corruption_metadata(camera_id)
        except Exception as e:
            logger.error(f"Error getting camera {camera_id} corruption metadata: {e}")
            raise


class SyncCorruptionService:
    """
    Sync corruption service for worker operations.

    Provides quality analysis business logic for sync operations
    with coordination capabilities for worker processes.
    """

    def __init__(self, db: SyncDatabase, camera_service=None):
        """
        Initialize with sync database instance and service dependencies.

        Args:
            db: SyncDatabase instance
            camera_service: Optional SyncCameraService for health coordination
        """
        self.db = db
        self.operations = SyncCorruptionOperations(db)
        from ..database.settings_operations import SyncSettingsOperations

        self.settings_ops = SyncSettingsOperations(db)
        self.camera_service = camera_service

    def log_corruption_detection(
        self,
        camera_id: int,
        image_id: Optional[int],
        corruption_score: int,
        fast_score: Optional[int],
        heavy_score: Optional[int],
        detection_details: Dict[str, Any],
        action_taken: str,
        processing_time_ms: int,
    ) -> CorruptionLogEntry:
        """
        Log a corruption detection result.

        Args:
            camera_id: ID of the camera
            image_id: ID of the image (None if image was discarded)
            corruption_score: Final corruption score (0-100)
            fast_score: Fast detection score (0-100)
            heavy_score: Heavy detection score (0-100, None if not enabled)
            detection_details: Dictionary containing detection details
            action_taken: Action taken ('saved', 'discarded', 'retried')
            processing_time_ms: Processing time in milliseconds

        Returns:
            Created corruption log record
        """
        try:
            result = self.operations.log_corruption_detection(
                camera_id=camera_id,
                image_id=image_id,
                corruption_score=corruption_score,
                fast_score=fast_score,
                heavy_score=heavy_score,
                detection_details=detection_details,
                action_taken=action_taken,
                processing_time_ms=processing_time_ms,
            )

            # SSE broadcasting handled by higher-level service layer

            return result

        except Exception as e:
            logger.error(
                f"Error logging corruption detection for camera {camera_id}: {e}"
            )
            raise

    def get_camera_corruption_failure_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get corruption failure statistics for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing failure statistics
        """
        try:
            return self.operations.get_camera_corruption_failure_stats(camera_id)

        except Exception as e:
            logger.error(
                f"Error getting camera {camera_id} corruption failure stats: {e}"
            )
            raise

    def check_degraded_mode_trigger(
        self, camera_id: int, settings: Dict[str, Any]
    ) -> bool:
        """
        Check if a camera should enter degraded mode.

        Args:
            camera_id: ID of the camera
            settings: Corruption detection settings

        Returns:
            True if camera should enter degraded mode
        """
        try:
            return self.operations.check_degraded_mode_trigger(camera_id, settings)

        except Exception as e:
            logger.error(
                f"Error checking degraded mode trigger for camera {camera_id}: {e}"
            )
            return False

    def set_camera_degraded_mode(self, camera_id: int, is_degraded: bool) -> bool:
        """
        Set camera degraded mode status.

        Args:
            camera_id: ID of the camera
            is_degraded: Whether camera should be in degraded mode

        Returns:
            True if update was successful
        """
        try:
            success = self.operations.set_camera_degraded_mode(camera_id, is_degraded)

            if success:
                mode_text = "enabled" if is_degraded else "disabled"
                logger.info(f"Degraded mode {mode_text} for camera {camera_id}")

                # SSE broadcasting handled by higher-level service layer

            return success

        except Exception as e:
            logger.error(f"Error setting degraded mode for camera {camera_id}: {e}")
            raise

    def reset_camera_corruption_failures(self, camera_id: int) -> bool:
        """
        Reset camera corruption failure counters.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful
        """
        try:
            success = self.operations.reset_camera_corruption_failures(camera_id)

            if success:
                logger.info(f"Reset corruption failure counters for camera {camera_id}")

                # SSE broadcasting handled by higher-level service layer

            return success

        except Exception as e:
            logger.error(
                f"Error resetting corruption failures for camera {camera_id}: {e}"
            )
            raise

    def cleanup_old_corruption_logs(
        self, days_to_keep: int = DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS
    ) -> int:
        """
        Clean up old corruption detection logs.

        Args:
            days_to_keep: Number of days to keep logs (default: from constants)

        Returns:
            Number of logs deleted
        """
        try:
            deleted_count = self.operations.cleanup_old_corruption_logs(days_to_keep)

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old corruption logs")

                # SSE broadcasting handled by higher-level service layer

            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old corruption logs: {e}")
            return 0

    def analyze_image_quality(self, camera_id: int, image_path: str) -> Dict[str, Any]:
        """
        Sync version of image quality analysis for worker processes.

        Args:
            camera_id: ID of the camera
            image_path: Path to the image file

        Returns:
            Quality analysis results
        """
        try:
            start_time = timezone_utils.get_timezone_aware_timestamp_sync(
                self.settings_ops
            )

            # Get corruption settings for configuration
            settings = self.operations.get_corruption_settings()

            # Run fast detection (always enabled)
            fast_result = detect_fast_corruption(image_path, config=settings)
            fast_score = fast_result.corruption_score

            # Check if heavy detection should run
            camera_settings = self.operations.get_camera_corruption_settings(camera_id)
            heavy_detection_enabled = camera_settings and camera_settings.get(
                "corruption_detection_heavy", False
            )

            heavy_score = None
            heavy_result = None

            if heavy_detection_enabled:
                heavy_result = detect_heavy_corruption(image_path, config=settings)
                heavy_score = heavy_result.corruption_score

            # Calculate final corruption score
            final_score = calculate_corruption_score(
                fast_score, heavy_score, config=settings
            )

            # Determine if image is valid (not corrupted)
            calculator = CorruptionScoreCalculator(settings)
            is_valid = not calculator.is_corrupted(final_score)

            # Calculate processing time
            end_time = timezone_utils.get_timezone_aware_timestamp_sync(
                self.settings_ops
            )
            processing_time = (end_time - start_time).total_seconds() * 1000

            return {
                "success": True,
                "quality_score": final_score,
                "fast_score": fast_score,
                "heavy_score": heavy_score,
                "is_valid": is_valid,
                "action_taken": "flagged" if not is_valid else "accepted",
                "processing_time_ms": processing_time,
                "detection_details": {
                    "fast_result": fast_result.to_dict() if fast_result else None,
                    "heavy_result": heavy_result.to_dict() if heavy_result else None,
                    "calculation_details": calculator.get_calculation_details(),
                },
            }

        except Exception as e:
            logger.error(
                f"Sync image quality analysis failed for camera {camera_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def coordinate_degraded_mode_management(self, camera_id: int) -> Dict[str, Any]:
        """
        Coordinate degraded mode management with camera service.

        Args:
            camera_id: ID of the camera

        Returns:
            Degraded mode management results
        """
        try:
            # Check if camera should enter degraded mode
            failure_stats = self.get_camera_corruption_failure_stats(camera_id)
            settings = {"corruption_failure_threshold": 10}  # Default threshold

            should_degrade = self.check_degraded_mode_trigger(camera_id, settings)

            if should_degrade:
                # Set camera to degraded mode
                success = self.set_camera_degraded_mode(camera_id, True)

                # Coordinate with camera service if available
                if self.camera_service and success:
                    self.camera_service.set_camera_degraded_mode(camera_id, True)

                return {
                    "action": "degraded_mode_enabled",
                    "success": success,
                    "reason": "corruption_failure_threshold_exceeded",
                    "failure_stats": failure_stats,
                }
            else:
                # Check if camera can exit degraded mode
                current_failures = failure_stats.get(
                    "consecutive_corruption_failures", 0
                )
                if current_failures == 0:
                    success = self.set_camera_degraded_mode(camera_id, False)

                    # Coordinate with camera service if available
                    if self.camera_service and success:
                        self.camera_service.set_camera_degraded_mode(camera_id, False)

                    return {
                        "action": "degraded_mode_disabled",
                        "success": success,
                        "reason": "consecutive_failures_cleared",
                    }

                return {
                    "action": "no_change",
                    "degraded_mode_active": False,
                    "consecutive_failures": current_failures,
                }

        except Exception as e:
            logger.error(
                f"Degraded mode coordination failed for camera {camera_id}: {e}"
            )
            return {"action": "error", "error": str(e)}
