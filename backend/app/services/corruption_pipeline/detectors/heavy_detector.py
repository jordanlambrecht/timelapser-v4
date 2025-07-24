# backend/app/services/corruption_pipeline/detectors/heavy_detector.py
"""
Heavy Corruption Detector

Advanced corruption detection using computer vision algorithms.
More CPU-intensive but catches subtle corruption that fast detection misses.
Can be disabled per-camera for performance optimization.
"""

import cv2
import numpy as np
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class HeavyDetectionResult:
    """Result from heavy corruption detection analysis"""

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
            "texture_threshold": 50.0,  # Minimum texture complexity
            "symmetry_threshold": 0.3,  # Maximum allowed symmetry (for solid colors)
        }

    def detect(self, image_path: str) -> Dict[str, Any]:
        """
        Perform heavy corruption detection on an image.

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

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Blur detection
            blur_result = self._check_blur(gray)
            details["blur"] = blur_result
            if not blur_result["valid"]:
                failed_checks.append("blur")
                score -= blur_result["penalty"]

            # Edge density check
            edge_result = self._check_edge_density(gray)
            details["edge_density"] = edge_result
            if not edge_result["valid"]:
                failed_checks.append("edge_density")
                score -= edge_result["penalty"]

            # Color variance check
            color_result = self._check_color_variance(image)
            details["color_variance"] = color_result
            if not color_result["valid"]:
                failed_checks.append("color_variance")
                score -= color_result["penalty"]

            # Histogram analysis
            histogram_result = self._check_histogram(gray)
            details["histogram"] = histogram_result
            if not histogram_result["valid"]:
                failed_checks.append("histogram")
                score -= histogram_result["penalty"]

            # Saturation check
            saturation_result = self._check_saturation(image)
            details["saturation"] = saturation_result
            if not saturation_result["valid"]:
                failed_checks.append("saturation")
                score -= saturation_result["penalty"]

            # Texture analysis
            texture_result = self._check_texture(gray)
            details["texture"] = texture_result
            if not texture_result["valid"]:
                failed_checks.append("texture")
                score -= texture_result["penalty"]

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
                    "blur",
                    "edge_density",
                    "color_variance",
                    "histogram",
                    "saturation",
                    "texture",
                ],
            }

        except Exception as e:
            logger.error(f"Error in heavy corruption detection: {e}")
            return {
                "success": False,
                "corruption_score": 0.0,
                "failed_checks": ["detection_error"],
                "detection_time_ms": (time.time() - start_time) * 1000,
                "details": {"error": str(e)},
            }

    def _check_blur(self, gray_image: np.ndarray) -> Dict[str, Any]:
        """Detect image blur using Laplacian variance"""
        try:
            blur_score = cv2.Laplacian(gray_image, cv2.CV_64F).var()
            threshold = self.config["blur_threshold"]

            if blur_score < threshold:
                return {
                    "valid": False,
                    "penalty": 25.0,
                    "reason": f"Image too blurry: {blur_score:.1f} < {threshold}",
                    "blur_score": float(blur_score),
                }
            else:
                return {"valid": True, "penalty": 0.0, "blur_score": float(blur_score)}
        except Exception as e:
            return {
                "valid": False,
                "penalty": 30.0,
                "reason": f"Blur detection error: {e}",
                "blur_score": 0.0,
            }

    def _check_edge_density(self, gray_image: np.ndarray) -> Dict[str, Any]:
        """Calculate edge density using Canny edge detection"""
        try:
            edges = cv2.Canny(gray_image, 50, 150)
            edge_density = np.sum(edges > 0) / (
                gray_image.shape[0] * gray_image.shape[1]
            )
            threshold = self.config["edge_density_threshold"]

            if edge_density < threshold:
                return {
                    "valid": False,
                    "penalty": 20.0,
                    "reason": f"Too few edges: {edge_density:.3f} < {threshold}",
                    "edge_density": float(edge_density),
                }
            else:
                return {
                    "valid": True,
                    "penalty": 0.0,
                    "edge_density": float(edge_density),
                }
        except Exception as e:
            return {
                "valid": False,
                "penalty": 25.0,
                "reason": f"Edge density error: {e}",
                "edge_density": 0.0,
            }

    def _check_color_variance(self, image: np.ndarray) -> Dict[str, Any]:
        """Calculate color variance across channels"""
        try:
            b, g, r = cv2.split(image)
            color_variance = float(np.var(b) + np.var(g) + np.var(r))
            threshold = self.config["color_variance_threshold"]

            if color_variance < threshold:
                return {
                    "valid": False,
                    "penalty": 15.0,
                    "reason": f"Low color variance: {color_variance:.1f} < {threshold}",
                    "color_variance": color_variance,
                }
            else:
                return {"valid": True, "penalty": 0.0, "color_variance": color_variance}
        except Exception as e:
            return {
                "valid": False,
                "penalty": 20.0,
                "reason": f"Color variance error: {e}",
                "color_variance": 0.0,
            }

    def _check_histogram(self, gray_image: np.ndarray) -> Dict[str, Any]:
        """Analyze histogram to detect meaningful peaks"""
        try:
            hist = cv2.calcHist([gray_image], [0], None, [256], [0, 256])
            hist = hist.flatten()

            # Find peaks (local maxima)
            peaks = 0
            for i in range(1, len(hist) - 1):
                if hist[i] > hist[i - 1] and hist[i] > hist[i + 1] and hist[i] > 100:
                    peaks += 1

            min_peaks = self.config["histogram_peaks_min"]

            if peaks < min_peaks:
                return {
                    "valid": False,
                    "penalty": 18.0,
                    "reason": f"Too few histogram peaks: {peaks} < {min_peaks}",
                    "histogram_peaks": peaks,
                }
            else:
                return {"valid": True, "penalty": 0.0, "histogram_peaks": peaks}
        except Exception as e:
            return {
                "valid": False,
                "penalty": 22.0,
                "reason": f"Histogram analysis error: {e}",
                "histogram_peaks": 0,
            }

    def _check_saturation(self, image: np.ndarray) -> Dict[str, Any]:
        """Calculate average saturation in HSV color space"""
        try:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            saturation_score = float(np.mean(saturation) / 255.0)
            threshold = self.config["saturation_threshold"]

            if saturation_score < threshold:
                return {
                    "valid": False,
                    "penalty": 12.0,
                    "reason": f"Low saturation: {saturation_score:.3f} < {threshold}",
                    "saturation_score": saturation_score,
                }
            else:
                return {
                    "valid": True,
                    "penalty": 0.0,
                    "saturation_score": saturation_score,
                }
        except Exception as e:
            return {
                "valid": False,
                "penalty": 15.0,
                "reason": f"Saturation check error: {e}",
                "saturation_score": 0.0,
            }

    def _check_texture(self, gray_image: np.ndarray) -> Dict[str, Any]:
        """Check texture complexity using local binary patterns"""
        try:
            # Simple texture analysis using Sobel operators
            sobel_x = cv2.Sobel(gray_image, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray_image, cv2.CV_64F, 0, 1, ksize=3)
            texture_score = np.mean(np.sqrt(sobel_x**2 + sobel_y**2))
            threshold = self.config["texture_threshold"]

            if texture_score < threshold:
                return {
                    "valid": False,
                    "penalty": 10.0,
                    "reason": f"Low texture complexity: {texture_score:.1f} < {threshold}",
                    "texture_score": float(texture_score),
                }
            else:
                return {
                    "valid": True,
                    "penalty": 0.0,
                    "texture_score": float(texture_score),
                }
        except Exception as e:
            return {
                "valid": False,
                "penalty": 12.0,
                "reason": f"Texture analysis error: {e}",
                "texture_score": 0.0,
            }

    def analyze_image(self, image_path: str) -> HeavyDetectionResult:
        """
        Legacy method for backward compatibility.

        Args:
            image_path: Path to the image file

        Returns:
            HeavyDetectionResult with analysis results
        """
        result = self.detect(image_path)

        return HeavyDetectionResult(
            is_corrupted=not result["success"] or result["corruption_score"] < 60.0,
            corruption_score=result["corruption_score"],
            failed_checks=result["failed_checks"],
            processing_time_ms=result["detection_time_ms"],
            details=result["details"],
        )
