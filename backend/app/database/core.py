# backend/app/database/core.py

"""
Base database classes for composition-based architecture.

These classes provide connection management and common functionality
without mixin inheritance, eliminating type safety issues.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Dict, Generator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from ..config import settings
from ..utils.time_utils import utc_now


class AsyncDatabaseCore:
    """
    Core async database functionality for composition-based architecture.

    This class provides connection management and common database operations
    without mixin inheritance.
    """

    def __init__(self) -> None:
        """Initialize the AsyncDatabaseCore instance with empty connection pool."""
        self._pool: Optional[AsyncConnectionPool] = None
        self._connection_attempts = 0
        self._failed_connections = 0
        self._last_health_check = None
        self._pool_created_at = None
        self._logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        """
        Initialize the async connection pool.

        Creates and opens an AsyncConnectionPool with configuration from settings.
        This method must be called before using any database operations.

        Raises:
            Exception: If connection pool initialization fails

        Note:
            This is typically called during FastAPI application startup.
        """
        try:
            self._pool = AsyncConnectionPool(
                settings.database_url,
                min_size=5,  # Increase minimum pool size for stability
                max_size=min(15, settings.db_pool_size),  # Reduce max pool size
                max_waiting=min(15, settings.db_max_overflow),  # Reduce waiting queue
                timeout=60,  # Increase timeout to 60 seconds
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 15,  # Increase connect timeout
                    "keepalives_idle": 300,  # Keep alive for 5 minutes (reduced)
                    "keepalives_interval": 60,  # Send keepalive every 60s (reduced frequency)
                    "keepalives_count": 5,  # Increase keepalive attempts
                },
                open=False,
            )
            await self._pool.open()
            self._pool_created_at = utc_now()
            self._connection_attempts = 0
            self._failed_connections = 0
        except (psycopg.Error, ConnectionError, OSError) as e:
            self._failed_connections += 1
            self._logger.error(f"Failed to initialize async database pool: {e}")
            raise

    async def close(self) -> None:
        """
        Close the connection pool and cleanup resources.

        This should be called during application shutdown to ensure
        all database connections are properly closed.
        """
        if self._pool:
            await self._pool.close()

    async def check_pool_health(self) -> bool:
        """
        Check if the async database connection pool is healthy.

        Returns:
            True if pool is healthy, False otherwise
        """
        if not self._pool:
            return False

        try:
            # Try to get a connection briefly
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()

            self._last_health_check = utc_now()
            return True
        except Exception as e:
            self._failed_connections += 1
            self._logger.warning(f"Async database health check failed: {e}")
            return False

    async def recover_connection_pool(self) -> bool:
        """
        Attempt to recover the async connection pool after failures.

        Returns:
            True if recovery successful, False otherwise
        """
        try:
            self._logger.warning(
                "Attempting async database connection pool recovery..."
            )

            # Close existing pool if it exists
            if self._pool:
                try:
                    await self._pool.close()
                    self._logger.debug("Closed old async connection pool")
                except Exception as e:
                    self._logger.warning(f"Error closing old async pool: {e}")

            # Wait briefly before re-initializing to avoid rapid reconnection attempts
            await asyncio.sleep(1)

            # Re-initialize the pool
            await self.initialize()
            self._logger.info("Re-initialized async connection pool")

            # Wait and then verify recovery worked
            await asyncio.sleep(0.5)
            if await self.check_pool_health():
                self._logger.info("Async database connection pool recovery successful")
                return True
            else:
                self._logger.error(
                    "Async database connection pool recovery failed - "
                    "health check failed"
                )
                return False

        except Exception as e:
            self._logger.error(f"Async database connection pool recovery failed: {e}")
            return False

    @asynccontextmanager
    async def get_connection(
        self, auto_recover: bool = True, max_retries: int = 2
    ) -> AsyncGenerator[Any, None]:
        """
        Get an async database connection with automatic recovery.

        Args:
            auto_recover: Whether to attempt automatic recovery on failures
            max_retries: Maximum number of recovery attempts

        Yields:
            Connection: An async database connection with dict_row factory

        Raises:
            Exception: If pool not initialized or connection fails after retries

        Usage:
            async with db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM cameras")
                    data = await cur.fetchall()
        """
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        retries = 0
        while retries <= max_retries:
            try:
                self._connection_attempts += 1
                async with self._pool.connection() as conn:
                    async with conn.transaction():
                        yield conn
                return  # Success, exit the retry loop

            except (
                psycopg.Error,
                psycopg.OperationalError,
                psycopg.DatabaseError,
                Exception,
            ) as e:
                self._failed_connections += 1
                self._logger.warning(
                    f"Async database connection failed "
                    f"(attempt {retries + 1}/{max_retries + 1}): {e}"
                )

                if retries >= max_retries:
                    # Final attempt failed, handle specific error types
                    self._logger.error(
                        f"Async database connection failed after "
                        f"{max_retries + 1} attempts"
                    )
                    if isinstance(e, psycopg.OperationalError):
                        raise ConnectionError("Database connection failed") from e
                    elif isinstance(e, psycopg.DatabaseError):
                        raise RuntimeError("Database operation failed") from e
                    else:
                        raise

                if auto_recover and retries < max_retries:
                    # Only attempt recovery for operational errors or after waiting
                    if isinstance(e, (psycopg.OperationalError, psycopg.DatabaseError)):
                        self._logger.info(
                            f"Attempting async database recovery (retry {retries + 1})"
                        )
                        recovery_success = await self.recover_connection_pool()

                        if not recovery_success:
                            # Recovery failed, but we might still try one more time
                            self._logger.warning(
                                f"Async database recovery attempt {retries + 1} failed"
                            )
                    else:
                        # For other errors, just wait before retry
                        await asyncio.sleep(0.5)

                retries += 1

    async def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get detailed connection pool statistics for monitoring.

        Returns:
            Dict containing pool health metrics, connection counts, and performance data
        """
        if not self._pool:
            return {"status": "not_initialized"}

        try:
            # Basic pool information
            stats = {
                "status": "healthy",
                "pool_created_at": (
                    self._pool_created_at.isoformat() if self._pool_created_at else None
                ),
                "uptime_seconds": (
                    (utc_now() - self._pool_created_at).total_seconds()
                    if self._pool_created_at
                    else 0
                ),
                "connection_attempts": self._connection_attempts,
                "failed_connections": self._failed_connections,
                "success_rate": (self._connection_attempts - self._failed_connections)
                / max(self._connection_attempts, 1)
                * 100,
                "configuration": {
                    "min_size": 2,
                    "max_size": settings.db_pool_size,
                    "max_waiting": settings.db_max_overflow,
                    "timeout": settings.db_pool_timeout,
                },
            }

            # Try to get pool status (this may not be available in all psycopg3
            # versions)
            try:
                if hasattr(self._pool, "get_stats"):
                    pool_stats = self._pool.get_stats()
                    stats.update(
                        {
                            "pool_stats": {
                                "pool_size": getattr(
                                    pool_stats, "pool_size", "unknown"
                                ),
                                "pool_available": getattr(
                                    pool_stats, "pool_available", "unknown"
                                ),
                                "requests_waiting": getattr(
                                    pool_stats, "requests_waiting", "unknown"
                                ),
                            }
                        }
                    )
            except (AttributeError, TypeError) as e:
                stats["pool_stats_error"] = str(e)

            return stats

        except (psycopg.Error, ConnectionError, RuntimeError) as e:
            return {
                "status": "error",
                "error": str(e),
                "connection_attempts": self._connection_attempts,
                "failed_connections": self._failed_connections,
            }

    async def health_check(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of the database connection.

        Args:
            timeout: Maximum time to wait for health check to complete

        Returns:
            Dict containing health status and performance metrics
        """
        if not self._pool:
            return {"status": "unhealthy", "error": "Pool not initialized"}

        start_time = time.time()  # Performance timing - timezone-irrelevant

        try:
            # Test connection with timeout - wrap the entire async context manager usage
            async with asyncio.timeout(timeout):
                async with self.get_connection() as conn:
                    async with conn.cursor() as cur:
                        # Test basic connectivity
                        await cur.execute("SELECT 1")
                        await cur.fetchone()

                        # Test transaction capability
                        await cur.execute("SELECT NOW()")
                        result = await cur.fetchone()

            connection_time = (
                time.time() - start_time
            )  # Performance timing - timezone-irrelevant
            self._last_health_check = utc_now()

            return {
                "status": "healthy",
                "response_time_ms": round(connection_time * 1000, 2),
                "last_check": self._last_health_check.isoformat(),
                "database_time": result[0].isoformat() if result else None,
            }

        except asyncio.TimeoutError:
            return {
                "status": "unhealthy",
                "error": f"Health check timed out after {timeout}s",
                "response_time_ms": round(
                    (time.time() - start_time) * 1000, 2
                ),  # Performance timing - timezone-irrelevant
            }
        except (psycopg.Error, ConnectionError, RuntimeError) as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(
                    (time.time() - start_time) * 1000, 2
                ),  # Performance timing - timezone-irrelevant
            }


class SyncDatabaseCore:
    """
    Core sync database functionality for composition-based architecture.

    This class provides connection management and common database operations
    without mixin inheritance.
    """

    def __init__(self) -> None:
        """Initialize the SyncDatabaseCore instance with empty connection pool."""
        self._pool: Optional[ConnectionPool] = None
        self._connection_attempts = 0
        self._failed_connections = 0
        self._last_health_check = None
        self._pool_created_at = None
        self._logger = logging.getLogger(__name__)

    def initialize(self) -> None:
        """
        Initialize the sync connection pool.

        Creates and opens a ConnectionPool with configuration from settings.
        This method must be called before using any database operations.

        Raises:
            Exception: If connection pool initialization fails

        Note:
            This is typically called during worker process startup.
        """
        try:
            self._pool = ConnectionPool(
                settings.database_url,
                min_size=3,  # Increase minimum pool size for stability
                max_size=max(
                    5, min(10, settings.db_pool_size // 2)
                ),  # Conservative pool size
                max_waiting=min(10, settings.db_max_overflow),
                timeout=60,  # Increase timeout to 60 seconds
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 15,  # Increase connect timeout
                    "keepalives_idle": 300,  # Keep alive for 5 minutes (reduced)
                    "keepalives_interval": 60,  # Send keepalive every 60s (reduced frequency)
                    "keepalives_count": 5,  # Increase keepalive attempts
                },
                open=False,
            )
            self._pool.open()
            self._pool_created_at = utc_now()
            self._connection_attempts = 0
            self._failed_connections = 0
        except Exception as e:
            self._failed_connections += 1
            self._logger.error(f"Failed to initialize database pool: {e}")
            raise

    def close(self) -> None:
        """
        Close the connection pool and cleanup resources.

        This should be called during worker process shutdown to ensure
        all database connections are properly closed.
        """
        if self._pool:
            self._pool.close()

    def check_pool_health(self) -> bool:
        """
        Check if the database connection pool is healthy.

        Returns:
            True if pool is healthy, False otherwise
        """
        if not self._pool:
            return False

        try:
            # Try to get a connection briefly
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()

            self._last_health_check = utc_now()
            return True
        except Exception as e:
            self._failed_connections += 1
            self._logger.warning(f"Database health check failed: {e}")
            return False

    def recover_connection_pool(self) -> bool:
        """
        Attempt to recover the connection pool after failures.

        Returns:
            True if recovery successful, False otherwise
        """
        try:
            self._logger.warning("Attempting sync database connection pool recovery...")

            # Close existing pool if it exists
            if self._pool:
                try:
                    self._pool.close()
                    self._logger.debug("Closed old sync connection pool")
                except Exception as e:
                    self._logger.warning(f"Error closing old pool: {e}")

            # Wait briefly before re-initializing
            time.sleep(1)

            # Re-initialize the pool
            self.initialize()
            self._logger.info("Re-initialized sync connection pool")

            # Wait and then verify recovery worked
            time.sleep(0.5)
            if self.check_pool_health():
                self._logger.info("Sync database connection pool recovery successful")
                return True
            else:
                self._logger.error(
                    "Sync database connection pool recovery failed - health check failed"
                )
                return False

        except Exception as e:
            self._logger.error(f"Sync database connection pool recovery failed: {e}")
            return False

    def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        if not self._pool:
            return {"pool_initialized": False}

        return {
            "pool_initialized": True,
            "pool_created_at": self._pool_created_at,
            "connection_attempts": self._connection_attempts,
            "failed_connections": self._failed_connections,
            "last_health_check": self._last_health_check,
            "pool_size": getattr(self._pool, "size", 0),
            "pool_available": getattr(self._pool, "available", 0),
        }

    @contextmanager
    def get_connection(
        self, auto_recover: bool = True, max_retries: int = 2
    ) -> Generator[Any, None, None]:
        """
        Get a sync database connection with automatic recovery.

        Args:
            auto_recover: Whether to attempt automatic recovery on failures
            max_retries: Maximum number of recovery attempts

        Yields:
            Connection: A sync database connection with dict_row factory

        Raises:
            Exception: If pool not initialized or connection fails after retries

        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM cameras")
                    data = cur.fetchall()
        """
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        retries = 0
        while retries <= max_retries:
            try:
                self._connection_attempts += 1
                with self._pool.connection() as conn:
                    with conn.transaction():
                        yield conn
                return  # Success, exit the retry loop

            except Exception as e:
                self._failed_connections += 1
                self._logger.warning(
                    f"Database connection failed "
                    f"(attempt {retries + 1}/{max_retries + 1}): {e}"
                )

                if retries >= max_retries:
                    # Final attempt failed, raise the error
                    self._logger.error(
                        f"Database connection failed after {max_retries + 1} attempts"
                    )
                    raise

                if auto_recover and retries < max_retries:
                    # Only attempt recovery for connection-related errors
                    if isinstance(e, (psycopg.OperationalError, psycopg.DatabaseError)):
                        self._logger.info(
                            f"Attempting sync database recovery (retry {retries + 1})"
                        )
                        recovery_success = self.recover_connection_pool()

                        if not recovery_success:
                            # Recovery failed, but we might still try one more time
                            self._logger.warning(
                                f"Sync database recovery attempt {retries + 1} failed"
                            )
                    else:
                        # For other errors, just wait before retry
                        time.sleep(0.5)

                retries += 1


# Composition-based database classes for services and routers
AsyncDatabase = AsyncDatabaseCore
SyncDatabase = SyncDatabaseCore
