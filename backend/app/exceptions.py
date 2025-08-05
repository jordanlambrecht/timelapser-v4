# backend/app/exceptions.py
"""
Custom exceptions for Timelapser v4.

Centralized location for all custom exception classes to avoid
duplicating exception definitions across modules.
"""

# Exception design follows semantic clarity - each exception type represents
# a distinct error domain with specific handling requirements


class TimelapserError(Exception):
    """Base exception for all Timelapser-specific errors."""

    pass


class RTSPConnectionError(TimelapserError):
    """Custom exception for RTSP connection failures."""

    pass


class RTSPCaptureError(TimelapserError):
    """Custom exception for RTSP capture failures."""

    pass


class CorruptionDetectionError(TimelapserError):
    """Custom exception for corruption detection failures."""

    pass


class VideoGenerationError(TimelapserError):
    """Custom exception for video generation failures."""

    pass


class DatabaseOperationError(TimelapserError):
    """Custom exception for database operation failures."""

    pass


class FileOperationError(TimelapserError):
    """Custom exception for file system operation failures."""

    pass


class ImageNotFoundError(TimelapserError):
    """Custom exception for when an image is not found."""

    pass


class InvalidImageSizeError(TimelapserError):
    """Custom exception for invalid image size variants."""

    pass


class ServiceError(TimelapserError):
    """Custom exception for general service operation errors."""

    pass


class ConfigurationError(TimelapserError):
    """Custom exception for configuration and validation errors."""

    pass


class CameraNotFoundError(TimelapserError):
    """Custom exception for camera not found errors."""

    pass


class WorkflowError(TimelapserError):
    """Custom exception for workflow orchestration errors."""

    pass


class JobCoordinationError(TimelapserError):
    """Custom exception for job coordination failures."""

    pass


class CaptureValidationError(TimelapserError):
    """Custom exception for capture validation failures."""

    pass


class OverlayGenerationError(TimelapserError):
    """Custom exception for overlay generation failures."""

    pass


class CaptureContextError(TimelapserError):
    """Custom exception for capture context validation failures."""

    pass
