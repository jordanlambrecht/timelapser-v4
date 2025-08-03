# backend/app/utils/router_helpers.py
"""
Router Helper Functions

Common functions and decorators for FastAPI routers to reduce code duplication.
Provides standardized error handling, entity validation, and response patterns.
"""


from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from fastapi import HTTPException

from ..enums import LoggerName
from ..services.logger import get_service_logger

T = TypeVar("T")
logger = get_service_logger(LoggerName.SYSTEM)


def handle_exceptions(operation_name: str):
    """
    Decorator for standardized exception handling in router endpoints.

    Provides consistent error logging and HTTP response patterns across all routers.

    Args:
        operation_name: Human-readable description of the operation for error messages

    Usage:
        @handle_exceptions("fetch cameras")
        async def get_cameras():
            # endpoint logic here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except Exception as e:
                logger.error(f"Error {operation_name}: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to {operation_name}"
                )

        return wrapper

    return decorator


async def validate_entity_exists(
    db_method: Callable[..., Awaitable[Optional[T]]],
    entity_id: int,
    entity_name: str = "entity",
) -> T:
    """
    Validate that an entity exists in the database with proper typing.

    Args:
        db_method: Database method to call (e.g., video_service.get_video_by_id)
        entity_id: ID of the entity to validate
        entity_name: Human-readable name for error messages

    Returns:
        The entity (properly typed as returned by db_method)

    Raises:
        HTTPException: 404 if entity not found

    Usage:
        video = await validate_entity_exists(
            video_service.get_video_by_id,
            video_id,
            "video"
        )
    """
    entity = await db_method(entity_id)
    if not entity:
        raise HTTPException(
            status_code=404, detail=f"{entity_name.capitalize()} not found"
        )
    return entity


def validate_entity_exists_sync(
    db_method: Callable, entity_id: int, entity_name: str = "entity"
) -> Dict[str, Any]:
    """
    Synchronous version of validate_entity_exists for sync database operations.

    Args:
        db_method: Sync database method to call
        entity_id: ID of the entity to validate
        entity_name: Human-readable name for error messages

    Returns:
        Dict containing the entity data

    Raises:
        HTTPException: 404 if entity not found
    """
    entity = db_method(entity_id)
    if not entity:
        raise HTTPException(
            status_code=404, detail=f"{entity_name.capitalize()} not found"
        )
    return entity


async def validate_camera_online(camera: Dict[str, Any]) -> None:
    """
    Validate that a camera is online and can capture images.

    Args:
        camera: Camera dictionary from database

    Raises:
        HTTPException: 400 if camera is not online
    """
    health_status = camera.get("health_status")
    if health_status != "online":
        raise HTTPException(
            status_code=400,
            detail=f"Camera is {health_status or 'unknown'} and cannot capture images",
        )


async def validate_timelapse_running(timelapse: Dict[str, Any]) -> None:
    """
    Validate that a timelapse is in running state.

    Args:
        timelapse: Timelapse dictionary from database

    Raises:
        HTTPException: 400 if timelapse is not running
    """
    status = timelapse.get("status")
    if status != "running":
        raise HTTPException(
            status_code=400, detail=f"Timelapse is {status} and cannot capture images"
        )


def create_success_response(
    message: str, data: Optional[Dict[str, Any]] = None, **kwargs
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        message: Success message
        data: Optional data payload
        **kwargs: Additional fields to include in response

    Returns:
        Standardized success response dictionary
    """
    response = {"success": True, "message": message}

    if data:
        response["data"] = data

    response.update(kwargs)
    return response


def create_error_response(
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        message: Error message
        error_code: Optional error code for client handling
        details: Optional additional error details

    Returns:
        Standardized error response dictionary
    """
    response = {"success": False, "message": message}

    if error_code:
        response["error_code"] = error_code

    if details:
        response["details"] = details

    return response


async def get_active_timelapse_for_camera(timelapse_service, camera_id: int):
    """
    Get the active timelapse for a camera, validating it exists and is running.

    Args:
        timelapse_service: TimelapseService instance
        camera_id: Camera ID

    Returns:
        Active timelapse Pydantic model

    Raises:
        HTTPException: 400 if no active timelapse found
    """
    timelapses = await timelapse_service.get_timelapses(camera_id=camera_id)
    active_timelapse = next((t for t in timelapses if t.status == "running"), None)

    if not active_timelapse:
        raise HTTPException(
            status_code=400,
            detail="No active timelapse found for this camera. Start a timelapse first.",
        )

    return active_timelapse


def build_dynamic_update_query(
    table_name: str,
    updates: Dict[str, Any],
    allowed_fields: set,
    where_field: str = "id",
) -> tuple[str, Dict[str, Any]]:
    """
    Build a dynamic UPDATE query with only allowed fields.

    Args:
        table_name: Name of the table to update
        updates: Dictionary of field updates
        allowed_fields: Set of allowed field names
        where_field: Field to use in WHERE clause

    Returns:
        Tuple of (query_string, values_dict)

    Usage:
        query, values = build_dynamic_update_query(
            "cameras",
            {"name": "New Name", "status": "active"},
            {"name", "status", "rtsp_url"},
            "id"
        )
        values["id"] = camera_id
        cur.execute(query, values)
    """
    # Filter only allowed fields
    filtered_updates = {
        field: value for field, value in updates.items() if field in allowed_fields
    }

    if not filtered_updates:
        return "", {}

    # Build SET clauses
    set_clauses = [f"{field} = %({field})s" for field in filtered_updates.keys()]
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {where_field} = %({where_field})s"

    values = filtered_updates.copy()

    return query, values


def validate_request_data(data: Dict[str, Any], required_fields: set) -> None:
    """
    Validate that required fields are present in request data.

    Args:
        data: Request data dictionary
        required_fields: Set of required field names

    Raises:
        HTTPException: 400 if required fields are missing
    """
    missing_fields = required_fields - set(data.keys())
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing_fields)}",
        )


def paginate_query_params(
    page: int = 1, per_page: int = 50, max_per_page: int = 100
) -> tuple[int, int]:
    """
    Validate and calculate pagination parameters.

    Args:
        page: Page number (1-based)
        per_page: Items per page
        max_per_page: Maximum allowed items per page

    Returns:
        Tuple of (limit, offset)

    Raises:
        HTTPException: 400 if parameters are invalid
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")

    if per_page < 1 or per_page > max_per_page:
        raise HTTPException(
            status_code=400,
            detail=f"Items per page must be between 1 and {max_per_page}",
        )

    limit = per_page
    offset = (page - 1) * per_page

    return limit, offset


class DatabaseOperationMixin:
    """
    Mixin class for common database operation patterns.

    Can be used with both async and sync database classes to reduce duplication.
    """

    @staticmethod
    def build_insert_query(
        table_name: str,
        data: Dict[str, Any],
        allowed_fields: set,
        returning_field: str = "id",
    ) -> tuple[str, Dict[str, Any]]:
        """Build a dynamic INSERT query with only allowed fields."""
        filtered_data = {
            field: value for field, value in data.items() if field in allowed_fields
        }

        if not filtered_data:
            raise ValueError("No valid fields provided for insert")

        fields = list(filtered_data.keys())
        placeholders = [f"%({field})s" for field in fields]

        query = f"""
            INSERT INTO {table_name} ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            RETURNING {returning_field}
        """

        return query, filtered_data

    @staticmethod
    def format_where_conditions(
        conditions: Dict[str, Any], allowed_fields: set
    ) -> tuple[str, Dict[str, Any]]:
        """Build WHERE clause conditions dynamically."""
        filtered_conditions = {
            field: value
            for field, value in conditions.items()
            if field in allowed_fields and value is not None
        }

        if not filtered_conditions:
            return "", {}

        where_clauses = [
            f"{field} = %({field})s" for field in filtered_conditions.keys()
        ]
        where_clause = " AND ".join(where_clauses)

        return where_clause, filtered_conditions


async def run_sync_service_method(func, *args, **kwargs):
    """
    Helper to run sync service methods in async context with proper error handling.

    This utility bridges the gap between async router endpoints and sync service methods,
    executing sync functions in a thread pool to avoid blocking the event loop.

    Args:
        func: Sync function to call
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Raises:
        Exception: Re-raises any exceptions from the wrapped function
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    except Exception:
        # Let the @handle_exceptions decorator handle logging
        # Router layer should not do direct logging
        raise
