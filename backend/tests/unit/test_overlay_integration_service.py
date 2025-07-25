#!/usr/bin/env python3
"""
Unit tests for OverlayIntegrationService.

Tests the service layer for overlay system including business logic,
preset management, configuration validation, and asset handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.services.overlay_pipeline.services.integration_service import OverlayIntegrationService
from app.models.overlay_model import (
    OverlayPreset,
    OverlayPresetCreate,
    OverlayPresetUpdate,
    TimelapseOverlay,
    TimelapseOverlayCreate,
    TimelapseOverlayUpdate,
    OverlayAsset,
    OverlayAssetCreate,
    OverlayPreviewRequest,
    OverlayPreviewResponse,
    OverlayConfiguration,
)
from app.models.shared_models import ResponseWithMessage


@pytest.mark.unit
@pytest.mark.overlay
class TestOverlayIntegrationService:
    """Test suite for OverlayIntegrationService business logic layer."""

    @pytest.fixture
    def mock_overlay_ops(self):
        """Mock overlay operations for testing."""
        mock_ops = AsyncMock()
        
        # Setup mock responses for preset operations
        mock_ops.get_all_presets.return_value = [
            OverlayPreset(
                id=1,
                name="Basic Timestamp",
                description="Simple timestamp overlay",
                overlay_config=OverlayConfiguration(
                    show_timestamp=True,
                    timestamp_format="%Y-%m-%d %H:%M:%S",
                    timestamp_position="bottom_right",
                ),
                is_builtin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            OverlayPreset(
                id=2,
                name="Weather + Time",
                description="Timestamp with weather info",
                overlay_config=OverlayConfiguration(
                    show_timestamp=True,
                    show_weather=True,
                    timestamp_position="bottom_center",
                ),
                is_builtin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]
        
        return mock_ops

    @pytest.fixture
    def mock_overlay_job_ops(self):
        """Mock overlay job operations for testing."""
        return AsyncMock()

    @pytest.fixture
    def overlay_service(self, mock_async_database, mock_overlay_ops, mock_overlay_job_ops):
        """Create OverlayIntegrationService instance with mocked dependencies."""
        service = OverlayIntegrationService(mock_async_database)
        
        # Inject mocked operations
        service.overlay_ops = mock_overlay_ops
        service.overlay_job_ops = mock_overlay_job_ops
        
        return service

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
            name="Custom Test Preset",
            description="A custom test overlay preset",
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

    # ============================================================================
    # PRESET MANAGEMENT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_overlay_presets_success(self, overlay_service, mock_overlay_ops):
        """Test successful retrieval of overlay presets."""
        # Test getting all presets
        presets = await overlay_service.get_overlay_presets()

        # Assertions
        assert len(presets) == 2
        assert all(isinstance(preset, OverlayPreset) for preset in presets)
        assert presets[0].name == "Basic Timestamp"
        assert presets[0].is_builtin is True
        assert presets[1].name == "Weather + Time"
        assert presets[1].is_builtin is True

        # Verify operations were called correctly
        mock_overlay_ops.get_all_presets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_overlay_preset_by_id_success(self, overlay_service, mock_overlay_ops):
        """Test successful retrieval of preset by ID."""
        # Setup mock response
        expected_preset = OverlayPreset(
            id=1,
            name="Basic Timestamp",
            description="Simple timestamp overlay",
            overlay_config=OverlayConfiguration(show_timestamp=True),
            is_builtin=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.get_preset_by_id.return_value = expected_preset

        # Test getting preset by ID
        preset = await overlay_service.get_overlay_preset_by_id(1)

        # Assertions
        assert preset is not None
        assert preset.id == 1
        assert preset.name == "Basic Timestamp"
        assert preset.is_builtin is True

        # Verify operations were called correctly
        mock_overlay_ops.get_preset_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_overlay_preset_by_id_not_found(self, overlay_service, mock_overlay_ops):
        """Test getting a preset that doesn't exist."""
        # Setup mock to return None
        mock_overlay_ops.get_preset_by_id.return_value = None

        # Test getting non-existent preset
        preset = await overlay_service.get_overlay_preset_by_id(999)

        # Assertions
        assert preset is None

        # Verify operations were called correctly
        mock_overlay_ops.get_preset_by_id.assert_called_once_with(999)

    @pytest.mark.asyncio
    async def test_create_overlay_preset_success(self, overlay_service, sample_preset_data, mock_overlay_ops):
        """Test successful preset creation."""
        # Setup mock response
        expected_preset = OverlayPreset(
            id=3,
            name=sample_preset_data.name,
            description=sample_preset_data.description,
            overlay_config=sample_preset_data.overlay_config,
            is_builtin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.create_preset.return_value = expected_preset

        # Test preset creation
        preset = await overlay_service.create_overlay_preset(sample_preset_data)

        # Assertions
        assert preset is not None
        assert preset.id == 3
        assert preset.name == "Custom Test Preset"
        assert preset.is_builtin is False
        assert preset.overlay_config.show_timestamp is True

        # Verify operations were called correctly
        mock_overlay_ops.create_preset.assert_called_once_with(sample_preset_data)

    @pytest.mark.asyncio
    async def test_create_overlay_preset_failure(self, overlay_service, sample_preset_data, mock_overlay_ops):
        """Test preset creation failure handling."""
        # Setup mock to return None (creation failed)
        mock_overlay_ops.create_preset.return_value = None

        # Test preset creation
        preset = await overlay_service.create_overlay_preset(sample_preset_data)

        # Assertions
        assert preset is None

        # Verify operations were called correctly
        mock_overlay_ops.create_preset.assert_called_once_with(sample_preset_data)

    @pytest.mark.asyncio
    async def test_update_overlay_preset_success(self, overlay_service, mock_overlay_ops):
        """Test successful preset update."""
        # Setup mock response
        updated_preset = OverlayPreset(
            id=3,
            name="Updated Custom Preset",
            description="Updated description",
            overlay_config=OverlayConfiguration(
                show_timestamp=False,
                show_weather=True,
            ),
            is_builtin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.update_preset.return_value = updated_preset

        # Test update data
        update_data = OverlayPresetUpdate(
            name="Updated Custom Preset",
            description="Updated description",
        )

        # Test preset update
        preset = await overlay_service.update_overlay_preset(3, update_data)

        # Assertions
        assert preset is not None
        assert preset.id == 3
        assert preset.name == "Updated Custom Preset"
        assert preset.description == "Updated description"

        # Verify operations were called correctly
        mock_overlay_ops.update_preset.assert_called_once_with(3, update_data)

    @pytest.mark.asyncio
    async def test_delete_overlay_preset_success(self, overlay_service, mock_overlay_ops):
        """Test successful preset deletion."""
        # Setup mock response
        mock_overlay_ops.delete_preset.return_value = True

        # Test preset deletion
        result = await overlay_service.delete_overlay_preset(3)

        # Assertions
        assert result is True

        # Verify operations were called correctly
        mock_overlay_ops.delete_preset.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_delete_overlay_preset_not_found(self, overlay_service, mock_overlay_ops):
        """Test deleting a preset that doesn't exist."""
        # Setup mock response
        mock_overlay_ops.delete_preset.return_value = False

        # Test preset deletion
        result = await overlay_service.delete_overlay_preset(999)

        # Assertions
        assert result is False

        # Verify operations were called correctly
        mock_overlay_ops.delete_preset.assert_called_once_with(999)

    # ============================================================================
    # TIMELAPSE OVERLAY CONFIGURATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_timelapse_overlay_config_success(self, overlay_service, mock_overlay_ops):
        """Test successful retrieval of timelapse overlay configuration."""
        # Setup mock response
        expected_config = TimelapseOverlay(
            id=1,
            timelapse_id=1,
            preset_id=1,
            overlay_config=OverlayConfiguration(
                show_timestamp=True,
                show_weather=True,
            ),
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.get_timelapse_overlay.return_value = expected_config

        # Test getting timelapse overlay config
        config = await overlay_service.get_timelapse_overlay_config(1)

        # Assertions
        assert config is not None
        assert config.timelapse_id == 1
        assert config.preset_id == 1
        assert config.enabled is True
        assert config.overlay_config.show_timestamp is True

        # Verify operations were called correctly
        mock_overlay_ops.get_timelapse_overlay.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_create_or_update_timelapse_overlay_config_create(self, overlay_service, sample_timelapse_overlay_data, mock_overlay_ops):
        """Test creating new timelapse overlay configuration."""
        # Setup mock response (no existing config)
        mock_overlay_ops.get_timelapse_overlay.return_value = None
        
        expected_config = TimelapseOverlay(
            id=1,
            timelapse_id=sample_timelapse_overlay_data.timelapse_id,
            preset_id=sample_timelapse_overlay_data.preset_id,
            overlay_config=sample_timelapse_overlay_data.overlay_config,
            enabled=sample_timelapse_overlay_data.enabled,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.create_timelapse_overlay.return_value = expected_config

        # Test creating configuration
        config = await overlay_service.create_or_update_timelapse_overlay_config(sample_timelapse_overlay_data)

        # Assertions
        assert config is not None
        assert config.timelapse_id == 1
        assert config.enabled is True

        # Verify operations were called correctly
        mock_overlay_ops.get_timelapse_overlay.assert_called_once_with(1)
        mock_overlay_ops.create_timelapse_overlay.assert_called_once_with(sample_timelapse_overlay_data)

    @pytest.mark.asyncio
    async def test_create_or_update_timelapse_overlay_config_update(self, overlay_service, sample_timelapse_overlay_data, mock_overlay_ops):
        """Test updating existing timelapse overlay configuration."""
        # Setup mock response (existing config)
        existing_config = TimelapseOverlay(
            id=1,
            timelapse_id=1,
            preset_id=2,  # Different preset
            overlay_config=OverlayConfiguration(show_timestamp=False),
            enabled=False,
            created_at=datetime.utcnow() - timedelta(days=1),
            updated_at=datetime.utcnow() - timedelta(days=1),
        )
        mock_overlay_ops.get_timelapse_overlay.return_value = existing_config
        
        updated_config = TimelapseOverlay(
            id=1,
            timelapse_id=sample_timelapse_overlay_data.timelapse_id,
            preset_id=sample_timelapse_overlay_data.preset_id,
            overlay_config=sample_timelapse_overlay_data.overlay_config,
            enabled=sample_timelapse_overlay_data.enabled,
            created_at=existing_config.created_at,
            updated_at=datetime.utcnow(),
        )
        
        # Convert create data to update data
        update_data = TimelapseOverlayUpdate(
            preset_id=sample_timelapse_overlay_data.preset_id,
            overlay_config=sample_timelapse_overlay_data.overlay_config,
            enabled=sample_timelapse_overlay_data.enabled,
        )
        mock_overlay_ops.update_timelapse_overlay.return_value = updated_config

        # Test updating configuration
        config = await overlay_service.create_or_update_timelapse_overlay_config(sample_timelapse_overlay_data)

        # Assertions
        assert config is not None
        assert config.timelapse_id == 1
        assert config.preset_id == 1  # Updated value
        assert config.enabled is True  # Updated value

        # Verify operations were called correctly
        mock_overlay_ops.get_timelapse_overlay.assert_called_once_with(1)
        mock_overlay_ops.update_timelapse_overlay.assert_called_once_with(1, update_data)

    @pytest.mark.asyncio
    async def test_delete_timelapse_overlay_config_success(self, overlay_service, mock_overlay_ops):
        """Test successful timelapse overlay configuration deletion."""
        # Setup mock response
        mock_overlay_ops.delete_timelapse_overlay.return_value = True

        # Test configuration deletion
        result = await overlay_service.delete_timelapse_overlay_config(1)

        # Assertions
        assert result is True

        # Verify operations were called correctly
        mock_overlay_ops.delete_timelapse_overlay.assert_called_once_with(1)

    # ============================================================================
    # OVERLAY CONFIGURATION VALIDATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_validate_overlay_configuration_valid(self, overlay_service):
        """Test validation of valid overlay configuration."""
        # Valid configuration
        config = {
            "show_timestamp": True,
            "timestamp_format": "%Y-%m-%d %H:%M:%S",
            "timestamp_position": "bottom_right",
            "show_weather": False,
            "show_camera_name": True,
            "camera_name_position": "top_left",
            "background_opacity": 0.7,
            "text_color": "#FFFFFF",
            "font_size": 24,
        }

        # Test validation
        is_valid = await overlay_service.validate_overlay_configuration(config)

        # Assertions
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_overlay_configuration_invalid_position(self, overlay_service):
        """Test validation with invalid position value."""
        # Invalid position value
        config = {
            "show_timestamp": True,
            "timestamp_position": "invalid_position",  # Invalid
            "timestamp_format": "%Y-%m-%d %H:%M:%S",
        }

        # Test validation
        is_valid = await overlay_service.validate_overlay_configuration(config)

        # Assertions
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_overlay_configuration_invalid_opacity(self, overlay_service):
        """Test validation with invalid opacity value."""
        # Invalid opacity value
        config = {
            "show_timestamp": True,
            "background_opacity": 1.5,  # Invalid (> 1.0)
        }

        # Test validation
        is_valid = await overlay_service.validate_overlay_configuration(config)

        # Assertions
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_overlay_configuration_invalid_color(self, overlay_service):
        """Test validation with invalid color format."""
        # Invalid color format
        config = {
            "show_timestamp": True,
            "text_color": "invalid_color",  # Invalid hex color
        }

        # Test validation
        is_valid = await overlay_service.validate_overlay_configuration(config)

        # Assertions
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_overlay_configuration_missing_required(self, overlay_service):
        """Test validation with missing required fields."""
        # Missing required timestamp format when timestamp is enabled
        config = {
            "show_timestamp": True,
            # Missing timestamp_format and timestamp_position
        }

        # Test validation
        is_valid = await overlay_service.validate_overlay_configuration(config)

        # Assertions
        assert is_valid is False

    # ============================================================================
    # ASSET MANAGEMENT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_overlay_assets_success(self, overlay_service, mock_overlay_ops):
        """Test successful retrieval of overlay assets."""
        # Setup mock response
        expected_assets = [
            OverlayAsset(
                id=1,
                name="Logo",
                description="Company logo",
                file_path="/assets/logo.png",
                original_name="logo.png",
                mime_type="image/png",
                file_size=2048,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            OverlayAsset(
                id=2,
                name="Watermark",
                description="Copyright watermark",
                file_path="/assets/watermark.png",
                original_name="watermark.png",
                mime_type="image/png",
                file_size=1024,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]
        mock_overlay_ops.get_all_assets.return_value = expected_assets

        # Test getting all assets
        assets = await overlay_service.get_overlay_assets()

        # Assertions
        assert len(assets) == 2
        assert all(isinstance(asset, OverlayAsset) for asset in assets)
        assert assets[0].name == "Logo"
        assert assets[1].name == "Watermark"

        # Verify operations were called correctly
        mock_overlay_ops.get_all_assets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_overlay_asset_by_id_success(self, overlay_service, mock_overlay_ops):
        """Test successful retrieval of asset by ID."""
        # Setup mock response
        expected_asset = OverlayAsset(
            id=1,
            name="Logo",
            description="Company logo",
            file_path="/assets/logo.png",
            original_name="logo.png",
            mime_type="image/png",
            file_size=2048,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_overlay_ops.get_asset_by_id.return_value = expected_asset

        # Test getting asset by ID
        asset = await overlay_service.get_overlay_asset_by_id(1)

        # Assertions
        assert asset is not None
        assert asset.id == 1
        assert asset.name == "Logo"
        assert asset.mime_type == "image/png"

        # Verify operations were called correctly
        mock_overlay_ops.get_asset_by_id.assert_called_once_with(1)

    # ============================================================================
    # PREVIEW GENERATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_generate_overlay_preview_success(self, overlay_service):
        """Test successful overlay preview generation."""
        # Mock preview request
        preview_request = OverlayPreviewRequest(
            camera_id=1,
            overlay_config=OverlayConfiguration(
                show_timestamp=True,
                timestamp_format="%Y-%m-%d %H:%M:%S",
                timestamp_position="bottom_right",
            ),
        )

        # Mock the preview generation process
        with patch.object(overlay_service, '_generate_preview_image') as mock_generate:
            mock_generate.return_value = OverlayPreviewResponse(
                success=True,
                preview_image_path="/tmp/preview_123.jpg",
                message="Preview generated successfully",
                camera_id=1,
                processing_time_ms=250,
            )

            # Test preview generation
            result = await overlay_service.generate_overlay_preview(preview_request)

            # Assertions
            assert result is not None
            assert result.success is True
            assert result.camera_id == 1
            assert result.preview_image_path == "/tmp/preview_123.jpg"
            assert result.processing_time_ms == 250

            # Verify internal method was called
            mock_generate.assert_called_once_with(preview_request)

    @pytest.mark.asyncio
    async def test_capture_fresh_photo_for_preview_success(self, overlay_service):
        """Test successful fresh photo capture for preview."""
        # Mock the capture process
        with patch.object(overlay_service, '_capture_temp_image') as mock_capture:
            mock_capture.return_value = "/tmp/temp_camera_1.jpg"

            # Test fresh photo capture
            temp_path = await overlay_service.capture_fresh_photo_for_preview(1)

            # Assertions
            assert temp_path == "/tmp/temp_camera_1.jpg"

            # Verify internal method was called
            mock_capture.assert_called_once_with(1)

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_error_handling_database_exception(self, overlay_service, mock_overlay_ops):
        """Test error handling when database operations fail."""
        # Mock database operation raising an exception
        mock_overlay_ops.get_all_presets.side_effect = Exception("Database connection failed")

        # Test that exceptions are handled gracefully
        presets = await overlay_service.get_overlay_presets()

        # Should return empty list on error, not raise exception
        assert presets == []

    @pytest.mark.asyncio
    async def test_error_handling_invalid_preset_data(self, overlay_service, mock_overlay_ops):
        """Test error handling with invalid preset data."""
        # Setup mock to raise validation error
        mock_overlay_ops.create_preset.side_effect = ValueError("Invalid preset configuration")

        # Create invalid preset data
        invalid_preset_data = OverlayPresetCreate(
            name="",  # Empty name should be invalid
            description="Test",
            overlay_config=OverlayConfiguration(),
            is_builtin=False,
        )

        # Test that validation errors are handled gracefully
        preset = await overlay_service.create_overlay_preset(invalid_preset_data)

        # Should return None on validation error
        assert preset is None