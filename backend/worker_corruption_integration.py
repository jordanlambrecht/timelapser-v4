"""
Worker Integration Module for Corruption Detection

Provides integration functions for corruption detection in the worker capture pipeline.
Designed to work with the existing AsyncTimelapseWorker architecture.
"""

import asyncio
import cv2
import os
import logging
from typing import Dict, Any, Optional, Tuple
from corruption_detection.controller import CorruptionController


class WorkerCorruptionIntegration:
    """Integration class for corruption detection in worker processes"""

    def __init__(self, sync_db):
        """Initialize with sync database reference"""
        self.sync_db = sync_db
        self.corruption_controller = None
        self.logger = logging.getLogger(__name__)
        self._initialize_controller()

    def _initialize_controller(self):
        """Initialize corruption controller with settings from database"""
        try:
            # Get settings from database
            settings = self.sync_db.get_corruption_settings()

            # Create controller with database settings
            self.corruption_controller = CorruptionController(settings)

            self.logger.info("Corruption detection initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize corruption detection: {e}")
            # Create controller with defaults if database fails
            self.corruption_controller = CorruptionController()

    def evaluate_captured_image(
        self, camera_id: int, file_path: str, timelapse_id: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate a captured image for corruption

        Args:
            camera_id: Camera ID
            file_path: Path to captured image file
            timelapse_id: Active timelapse ID

        Returns:
            Tuple of (is_valid, evaluation_details)
        """
        try:
            # Check if corruption detection is enabled
            if not self.corruption_controller:
                return True, {"detection_disabled": True}

            # Get per-camera corruption settings
            camera_settings = self.sync_db.get_camera_corruption_settings(camera_id)
            heavy_detection_enabled = camera_settings.get(
                "corruption_detection_heavy", False
            )

            # Load the image using OpenCV
            frame = cv2.imread(file_path)
            if frame is None:
                self.logger.error(
                    f"Could not load image for corruption check: {file_path}"
                )
                return True, {"error": "could_not_load_image"}

            # Evaluate the frame with per-camera heavy detection setting
            result = self.corruption_controller.evaluate_frame(
                frame=frame,
                file_path=file_path,
                camera_id=camera_id,
                heavy_detection_enabled=heavy_detection_enabled,
            )

            # Log corruption detection result
            self.sync_db.log_corruption_detection(
                camera_id=camera_id,
                image_id=None,  # Will be set after database record creation
                corruption_score=result.score,
                fast_score=result.corruption_score.fast_score,
                heavy_score=result.corruption_score.heavy_score,
                detection_details=result.corruption_score.details,
                action_taken=result.action_taken,
                processing_time_ms=int(
                    result.corruption_score.details.get("total_processing_time_ms", 0)
                ),
            )

            # Update camera corruption statistics
            self.sync_db.update_camera_corruption_stats(
                camera_id=camera_id,
                corruption_score=result.score,
                is_valid=result.is_valid,
            )

            # Check for degraded mode trigger
            if not result.is_valid:
                should_degrade = self.sync_db.check_degraded_mode_trigger(camera_id)
                if should_degrade:
                    self.sync_db.set_camera_degraded_mode(camera_id, True)
                    self.logger.warning(
                        f"Camera {camera_id} entered degraded mode due to corruption"
                    )

            # Broadcast corruption event if image was flagged
            if not result.is_valid:
                failed_checks = result.corruption_score.details.get(
                    "fast_failed_checks", []
                )
                heavy_failed_checks = result.corruption_score.details.get(
                    "heavy_failed_checks", []
                )
                all_failed_checks = failed_checks + heavy_failed_checks
                processing_time = result.corruption_score.details.get(
                    "total_processing_time_ms", 0
                )

                self.sync_db.broadcast_corruption_event(
                    camera_id=camera_id,
                    corruption_score=result.score,
                    is_corrupted=not result.is_valid,
                    action_taken=result.action_taken,
                    failed_checks=all_failed_checks,
                    processing_time_ms=processing_time,
                )

            return result.is_valid, result.to_dict()

        except Exception as e:
            self.logger.error(
                f"Corruption evaluation failed for camera {camera_id}: {e}"
            )
            # Return valid if evaluation fails to avoid blocking captures
            return True, {"error": str(e)}

    def evaluate_with_retry(
        self, camera_id: int, rtsp_url: str, capture_func, timelapse_id: int
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """
        Evaluate image with retry logic

        Args:
            camera_id: Camera ID
            rtsp_url: RTSP URL for retry capture
            capture_func: Function to call for image capture
            timelapse_id: Active timelapse ID

        Returns:
            Tuple of (success, message, file_path, corruption_details)
        """
        try:
            # First capture attempt
            success, message, file_path = capture_func()

            if not success:
                return success, message, file_path, {"capture_failed": True}

            # Evaluate for corruption
            is_valid, corruption_details = self.evaluate_captured_image(
                camera_id, file_path, timelapse_id
            )

            if is_valid:
                return True, message, file_path, corruption_details

            # Image is corrupted - check if retry is enabled
            settings = self.sync_db.get_corruption_settings()
            if not settings.get("corruption_auto_discard_enabled", False):
                # Auto-discard is disabled, keep the image but flag it
                self.logger.warning(
                    f"Camera {camera_id}: Corrupted image kept (auto-discard disabled)"
                )
                return True, f"{message} (flagged)", file_path, corruption_details

            # Auto-discard is enabled - try retry
            self.logger.info(
                f"Camera {camera_id}: Image corrupted (score: {corruption_details.get('score', 0)}), attempting retry"
            )

            # Delete the corrupted image
            try:
                os.remove(file_path)
            except Exception as e:
                self.logger.warning(
                    f"Failed to delete corrupted image {file_path}: {e}"
                )

            # Attempt retry
            retry_success, retry_message, retry_file_path = capture_func()

            if not retry_success:
                return False, f"Retry failed: {retry_message}", "", corruption_details

            # Evaluate retry
            retry_is_valid, retry_corruption_details = self.evaluate_captured_image(
                camera_id, retry_file_path, timelapse_id
            )

            if retry_is_valid:
                self.logger.info(f"Camera {camera_id}: Retry successful")
                return (
                    True,
                    f"Retry successful: {retry_message}",
                    retry_file_path,
                    retry_corruption_details,
                )
            else:
                self.logger.warning(f"Camera {camera_id}: Retry also failed")
                # Keep the retry image but flag it
                return (
                    True,
                    f"Retry failed (flagged): {retry_message}",
                    retry_file_path,
                    retry_corruption_details,
                )

        except Exception as e:
            self.logger.error(f"Corruption evaluation with retry failed: {e}")
            # Return original capture result if corruption evaluation fails
            return capture_func() + ({"error": str(e)},)

    def refresh_settings(self):
        """Refresh corruption detection settings from database"""
        try:
            settings = self.sync_db.get_corruption_settings()
            if self.corruption_controller:
                self.corruption_controller.update_config(settings)
                self.logger.debug("Corruption detection settings refreshed")
        except Exception as e:
            self.logger.error(f"Failed to refresh corruption settings: {e}")


# Global integration instance (will be initialized by worker)
worker_corruption_integration: Optional[WorkerCorruptionIntegration] = None


def initialize_worker_corruption_detection(sync_db) -> WorkerCorruptionIntegration:
    """Initialize the global worker corruption integration"""
    global worker_corruption_integration
    worker_corruption_integration = WorkerCorruptionIntegration(sync_db)
    return worker_corruption_integration


def get_worker_corruption_integration() -> Optional[WorkerCorruptionIntegration]:
    """Get the global worker corruption integration instance"""
    return worker_corruption_integration
