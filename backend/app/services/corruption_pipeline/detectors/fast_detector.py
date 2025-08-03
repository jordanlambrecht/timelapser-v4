# backend/app/services/corruption_pipeline/detectors/fast_detector.py
"""
Fast Corruption Detector

Lightweight heuristic checks for obviously corrupted images.
Designed to run in 1-5ms per image with minimal performance impact.
These are basic sanity checks that catch obvious corruption.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np

from ....enums import LoggerName
from ....services.logger import LogEmoji, get_service_logger

logger = get_service_logger(LoggerName.CORRUPTION_PIPELINE)


@dataclass
class FastDetectionResult:
    """Result from fast corruption detection analysis"""

    is_corrupted: bool
    corruption_score: float
    failed_checks: list
    processing_time_ms: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            "is_corrupted": self.is_corrupted,
            "corruption_score": self.corruption_score,
            "failed_checks": self.failed_checks,
            "processing_time_ms": self.processing_time_ms,
            "details": self.details,
        }


class FastCorruptionDetector:
    """
    Fast heuristic checks for obviously corrupted images.

    Designed to run in 1-5ms per image with minimal performance impact.
    These are basic sanity checks that catch obvious corruption.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with configuration"""
        self.config = config or self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for fast detection"""
        return {
            "min_file_size": 1024,  # 1KB minimum file size
            "max_file_size": 50 * 1024 * 1024,  # 50MB maximum file size
            "min_width": 100,  # Minimum image width
            "min_height": 100,  # Minimum image height
            "max_width": 10000,  # Maximum reasonable width
            "max_height": 10000,  # Maximum reasonable height
            "min_brightness": 5,  # Minimum average brightness
            "max_brightness": 250,  # Maximum average brightness
            "min_contrast": 0.1,  # Minimum contrast ratio
            "max_noise_threshold": 0.8,  # Maximum noise ratio
        }

    def detect(self, image_path: str) -> Dict[str, Any]:
        """
        Perform fast corruption detection on an image.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary with detection results
        """
        start_time = time.time()
        failed_checks = []
        details = {}
        score = 100.0  # Start with perfect score

        try:
            # File size check
            file_size_result = self._check_file_size(image_path)
            details["file_size"] = file_size_result
            if not file_size_result["valid"]:
                failed_checks.append("file_size")
                score -= file_size_result["penalty"]

            # Load image
            image = cv2.imread(image_path)
            if image is None:
                failed_checks.append("image_load")
                return {
                    "success": False,
                    "corruption_score": 0.0,
                    "failed_checks": failed_checks,
                    "detection_time_ms": (time.time() - start_time) * 1000,
                    "details": {"error": "Could not load image"},
                }

            # Dimension checks
            dimension_result = self._check_dimensions(image)
            details["dimensions"] = dimension_result
            if not dimension_result["valid"]:
                failed_checks.append("dimensions")
                score -= dimension_result["penalty"]

            # Brightness checks
            brightness_result = self._check_brightness(image)
            details["brightness"] = brightness_result
            if not brightness_result["valid"]:
                failed_checks.append("brightness")
                score -= brightness_result["penalty"]

            # Uniformity checks
            uniformity_result = self._check_uniformity(image)
            details["uniformity"] = uniformity_result
            if not uniformity_result["valid"]:
                failed_checks.append("uniformity")
                score -= uniformity_result["penalty"]

            # Ensure score doesn't go below 0
            score = max(0.0, score)

            processing_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "corruption_score": score,
                "failed_checks": failed_checks,
                "detection_time_ms": processing_time,
                "details": details,
                "checks_performed": [
                    "file_size",
                    "dimensions",
                    "brightness",
                    "uniformity",
                ],
            }

        except Exception as e:
            logger.error(
                "Error in fast corruption detection", exception=e, emoji=LogEmoji.FAILED
            )
            return {
                "success": False,
                "corruption_score": 0.0,
                "failed_checks": ["detection_error"],
                "detection_time_ms": (time.time() - start_time) * 1000,
                "details": {"error": str(e)},
            }

    def _check_file_size(self, image_path: str) -> Dict[str, Any]:
        """Check if file size is within reasonable bounds"""
        try:
            file_size = os.path.getsize(image_path)
            min_size = self.config["min_file_size"]
            max_size = self.config["max_file_size"]

            if file_size < min_size:
                return {
                    "valid": False,
                    "penalty": 50.0,
                    "reason": f"File too small: {file_size} < {min_size} bytes",
                    "file_size": file_size,
                }
            elif file_size > max_size:
                return {
                    "valid": False,
                    "penalty": 30.0,
                    "reason": f"File too large: {file_size} > {max_size} bytes",
                    "file_size": file_size,
                }
            else:
                return {"valid": True, "penalty": 0.0, "file_size": file_size}
        except Exception as e:
            return {
                "valid": False,
                "penalty": 100.0,
                "reason": f"File access error: {e}",
                "file_size": 0,
            }

    def _check_dimensions(self, image: np.ndarray) -> Dict[str, Any]:
        """Check if image dimensions are reasonable"""
        try:
            height, width = image.shape[:2]
            min_width = self.config["min_width"]
            min_height = self.config["min_height"]
            max_width = self.config["max_width"]
            max_height = self.config["max_height"]

            if width < min_width or height < min_height:
                return {
                    "valid": False,
                    "penalty": 40.0,
                    "reason": f"Image too small: {width}x{height}",
                    "width": width,
                    "height": height,
                }
            elif width > max_width or height > max_height:
                return {
                    "valid": False,
                    "penalty": 20.0,
                    "reason": f"Image too large: {width}x{height}",
                    "width": width,
                    "height": height,
                }
            else:
                return {"valid": True, "penalty": 0.0, "width": width, "height": height}
        except Exception as e:
            return {
                "valid": False,
                "penalty": 100.0,
                "reason": f"Dimension check error: {e}",
                "width": 0,
                "height": 0,
            }

    def _check_brightness(self, image: np.ndarray) -> Dict[str, Any]:
        """Check if image brightness is within reasonable bounds"""
        try:
            # Convert to grayscale for brightness analysis
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            mean_brightness = np.mean(gray)
            min_brightness = self.config["min_brightness"]
            max_brightness = self.config["max_brightness"]

            if mean_brightness < min_brightness:
                return {
                    "valid": False,
                    "penalty": 25.0,
                    "reason": f"Image too dark: {mean_brightness:.1f}",
                    "mean_brightness": float(mean_brightness),
                }
            elif mean_brightness > max_brightness:
                return {
                    "valid": False,
                    "penalty": 25.0,
                    "reason": f"Image too bright: {mean_brightness:.1f}",
                    "mean_brightness": float(mean_brightness),
                }
            else:
                return {
                    "valid": True,
                    "penalty": 0.0,
                    "mean_brightness": float(mean_brightness),
                }
        except Exception as e:
            return {
                "valid": False,
                "penalty": 30.0,
                "reason": f"Brightness check error: {e}",
                "mean_brightness": 0.0,
            }

    def _check_uniformity(self, image: np.ndarray) -> Dict[str, Any]:
        """Check for excessive uniformity which might indicate corruption"""
        try:
            # Convert to grayscale for uniformity analysis
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # Calculate variance to detect uniform images
            variance = np.var(gray)
            unique_values = len(np.unique(gray))
            total_pixels = gray.size
            unique_ratio = unique_values / total_pixels

            if variance < 10.0:  # Very low variance indicates uniform image
                return {
                    "valid": False,
                    "penalty": 35.0,
                    "reason": f"Image too uniform: variance={variance:.1f}",
                    "variance": float(variance),
                    "unique_ratio": float(unique_ratio),
                }
            elif unique_ratio < 0.01:  # Less than 1% unique pixels
                return {
                    "valid": False,
                    "penalty": 40.0,
                    "reason": f"Too few unique pixels: {unique_ratio:.3f}",
                    "variance": float(variance),
                    "unique_ratio": float(unique_ratio),
                }
            else:
                return {
                    "valid": True,
                    "penalty": 0.0,
                    "variance": float(variance),
                    "unique_ratio": float(unique_ratio),
                }
        except Exception as e:
            return {
                "valid": False,
                "penalty": 30.0,
                "reason": f"Uniformity check error: {e}",
                "variance": 0.0,
                "unique_ratio": 0.0,
            }

    def analyze_image(self, image_path: str) -> FastDetectionResult:
        """
        Legacy method for backward compatibility.

        Args:
            image_path: Path to the image file

        Returns:
            FastDetectionResult with analysis results
        """
        result = self.detect(image_path)

        return FastDetectionResult(
            is_corrupted=not result["success"] or result["corruption_score"] < 70.0,
            corruption_score=result["corruption_score"],
            failed_checks=result["failed_checks"],
            processing_time_ms=result["detection_time_ms"],
            details=result["details"],
        )
