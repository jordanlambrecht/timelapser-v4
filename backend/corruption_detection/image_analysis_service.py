"""
Image Analysis Service

Service layer for corruption detection on uploaded images.
Encapsulates heavy image processing logic and provides clean interface for API routes.
"""

import tempfile
import os
import time
from typing import Dict, Any, Optional
import cv2

from .controller import CorruptionController
from .models import CorruptionResult


class ImageAnalysisService:
    """Service for analyzing uploaded images for corruption detection"""

    def __init__(self, sync_db=None):
        """Initialize with optional database connection"""
        self.sync_db = sync_db
        self.controller = None

    def _get_controller(
        self, heavy_detection_enabled: bool = True
    ) -> CorruptionController:
        """Get or create corruption controller with specified settings"""
        config = {
            "corruption_detection_enabled": True,
            "corruption_score_threshold": 70,
            "corruption_auto_discard_enabled": False,
            "heavy_detection_enabled": heavy_detection_enabled,
            "retry_enabled": False,  # No retry for test images
            "max_retries": 0,
        }

        return CorruptionController(config=config, sync_db=self.sync_db)

    async def analyze_uploaded_image(
        self, image_data: bytes, heavy_detection_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze uploaded image data for corruption

        Args:
            image_data: Raw image bytes
            heavy_detection_enabled: Whether to run heavy detection analysis

        Returns:
            Dictionary with analysis results in API-friendly format
        """
        if len(image_data) == 0:
            raise ValueError("Empty image data")

        # Create temporary file for OpenCV processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(image_data)
            temp_file.flush()
            temp_path = temp_file.name

        try:
            # Load image with OpenCV
            frame = cv2.imread(temp_path)
            if frame is None:
                raise ValueError("Could not read image file")

            # Run corruption analysis using existing controller
            start_time = time.time()
            controller = self._get_controller(heavy_detection_enabled)

            result = controller.evaluate_frame(
                frame=frame,
                file_path=temp_path,
                camera_id=None,  # Test image, no camera
                heavy_detection_enabled=heavy_detection_enabled,
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Convert result to API-friendly format
            return self._format_analysis_result(result, processing_time_ms)

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _format_analysis_result(
        self, result: CorruptionResult, processing_time_ms: int
    ) -> Dict[str, Any]:
        """Format CorruptionResult for API response"""
        corruption_score = result.corruption_score

        # Determine action based on score
        threshold = corruption_score.threshold_used
        if result.score >= threshold:
            action_taken = "saved"
        elif result.score >= 30:
            action_taken = "flagged_for_review"
        else:
            action_taken = "would_be_discarded"

        # Extract failed checks from details
        failed_checks = []
        details = corruption_score.details

        # Get fast detection failures
        fast_checks = details.get("fast_detection", {})
        for check_name, check_result in fast_checks.items():
            if isinstance(check_result, dict) and not check_result.get("passed", True):
                failed_checks.append(f"Fast: {check_name}")

        # Get heavy detection failures
        heavy_checks = details.get("heavy_detection", {})
        for check_name, check_result in heavy_checks.items():
            if isinstance(check_result, dict) and not check_result.get("passed", True):
                failed_checks.append(f"Heavy: {check_name}")

        return {
            "corruption_score": int(result.score),
            "fast_score": int(corruption_score.fast_score or 100),
            "heavy_score": int(corruption_score.heavy_score or 100),
            "processing_time_ms": int(processing_time_ms),
            "action_taken": str(action_taken),
            "detection_details": {
                "fast_detection": self._convert_checks_to_json(fast_checks),
                "heavy_detection": self._convert_checks_to_json(heavy_checks),
            },
            "failed_checks": [str(check) for check in failed_checks],
        }

    def _convert_checks_to_json(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """Convert check results to JSON-serializable format"""
        json_checks = {}
        for key, value in checks.items():
            if isinstance(value, dict):
                json_checks[key] = {
                    "passed": bool(value.get("passed", True)),
                    "reason": str(value.get("reason", "")),
                }
            else:
                json_checks[key] = {"passed": bool(value), "reason": ""}
        return json_checks

    def validate_image_type(self, content_type: Optional[str]) -> bool:
        """Validate that the uploaded file is an image"""
        if not content_type:
            return False
        return content_type.startswith("image/")
