"""
Corruption Detection Models

Shared data classes and types for the corruption detection system.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

# Import CorruptionScore from score_calculator to avoid another circular import
from .score_calculator import CorruptionScore


@dataclass
class CorruptionResult:
    """Complete corruption evaluation result"""

    is_valid: bool
    score: int
    action_taken: str  # 'saved', 'discarded', 'retried'
    corruption_score: CorruptionScore
    retry_attempted: bool
    retry_result: Optional["CorruptionResult"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        result = {
            "is_valid": self.is_valid,
            "score": self.score,
            "action_taken": self.action_taken,
            "retry_attempted": self.retry_attempted,
            "corruption_details": self.corruption_score.details,
            "fast_score": self.corruption_score.fast_score,
            "heavy_score": self.corruption_score.heavy_score,
            "threshold_used": self.corruption_score.threshold_used,
        }

        if self.retry_result:
            result["retry_details"] = self.retry_result.to_dict()

        return result
