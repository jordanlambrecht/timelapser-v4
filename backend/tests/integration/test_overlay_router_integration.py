#!/usr/bin/env python3
"""
Overlay Router Integration Tests.

Tests the HTTP API layer for overlay system including all endpoints,
request/response handling, validation, and error scenarios.
"""

import asyncio
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.overlay_model import (
    OverlayAsset,
    OverlayConfiguration,
    OverlayPreset,
    OverlayPresetCreate,
    OverlayPresetUpdate,
    OverlayPreviewRequest,
    TimelapseOverlay,
    TimelapseOverlayCreate,
    TimelapseOverlayUpdate,
)
from app.services.overlay_job_service import SyncOverlayJobService
from app.services.overlay_pipeline.services.integration_service import (
    OverlayIntegrationService,
)


@pytest.fixture
def test_client():
    """Create test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_overlay_service_responses():
    """Mock responses for overlay service methods."""

    builtin_presets = [
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

    custom_preset = OverlayPreset(
        id=3,
        name="Custom Preset",
        description="User-created preset",
        overlay_config=OverlayConfiguration(
            show_timestamp=True,
            show_weather=True,
            show_camera_name=True,
            timestamp_position="bottom_right",
        ),
        is_builtin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    test_assets = [
        OverlayAsset(
            id=1,
            name="Company Logo",
            description="Corporate logo watermark",
            file_path="/test/assets/logo.png",
            original_name="logo.png",
            mime_type="image/png",
            file_size=2048,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        OverlayAsset(
            id=2,
            name="Copyright Mark",
            description="Copyright watermark",
            file_path="/test/assets/copyright.png",
            original_name="copyright.png",
            mime_type="image/png",
            file_size=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]

    timelapse_config = TimelapseOverlay(
        id=1,
        timelapse_id=1,
        preset_id=1,
        overlay_config=OverlayConfiguration(
            show_timestamp=True,
            timestamp_format="%Y-%m-%d %H:%M:%S",
            timestamp_position="bottom_center",
        ),
        enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    return {
        "builtin_presets": builtin_presets,
        "custom_preset": custom_preset,
        "all_presets": builtin_presets + [custom_preset],
        "assets": test_assets,
        "timelapse_config": timelapse_config,
    }


@pytest.mark.integration
@pytest.mark.overlay_router
class TestOverlayRouterIntegration:
    """Integration tests for overlay router endpoints."""

    # ============================================================================
    # PRESET MANAGEMENT ENDPOINT TESTS
    # ============================================================================

    def test_get_overlay_presets_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful retrieval of all overlay presets."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_presets.return_value = (
                mock_overlay_service_responses["all_presets"]
            )
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/presets")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert len(data) == 3
            assert data[0]["name"] == "Basic Timestamp"
            assert data[0]["is_builtin"] is True
            assert data[1]["name"] == "Weather + Time"
            assert data[1]["is_builtin"] is True
            assert data[2]["name"] == "Custom Preset"
            assert data[2]["is_builtin"] is False

            # Verify service was called
            mock_overlay_service.get_overlay_presets.assert_called_once()

    def test_get_overlay_presets_filtered_builtin_only(
        self, test_client, mock_overlay_service_responses
    ):
        """Test filtering to get only built-in presets."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_presets.return_value = (
                mock_overlay_service_responses["all_presets"]
            )
            mock_service.return_value = mock_overlay_service

            # Make request with filter
            response = test_client.get("/api/overlays/presets?include_custom=false")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should filter out custom presets in the endpoint logic
            builtin_count = sum(1 for preset in data if preset["is_builtin"])
            assert builtin_count == 2  # Only built-in presets

    def test_get_overlay_preset_by_id_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful retrieval of specific preset."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_preset_by_id.return_value = (
                mock_overlay_service_responses["builtin_presets"][0]
            )
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/presets/1")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["id"] == 1
            assert data["name"] == "Basic Timestamp"
            assert data["is_builtin"] is True
            assert "overlay_config" in data

            # Verify service was called
            mock_overlay_service.get_overlay_preset_by_id.assert_called_once_with(1)

    def test_get_overlay_preset_by_id_not_found(self, test_client):
        """Test getting a preset that doesn't exist."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to return None
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_preset_by_id.return_value = None
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/presets/999")

            # Assertions
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_create_overlay_preset_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful preset creation."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.validate_overlay_configuration.return_value = True
            mock_overlay_service.create_overlay_preset.return_value = (
                mock_overlay_service_responses["custom_preset"]
            )
            mock_service.return_value = mock_overlay_service

            # Request data
            preset_data = {
                "name": "Custom Preset",
                "description": "User-created preset",
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                    "timestamp_position": "bottom_right",
                    "show_weather": True,
                    "show_camera_name": True,
                    "background_opacity": 0.7,
                    "text_color": "#FFFFFF",
                    "font_size": 24,
                },
                "is_builtin": False,
            }

            # Make request
            response = test_client.post("/api/overlays/presets", json=preset_data)

            # Assertions
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()

            assert data["id"] == 3
            assert data["name"] == "Custom Preset"
            assert data["is_builtin"] is False

            # Verify service calls
            mock_overlay_service.validate_overlay_configuration.assert_called_once()
            mock_overlay_service.create_overlay_preset.assert_called_once()

    def test_create_overlay_preset_invalid_config(self, test_client):
        """Test preset creation with invalid configuration."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to reject configuration
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.validate_overlay_configuration.return_value = False
            mock_service.return_value = mock_overlay_service

            # Request data with invalid config
            preset_data = {
                "name": "Invalid Preset",
                "description": "Preset with invalid config",
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_position": "invalid_position",  # Invalid
                },
                "is_builtin": False,
            }

            # Make request
            response = test_client.post("/api/overlays/presets", json=preset_data)

            # Assertions
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "invalid" in data["detail"].lower()

    def test_update_overlay_preset_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful preset update."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_preset_by_id.return_value = (
                mock_overlay_service_responses["custom_preset"]
            )
            mock_overlay_service.validate_overlay_configuration.return_value = True

            updated_preset = mock_overlay_service_responses["custom_preset"]
            updated_preset.name = "Updated Custom Preset"
            mock_overlay_service.update_overlay_preset.return_value = updated_preset
            mock_service.return_value = mock_overlay_service

            # Request data
            update_data = {
                "name": "Updated Custom Preset",
                "description": "Updated description",
            }

            # Make request
            response = test_client.put("/api/overlays/presets/3", json=update_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "Updated Custom Preset"

            # Verify service calls
            mock_overlay_service.get_overlay_preset_by_id.assert_called_once_with(3)
            mock_overlay_service.update_overlay_preset.assert_called_once()

    def test_update_builtin_preset_forbidden(
        self, test_client, mock_overlay_service_responses
    ):
        """Test that built-in presets cannot be updated."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to return built-in preset
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_preset_by_id.return_value = (
                mock_overlay_service_responses["builtin_presets"][0]
            )
            mock_service.return_value = mock_overlay_service

            # Request data
            update_data = {
                "name": "Modified Built-in",
            }

            # Make request
            response = test_client.put("/api/overlays/presets/1", json=update_data)

            # Assertions
            assert response.status_code == status.HTTP_403_FORBIDDEN
            data = response.json()
            assert "built-in" in data["detail"].lower()

    def test_delete_overlay_preset_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful preset deletion."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_preset_by_id.return_value = (
                mock_overlay_service_responses["custom_preset"]
            )
            mock_overlay_service.delete_overlay_preset.return_value = True
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.delete("/api/overlays/presets/3")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "deleted successfully" in data["message"]

            # Verify service calls
            mock_overlay_service.get_overlay_preset_by_id.assert_called_once_with(3)
            mock_overlay_service.delete_overlay_preset.assert_called_once_with(3)

    def test_delete_builtin_preset_forbidden(
        self, test_client, mock_overlay_service_responses
    ):
        """Test that built-in presets cannot be deleted."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to return built-in preset
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_preset_by_id.return_value = (
                mock_overlay_service_responses["builtin_presets"][0]
            )
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.delete("/api/overlays/presets/1")

            # Assertions
            assert response.status_code == status.HTTP_403_FORBIDDEN
            data = response.json()
            assert "built-in" in data["detail"].lower()

    # ============================================================================
    # TIMELAPSE OVERLAY CONFIGURATION ENDPOINT TESTS
    # ============================================================================

    def test_get_timelapse_overlay_config_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful retrieval of timelapse overlay configuration."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_timelapse_overlay_config.return_value = (
                mock_overlay_service_responses["timelapse_config"]
            )
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/config/1")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["id"] == 1
            assert data["timelapse_id"] == 1
            assert data["preset_id"] == 1
            assert data["enabled"] is True
            assert "overlay_config" in data

            # Verify service was called
            mock_overlay_service.get_timelapse_overlay_config.assert_called_once_with(1)

    def test_get_timelapse_overlay_config_not_found(self, test_client):
        """Test getting configuration for timelapse with no overlay."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to return None
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_timelapse_overlay_config.return_value = None
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/config/999")

            # Assertions
            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_create_timelapse_overlay_config_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful timelapse overlay configuration creation."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.validate_overlay_configuration.return_value = True
            mock_overlay_service.create_or_update_timelapse_overlay_config.return_value = mock_overlay_service_responses[
                "timelapse_config"
            ]
            mock_service.return_value = mock_overlay_service

            # Request data
            config_data = {
                "preset_id": 1,
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                    "timestamp_position": "bottom_center",
                },
                "enabled": True,
            }

            # Make request
            response = test_client.post("/api/overlays/config/1", json=config_data)

            # Assertions
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()

            assert data["timelapse_id"] == 1
            assert data["preset_id"] == 1
            assert data["enabled"] is True

            # Verify service calls
            mock_overlay_service.validate_overlay_configuration.assert_called_once()
            mock_overlay_service.create_or_update_timelapse_overlay_config.assert_called_once()

    def test_update_timelapse_overlay_config_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful timelapse overlay configuration update."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_timelapse_overlay_config.return_value = (
                mock_overlay_service_responses["timelapse_config"]
            )
            mock_overlay_service.validate_overlay_configuration.return_value = True

            updated_config = mock_overlay_service_responses["timelapse_config"]
            updated_config.enabled = False
            mock_overlay_service.update_timelapse_overlay_config.return_value = (
                updated_config
            )
            mock_service.return_value = mock_overlay_service

            # Request data
            update_data = {
                "enabled": False,
            }

            # Make request
            response = test_client.put("/api/overlays/config/1", json=update_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["enabled"] is False

            # Verify service calls
            mock_overlay_service.get_timelapse_overlay_config.assert_called_once_with(1)
            mock_overlay_service.update_timelapse_overlay_config.assert_called_once()

    def test_delete_timelapse_overlay_config_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful timelapse overlay configuration deletion."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.delete_timelapse_overlay_config.return_value = True
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.delete("/api/overlays/config/1")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "deleted successfully" in data["message"]

            # Verify service was called
            mock_overlay_service.delete_timelapse_overlay_config.assert_called_once_with(
                1
            )

    # ============================================================================
    # ASSET MANAGEMENT ENDPOINT TESTS
    # ============================================================================

    def test_get_overlay_assets_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful retrieval of overlay assets."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_assets.return_value = (
                mock_overlay_service_responses["assets"]
            )
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/assets")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert len(data) == 2
            assert data[0]["name"] == "Company Logo"
            assert data[0]["mime_type"] == "image/png"
            assert data[1]["name"] == "Copyright Mark"

            # Verify service was called
            mock_overlay_service.get_overlay_assets.assert_called_once()

    def test_upload_overlay_asset_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful asset upload."""
        with patch("app.dependencies.get_overlay_service") as mock_service, patch(
            "app.utils.validation_helpers.process_overlay_asset_upload"
        ) as mock_process:

            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.upload_overlay_asset.return_value = (
                mock_overlay_service_responses["assets"][0]
            )
            mock_service.return_value = mock_overlay_service

            # Setup mock asset processing
            mock_process.return_value = {
                "asset_data": {
                    "name": "Test Logo",
                    "description": "Uploaded test logo",
                    "mime_type": "image/png",
                },
                "validated_file": MagicMock(),
            }

            # Create mock file upload
            test_file_content = b"fake_png_content"
            files = {
                "file": ("test_logo.png", io.BytesIO(test_file_content), "image/png")
            }
            data = {"name": "Test Logo"}

            # Make request
            response = test_client.post(
                "/api/overlays/assets/upload", files=files, data=data
            )

            # Assertions
            assert response.status_code == status.HTTP_201_CREATED
            response_data = response.json()

            assert response_data["id"] == 1
            assert response_data["name"] == "Company Logo"
            assert response_data["mime_type"] == "image/png"

            # Verify service calls
            mock_process.assert_called_once()
            mock_overlay_service.upload_overlay_asset.assert_called_once()

    def test_get_overlay_asset_file_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful asset file serving."""
        with patch("app.dependencies.get_overlay_service") as mock_service, patch(
            "app.utils.file_helpers.validate_file_path"
        ) as mock_validate, patch("pathlib.Path.exists") as mock_exists:

            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_asset_by_id.return_value = (
                mock_overlay_service_responses["assets"][0]
            )
            mock_service.return_value = mock_overlay_service

            # Setup file validation mocks
            mock_validate.return_value = True
            mock_exists.return_value = True

            # Make request
            response = test_client.get("/api/overlays/assets/1")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "image/png"

            # Verify service was called
            mock_overlay_service.get_overlay_asset_by_id.assert_called_once_with(1)

    def test_get_overlay_asset_file_not_found(self, test_client):
        """Test asset file serving when asset doesn't exist."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to return None
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_asset_by_id.return_value = None
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/assets/999")

            # Assertions
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_overlay_asset_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful asset deletion."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_asset_by_id.return_value = (
                mock_overlay_service_responses["assets"][0]
            )
            mock_overlay_service.delete_overlay_asset.return_value = True
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.delete("/api/overlays/assets/1")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "deleted successfully" in data["message"]

            # Verify service calls
            mock_overlay_service.get_overlay_asset_by_id.assert_called_once_with(1)
            mock_overlay_service.delete_overlay_asset.assert_called_once_with(1)

    # ============================================================================
    # PREVIEW GENERATION ENDPOINT TESTS
    # ============================================================================

    def test_generate_overlay_preview_success(self, test_client):
        """Test successful overlay preview generation."""
        with patch(
            "app.dependencies.get_overlay_service"
        ) as mock_overlay_service_dep, patch(
            "app.dependencies.get_overlay_job_service"
        ) as mock_job_service_dep:

            # Setup mock services
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.validate_overlay_configuration.return_value = True
            mock_overlay_service.generate_overlay_preview.return_value = type(
                "OverlayPreviewResponse",
                (),
                {
                    "success": True,
                    "preview_image_path": "/tmp/preview_123.jpg",
                    "message": "Preview generated successfully",
                    "camera_id": 1,
                    "processing_time_ms": 150,
                },
            )()

            mock_job_service = AsyncMock(spec=SyncOverlayJobService)

            mock_overlay_service_dep.return_value = mock_overlay_service
            mock_job_service_dep.return_value = mock_job_service

            # Request data
            preview_data = {
                "camera_id": 1,
                "overlay_config": {
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                    "timestamp_position": "bottom_right",
                },
            }

            # Make request
            response = test_client.post("/api/overlays/preview", json=preview_data)

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["success"] is True
            assert data["camera_id"] == 1
            assert data["preview_image_path"] == "/tmp/preview_123.jpg"
            assert data["processing_time_ms"] == 150

            # Verify service calls
            mock_overlay_service.validate_overlay_configuration.assert_called_once()
            mock_overlay_service.generate_overlay_preview.assert_called_once()

    def test_capture_fresh_photo_for_preview_success(self, test_client):
        """Test successful fresh photo capture for preview."""
        with patch(
            "app.dependencies.get_overlay_service"
        ) as mock_overlay_service_dep, patch(
            "app.dependencies.get_scheduler_service"
        ) as mock_scheduler_dep, patch(
            "pathlib.Path.exists"
        ) as mock_exists:

            # Setup mock services
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.capture_fresh_photo_for_preview.return_value = (
                "/tmp/temp_camera_1.jpg"
            )

            mock_scheduler_service = AsyncMock()
            mock_scheduler_service.schedule_immediate_capture.return_value = {
                "success": True
            }

            mock_overlay_service_dep.return_value = mock_overlay_service
            mock_scheduler_dep.return_value = mock_scheduler_service
            mock_exists.return_value = True

            # Make request
            response = test_client.post("/api/overlays/fresh-photo/1")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "image/jpeg"

            # Verify service calls
            mock_scheduler_service.schedule_immediate_capture.assert_called_once_with(
                camera_id=1,
                timelapse_id=-1,  # Special ID for preview captures
                priority="high",
            )
            mock_overlay_service.capture_fresh_photo_for_preview.assert_called_once_with(
                1
            )

    def test_capture_fresh_photo_scheduler_failure(self, test_client):
        """Test fresh photo capture when scheduler fails."""
        with patch(
            "app.dependencies.get_overlay_service"
        ) as mock_overlay_service_dep, patch(
            "app.dependencies.get_scheduler_service"
        ) as mock_scheduler_dep:

            # Setup mock services
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)

            mock_scheduler_service = AsyncMock()
            mock_scheduler_service.schedule_immediate_capture.return_value = {
                "success": False,
                "error": "Camera offline",
            }

            mock_overlay_service_dep.return_value = mock_overlay_service
            mock_scheduler_dep.return_value = mock_scheduler_service

            # Make request
            response = test_client.post("/api/overlays/fresh-photo/1")

            # Assertions
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "Failed to schedule camera capture" in data["detail"]

    # ============================================================================
    # SYSTEM STATUS ENDPOINT TESTS
    # ============================================================================

    def test_get_overlay_system_status_success(
        self, test_client, mock_overlay_service_responses
    ):
        """Test successful system status retrieval."""
        with patch(
            "app.dependencies.get_overlay_service"
        ) as mock_overlay_service_dep, patch(
            "app.dependencies.get_overlay_job_service"
        ) as mock_job_service_dep:

            # Setup mock services
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_presets.return_value = (
                mock_overlay_service_responses["all_presets"]
            )
            mock_overlay_service.get_overlay_assets.return_value = (
                mock_overlay_service_responses["assets"]
            )

            mock_job_service = AsyncMock(spec=SyncOverlayJobService)
            mock_job_service.get_job_statistics.return_value = type(
                "OverlayJobStatistics",
                (),
                {
                    "pending_jobs": 5,
                    "processing_jobs": 2,
                    "completed_jobs_24h": 150,
                    "failed_jobs_24h": 3,
                },
            )()

            mock_overlay_service_dep.return_value = mock_overlay_service
            mock_job_service_dep.return_value = mock_job_service

            # Make request
            response = test_client.get("/api/overlays/status")

            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "healthy"
            assert data["system_health"] == "operational"

            # Check presets data
            assert data["presets"]["total"] == 3
            assert data["presets"]["builtin"] == 2
            assert data["presets"]["custom"] == 1

            # Check assets data
            assert data["assets"]["total"] == 2

            # Check job queue data
            assert data["job_queue"]["pending"] == 5
            assert data["job_queue"]["processing"] == 2
            assert data["job_queue"]["completed_today"] == 150
            assert data["job_queue"]["failed_today"] == 3

            # Verify service calls
            mock_overlay_service.get_overlay_presets.assert_called_once()
            mock_overlay_service.get_overlay_assets.assert_called_once()
            mock_job_service.get_job_statistics.assert_called_once()

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_invalid_request_validation(self, test_client):
        """Test request validation for invalid data."""
        # Test invalid preset creation with missing required fields
        response = test_client.post(
            "/api/overlays/presets",
            json={
                "name": "",  # Empty name
                "overlay_config": {},  # Empty config
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_service_error_handling(self, test_client):
        """Test handling of service layer errors."""
        with patch("app.dependencies.get_overlay_service") as mock_service:
            # Setup mock service to raise exception
            mock_overlay_service = AsyncMock(spec=OverlayIntegrationService)
            mock_overlay_service.get_overlay_presets.side_effect = Exception(
                "Database connection failed"
            )
            mock_service.return_value = mock_overlay_service

            # Make request
            response = test_client.get("/api/overlays/presets")

            # Should be handled by exception middleware
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_authentication_required(self, test_client):
        """Test that endpoints require authentication (if implemented)."""
        # This test would verify authentication middleware
        # For now, we assume endpoints are accessible for testing
        # In production, you'd test with/without auth tokens
        pass
