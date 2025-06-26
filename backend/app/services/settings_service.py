# backend/app/services/settings_service.py
"""
Settings service layer for business logic orchestration.

This service provides a clean interface for settings operations,
handling business logic and coordinating between database operations
and external systems.
"""

from typing import List, Dict, Optional, Any, Tuple
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.settings_operations import SettingsOperations, SyncSettingsOperations
from ..models.settings_model import Setting
from ..models.shared_models import CorruptionSettings


class SettingsService:
    """Async settings service for handling business logic."""

    def __init__(self, db: AsyncDatabase):
        """Initialize service with async database instance."""
        self.db = db
        self.settings_ops = SettingsOperations(db)

    async def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            return await self.settings_ops.get_all_settings()
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            raise

    async def get_setting(self, key: str) -> Optional[str]:
        """Get specific setting by key."""
        try:
            return await self.settings_ops.get_setting(key)
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            raise

    async def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        try:
            return await self.settings_ops.set_setting(key, value)
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise

    async def set_multiple_settings(self, settings_dict: Dict[str, str]) -> bool:
        """Set multiple settings in a single transaction."""
        try:
            return await self.settings_ops.set_multiple_settings(settings_dict)
        except Exception as e:
            logger.error(f"Failed to set multiple settings: {e}")
            raise

    async def delete_setting(self, key: str) -> bool:
        """Delete a setting by key."""
        try:
            return await self.settings_ops.delete_setting(key)
        except Exception as e:
            logger.error(f"Failed to delete setting {key}: {e}")
            raise

    async def get_corruption_settings(self) -> CorruptionSettings:
        """Get corruption detection related settings."""
        try:
            return await self.settings_ops.get_corruption_settings()
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            raise

    async def get_settings(self) -> List[Setting]:
        """Get all settings as a list of Setting model instances."""
        try:
            return await self.settings_ops.get_settings()
        except Exception as e:
            logger.error(f"Failed to get settings list: {e}")
            raise

    async def get_settings_dict(self) -> Dict[str, Any]:
        """Get all settings as a dictionary (backward compatibility)."""
        try:
            return await self.settings_ops.get_settings_dict()
        except Exception as e:
            logger.error(f"Failed to get settings dict: {e}")
            raise


class SyncSettingsService:
    """Sync settings service for worker processes."""

    def __init__(self, db: SyncDatabase):
        """Initialize service with sync database instance."""
        self.db = db
        self.settings_ops = SyncSettingsOperations(db)

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            return self.settings_ops.get_all_settings()
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            raise

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get specific setting by key."""
        try:
            return self.settings_ops.get_setting(key, default)
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            raise

    def get_capture_interval_setting(self) -> int:
        """Get capture interval setting as integer."""
        try:
            return self.settings_ops.get_capture_interval_setting()
        except Exception as e:
            logger.error(f"Failed to get capture interval setting: {e}")
            raise

    def get_corruption_settings(self) -> CorruptionSettings:
        """Get corruption detection related settings."""
        try:
            return self.settings_ops.get_corruption_settings()
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            raise

    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        try:
            return self.settings_ops.set_setting(key, value)
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise
