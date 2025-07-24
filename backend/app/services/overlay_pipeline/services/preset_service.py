# backend/app/services/overlay_pipeline/services/preset_service.py
"""
Overlay Preset Service - Management of system-wide overlay presets.
"""

from typing import List, Optional, Dict, Any
from loguru import logger

from ....database.core import SyncDatabase, AsyncDatabase
from ....database.overlay_operations import SyncOverlayOperations, OverlayOperations
from ....models.overlay_model import OverlayPreset, OverlayPresetCreate


class SyncOverlayPresetService:
    """
    Synchronous service for overlay preset management.
    Handles system-wide overlay presets for worker processes.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database."""
        self.db = db
        self.overlay_ops = SyncOverlayOperations(db)

    def get_all_presets(self) -> List[OverlayPreset]:
        """Get all available overlay presets."""
        try:
            return self.overlay_ops.get_all_presets()
        except Exception as e:
            logger.error(f"Failed to get overlay presets: {e}")
            return []

    def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID."""
        try:
            return self.overlay_ops.get_preset_by_id(preset_id)
        except Exception as e:
            logger.error(f"Failed to get overlay preset {preset_id}: {e}")
            return None

    def get_preset_by_name(self, name: str) -> Optional[OverlayPreset]:
        """Get overlay preset by name."""
        try:
            return self.overlay_ops.get_preset_by_name(name)
        except Exception as e:
            logger.error(f"Failed to get overlay preset '{name}': {e}")
            return None

    def create_preset(self, preset_data: OverlayPresetCreate) -> Optional[OverlayPreset]:
        """Create a new overlay preset."""
        try:
            return self.overlay_ops.create_preset(preset_data)
        except Exception as e:
            logger.error(f"Failed to create overlay preset: {e}")
            return None

    def update_preset(self, preset_id: int, updates: Dict[str, Any]) -> bool:
        """Update an existing overlay preset."""
        try:
            return self.overlay_ops.update_preset(preset_id, updates)
        except Exception as e:
            logger.error(f"Failed to update overlay preset {preset_id}: {e}")
            return False

    def delete_preset(self, preset_id: int) -> bool:
        """Delete an overlay preset."""
        try:
            return self.overlay_ops.delete_preset(preset_id)
        except Exception as e:
            logger.error(f"Failed to delete overlay preset {preset_id}: {e}")
            return False

    def get_built_in_presets(self) -> List[OverlayPreset]:
        """Get built-in overlay presets."""
        try:
            return self.overlay_ops.get_built_in_presets()
        except Exception as e:
            logger.error(f"Failed to get built-in overlay presets: {e}")
            return []

    def get_custom_presets(self) -> List[OverlayPreset]:
        """Get user-created custom overlay presets."""
        try:
            return self.overlay_ops.get_custom_presets()
        except Exception as e:
            logger.error(f"Failed to get custom overlay presets: {e}")
            return []

    def duplicate_preset(self, preset_id: int, new_name: str) -> Optional[OverlayPreset]:
        """Duplicate an existing preset with a new name."""
        try:
            # Get the original preset
            original = self.get_preset_by_id(preset_id)
            if not original:
                return None

            # Create new preset data
            preset_data = OverlayPresetCreate(
                name=new_name,
                configuration=original.configuration,
                description=f"Copy of {original.name}",
                is_built_in=False
            )

            return self.create_preset(preset_data)
        except Exception as e:
            logger.error(f"Failed to duplicate overlay preset {preset_id}: {e}")
            return None


class OverlayPresetService:
    """
    Asynchronous service for overlay preset management.
    Provides async versions for use in API endpoints.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database."""
        self.db = db
        self.overlay_ops = OverlayOperations(db)

    async def get_all_presets(self) -> List[OverlayPreset]:
        """Get all available overlay presets (async)."""
        try:
            return await self.overlay_ops.get_all_presets()
        except Exception as e:
            logger.error(f"Failed to get overlay presets: {e}")
            return []

    async def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID (async)."""
        try:
            return await self.overlay_ops.get_preset_by_id(preset_id)
        except Exception as e:
            logger.error(f"Failed to get overlay preset {preset_id}: {e}")
            return None

    async def get_preset_by_name(self, name: str) -> Optional[OverlayPreset]:
        """Get overlay preset by name (async)."""
        try:
            return await self.overlay_ops.get_preset_by_name(name)
        except Exception as e:
            logger.error(f"Failed to get overlay preset '{name}': {e}")
            return None

    async def create_preset(self, preset_data: OverlayPresetCreate) -> Optional[OverlayPreset]:
        """Create a new overlay preset (async)."""
        try:
            return await self.overlay_ops.create_preset(preset_data)
        except Exception as e:
            logger.error(f"Failed to create overlay preset: {e}")
            return None

    async def update_preset(self, preset_id: int, updates: Dict[str, Any]) -> bool:
        """Update an existing overlay preset (async)."""
        try:
            return await self.overlay_ops.update_preset(preset_id, updates)
        except Exception as e:
            logger.error(f"Failed to update overlay preset {preset_id}: {e}")
            return False

    async def delete_preset(self, preset_id: int) -> bool:
        """Delete an overlay preset (async)."""
        try:
            return await self.overlay_ops.delete_preset(preset_id)
        except Exception as e:
            logger.error(f"Failed to delete overlay preset {preset_id}: {e}")
            return False

    async def get_built_in_presets(self) -> List[OverlayPreset]:
        """Get built-in overlay presets (async)."""
        try:
            return await self.overlay_ops.get_built_in_presets()
        except Exception as e:
            logger.error(f"Failed to get built-in overlay presets: {e}")
            return []

    async def get_custom_presets(self) -> List[OverlayPreset]:
        """Get user-created custom overlay presets (async)."""
        try:
            return await self.overlay_ops.get_custom_presets()
        except Exception as e:
            logger.error(f"Failed to get custom overlay presets: {e}")
            return []

    async def duplicate_preset(self, preset_id: int, new_name: str) -> Optional[OverlayPreset]:
        """Duplicate an existing preset with a new name (async)."""
        try:
            # Get the original preset
            original = await self.get_preset_by_id(preset_id)
            if not original:
                return None

            # Create new preset data
            preset_data = OverlayPresetCreate(
                name=new_name,
                configuration=original.configuration,
                description=f"Copy of {original.name}",
                is_built_in=False
            )

            return await self.create_preset(preset_data)
        except Exception as e:
            logger.error(f"Failed to duplicate overlay preset {preset_id}: {e}")
            return None