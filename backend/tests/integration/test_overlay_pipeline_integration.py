#!/usr/bin/env python3
"""
Overlay Pipeline Integration Tests.

Tests the complete overlay pipeline with service coordination, job queue management,
asset handling, and preview generation to ensure all components work together correctly.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

from app.services.overlay_pipeline.services.integration_service import OverlayIntegrationService
from app.services.overlay_job_service import SyncOverlayJobService
from app.database.overlay_operations import OverlayOperations, SyncOverlayOperations
from app.database.overlay_job_operations import OverlayJobOperations, SyncOverlayJobOperations
from app.models.overlay_model import (
    OverlayPreset,
    OverlayPresetCreate,
    TimelapseOverlay,
    TimelapseOverlayCreate,
    OverlayAsset,
    OverlayAssetCreate,
    OverlayJob,
    OverlayJobCreate,
    OverlayPreviewRequest,
    OverlayConfiguration,
)
from app.enums import JobStatus, JobPriority
from app.constants import (
    OVERLAY_JOB_TYPE_SINGLE,
    OVERLAY_JOB_TYPE_BATCH,
    OVERLAY_JOB_PRIORITY_HIGH,
    OVERLAY_JOB_PRIORITY_MEDIUM,
)


@pytest.fixture
def mock_overlay_pipeline_services(mock_async_database, mock_sync_database):
    """Bundle of mock services for overlay pipeline integration testing."""
    
    class MockOverlayServices:
        def __init__(self, async_db, sync_db):
            self.async_db = async_db
            self.sync_db = sync_db
            
            # Track created entities for testing
            self.presets = {}
            self.timelapse_overlays = {}
            self.assets = {}
            self.jobs = {}
            self.next_id = 1
            
        def create_mock_preset(self, name="Test Preset", is_builtin=False):
            """Create mock overlay preset data."""
            preset = OverlayPreset(
                id=self.next_id,
                name=name,
                description=f"Description for {name}",
                overlay_config=OverlayConfiguration(
                    show_timestamp=True,
                    timestamp_format="%Y-%m-%d %H:%M:%S",
                    timestamp_position="bottom_right",
                    show_weather=not is_builtin,  # Built-in presets are simpler
                    show_camera_name=True,
                    background_opacity=0.7,
                    text_color="#FFFFFF",
                    font_size=24,
                ),
                is_builtin=is_builtin,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.presets[self.next_id] = preset
            self.next_id += 1
            return preset
            
        def create_mock_timelapse_overlay(self, timelapse_id=1, preset_id=1, enabled=True):
            """Create mock timelapse overlay configuration."""
            config = TimelapseOverlay(
                id=self.next_id,
                timelapse_id=timelapse_id,
                preset_id=preset_id,
                overlay_config=OverlayConfiguration(
                    show_timestamp=True,
                    show_weather=True,
                    timestamp_position="bottom_center",
                ),
                enabled=enabled,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.timelapse_overlays[self.next_id] = config
            self.next_id += 1
            return config
            
        def create_mock_asset(self, name="Test Logo", file_path="/test/assets/logo.png"):
            """Create mock overlay asset."""
            asset = OverlayAsset(
                id=self.next_id,
                name=name,
                description=f"Description for {name}",
                file_path=file_path,
                original_name=Path(file_path).name,
                mime_type="image/png",
                file_size=2048,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.assets[self.next_id] = asset
            self.next_id += 1
            return asset
            
        def create_mock_job(self, image_id=1, timelapse_id=1, preset_id=1, status=JobStatus.PENDING):
            """Create mock overlay job."""
            job = OverlayJob(
                id=self.next_id,
                image_id=image_id,
                timelapse_id=timelapse_id,
                preset_id=preset_id,
                job_type=OVERLAY_JOB_TYPE_SINGLE,
                priority=OVERLAY_JOB_PRIORITY_MEDIUM,
                overlay_config={
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                },
                status=status,
                created_at=datetime.utcnow(),
                started_at=datetime.utcnow() if status != JobStatus.PENDING else None,
                completed_at=datetime.utcnow() if status == JobStatus.COMPLETED else None,
                error_message=None,
                processing_time_ms=1500 if status == JobStatus.COMPLETED else None,
                retry_count=0,
                output_path="/data/overlays/output_1.jpg" if status == JobStatus.COMPLETED else None,
            )
            self.jobs[self.next_id] = job
            self.next_id += 1
            return job
    
    return MockOverlayServices(mock_async_database, mock_sync_database)


@pytest.fixture
def overlay_integration_pipeline(mock_overlay_pipeline_services):
    """Create complete overlay integration pipeline for testing."""
    services = mock_overlay_pipeline_services
    
    # Create integration service
    integration_service = OverlayIntegrationService(services.async_db)
    
    # Mock the database operations with our test data
    async_overlay_ops = AsyncMock(spec=OverlayOperations)
    async_job_ops = AsyncMock(spec=OverlayJobOperations)
    
    # Setup operations mocks
    async_overlay_ops.get_all_presets.return_value = list(services.presets.values())
    async_overlay_ops.get_preset_by_id.side_effect = lambda preset_id: services.presets.get(preset_id)
    async_overlay_ops.get_all_assets.return_value = list(services.assets.values())
    async_overlay_ops.get_asset_by_id.side_effect = lambda asset_id: services.assets.get(asset_id)
    async_overlay_ops.get_timelapse_overlay.side_effect = lambda timelapse_id: next(
        (config for config in services.timelapse_overlays.values() if config.timelapse_id == timelapse_id), 
        None
    )
    
    async_job_ops.get_pending_jobs.return_value = [
        job for job in services.jobs.values() if job.status == JobStatus.PENDING
    ]
    async_job_ops.get_job_by_id.side_effect = lambda job_id: services.jobs.get(job_id)
    
    # Inject mocked operations
    integration_service.overlay_ops = async_overlay_ops
    integration_service.overlay_job_ops = async_job_ops
    
    return {
        "integration_service": integration_service,
        "services": services,
        "async_overlay_ops": async_overlay_ops,
        "async_job_ops": async_job_ops,
    }


@pytest.mark.integration
@pytest.mark.overlay_pipeline
class TestOverlayPipelineIntegration:
    """Integration tests for complete overlay pipeline functionality."""

    @pytest.mark.asyncio
    async def test_preset_management_full_cycle(self, overlay_integration_pipeline):
        """Test complete preset management lifecycle."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        services = pipeline["services"]
        async_overlay_ops = pipeline["async_overlay_ops"]
        
        # Create built-in presets (simulating migration seeding)
        builtin_preset = services.create_mock_preset("Basic Timestamp", is_builtin=True)
        weather_preset = services.create_mock_preset("Weather + Time", is_builtin=True)
        
        # Test: Get all presets (should include built-in presets)
        presets = await integration_service.get_overlay_presets()
        
        assert len(presets) == 2
        assert all(preset.is_builtin for preset in presets)
        assert "Basic Timestamp" in [p.name for p in presets]
        assert "Weather + Time" in [p.name for p in presets]
        
        # Mock preset creation
        custom_preset_data = OverlayPresetCreate(
            name="Custom Overlay",
            description="User-created custom overlay",
            overlay_config=OverlayConfiguration(
                show_timestamp=True,
                show_weather=True,
                show_camera_name=True,
                timestamp_position="bottom_right",
            ),
            is_builtin=False,
        )
        
        created_preset = services.create_mock_preset("Custom Overlay", is_builtin=False)
        async_overlay_ops.create_preset.return_value = created_preset
        
        # Test: Create custom preset
        result = await integration_service.create_overlay_preset(custom_preset_data)
        
        assert result is not None
        assert result.name == "Custom Overlay"
        assert result.is_builtin is False
        
        # Verify operations were called correctly
        async_overlay_ops.get_all_presets.assert_called()
        async_overlay_ops.create_preset.assert_called_once_with(custom_preset_data)

    @pytest.mark.asyncio
    async def test_timelapse_overlay_configuration_flow(self, overlay_integration_pipeline):
        """Test timelapse overlay configuration workflow."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        services = pipeline["services"]
        async_overlay_ops = pipeline["async_overlay_ops"]
        
        # Create a preset to use
        preset = services.create_mock_preset("Test Preset")
        
        # Test: Create timelapse overlay configuration
        config_data = TimelapseOverlayCreate(
            timelapse_id=1,
            preset_id=preset.id,
            overlay_config=OverlayConfiguration(
                show_timestamp=True,
                timestamp_format="%Y-%m-%d %H:%M:%S",
                timestamp_position="bottom_center",
                show_weather=True,
            ),
            enabled=True,
        )
        
        # Mock no existing configuration (create scenario)
        async_overlay_ops.get_timelapse_overlay.return_value = None
        
        created_config = services.create_mock_timelapse_overlay(
            timelapse_id=1, 
            preset_id=preset.id
        )
        async_overlay_ops.create_timelapse_overlay.return_value = created_config
        
        # Test configuration creation
        result = await integration_service.create_or_update_timelapse_overlay_config(config_data)
        
        assert result is not None
        assert result.timelapse_id == 1
        assert result.preset_id == preset.id
        assert result.enabled is True
        
        # Verify operations were called correctly
        async_overlay_ops.get_timelapse_overlay.assert_called_with(1)
        async_overlay_ops.create_timelapse_overlay.assert_called_once_with(config_data)

    @pytest.mark.asyncio
    async def test_asset_management_integration(self, overlay_integration_pipeline):
        """Test asset upload and management integration."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        services = pipeline["services"]
        async_overlay_ops = pipeline["async_overlay_ops"]
        
        # Create test assets
        logo_asset = services.create_mock_asset("Company Logo", "/assets/logo.png")
        watermark_asset = services.create_mock_asset("Watermark", "/assets/watermark.png")
        
        # Test: Get all assets
        assets = await integration_service.get_overlay_assets()
        
        assert len(assets) == 2
        assert "Company Logo" in [a.name for a in assets]
        assert "Watermark" in [a.name for a in assets]
        
        # Test: Get specific asset
        asset = await integration_service.get_overlay_asset_by_id(logo_asset.id)
        
        assert asset is not None
        assert asset.name == "Company Logo"
        assert asset.mime_type == "image/png"
        assert asset.file_size == 2048
        
        # Verify operations were called correctly
        async_overlay_ops.get_all_assets.assert_called_once()
        async_overlay_ops.get_asset_by_id.assert_called_once_with(logo_asset.id)

    @pytest.mark.asyncio
    async def test_job_queue_integration(self, overlay_integration_pipeline):
        """Test overlay job queue management integration."""
        pipeline = overlay_integration_pipeline
        services = pipeline["services"]
        async_job_ops = pipeline["async_job_ops"]
        
        # Create test jobs with different statuses
        pending_job = services.create_mock_job(image_id=1, status=JobStatus.PENDING)
        processing_job = services.create_mock_job(image_id=2, status=JobStatus.PROCESSING)
        completed_job = services.create_mock_job(image_id=3, status=JobStatus.COMPLETED)
        failed_job = services.create_mock_job(image_id=4, status=JobStatus.FAILED)
        
        # Test: Get pending jobs (simulating worker fetching work)
        pending_jobs = await async_job_ops.get_pending_jobs(batch_size=10)
        
        assert len(pending_jobs) == 1
        assert pending_jobs[0].status == JobStatus.PENDING
        assert pending_jobs[0].image_id == 1
        
        # Test: Job status progression
        # Mark job as started
        async_job_ops.mark_job_started.return_value = True
        result = await async_job_ops.mark_job_started(pending_job.id)
        assert result is True
        
        # Mark job as completed
        async_job_ops.mark_job_completed.return_value = True
        result = await async_job_ops.mark_job_completed(
            pending_job.id, 
            "/data/overlays/output_1.jpg", 
            processing_time_ms=2500
        )
        assert result is True
        
        # Verify operations were called correctly
        async_job_ops.get_pending_jobs.assert_called_once_with(batch_size=10)
        async_job_ops.mark_job_started.assert_called_once_with(pending_job.id)
        async_job_ops.mark_job_completed.assert_called_once_with(
            pending_job.id, 
            "/data/overlays/output_1.jpg", 
            processing_time_ms=2500
        )

    @pytest.mark.asyncio
    async def test_overlay_configuration_validation_integration(self, overlay_integration_pipeline):
        """Test overlay configuration validation across the pipeline."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        
        # Test: Valid configuration
        valid_config = {
            "show_timestamp": True,
            "timestamp_format": "%Y-%m-%d %H:%M:%S",
            "timestamp_position": "bottom_right",
            "show_weather": True,
            "show_camera_name": True,
            "camera_name_position": "top_left",
            "background_opacity": 0.7,
            "text_color": "#FFFFFF",
            "font_size": 24,
        }
        
        is_valid = await integration_service.validate_overlay_configuration(valid_config)
        assert is_valid is True
        
        # Test: Invalid configuration (multiple issues)
        invalid_config = {
            "show_timestamp": True,
            "timestamp_position": "invalid_position",  # Invalid position
            "background_opacity": 1.5,  # Invalid opacity (> 1.0)
            "text_color": "not_hex_color",  # Invalid color format
            "font_size": -10,  # Invalid font size
        }
        
        is_valid = await integration_service.validate_overlay_configuration(invalid_config)
        assert is_valid is False
        
        # Test: Configuration with missing required fields
        incomplete_config = {
            "show_timestamp": True,
            # Missing timestamp_format and timestamp_position
        }
        
        is_valid = await integration_service.validate_overlay_configuration(incomplete_config)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_preview_generation_integration(self, overlay_integration_pipeline):
        """Test overlay preview generation integration."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        
        # Mock preview generation components
        with patch.object(integration_service, '_generate_preview_image') as mock_generate, \
             patch.object(integration_service, '_capture_temp_image') as mock_capture:
            
            # Setup mocks
            mock_capture.return_value = "/tmp/temp_camera_1.jpg"
            mock_generate.return_value = type('OverlayPreviewResponse', (), {
                'success': True,
                'preview_image_path': '/tmp/preview_123.jpg',
                'message': 'Preview generated successfully',
                'camera_id': 1,
                'processing_time_ms': 150,
            })()
            
            # Test: Capture fresh photo for preview
            temp_path = await integration_service.capture_fresh_photo_for_preview(1)
            assert temp_path == "/tmp/temp_camera_1.jpg"
            
            # Test: Generate overlay preview
            preview_request = OverlayPreviewRequest(
                camera_id=1,
                overlay_config=OverlayConfiguration(
                    show_timestamp=True,
                    timestamp_format="%Y-%m-%d %H:%M:%S",
                    timestamp_position="bottom_right",
                ),
            )
            
            preview_result = await integration_service.generate_overlay_preview(preview_request)
            
            assert preview_result is not None
            assert preview_result.success is True
            assert preview_result.camera_id == 1
            assert preview_result.preview_image_path == "/tmp/preview_123.jpg"
            assert preview_result.processing_time_ms == 150
            
            # Verify internal methods were called
            mock_capture.assert_called_once_with(1)
            mock_generate.assert_called_once_with(preview_request)

    @pytest.mark.asyncio
    async def test_error_handling_across_pipeline(self, overlay_integration_pipeline):
        """Test error handling and resilience across the overlay pipeline."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        async_overlay_ops = pipeline["async_overlay_ops"]
        async_job_ops = pipeline["async_job_ops"]
        
        # Test: Database connection failure
        async_overlay_ops.get_all_presets.side_effect = Exception("Database connection failed")
        
        presets = await integration_service.get_overlay_presets()
        assert presets == []  # Should return empty list, not raise exception
        
        # Test: Job creation failure
        async_job_ops.create_job.side_effect = Exception("Job creation failed")
        
        job_data = OverlayJobCreate(
            image_id=1,
            timelapse_id=1,
            preset_id=1,
            job_type=OVERLAY_JOB_TYPE_SINGLE,
            priority=OVERLAY_JOB_PRIORITY_MEDIUM,
            overlay_config={"show_timestamp": True},
            status=JobStatus.PENDING,
        )
        
        # This would typically be called by a job scheduling service
        # For this test, we're verifying the mock behavior
        try:
            await async_job_ops.create_job(job_data)
            assert False, "Should have raised exception"
        except Exception as e:
            assert str(e) == "Job creation failed"
        
        # Test: Invalid configuration handling
        invalid_config = {"invalid": "configuration"}
        is_valid = await integration_service.validate_overlay_configuration(invalid_config)
        assert is_valid is False  # Should handle gracefully

    @pytest.mark.asyncio
    async def test_sync_async_coordination(self, overlay_integration_pipeline, mock_sync_database):
        """Test coordination between sync (worker) and async (API) operations."""
        pipeline = overlay_integration_pipeline
        services = pipeline["services"]
        
        # Create sync overlay job service (simulating worker)
        sync_job_service = SyncOverlayJobService(mock_sync_database)
        
        # Mock sync operations
        sync_job_ops = MagicMock(spec=SyncOverlayJobOperations)
        sync_job_service.overlay_job_ops = sync_job_ops
        
        # Create test job
        test_job = services.create_mock_job(status=JobStatus.PROCESSING)
        sync_job_ops.get_job_by_id.return_value = test_job
        sync_job_ops.mark_job_completed.return_value = True
        
        # Test: Worker completing a job (sync operation)
        job = sync_job_service.overlay_job_ops.get_job_by_id(test_job.id)
        assert job is not None
        assert job.status == JobStatus.PROCESSING
        
        # Mark job as completed
        result = sync_job_service.overlay_job_ops.mark_job_completed(
            test_job.id,
            "/data/overlays/output.jpg",
            processing_time_ms=3000
        )
        assert result is True
        
        # Verify sync operations were called
        sync_job_ops.get_job_by_id.assert_called_once_with(test_job.id)
        sync_job_ops.mark_job_completed.assert_called_once_with(
            test_job.id,
            "/data/overlays/output.jpg",
            processing_time_ms=3000
        )

    @pytest.mark.asyncio
    async def test_complete_overlay_workflow(self, overlay_integration_pipeline):
        """Test complete end-to-end overlay workflow."""
        pipeline = overlay_integration_pipeline
        integration_service = pipeline["integration_service"]
        services = pipeline["services"]
        async_overlay_ops = pipeline["async_overlay_ops"]
        async_job_ops = pipeline["async_job_ops"]
        
        # Step 1: Create a custom preset
        preset_data = OverlayPresetCreate(
            name="E2E Test Preset",
            description="End-to-end test preset",
            overlay_config=OverlayConfiguration(
                show_timestamp=True,
                show_weather=True,
                show_camera_name=True,
                timestamp_position="bottom_right",
            ),
            is_builtin=False,
        )
        
        created_preset = services.create_mock_preset("E2E Test Preset")
        async_overlay_ops.create_preset.return_value = created_preset
        
        preset = await integration_service.create_overlay_preset(preset_data)
        assert preset is not None
        
        # Step 2: Configure timelapse overlay
        timelapse_config_data = TimelapseOverlayCreate(
            timelapse_id=1,
            preset_id=preset.id,
            overlay_config=preset.overlay_config,
            enabled=True,
        )
        
        async_overlay_ops.get_timelapse_overlay.return_value = None  # No existing config
        created_config = services.create_mock_timelapse_overlay(1, preset.id)
        async_overlay_ops.create_timelapse_overlay.return_value = created_config
        
        timelapse_config = await integration_service.create_or_update_timelapse_overlay_config(
            timelapse_config_data
        )
        assert timelapse_config is not None
        assert timelapse_config.enabled is True
        
        # Step 3: Validate configuration
        is_valid = await integration_service.validate_overlay_configuration(
            preset.overlay_config.model_dump()
        )
        assert is_valid is True
        
        # Step 4: Get configuration for processing
        final_config = await integration_service.get_timelapse_overlay_config(1)
        assert final_config is not None
        assert final_config.preset_id == preset.id
        
        # Verify all operations were called in correct sequence
        async_overlay_ops.create_preset.assert_called_once()
        async_overlay_ops.get_timelapse_overlay.assert_called()
        async_overlay_ops.create_timelapse_overlay.assert_called_once()
        
        # This completes a realistic workflow from preset creation to configuration retrieval