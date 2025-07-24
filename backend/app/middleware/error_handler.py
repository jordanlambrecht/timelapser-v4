# backend/app/middleware/error_handler.py
"""
Error handling middleware for FastAPI application.

Provides centralized error handling, logging, and user-friendly error responses
while maintaining security by not exposing internal details.
"""

import traceback
import uuid

from datetime import datetime, timezone
from ..utils.time_utils import get_timezone_aware_timestamp_from_settings, utc_now

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from loguru import logger
import psycopg
from pydantic import ValidationError

from ..config import settings


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Centralized error handling middleware.

    Catches all unhandled exceptions, logs them with correlation IDs,
    and returns user-friendly error responses.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.debug_mode = settings.environment == "development"

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and handle any errors that occur."""

        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        try:
            # Process the request
            response = await call_next(request)
            return response

        except Exception as exc:
            # Log the error with full context
            await self._log_error(exc, request, correlation_id)

            # Return appropriate error response
            return await self._create_error_response(exc, correlation_id)

    async def _log_error(
        self, exc: Exception, request: Request, correlation_id: str
    ) -> None:
        """Log error with full context and correlation ID."""

        try:
            # Gather request context
            request_info = {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": {
                    k: v
                    for k, v in request.headers.items()
                    if k.lower() not in ["authorization", "cookie"]  # Security
                },
                "client_ip": getattr(request.client, "host", "unknown"),
                "user_agent": request.headers.get("user-agent", "unknown"),
            }

            # Log with structured data
            logger.error(
                f"🚨 Unhandled exception in {request.method} {request.url.path}",
                extra={
                    "correlation_id": correlation_id,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "request_info": request_info,
                    "traceback": traceback.format_exc() if self.debug_mode else None,
                },
            )

        except Exception as log_error:
            # Fallback logging if structured logging fails
            logger.error(f"Error logging failed: {log_error}")
            logger.error(f"Original error: {exc}")

    async def _create_error_response(
        self, exc: Exception, correlation_id: str
    ) -> JSONResponse:
        """Create appropriate error response based on exception type."""

        # Handle specific exception types
        if isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, correlation_id)
        elif isinstance(exc, ValidationError):
            return await self._handle_validation_error(exc, correlation_id)
        elif isinstance(exc, psycopg.Error):
            return await self._handle_database_error(exc, correlation_id)
        else:
            return await self._handle_generic_error(exc, correlation_id)

    async def _handle_http_exception(
        self, exc: HTTPException, correlation_id: str
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""

        # Use centralized timezone utility for all timestamps (AI-CONTEXT compliance)
        try:
            timestamp = get_timezone_aware_timestamp_from_settings(
                settings.model_dump()
                if hasattr(settings, "model_dump")
                else dict(settings)
            )
        except Exception:
            timestamp = utc_now().isoformat()
        response_data = {
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
                "correlation_id": correlation_id,
                "timestamp": timestamp,
            }
        }

        return JSONResponse(status_code=exc.status_code, content=response_data)

    async def _handle_validation_error(
        self, exc: ValidationError, correlation_id: str
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""

        # Extract validation error details
        error_details = []
        for error in exc.errors():
            error_details.append(
                {
                    "field": " -> ".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        # Use centralized timezone utility for all timestamps (AI-CONTEXT compliance)
        try:
            timestamp = get_timezone_aware_timestamp_from_settings(
                settings.dict() if hasattr(settings, "dict") else dict(settings)
            )
        except Exception:
            timestamp = datetime.now(timezone.utc).isoformat()
        response_data = {
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "details": error_details,
                "correlation_id": correlation_id,
                "timestamp": timestamp,
            }
        }

        return JSONResponse(status_code=422, content=response_data)

    async def _handle_database_error(
        self, exc: psycopg.Error, correlation_id: str
    ) -> JSONResponse:
        """Handle database-related errors."""

        # Categorize database errors
        if isinstance(exc, psycopg.IntegrityError):
            message = "Data integrity constraint violation"
            status_code = 409
        elif isinstance(exc, psycopg.OperationalError):
            message = "Database connection or operation failed"
            status_code = 503
        else:
            message = "Database error occurred"
            status_code = 500

        # Use centralized timezone utility for all timestamps (AI-CONTEXT compliance)
        try:
            timestamp = get_timezone_aware_timestamp_from_settings(
                settings.dict() if hasattr(settings, "dict") else dict(settings)
            )
        except Exception:
            timestamp = datetime.now(timezone.utc).isoformat()
        response_data = {
            "error": {
                "type": "database_error",
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": timestamp,
            }
        }

        # Include SQL state code in debug mode (always as string, per standards)
        if self.debug_mode and hasattr(exc, "sqlstate"):
            sql_state = exc.sqlstate
            # Always cast to string for type safety and API consistency
            response_data["error"]["sql_state"] = (
                f"{sql_state}" if sql_state is not None else ""
            )

        return JSONResponse(status_code=status_code, content=response_data)

    async def _handle_generic_error(
        self, exc: Exception, correlation_id: str
    ) -> JSONResponse:
        """Handle all other unhandled exceptions."""
        # Use centralized timezone utility for all timestamps (AI-CONTEXT compliance)
        try:
            timestamp = get_timezone_aware_timestamp_from_settings(
                settings.dict() if hasattr(settings, "dict") else dict(settings)
            )
        except Exception:
            timestamp = datetime.now(timezone.utc).isoformat()
        response_data = {
            "error": {
                "type": "internal_error",
                "message": "An internal server error occurred",
                "correlation_id": correlation_id,
                "timestamp": timestamp,
            }
        }
        # Include exception details in debug mode
        if self.debug_mode:
            tb = traceback.format_exc()
            exception_type = type(exc).__name__
            response_data["error"]["exception_type"] = (
                str(exception_type) if exception_type is not None else ""
            )
            exception_message = str(exc) if exc is not None else ""
            response_data["error"]["exception_message"] = exception_message
            response_data["error"]["traceback"] = str(tb) if tb is not None else ""
        return JSONResponse(status_code=500, content=response_data)
