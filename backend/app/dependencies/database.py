# backend/app/dependencies/database.py
"""
Database dependency providers.

Simple, clean database dependency injection without the mess of the original.
"""

from ..database import async_db, sync_db
from ..database.core import AsyncDatabase, SyncDatabase


async def get_async_database() -> AsyncDatabase:
    """Get async database instance."""
    return async_db


def get_sync_database() -> SyncDatabase:
    """Get sync database instance."""
    return sync_db
