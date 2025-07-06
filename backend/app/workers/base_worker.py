"""
Base worker class for Timelapser v4 worker architecture.

Provides common interfaces and utilities for all worker types.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional
from loguru import logger


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
