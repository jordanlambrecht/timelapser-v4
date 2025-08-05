"""
Corruption Pipeline Exception Classes

Custom exceptions for corruption detection and evaluation operations.
Provides specific error types for different failure modes in the corruption pipeline.
"""


class CorruptionPipelineError(Exception):
    """Base exception for corruption pipeline operations."""

    pass


class ScoreCalculationError(CorruptionPipelineError):
    """Exception raised when corruption score calculation fails."""

    pass


class CorruptionDetectionError(CorruptionPipelineError):
    """Exception raised when corruption detection process fails."""

    pass


class CorruptionEvaluationError(CorruptionPipelineError):
    """Exception raised when corruption evaluation fails."""

    pass


class CorruptionSettingsError(CorruptionPipelineError):
    """Exception raised when corruption settings are invalid or missing."""

    pass


class CameraHealthError(CorruptionPipelineError):
    """Exception raised when camera health assessment fails."""

    pass


class DegradedModeError(CorruptionPipelineError):
    """Exception raised when degraded mode operations fail."""

    pass


class CorruptionStatisticsError(CorruptionPipelineError):
    """Exception raised when corruption statistics collection fails."""

    pass


class FastDetectionError(CorruptionDetectionError):
    """Exception raised when fast corruption detection fails."""

    pass


class HeavyDetectionError(CorruptionDetectionError):
    """Exception raised when heavy corruption detection fails."""

    pass


class CorruptionThresholdError(CorruptionSettingsError):
    """Exception raised when corruption threshold validation fails."""

    pass


class CameraCorruptionConfigError(CorruptionSettingsError):
    """Exception raised when camera-specific corruption configuration is invalid."""

    pass


class RetryLogicError(CorruptionPipelineError):
    """Exception raised when retry logic evaluation fails."""

    pass


class QualityAnalysisError(CorruptionEvaluationError):
    """Exception raised when image quality analysis fails."""

    pass


class MetadataExtractionError(CorruptionPipelineError):
    """Exception raised when corruption metadata extraction fails."""

    pass


class CorruptionAuditError(CorruptionPipelineError):
    """Exception raised when corruption audit operations fail."""

    pass
