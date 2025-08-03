"""
Database Operation Exceptions - Clean Error Handling Pattern

This module defines custom exceptions for database operations to enable
clean separation between data layer and logging layer, preventing circular imports.

Architecture Pattern:
- Database operations raise specific exceptions (no logging)
- Service layer catches exceptions and handles logging
- Clean separation of concerns between data and business logic layers

Usage Examples:
    # In database operations file:
    from .exceptions import CameraOperationError

    try:
        # Database operation code...
        await cur.execute(query, params)
        return results
    except (psycopg.Error, KeyError, ValueError) as e:
        raise CameraOperationError(
            "Failed to retrieve camera data",
            operation="get_camera_by_id"
        ) from e

    # In service layer:
    try:
        camera = await self.camera_ops.get_camera_by_id(camera_id)
        logger.info(f"✅ Retrieved camera {camera_id}")
        return camera
    except CameraOperationError as e:
        logger.error(f"❌ Database error retrieving camera {camera_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error retrieving camera {camera_id}: {e}")
        raise

Implementation Pattern:
    1. Import the appropriate exception class
    2. Catch specific database errors (psycopg.Error, KeyError, ValueError)
    3. Raise the domain-specific exception with descriptive message and operation
    4. Use 'from e' to preserve the original error chain
    5. Let the service layer handle logging and business logic
"""

from typing import Any, Dict, Optional


class DatabaseOperationError(Exception):
    """
    Base exception for all database operation failures.

    Provides a clean interface for database errors without requiring
    logging dependencies in the database layer.
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}

    def __str__(self):
        if self.operation:
            return f"{self.operation}: {super().__str__()}"
        return super().__str__()


class SettingsOperationError(DatabaseOperationError):
    """Settings-specific database operation errors."""

    pass


class CameraOperationError(DatabaseOperationError):
    """Camera-specific database operation errors."""

    pass


class ImageOperationError(DatabaseOperationError):
    """Image-specific database operation errors."""

    pass


class VideoOperationError(DatabaseOperationError):
    """Video-specific database operation errors."""

    pass


class TimelapseOperationError(DatabaseOperationError):
    """Timelapse-specific database operation errors."""

    pass


class LogOperationError(DatabaseOperationError):
    """Log-specific database operation errors."""

    pass


class SSEOperationError(DatabaseOperationError):
    """SSE events-specific database operation errors."""

    pass


class HealthOperationError(DatabaseOperationError):
    """Health monitoring-specific database operation errors."""

    pass


class StatisticsOperationError(DatabaseOperationError):
    """Statistics-specific database operation errors."""

    pass


class OverlayOperationError(DatabaseOperationError):
    """Overlay-specific database operation errors."""

    pass


class CorruptionOperationError(DatabaseOperationError):
    """Corruption detection-specific database operation errors."""

    pass


class RecoveryOperationError(DatabaseOperationError):
    """Recovery-specific database operation errors."""

    pass


class WeatherOperationError(DatabaseOperationError):
    """Weather-specific database operation errors."""

    pass


class ScheduledJobOperationError(DatabaseOperationError):
    """Scheduled job-specific database operation errors."""

    pass


class ThumbnailOperationError(DatabaseOperationError):
    """Thumbnail-specific database operation errors."""

    pass


# Convenience mapping for operation types to exception classes
OPERATION_EXCEPTIONS = {
    "settings": SettingsOperationError,
    "camera": CameraOperationError,
    "image": ImageOperationError,
    "video": VideoOperationError,
    "timelapse": TimelapseOperationError,
    "log": LogOperationError,
    "sse": SSEOperationError,
    "health": HealthOperationError,
    "statistics": StatisticsOperationError,
    "overlay": OverlayOperationError,
    "corruption": CorruptionOperationError,
    "recovery": RecoveryOperationError,
    "weather": WeatherOperationError,
    "scheduled_job": ScheduledJobOperationError,
    "thumbnail": ThumbnailOperationError,
}


def get_operation_exception(operation_type: str) -> type[DatabaseOperationError]:
    """
    Get the appropriate exception class for a given operation type.

    Args:
        operation_type: The type of database operation

    Returns:
        The appropriate exception class

    Example:
        ExceptionClass = get_operation_exception('settings')
        raise ExceptionClass("Failed to update setting")
    """
    return OPERATION_EXCEPTIONS.get(operation_type, DatabaseOperationError)


def raise_operation_error(
    operation_type: str,
    message: str,
    operation: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    original_error: Optional[Exception] = None,
) -> None:
    """
    Convenience function to raise the appropriate operation exception.

    Args:
        operation_type: The type of database operation (e.g., 'camera', 'image')
        message: The error message
        operation: The specific operation that failed (optional)
        details: Additional error details (optional)
        original_error: The original exception to chain (optional)

    Example:
        raise_operation_error(
            'camera',
            'Failed to retrieve camera data',
            operation='get_camera_by_id',
            original_error=e
        )
    """
    exception_class = get_operation_exception(operation_type)
    exc = exception_class(message, operation=operation, details=details)

    if original_error:
        raise exc from original_error
    else:
        raise exc


# Standard error handling decorator for database operations
def handle_database_errors(operation_type: str, operation_name: str):
    """
    Decorator to standardize database error handling.

    Args:
        operation_type: The type of database operation (e.g., 'camera', 'image')
        operation_name: The name of the specific operation

    Example:
        @handle_database_errors('camera', 'get_camera_by_id')
        async def get_camera_by_id(self, camera_id: int):
            # Your database operation code here
            pass
    """

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except (DatabaseOperationError,):
                # Re-raise our own exceptions
                raise
            except Exception as e:
                raise_operation_error(
                    operation_type,
                    f"Database operation failed: {operation_name}",
                    operation=operation_name,
                    original_error=e,
                )

        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (DatabaseOperationError,):
                # Re-raise our own exceptions
                raise
            except Exception as e:
                raise_operation_error(
                    operation_type,
                    f"Database operation failed: {operation_name}",
                    operation=operation_name,
                    original_error=e,
                )

        # Return appropriate wrapper based on whether function is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
