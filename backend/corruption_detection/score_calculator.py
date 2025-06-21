"""
Score Calculation Module for Corruption Detection

Handles the weighted scoring algorithm that combines results from
different detection methods into a single corruption score.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .fast_detector import FastDetectionResult


@dataclass
class CorruptionScore:
    """Final corruption score result"""

    final_score: int  # 0-100
    fast_score: int  # 0-100
    heavy_score: Optional[int]  # 0-100 (None if heavy detection disabled)
    is_corrupted: bool
    threshold_used: int
    details: Dict[str, Any]


class ScoreCalculator:
    """Calculates weighted corruption scores from detection results"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize score calculator with configuration"""
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(__name__)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for score calculation"""
        return {
            "fast_weight": 0.3,  # 30% weight for fast detection
            "heavy_weight": 0.7,  # 70% weight for heavy detection
            "default_threshold": 70,  # Default corruption threshold
        }

    def calculate_combined_score(
        self,
        fast_result: FastDetectionResult,
        heavy_result: Optional[Dict[str, Any]] = None,
        threshold: Optional[int] = None,
    ) -> CorruptionScore:
        """
        Calculate final corruption score from detection results

        Args:
            fast_result: Result from FastDetector
            heavy_result: Result from HeavyDetector (dictionary format, optional)
            threshold: Corruption threshold (0-100)

        Returns:
            CorruptionScore with final assessment
        """
        try:
            threshold_value = (
                threshold if threshold is not None else self.config["default_threshold"]
            )

            # For Phase 1, only fast detection is available
            if heavy_result is None or "heavy_score" not in heavy_result:
                final_score = fast_result.score
                heavy_score = None
                heavy_failed_checks = []
                heavy_processing_time = None
            else:
                # Phase 2: Weighted combination
                heavy_score = heavy_result["heavy_score"]

                # Take worst case for complete failures
                if fast_result.score == 0 or heavy_score == 0:
                    final_score = 0
                else:
                    # Weighted average
                    final_score = int(
                        (fast_result.score * self.config["fast_weight"])
                        + (heavy_score * self.config["heavy_weight"])
                    )

                # Extract heavy detection failed checks
                heavy_failed_checks = []
                heavy_processing_time = heavy_result.get("processing_time_ms", 0)

                # Collect failed checks from heavy detection
                for method_name, method_result in heavy_result.items():
                    if (
                        isinstance(method_result, dict)
                        and method_result.get("penalty", 0) < 0
                    ):
                        reason = method_result.get("reason", method_name)
                        heavy_failed_checks.append(reason)

            # Ensure score is within bounds
            final_score = max(0, min(100, final_score))

            # Determine if image is corrupted
            is_corrupted = final_score < threshold_value

            # Compile details
            details = {
                "fast_details": fast_result.details,
                "fast_failed_checks": fast_result.failed_checks,
                "fast_processing_time_ms": fast_result.processing_time_ms,
                "threshold": threshold_value,
                "calculation_method": (
                    "fast_only" if heavy_result is None else "weighted_average"
                ),
            }

            if heavy_result is not None and "heavy_score" in heavy_result:
                details.update(
                    {
                        "heavy_details": {
                            k: v for k, v in heavy_result.items() if k != "heavy_score"
                        },
                        "heavy_failed_checks": heavy_failed_checks,
                        "heavy_processing_time_ms": heavy_processing_time,
                        "weights": {
                            "fast": self.config["fast_weight"],
                            "heavy": self.config["heavy_weight"],
                        },
                    }
                )

            return CorruptionScore(
                final_score=final_score,
                fast_score=fast_result.score,
                heavy_score=heavy_score,
                is_corrupted=is_corrupted,
                threshold_used=threshold_value,
                details=details,
            )

        except Exception as e:
            self.logger.error(f"Score calculation failed: {e}")

            # Return safe defaults on calculation failure
            return CorruptionScore(
                final_score=100,  # Assume good if calculation fails
                fast_score=100,
                heavy_score=None,
                is_corrupted=False,
                threshold_used=(
                    threshold
                    if threshold is not None
                    else self.config["default_threshold"]
                ),
                details={"error": str(e), "calculation_failed": True},
            )

    def get_quality_label(self, score: int) -> str:
        """Get human-readable quality label for score"""
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "fair"
        elif score >= 30:
            return "poor"
        else:
            return "critical"

    def get_score_color_class(self, score: int) -> str:
        """Get CSS color class for score display"""
        if score >= 90:
            return "score-excellent"  # Green
        elif score >= 70:
            return "score-good"  # Blue
        elif score >= 50:
            return "score-fair"  # Yellow
        elif score >= 30:
            return "score-poor"  # Orange
        else:
            return "score-critical"  # Red
