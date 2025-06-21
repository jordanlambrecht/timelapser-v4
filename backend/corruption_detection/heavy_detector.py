"""
Heavy Detector for advanced computer vision-based corruption detection.

This module implements sophisticated image quality analysis using OpenCV
for detecting blur, noise, edge anomalies, and compression artifacts.
Processing time: 20-100ms per image.
"""

import cv2
import numpy as np
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class HeavyDetector:
    """
    Advanced corruption detection using computer vision algorithms.

    Implements:
    - Blur detection via Laplacian variance
    - Edge analysis via Canny edge detection
    - Noise detection via median filter comparison
    - Histogram entropy analysis
    - JPEG compression artifact detection
    """

    def __init__(self):
        """Initialize heavy detector with algorithm parameters."""
        # Blur detection thresholds
        self.blur_threshold = 100.0  # Laplacian variance threshold

        # Edge analysis parameters
        self.edge_low_threshold = 50
        self.edge_high_threshold = 150
        self.edge_density_min = 0.01  # 1% minimum edge density
        self.edge_density_max = 0.50  # 50% maximum edge density

        # Noise detection parameters
        self.noise_ratio_max = 0.30  # 30% maximum noise ratio

        # Histogram analysis parameters
        self.entropy_min = 3.0  # Minimum entropy for good distribution

        # Pattern detection parameters
        self.block_size = 8  # 8x8 blocks for JPEG corruption detection
        self.block_corruption_max = 0.80  # 80% maximum block uniformity

    def analyze(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Perform comprehensive heavy analysis on the image frame.

        Args:
            frame: OpenCV image array (BGR format)

        Returns:
            Dictionary containing analysis results and calculated score
        """
        try:
            start_time = cv2.getTickCount()

            # Convert to grayscale for most analyses
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Perform all detection methods
            blur_result = self._detect_blur(gray)
            edge_result = self._analyze_edges(gray)
            noise_result = self._detect_noise(frame, gray)
            histogram_result = self._analyze_histogram(frame)
            pattern_result = self._detect_corruption_patterns(gray)

            # Calculate processing time
            end_time = cv2.getTickCount()
            processing_time_ms = (
                (end_time - start_time) / cv2.getTickFrequency()
            ) * 1000

            # Combine all results
            results = {
                "blur_detection": blur_result,
                "edge_analysis": edge_result,
                "noise_detection": noise_result,
                "histogram_analysis": histogram_result,
                "pattern_detection": pattern_result,
                "processing_time_ms": round(processing_time_ms, 2),
            }

            # Calculate heavy score
            heavy_score = self._calculate_heavy_score(results)
            results["heavy_score"] = heavy_score

            return results

        except Exception as e:
            logger.error(f"Heavy detection failed: {e}")
            return {
                "error": str(e),
                "heavy_score": 50,  # Default middle score on failure
                "processing_time_ms": 0,
            }

    def _detect_blur(self, gray: np.ndarray) -> Dict[str, Any]:
        """
        Detect blur using Laplacian variance method.

        Args:
            gray: Grayscale image

        Returns:
            Dictionary with blur detection results
        """
        try:
            # Calculate Laplacian variance
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = np.var(laplacian)

            # Determine if blurred
            is_blurred = variance < self.blur_threshold
            penalty = -30 if is_blurred else 0

            return {
                "laplacian_variance": round(variance, 2),
                "is_blurred": is_blurred,
                "threshold": self.blur_threshold,
                "penalty": penalty,
                "reason": (
                    f"Laplacian variance {variance:.1f} < {self.blur_threshold}"
                    if is_blurred
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Blur detection failed: {e}")
            return {"error": str(e), "penalty": 0}

    def _analyze_edges(self, gray: np.ndarray) -> Dict[str, Any]:
        """
        Analyze edge distribution using Canny edge detection.

        Args:
            gray: Grayscale image

        Returns:
            Dictionary with edge analysis results
        """
        try:
            # Apply Canny edge detection
            edges = cv2.Canny(gray, self.edge_low_threshold, self.edge_high_threshold)

            # Calculate edge density
            total_pixels = gray.shape[0] * gray.shape[1]
            edge_pixels = np.count_nonzero(edges)
            edge_density = edge_pixels / total_pixels

            # Check if edge density is abnormal
            is_abnormal = (
                edge_density < self.edge_density_min
                or edge_density > self.edge_density_max
            )
            penalty = -25 if is_abnormal else 0

            reason = None
            if edge_density < self.edge_density_min:
                reason = f"Too few edges: {edge_density:.3f} < {self.edge_density_min}"
            elif edge_density > self.edge_density_max:
                reason = f"Too many edges: {edge_density:.3f} > {self.edge_density_max}"

            return {
                "edge_density": round(edge_density, 4),
                "edge_pixels": edge_pixels,
                "total_pixels": total_pixels,
                "is_abnormal": is_abnormal,
                "penalty": penalty,
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Edge analysis failed: {e}")
            return {"error": str(e), "penalty": 0}

    def _detect_noise(self, frame: np.ndarray, gray: np.ndarray) -> Dict[str, Any]:
        """
        Detect noise using median filter comparison.

        Args:
            frame: Original color image
            gray: Grayscale version

        Returns:
            Dictionary with noise detection results
        """
        try:
            # Apply median filter to reduce noise
            filtered = cv2.medianBlur(gray, 5)

            # Calculate difference between original and filtered
            diff = cv2.absdiff(gray, filtered)

            # Calculate noise ratio
            total_pixels = gray.shape[0] * gray.shape[1]
            noise_pixels = np.count_nonzero(
                np.where(diff > 10, 1, 0)
            )  # Pixels with significant difference
            noise_ratio = noise_pixels / total_pixels

            # Check if noise is excessive
            is_noisy = noise_ratio > self.noise_ratio_max
            penalty = -20 if is_noisy else 0

            return {
                "noise_ratio": round(noise_ratio, 4),
                "noise_pixels": noise_pixels,
                "is_noisy": is_noisy,
                "threshold": self.noise_ratio_max,
                "penalty": penalty,
                "reason": (
                    f"Noise ratio {noise_ratio:.3f} > {self.noise_ratio_max}"
                    if is_noisy
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Noise detection failed: {e}")
            return {"error": str(e), "penalty": 0}

    def _analyze_histogram(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Analyze color distribution using histogram entropy.

        Args:
            frame: Color image (BGR)

        Returns:
            Dictionary with histogram analysis results
        """
        try:
            # Convert to grayscale for histogram analysis
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])

            # Normalize histogram
            hist_norm = hist / hist.sum()

            # Calculate entropy (measure of information content)
            # Higher entropy = better color distribution
            entropy = -np.sum(
                hist_norm * np.log2(hist_norm + 1e-10)
            )  # Add small value to avoid log(0)

            # Check if entropy is too low (poor distribution)
            is_poor_distribution = entropy < self.entropy_min
            penalty = -15 if is_poor_distribution else 0

            return {
                "entropy": round(entropy, 2),
                "is_poor_distribution": is_poor_distribution,
                "threshold": self.entropy_min,
                "penalty": penalty,
                "reason": (
                    f"Entropy {entropy:.2f} < {self.entropy_min}"
                    if is_poor_distribution
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Histogram analysis failed: {e}")
            return {"error": str(e), "penalty": 0}

    def _detect_corruption_patterns(self, gray: np.ndarray) -> Dict[str, Any]:
        """
        Detect JPEG compression artifacts and corruption patterns.

        Args:
            gray: Grayscale image

        Returns:
            Dictionary with pattern detection results
        """
        try:
            height, width = gray.shape

            # Analyze 8x8 blocks for uniformity (common in JPEG corruption)
            uniform_blocks = 0
            total_blocks = 0

            for y in range(0, height - self.block_size, self.block_size):
                for x in range(0, width - self.block_size, self.block_size):
                    block = gray[y : y + self.block_size, x : x + self.block_size]

                    # Check if block is too uniform (potential corruption)
                    block_std = np.std(block)
                    if block_std < 5:  # Very low variation
                        uniform_blocks += 1

                    total_blocks += 1

            # Calculate block corruption ratio
            if total_blocks > 0:
                block_corruption_ratio = uniform_blocks / total_blocks
            else:
                block_corruption_ratio = 0

            # Check if too many blocks are uniform
            is_corrupted = block_corruption_ratio > self.block_corruption_max
            penalty = -40 if is_corrupted else 0

            return {
                "uniform_blocks": uniform_blocks,
                "total_blocks": total_blocks,
                "block_corruption_ratio": round(block_corruption_ratio, 4),
                "is_corrupted": is_corrupted,
                "threshold": self.block_corruption_max,
                "penalty": penalty,
                "reason": (
                    f"Block corruption {block_corruption_ratio:.3f} > {self.block_corruption_max}"
                    if is_corrupted
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            return {"error": str(e), "penalty": 0}

    def _calculate_heavy_score(self, results: Dict[str, Any]) -> int:
        """
        Calculate overall heavy detection score based on all analyses.

        Args:
            results: Combined results from all detection methods

        Returns:
            Score from 0-100 (100 = perfect quality)
        """
        starting_score = 100
        total_penalty = 0

        # Sum all penalties from each detection method
        for method_name, method_result in results.items():
            if isinstance(method_result, dict) and "penalty" in method_result:
                penalty = method_result["penalty"]
                if penalty < 0:  # Only count negative penalties
                    total_penalty += abs(penalty)

        # Calculate final score
        final_score = max(0, starting_score - total_penalty)

        return int(final_score)
