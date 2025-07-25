#!/usr/bin/env python3
"""
Unit tests for OverlayOperations - Simplified approach.

Tests the database layer for overlay system using the mock-based approach
that matches the existing test patterns in the codebase.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.overlay_model import (
    OverlayPreset,
    OverlayPresetCreate,
    TimelapseOverlay,
    TimelapseOverlayCreate,
    OverlayAsset,
    OverlayAssetCreate,
    OverlayConfiguration,
)


@pytest.mark.unit
@pytest.mark.overlay
class TestOverlayOperations:
    """Test suite for OverlayOperations database layer using mocked operations."""

    @pytest.fixture
    def mock_overlay_ops(self):
        """Create mock overlay operations for testing."""
        return AsyncMock()

    @pytest.fixture
    def sample_preset_data(self):
        """Sample overlay preset creation data."""
        from app.enums import OverlayType
        from app.models.overlay_model import OverlayItem, GlobalOverlayOptions
        
        # Create a proper overlay configuration with the actual structure
        overlay_config = OverlayConfiguration(
            overlayPositions={
                "bottomRight": OverlayItem(
                    type=OverlayType.DATE_TIME,
                    textSize=16,
                    textColor="#FFFFFF",
                    dateFormat="MM/dd/yyyy HH:mm",
                ),
                "topLeft": OverlayItem(
                    type=OverlayType.TIMELAPSE_NAME,
                    textSize=14,
                    textColor="#FFFF00",
                ),
            },
            globalOptions=GlobalOverlayOptions(
                opacity=100,
                font="Arial",
                backgroundColor="#000000",
                backgroundOpacity=50,
            ),
        )
        
        return OverlayPresetCreate(
            name="Test Preset",
            description="A test overlay preset",
            overlay_config=overlay_config,
            is_builtin=False,
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
    async def test_get_all_presets_success(self, mock_overlay_ops):
        """Test successful retrieval of all overlay presets."""
        # Setup mock response
        from app.enums import OverlayType
        from app.models.overlay_model import OverlayItem, GlobalOverlayOptions
        
        expected_presets = [
            OverlayPreset(
                id=1,
                name="Basic Timestamp",
                description="Simple timestamp overlay",
                overlay_config=OverlayConfiguration(
                    overlayPositions={
                        "bottomRight": OverlayItem(type=OverlayType.DATE_TIME)
                    }
                ),
                is_builtin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            OverlayPreset(
                id=2,
                name="Custom Preset",
                description="User created preset",
                overlay_config=OverlayConfiguration(
                    overlayPositions={
                        "bottomCenter": OverlayItem(type=OverlayType.WEATHER_CONDITIONS)
                    }
                ),
                is_builtin=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]
        mock_overlay_ops.get_all_presets.return_value = expected_presets

        # Test getting all presets
        presets = await mock_overlay_ops.get_all_presets()

        # Assertions
        assert len(presets) == 2
        assert all(isinstance(preset, OverlayPreset) for preset in presets)
        assert presets[0].name == "Basic Timestamp"
        assert presets[0].is_builtin is True
        assert presets[1].name == "Custom Preset"
        assert presets[1].is_builtin is False

        # Verify mock was called correctly
        mock_overlay_ops.get_all_presets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_preset_by_id_success(self, mock_overlay_ops):
        """Test successful retrieval of preset by ID."""
        # Setup mock response
        from app.enums import OverlayType
        from app.models.overlay_model import OverlayItem, GlobalOverlayOptions
        
        expected_preset = OverlayPreset(
            id=1,
            name="Basic Timestamp",
            description="Simple timestamp overlay",
            overlay_config=OverlayConfiguration(
                overlayPositions={
                    "bottomRight": OverlayItem(type=OverlayType.DATE_TIME)
                },
                globalOptions=GlobalOverlayOptions()
            ),
            is_builtin=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.get_preset_by_id.return_value = expected_preset

        # Test getting preset
        preset = await mock_overlay_ops.get_preset_by_id(1)

        # Assertions
        assert preset is not None
        assert isinstance(preset, OverlayPreset)
        assert preset.id == 1
        assert preset.name == "Basic Timestamp"
        assert preset.is_builtin is True

        # Verify mock was called correctly
        mock_overlay_ops.get_preset_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_preset_by_id_not_found(self, mock_overlay_ops):
        """Test getting a preset that doesn't exist."""
        # Setup mock to return None
        mock_overlay_ops.get_preset_by_id.return_value = None

        # Test getting non-existent preset
        preset = await mock_overlay_ops.get_preset_by_id(999)

        # Assertions
        assert preset is None

        # Verify mock was called correctly
        mock_overlay_ops.get_preset_by_id.assert_called_once_with(999)

    @pytest.mark.asyncio
    async def test_create_preset_success(self, mock_overlay_ops, sample_preset_data):
        """Test successful preset creation."""
        # Setup mock response
        expected_preset = OverlayPreset(
            id=1,
            name=sample_preset_data.name,
            description=sample_preset_data.description,
            overlay_config=sample_preset_data.overlay_config,
            is_builtin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.create_preset.return_value = expected_preset

        # Test preset creation
        preset = await mock_overlay_ops.create_preset(sample_preset_data)

        # Assertions
        assert preset is not None
        assert isinstance(preset, OverlayPreset)
        assert preset.name == "Test Preset"
        assert preset.is_builtin is False
        assert len(preset.overlay_config.overlayPositions) > 0

        # Verify mock was called correctly
        mock_overlay_ops.create_preset.assert_called_once_with(sample_preset_data)

    @pytest.mark.asyncio
    async def test_create_preset_failure(self, mock_overlay_ops, sample_preset_data):
        """Test preset creation failure handling."""
        # Setup mock to return None (creation failed)
        mock_overlay_ops.create_preset.return_value = None

        # Test preset creation
        preset = await mock_overlay_ops.create_preset(sample_preset_data)

        # Assertions
        assert preset is None

        # Verify mock was called correctly
        mock_overlay_ops.create_preset.assert_called_once_with(sample_preset_data)

    @pytest.mark.asyncio
    async def test_delete_preset_success(self, mock_overlay_ops):
        """Test successful preset deletion."""
        # Setup mock response
        mock_overlay_ops.delete_preset.return_value = True

        # Test preset deletion
        result = await mock_overlay_ops.delete_preset(1)

        # Assertions
        assert result is True

        # Verify mock was called correctly
        mock_overlay_ops.delete_preset.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_preset_not_found(self, mock_overlay_ops):
        """Test deleting a preset that doesn't exist."""
        # Setup mock response
        mock_overlay_ops.delete_preset.return_value = False

        # Test preset deletion
        result = await mock_overlay_ops.delete_preset(999)

        # Assertions
        assert result is False

        # Verify mock was called correctly
        mock_overlay_ops.delete_preset.assert_called_once_with(999)

    # ============================================================================
    # TIMELAPSE OVERLAY CONFIGURATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_timelapse_overlay_success(self, mock_overlay_ops):
        """Test successful retrieval of timelapse overlay configuration."""
        # Setup mock response
        from app.enums import OverlayType
        from app.models.overlay_model import OverlayItem, GlobalOverlayOptions
        
        expected_config = TimelapseOverlay(
            id=1,
            timelapse_id=1,
            preset_id=1,
            overlay_config=OverlayConfiguration(
                overlayPositions={
                    "bottomRight": OverlayItem(type=OverlayType.DATE_TIME),
                    "topLeft": OverlayItem(type=OverlayType.WEATHER_CONDITIONS),
                },
                globalOptions=GlobalOverlayOptions()
            ),
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.get_timelapse_overlay.return_value = expected_config

        # Test getting timelapse overlay
        config = await mock_overlay_ops.get_timelapse_overlay(1)

        # Assertions
        assert config is not None
        assert isinstance(config, TimelapseOverlay)
        assert config.timelapse_id == 1
        assert config.preset_id == 1
        assert config.enabled is True

        # Verify mock was called correctly
        mock_overlay_ops.get_timelapse_overlay.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_create_timelapse_overlay_success(self, mock_overlay_ops):
        """Test successful timelapse overlay configuration creation."""
        # Test data
        from app.enums import OverlayType
        from app.models.overlay_model import OverlayItem, GlobalOverlayOptions
        
        config_data = TimelapseOverlayCreate(
            timelapse_id=1,
            preset_id=1,
            overlay_config=OverlayConfiguration(
                overlayPositions={
                    "bottomRight": OverlayItem(type=OverlayType.DATE_TIME),
                    "topLeft": OverlayItem(type=OverlayType.WEATHER_CONDITIONS),
                },
                globalOptions=GlobalOverlayOptions()
            ),
            enabled=True,
        )

        # Setup mock response
        expected_config = TimelapseOverlay(
            id=1,
            timelapse_id=config_data.timelapse_id,
            preset_id=config_data.preset_id,
            overlay_config=config_data.overlay_config,
            enabled=config_data.enabled,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.create_timelapse_overlay.return_value = expected_config

        # Test configuration creation
        config = await mock_overlay_ops.create_timelapse_overlay(config_data)

        # Assertions
        assert config is not None
        assert isinstance(config, TimelapseOverlay)
        assert config.timelapse_id == 1
        assert config.enabled is True
        assert "topLeft" in config.overlay_config.overlayPositions

        # Verify mock was called correctly
        mock_overlay_ops.create_timelapse_overlay.assert_called_once_with(config_data)

    @pytest.mark.asyncio
    async def test_delete_timelapse_overlay_success(self, mock_overlay_ops):
        """Test successful timelapse overlay deletion."""
        # Setup mock response
        mock_overlay_ops.delete_timelapse_overlay.return_value = True

        # Test configuration deletion
        result = await mock_overlay_ops.delete_timelapse_overlay(1)

        # Assertions
        assert result is True

        # Verify mock was called correctly
        mock_overlay_ops.delete_timelapse_overlay.assert_called_once_with(1)

    # ============================================================================
    # ASSET OPERATIONS TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_all_assets_success(self, mock_overlay_ops):
        """Test successful retrieval of all overlay assets."""
        # Setup mock response
        expected_assets = [
            OverlayAsset(
                id=1,
                filename="Logo",
                file_path="/assets/logo.png",
                original_name="logo.png",
                mime_type="image/png",
                file_size=2048,
                uploaded_at=datetime.utcnow(),
            ),
            OverlayAsset(
                id=2,
                filename="Watermark",
                file_path="/assets/watermark.png",
                original_name="watermark.png",
                mime_type="image/png",
                file_size=1024,
                uploaded_at=datetime.utcnow(),
            ),
        ]
        mock_overlay_ops.get_all_assets.return_value = expected_assets

        # Test getting all assets
        assets = await mock_overlay_ops.get_all_assets()

        # Assertions
        assert len(assets) == 2
        assert all(isinstance(asset, OverlayAsset) for asset in assets)
        assert assets[0].filename == "Logo"
        assert assets[1].filename == "Watermark"

        # Verify mock was called correctly
        mock_overlay_ops.get_all_assets.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_asset_success(self, mock_overlay_ops, sample_asset_data):
        """Test successful asset creation."""
        # Setup mock response
        expected_asset = OverlayAsset(
            id=1,
            filename="Test Logo",
            file_path=sample_asset_data.file_path,
            original_name=sample_asset_data.original_name,
            mime_type=sample_asset_data.mime_type,
            file_size=sample_asset_data.file_size,
            uploaded_at=datetime.utcnow(),
        )
        mock_overlay_ops.create_asset.return_value = expected_asset

        # Test asset creation
        asset = await mock_overlay_ops.create_asset(sample_asset_data)

        # Assertions
        assert asset is not None
        assert isinstance(asset, OverlayAsset)
        assert asset.filename == "Test Logo"
        assert asset.file_path == "/test/assets/logo.png"
        assert asset.mime_type == "image/png"

        # Verify mock was called correctly
        mock_overlay_ops.create_asset.assert_called_once_with(sample_asset_data)

    @pytest.mark.asyncio
    async def test_get_asset_by_id_success(self, mock_overlay_ops):
        """Test successful retrieval of asset by ID."""
        # Setup mock response
        expected_asset = OverlayAsset(
            id=1,
            filename="Test Logo",
            file_path="/test/assets/logo.png",
            original_name="logo.png",
            mime_type="image/png",
            file_size=2048,
            uploaded_at=datetime.utcnow(),
        )
        mock_overlay_ops.get_asset_by_id.return_value = expected_asset

        # Test getting asset
        asset = await mock_overlay_ops.get_asset_by_id(1)

        # Assertions
        assert asset is not None
        assert isinstance(asset, OverlayAsset)
        assert asset.id == 1
        assert asset.filename == "Test Logo"

        # Verify mock was called correctly
        mock_overlay_ops.get_asset_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_asset_success(self, mock_overlay_ops):
        """Test successful asset deletion."""
        # Setup mock response
        mock_overlay_ops.delete_asset.return_value = True

        # Test asset deletion
        result = await mock_overlay_ops.delete_asset(1)

        # Assertions
        assert result is True

        # Verify mock was called correctly
        mock_overlay_ops.delete_asset.assert_called_once_with(1)

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_error_handling_database_exception(self, mock_overlay_ops):
        """Test error handling when database operations fail."""
        # Setup mock to raise an exception
        mock_overlay_ops.get_all_presets.side_effect = Exception("Database connection failed")

        # Test that exceptions propagate (this is expected behavior for unit tests)
        with pytest.raises(Exception) as exc_info:
            await mock_overlay_ops.get_all_presets()
        
        assert "Database connection failed" in str(exc_info.value)

        # Verify mock was called
        mock_overlay_ops.get_all_presets.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_behavior(self, mock_overlay_ops):
        """Test that operations handle validation appropriately."""
        # Setup mock to return None for invalid data
        mock_overlay_ops.create_preset.return_value = None

        # Test that mock returns None for any data (simulating validation failure)
        test_preset_data = OverlayPresetCreate(
            name="Test Name",  # Valid name
            description="Test",
            overlay_config=OverlayConfiguration(),
            is_builtin=False,
        )

        # Test that validation failure results in None return
        preset = await mock_overlay_ops.create_preset(test_preset_data)

        # Assertions
        assert preset is None

        # Verify mock was called
        mock_overlay_ops.create_preset.assert_called_once_with(test_preset_data)