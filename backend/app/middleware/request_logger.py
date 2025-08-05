# backend/app/middleware/request_logger.py
"""
Request logging middleware for FastAPI application.

Provides structured request/response logging with performance metrics,
correlation IDs, and security-conscious data handling.
"""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..config import settings
from ..enums import LogEmoji, LoggerName
from ..services.logger import get_service_logger

logger = get_service_logger(LoggerName.MIDDLEWARE)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    Request logging middleware with performance metrics.

    Logs all requests with timing, status codes, and security-conscious
    data filtering. Provides correlation ID tracking for debugging.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.debug_mode = settings.environment == "development"

        # Paths to exclude from logging (health checks, static files)
        self.exclude_paths = {
            "/api/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
        }

        # Headers to exclude from logs for security
        self.excluded_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and log details with timing."""

        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Get correlation ID (set by error handler middleware)
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        # Log request start
        await self._log_request_start(request, correlation_id)

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log successful response
            await self._log_request_complete(
                request, response, duration, correlation_id
            )

            return response

        except Exception as exc:
            # Calculate duration for failed requests
            duration = time.time() - start_time

            # Log failed request
            await self._log_request_failed(request, exc, duration, correlation_id)

            # Re-raise exception for error handler
            raise

    async def _log_request_start(self, request: Request, correlation_id: str) -> None:
        """Log request start with sanitized details."""

        try:
            # Build request info with security filtering
            request_info = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": getattr(request.client, "host", "unknown"),
                "user_agent": request.headers.get("user-agent", "unknown"),
                "content_length": request.headers.get("content-length"),
                "content_type": request.headers.get("content-type"),
            }

            # Include filtered headers in debug mode
            if self.debug_mode:
                request_info["headers"] = {
                    k: v
                    for k, v in request.headers.items()
                    if k.lower() not in self.excluded_headers
                }

            logger.info(
                f"{request.method} {request.url.path}",
                extra_context={
                    "correlation_id": correlation_id,
                    "event_type": "request_start",
                    "request_info": request_info,
                },
                emoji=LogEmoji.REQUEST,
            )

        except Exception as e:
            logger.warning(f"Failed to log request start: {e}")

    async def _log_request_complete(
        self, request: Request, response: Response, duration: float, correlation_id: str
    ) -> None:
        """Log successful request completion with metrics."""

        try:
            # Determine log level based on response status and duration
            status_code = response.status_code

            if status_code >= 500:
                log_level = "error"
                emoji = "💥"
            elif status_code >= 400:
                log_level = "warning"
                emoji = "⚠️"
            elif duration > 5.0:  # Slow requests
                log_level = "warning"
                emoji = "🐌"
            else:
                log_level = "info"
                emoji = "✅"

            # Build response info
            response_info = {
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "content_length": response.headers.get("content-length"),
                "content_type": response.headers.get("content-type"),
            }

            # Log with appropriate level
            log_message = f"{emoji} {request.method} {request.url.path} -> {status_code} ({response_info['duration_ms']}ms)"

            getattr(logger, log_level)(
                log_message,
                extra_context={
                    "correlation_id": correlation_id,
                    "event_type": "request_complete",
                    "response_info": response_info,
                },
            )

        except Exception as e:
            logger.warning(f"Failed to log request completion: {e}")

    async def _log_request_failed(
        self,
        request: Request,
        exception: Exception,
        duration: float,
        correlation_id: str,
    ) -> None:
        """Log failed request with exception details."""

        try:
            failure_info = {
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "duration_ms": round(duration * 1000, 2),
            }

            logger.error(
                f"{request.method} {request.url.path} -> FAILED ({failure_info['duration_ms']}ms)",
                extra_context={
                    "correlation_id": correlation_id,
                    "event_type": "request_failed",
                    "failure_info": failure_info,
                },
            )

        except Exception as e:
            logger.warning(f"Failed to log request failure: {e}")
