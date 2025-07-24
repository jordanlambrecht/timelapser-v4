"""
Corruption Detection Algorithms

Contains the core image quality detection algorithms:
- FastCorruptionDetector: Lightweight heuristic checks (1-5ms)
- HeavyCorruptionDetector: Computer vision analysis (20-100ms)
- CorruptionScoreCalculator: Scoring and penalty system

All detection algorithms consolidated from legacy utils/corruption_detection_utils.py
with improved error handling, standardized interfaces, and enhanced scoring.
"""

from .fast_detector import FastCorruptionDetector, FastDetectionResult
from .heavy_detector import HeavyCorruptionDetector, HeavyDetectionResult
from .score_calculator import CorruptionScoreCalculator, ScoreCalculationResult

__all__ = [
    "FastCorruptionDetector",
    "FastDetectionResult",
    "HeavyCorruptionDetector",
    "HeavyDetectionResult",
    "CorruptionScoreCalculator",
    "ScoreCalculationResult",
]
