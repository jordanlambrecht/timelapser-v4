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
from datetime import datetime
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
from ..utils.time_utils import utc_now
from ..utils.cache_manager import (
    cache,
    cached_response,
    generate_timestamp_etag,
    generate_composite_etag,
    generate_collection_etag,
)
from ..utils.cache_invalidation import CacheInvalidationService


class OverlayQueryBuilder:
    """Centralized query builder for overlay operations.
    
    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_overlay_presets_name ON overlay_presets(name);
    - CREATE INDEX idx_overlay_presets_builtin ON overlay_presets(is_builtin, name);
    - CREATE UNIQUE INDEX idx_overlay_presets_name_unique ON overlay_presets(name) WHERE is_builtin = false;
    - CREATE INDEX idx_timelapse_overlays_timelapse ON timelapse_overlays(timelapse_id);
    - CREATE INDEX idx_timelapse_overlays_preset ON timelapse_overlays(preset_id);
    - CREATE INDEX idx_timelapse_overlays_enabled ON timelapse_overlays(enabled) WHERE enabled = true;
    - CREATE INDEX idx_overlay_assets_filename ON overlay_assets(filename);
    - CREATE INDEX idx_overlay_assets_uploaded ON overlay_assets(uploaded_at DESC);
    - CREATE INDEX idx_overlay_assets_mime_type ON overlay_assets(mime_type);
    """

    @staticmethod
    def get_preset_fields():
        """Get standard fields for overlay preset queries."""
        return (
            "id, name, description, overlay_config, is_builtin, created_at, updated_at"
        )

    @staticmethod
    def get_timelapse_overlay_fields():
        """Get standard fields for timelapse overlay queries."""
        return "id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at"

    @staticmethod
    def get_asset_fields():
        """Get standard fields for overlay asset queries."""
        return (
            "id, filename, original_name, file_path, file_size, mime_type, uploaded_at"
        )

    @staticmethod
    def build_preset_query_by_id():
        """Build query to get preset by ID using named parameters."""
        fields = OverlayQueryBuilder.get_preset_fields()
        return f"""
            SELECT {fields}
            FROM overlay_presets
            WHERE id = %(preset_id)s
        """

    @staticmethod
    def build_preset_query_by_name():
        """Build query to get preset by name using named parameters."""
        fields = OverlayQueryBuilder.get_preset_fields()
        return f"""
            SELECT {fields}
            FROM overlay_presets
            WHERE name = %(name)s
        """

    @staticmethod
    def build_all_presets_query(include_builtin: bool = True):
        """Build query to get all presets with optional builtin filter using named parameters."""
        fields = OverlayQueryBuilder.get_preset_fields()
        query = f"""
            SELECT {fields}
            FROM overlay_presets
        """

        if not include_builtin:
            query += " WHERE is_builtin = %(is_builtin)s"

        query += " ORDER BY is_builtin DESC, name ASC"
        return query

    @staticmethod
    def build_timelapse_overlay_query():
        """Build query to get timelapse overlay configuration using named parameters."""
        fields = OverlayQueryBuilder.get_timelapse_overlay_fields()
        return f"""
            SELECT {fields}
            FROM timelapse_overlays
            WHERE timelapse_id = %(timelapse_id)s
        """

    @staticmethod
    def build_upsert_timelapse_overlay_query():
        """Build upsert query for timelapse overlay using ON CONFLICT with named parameters."""
        fields = OverlayQueryBuilder.get_timelapse_overlay_fields()
        return f"""
            INSERT INTO timelapse_overlays (timelapse_id, preset_id, overlay_config, enabled)
            VALUES (%(timelapse_id)s, %(preset_id)s, %(overlay_config)s, %(enabled)s)
            ON CONFLICT (timelapse_id)
            DO UPDATE SET
                preset_id = EXCLUDED.preset_id,
                overlay_config = EXCLUDED.overlay_config,
                enabled = EXCLUDED.enabled,
                updated_at = %(updated_at)s
            RETURNING {fields}
        """

    @staticmethod
    def build_asset_query_by_id():
        """Build query to get asset by ID using named parameters."""
        fields = OverlayQueryBuilder.get_asset_fields()
        return f"""
            SELECT {fields}
            FROM overlay_assets
            WHERE id = %(asset_id)s
        """

    @staticmethod
    def build_all_assets_query():
        """Build query to get all assets."""
        fields = OverlayQueryBuilder.get_asset_fields()
        return f"""
            SELECT {fields}
            FROM overlay_assets
            ORDER BY uploaded_at DESC
        """


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

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_overlay_caches(
        self,
        preset_id: Optional[int] = None,
        timelapse_id: Optional[int] = None,
        asset_id: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Clear caches related to overlay operations using sophisticated cache system."""
        # Clear overlay-related caches using advanced cache manager
        cache_patterns = [
            "overlay:get_all_presets",
            "overlay:preset_by_id",
            "overlay:preset_by_name",
            "overlay:timelapse_overlay",
            "overlay:get_all_assets",
            "overlay:asset_by_id",
        ]

        if preset_id:
            cache_patterns.extend(
                [f"overlay:preset_by_id:{preset_id}", f"overlay:metadata:{preset_id}"]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(preset_id, updated_at)
                await self.cache_invalidation.invalidate_with_etag_validation(
                    f"overlay:metadata:{preset_id}", etag
                )

        if timelapse_id:
            cache_patterns.append(f"overlay:timelapse_overlay:{timelapse_id}")

        if asset_id:
            cache_patterns.append(f"overlay:asset_by_id:{asset_id}")

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

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
                        VALUES (%(name)s, %(description)s, %(overlay_config)s, %(is_builtin)s)
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                        """,
                        {
                            "name": preset_data.name,
                            "description": preset_data.description,
                            "overlay_config": json.dumps(preset_data.overlay_config.model_dump()),
                            "is_builtin": preset_data.is_builtin,
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        preset = _row_to_overlay_preset(dict(row))
                        # Clear related caches after successful creation
                        await self._clear_overlay_caches(
                            preset_id=preset.id, updated_at=utc_now()
                        )
                        return preset
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create overlay preset: {e}")
            return None

    @cached_response(ttl_seconds=300, key_prefix="overlay")
    async def get_preset_by_id(self, preset_id: int) -> Optional[OverlayPreset]:
        """Get overlay preset by ID with 5-minute caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayQueryBuilder.build_preset_query_by_id()
                    await cur.execute(query, {"preset_id": preset_id})

                    row = await cur.fetchone()
                    if row:
                        preset = _row_to_overlay_preset(dict(row))
                        return preset
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay preset {preset_id}: {e}")
            return None

    @cached_response(ttl_seconds=300, key_prefix="overlay")
    async def get_preset_by_name(self, name: str) -> Optional[OverlayPreset]:
        """Get overlay preset by name with 5-minute caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayQueryBuilder.build_preset_query_by_name()
                    await cur.execute(query, {"name": name})

                    row = await cur.fetchone()
                    if row:
                        preset = _row_to_overlay_preset(dict(row))
                        return preset
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay preset '{name}': {e}")
            return None

    @cached_response(ttl_seconds=120, key_prefix="overlay")
    async def get_all_presets(
        self, include_builtin: bool = True
    ) -> List[OverlayPreset]:
        """Get all overlay presets with 2-minute caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayQueryBuilder.build_all_presets_query(include_builtin)
                    params = {} if include_builtin else {"is_builtin": False}

                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    presets = [_row_to_overlay_preset(dict(row)) for row in rows]
                    return presets

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay presets: {e}")
            return []

    async def update_preset(
        self, preset_id: int, preset_data: OverlayPresetUpdate
    ) -> Optional[OverlayPreset]:
        """Update overlay preset"""
        try:
            # Build dynamic update query safely with named parameters
            update_fields = []
            params = {"preset_id": preset_id, "updated_at": utc_now()}

            if preset_data.name is not None:
                update_fields.append("name = %(name)s")
                params["name"] = preset_data.name

            if preset_data.description is not None:
                update_fields.append("description = %(description)s")
                params["description"] = preset_data.description

            if preset_data.overlay_config is not None:
                update_fields.append("overlay_config = %(overlay_config)s")
                params["overlay_config"] = json.dumps(preset_data.overlay_config.model_dump())

            if not update_fields:
                # No fields to update, return existing preset
                return await self.get_preset_by_id(preset_id)

            update_fields.append("updated_at = %(updated_at)s")

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Safe query construction - join is not user input
                    query = f"""
                        UPDATE overlay_presets
                        SET {', '.join(update_fields)}
                        WHERE id = %(preset_id)s
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                    """
                    await cur.execute(query, params)

                    row = await cur.fetchone()
                    if row:
                        preset = _row_to_overlay_preset(dict(row))
                        # Clear related caches after successful update
                        await self._clear_overlay_caches(
                            preset_id=preset.id, updated_at=utc_now()
                        )
                        return preset
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to update overlay preset {preset_id}: {e}")
            return None

    async def delete_preset(self, preset_id: int) -> bool:
        """Delete overlay preset (only custom presets, not built-in)"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Only allow deletion of custom presets using named parameters
                    await cur.execute(
                        "DELETE FROM overlay_presets WHERE id = %(preset_id)s AND is_builtin = FALSE",
                        {"preset_id": preset_id},
                    )

                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful deletion
                        await self._clear_overlay_caches(preset_id=preset_id)

                    return success

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
                        VALUES (%(timelapse_id)s, %(preset_id)s, %(overlay_config)s, %(enabled)s)
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        """,
                        {
                            "timelapse_id": overlay_data.timelapse_id,
                            "preset_id": overlay_data.preset_id,
                            "overlay_config": json.dumps(overlay_data.overlay_config.model_dump()),
                            "enabled": overlay_data.enabled,
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        overlay = _row_to_timelapse_overlay(dict(row))
                        # Clear related caches after successful creation
                        await self._clear_overlay_caches(
                            timelapse_id=overlay.timelapse_id, updated_at=utc_now()
                        )
                        return overlay
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create timelapse overlay: {e}")
            return None

    @cached_response(ttl_seconds=60, key_prefix="overlay")
    async def get_timelapse_overlay(
        self, timelapse_id: int
    ) -> Optional[TimelapseOverlay]:
        """Get overlay configuration for timelapse with 60s caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayQueryBuilder.build_timelapse_overlay_query()
                    await cur.execute(query, {"timelapse_id": timelapse_id})

                    row = await cur.fetchone()
                    if row:
                        overlay = _row_to_timelapse_overlay(dict(row))
                        return overlay
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get timelapse overlay for {timelapse_id}: {e}")
            return None

    async def update_timelapse_overlay(
        self, timelapse_id: int, overlay_data: TimelapseOverlayUpdate
    ) -> Optional[TimelapseOverlay]:
        """Update timelapse overlay configuration"""
        try:
            # Build dynamic update query safely with named parameters
            update_fields = []
            params = {"timelapse_id": timelapse_id, "updated_at": utc_now()}

            if overlay_data.preset_id is not None:
                update_fields.append("preset_id = %(preset_id)s")
                params["preset_id"] = overlay_data.preset_id

            if overlay_data.overlay_config is not None:
                update_fields.append("overlay_config = %(overlay_config)s")
                params["overlay_config"] = json.dumps(overlay_data.overlay_config.model_dump())

            if overlay_data.enabled is not None:
                update_fields.append("enabled = %(enabled)s")
                params["enabled"] = overlay_data.enabled

            if not update_fields:
                # No fields to update, return existing configuration
                return await self.get_timelapse_overlay(timelapse_id)

            update_fields.append("updated_at = %(updated_at)s")

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Safe query construction - join is not user input
                    query = f"""
                        UPDATE timelapse_overlays 
                        SET {', '.join(update_fields)}
                        WHERE timelapse_id = %(timelapse_id)s
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                    """
                    await cur.execute(query, params)

                    row = await cur.fetchone()
                    if row:
                        overlay = _row_to_timelapse_overlay(dict(row))
                        # Clear related caches after successful update
                        await self._clear_overlay_caches(
                            timelapse_id=overlay.timelapse_id, updated_at=utc_now()
                        )
                        return overlay
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to update timelapse overlay {timelapse_id}: {e}")
            return None

    async def create_or_update_timelapse_overlay(
        self, config_data
    ) -> Optional[TimelapseOverlay]:
        """Create or update timelapse overlay configuration (efficient upsert operation)."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized UPSERT query with ON CONFLICT using named parameters
                    query = OverlayQueryBuilder.build_upsert_timelapse_overlay_query()
                    await cur.execute(
                        query,
                        {
                            "timelapse_id": config_data.timelapse_id,
                            "preset_id": config_data.preset_id,
                            "overlay_config": json.dumps(config_data.overlay_config.model_dump()),
                            "enabled": config_data.enabled,
                            "updated_at": utc_now(),
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        overlay = _row_to_timelapse_overlay(dict(row))
                        # Clear related caches after successful upsert
                        await self._clear_overlay_caches(
                            timelapse_id=overlay.timelapse_id, updated_at=utc_now()
                        )
                        return overlay
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create or update timelapse overlay: {e}")
            return None

    async def delete_timelapse_overlay(self, timelapse_id: int) -> bool:
        """Delete timelapse overlay configuration"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM timelapse_overlays WHERE timelapse_id = %(timelapse_id)s",
                        {"timelapse_id": timelapse_id},
                    )

                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful deletion
                        await self._clear_overlay_caches(timelapse_id=timelapse_id)

                    return success

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
                        VALUES (%(filename)s, %(original_name)s, %(file_path)s, %(file_size)s, %(mime_type)s)
                        RETURNING id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        """,
                        {
                            "filename": asset_data.filename,
                            "original_name": asset_data.original_name,
                            "file_path": asset_data.file_path,
                            "file_size": asset_data.file_size,
                            "mime_type": asset_data.mime_type,
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        asset = _row_to_overlay_asset(dict(row))
                        # Clear related caches after successful creation
                        await self._clear_overlay_caches(
                            asset_id=asset.id, updated_at=utc_now()
                        )
                        return asset
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create overlay asset: {e}")
            return None

    @cached_response(ttl_seconds=600, key_prefix="overlay")
    async def get_asset_by_id(self, asset_id: int) -> Optional[OverlayAsset]:
        """Get overlay asset by ID with 10-minute caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder with named parameters
                    query = OverlayQueryBuilder.build_asset_query_by_id()
                    await cur.execute(query, {"asset_id": asset_id})

                    row = await cur.fetchone()
                    if row:
                        asset = _row_to_overlay_asset(dict(row))
                        return asset
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay asset {asset_id}: {e}")
            return None

    @cached_response(ttl_seconds=180, key_prefix="overlay")
    async def get_all_assets(self) -> List[OverlayAsset]:
        """Get all overlay assets with 3-minute caching."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use optimized query builder
                    query = OverlayQueryBuilder.build_all_assets_query()
                    await cur.execute(query)

                    rows = await cur.fetchall()
                    assets = [_row_to_overlay_asset(dict(row)) for row in rows]
                    return assets

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get overlay assets: {e}")
            return []

    async def delete_asset(self, asset_id: int) -> bool:
        """Delete overlay asset"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM overlay_assets WHERE id = %(asset_id)s",
                        {"asset_id": asset_id},
                    )

                    success = cur.rowcount > 0
                    if success:
                        # Clear related caches after successful deletion
                        await self._clear_overlay_caches(asset_id=asset_id)

                    return success

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete overlay asset {asset_id}: {e}")
            return False


class SyncOverlayOperations:
    """
    Sync database operations for overlay system.

    Provides synchronous versions of overlay database operations
    for use in worker processes and synchronous contexts.
    """

    def __init__(self, db: SyncDatabase) -> None:
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
                        VALUES (%(name)s, %(description)s, %(overlay_config)s, %(is_builtin)s)
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                        """,
                        {
                            "name": preset_data.name,
                            "description": preset_data.description,
                            "overlay_config": json.dumps(preset_data.overlay_config.model_dump()),
                            "is_builtin": preset_data.is_builtin,
                        },
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
                    # Use centralized query builder with named parameters
                    query = OverlayQueryBuilder.build_preset_query_by_id()
                    cur.execute(query, {"preset_id": preset_id})

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
                    # Use centralized query builder with named parameters
                    query = OverlayQueryBuilder.build_timelapse_overlay_query()
                    cur.execute(query, {"timelapse_id": timelapse_id})

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
                    # Use centralized query builder with named parameters
                    query = OverlayQueryBuilder.build_all_presets_query(include_builtin)
                    params = {} if include_builtin else {"is_builtin": False}
                    
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
            # Build dynamic update query safely with named parameters
            update_fields = []
            params = {"preset_id": preset_id, "updated_at": utc_now()}

            if preset_data.name is not None:
                update_fields.append("name = %(name)s")
                params["name"] = preset_data.name

            if preset_data.description is not None:
                update_fields.append("description = %(description)s")
                params["description"] = preset_data.description

            if preset_data.overlay_config is not None:
                update_fields.append("overlay_config = %(overlay_config)s")
                params["overlay_config"] = json.dumps(preset_data.overlay_config.model_dump())

            if not update_fields:
                # No fields to update, return existing preset
                return self.get_preset_by_id(preset_id)

            update_fields.append("updated_at = %(updated_at)s")

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Safe query construction - join is not user input
                    query = f"""
                        UPDATE overlay_presets
                        SET {', '.join(update_fields)}
                        WHERE id = %(preset_id)s
                        RETURNING id, name, description, overlay_config, is_builtin, created_at, updated_at
                    """
                    cur.execute(query, params)

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
                    # Only allow deletion of custom presets using named parameters
                    cur.execute(
                        "DELETE FROM overlay_presets WHERE id = %(preset_id)s AND is_builtin = FALSE",
                        {"preset_id": preset_id},
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
                        VALUES (%(timelapse_id)s, %(preset_id)s, %(overlay_config)s, %(enabled)s)
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                        """,
                        {
                            "timelapse_id": overlay_data.timelapse_id,
                            "preset_id": overlay_data.preset_id,
                            "overlay_config": json.dumps(overlay_data.overlay_config.model_dump()),
                            "enabled": overlay_data.enabled,
                        },
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
            # Build dynamic update query safely with named parameters
            update_fields = []
            params = {"timelapse_id": timelapse_id, "updated_at": utc_now()}

            if overlay_data.preset_id is not None:
                update_fields.append("preset_id = %(preset_id)s")
                params["preset_id"] = overlay_data.preset_id

            if overlay_data.overlay_config is not None:
                update_fields.append("overlay_config = %(overlay_config)s")
                params["overlay_config"] = json.dumps(overlay_data.overlay_config.model_dump())

            if overlay_data.enabled is not None:
                update_fields.append("enabled = %(enabled)s")
                params["enabled"] = overlay_data.enabled

            if not update_fields:
                # No fields to update, return existing configuration
                return self.get_timelapse_overlay(timelapse_id)

            update_fields.append("updated_at = %(updated_at)s")

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Safe query construction - join is not user input
                    query = f"""
                        UPDATE timelapse_overlays
                        SET {', '.join(update_fields)}
                        WHERE timelapse_id = %(timelapse_id)s
                        RETURNING id, timelapse_id, preset_id, overlay_config, enabled, created_at, updated_at
                    """
                    cur.execute(query, params)

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
        """Create or update timelapse overlay configuration (efficient upsert operation) (sync)."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use optimized UPSERT query with ON CONFLICT using named parameters
                    query = OverlayQueryBuilder.build_upsert_timelapse_overlay_query()
                    cur.execute(
                        query,
                        {
                            "timelapse_id": config_data.timelapse_id,
                            "preset_id": config_data.preset_id,
                            "overlay_config": json.dumps(config_data.overlay_config.model_dump()),
                            "enabled": config_data.enabled,
                            "updated_at": utc_now(),
                        },
                    )

                    row = cur.fetchone()
                    if row:
                        return _row_to_timelapse_overlay(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create or update timelapse overlay (sync): {e}")
            return None

    def delete_timelapse_overlay(self, timelapse_id: int) -> bool:
        """Delete timelapse overlay configuration (sync)"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM timelapse_overlays WHERE timelapse_id = %(timelapse_id)s",
                        {"timelapse_id": timelapse_id},
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
                        VALUES (%(filename)s, %(original_name)s, %(file_path)s, %(file_size)s, %(mime_type)s)
                        RETURNING id, filename, original_name, file_path, file_size, mime_type, uploaded_at
                        """,
                        {
                            "filename": asset_data.filename,
                            "original_name": asset_data.original_name,
                            "file_path": asset_data.file_path,
                            "file_size": asset_data.file_size,
                            "mime_type": asset_data.mime_type,
                        },
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
                    # Use centralized query builder with named parameters
                    query = OverlayQueryBuilder.build_asset_query_by_id()
                    cur.execute(query, {"asset_id": asset_id})

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
                    # Use centralized query builder
                    query = OverlayQueryBuilder.build_all_assets_query()
                    cur.execute(query)

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
                        "DELETE FROM overlay_assets WHERE id = %(asset_id)s",
                        {"asset_id": asset_id},
                    )

                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to delete overlay asset {asset_id} (sync): {e}")
            return False
