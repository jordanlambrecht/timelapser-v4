# backend/app/workers/database_factory.py
"""
Worker Database Factory

Provides centralized database initialization for the worker process
following the same patterns as main.py but optimized for worker use.
"""

from typing import Tuple

from ..database import async_db, sync_db
from ..enums import LogEmoji, LoggerName
from ..services.logger.logger_service import (
    get_service_logger,
    initialize_global_logger,
)


async def initialize_worker_databases() -> Tuple[object, object]:
    """
    Initialize both async and sync databases for worker process.

    This follows the same pattern as main.py but is optimized for worker use
    where we need both database types to be fully initialized before
    proceeding with service creation.

    Returns:
        Tuple of (async_db, sync_db) - both fully initialized

    Raises:
        Exception: If database initialization fails
    """
    # Initialize async database first (required for logger)
    await async_db.initialize()

    # Initialize sync database for worker operations
    sync_db.initialize()

    return async_db, sync_db


async def initialize_worker_logger(async_db_instance, sync_db_instance):
    """
    Initialize the global logger for worker process.

    Args:
        async_db_instance: Initialized async database instance
        sync_db_instance: Initialized sync database instance

    Returns:
        Logger instance ready for use
    """
    # Initialize the global logger with worker-optimized settings
    await initialize_global_logger(
        async_db=async_db_instance,
        sync_db=sync_db_instance,
        enable_console=True,
        enable_file_logging=True,
        enable_sse_broadcasting=True,
        enable_batching=True,
    )

    # Get the system logger for worker use
    return get_service_logger(LoggerName.SYSTEM)


async def create_worker_database_context():
    """
    Create complete database context for worker.

    This is the main entry point for worker database initialization.
    It handles the complete initialization sequence:

    1. Initialize both databases
    2. Initialize global logger system
    3. Return logger instance ready for immediate use

    Returns:
        Tuple of (logger, async_db, sync_db) - all ready for use

    Example:
        logger, async_db, sync_db = await create_worker_database_context()
        logger.info("Worker databases initialized")
    """
    try:
        # Step 1: Initialize databases
        async_db_instance, sync_db_instance = await initialize_worker_databases()

        # Step 2: Initialize logger system
        logger = await initialize_worker_logger(async_db_instance, sync_db_instance)

        logger.info(
            "Worker database context created successfully",
            emoji=LogEmoji.SUCCESS,
            store_in_db=False,
        )

        return logger, async_db_instance, sync_db_instance

    except Exception as e:
        # If we can't get a logger yet, print to console
        print(f"CRITICAL: Worker database context creation failed: {e}")
        raise


def close_worker_databases():
    """
    Close both database connections gracefully.

    This should be called during worker shutdown to ensure
    clean database connection closure.
    """
    try:
        # Close sync database first
        sync_db.close()

        # Note: async_db will be closed by FastAPI/async framework

    except Exception as e:
        # If logger is still available, use it; otherwise print to console
        try:
            logger = get_service_logger(LoggerName.SYSTEM)
            logger.error(f"Error closing worker databases: {e}")
        except Exception:
            print(f"Error closing worker databases: {e}")
