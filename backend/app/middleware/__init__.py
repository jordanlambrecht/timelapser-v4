# backend/app/middleware/__init__.py
"""
Middleware package for FastAPI application.

Provides centralized error handling, request logging, and performance monitoring.
"""

from .error_handler import ErrorHandlerMiddleware
from .request_logger import RequestLoggerMiddleware

__all__ = [
    "ErrorHandlerMiddleware",
    "RequestLoggerMiddleware",
]