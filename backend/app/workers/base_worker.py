"""
Base worker class for Timelapser v4 worker architecture.

Provides common interfaces and utilities for all worker types.

IMPORTANT ARCHITECTURAL NOTE:
This base class provides TWO distinct lifecycle methods:

1. start()/stop() - Worker lifecycle management
   - Called by worker.py to initialize/cleanup workers
   - Sets self.running flag and calls initialize()/cleanup()
   - DOES NOT start autonomous processing loops

2. run() - Optional autonomous background processing (NOT DEFINED HERE)
   - Implemented by workers that need continuous background processing
   - Examples: ThumbnailWorker, OverlayWorker, CleanupWorker
   - These run() methods are LEGITIMATE and follow the CEO architecture
   - They process job queues or run scheduled tasks autonomously
   - They do NOT make timing decisions (that's the SchedulerWorker's job)

CEO ARCHITECTURE COMPLIANCE:
- SchedulerWorker = CEO (makes all timing decisions)
- Background Workers with run() = Departments processing job queues
- Direct Workers (CaptureWorker) = Immediate delegates with no autonomous timing

Workers with run() methods are NOT architectural violations - they are
essential background processors that handle work queues independently
while respecting the scheduler's timing authority.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional, TypedDict, Dict
from loguru import logger


class WorkerErrorResponse(TypedDict):
    """Standardized error response format for worker operations."""

    success: bool
    error: Optional[str]
    data: Optional[Dict[str, Any]]


class BaseWorker(ABC):
    """
    Abstract base class for all Timelapser workers.

    Provides common interface and utilities for worker implementation.
    Each worker is responsible for a specific domain of functionality.
    """

    def __init__(self, name: str):
        """
        Initialize base worker.

        Args:
            name: Worker name for logging and identification
        """
        self.name = name
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Get the current event loop."""
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def start(self) -> None:
        """Start the worker."""
        logger.info(f"Starting {self.name} worker")
        self.running = True
        await self.initialize()

    async def stop(self) -> None:
        """Stop the worker."""
        logger.info(f"Stopping {self.name} worker")
        self.running = False
        await self.cleanup()

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize worker-specific resources."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup worker-specific resources."""
        pass

    def log_info(self, message: str) -> None:
        """Log info message with worker name prefix."""
        logger.info(f"[{self.name}] {message}")

    def log_error(self, message: str, error: Optional[Exception] = None) -> None:
        """Log error message with worker name prefix."""
        if error:
            logger.error(f"[{self.name}] {message}: {error}")
        else:
            logger.error(f"[{self.name}] {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message with worker name prefix."""
        logger.warning(f"[{self.name}] {message}")

    def log_debug(self, message: str) -> None:
        """Log debug message with worker name prefix."""
        logger.debug(f"[{self.name}] {message}")

    async def run_in_executor(self, func, *args, **kwargs) -> Any:
        """Run a sync function in executor to maintain async compatibility."""
        return await self.loop.run_in_executor(None, func, *args, **kwargs)

    # Standardized optional methods for job processing workers

    def get_status(self) -> Dict[str, Any]:
        """
        Get current worker status.

        This is the standardized method name that all workers should implement
        for status reporting. Job processing workers that use JobProcessingMixin
        get this automatically.

        Returns:
            Dictionary with worker status information
        """
        return {
            "name": self.name,
            "running": self.running,
            "worker_type": self.__class__.__name__,
        }

    # Enhanced logging methods with performance tracking

    def log_performance(self, operation: str, duration_ms: float) -> None:
        """
        Log performance metrics with worker name prefix.

        Args:
            operation: Name of the operation being measured
            duration_ms: Duration in milliseconds
        """
        logger.info(f"[{self.name}] 📊 {operation} completed in {duration_ms:.2f}ms")

    def log_job_metrics(self, processed: int, failed: int, success_rate: float) -> None:
        """
        Log job processing metrics with worker name prefix.

        Args:
            processed: Number of jobs processed successfully
            failed: Number of jobs that failed
            success_rate: Success rate as a percentage
        """
        logger.info(
            f"[{self.name}] 📈 Jobs processed: {processed}, failed: {failed}, "
            f"success rate: {success_rate:.1f}%"
        )

    def log_queue_metrics(self, pending: int, processing: int, total: int) -> None:
        """
        Log job queue metrics with worker name prefix.

        Args:
            pending: Number of pending jobs
            processing: Number of jobs currently processing
            total: Total number of jobs in queue
        """
        logger.info(
            f"[{self.name}] 📋 Queue status: {pending} pending, {processing} processing, "
            f"{total} total"
        )

    # Worker health monitoring utilities

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get worker health status for monitoring.

        Returns:
            Dictionary with health status information
        """
        return {
            "worker_name": self.name,
            "running": self.running,
            "healthy": self.running,  # Basic health check
            "last_check": "now",  # Can be overridden by subclasses
        }

    def is_healthy(self) -> bool:
        """
        Check if worker is in a healthy state.

        Returns:
            True if worker is healthy, False otherwise
        """
        return self.running

    # Standardized error response creation

    def create_error_response(
        self, error_message: str, data: Optional[Dict[str, Any]] = None
    ) -> WorkerErrorResponse:
        """
        Create standardized error response.

        Args:
            error_message: Description of the error
            data: Optional additional error data

        Returns:
            Standardized error response
        """
        return WorkerErrorResponse(success=False, error=error_message, data=data)

    def create_success_response(
        self, data: Optional[Dict[str, Any]] = None
    ) -> WorkerErrorResponse:
        """
        Create standardized success response.

        Args:
            data: Optional response data

        Returns:
            Standardized success response
        """
        return WorkerErrorResponse(success=True, error=None, data=data)
