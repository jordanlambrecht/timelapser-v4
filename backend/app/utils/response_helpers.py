# backend/app/utils/response_helpers.py
"""
Response Helper Functions

Standardized response formatting and SSE event broadcasting utilities.
Provides consistent response structures across all API endpoints.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from loguru import logger


class ResponseFormatter:
    """
    Helper class for creating standardized API responses.
    """

    @staticmethod
    def success(
        message: str, data: Optional[Union[Dict[str, Any], List]] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Create a standardized success response.

        Args:
            message: Success message
            data: Optional data payload
            **kwargs: Additional fields to include

        Returns:
            Standardized success response
        """
        response = {"success": True, "message": message}

        if data is not None:
            response["data"] = data

        # Add any additional fields
        response.update(kwargs)

        return response

    @staticmethod
    def error(
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a standardized error response.

        Args:
            message: Error message
            error_code: Optional error code for client handling
            details: Optional additional error details
            **kwargs: Additional fields to include

        Returns:
            Standardized error response
        """
        response = {"success": False, "message": message}

        if error_code:
            response["error_code"] = error_code

        if details:
            response["details"] = details

        # Add any additional fields
        response.update(kwargs)

        return response

    @staticmethod
    def paginated(
        data: List,
        total_count: int,
        page: int,
        per_page: int,
        message: str = "Data retrieved successfully",
    ) -> Dict[str, Any]:
        """
        Create a standardized paginated response.

        Args:
            data: List of items for current page
            total_count: Total number of items across all pages
            page: Current page number (1-based)
            per_page: Items per page
            message: Success message

        Returns:
            Standardized paginated response
        """
        total_pages = (total_count + per_page - 1) // per_page

        return {
            "success": True,
            "message": message,
            "data": data,
            "pagination": {
                "total_count": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
                "start_index": (page - 1) * per_page + 1 if total_count > 0 else 0,
                "end_index": min(page * per_page, total_count),
            },
        }

    @staticmethod
    def operation_result(
        operation: str,
        entity_type: str,
        entity_id: Union[int, str],
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a standardized operation result response.

        Args:
            operation: Operation performed (create, update, delete, etc.)
            entity_type: Type of entity (camera, timelapse, etc.)
            entity_id: ID of the entity
            success: Whether operation succeeded
            details: Optional additional details

        Returns:
            Standardized operation result response
        """
        if success:
            message = f"{entity_type.capitalize()} {operation}d successfully"
            response = ResponseFormatter.success(
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                operation=operation,
            )
        else:
            message = f"Failed to {operation} {entity_type}"
            response = ResponseFormatter.error(
                message=message,
                error_code=f"{operation}_failed",
                entity_type=entity_type,
                entity_id=entity_id,
                operation=operation,
            )

        if details:
            response["details"] = details

        return response


class SSEEventBuilder:
    """
    Helper class for building standardized Server-Sent Events.
    """

    @staticmethod
    def image_captured(
        camera_id: int,
        timelapse_id: int,
        image_count: int,
        day_number: int,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an image captured event.

        Args:
            camera_id: ID of the camera
            timelapse_id: ID of the timelapse
            image_count: Current image count
            day_number: Day number of the capture
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            SSE event data
        """
        return {
            "type": "image_captured",
            "data": {
                "camera_id": camera_id,
                "timelapse_id": timelapse_id,
                "image_count": image_count,
                "day_number": day_number,
            },
            "timestamp": timestamp or datetime.now().isoformat(),
        }

    @staticmethod
    def camera_status_changed(
        camera_id: int,
        status: str,
        health_status: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a camera status changed event.

        Args:
            camera_id: ID of the camera
            status: New camera status
            health_status: Optional health status
            timestamp: Optional timestamp

        Returns:
            SSE event data
        """
        event_data = {
            "type": "camera_status_changed",
            "data": {"camera_id": camera_id, "status": status},
            "timestamp": timestamp or datetime.now().isoformat(),
        }

        if health_status:
            event_data["data"]["health_status"] = health_status

        return event_data

    @staticmethod
    def timelapse_status_changed(
        camera_id: int, timelapse_id: int, status: str, timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a timelapse status changed event.

        Args:
            camera_id: ID of the camera
            timelapse_id: ID of the timelapse
            status: New timelapse status
            timestamp: Optional timestamp

        Returns:
            SSE event data
        """
        return {
            "type": "timelapse_status_changed",
            "data": {
                "camera_id": camera_id,
                "timelapse_id": timelapse_id,
                "status": status,
            },
            "timestamp": timestamp or datetime.now().isoformat(),
        }

    @staticmethod
    def video_generation_status(
        camera_id: int,
        video_id: int,
        status: str,
        progress: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a video generation status event.

        Args:
            camera_id: ID of the camera
            video_id: ID of the video
            status: Generation status
            progress: Optional progress percentage (0-100)
            timestamp: Optional timestamp

        Returns:
            SSE event data
        """
        event_data = {
            "type": "video_generation_status",
            "data": {"camera_id": camera_id, "video_id": video_id, "status": status},
            "timestamp": timestamp or datetime.now().isoformat(),
        }

        if progress is not None:
            event_data["data"]["progress"] = progress

        return event_data

    @staticmethod
    def corruption_detection_event(
        camera_id: int,
        image_id: Optional[int],
        corruption_score: int,
        action_taken: str,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a corruption detection event.

        Args:
            camera_id: ID of the camera
            image_id: ID of the image (if any)
            corruption_score: Corruption score (0-100)
            action_taken: Action taken (saved, discarded, retried)
            timestamp: Optional timestamp

        Returns:
            SSE event data
        """
        return {
            "type": "corruption_detection",
            "data": {
                "camera_id": camera_id,
                "image_id": image_id,
                "corruption_score": corruption_score,
                "action_taken": action_taken,
            },
            "timestamp": timestamp or datetime.now().isoformat(),
        }

    @staticmethod
    def system_health_update(
        metric_name: str,
        metric_value: Union[int, float, str],
        severity: str = "info",
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a system health update event.

        Args:
            metric_name: Name of the health metric
            metric_value: Value of the metric
            severity: Severity level (info, warning, error)
            timestamp: Optional timestamp

        Returns:
            SSE event data
        """
        return {
            "type": "system_health_update",
            "data": {
                "metric_name": metric_name,
                "metric_value": metric_value,
                "severity": severity,
            },
            "timestamp": timestamp or datetime.now().isoformat(),
        }

    @staticmethod
    def custom_event(
        event_type: str, data: Dict[str, Any], timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a custom event with arbitrary data.

        Args:
            event_type: Type of the event
            data: Event data payload
            timestamp: Optional timestamp

        Returns:
            SSE event data
        """
        return {
            "type": event_type,
            "data": data,
            "timestamp": timestamp or datetime.now().isoformat(),
        }


class ValidationHelper:
    """
    Helper class for common validation patterns in responses.
    """

    @staticmethod
    def validate_pagination_params(
        page: int, per_page: int, max_per_page: int = 100
    ) -> tuple[int, int]:
        """
        Validate pagination parameters and return limit/offset.

        Args:
            page: Page number (1-based)
            per_page: Items per page
            max_per_page: Maximum allowed items per page

        Returns:
            Tuple of (limit, offset)

        Raises:
            ValueError: If parameters are invalid
        """
        if page < 1:
            raise ValueError("Page must be >= 1")

        if per_page < 1 or per_page > max_per_page:
            raise ValueError(f"Items per page must be between 1 and {max_per_page}")

        limit = per_page
        offset = (page - 1) * per_page

        return limit, offset

    @staticmethod
    def validate_id_parameter(
        entity_id: Union[int, str], entity_name: str = "entity"
    ) -> int:
        """
        Validate and convert an ID parameter.

        Args:
            entity_id: ID value to validate
            entity_name: Name of entity for error messages

        Returns:
            Validated integer ID

        Raises:
            ValueError: If ID is invalid
        """
        try:
            int_id = int(entity_id)
            if int_id <= 0:
                raise ValueError(f"{entity_name.capitalize()} ID must be positive")
            return int_id
        except (ValueError, TypeError):
            raise ValueError(f"Invalid {entity_name} ID: must be a positive integer")

    @staticmethod
    def validate_enum_value(value: str, allowed_values: set, field_name: str) -> str:
        """
        Validate that a value is in the allowed set.

        Args:
            value: Value to validate
            allowed_values: Set of allowed values
            field_name: Name of field for error messages

        Returns:
            Validated value

        Raises:
            ValueError: If value is not allowed
        """
        if value not in allowed_values:
            raise ValueError(
                f"Invalid {field_name}: '{value}'. "
                f"Allowed values: {', '.join(sorted(allowed_values))}"
            )
        return value


class MetricsHelper:
    """
    Helper class for common metrics and statistics calculations.
    """

    @staticmethod
    def calculate_percentage(
        part: Union[int, float], total: Union[int, float]
    ) -> float:
        """
        Calculate percentage with division by zero protection.

        Args:
            part: Part value
            total: Total value

        Returns:
            Percentage (0.0 to 100.0)
        """
        if total == 0:
            return 0.0
        return min(100.0, max(0.0, (part / total) * 100.0))

    @staticmethod
    def calculate_average(values: List[Union[int, float]]) -> float:
        """
        Calculate average with empty list protection.

        Args:
            values: List of numeric values

        Returns:
            Average value or 0.0 if list is empty
        """
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def format_duration(seconds: Union[int, float]) -> str:
        """
        Format duration in human-readable format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    @staticmethod
    def calculate_health_score(
        total_items: int, healthy_items: int, degraded_items: int
    ) -> int:
        """
        Calculate a health score based on item states.

        Args:
            total_items: Total number of items
            healthy_items: Number of healthy items
            degraded_items: Number of degraded items

        Returns:
            Health score (0-100)
        """
        if total_items == 0:
            return 100

        health_ratio = healthy_items / total_items
        degraded_penalty = (degraded_items / total_items) * 50

        return max(0, int((health_ratio * 100) - degraded_penalty))


# NOTE: SSEEventManager class removed - replaced with database-driven SSE architecture
# Events are now handled through:
# 1. Services create events using SSEEventsOperations.create_event()
# 2. FastAPI streams events from database via /api/events endpoint
# 3. Next.js proxy streams events to frontend clients
#
# This eliminates the architectural violations:
# - Utils layer making HTTP requests (violates pure functions)
# - Synchronous HTTP in async context (performance bottleneck)
# - In-memory queue without persistence (data loss risk)


class LoggingHelper:
    """
    Helper class for consistent logging patterns.
    """

    @staticmethod
    def log_operation_start(
        operation: str, entity_type: str, entity_id: Union[int, str]
    ):
        """Log the start of an operation."""
        logger.info(f"Starting {operation} operation for {entity_type} {entity_id}")

    @staticmethod
    def log_operation_success(
        operation: str,
        entity_type: str,
        entity_id: Union[int, str],
        details: Optional[str] = None,
    ):
        """Log successful operation completion."""
        message = f"Successfully {operation}d {entity_type} {entity_id}"
        if details:
            message += f": {details}"
        logger.info(message)

    @staticmethod
    def log_operation_error(
        operation: str, entity_type: str, entity_id: Union[int, str], error: Exception
    ):
        """Log operation error."""
        logger.error(f"Failed to {operation} {entity_type} {entity_id}: {error}")

    @staticmethod
    def log_validation_error(field_name: str, value: Any, reason: str):
        """Log validation error."""
        logger.warning(f"Validation failed for {field_name}='{value}': {reason}")
