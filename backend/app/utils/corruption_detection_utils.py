# backend/app/utils/corruption_detection_utils.py
"""
Corruption Detection Utilities

Provides computer vision algorithms for detecting corrupted, distorted,
or invalid images from RTSP camera captures. Contains both fast and heavy
detection algorithms as pure utility functions.
"""

import cv2
import numpy as np
import os
import logging
import time
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result from corruption detection analysis"""

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

    def analyze_image(self, image_path: str) -> DetectionResult:
        """
        Perform fast corruption detection on an image.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with analysis results
        """
        start_time = time.time()
        failed_checks = []
        details = {}

        try:
            # File size check
            if not self._check_file_size(image_path):
                failed_checks.append("file_size")

            # Load image
            image = cv2.imread(image_path)
            if image is None:
                failed_checks.append("image_load")
                return DetectionResult(
                    is_corrupted=True,
                    corruption_score=100.0,
                    failed_checks=failed_checks,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    details={"error": "Could not load image"},
                )

            # Dimension checks
            height, width = image.shape[:2]
            details.update({"width": width, "height": height})

            if not self._check_dimensions(width, height):
                failed_checks.append("dimensions")

            # Brightness check
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            avg_brightness = np.mean(gray)
            details["avg_brightness"] = float(avg_brightness)

            if not self._check_brightness(float(avg_brightness)):
                failed_checks.append("brightness")

            # Contrast check
            contrast = float(np.std(gray))
            details["contrast"] = contrast

            if not self._check_contrast(contrast):
                failed_checks.append("contrast")

            # Simple noise check
            if self._check_excessive_noise(gray):
                failed_checks.append("noise")

            # Calculate corruption score
            corruption_score = (
                len(failed_checks) * 25.0
            )  # Each failed check = 25 points
            is_corrupted = corruption_score > 50.0

            processing_time = (time.time() - start_time) * 1000

            return DetectionResult(
                is_corrupted=is_corrupted,
                corruption_score=corruption_score,
                failed_checks=failed_checks,
                processing_time_ms=processing_time,
                details=details,
            )

        except Exception as e:
            logger.error(f"Fast detection failed for {image_path}: {e}")
            return DetectionResult(
                is_corrupted=True,
                corruption_score=100.0,
                failed_checks=["exception"],
                processing_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
            )

    def _check_file_size(self, image_path: str) -> bool:
        """Check if file size is within acceptable range"""
        try:
            file_size = os.path.getsize(image_path)
            return (
                self.config["min_file_size"]
                <= file_size
                <= self.config["max_file_size"]
            )
        except OSError:
            return False

    def _check_dimensions(self, width: int, height: int) -> bool:
        """Check if image dimensions are reasonable"""
        return (
            self.config["min_width"] <= width <= self.config["max_width"]
            and self.config["min_height"] <= height <= self.config["max_height"]
        )

    def _check_brightness(self, avg_brightness: float) -> bool:
        """Check if average brightness is reasonable"""
        return (
            self.config["min_brightness"]
            <= avg_brightness
            <= self.config["max_brightness"]
        )

    def _check_contrast(self, contrast: float) -> bool:
        """Check if contrast is sufficient"""
        return contrast >= self.config["min_contrast"]

    def _check_excessive_noise(self, gray_image) -> bool:
        """Simple check for excessive noise"""
        # Calculate noise using Laplacian variance
        laplacian_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()
        noise_ratio = laplacian_var / (gray_image.var() + 1e-6)
        return noise_ratio > self.config["max_noise_threshold"]


class HeavyCorruptionDetector:
    """
    Advanced corruption detection using computer vision algorithms.

    More CPU-intensive but catches subtle corruption that fast detection misses.
    Can be disabled per-camera for performance optimization.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with configuration"""
        self.config = config or self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for heavy detection"""
        return {
            "blur_threshold": 100.0,  # Laplacian variance threshold for blur
            "jpeg_quality_threshold": 75,  # Minimum JPEG quality
            "edge_density_threshold": 0.05,  # Minimum edge density
            "color_variance_threshold": 100,  # Minimum color variance
            "histogram_peaks_min": 3,  # Minimum histogram peaks
            "saturation_threshold": 0.1,  # Minimum saturation
        }

    def analyze_image(self, image_path: str) -> DetectionResult:
        """
        Perform heavy corruption detection on an image.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with analysis results
        """
        start_time = time.time()
        failed_checks = []
        details = {}

        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return DetectionResult(
                    is_corrupted=True,
                    corruption_score=100.0,
                    failed_checks=["image_load"],
                    processing_time_ms=(time.time() - start_time) * 1000,
                    details={"error": "Could not load image"},
                )

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Blur detection
            blur_score = self._detect_blur(gray)
            details["blur_score"] = blur_score
            if blur_score < self.config["blur_threshold"]:
                failed_checks.append("blur")

            # Edge density check
            edge_density = self._calculate_edge_density(gray)
            details["edge_density"] = edge_density
            if edge_density < self.config["edge_density_threshold"]:
                failed_checks.append("edge_density")

            # Color variance check
            color_variance = self._calculate_color_variance(image)
            details["color_variance"] = color_variance
            if color_variance < self.config["color_variance_threshold"]:
                failed_checks.append("color_variance")

            # Histogram analysis
            histogram_peaks = self._analyze_histogram(gray)
            details["histogram_peaks"] = histogram_peaks
            if histogram_peaks < self.config["histogram_peaks_min"]:
                failed_checks.append("histogram")

            # Saturation check
            saturation_score = self._calculate_saturation(image)
            details["saturation_score"] = saturation_score
            if saturation_score < self.config["saturation_threshold"]:
                failed_checks.append("saturation")

            # Calculate corruption score
            corruption_score = (
                len(failed_checks) * 20.0
            )  # Each failed check = 20 points
            is_corrupted = corruption_score > 40.0

            processing_time = (time.time() - start_time) * 1000

            return DetectionResult(
                is_corrupted=is_corrupted,
                corruption_score=corruption_score,
                failed_checks=failed_checks,
                processing_time_ms=processing_time,
                details=details,
            )

        except Exception as e:
            logger.error(f"Heavy detection failed for {image_path}: {e}")
            return DetectionResult(
                is_corrupted=True,
                corruption_score=100.0,
                failed_checks=["exception"],
                processing_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
            )

    def _detect_blur(self, gray_image) -> float:
        """Detect image blur using Laplacian variance"""
        return cv2.Laplacian(gray_image, cv2.CV_64F).var()

    def _calculate_edge_density(self, gray_image) -> float:
        """Calculate edge density using Canny edge detection"""
        edges = cv2.Canny(gray_image, 50, 150)
        return np.sum(edges > 0) / (gray_image.shape[0] * gray_image.shape[1])

    def _calculate_color_variance(self, image) -> float:
        """Calculate color variance across channels"""
        b, g, r = cv2.split(image)
        return float(np.var(b) + np.var(g) + np.var(r))

    def _analyze_histogram(self, gray_image) -> int:
        """Analyze histogram to detect meaningful peaks"""
        hist = cv2.calcHist([gray_image], [0], None, [256], [0, 256])
        hist = hist.flatten()

        # Find peaks (local maxima)
        peaks = 0
        for i in range(1, len(hist) - 1):
            if hist[i] > hist[i - 1] and hist[i] > hist[i + 1] and hist[i] > 100:
                peaks += 1

        return peaks

    def _calculate_saturation(self, image) -> float:
        """Calculate average saturation in HSV color space"""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        return float(np.mean(saturation) / 255.0)


class CorruptionScoreCalculator:
    """
    Calculates final corruption scores by combining fast and heavy detection results.

    Implements weighted scoring and decision thresholds for determining
    whether an image should be considered corrupted.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with configuration"""
        self.config = config or self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for score calculation"""
        return {
            "fast_weight": 0.7,  # Weight for fast detection score
            "heavy_weight": 0.3,  # Weight for heavy detection score
            "corruption_threshold": 50.0,  # Threshold for marking as corrupted
            "auto_discard_threshold": 75.0,  # Threshold for auto-discard
            "max_score": 100.0,  # Maximum possible score
        }

    def calculate_final_score(
        self, fast_score: float, heavy_score: Optional[float] = None
    ) -> float:
        """
        Calculate final corruption score from fast and heavy detection results.

        Args:
            fast_score: Score from fast detection (0-100)
            heavy_score: Optional score from heavy detection (0-100)

        Returns:
            Final corruption score (0-100)
        """
        if heavy_score is None:
            # Only fast detection available
            return min(fast_score, self.config["max_score"])

        # Weighted combination of fast and heavy scores
        final_score = (
            fast_score * self.config["fast_weight"]
            + heavy_score * self.config["heavy_weight"]
        )

        return min(final_score, self.config["max_score"])

    def is_corrupted(self, score: float) -> bool:
        """Determine if image is corrupted based on score"""
        return score >= self.config["corruption_threshold"]

    def should_auto_discard(self, score: float) -> bool:
        """Determine if image should be automatically discarded"""
        return score >= self.config["auto_discard_threshold"]

    def get_calculation_details(self) -> Dict[str, Any]:
        """Get details about score calculation configuration"""
        return {
            "fast_weight": self.config["fast_weight"],
            "heavy_weight": self.config["heavy_weight"],
            "corruption_threshold": self.config["corruption_threshold"],
            "auto_discard_threshold": self.config["auto_discard_threshold"],
        }


# Utility functions for external use
def detect_fast_corruption(
    image_path: str, config: Optional[Dict] = None
) -> DetectionResult:
    """
    Utility function for fast corruption detection.

    Args:
        image_path: Path to image file
        config: Optional configuration dict

    Returns:
        DetectionResult with analysis
    """
    detector = FastCorruptionDetector(config)
    return detector.analyze_image(image_path)


def detect_heavy_corruption(
    image_path: str, config: Optional[Dict] = None
) -> DetectionResult:
    """
    Utility function for heavy corruption detection.

    Args:
        image_path: Path to image file
        config: Optional configuration dict

    Returns:
        DetectionResult with analysis
    """
    detector = HeavyCorruptionDetector(config)
    return detector.analyze_image(image_path)


def calculate_corruption_score(
    fast_score: float,
    heavy_score: Optional[float] = None,
    config: Optional[Dict] = None,
) -> float:
    """
    Utility function for calculating final corruption score.

    Args:
        fast_score: Fast detection score (0-100)
        heavy_score: Optional heavy detection score (0-100)
        config: Optional configuration dict

    Returns:
        Final corruption score (0-100)
    """
    calculator = CorruptionScoreCalculator(config)
    return calculator.calculate_final_score(fast_score, heavy_score)
