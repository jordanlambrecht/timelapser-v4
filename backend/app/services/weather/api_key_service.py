# backend/app/services/api_key_service.py
"""
Dedicated API key management service.

This service handles OpenWeather API key storage, retrieval, and security.
Completely separate from other settings to avoid confusion.
"""

from typing import Optional
from loguru import logger

from ...database.settings_operations import SettingsOperations, SyncSettingsOperations
from ...database.core import AsyncDatabase, SyncDatabase
from ...utils.hashing import hash_api_key, mask_api_key


class APIKeyService:
    """Async API key management service."""

    def __init__(self, db: AsyncDatabase):
        self.db = db
        self.settings_ops = SettingsOperations(db)

    async def store_api_key(self, api_key: str) -> bool:
        """
        Store an API key securely.

        Args:
            api_key: The plain text API key to store

        Returns:
            True if stored successfully
        """
        try:
            if not api_key or not api_key.strip():
                # Clear both keys
                await self.settings_ops.set_setting("openweather_api_key_plain", "")
                await self.settings_ops.set_setting("openweather_api_key_hash", "")
                logger.info("Cleared OpenWeather API key")
                return True

            # Store the plain key for retrieval and display
            await self.settings_ops.set_setting("openweather_api_key_plain", api_key)

            # Store the hash for future security verification
            hashed_key = hash_api_key(api_key)
            await self.settings_ops.set_setting("openweather_api_key_hash", hashed_key)

            logger.info("Stored OpenWeather API key and hash")
            return True

        except Exception as e:
            logger.error(f"Failed to store API key: {e}")
            return False

    async def get_api_key_for_display(self) -> Optional[str]:
        """
        Get the API key for frontend display.

        Returns:
            The plain text API key or None if not found
        """
        try:
            return await self.settings_ops.get_setting("openweather_api_key_plain")
        except Exception as e:
            logger.error(f"Failed to get API key for display: {e}")
            return None

    async def get_api_key_for_service(self) -> Optional[str]:
        """
        Get the API key for weather service use.

        Returns:
            The plain text API key or None if not found
        """
        try:
            return await self.settings_ops.get_setting("openweather_api_key_plain")
        except Exception as e:
            logger.error(f"Failed to get API key for service: {e}")
            return None

    async def has_api_key(self) -> bool:
        """Check if an API key is stored."""
        try:
            key = await self.settings_ops.get_setting("openweather_api_key_plain")
            return bool(key and key.strip())
        except Exception as e:
            logger.error(f"Failed to check API key existence: {e}")
            return False


class SyncAPIKeyService:
    """Sync API key management service for worker."""

    def __init__(self, db: SyncDatabase):
        self.db = db
        self.settings_ops = SyncSettingsOperations(db)

    def store_api_key(self, api_key: str) -> bool:
        """Store an API key securely (sync version)."""
        try:
            if not api_key or not api_key.strip():
                # Clear both keys
                self.settings_ops.set_setting("openweather_api_key_plain", "")
                self.settings_ops.set_setting("openweather_api_key_hash", "")
                logger.info("Cleared OpenWeather API key")
                return True

            # Store the plain key for retrieval and display
            self.settings_ops.set_setting("openweather_api_key_plain", api_key)

            # Store the hash for future security verification
            hashed_key = hash_api_key(api_key)
            self.settings_ops.set_setting("openweather_api_key_hash", hashed_key)

            logger.info("Stored OpenWeather API key and hash")
            return True

        except Exception as e:
            logger.error(f"Failed to store API key: {e}")
            return False

    def get_api_key_for_display(self) -> Optional[str]:
        """Get the API key for frontend display (sync version)."""
        try:
            return self.settings_ops.get_setting("openweather_api_key_plain")
        except Exception as e:
            logger.error(f"Failed to get API key for display: {e}")
            return None

    def get_api_key_for_service(self) -> Optional[str]:
        """Get the API key for weather service use (sync version)."""
        try:
            return self.settings_ops.get_setting("openweather_api_key_plain")
        except Exception as e:
            logger.error(f"Failed to get API key for service: {e}")
            return None

    def has_api_key(self) -> bool:
        """Check if an API key is stored (sync version)."""
        try:
            key = self.settings_ops.get_setting("openweather_api_key_plain")
            return bool(key and key.strip())
        except Exception as e:
            logger.error(f"Failed to check API key existence: {e}")
            return False
