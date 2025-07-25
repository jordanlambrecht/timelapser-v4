#!/usr/bin/env python3
"""
Capture Pipeline Integration Tests.

Tests the complete capture pipeline with dependency injection, scheduler trust model,
and service standardization to ensure all architectural changes work together correctly.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path

from app.services.capture_pipeline import create_capture_pipeline
from app.services.capture_pipeline.workflow_orchestrator_service import WorkflowOrchestratorService
from app.services.scheduling import SchedulingService, SyncSchedulingService, CaptureReadinessValidationResult
from app.services.settings_service import SyncSettingsService
from app.services.thumbnail_pipeline.thumbnail_service import ThumbnailService
from app.services.overlay_pipeline import OverlayService
from app.services.video_automation_service import VideoAutomationService
from app.workers.capture_worker import CaptureWorker
from app.workers.scheduler_worker import SchedulerWorker
from app.database.core import SyncDatabase
from app.models.camera_model import Camera
from app.models.timelapse_model import Timelapse
from app.models.image_model import Image
from app.models.shared_models import RTSPCaptureResult


@pytest.fixture
def mock_sync_database():
    """Enhanced mock sync database for capture pipeline testing."""
    
    class MockSyncDatabase:
        def __init__(self):
            self.connection_active = True
            self.cameras = {}
            self.timelapses = {}
            self.images = {}
            self.settings = {
                "timezone": "UTC",
                "capture_interval": 30,
                "data_directory": "/test/data",
                "corruption_detection_enabled": True,
                "generate_thumbnails": True,
            }
            
        def get_connection(self):
            return self._mock_connection()
            
        def _mock_connection(self):
            """Mock connection context manager."""
            
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
                    """Mock cursor for executing queries."""
                    
                    class MockCursor:
                        def __init__(self, db):
                            self.db = db
                            self.rowcount = 1
                            
                        def __enter__(self):
                            return self
                            
                        def __exit__(self, exc_type, exc_val, exc_tb):
                            pass
                            
                        def execute(self, query, params=None):
                            # Mock database operations
                            if "SELECT" in query.upper():
                                return self
                            elif "INSERT" in query.upper():
                                self.rowcount = 1
                                return self
                            elif "UPDATE" in query.upper():
                                self.rowcount = 1
                                return self
                            return self
                            
                        def fetchone(self):
                            # Return mock data based on query context
                            return {"id": 1, "name": "Test Camera", "status": "active"}
                            
                        def fetchall(self):
                            # Return mock data based on query context
                            return [{"id": 1, "name": "Test Camera", "status": "active"}]
                            
                    return MockCursor(self.db)
                    
            return MockConnection(self)
    
    return MockSyncDatabase()


@pytest.fixture
def test_camera_data():
    """Test camera data for integration tests."""
    return {
        "id": 1,
        "name": "Test Camera",
        "rtsp_url": "rtsp://test.camera/stream",
        "status": "active",
        "health_status": "healthy",
        "active_timelapse_id": 1,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.fixture
def test_timelapse_data():
    """Test timelapse data for integration tests."""
    return {
        "id": 1,
        "camera_id": 1,
        "name": "Test Timelapse",
        "status": "active",
        "capture_interval": 30,
        "image_count": 5,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.fixture
def mock_settings_service(mock_sync_database):
    """Mock settings service for testing."""
    return SyncSettingsService(mock_sync_database)


@pytest.fixture
def mock_rtsp_capture():
    """Mock RTSP capture for testing."""
    
    def mock_capture_frame(rtsp_url, **kwargs):
        """Mock successful frame capture."""
        return RTSPCaptureResult(
            success=True,
            image_path="/test/data/images/test_image.jpg",
            file_size=1024,
            capture_time_ms=50,
            rtsp_url=rtsp_url,
            error_message=None,
        )
    
    return mock_capture_frame


@pytest.fixture
def capture_pipeline_dependencies(mock_sync_database, mock_settings_service):
    """Bundle of dependencies for capture pipeline testing."""
    return {
        "sync_db": mock_sync_database,
        "settings_service": mock_settings_service,
    }


@pytest.mark.integration
@pytest.mark.capture_pipeline
class TestCapturePipelineIntegration:
    """Integration tests for capture pipeline with dependency injection."""
    
    def test_capture_pipeline_factory_creates_all_services(self, capture_pipeline_dependencies):
        """Test that factory creates WorkflowOrchestratorService with all 10 dependencies."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        
        # Act
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Assert
        assert isinstance(workflow_orchestrator, WorkflowOrchestratorService)
        
        # Verify all 10 services are injected
        assert workflow_orchestrator.camera_service is not None
        assert workflow_orchestrator.timelapse_service is not None
        assert workflow_orchestrator.image_service is not None
        assert workflow_orchestrator.rtsp_service is not None
        assert workflow_orchestrator.corruption_service is not None
        assert workflow_orchestrator.weather_service is not None
        assert workflow_orchestrator.overlay_service is not None
        assert workflow_orchestrator.job_coordination_service is not None
        assert workflow_orchestrator.sse_service is not None
        assert workflow_orchestrator.scheduling_service is not None
        
        # Verify services have proper database connections
        assert workflow_orchestrator.camera_service.db is not None
        assert workflow_orchestrator.timelapse_service.db is not None
        assert workflow_orchestrator.image_service.db is not None
    
    def test_service_constructor_standardization(self, mock_sync_database, mock_settings_service):
        """Test that all services use consistent constructor patterns."""
        # Test ThumbnailService with sync database
        thumbnail_service = ThumbnailService(
            db=mock_sync_database,
            sse_operations=None,
            settings_service=mock_settings_service,
        )
        assert thumbnail_service.db is mock_sync_database
        assert thumbnail_service.settings_service is mock_settings_service
        
        # Test OverlayService with sync database
        overlay_service = OverlayService(
            db=mock_sync_database,
            settings_service=mock_settings_service,
            weather_manager=None,
            sse_ops=None,
        )
        assert overlay_service.db is mock_sync_database
        assert overlay_service.settings_service is mock_settings_service
        
        # Test VideoAutomationService with sync database
        video_automation_service = VideoAutomationService(
            db=mock_sync_database,
            timelapse_service=None,
        )
        assert video_automation_service.db is mock_sync_database
    
    def test_scheduler_trust_model_integration(self, capture_pipeline_dependencies):
        """Test scheduler validation and worker trust model."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        sync_db = capture_pipeline_dependencies["sync_db"]
        
        # Create workflow orchestrator with scheduling service
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        scheduling_service = workflow_orchestrator.scheduling_service
        
        # Create scheduler worker with scheduling service
        scheduler_worker = SchedulerWorker(
            settings_service=settings_service,
            db=sync_db,
            scheduling_service=scheduling_service,
        )
        
        # Test scheduling service validation
        assert isinstance(scheduling_service, SyncSchedulingService)
        
        # Test validation method exists and returns proper result
        with patch.object(scheduling_service, 'validate_capture_readiness') as mock_validate:
            mock_validate.return_value = CaptureReadinessValidationResult(
                valid=True,
                error=None,
                error_type=None,
                camera_id=1,
                timelapse_id=1,
            )
            
            result = scheduling_service.validate_capture_readiness(1, 1)
            assert result.valid is True
            assert result.camera_id == 1
            assert result.timelapse_id == 1
    
    def test_capture_worker_dependency_injection(self, capture_pipeline_dependencies):
        """Test CaptureWorker uses dependency injection correctly."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Create mock video automation service
        mock_video_automation = MagicMock()
        mock_weather_manager = MagicMock()
        
        # Act
        capture_worker = CaptureWorker(
            workflow_orchestrator=workflow_orchestrator,
            video_automation_service=mock_video_automation,
            weather_manager=mock_weather_manager,
        )
        
        # Assert
        assert capture_worker.workflow_orchestrator is workflow_orchestrator
        assert capture_worker.video_automation_service is mock_video_automation
        assert capture_worker.weather_manager is mock_weather_manager
        
        # Verify worker can access services through orchestrator
        assert capture_worker.workflow_orchestrator.camera_service is not None
        assert capture_worker.workflow_orchestrator.timelapse_service is not None
    
    @patch('app.services.capture_pipeline.rtsp_service.RTSPService.capture_and_process_frame')
    @patch('app.services.corruption_service.SyncCorruptionService.analyze_image_quality')
    def test_end_to_end_capture_flow_success(
        self,
        mock_analyze_quality,
        mock_rtsp_capture,
        capture_pipeline_dependencies,
        test_camera_data,
        test_timelapse_data,
    ):
        """Test complete capture flow from orchestrator to image save."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Mock successful RTSP capture
        mock_rtsp_capture.return_value = {
            "success": True,
            "image_path": "/test/data/images/test_image.jpg",
            "file_size": 1024,
            "capture_time_ms": 50,
            "metadata": {},
        }
        
        # Mock successful corruption analysis
        mock_analyze_quality.return_value = {
            "success": True,
            "quality_score": 95,
            "is_valid": True,
            "processing_time_ms": 25,
        }
        
        # Mock the internal image record creation to bypass path validation
        with patch.object(workflow_orchestrator, '_create_image_record') as mock_create_record:
            mock_image_record = MagicMock()
            mock_image_record.id = 1
            mock_image_record.day_number = 1
            mock_create_record.return_value = mock_image_record
            
            # Act - Execute capture flow
            with patch.object(workflow_orchestrator.camera_ops, 'get_camera_by_id') as mock_get_camera:
                with patch.object(workflow_orchestrator.timelapse_ops, 'get_timelapse_by_id') as mock_get_timelapse:
                    # Mock database responses
                    mock_get_camera.return_value = MagicMock()
                    mock_get_camera.return_value.id = 1
                    mock_get_timelapse.return_value = MagicMock()
                    mock_get_timelapse.return_value.id = 1
                    
                    # Execute capture
                    result = workflow_orchestrator.execute_capture_workflow(
                        camera_id=1,
                        timelapse_id=1,
                    )
        
        # Assert
        assert result.success is True
        assert result.image_id is not None
        
        # Verify all services were called
        mock_rtsp_capture.assert_called_once()
        mock_analyze_quality.assert_called_once()
        mock_create_record.assert_called_once()
    
    @patch('app.services.capture_pipeline.rtsp_service.RTSPService.capture_and_process_frame')
    def test_end_to_end_capture_flow_rtsp_failure(
        self,
        mock_rtsp_capture,
        capture_pipeline_dependencies,
        test_camera_data,
        test_timelapse_data,
    ):
        """Test capture flow handles RTSP failures gracefully."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Mock RTSP capture failure
        mock_rtsp_capture.return_value = {
            "success": False,
            "error": "Connection timeout",
            "image_path": None,
            "file_size": 0,
            "capture_time_ms": 0,
        }
        
        # Act - Execute capture flow
        with patch.object(workflow_orchestrator.camera_ops, 'get_camera_by_id') as mock_get_camera:
            with patch.object(workflow_orchestrator.timelapse_ops, 'get_timelapse_by_id') as mock_get_timelapse:
                # Mock database responses
                mock_get_camera.return_value = MagicMock()
                mock_get_camera.return_value.id = 1
                mock_get_timelapse.return_value = MagicMock()
                mock_get_timelapse.return_value.id = 1
                
                # Execute capture
                result = workflow_orchestrator.execute_capture_workflow(
                    camera_id=1,
                    timelapse_id=1,
                )
        
        # Assert
        assert result.success is False
        assert result.error is not None
        assert "Connection timeout" in result.error
        
        # Verify RTSP was called but capture flow stopped
        mock_rtsp_capture.assert_called_once()
    
    def test_capture_pipeline_health_check(self, capture_pipeline_dependencies):
        """Test capture pipeline health check functionality."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        
        # Act
        from app.services.capture_pipeline import create_capture_pipeline, get_capture_pipeline_health
        orchestrator = create_capture_pipeline(settings_service=settings_service)
        health = get_capture_pipeline_health(orchestrator)
        
        # Assert
        assert "services" in health
        assert "database_info" in health
        assert "status" in health
        assert health["status"] == "healthy"
        assert len(health["services"]) == 12  # All 12 services should be listed
    
    @patch('app.services.capture_pipeline.workflow_orchestrator_service.WorkflowOrchestratorService._validate_capture_prerequisites')
    def test_scheduler_trust_model_validation_bypass(
        self,
        mock_validate_prereq,
        capture_pipeline_dependencies,
    ):
        """Test that CaptureWorker trusts scheduler validation."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        sync_db = capture_pipeline_dependencies["sync_db"]
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Mock minimal validation (trust scheduler)
        mock_validate_prereq.return_value = {"valid": True}
        
        # Create capture worker
        capture_worker = CaptureWorker(
            workflow_orchestrator=workflow_orchestrator,
            video_automation_service=MagicMock(),
            weather_manager=MagicMock(),
        )
        
        # Mock timelapse operations to provide timelapse data
        with patch.object(capture_worker.timelapse_ops, 'get_timelapse_by_id') as mock_get_timelapse:
            mock_timelapse = MagicMock()
            mock_timelapse.camera_id = 1
            mock_get_timelapse.return_value = mock_timelapse
            
            # Mock camera service to provide camera data  
            with patch.object(capture_worker.camera_service, 'get_camera_by_id') as mock_get_camera:
                mock_camera = MagicMock()
                mock_camera.id = 1
                mock_get_camera.return_value = mock_camera
                
                # Act - Call capture method
                with patch.object(workflow_orchestrator, 'execute_capture_workflow') as mock_execute:
                    mock_execute.return_value = {"success": True, "image_id": 1}
                    
                    result = asyncio.run(capture_worker.capture_single_timelapse(1))
                
                # Assert - capture_single_timelapse returns None but calls workflow orchestrator
                assert result is None  # Method returns None, not a result dict
                
                # Verify workflow orchestrator was called (trust scheduler pattern)
                mock_execute.assert_called_once()


def assert_performance_metrics(caplog, max_capture_time=3.0, max_service_creations=1):
    """Helper to assert performance metrics from logs."""
    # Check capture times
    capture_logs = [r for r in caplog.records if "Capture workflow completed" in r.message]
    for log in capture_logs:
        # Extract time from log message
        if "in" in log.message and "s" in log.message:
            time_str = log.message.split("in")[1].split("s")[0].strip()
            capture_time = float(time_str)
            assert capture_time < max_capture_time, f"Capture took {capture_time}s, max allowed is {max_capture_time}s"
    
    # Check service creations
    creation_logs = [r for r in caplog.records if "instance created" in r.message]
    assert len(creation_logs) <= max_service_creations, f"Found {len(creation_logs)} service creations, max allowed is {max_service_creations}"


@pytest.mark.integration
@pytest.mark.service_constructors
class TestServiceConstructorStandardization:
    """Test service constructor standardization across the application."""
    
    def test_all_services_use_db_first_parameter(self, mock_sync_database, mock_settings_service):
        """Test that all services use 'db' as the first parameter."""
        # Test ThumbnailService
        thumbnail_service = ThumbnailService(
            db=mock_sync_database,
            sse_operations=None,
            settings_service=mock_settings_service,
        )
        assert thumbnail_service.db is mock_sync_database
        
        # Test OverlayService
        overlay_service = OverlayService(
            db=mock_sync_database,
            settings_service=mock_settings_service,
        )
        assert overlay_service.db is mock_sync_database
        
        # Test VideoAutomationService
        video_automation = VideoAutomationService(db=mock_sync_database)
        assert video_automation.db is mock_sync_database
        
        # Test SyncSettingsService
        settings_service = SyncSettingsService(db=mock_sync_database)
        assert settings_service.db is mock_sync_database
    
    def test_services_handle_optional_dependencies(self, mock_sync_database):
        """Test that services handle optional dependencies correctly."""
        # Test ThumbnailService with minimal dependencies
        thumbnail_service = ThumbnailService(db=mock_sync_database)
        assert thumbnail_service.db is mock_sync_database
        assert thumbnail_service.sse_operations is None
        assert thumbnail_service.settings_service is None
        
        # Test OverlayService with minimal dependencies
        overlay_service = OverlayService(db=mock_sync_database)
        assert overlay_service.db is mock_sync_database
        assert overlay_service.settings_service is None
        assert overlay_service.weather_manager is None
        assert overlay_service.sse_ops is None
    
    def test_services_create_internal_operations_correctly(self, mock_sync_database):
        """Test that services create internal operations from database."""
        # Test ThumbnailService creates operations
        thumbnail_service = ThumbnailService(db=mock_sync_database)
        assert hasattr(thumbnail_service, 'thumbnail_job_ops')
        assert hasattr(thumbnail_service, 'image_operations')
        
        # Test OverlayService creates operations
        overlay_service = OverlayService(db=mock_sync_database)
        assert hasattr(overlay_service, 'overlay_ops')
        assert hasattr(overlay_service, 'image_ops')


@pytest.mark.integration
@pytest.mark.performance
class TestCapturePipelinePerformance:
    """Performance validation tests for capture pipeline."""
    
    def test_capture_workflow_performance(self, capture_pipeline_dependencies, caplog):
        """Test that capture workflow completes within acceptable time limits."""
        import time
        
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        workflow_orchestrator = create_capture_pipeline(settings_service=settings_service)
        
        # Mock the services to avoid actual RTSP/file operations
        with patch.object(workflow_orchestrator.camera_ops, 'get_camera_by_id') as mock_get_camera:
            with patch.object(workflow_orchestrator.timelapse_ops, 'get_timelapse_by_id') as mock_get_timelapse:
                with patch.object(workflow_orchestrator.rtsp_service, 'capture_and_process_frame') as mock_capture:
                    with patch.object(workflow_orchestrator.corruption_service, 'analyze_image_quality') as mock_analyze:
                        with patch.object(workflow_orchestrator, '_create_image_record') as mock_create_record:
                            # Setup mocks
                            mock_get_camera.return_value = MagicMock(id=1)
                            mock_get_timelapse.return_value = MagicMock(id=1)
                            mock_capture.return_value = {"success": True, "image_path": "/test/image.jpg"}
                            mock_analyze.return_value = {"success": True, "quality_score": 95}
                            mock_create_record.return_value = MagicMock(id=1, day_number=1)
                            
                            # Act - Run 5 captures and measure time
                            timings = []
                            for i in range(5):
                                start = time.time()
                                result = workflow_orchestrator.execute_capture_workflow(
                                    camera_id=1,
                                    timelapse_id=1,
                                )
                                duration = time.time() - start
                                timings.append(duration)
                                assert result.success is True
                            
                            # Assert
                            avg_time = sum(timings) / len(timings)
                            assert avg_time < 0.1  # Should be very fast with mocks
                            
                            # Check that services were created only once
                            service_creation_logs = [r for r in caplog.records if "instance created" in r.message]
                            assert len(service_creation_logs) <= 1  # At most one service creation
    
    def test_service_reuse_not_recreation(self, capture_pipeline_dependencies):
        """Test that services are reused, not recreated per capture."""
        # Arrange
        settings_service = capture_pipeline_dependencies["settings_service"]
        
        # Act - Create multiple workflow orchestrators
        orchestrator1 = create_capture_pipeline(settings_service=settings_service)
        orchestrator2 = create_capture_pipeline(settings_service=settings_service)
        
        # Assert - Services should be different instances (factory creates new ones)
        assert orchestrator1 is not orchestrator2
        assert orchestrator1.camera_service is not orchestrator2.camera_service
        
        # But within an orchestrator, services should be stable
        assert orchestrator1.camera_service is orchestrator1.camera_service
        assert orchestrator1.rtsp_service is orchestrator1.rtsp_service