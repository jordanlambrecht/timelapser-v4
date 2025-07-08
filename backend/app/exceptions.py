# backend/app/exceptions.py
"""
Custom exceptions for Timelapser v4.

Centralized location for all custom exception classes to avoid
duplicating exception definitions across modules.
"""

# TODO: Gotta get rid of this eventually because it's too comparmentalized imho


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


class ConfigurationError(TimelapserError):
    """Custom exception for configuration errors."""

    pass


class ValidationError(TimelapserError):
    """Custom exception for data validation errors."""

    pass
