# backend/app/database/core.py

"""
Base database classes for composition-based architecture.

These classes provide connection management and common functionality
without mixin inheritance, eliminating type safety issues.
"""

from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Optional, Any, AsyncGenerator, Generator
import time
import asyncio

from loguru import logger
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, AsyncConnectionPool
import psycopg

from ..config import settings
from ..utils.timezone_utils import utc_now



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
                min_size=2,
                max_size=settings.db_pool_size,
                max_waiting=settings.db_max_overflow,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            await self._pool.open()
            self._pool_created_at = utc_now()
            logger.info(f"Async database pool initialized (min: 2, max: {settings.db_pool_size}, overflow: {settings.db_max_overflow})")
        except Exception as e:
            logger.error(f"Failed to initialize async database pool: {e}")
            raise

    async def close(self) -> None:
        """
        Close the connection pool and cleanup resources.

        This should be called during application shutdown to ensure
        all database connections are properly closed.
        """
        if self._pool:
            await self._pool.close()
            logger.info("Async database pool closed")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Any, None]:
        """
        Get an async database connection from the pool with automatic transaction management.

        Yields:
            Connection: An async database connection with dict_row factory

        Raises:
            Exception: If connection pool is not initialized or connection fails

        Usage:
            async with db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM cameras")
                    data = await cur.fetchall()
        """
        if not self._pool:
            raise Exception("Database pool not initialized. Call initialize() first.")

        self._connection_attempts += 1
        start_time = time.time()
        
        try:
            async with self._pool.connection() as conn:
                async with conn.transaction():
                    yield conn
        except Exception as e:
            self._failed_connections += 1
            connection_time = time.time() - start_time
            logger.error(f"Database connection failed after {connection_time:.3f}s: {str(e) or type(e).__name__}")
            raise

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
                "pool_created_at": self._pool_created_at.isoformat() if self._pool_created_at else None,
                "uptime_seconds": (utc_now() - self._pool_created_at).total_seconds() if self._pool_created_at else 0,
                "connection_attempts": self._connection_attempts,
                "failed_connections": self._failed_connections,
                "success_rate": (self._connection_attempts - self._failed_connections) / max(self._connection_attempts, 1) * 100,
                "configuration": {
                    "min_size": 2,
                    "max_size": settings.db_pool_size,
                    "max_waiting": settings.db_max_overflow,
                }
            }
            
            # Try to get pool status (this may not be available in all psycopg3 versions)
            try:
                if hasattr(self._pool, 'get_stats'):
                    pool_stats = self._pool.get_stats()
                    stats.update({
                        "pool_stats": {
                            "pool_size": getattr(pool_stats, 'pool_size', 'unknown'),
                            "pool_available": getattr(pool_stats, 'pool_available', 'unknown'),
                            "requests_waiting": getattr(pool_stats, 'requests_waiting', 'unknown'),
                        }
                    })
            except Exception as e:
                stats["pool_stats_error"] = str(e)
            
            return stats
            
        except Exception as e:
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
        
        start_time = time.time()
        
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
                    
            connection_time = time.time() - start_time
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
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e),
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
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
                min_size=1,
                max_size=settings.db_pool_size // 2,  # Smaller pool for sync
                max_waiting=settings.db_max_overflow,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            self._pool.open()
            logger.info("Sync database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize sync database pool: {e}")
            raise

    def close(self) -> None:
        """
        Close the connection pool and cleanup resources.

        This should be called during worker process shutdown to ensure
        all database connections are properly closed.
        """
        if self._pool:
            self._pool.close()
            logger.info("Sync database pool closed")

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """
        Get a sync database connection from the pool with automatic transaction management.

        Yields:
            Connection: A sync database connection with dict_row factory

        Raises:
            Exception: If connection pool is not initialized or connection fails

        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM cameras")
                    data = cur.fetchall()
        """
        if not self._pool:
            raise Exception("Database pool not initialized. Call initialize() first.")

        with self._pool.connection() as conn:
            with conn.transaction():
                yield conn




# Composition-based database classes for services and routers
AsyncDatabase = AsyncDatabaseCore
SyncDatabase = SyncDatabaseCore
