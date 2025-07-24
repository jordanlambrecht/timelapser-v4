# backend/app/database/overlay_operations.py
"""
Overlay Operations - Database layer for overlay preset and configuration management.

Responsibilities:
- CRUD operations for overlay_presets table
- CRUD operations for timelapse_overlays table
- CRUD operations for overlay_assets table
- Preset retrieval and filtering
- Configuration inheritance and merging
"""

from typing import List, Optional, Dict, Any
import json
from loguru import logger
import psycopg

from .core import AsyncDatabase, SyncDatabase
from ..models.overlay_model import (
    OverlayPreset,
    OverlayPresetCreate,
    OverlayPresetUpdate,
    TimelapseOverlay,
    TimelapseOverlayCreate,
    TimelapseOverlayUpdate,
    OverlayAsset,
    OverlayAssetCreate,
    OverlayConfiguration,
)


def _row_to_overlay_preset(row: Dict[str, Any]) -> OverlayPreset:
    """Convert database row to OverlayPreset model"""
    overlay_config = row["overlay_config"]
    if isinstance(overlay_config, str):
        overlay_config = json.loads(overlay_config)

    return OverlayPreset(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        overlay_config=OverlayConfiguration(**overlay_config),
        is_builtin=row["is_builtin"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_timelapse_overlay(row: Dict[str, Any]) -> TimelapseOverlay:
    """Convert database row to TimelapseOverlay model"""
    overlay_config = row["overlay_config"]
    if isinstance(overlay_config, str):
        overlay_config = json.loads(overlay_config)

    return TimelapseOverlay(
        id=row["id"],
        timelapse_id=row["timelapse_id"],
        preset_id=row["preset_id"],
        overlay_config=OverlayConfiguration(**overlay_config),
        enabled=row["enabled"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_overlay_asset(row: Dict[str, Any]) -> OverlayAsset:
    """Convert database row to OverlayAsset model"""
    return OverlayAsset(
        id=row["id"],
        filename=row["filename"],
        original_name=row["original_name"],
        file_path=row["file_path"],
        file_size=row["file_size"],
        mime_type=row["mime_type"],
        uploaded_at=row["uploaded_at"],
    )


class OverlayOperations:
    """
    Async database operations for overlay system.

    Provides CRUD operations for presets, configurations, and assets
    following the established database operations pattern.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance."""
        self.db = db

    # ================================================================
    # OVERLAY PRESETS OPERATIONS
    # ================================================================

    async def create_preset(
        self, preset_data: OverlayPresetCreate
    ) -> Optional[OverlayPreset]:
        """
        Create a new overlay preset.

        Args:
            preset_data: Preset creation data

        Returns:
            Created preset or None if creation failed
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO overlay_presets (name, description, overlay_config, is_builtin)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                        """,
                        (
                            preset_data.name,
                            preset_data.description,
                            json.dumps(preset_data.overlay_config.model_dump()),
                            preset_data.is_builtin,
                        ),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create overlay preset: {e}")
            return None

    async def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, name, description, overlay_config, is_builtin, created_at, updated_at
                        FROM overlay_presets 
                        WHERE id = %s
                        """,
                        (preset_id,),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay preset {preset_id}: {e}")
            return None

    async def get_preset_by_name(self, name: str) -> Optional[OverlayPreset]:
        """Get overlay preset by name"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, name, description, overlay_config, is_builtin, created_at, updated_at
                        FROM overlay_presets 
                        WHERE name = %s
                        """,
                        (name,),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay preset '{name}': {e}")
            return None

    async def get_all_presets(
        self, include_builtin: bool = True
    ) -> List[OverlayPreset]:
        """Get all overlay presets"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    query = """
                        SELECT id, name, description, overlay_config, is_builtin, created_at, updated_at
                        FROM overlay_presets
                    """
                    params = []

                    if not include_builtin:
                        query += " WHERE is_builtin = %s"
                        params.append(False)

                    query += " ORDER BY is_builtin DESC, name ASC"

                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    return [_row_to_overlay_preset(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay presets: {e}")
            return []

    async def update_preset(
        self, preset_id: int, preset_data: OverlayPresetUpdate
    ) -> Optional[OverlayPreset]:
        """Update overlay preset"""
        try:
            # Build dynamic update query
            update_fields = []
            params = []

            if preset_data.name is not None:
                update_fields.append("name = %s")
                params.append(preset_data.name)

            if preset_data.description is not None:
                update_fields.append("description = %s")
                params.append(preset_data.description)

            if preset_data.overlay_config is not None:
                update_fields.append("overlay_config = %s")
                params.append(json.dumps(preset_data.overlay_config.model_dump()))

            if not update_fields:
                # No fields to update, return existing preset
                return await self.get_preset_by_id(preset_id)

            update_fields.append("updated_at = NOW()")
            params.append(preset_id)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"""
                        UPDATE overlay_presets 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                        """,
                        params,
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to update overlay preset {preset_id}: {e}")
            return None

    async def delete_preset(self, preset_id: int) -> bool:
        """Delete overlay preset (only custom presets, not built-in)"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Only allow deletion of custom presets
                    await cur.execute(
                        "DELETE FROM overlay_presets WHERE id = %s AND is_builtin = FALSE",
                        (preset_id,),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete overlay preset {preset_id}: {e}")
            return False

    # ================================================================
    # TIMELAPSE OVERLAY OPERATIONS
    # ================================================================

    async def create_timelapse_overlay(
        self, overlay_data: TimelapseOverlayCreate
    ) -> Optional[TimelapseOverlay]:
        """Create timelapse overlay configuration"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO timelapse_overlays (timelapse_id, preset_id, overlay_config, enabled)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        """,
                        (
                            overlay_data.timelapse_id,
                            overlay_data.preset_id,
                            json.dumps(overlay_data.overlay_config.model_dump()),
                            overlay_data.enabled,
                        ),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create timelapse overlay: {e}")
            return None

    async def get_timelapse_overlay(
        self, timelapse_id: int
    ) -> Optional[TimelapseOverlay]:
        """Get overlay configuration for timelapse"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        FROM timelapse_overlays
                        WHERE timelapse_id = %s
                        """,
                        (timelapse_id,),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get timelapse overlay for {timelapse_id}: {e}")
            return None

    async def update_timelapse_overlay(
        self, timelapse_id: int, overlay_data: TimelapseOverlayUpdate
    ) -> Optional[TimelapseOverlay]:
        """Update timelapse overlay configuration"""
        try:
            # Build dynamic update query
            update_fields = []
            params = []

            if overlay_data.preset_id is not None:
                update_fields.append("preset_id = %s")
                params.append(overlay_data.preset_id)

            if overlay_data.overlay_config is not None:
                update_fields.append("overlay_config = %s")
                params.append(json.dumps(overlay_data.overlay_config.model_dump()))

            if overlay_data.enabled is not None:
                update_fields.append("enabled = %s")
                params.append(overlay_data.enabled)

            if not update_fields:
                # No fields to update, return existing configuration
                return await self.get_timelapse_overlay(timelapse_id)

            update_fields.append("updated_at = NOW()")
            params.append(timelapse_id)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"""
                        UPDATE timelapse_overlays 
                        SET {', '.join(update_fields)}
                        WHERE timelapse_id = %s
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        """,
                        params,
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to update timelapse overlay {timelapse_id}: {e}")
            return None

    async def create_or_update_timelapse_overlay(
        self, config_data
    ) -> Optional[TimelapseOverlay]:
        """Create or update timelapse overlay configuration (upsert operation)."""
        try:
            timelapse_id = config_data.timelapse_id

            # Check if overlay config already exists
            existing = await self.get_timelapse_overlay(timelapse_id)

            if existing:
                # Update existing configuration
                return await self.update_timelapse_overlay(
                    timelapse_id=timelapse_id, overlay_data=config_data
                )
            else:
                # Create new configuration
                return await self.create_timelapse_overlay(config_data)

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create or update timelapse overlay: {e}")
            return None

    async def delete_timelapse_overlay(self, timelapse_id: int) -> bool:
        """Delete timelapse overlay configuration"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM timelapse_overlays WHERE timelapse_id = %s",
                        (timelapse_id,),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete timelapse overlay {timelapse_id}: {e}")
            return False

    # ================================================================
    # OVERLAY ASSET OPERATIONS
    # ================================================================

    async def create_asset(
        self, asset_data: OverlayAssetCreate
    ) -> Optional[OverlayAsset]:
        """Create overlay asset record"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO overlay_assets (filename, original_name, file_path, file_size, mime_type)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        """,
                        (
                            asset_data.filename,
                            asset_data.original_name,
                            asset_data.file_path,
                            asset_data.file_size,
                            asset_data.mime_type,
                        ),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_asset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create overlay asset: {e}")
            return None

    async def get_asset_by_id(self, asset_id: int) -> Optional[OverlayAsset]:
        """Get overlay asset by ID"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        FROM overlay_assets 
                        WHERE id = %s
                        """,
                        (asset_id,),
                    )

                    row = await cur.fetchone()
                    if row:
                        return _row_to_overlay_asset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay asset {asset_id}: {e}")
            return None

    async def get_all_assets(self) -> List[OverlayAsset]:
        """Get all overlay assets"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        FROM overlay_assets
                        ORDER BY uploaded_at DESC
                        """
                    )

                    rows = await cur.fetchall()
                    return [_row_to_overlay_asset(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay assets: {e}")
            return []

    async def delete_asset(self, asset_id: int) -> bool:
        """Delete overlay asset"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM overlay_assets WHERE id = %s",
                        (asset_id,),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete overlay asset {asset_id}: {e}")
            return False


class SyncOverlayOperations:
    """
    Sync database operations for overlay system.

    Provides synchronous versions of overlay database operations
    for use in worker processes and synchronous contexts.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance."""
        self.db = db

    # ================================================================
    # OVERLAY PRESETS OPERATIONS (SYNC)
    # ================================================================

    def create_preset(
        self, preset_data: OverlayPresetCreate
    ) -> Optional[OverlayPreset]:
        """Create a new overlay preset (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO overlay_presets (name, description, overlay_config, is_builtin)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                        """,
                        (
                            preset_data.name,
                            preset_data.description,
                            json.dumps(preset_data.overlay_config.model_dump()),
                            preset_data.is_builtin,
                        ),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create overlay preset (sync): {e}")
            return None

    def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, name, description, overlay_config, is_builtin, created_at, updated_at
                        FROM overlay_presets 
                        WHERE id = %s
                        """,
                        (preset_id,),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay preset {preset_id} (sync): {e}")
            return None

    def get_timelapse_overlay(self, timelapse_id: int) -> Optional[TimelapseOverlay]:
        """Get overlay configuration for timelapse (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        FROM timelapse_overlays
                        WHERE timelapse_id = %s
                        """,
                        (timelapse_id,),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to get timelapse overlay for {timelapse_id} (sync): {e}"
            )
            return None

    def get_all_presets(self, include_builtin: bool = True) -> List[OverlayPreset]:
        """Get all overlay presets (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT id, name, description, overlay_config, is_builtin, created_at, updated_at
                        FROM overlay_presets
                    """
                    params = []

                    if not include_builtin:
                        query += " WHERE is_builtin = %s"
                        params.append(False)

                    query += " ORDER BY is_builtin DESC, name ASC"

                    cur.execute(query, params)
                    rows = cur.fetchall()

                    return [_row_to_overlay_preset(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay presets (sync): {e}")
            return []

    def update_preset(
        self, preset_id: int, preset_data: OverlayPresetUpdate
    ) -> Optional[OverlayPreset]:
        """Update overlay preset (sync)"""
        try:
            # Build dynamic update query
            update_fields = []
            params = []

            if preset_data.name is not None:
                update_fields.append("name = %s")
                params.append(preset_data.name)

            if preset_data.description is not None:
                update_fields.append("description = %s")
                params.append(preset_data.description)

            if preset_data.overlay_config is not None:
                update_fields.append("overlay_config = %s")
                params.append(json.dumps(preset_data.overlay_config.model_dump()))

            if not update_fields:
                # No fields to update, return existing preset
                return self.get_preset_by_id(preset_id)

            update_fields.append("updated_at = NOW()")
            params.append(preset_id)

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE overlay_presets 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                        """,
                        params,
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_preset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to update overlay preset {preset_id} (sync): {e}")
            return None

    def delete_preset(self, preset_id: int) -> bool:
        """Delete overlay preset (only custom presets, not built-in) (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Only allow deletion of custom presets
                    cur.execute(
                        "DELETE FROM overlay_presets WHERE id = %s AND is_builtin = FALSE",
                        (preset_id,),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete overlay preset {preset_id} (sync): {e}")
            return False

    def create_timelapse_overlay(
        self, overlay_data: TimelapseOverlayCreate
    ) -> Optional[TimelapseOverlay]:
        """Create timelapse overlay configuration (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO timelapse_overlays (timelapse_id, preset_id, overlay_config, enabled)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        """,
                        (
                            overlay_data.timelapse_id,
                            overlay_data.preset_id,
                            json.dumps(overlay_data.overlay_config.model_dump()),
                            overlay_data.enabled,
                        ),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create timelapse overlay (sync): {e}")
            return None

    def update_timelapse_overlay(
        self, timelapse_id: int, overlay_data: TimelapseOverlayUpdate
    ) -> Optional[TimelapseOverlay]:
        """Update timelapse overlay configuration (sync)"""
        try:
            # Build dynamic update query
            update_fields = []
            params = []

            if overlay_data.preset_id is not None:
                update_fields.append("preset_id = %s")
                params.append(overlay_data.preset_id)

            if overlay_data.overlay_config is not None:
                update_fields.append("overlay_config = %s")
                params.append(json.dumps(overlay_data.overlay_config.model_dump()))

            if overlay_data.enabled is not None:
                update_fields.append("enabled = %s")
                params.append(overlay_data.enabled)

            if not update_fields:
                # No fields to update, return existing configuration
                return self.get_timelapse_overlay(timelapse_id)

            update_fields.append("updated_at = NOW()")
            params.append(timelapse_id)

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE timelapse_overlays
                        SET {', '.join(update_fields)}
                        WHERE timelapse_id = %s
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        """,
                        params,
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to update timelapse overlay {timelapse_id} (sync): {e}"
            )
            return None

    def create_or_update_timelapse_overlay(
        self, config_data
    ) -> Optional[TimelapseOverlay]:
        """Create or update timelapse overlay configuration (upsert operation) (sync)."""
        try:
            timelapse_id = config_data.timelapse_id

            # Check if overlay config already exists
            existing = self.get_timelapse_overlay(timelapse_id)

            if existing:
                # Update existing configuration
                return self.update_timelapse_overlay(
                    timelapse_id=timelapse_id, overlay_data=config_data
                )
            else:
                # Create new configuration
                return self.create_timelapse_overlay(config_data)

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create or update timelapse overlay (sync): {e}")
            return None

    def delete_timelapse_overlay(self, timelapse_id: int) -> bool:
        """Delete timelapse overlay configuration (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM timelapse_overlays WHERE timelapse_id = %s",
                        (timelapse_id,),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to delete timelapse overlay {timelapse_id} (sync): {e}"
            )
            return False

    def create_asset(self, asset_data: OverlayAssetCreate) -> Optional[OverlayAsset]:
        """Create overlay asset record (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO overlay_assets (filename, original_name, file_path, file_size, mime_type)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        """,
                        (
                            asset_data.filename,
                            asset_data.original_name,
                            asset_data.file_path,
                            asset_data.file_size,
                            asset_data.mime_type,
                        ),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_asset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create overlay asset (sync): {e}")
            return None

    def get_asset_by_id(self, asset_id: int) -> Optional[OverlayAsset]:
        """Get overlay asset by ID (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        FROM overlay_assets 
                        WHERE id = %s
                        """,
                        (asset_id,),
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_overlay_asset(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay asset {asset_id} (sync): {e}")
            return None

    def get_all_assets(self) -> List[OverlayAsset]:
        """Get all overlay assets (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        FROM overlay_assets
                        ORDER BY uploaded_at DESC
                        """
                    )

                    rows = cur.fetchall()
                    return [_row_to_overlay_asset(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay assets (sync): {e}")
            return []

    def delete_asset(self, asset_id: int) -> bool:
        """Delete overlay asset (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM overlay_assets WHERE id = %s",
                        (asset_id,),
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete overlay asset {asset_id} (sync): {e}")
            return False
