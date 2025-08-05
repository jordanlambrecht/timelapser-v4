"""
Worker-specific exceptions for better error handling.

These exceptions replace generic Exception catching with specific,
actionable error types that indicate the exact failure mode.
"""


class WorkerInitializationError(Exception):
    """Raised when a worker fails to initialize required services."""

    pass


class ServiceUnavailableError(Exception):
    """Raised when a required service is not available."""

    pass


class VideoGenerationError(Exception):
    """Raised when video generation fails."""

    pass


class JobProcessingError(Exception):
    """Raised when job processing fails."""

    pass


class RecoveryOperationError(Exception):
    """Raised when recovery operations fail."""

    pass


class HealthCheckError(Exception):
    """Raised when health check operations fail."""

    pass


class CleanupOperationError(Exception):
    """Raised when cleanup operations fail."""

    pass


class WeatherDataError(Exception):
    """Raised when weather data operations fail."""

    pass


class WeatherApiError(Exception):
    """Raised when weather API operations fail."""

    pass


class WeatherConfigurationError(Exception):
    """Raised when weather configuration is invalid."""

    pass


class RetentionConfigurationError(Exception):
    """Raised when retention configuration is invalid."""

    pass


class CleanupServiceError(Exception):
    """Raised when cleanup service operations fail."""

    pass


class CaptureWorkflowError(Exception):
    """Raised when capture workflow operations fail."""

    pass


class CameraConnectionError(Exception):
    """Raised when camera connection operations fail."""

    pass


class TimelapseValidationError(Exception):
    """Raised when timelapse validation fails."""

    pass
