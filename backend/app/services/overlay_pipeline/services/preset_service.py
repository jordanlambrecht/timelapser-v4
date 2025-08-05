# backend/app/services/overlay_pipeline/services/preset_service.py
"""
Overlay Preset Service - Management of system-wide overlay presets.
"""

from typing import Any, Dict, List, Optional

from ....database.core import AsyncDatabase, SyncDatabase
from ....database.overlay_operations import OverlayOperations, SyncOverlayOperations
from ....enums import LoggerName, LogSource
from ....models.overlay_model import (
    OverlayPreset,
    OverlayPresetCreate,
    OverlayPresetUpdate,
)
from ....services.logger import get_service_logger

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


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
            logger.error("Failed to get overlay presets", exception=e)
            return []

    def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID."""
        try:
            return self.overlay_ops.get_preset_by_id(preset_id)
        except Exception as e:
            logger.error(f"Failed to get overlay preset {preset_id}", exception=e)
            return None

    def get_preset_by_name(self, name: str) -> Optional[OverlayPreset]:
        """Get overlay preset by name."""
        try:
            # Sync operations don't have get_preset_by_name, need to filter from all presets
            all_presets = self.overlay_ops.get_all_presets()
            for preset in all_presets:
                if preset.name == name:
                    return preset
            return None
        except Exception as e:
            logger.error(f"Failed to get overlay preset '{name}'", exception=e)
            return None

    def create_preset(
        self, preset_data: OverlayPresetCreate
    ) -> Optional[OverlayPreset]:
        """Create a new overlay preset."""
        try:
            return self.overlay_ops.create_preset(preset_data)
        except Exception as e:
            logger.error("Failed to create overlay preset", exception=e)
            return None

    def update_preset(self, preset_id: int, updates: Dict[str, Any]) -> bool:
        """Update an existing overlay preset."""
        try:
            # Convert dict to OverlayPresetUpdate model
            preset_update = OverlayPresetUpdate(**updates)
            result = self.overlay_ops.update_preset(preset_id, preset_update)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to update overlay preset {preset_id}", exception=e)
            return False

    def delete_preset(self, preset_id: int) -> bool:
        """Delete an overlay preset."""
        try:
            return self.overlay_ops.delete_preset(preset_id)
        except Exception as e:
            logger.error(f"Failed to delete overlay preset {preset_id}", exception=e)
            return False

    def get_built_in_presets(self) -> List[OverlayPreset]:
        """Get built-in overlay presets."""
        try:
            # Get all presets and filter for built-in ones
            all_presets = self.overlay_ops.get_all_presets(include_builtin=True)
            return [p for p in all_presets if p.is_builtin]
        except Exception as e:
            logger.error("Failed to get built-in overlay presets", exception=e)
            return []

    def get_custom_presets(self) -> List[OverlayPreset]:
        """Get user-created custom overlay presets."""
        try:
            # Get all presets and filter for non-built-in ones
            all_presets = self.overlay_ops.get_all_presets(include_builtin=True)
            return [p for p in all_presets if not p.is_builtin]
        except Exception as e:
            logger.error("Failed to get custom overlay presets", exception=e)
            return []

    def duplicate_preset(
        self, preset_id: int, new_name: str
    ) -> Optional[OverlayPreset]:
        """Duplicate an existing preset with a new name."""
        try:
            # Get the original preset
            original = self.get_preset_by_id(preset_id)
            if not original:
                return None

            # Create new preset data
            preset_data = OverlayPresetCreate(
                name=new_name,
                overlay_config=original.overlay_config,
                description=f"Copy of {original.name}",
                is_builtin=False,
            )

            return self.create_preset(preset_data)
        except Exception as e:
            logger.error(f"Failed to duplicate overlay preset {preset_id}", exception=e)
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
            logger.error("Failed to get overlay presets", exception=e)
            return []

    async def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID (async)."""
        try:
            return await self.overlay_ops.get_preset_by_id(preset_id)
        except Exception as e:
            logger.error(f"Failed to get overlay preset {preset_id}", exception=e)
            return None

    async def get_preset_by_name(self, name: str) -> Optional[OverlayPreset]:
        """Get overlay preset by name (async)."""
        try:
            return await self.overlay_ops.get_preset_by_name(name)
        except Exception as e:
            logger.error(f"Failed to get overlay preset '{name}'", exception=e)
            return None

    async def create_preset(
        self, preset_data: OverlayPresetCreate
    ) -> Optional[OverlayPreset]:
        """Create a new overlay preset (async)."""
        try:
            return await self.overlay_ops.create_preset(preset_data)
        except Exception as e:
            logger.error("Failed to create overlay preset", exception=e)
            return None

    async def update_preset(self, preset_id: int, updates: Dict[str, Any]) -> bool:
        """Update an existing overlay preset (async)."""
        try:
            # Convert dict to OverlayPresetUpdate model
            preset_update = OverlayPresetUpdate(**updates)
            result = await self.overlay_ops.update_preset(preset_id, preset_update)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to update overlay preset {preset_id}", exception=e)
            return False

    async def delete_preset(self, preset_id: int) -> bool:
        """Delete an overlay preset (async)."""
        try:
            return await self.overlay_ops.delete_preset(preset_id)
        except Exception as e:
            logger.error(f"Failed to delete overlay preset {preset_id}", exception=e)
            return False

    async def get_built_in_presets(self) -> List[OverlayPreset]:
        """Get built-in overlay presets (async)."""
        try:
            # Get all presets and filter for built-in ones
            all_presets = await self.overlay_ops.get_all_presets(include_builtin=True)
            return [p for p in all_presets if p.is_builtin]
        except Exception as e:
            logger.error("Failed to get built-in overlay presets", exception=e)
            return []

    async def get_custom_presets(self) -> List[OverlayPreset]:
        """Get user-created custom overlay presets (async)."""
        try:
            # Get all presets and filter for non-built-in ones
            all_presets = await self.overlay_ops.get_all_presets(include_builtin=True)
            return [p for p in all_presets if not p.is_builtin]
        except Exception as e:
            logger.error("Failed to get custom overlay presets", exception=e)
            return []

    async def duplicate_preset(
        self, preset_id: int, new_name: str
    ) -> Optional[OverlayPreset]:
        """Duplicate an existing preset with a new name (async)."""
        try:
            # Get the original preset
            original = await self.get_preset_by_id(preset_id)
            if not original:
                return None

            # Create new preset data
            preset_data = OverlayPresetCreate(
                name=new_name,
                overlay_config=original.overlay_config,
                description=f"Copy of {original.name}",
                is_builtin=False,
            )

            return await self.create_preset(preset_data)
        except Exception as e:
            logger.error(f"Failed to duplicate overlay preset {preset_id}", exception=e)
            return None
