"""
Fast Image Corruption Detection Module

Provides lightweight heuristic checks for obviously corrupted images.
Designed to run in 1-5ms per image with minimal performance impact.
"""

import cv2
import numpy as np
import os
import logging
import time
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FastDetectionResult:
    """Result from fast corruption detection"""

    score: int  # 0-100
    details: Dict[str, Any]
    passed_checks: Dict[str, bool]
    failed_checks: list[str]
    processing_time_ms: float


class FastDetector:
    """Fast heuristic checks for obviously corrupted images"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize fast detector with configuration"""
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(__name__)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for fast detection"""
        return {
            "min_file_size": 1000,  # Minimum file size in bytes
            "max_file_size": 5_000_000,  # Maximum file size in bytes (5MB)
            "min_variance": 10,  # Minimum pixel variance
            "max_uniform_ratio": 0.95,  # Max ratio of identical pixels
            "min_mean": 5,  # Minimum mean intensity
            "max_mean": 250,  # Maximum mean intensity
            "min_nonzero_pixels": 0.1,  # Min ratio of non-zero pixels
            "min_width": 32,  # Minimum image width
            "min_height": 32,  # Minimum image height
        }

    def check_file_size(self, file_path: str) -> Tuple[bool, int]:
        """Check if file size is within reasonable bounds"""
        try:
            if not os.path.exists(file_path):
                return False, 0

            size = os.path.getsize(file_path)
            is_valid = (
                self.config["min_file_size"] <= size <= self.config["max_file_size"]
            )
            return is_valid, size

        except Exception as e:
            self.logger.warning(f"File size check failed: {e}")
            return False, 0

    def check_image_loadable(self, file_path: str) -> Tuple[bool, Optional[np.ndarray]]:
        """Verify image can be loaded and is valid"""
        try:
            img = cv2.imread(file_path)
            if img is None or img.size == 0:
                return False, None

            # Check minimum dimensions
            height, width = img.shape[:2]
            if height < self.config["min_height"] or width < self.config["min_width"]:
                return False, None

            return True, img

        except Exception as e:
            self.logger.warning(f"Image load check failed: {e}")
            return False, None

    def check_pixel_statistics(self, img: np.ndarray) -> Dict[str, Any]:
        """Fast statistical checks on pixel values"""
        if img is None or img.size == 0:
            return {"valid": False, "reason": "empty_image"}

        try:
            # Convert to grayscale for analysis
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img

            # Calculate basic statistics
            mean_val = float(np.mean(gray))
            variance = float(np.var(gray))

            checks = {}
            failed_tests = []

            # Check variance (corrupted images often have very low/high variance)
            checks["variance_ok"] = variance >= self.config["min_variance"]
            if not checks["variance_ok"]:
                failed_tests.append(f"low_variance_{variance:.1f}")

            # Check mean intensity (all black/white images)
            checks["mean_ok"] = (
                self.config["min_mean"] <= mean_val <= self.config["max_mean"]
            )
            if not checks["mean_ok"]:
                if mean_val < self.config["min_mean"]:
                    failed_tests.append(f"too_dark_{mean_val:.1f}")
                else:
                    failed_tests.append(f"too_bright_{mean_val:.1f}")

            # Check for too many identical pixels (uniform corruption)
            unique_values, counts = np.unique(gray, return_counts=True)
            max_count_ratio = float(np.max(counts)) / gray.size
            checks["uniformity_ok"] = (
                max_count_ratio <= self.config["max_uniform_ratio"]
            )
            if not checks["uniformity_ok"]:
                failed_tests.append(f"too_uniform_{max_count_ratio:.2f}")

            # Check for mostly zero pixels (corruption pattern)
            nonzero_ratio = float(np.count_nonzero(gray)) / gray.size
            checks["nonzero_ok"] = nonzero_ratio >= self.config["min_nonzero_pixels"]
            if not checks["nonzero_ok"]:
                failed_tests.append(f"mostly_empty_{nonzero_ratio:.2f}")

            # Overall validity
            checks["valid"] = all(
                [
                    checks["variance_ok"],
                    checks["mean_ok"],
                    checks["uniformity_ok"],
                    checks["nonzero_ok"],
                ]
            )

            # Add detailed statistics
            checks.update(
                {
                    "mean_intensity": mean_val,
                    "variance": variance,
                    "max_uniform_ratio": max_count_ratio,
                    "nonzero_ratio": nonzero_ratio,
                    "failed_tests": failed_tests,
                }
            )

            return checks

        except Exception as e:
            self.logger.warning(f"Pixel statistics check failed: {e}")
            return {"valid": False, "reason": f"analysis_error_{str(e)[:50]}"}

    def analyze_frame(
        self, frame: Optional[np.ndarray], file_path: Optional[str] = None
    ) -> FastDetectionResult:
        """
        Analyze an OpenCV frame for corruption
        Args:
            frame: numpy array from cv2.VideoCapture
            file_path: optional file path for size checks
        """
        start_time = time.time()

        try:
            details = {}
            passed_checks = {}
            failed_checks = []

            # File size check (if file_path provided)
            if file_path:
                size_ok, file_size = self.check_file_size(file_path)
                details["file_size"] = file_size
                passed_checks["file_size"] = size_ok
                if not size_ok:
                    if file_size == 0:
                        failed_checks.append("zero_file_size")
                    elif file_size < self.config["min_file_size"]:
                        failed_checks.append(f"file_too_small_{file_size}")
                    else:
                        failed_checks.append(f"file_too_large_{file_size}")

            # Frame validity check
            if frame is None or frame.size == 0:
                failed_checks.append("invalid_frame")
                passed_checks["frame_valid"] = False
            else:
                passed_checks["frame_valid"] = True

                # Pixel statistics check
                pixel_stats = self.check_pixel_statistics(frame)
                details["pixel_stats"] = pixel_stats
                passed_checks["pixel_stats"] = pixel_stats["valid"]

                if not pixel_stats["valid"]:
                    failed_checks.extend(pixel_stats.get("failed_tests", []))

            # Calculate score based on spec penalty system
            score = self._calculate_fast_score(passed_checks, failed_checks, details)

            processing_time = (time.time() - start_time) * 1000  # Convert to ms

            return FastDetectionResult(
                score=score,
                details=details,
                passed_checks=passed_checks,
                failed_checks=failed_checks,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            self.logger.error(f"Fast detection analysis failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            return FastDetectionResult(
                score=0,  # Complete failure
                details={"error": str(e)},
                passed_checks={},
                failed_checks=["analysis_exception"],
                processing_time_ms=processing_time,
            )

    def _calculate_fast_score(
        self,
        passed_checks: Dict[str, bool],
        failed_checks: list[str],
        details: Dict[str, Any],
    ) -> int:
        """Calculate fast detection score based on penalty system from spec"""
        base_score = 100

        # File size penalties
        if "zero_file_size" in failed_checks:
            base_score -= 100  # Complete failure
        elif any("file_too_small" in check for check in failed_checks):
            base_score -= 20  # Suspiciously small
        elif any("file_too_large" in check for check in failed_checks):
            base_score -= 15  # Unexpectedly large

        # Frame validity penalty
        if not passed_checks.get("frame_valid", True):
            base_score -= 100  # Complete failure

        # Pixel statistics penalties
        if not passed_checks.get("pixel_stats", True):
            pixel_stats = details.get("pixel_stats", {})

            # Mean intensity penalties
            if any("too_dark" in check for check in failed_checks):
                base_score -= 15
            elif any("too_bright" in check for check in failed_checks):
                base_score -= 15

            # Variance penalty
            if any("low_variance" in check for check in failed_checks):
                base_score -= 10

            # Uniformity penalty
            if any("too_uniform" in check for check in failed_checks):
                base_score -= 20

            # Empty image penalty
            if any("mostly_empty" in check for check in failed_checks):
                base_score -= 25

        return max(0, min(100, base_score))
