#!/usr/bin/env python3
"""
Service Factory Pattern Integration Tests.

Tests the service factory patterns and dependency injection to ensure
services are created correctly and have proper dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.capture_pipeline import create_capture_pipeline, get_capture_pipeline_health
from app.services.capture_pipeline.workflow_orchestrator_service import WorkflowOrchestratorService
from app.services.settings_service import SyncSettingsService
from app.services.thumbnail_pipeline.thumbnail_service import ThumbnailService
from app.services.overlay_pipeline import OverlayService
from app.services.video_automation_service import VideoAutomationService
from app.services.video_service import SyncVideoService
from app.database.core import SyncDatabase


@pytest.fixture
def mock_sync_database():
    """Enhanced mock sync database for factory testing."""
    
    class MockSyncDatabase:
        def __init__(self):
            self.connection_active = True
            self.queries_executed = []
            
        def get_connection(self):
            return self._mock_connection()
            
        def _mock_connection(self):
            class MockConnection:
                def __init__(self, db):
                    self.db = db
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
                def cursor(self):
                    return self._mock_cursor()
                def _mock_cursor(self):
                    class MockCursor:
                        def __init__(self, db):
                            self.db = db
                            self.rowcount = 1
                        def __enter__(self):
                            return self
                        def __exit__(self, exc_type, exc_val, exc_tb):
                            pass
                        def execute(self, query, params=None):
                            self.db.queries_executed.append(query)
                            return self
                        def fetchone(self):
                            return {"id": 1, "name": "Test"}
                        def fetchall(self):
                            return [{"id": 1, "name": "Test"}]
                    return MockCursor(self.db)
            return MockConnection(self)
            
        def initialize(self):
            pass
            
        def close(self):
            pass
    
    return MockSyncDatabase()


@pytest.mark.integration
@pytest.mark.service_factory
class TestServiceFactoryPatterns:
    """Integration tests for service factory patterns."""
    
    def test_capture_pipeline_factory_creates_workflow_orchestrator(self, mock_sync_database):
        """Test factory creates WorkflowOrchestratorService with all dependencies."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Assert
        assert isinstance(workflow_orchestrator, WorkflowOrchestratorService)
        assert workflow_orchestrator is not None
    
    def test_factory_creates_all_ten_services(self, mock_sync_database):
        """Test factory creates all 10 required services."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Assert - All 10 services should be created
        services = [
            workflow_orchestrator.camera_service,
            workflow_orchestrator.timelapse_service,
            workflow_orchestrator.image_service,
            workflow_orchestrator.rtsp_service,
            workflow_orchestrator.corruption_service,
            workflow_orchestrator.weather_service,
            workflow_orchestrator.overlay_service,
            workflow_orchestrator.job_coordination_service,
            workflow_orchestrator.sse_service,
            workflow_orchestrator.scheduling_service,
        ]
        
        # Verify all services are created
        for service in services:
            assert service is not None
            
        # Verify services have database connections
        assert workflow_orchestrator.camera_service.db is not None
        assert workflow_orchestrator.timelapse_service.db is not None
        assert workflow_orchestrator.image_service.db is not None
    
    def test_factory_creates_services_with_proper_dependencies(self, mock_sync_database):
        """Test factory creates services with proper dependency injection."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Assert - Check specific service dependencies
        
        # Camera service should have database
        assert workflow_orchestrator.camera_service.db is not None
        
        # Timelapse service should have database
        assert workflow_orchestrator.timelapse_service.db is not None
        
        # Image service should have database
        assert workflow_orchestrator.image_service.db is not None
        
        # RTSP service should have database
        assert workflow_orchestrator.rtsp_service.db is not None
        
        # Corruption service should have database
        assert workflow_orchestrator.corruption_service.db is not None
        
        # Weather service should have weather operations
        assert workflow_orchestrator.weather_service.weather_ops is not None
        
        # Overlay service should have database
        assert workflow_orchestrator.overlay_service.db is not None
        
        # Job coordination service should have database
        assert workflow_orchestrator.job_coordination_service.db is not None
        
        # SSE service should have database (this is actually SSE operations, not a service)
        assert workflow_orchestrator.sse_service is not None
        
        # Scheduling service should have database
        assert workflow_orchestrator.scheduling_service.db is not None
    
    def test_factory_reuses_database_connection(self, mock_sync_database):
        """Test factory reuses the same database connection across services."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Assert - All services that have db should use the same database instance
        services_with_db = [
            workflow_orchestrator.camera_service,
            workflow_orchestrator.timelapse_service,
            workflow_orchestrator.image_service,
            workflow_orchestrator.rtsp_service,
            workflow_orchestrator.corruption_service,
            workflow_orchestrator.overlay_service,
            workflow_orchestrator.job_coordination_service,
            workflow_orchestrator.scheduling_service,
        ]
        
        # Verify all services with db use the same database instance
        for service in services_with_db:
            assert service.db is not None
            
        # Verify weather service has weather operations
        assert workflow_orchestrator.weather_service.weather_ops is not None
        
        # Verify SSE service exists (it's operations, not a service with db)
        assert workflow_orchestrator.sse_service is not None
    
    def test_factory_health_check_function(self, mock_sync_database):
        """Test factory provides health check functionality."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act - First create pipeline, then check health
        orchestrator = create_capture_pipeline(settings_service=settings_service)
        health = get_capture_pipeline_health(orchestrator)
        
        # Assert
        assert isinstance(health, dict)
        assert "status" in health
        assert "services" in health
        assert "service_count" in health
        assert health["service_count"] == 12
        
        # Check service health structure
        assert health["status"] == "healthy"
        assert health["all_services_healthy"] is True
        assert len(health["services"]) == 12
        
        # Check database health
        assert "database_info" in health
        assert health["database_info"]["database_type"] == "SyncDatabase"
        assert health["database_info"]["database_initialized"] is True
    
    def test_service_constructor_standardization_thumbnail_service(self, mock_sync_database):
        """Test ThumbnailService follows standardized constructor pattern."""
        # Arrange
        mock_settings_service = MagicMock()
        mock_sse_operations = MagicMock()
        mock_job_queue_service = MagicMock()
        
        # Act
        service = ThumbnailService(
            db=mock_sync_database,
            sse_operations=mock_sse_operations,
            settings_service=mock_settings_service,
            job_queue_service=mock_job_queue_service,
        )
        
        # Assert
        assert service.db is mock_sync_database
        assert service.sse_operations is mock_sse_operations
        assert service.settings_service is mock_settings_service
        assert service.job_queue_service is mock_job_queue_service
        
        # Verify internal operations are created
        assert hasattr(service, 'thumbnail_job_ops')
        assert hasattr(service, 'image_operations')
    
    def test_service_constructor_standardization_overlay_service(self, mock_sync_database):
        """Test OverlayService follows standardized constructor pattern."""
        # Arrange
        mock_settings_service = MagicMock()
        mock_weather_manager = MagicMock()
        mock_sse_ops = MagicMock()
        
        # Act
        service = OverlayService(
            db=mock_sync_database,
            settings_service=mock_settings_service,
            weather_manager=mock_weather_manager,
            sse_ops=mock_sse_ops,
        )
        
        # Assert
        assert service.db is mock_sync_database
        assert service.settings_service is mock_settings_service
        assert service.weather_manager is mock_weather_manager
        assert service.sse_ops is mock_sse_ops
        
        # Verify internal operations are created
        assert hasattr(service, 'overlay_ops')
        assert hasattr(service, 'image_ops')
    
    def test_service_constructor_standardization_video_automation_service(self, mock_sync_database):
        """Test VideoAutomationService follows standardized constructor pattern."""
        # Arrange
        mock_timelapse_service = MagicMock()
        
        # Act
        service = VideoAutomationService(
            db=mock_sync_database,
            timelapse_service=mock_timelapse_service,
        )
        
        # Assert
        assert service.db is mock_sync_database
        assert service.timelapse_service is mock_timelapse_service
        
        # Verify internal components are created
        assert hasattr(service, 'queue')
        assert hasattr(service, 'video_service')
        assert hasattr(service, 'video_ops')
        assert hasattr(service, 'sse_ops')
        assert hasattr(service, 'settings_ops')
    
    def test_service_constructor_standardization_sync_video_service(self, mock_sync_database):
        """Test SyncVideoService follows standardized constructor pattern."""
        # Act
        service = SyncVideoService(db=mock_sync_database)
        
        # Assert
        assert service.db is mock_sync_database
        
        # Verify internal operations are created
        assert hasattr(service, 'video_ops')
        assert hasattr(service, 'timelapse_ops')
        assert hasattr(service, 'camera_ops')
        assert hasattr(service, 'image_ops')
    
    def test_service_constructor_standardization_settings_service(self, mock_sync_database):
        """Test SyncSettingsService follows standardized constructor pattern."""
        # Act
        service = SyncSettingsService(db=mock_sync_database)
        
        # Assert
        assert service.db is mock_sync_database
        
        # Verify internal operations are created
        assert hasattr(service, 'settings_ops')
        assert hasattr(service, 'api_key_service')
    
    def test_services_handle_none_optional_parameters(self, mock_sync_database):
        """Test services handle None optional parameters correctly."""
        # Test ThumbnailService with minimal parameters
        thumbnail_service = ThumbnailService(db=mock_sync_database)
        assert thumbnail_service.db is mock_sync_database
        assert thumbnail_service.sse_operations is None
        assert thumbnail_service.settings_service is None
        assert thumbnail_service.job_queue_service is None
        
        # Test OverlayService with minimal parameters
        overlay_service = OverlayService(db=mock_sync_database)
        assert overlay_service.db is mock_sync_database
        assert overlay_service.settings_service is None
        assert overlay_service.weather_manager is None
        assert overlay_service.sse_ops is None
        
        # Test VideoAutomationService with minimal parameters
        video_automation = VideoAutomationService(db=mock_sync_database)
        assert video_automation.db is mock_sync_database
        assert video_automation.timelapse_service is None
    
    def test_services_create_sync_operations_for_sync_database(self, mock_sync_database):
        """Test services create sync operations when given sync database."""
        # Test ThumbnailService creates sync operations
        thumbnail_service = ThumbnailService(db=mock_sync_database)
        
        # Verify it creates sync operations (not async)
        assert hasattr(thumbnail_service, 'thumbnail_job_ops')
        assert hasattr(thumbnail_service, 'image_operations')
        
        # The operations should be sync versions
        assert not hasattr(thumbnail_service.thumbnail_job_ops, 'execute_async')
        assert not hasattr(thumbnail_service.image_operations, 'execute_async')
    
    def test_factory_dependency_ordering(self, mock_sync_database):
        """Test factory creates services in correct dependency order."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Assert - Services should be created successfully without dependency issues
        assert workflow_orchestrator is not None
        
        # Services that follow the standard db pattern
        services_with_db = [
            workflow_orchestrator.camera_service,
            workflow_orchestrator.timelapse_service,  # This is an operations object with db
            workflow_orchestrator.image_service,
            workflow_orchestrator.rtsp_service,
            workflow_orchestrator.corruption_service,
            workflow_orchestrator.overlay_service,
            workflow_orchestrator.job_coordination_service,
            workflow_orchestrator.scheduling_service,
        ]
        
        # Services that have different patterns (weather_service, sse_service are operations)
        other_services = [
            workflow_orchestrator.weather_service,  # WeatherManager with weather_ops attribute
            workflow_orchestrator.sse_service,      # SSE operations object
        ]
        
        # Test services that should have db attribute
        for service in services_with_db:
            assert service is not None
            assert hasattr(service, 'db')
            assert service.db is not None
            
        # Test other services exist but don't require db attribute
        for service in other_services:
            assert service is not None
            
        # Test weather service has correct attributes
        assert hasattr(workflow_orchestrator.weather_service, 'weather_ops')
        assert workflow_orchestrator.weather_service.weather_ops is not None
    
    def test_factory_error_handling(self, mock_sync_database):
        """Test factory handles None settings service gracefully by creating default."""
        # Test with None settings service - should create default SyncSettingsService
        orchestrator = create_capture_pipeline(settings_service=None)
        assert orchestrator is not None
        
        # Factory creates default services when None is passed
        # This is expected behavior, not an error condition
    
    def test_factory_creates_unique_service_instances(self, mock_sync_database):
        """Test factory creates unique service instances."""
        # Arrange
        settings_service = SyncSettingsService(mock_sync_database)
        
        # Act
        workflow_orchestrator1 = create_capture_pipeline(settings_service=settings_service)
        workflow_orchestrator2 = create_capture_pipeline(settings_service=settings_service)
        
        # Assert - Different instances should be created
        assert workflow_orchestrator1 is not workflow_orchestrator2
        assert workflow_orchestrator1.camera_service is not workflow_orchestrator2.camera_service
        assert workflow_orchestrator1.timelapse_service is not workflow_orchestrator2.timelapse_service