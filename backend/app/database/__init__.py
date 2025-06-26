"""
Database package for Timelapser v4

This package provides composition-based database operations for clean
architecture and type safety.

Usage:
    from app.database import async_db, sync_db
    from app.services.camera_service import CameraService

    # Initialize services
    camera_service = CameraService(async_db)
"""

# Composition-based database classes
from .core import AsyncDatabase, SyncDatabase

# Create shared database instances
async_db = AsyncDatabase()
sync_db = SyncDatabase()

__all__ = ["AsyncDatabase", "SyncDatabase", "async_db", "sync_db"]
