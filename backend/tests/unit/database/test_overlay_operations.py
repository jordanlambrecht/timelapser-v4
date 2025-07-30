#!/usr/bin/env python3
"""
Unit tests for OverlayOperations.

Tests the database layer for overlay system including preset management,
timelapse overlay configuration, and asset operations.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from app.database.overlay_operations import OverlayOperations, SyncOverlayOperations
from app.models.overlay_model import (
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


@pytest.mark.unit
@pytest.mark.overlay
class TestOverlayOperations:
    """Test suite for OverlayOperations database layer."""

    @pytest.fixture
    def overlay_ops(self, mock_async_database):
        """Create OverlayOperations instance with properly mocked database."""
        # Create a properly mocked database connection
        mock_connection = AsyncMock()
        mock_cursor = AsyncMock()
        
        # Setup the connection context manager chain
        mock_async_database.get_connection.return_value.__aenter__.return_value = mock_connection
        mock_connection.cursor.return_value.__aenter__.return_value = mock_cursor
        
        return OverlayOperations(mock_async_database)

    @pytest.fixture
    def sample_preset_data(self):
        """Sample overlay preset creation data."""
        overlay_config = OverlayConfiguration(
            show_timestamp=True,
            timestamp_format="%Y-%m-%d %H:%M:%S",
            timestamp_position="bottom_right",
            show_weather=False,
            show_camera_name=True,
            camera_name_position="top_left",
            background_opacity=0.7,
            text_color="#FFFFFF",
            font_size=24,
        )
        
        return OverlayPresetCreate(
            name="Test Preset",
            description="A test overlay preset",
            overlay_config=overlay_config,
            is_builtin=False,
        )

    @pytest.fixture
    def sample_timelapse_overlay_data(self):
        """Sample timelapse overlay configuration data."""
        overlay_config = OverlayConfiguration(
            show_timestamp=True,
            timestamp_format="%Y-%m-%d %H:%M:%S",
            timestamp_position="bottom_center",
            show_weather=True,
            show_camera_name=False,
            background_opacity=0.8,
            text_color="#FFFF00",
            font_size=20,
        )
        
        return TimelapseOverlayCreate(
            timelapse_id=1,
            preset_id=1,
            overlay_config=overlay_config,
            enabled=True,
        )

    @pytest.fixture
    def sample_asset_data(self):
        """Sample overlay asset creation data."""
        return OverlayAssetCreate(
            filename="Test Logo",
            file_path="/test/assets/logo.png",
            original_name="logo.png",
            mime_type="image/png",
            file_size=2048,
        )

    # ============================================================================
    # PRESET OPERATIONS TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_all_presets_success(self, overlay_ops, mock_async_database):
        """Test successful retrieval of all overlay presets."""
        # Mock database response
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "name": "Basic Timestamp",
                    "description": "Simple timestamp overlay",
                    "overlay_config": {
                        "show_timestamp": True,
                        "timestamp_format": "%Y-%m-%d %H:%M:%S",
                        "timestamp_position": "bottom_right",
                    },
                    "is_builtin": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
                {
                    "id": 2,
                    "name": "Custom Preset",
                    "description": "User created preset",
                    "overlay_config": {
                        "show_timestamp": True,
                        "show_weather": True,
                    },
                    "is_builtin": False,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            ]
        )

        # Test getting all presets
        presets = await overlay_ops.get_all_presets()

        # Assertions
        assert len(presets) == 2
        assert all(isinstance(preset, OverlayPreset) for preset in presets)
        assert presets[0].name == "Basic Timestamp"
        assert presets[0].is_builtin is True
        assert presets[1].name == "Custom Preset"
        assert presets[1].is_builtin is False

        # Verify database was called correctly
        mock_async_database.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_preset_by_id_success(self, overlay_ops, mock_async_database):
        """Test successful retrieval of preset by ID."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "name": "Basic Timestamp",
                "description": "Simple timestamp overlay",
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                },
                "is_builtin": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test getting preset
        preset = await overlay_ops.get_preset_by_id(1)

        # Assertions
        assert preset is not None
        assert isinstance(preset, OverlayPreset)
        assert preset.id == 1
        assert preset.name == "Basic Timestamp"
        assert preset.is_builtin is True

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()
        args = mock_async_database.fetch_one.call_args[0]
        assert 1 in args  # preset_id

    @pytest.mark.asyncio
    async def test_get_preset_by_id_not_found(self, overlay_ops, mock_async_database):
        """Test getting a preset that doesn't exist."""
        # Mock database returning None
        mock_async_database.fetch_one = AsyncMock(return_value=None)

        # Test getting non-existent preset
        preset = await overlay_ops.get_preset_by_id(999)

        # Assertions
        assert preset is None

    @pytest.mark.asyncio
    async def test_create_preset_success(self, overlay_ops, sample_preset_data, mock_async_database):
        """Test successful preset creation."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "name": "Test Preset",
                "description": "A test overlay preset",
                "overlay_config": sample_preset_data.overlay_config.model_dump(),
                "is_builtin": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test preset creation
        preset = await overlay_ops.create_preset(sample_preset_data)

        # Assertions
        assert preset is not None
        assert isinstance(preset, OverlayPreset)
        assert preset.name == "Test Preset"
        assert preset.is_builtin is False
        assert preset.overlay_config.show_timestamp is True

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_preset_failure(self, overlay_ops, sample_preset_data, mock_async_database):
        """Test preset creation failure handling."""
        # Mock database returning None (creation failed)
        mock_async_database.fetch_one = AsyncMock(return_value=None)

        # Test preset creation
        preset = await overlay_ops.create_preset(sample_preset_data)

        # Assertions
        assert preset is None

    @pytest.mark.asyncio
    async def test_update_preset_success(self, overlay_ops, mock_async_database):
        """Test successful preset update."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "name": "Updated Preset",
                "description": "Updated description",
                "overlay_config": {
                    "show_timestamp": False,
                    "show_weather": True,
                },
                "is_builtin": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test update data
        update_data = OverlayPresetUpdate(
            name="Updated Preset",
            description="Updated description",
        )

        # Test preset update
        preset = await overlay_ops.update_preset(1, update_data)

        # Assertions
        assert preset is not None
        assert isinstance(preset, OverlayPreset)
        assert preset.name == "Updated Preset"
        assert preset.description == "Updated description"

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_preset_success(self, overlay_ops, mock_async_database):
        """Test successful preset deletion."""
        # Mock database execute
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test preset deletion
        result = await overlay_ops.delete_preset(1)

        # Assertions
        assert result is True

        # Verify database was called correctly
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert 1 in args  # preset_id

    @pytest.mark.asyncio
    async def test_delete_preset_not_found(self, overlay_ops, mock_async_database):
        """Test deleting a preset that doesn't exist."""
        # Mock database execute with 0 rows affected
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test preset deletion
        result = await overlay_ops.delete_preset(999)

        # Assertions
        assert result is False

    # ============================================================================
    # TIMELAPSE OVERLAY CONFIGURATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_timelapse_overlay_success(self, overlay_ops, mock_async_database):
        """Test successful retrieval of timelapse overlay configuration."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "timelapse_id": 1,
                "preset_id": 1,
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                },
                "enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test getting timelapse overlay
        config = await overlay_ops.get_timelapse_overlay(1)

        # Assertions
        assert config is not None
        assert isinstance(config, TimelapseOverlay)
        assert config.timelapse_id == 1
        assert config.preset_id == 1
        assert config.enabled is True

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_timelapse_overlay_success(self, overlay_ops, sample_timelapse_overlay_data, mock_async_database):
        """Test successful timelapse overlay configuration creation."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "timelapse_id": 1,
                "preset_id": 1,
                "overlay_config": sample_timelapse_overlay_data.overlay_config.model_dump(),
                "enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test configuration creation
        config = await overlay_ops.create_timelapse_overlay(sample_timelapse_overlay_data)

        # Assertions
        assert config is not None
        assert isinstance(config, TimelapseOverlay)
        assert config.timelapse_id == 1
        assert config.enabled is True
        assert config.overlay_config.show_weather is True

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_timelapse_overlay_success(self, overlay_ops, mock_async_database):
        """Test successful timelapse overlay update."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "timelapse_id": 1,
                "preset_id": 2,
                "overlay_config": {
                    "show_timestamp": False,
                    "show_weather": True,
                },
                "enabled": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test update data
        update_data = TimelapseOverlayUpdate(
            preset_id=2,
            enabled=False,
        )

        # Test configuration update
        config = await overlay_ops.update_timelapse_overlay(1, update_data)

        # Assertions
        assert config is not None
        assert isinstance(config, TimelapseOverlay)
        assert config.preset_id == 2
        assert config.enabled is False

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_timelapse_overlay_success(self, overlay_ops, mock_async_database):
        """Test successful timelapse overlay deletion."""
        # Mock database execute
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test configuration deletion
        result = await overlay_ops.delete_timelapse_overlay(1)

        # Assertions
        assert result is True

        # Verify database was called correctly
        mock_async_database.execute.assert_called_once()

    # ============================================================================
    # ASSET OPERATIONS TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_all_assets_success(self, overlay_ops, mock_async_database):
        """Test successful retrieval of all overlay assets."""
        # Mock database response
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "name": "Logo",
                    "description": "Company logo",
                    "file_path": "/assets/logo.png",
                    "original_name": "logo.png",
                    "mime_type": "image/png",
                    "file_size": 2048,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
                {
                    "id": 2,
                    "name": "Watermark",
                    "description": "Copyright watermark",
                    "file_path": "/assets/watermark.png",
                    "original_name": "watermark.png",
                    "mime_type": "image/png",
                    "file_size": 1024,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            ]
        )

        # Test getting all assets
        assets = await overlay_ops.get_all_assets()

        # Assertions
        assert len(assets) == 2
        assert all(isinstance(asset, OverlayAsset) for asset in assets)
        assert assets[0].name == "Logo"
        assert assets[1].name == "Watermark"

        # Verify database was called correctly
        mock_async_database.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_asset_success(self, overlay_ops, sample_asset_data, mock_async_database):
        """Test successful asset creation."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "name": "Test Logo",
                "description": "A test watermark asset",
                "file_path": "/test/assets/logo.png",
                "original_name": "logo.png",
                "mime_type": "image/png",
                "file_size": 2048,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test asset creation
        asset = await overlay_ops.create_asset(sample_asset_data)

        # Assertions
        assert asset is not None
        assert isinstance(asset, OverlayAsset)
        assert asset.name == "Test Logo"
        assert asset.file_path == "/test/assets/logo.png"
        assert asset.mime_type == "image/png"

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_asset_by_id_success(self, overlay_ops, mock_async_database):
        """Test successful retrieval of asset by ID."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "name": "Test Logo",
                "description": "A test asset",
                "file_path": "/test/assets/logo.png",
                "original_name": "logo.png",
                "mime_type": "image/png",
                "file_size": 2048,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test getting asset
        asset = await overlay_ops.get_asset_by_id(1)

        # Assertions
        assert asset is not None
        assert isinstance(asset, OverlayAsset)
        assert asset.id == 1
        assert asset.name == "Test Logo"

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_asset_success(self, overlay_ops, mock_async_database):
        """Test successful asset deletion."""
        # Mock database execute
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test asset deletion
        result = await overlay_ops.delete_asset(1)

        # Assertions
        assert result is True

        # Verify database was called correctly
        mock_async_database.execute.assert_called_once()

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_error_handling_database_exception(self, overlay_ops, mock_async_database):
        """Test error handling when database operations fail."""
        # Mock database raising an exception
        mock_async_database.fetch_all = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        # Test that exceptions are handled gracefully
        presets = await overlay_ops.get_all_presets()

        # Should return empty list on error, not raise exception
        assert presets == []

    @pytest.mark.asyncio
    async def test_error_handling_invalid_json_config(self, overlay_ops, mock_async_database):
        """Test handling of invalid JSON in overlay configuration."""
        # Mock database response with invalid JSON-like structure
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "name": "Test Preset",
                "description": "Test",
                "overlay_config": "invalid_json",  # Invalid JSON
                "is_builtin": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test getting preset with malformed config
        preset = await overlay_ops.get_preset_by_id(1)

        # Should handle gracefully (exact behavior depends on implementation)
        # Either return None or return preset with default config
        assert preset is None or isinstance(preset, OverlayPreset)


@pytest.mark.unit
@pytest.mark.overlay
class TestSyncOverlayOperations:
    """Test suite for SyncOverlayOperations database layer."""

    @pytest.fixture
    def sync_overlay_ops(self, mock_sync_database):
        """Create SyncOverlayOperations instance with mock database."""
        return SyncOverlayOperations(mock_sync_database)

    @pytest.mark.asyncio
    async def test_sync_get_all_presets_success(self, sync_overlay_ops, mock_sync_database):
        """Test sync version of get_all_presets."""
        # Mock the sync database methods
        mock_sync_database.fetch_all = MagicMock(
            return_value=[
                {
                    "id": 1,
                    "name": "Basic Timestamp",
                    "description": "Simple timestamp overlay",
                    "overlay_config": {
                        "show_timestamp": True,
                        "timestamp_format": "%Y-%m-%d %H:%M:%S",
                    },
                    "is_builtin": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            ]
        )

        # Test getting all presets (sync version)
        presets = sync_overlay_ops.get_all_presets()

        # Assertions
        assert len(presets) == 1
        assert all(isinstance(preset, OverlayPreset) for preset in presets)
        assert presets[0].name == "Basic Timestamp"
        assert presets[0].is_builtin is True

        # Verify database was called correctly
        mock_sync_database.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_get_preset_by_id_success(self, sync_overlay_ops, mock_sync_database):
        """Test sync version of get_preset_by_id."""
        # Mock the sync database methods
        mock_sync_database.fetch_one = MagicMock(
            return_value={
                "id": 1,
                "name": "Basic Timestamp",
                "description": "Simple timestamp overlay",
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                },
                "is_builtin": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Test getting preset by ID (sync version)
        preset = sync_overlay_ops.get_preset_by_id(1)

        # Assertions
        assert preset is not None
        assert isinstance(preset, OverlayPreset)
        assert preset.id == 1
        assert preset.name == "Basic Timestamp"

        # Verify database was called correctly
        mock_sync_database.fetch_one.assert_called_once()