"""
Database package for Timelapser v4

This package provides composition-based database operations for clean
architecture and type safety.

Usage:
    from app.database import async_db, sync_db
    from app.services.camera_service import CameraService
    from app.services.settings_service import SettingsService

    # Initialize services with proper dependency injection
    settings_service = SettingsService(async_db)
    camera_service = CameraService(async_db, settings_service)
"""

# Composition-based database classes
from .core import AsyncDatabase, SyncDatabase

# Create shared database instances
async_db = AsyncDatabase()
sync_db = SyncDatabase()

__all__ = ["AsyncDatabase", "SyncDatabase", "async_db", "sync_db"]
