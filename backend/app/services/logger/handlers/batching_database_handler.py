"""
Batching Database Handler for the Logger Service.

This handler batches log entries in memory and flushes them to the database
in bulk operations for improved performance with high-frequency logging.
"""

import asyncio
import threading
from queue import Queue
from typing import Any, Dict, List, Optional

from loguru import logger

from ....constants import (
    LOG_BATCH_MAX_RETRIES,
    LOG_BATCH_RETRY_DELAY,
    LOG_BATCH_SIZE,
    LOG_BATCH_TIMEOUT_SECONDS,
)
from ....database.log_operations import LogOperations, SyncLogOperations
from ....enums import LogEmoji, LoggerName, LogLevel, LogSource
from ....models.log_model import LogCreate


class BatchingDatabaseHandler:
    """
    Database handler that batches log entries for efficient bulk insertion.

    Features:
    - Batches logs in memory before database writes
    - Automatic flush on batch size or timeout
    - Thread-safe for concurrent logging
    - Graceful shutdown with final flush
    - Retry logic for failed batches
    - Fallback to immediate writes if batching fails
    """

    def __init__(
        self,
        async_log_ops: LogOperations,
        sync_log_ops: SyncLogOperations,
        batch_size: int = LOG_BATCH_SIZE,
        batch_timeout: float = LOG_BATCH_TIMEOUT_SECONDS,
        max_retries: int = LOG_BATCH_MAX_RETRIES,
        retry_delay: float = LOG_BATCH_RETRY_DELAY,
    ):
        """
        Initialize the batching database handler.

        Args:
            async_log_ops: Async log operations instance
            sync_log_ops: Sync log operations instance
            batch_size: Maximum logs to batch before flush
            batch_timeout: Maximum seconds to wait before flush
            max_retries: Number of retries for failed batches
            retry_delay: Seconds between retry attempts
        """
        self.async_log_ops = async_log_ops
        self.sync_log_ops = sync_log_ops
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Thread-safe queue for log entries
        self.log_queue: Queue[LogCreate] = Queue()

        # Batch processing state
        self.current_batch: List[LogCreate] = []
        self.batch_lock = threading.Lock()

        # Async event loop and task management
        self.flush_event: Optional[asyncio.Event] = None
        self.flush_task: Optional[asyncio.Task] = None
        self.loop = None

        # Handler state
        self._running = True
        self._healthy = True
        self._last_error = None
        self._total_logs_batched = 0
        self._total_batches_flushed = 0
        self._failed_batches = 0

        # Start background flush timer
        self._start_flush_timer()

    def _start_flush_timer(self):
        """Start the background timer for periodic flushing."""
        try:
            # Get or create event loop
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, we'll handle sync only
                self.loop = None
                return

            # Create flush event
            self.flush_event = asyncio.Event()

            # Start background flush task
            self.flush_task = asyncio.create_task(self._flush_timer())

        except Exception as e:
            logger.error(f"Failed to start flush timer: {e}")
            self._healthy = False

    async def _flush_timer(self):
        """Background task that flushes batches on timeout."""
        while self._running:
            try:
                # Wait for timeout or flush event
                if self.flush_event is not None:
                    await asyncio.wait_for(
                        self.flush_event.wait(), timeout=self.batch_timeout
                    )
                else:
                    await asyncio.sleep(self.batch_timeout)

                # Clear the event if it exists
                if self.flush_event is not None:
                    self.flush_event.clear()

            except asyncio.TimeoutError:
                # Timeout reached, flush current batch
                await self._flush_batch_async()

            except Exception as e:
                logger.error(f"Flush timer error: {e}")
                await asyncio.sleep(1)  # Brief pause before retry

    async def handle_async(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        emoji: Optional[LogEmoji] = None,
    ) -> None:
        """
        Handle a log entry asynchronously with batching.

        Args:
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            camera_id: Optional camera ID
            extra_data: Optional extra data
        """
        try:
            # Create log entry with LogLevel enum
            log_level = LogLevel(level) if isinstance(level, str) else LogLevel.INFO

            log_entry = LogCreate(
                message=message,
                level=log_level,
                logger_name=logger_name,
                source=source,
                camera_id=camera_id,
                extra_data=extra_data,
                emoji=emoji,
            )

            # Add to batch
            with self.batch_lock:
                self.current_batch.append(log_entry)
                batch_full = len(self.current_batch) >= self.batch_size

            # Flush if batch is full
            if batch_full:
                await self._flush_batch_async()

        except Exception as e:
            self._last_error = str(e)
            self._healthy = False
            logger.error(f"BatchingDatabaseHandler.handle_async failed: {e}")

            # Fallback: Try immediate write
            try:
                await self._write_single_log_async(
                    message, level, source, logger_name, camera_id, extra_data
                )
            except Exception as fallback_error:
                logger.error("Fallback write also failed", exception=fallback_error)

    def handle_sync(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        emoji: Optional[LogEmoji] = None,
    ) -> None:
        """
        Handle a log entry synchronously with batching.

        Args:
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            camera_id: Optional camera ID
            extra_data: Optional extra data
        """

        try:
            # Ensure enums for logger_name and source
            log_level = LogLevel(level) if isinstance(level, str) else level
            logger_name_enum = (
                LoggerName(logger_name) if isinstance(logger_name, str) else logger_name
            )
            source_enum = LogSource(source) if isinstance(source, str) else source
            log_entry = LogCreate(
                message=message,
                level=log_level,
                logger_name=logger_name_enum,
                source=source_enum,
                camera_id=camera_id,
                extra_data=extra_data,
                emoji=emoji,
            )

            # Add to batch
            with self.batch_lock:
                self.current_batch.append(log_entry)
                batch_full = len(self.current_batch) >= self.batch_size

            # Flush if batch is full (sync version)
            if batch_full:
                self._flush_batch_sync()

        except Exception as e:
            self._last_error = str(e)
            self._healthy = False
            logger.error(f"BatchingDatabaseHandler.handle_sync failed: {e}")

            # Fallback: Try immediate write
            try:
                logger_name_enum = (
                    LoggerName(logger_name)
                    if isinstance(logger_name, str)
                    else logger_name
                )
                source_enum = LogSource(source) if isinstance(source, str) else source
                self._write_single_log_sync(
                    message=message,
                    level=level,
                    source=source_enum,
                    logger_name=logger_name_enum,
                    camera_id=camera_id,
                    extra_data=extra_data,
                )
            except Exception as fallback_error:
                logger.error("Fallback write also failed", exception=fallback_error)

    async def _flush_batch_async(self):
        """Flush the current batch to the database asynchronously."""
        with self.batch_lock:
            batch_to_flush = self.current_batch
            self.current_batch = []

        # Attempt to write batch with retries and exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Bulk insert logs
                await self.async_log_ops.bulk_create_logs(batch_to_flush)

                # Update statistics and mark as healthy on success
                self._total_logs_batched += len(batch_to_flush)
                self._total_batches_flushed += 1
                self._healthy = True  # Reset health status on successful write

                return  # Success

            except Exception as e:
                is_connection_error = (
                    any(
                        error_type in str(type(e))
                        for error_type in [
                            "ConnectionError",
                            "OperationalError",
                            "DatabaseError",
                            "SSL",
                        ]
                    )
                    or "connection" in str(e).lower()
                )

                logger.error(
                    f"Batch flush attempt {attempt + 1}/{self.max_retries} failed: {e}"
                    + (" [Connection Error]" if is_connection_error else "")
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff for connection errors, linear for others
                    delay = (
                        (self.retry_delay * (2**attempt))
                        if is_connection_error
                        else self.retry_delay
                    )
                    await asyncio.sleep(min(delay, 10.0))  # Cap at 10 seconds
                else:
                    # Final attempt failed
                    self._failed_batches += 1
                    self._healthy = False

                    # Try to save logs individually as last resort
                    await self._fallback_individual_writes_async(batch_to_flush)

    def _flush_batch_sync(self):
        """Flush the current batch to the database synchronously."""
        with self.batch_lock:
            batch_to_flush = self.current_batch
            self.current_batch = []

        # Attempt to write batch with retries
        for attempt in range(self.max_retries):
            try:
                # Bulk insert logs
                self.sync_log_ops.bulk_create_logs(batch_to_flush)

                # Update statistics
                self._total_logs_batched += len(batch_to_flush)
                self._total_batches_flushed += 1

                return  # Success

            except Exception as e:
                logger.error(f"Batch flush attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    import time

                    time.sleep(self.retry_delay)
                else:
                    # Final attempt failed
                    self._failed_batches += 1
                    self._healthy = False

                    # Try to save logs individually as last resort
                    self._fallback_individual_writes_sync(batch_to_flush)

    async def _write_single_log_async(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        camera_id: Optional[int],
        extra_data: Optional[Dict[str, Any]],
        emoji: Optional[LogEmoji] = None,
    ):
        """Write a single log entry directly to database (async)."""
        # Create log entry with LogLevel enum
        log_level = LogLevel(level) if isinstance(level, str) else level

        log_entry = LogCreate(
            message=message,
            level=log_level,
            logger_name=logger_name,
            source=source,
            camera_id=camera_id,
            extra_data=extra_data,
            emoji=emoji,
        )
        await self.async_log_ops.create_log(log_entry)

    def _write_single_log_sync(self, **kwargs):
        """Write a single log entry directly to database (sync)."""
        # Pydantic will validate and coerce types as needed
        log_entry = LogCreate(**kwargs)
        self.sync_log_ops.create_log(log_entry)

    async def _fallback_individual_writes_async(self, batch: List[LogCreate]):
        """Attempt to write logs individually as fallback with retry (async)."""
        saved_count = 0

        for log_entry in batch:
            # Try each individual log with limited retries
            for attempt in range(2):  # Only 2 attempts for fallback
                try:
                    await self.async_log_ops.create_log(log_entry)
                    saved_count += 1
                    break  # Success, move to next log
                except Exception as e:
                    if attempt == 0:
                        # Brief delay before retry
                        await asyncio.sleep(0.5)
                    else:
                        # Final attempt failed
                        logger.error(
                            f"Failed to save individual log after {attempt + 1} attempts: {e}"
                        )

        if saved_count > 0:
            logger.info(
                f"Saved {saved_count}/{len(batch)} logs via individual fallback"
            )
        elif len(batch) > 0:
            logger.warning(f"Failed to save all {len(batch)} logs in fallback mode")

    def _fallback_individual_writes_sync(self, batch: List[LogCreate]):
        """Attempt to write logs individually as fallback (sync)."""
        saved_count = 0

        for log_entry in batch:
            try:
                self.sync_log_ops.create_log(log_entry)
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save individual log: {e}")

        if saved_count > 0:
            logger.info(f"Saved {saved_count}/{len(batch)} logs via fallback")

    async def flush_async(self):
        """Manually flush any pending logs asynchronously."""
        await self._flush_batch_async()

    def flush_sync(self):
        """Manually flush any pending logs synchronously."""
        self._flush_batch_sync()

    async def shutdown(self):
        """Gracefully shutdown the handler with final flush."""
        logger.info("Shutting down BatchingDatabaseHandler...")

        # Stop accepting new logs
        self._running = False

        # Cancel flush timer
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush_async()

        logger.info(
            f"BatchingDatabaseHandler shutdown complete. "
            f"Total logs: {self._total_logs_batched}, "
            f"Batches: {self._total_batches_flushed}, "
            f"Failed: {self._failed_batches}"
        )

    def shutdown_sync(self):
        """Gracefully shutdown the handler with final flush (sync)."""
        logger.info("Shutting down BatchingDatabaseHandler...")

        # Stop accepting new logs
        self._running = False

        # Final flush
        self.flush_sync()

        logger.info(
            f"BatchingDatabaseHandler shutdown complete. "
            f"Total logs: {self._total_logs_batched}, "
            f"Batches: {self._total_batches_flushed}, "
            f"Failed: {self._failed_batches}"
        )

    def is_healthy(self) -> bool:
        """Check if handler is healthy."""
        return self._healthy and self._running

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        with self.batch_lock:
            pending_logs = len(self.current_batch)

        return {
            "healthy": self.is_healthy(),
            "running": self._running,
            "pending_logs": pending_logs,
            "total_logs_batched": self._total_logs_batched,
            "total_batches_flushed": self._total_batches_flushed,
            "failed_batches": self._failed_batches,
            "batch_size": self.batch_size,
            "batch_timeout_seconds": self.batch_timeout,
            "last_error": self._last_error,
        }
