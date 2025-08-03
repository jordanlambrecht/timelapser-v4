"""
Context Extractor for the Logger Service.

This module provides context extraction and enrichment utilities that
gather additional metadata and context information for log entries.
"""

import inspect
import traceback
from typing import Dict, Any, Optional

import asyncio
import threading
import os
import sys
import uuid

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from ....utils.time_utils import utc_now, utc_timestamp
from ..constants import (
    DEFAULT_MAX_STACK_DEPTH, MAX_CONTEXT_STRING_LENGTH, 
    CONTEXT_STRING_TRUNCATE_LENGTH, CONTEXT_TRUNCATE_SUFFIX,
    MEMORY_USAGE_DECIMAL_PLACES, CPU_PERCENT_DECIMAL_PLACES,
    STACK_FILTER_PATTERNS, DOCKER_ENV_FILE, DOCKER_CONTAINER_ENV_VAR,
    TIMELAPSER_MODULE_INDICATOR
)

# Note: Using UTC timestamps for consistency across async/sync contexts
# For future enhancement: could integrate with time_utils for user timezone display


class ContextExtractor:
    """
    Extractor for enriching log entries with additional context information.

    Features:
    - Stack trace analysis
    - Function and module context
    - Thread and process information
    - Performance metrics
    - Environment context
    - Correlation ID tracking
    """

    def __init__(
        self,
        max_stack_depth: int = DEFAULT_MAX_STACK_DEPTH,
        include_environment: bool = True,
        include_stack_traces: bool = False,
    ):
        """
        Initialize the context extractor.

        Args:
            max_stack_depth: Maximum stack frames to analyze
            include_environment: Whether to include environment information
            include_stack_traces: Whether to include stack traces (disabled in production)
        """
        self.max_stack_depth = max_stack_depth
        self.include_environment = include_environment
        self.include_stack_traces = include_stack_traces

        # Cache for environment context (computed once)
        self._env_context = None
        if include_environment:
            self._env_context = self._get_environment_context()

    def extract_context(
        self,
        base_context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        include_stack: bool = False,
        include_performance: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract comprehensive context information for a log entry.

        Args:
            base_context: Base context data provided by caller
            correlation_id: Optional correlation ID for request tracing
            include_stack: Whether to include stack trace information
            include_performance: Whether to include performance metrics

        Returns:
            Enriched context dictionary
        """
        # Start with base context
        context = base_context.copy() if base_context else {}

        # Add timestamp information
        context.update(self._get_timestamp_context())

        # Add correlation ID if provided
        if correlation_id:
            context["correlation_id"] = correlation_id

        # Add execution context
        context.update(self._get_execution_context())

        # Add stack information if requested and enabled
        if include_stack and self.include_stack_traces:
            context.update(self._get_stack_context())

        # Add performance information if requested
        if include_performance:
            context.update(self._get_performance_context())

        # Add environment context
        if self.include_environment and self._env_context:
            context.update(self._env_context)

        # Clean up context (remove None values, limit size)
        context = self._clean_context(context)

        return context

    def _get_timestamp_context(self) -> Dict[str, Any]:
        """Get timezone-aware timestamp context information."""
        # Use UTC timestamp for consistency across contexts

        return {
            "extracted_at": utc_timestamp(),
            "extracted_timestamp": utc_now().timestamp(),
            "extracted_at_utc": utc_timestamp(),
        }

    def _get_execution_context(self) -> Dict[str, Any]:
        """Get execution context information (thread, process, etc.)."""
        # Thread information
        current_thread = threading.current_thread()
        context = {
            "thread_name": current_thread.name,
            "thread_id": current_thread.ident,
            "process_id": os.getpid(),
        }

        # Async context if available
        try:
            loop = asyncio.get_event_loop()
            context["asyncio_loop"] = str(loop)
            context["is_asyncio"] = True
        except RuntimeError:
            context["is_asyncio"] = False

        return context

    def _get_stack_context(self) -> Dict[str, Any]:
        """Get stack trace context information."""
        # Get current stack
        stack = inspect.stack()

        # Skip frames from this extractor and logger
        relevant_frames = []
        for frame_info in stack[1:]:  # Skip current frame
            filename = frame_info.filename
            function_name = frame_info.function

            # Skip logger-related frames
            if any(skip in filename.lower() for skip in STACK_FILTER_PATTERNS):
                continue

            relevant_frames.append(
                {
                    "filename": os.path.basename(filename),
                    "function": function_name,
                    "line_number": frame_info.lineno,
                    "module": self._get_module_name(filename),
                }
            )

            # Limit stack depth
            if len(relevant_frames) >= self.max_stack_depth:
                break

        context = {}
        if relevant_frames:
            context["stack_trace"] = relevant_frames

            # Add caller information (most relevant frame)
            caller = relevant_frames[0]
            context["caller_function"] = caller["function"]
            context["caller_module"] = caller["module"]
            context["caller_file"] = caller["filename"]
            context["caller_line"] = caller["line_number"]

        return context

    def _get_performance_context(self) -> Dict[str, Any]:
        """Get performance-related context information."""
        try:
            if not PSUTIL_AVAILABLE:
                return {"performance_unavailable": "psutil_not_installed"}

            # Memory usage
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                "memory_usage_mb": round(memory_info.rss / 1024 / 1024, MEMORY_USAGE_DECIMAL_PLACES),
                "memory_percent": round(process.memory_percent(), MEMORY_USAGE_DECIMAL_PLACES),
                "cpu_percent": round(process.cpu_percent(), CPU_PERCENT_DECIMAL_PLACES),
                "thread_count": process.num_threads(),
            }

        except Exception:
            # psutil error
            return {"performance_unavailable": "psutil_error"}

    # TODO: This needs to be globalized and cached
    def _get_environment_context(self) -> Dict[str, Any]:
        """Get environment context information (cached)."""
        context = {"python_version": sys.version.split()[0], "platform": sys.platform}

        # Application information
        if "TIMELAPSER_VERSION" in os.environ:
            context["app_version"] = os.environ["TIMELAPSER_VERSION"]

        if "ENVIRONMENT" in os.environ:
            context["environment"] = os.environ["ENVIRONMENT"]

        # Docker/container detection
        if os.path.exists(DOCKER_ENV_FILE) or os.environ.get(DOCKER_CONTAINER_ENV_VAR):
            context["container"] = "docker"

        return context

    def _get_module_name(self, filename: str) -> str:
        """
        Extract module name from filename.

        Args:
            filename: Full file path

        Returns:
            Module name
        """
        # Extract meaningful module path
        if TIMELAPSER_MODULE_INDICATOR in filename:
            # Find the part after timelapser
            parts = filename.split(os.sep)
            if TIMELAPSER_MODULE_INDICATOR in parts:
                timelapser_idx = parts.index(TIMELAPSER_MODULE_INDICATOR)
                module_parts = parts[timelapser_idx + 1 :]
                # Remove .py extension
                if module_parts and module_parts[-1].endswith(".py"):
                    module_parts[-1] = module_parts[-1][:-3]
                return ".".join(module_parts)

        # Fallback to filename without extension
        return os.path.splitext(os.path.basename(filename))[0]

    def _clean_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and optimize context data.

        Args:
            context: Raw context dictionary

        Returns:
            Cleaned context dictionary
        """
        cleaned = {}

        for key, value in context.items():
            match value:
                # Skip None values
                case None:
                    continue
                # Skip empty strings
                case str() as s if not s.strip():
                    continue
                # Skip empty collections
                case list() | dict() as col if not col:
                    continue
                # Limit string length
                case str() as s if len(s) > MAX_CONTEXT_STRING_LENGTH:
                    cleaned[key] = s[:CONTEXT_STRING_TRUNCATE_LENGTH] + CONTEXT_TRUNCATE_SUFFIX
                case _:
                    cleaned[key] = value

        return cleaned

    def extract_error_context(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract comprehensive error context from an exception.

        Args:
            exception: Exception object
            operation: Operation that failed (optional)
            additional_context: Additional context data

        Returns:
            Error context dictionary
        """
        context = additional_context.copy() if additional_context else {}

        # Basic exception information
        context["exception_type"] = type(exception).__name__
        context["exception_message"] = str(exception)

        # Operation context
        if operation:
            context["failed_operation"] = operation

        # Stack trace
        context["stack_trace"] = traceback.format_exc()

        # Add execution context
        context.update(self._get_execution_context())

        return self._clean_context(context)

    def extract_performance_context(
        self,
        operation: str,
        start_time: float,
        end_time: Optional[float] = None,
        success: bool = True,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract performance context for an operation.

        Args:
            operation: Operation name
            start_time: Start timestamp
            end_time: End timestamp (defaults to now)
            success: Whether operation was successful
            metrics: Additional performance metrics

        Returns:
            Performance context dictionary
        """
        if end_time is None:
            end_time = utc_now().timestamp()

        context = {
            "operation": operation,
            "start_time": start_time,
            "end_time": end_time,
            "duration_ms": round((end_time - start_time) * 1000, 2),
            "success": success,
        }

        # Add custom metrics
        if metrics:
            context.update(metrics)

        # Add performance context if available
        context.update(self._get_performance_context())

        return self._clean_context(context)

    def create_correlation_id(self, prefix: str = "log") -> str:
        """
        Create a correlation ID for request tracing.

        Args:
            prefix: Prefix for the correlation ID

        Returns:
            Generated correlation ID
        """

        timestamp = int(utc_now().timestamp() * 1000)
        random_part = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{random_part}"
