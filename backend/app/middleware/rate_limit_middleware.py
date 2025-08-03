#!/usr/bin/env python3
# backend/app/middleware/rate_limit_middleware.py

"""
Rate Limiting Middleware for FastAPI application.

Integrates with the rate limiter to apply limits automatically
to API endpoints based on path patterns.
"""

import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..enums import LoggerName
from ..services.logger import get_service_logger


from .rate_limiter import apply_rate_limit, cleanup_rate_limiter

logger = get_service_logger(LoggerName.MIDDLEWARE)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for applying rate limits to API endpoints.

    Automatically applies rate limits based on endpoint patterns
    and manages cleanup of old rate limiting data.
    """

    def __init__(self, app):
        super().__init__(app)
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting.

        Args:
            request: FastAPI request object
            call_next: Next middleware in chain

        Returns:
            Response object
        """
        # Skip rate limiting for non-API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Skip rate limiting for health check endpoints
        if "/health" in request.url.path:
            return await call_next(request)

        # Periodic cleanup of old rate limiting data
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            try:
                cleaned_count = await cleanup_rate_limiter()
                if cleaned_count > 0:
                    logger.debug(
                        f"🧹 Rate limiter cleanup: {cleaned_count} entries removed"
                    )
                self.last_cleanup = current_time
            except Exception as e:
                logger.error(f"Rate limiter cleanup failed: {e}")

        try:
            # Create response object to add headers
            response = Response()

            # Apply rate limiting
            await apply_rate_limit(request, response)

            # Rate limit passed, process request
            actual_response = await call_next(request)

            # Copy rate limit headers to actual response
            for header_name, header_value in response.headers.items():
                if header_name.startswith("X-RateLimit"):
                    actual_response.headers[header_name] = header_value

            return actual_response

        except Exception as e:
            # Handle rate limit exceptions
            if hasattr(e, "status_code") and getattr(e, "status_code") == 429:
                # Rate limit exceeded - return 429 with details
                return JSONResponse(
                    status_code=429,
                    content=getattr(e, "detail", {"error": "Rate limit exceeded"}),
                    headers=getattr(e, "headers", {}),
                )
            else:
                # Other errors - re-raise
                raise e
