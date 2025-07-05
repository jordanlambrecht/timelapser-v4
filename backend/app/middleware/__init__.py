# backend/app/middleware/__init__.py
"""
Middleware package for FastAPI application.

Provides centralized error handling, request logging, and performance monitoring.
"""

from .error_handler import ErrorHandlerMiddleware
from .request_logger import RequestLoggerMiddleware
from .rate_limit_middleware import RateLimitMiddleware

__all__ = [
    "ErrorHandlerMiddleware",
    "RequestLoggerMiddleware",
    "RateLimitMiddleware",
]
