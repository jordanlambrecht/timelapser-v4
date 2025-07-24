# backend/app/services/corruption_pipeline/detectors/score_calculator.py
"""
Corruption Score Calculator

Calculates final corruption scores by combining fast and heavy detection results.
Implements weighted scoring and decision thresholds for determining
whether an image should be considered corrupted.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class ScoreCalculationResult:
    """Result from score calculation with detailed breakdown"""

    final_score: float
    is_corrupted: bool
    should_auto_discard: bool
    calculation_details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            "final_score": self.final_score,
            "is_corrupted": self.is_corrupted,
            "should_auto_discard": self.should_auto_discard,
            "calculation_details": self.calculation_details,
        }


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
            "health_degraded_penalty": 10.0,  # Additional penalty when in degraded mode
            "consecutive_failures_penalty": 5.0,  # Penalty per consecutive failure
        }

    def calculate_final_score(
        self,
        fast_score: float,
        heavy_score: Optional[float] = None,
        health_degraded: bool = False,
        consecutive_failures: int = 0,
    ) -> ScoreCalculationResult:
        """
        Calculate final corruption score from detection results.

        Args:
            fast_score: Score from fast detection (0-100)
            heavy_score: Optional score from heavy detection (0-100)
            health_degraded: Whether corruption detection is in degraded mode
            consecutive_failures: Number of consecutive detection failures

        Returns:
            ScoreCalculationResult with final score and decisions
        """
        try:
            calculation_details = {
                "fast_score": fast_score,
                "heavy_score": heavy_score,
                "fast_weight": self.config["fast_weight"],
                "heavy_weight": self.config["heavy_weight"],
                "health_degraded": health_degraded,
                "consecutive_failures": consecutive_failures,
            }

            if heavy_score is None:
                # Only fast detection available
                base_score = min(fast_score, self.config["max_score"])
                calculation_details["method"] = "fast_only"
            else:
                # Weighted combination of fast and heavy scores
                base_score = (
                    fast_score * self.config["fast_weight"]
                    + heavy_score * self.config["heavy_weight"]
                )
                calculation_details["method"] = "weighted_combination"
                calculation_details["base_score"] = base_score

            # Apply penalties
            final_score = base_score

            # Health degraded penalty
            if health_degraded:
                penalty = self.config["health_degraded_penalty"]
                final_score += penalty
                calculation_details["health_penalty"] = penalty

            # Consecutive failures penalty
            if consecutive_failures > 0:
                penalty = min(
                    consecutive_failures * self.config["consecutive_failures_penalty"],
                    20.0,  # Cap at 20 points
                )
                final_score += penalty
                calculation_details["consecutive_failures_penalty"] = penalty

            # Ensure score is within bounds
            final_score = min(max(final_score, 0.0), self.config["max_score"])
            calculation_details["final_score"] = final_score

            # Make decisions
            is_corrupted = self.is_corrupted(final_score)
            should_auto_discard = self.should_auto_discard(final_score)

            calculation_details.update(
                {
                    "corruption_threshold": self.config["corruption_threshold"],
                    "auto_discard_threshold": self.config["auto_discard_threshold"],
                    "is_corrupted": is_corrupted,
                    "should_auto_discard": should_auto_discard,
                }
            )

            return ScoreCalculationResult(
                final_score=final_score,
                is_corrupted=is_corrupted,
                should_auto_discard=should_auto_discard,
                calculation_details=calculation_details,
            )

        except Exception as e:
            logger.error(f"Error calculating corruption score: {e}")
            # Return safe defaults on error
            return ScoreCalculationResult(
                final_score=100.0,  # Assume corrupted on error
                is_corrupted=True,
                should_auto_discard=True,
                calculation_details={"error": str(e)},
            )

    def calculate_simple_score(
        self, fast_score: float, heavy_score: Optional[float] = None
    ) -> float:
        """
        Calculate simple final score (legacy compatibility).

        Args:
            fast_score: Score from fast detection (0-100)
            heavy_score: Optional score from heavy detection (0-100)

        Returns:
            Final corruption score (0-100)
        """
        result = self.calculate_final_score(fast_score, heavy_score)
        return result.final_score

    def is_corrupted(self, score: float) -> bool:
        """Determine if image is corrupted based on score"""
        return score >= self.config["corruption_threshold"]

    def should_auto_discard(self, score: float) -> bool:
        """Determine if image should be automatically discarded"""
        return score >= self.config["auto_discard_threshold"]

    def get_thresholds(self) -> Dict[str, float]:
        """Get current threshold configuration"""
        return {
            "corruption_threshold": self.config["corruption_threshold"],
            "auto_discard_threshold": self.config["auto_discard_threshold"],
        }

    def get_calculation_details(self) -> Dict[str, Any]:
        """Get details about score calculation configuration"""
        return {
            "fast_weight": self.config["fast_weight"],
            "heavy_weight": self.config["heavy_weight"],
            "corruption_threshold": self.config["corruption_threshold"],
            "auto_discard_threshold": self.config["auto_discard_threshold"],
            "health_degraded_penalty": self.config["health_degraded_penalty"],
            "consecutive_failures_penalty": self.config["consecutive_failures_penalty"],
        }

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values"""
        self.config.update(new_config)
        logger.info(f"Updated corruption score calculator config: {new_config}")

    def assess_quality_level(self, score: float) -> str:
        """
        Assess image quality level based on corruption score.

        Args:
            score: Corruption score (0-100)

        Returns:
            Quality level string
        """
        if score >= self.config["auto_discard_threshold"]:
            return "severely_corrupted"
        elif score >= self.config["corruption_threshold"]:
            return "corrupted"
        elif score >= 25.0:
            return "questionable"
        elif score >= 10.0:
            return "good"
        else:
            return "excellent"

    def get_score_breakdown(
        self, fast_result: Dict[str, Any], heavy_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of how score was calculated.

        Args:
            fast_result: Fast detection result dictionary
            heavy_result: Optional heavy detection result dictionary

        Returns:
            Detailed breakdown dictionary
        """
        breakdown: Dict[str, Any] = {
            "fast_detection": {
                "score": fast_result.get("corruption_score", 0.0),
                "failed_checks": fast_result.get("failed_checks", []),
                "processing_time_ms": fast_result.get("detection_time_ms", 0.0),
                "weight": self.config["fast_weight"],
            }
        }

        if heavy_result:
            breakdown["heavy_detection"] = {
                "score": heavy_result.get("corruption_score", 0.0),
                "failed_checks": heavy_result.get("failed_checks", []),
                "processing_time_ms": heavy_result.get("detection_time_ms", 0.0),
                "weight": self.config["heavy_weight"],
            }

        # Calculate final score
        final_score = self.calculate_simple_score(
            fast_result.get("corruption_score", 0.0),
            heavy_result.get("corruption_score") if heavy_result else None,
        )

        # Add final calculation results
        breakdown["final_score"] = final_score
        breakdown["quality_level"] = self.assess_quality_level(final_score)
        breakdown["decisions"] = {
            "is_corrupted": self.is_corrupted(final_score),
            "should_auto_discard": self.should_auto_discard(final_score),
        }
        breakdown["thresholds"] = self.get_thresholds()

        return breakdown
