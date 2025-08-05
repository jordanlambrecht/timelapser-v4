#!/usr/bin/env python3
# backend/app/middleware/rate_limiter.py

"""
Rate Limiting Middleware - Prevent API flooding and abuse.

Implements sliding window rate limiting for API endpoints to prevent
excessive requests and protect backend resources.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response, status

from ..enums import LoggerName
from ..services.logger import get_service_logger

logger = get_service_logger(LoggerName.MIDDLEWARE)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter implementation.

    Tracks requests per client within a time window and enforces limits.
    """

    def __init__(self) -> None:
        # Dict[client_id, deque[timestamp]]
        self._requests: Dict[str, deque] = defaultdict(lambda: deque())
        self._lock = asyncio.Lock()

    async def is_allowed(
        self, client_id: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed within rate limits.

        Args:
            client_id: Unique identifier for client (IP, user ID, etc.)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        current_time = time.time()
        window_start = current_time - window_seconds

        async with self._lock:
            # Get request history for this client
            request_times = self._requests[client_id]

            # Remove requests outside the current window
            while request_times and request_times[0] < window_start:
                request_times.popleft()

            # Check if we're within limits
            current_requests = len(request_times)
            is_allowed = current_requests < max_requests

            if is_allowed:
                # Add current request timestamp
                request_times.append(current_time)

            # Calculate rate limit headers
            remaining = max(
                0, max_requests - current_requests - (1 if is_allowed else 0)
            )
            reset_time = int(current_time + window_seconds)

            rate_limit_info = {
                "limit": max_requests,
                "remaining": remaining,
                "reset": reset_time,
                "window_seconds": window_seconds,
                "current_requests": current_requests,
            }

            if not is_allowed:
                logger.warning(
                    f"🚫 Rate limit exceeded for {client_id}: "
                    f"{current_requests}/{max_requests} requests in {window_seconds}s window"
                )

            return is_allowed, rate_limit_info

    async def cleanup_old_entries(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up old request tracking data.

        Args:
            max_age_seconds: Remove data older than this

        Returns:
            Number of client entries cleaned up
        """
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds
        cleaned_count = 0

        async with self._lock:
            clients_to_remove = []

            for client_id, request_times in self._requests.items():
                # Remove old requests for this client
                while request_times and request_times[0] < cutoff_time:
                    request_times.popleft()

                # If no requests remain, mark client for removal
                if not request_times:
                    clients_to_remove.append(client_id)

            # Remove clients with no recent requests
            for client_id in clients_to_remove:
                del self._requests[client_id]
                cleaned_count += 1

            if cleaned_count > 0:
                logger.debug(
                    f"🧹 Rate limiter cleaned up {cleaned_count} old client entries"
                )

        return cleaned_count


# Global rate limiter instance
rate_limiter = SlidingWindowRateLimiter()


class RateLimitConfig:
    """Configuration for different endpoint rate limits."""

    # Default rate limits (requests per time window)
    DEFAULT_LIMITS = {
        # Latest image endpoints - very restrictive to prevent flooding
        "latest_image": {"max_requests": 2, "window_seconds": 30},
        "latest_image_serve": {"max_requests": 5, "window_seconds": 30},
        # General API endpoints
        "api_general": {"max_requests": 30, "window_seconds": 60},
        # Image serving endpoints
        "image_serve": {"max_requests": 20, "window_seconds": 60},
        # Statistics and metadata
        "statistics": {"max_requests": 10, "window_seconds": 60},
        # Administrative operations
        "admin": {"max_requests": 5, "window_seconds": 60},
    }

    @classmethod
    def get_limit_for_endpoint(cls, endpoint_pattern: str) -> Dict[str, int]:
        """
        Get rate limit configuration for endpoint pattern.

        Args:
            endpoint_pattern: Pattern to match endpoint type

        Returns:
            Dict with max_requests and window_seconds
        """
        # Latest image endpoints get strictest limits
        if "latest-image" in endpoint_pattern:
            if any(x in endpoint_pattern for x in ["thumbnail", "small", "full"]):
                return cls.DEFAULT_LIMITS["latest_image_serve"]
            return cls.DEFAULT_LIMITS["latest_image"]

        # Image serving endpoints
        if "/images/" in endpoint_pattern and any(
            x in endpoint_pattern for x in ["serve", "download"]
        ):
            return cls.DEFAULT_LIMITS["image_serve"]

        # Statistics endpoints
        if "statistics" in endpoint_pattern:
            return cls.DEFAULT_LIMITS["statistics"]

        # Admin endpoints
        if any(x in endpoint_pattern for x in ["admin", "settings", "config"]):
            return cls.DEFAULT_LIMITS["admin"]

        # Default for everything else
        return cls.DEFAULT_LIMITS["api_general"]


def get_client_identifier(request: Request) -> str:
    """
    Extract client identifier for rate limiting.

    Args:
        request: FastAPI request object

    Returns:
        Unique client identifier
    """
    # Try to get real IP from reverse proxy headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP in chain
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # For authenticated requests, could use user ID instead
    # user_id = request.headers.get("X-User-ID")
    # if user_id:
    #     return f"user:{user_id}"

    return f"ip:{client_ip}"


async def apply_rate_limit(request: Request, response: Response) -> None:
    """
    Apply rate limiting to request and add headers to response.

    Args:
        request: FastAPI request object
        response: FastAPI response object

    Raises:
        HTTPException: If rate limit is exceeded
    """
    endpoint_path = request.url.path
    client_id = get_client_identifier(request)

    # Get rate limit config for this endpoint
    limit_config = RateLimitConfig.get_limit_for_endpoint(endpoint_path)

    # Check rate limit
    is_allowed, rate_info = await rate_limiter.is_allowed(
        client_id=client_id,
        max_requests=limit_config["max_requests"],
        window_seconds=limit_config["window_seconds"],
    )

    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
    response.headers["X-RateLimit-Window"] = str(rate_info["window_seconds"])

    if not is_allowed:
        # Rate limit exceeded
        retry_after = rate_info["window_seconds"]

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Maximum {rate_info['limit']} requests allowed per {rate_info['window_seconds']} seconds.",
                "retry_after": retry_after,
                "current_requests": rate_info["current_requests"],
                "limit": rate_info["limit"],
                "window_seconds": rate_info["window_seconds"],
            },
            headers={"Retry-After": str(retry_after)},
        )


async def cleanup_rate_limiter() -> int:
    """Clean up old rate limiting data."""
    return await rate_limiter.cleanup_old_entries()


def rate_limit_endpoint(
    max_requests: Optional[int] = None, window_seconds: Optional[int] = None
):
    """
    Decorator for applying custom rate limits to specific endpoints.

    Args:
        max_requests: Override max requests for this endpoint
        window_seconds: Override window duration for this endpoint

    Usage:
        @rate_limit_endpoint(max_requests=1, window_seconds=10)
        async def very_restricted_endpoint():
            pass
    """

    def decorator(func):
        # Store custom rate limit config on function
        func._rate_limit_config = {
            "max_requests": max_requests,
            "window_seconds": window_seconds,
        }
        return func

    return decorator
