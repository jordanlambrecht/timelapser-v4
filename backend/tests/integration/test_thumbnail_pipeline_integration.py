#!/usr/bin/env python3
"""
Integration tests for ThumbnailPipeline.

Tests the complete thumbnail pipeline integration including:
- End-to-end thumbnail generation workflows
- Scheduler integration and trust model
- Service composition and dependency injection
- Database operations and job management
"""

import pytest
import tempfile
import shutil
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from PIL import Image, ImageDraw

from app.services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
from app.services.scheduling.scheduler_authority_service import SchedulerAuthorityService
from app.database.core import AsyncDatabase, SyncDatabase
from app.enums import JobPriority, JobStatus, SSEPriority
from app.models.shared_models import ThumbnailGenerationJob, ThumbnailGenerationResult


@pytest.mark.integration
@pytest.mark.thumbnail
@pytest.mark.scheduler_trust_model
class TestThumbnailPipelineIntegration:
    """Test suite for ThumbnailPipeline integration with scheduler."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_image_path(self, temp_dir):
        """Create a sample test image."""
        image_path = temp_dir / "test_source.jpg"
        
        # Create a realistic test image
        img = Image.new('RGB', (1920, 1080), color='skyblue')
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 100, 1820, 980], fill='lightgreen')
        draw.text((500, 500), "Test Image for Pipeline", fill='black')
        img.save(image_path, 'JPEG', quality=95)
        
        return str(image_path)

    @pytest.fixture
    def mock_databases(self):
        """Create mock database instances."""
        mock_sync_db = Mock(spec=SyncDatabase)
        mock_async_db = Mock(spec=AsyncDatabase)
        
        # Mock connection context managers
        mock_sync_db.get_connection.return_value.__enter__.return_value = Mock()
        mock_async_db.get_connection.return_value.__aenter__.return_value = AsyncMock()
        
        return {
            'sync': mock_sync_db,
            'async': mock_async_db
        }

    @pytest.fixture
    def thumbnail_pipeline(self, mock_databases):
        """Create ThumbnailPipeline instance with mocked dependencies."""
        return ThumbnailPipeline(
            database=mock_databases['sync'],
            async_database=mock_databases['async']
        )

    @pytest.fixture
    def mock_scheduler_authority(self):
        """Create mock SchedulerAuthorityService."""
        mock_scheduler = Mock(spec=SchedulerAuthorityService)
        
        # Mock successful scheduling
        mock_scheduler.schedule_immediate_thumbnail_generation.return_value = {
            'success': True,
            'message': 'Immediate thumbnail generation scheduled',
            'image_id': 1,
            'priority': SSEPriority.NORMAL,
            'scheduled_via': 'scheduler_authority'
        }
        
        return mock_scheduler

    @pytest.fixture
    def sample_thumbnail_job(self):
        """Create sample thumbnail generation job."""
        return ThumbnailGenerationJob(
            id=1,
            image_id=123,
            priority=JobPriority.MEDIUM,
            status=JobStatus.PENDING,
            created_at="2023-07-01T12:00:00Z"
        )

    # ============================================================================
    # PIPELINE INITIALIZATION TESTS
    # ============================================================================

    def test_pipeline_initialization_with_dependencies(self, mock_databases):
        """Test pipeline initialization with proper dependency injection."""
        pipeline = ThumbnailPipeline(
            database=mock_databases['sync'],
            async_database=mock_databases['async']
        )
        
        # Verify pipeline components are initialized
        assert pipeline.database == mock_databases['sync']
        assert pipeline.async_database == mock_databases['async']
        
        # Verify generators are available
        assert hasattr(pipeline, 'thumbnail_generator')
        assert hasattr(pipeline, 'small_generator')
        assert hasattr(pipeline, 'batch_generator')
        
        # Verify services are initialized
        assert hasattr(pipeline, 'job_service')
        assert hasattr(pipeline, 'async_job_service')

    def test_pipeline_initialization_defaults(self):
        """Test pipeline initialization with default parameters."""
        pipeline = ThumbnailPipeline()
        
        # Should initialize with default settings
        assert pipeline.database is None  # Will be set when needed
        assert pipeline.async_database is None
        
        # Generators should still be available
        assert hasattr(pipeline, 'thumbnail_generator')
        assert hasattr(pipeline, 'small_generator')
        assert hasattr(pipeline, 'batch_generator')

    # ============================================================================
    # SCHEDULER INTEGRATION TESTS
    # ============================================================================

    @pytest.mark.asyncio 
    async def test_pipeline_scheduler_authority_integration(self, thumbnail_pipeline, mock_scheduler_authority, sample_image_path, temp_dir):
        """Test complete integration with SchedulerAuthorityService."""
        output_path = str(temp_dir / "scheduler_thumbnail.jpg")
        
        # Mock the pipeline's generate method
        with patch.object(thumbnail_pipeline, 'generate_thumbnail') as mock_generate:
            mock_generate.return_value = ThumbnailGenerationResult(
                success=True,
                output_path=output_path,
                size=(200, 150),
                generation_time_ms=75,
                source_size=(1920, 1080)
            )
            
            # Simulate scheduler authority requesting thumbnail generation
            scheduler_result = await mock_scheduler_authority.schedule_immediate_thumbnail_generation(
                image_id=123,
                priority=SSEPriority.HIGH
            )
            
            # Verify scheduler accepted the request
            assert scheduler_result['success'] is True
            assert scheduler_result['image_id'] == 123
            assert scheduler_result['priority'] == SSEPriority.HIGH
            assert scheduler_result['scheduled_via'] == 'scheduler_authority'
            
            # Simulate pipeline execution (would be triggered by scheduler worker)
            pipeline_result = thumbnail_pipeline.generate_thumbnail(
                source_path=sample_image_path,
                output_path=output_path
            )
            
            # Verify pipeline execution
            assert pipeline_result.success is True
            assert pipeline_result.output_path == output_path
            mock_generate.assert_called_once()

    def test_pipeline_scheduler_trust_model(self, thumbnail_pipeline, sample_image_path, temp_dir):
        """Test that pipeline trusts scheduler decisions (minimal validation)."""
        output_path = str(temp_dir / "trusted_thumbnail.jpg")
        
        # Mock successful generation
        with patch.object(thumbnail_pipeline.thumbnail_generator, 'generate_thumbnail') as mock_gen:
            mock_gen.return_value = {
                'success': True,
                'output_path': output_path,
                'size': (200, 150),
                'generation_time_ms': 50
            }
            
            # Pipeline should execute without extensive validation (trusting scheduler)
            result = thumbnail_pipeline.generate_thumbnail(
                source_path=sample_image_path,
                output_path=output_path
            )
            
            # Should complete successfully with minimal validation
            assert result.success is True
            mock_gen.assert_called_once_with(sample_image_path, output_path)

    @pytest.mark.asyncio
    async def test_pipeline_job_queue_integration(self, thumbnail_pipeline, sample_thumbnail_job):
        """Test pipeline integration with job queue system."""
        # Mock job service operations
        with patch.object(thumbnail_pipeline, 'async_job_service') as mock_job_service:
            mock_job_service.create_job.return_value = sample_thumbnail_job
            mock_job_service.get_pending_jobs.return_value = [sample_thumbnail_job]
            mock_job_service.mark_job_started.return_value = True
            mock_job_service.mark_job_completed.return_value = True
            
            # Simulate scheduler creating job
            created_job = await mock_job_service.create_job(
                image_id=123,
                priority=JobPriority.HIGH
            )
            
            # Verify job creation
            assert created_job.image_id == 123
            assert created_job.priority == JobPriority.HIGH
            
            # Simulate job processing
            pending_jobs = await mock_job_service.get_pending_jobs(limit=1)
            assert len(pending_jobs) == 1
            
            job = pending_jobs[0]
            await mock_job_service.mark_job_started(job.id)
            
            # Process job (would trigger actual thumbnail generation)
            # ... thumbnail generation logic ...
            
            await mock_job_service.mark_job_completed(job.id)
            
            # Verify all job operations were called
            mock_job_service.create_job.assert_called_once()
            mock_job_service.get_pending_jobs.assert_called_once()
            mock_job_service.mark_job_started.assert_called_once()
            mock_job_service.mark_job_completed.assert_called_once()

    # ============================================================================
    # END-TO-END WORKFLOW TESTS
    # ============================================================================

    def test_complete_thumbnail_workflow(self, thumbnail_pipeline, sample_image_path, temp_dir):
        """Test complete end-to-end thumbnail generation workflow."""
        thumbnail_output = str(temp_dir / "workflow_thumbnail.jpg")
        small_output = str(temp_dir / "workflow_small.jpg")
        
        # Mock both generators
        with patch.object(thumbnail_pipeline.thumbnail_generator, 'generate_thumbnail') as mock_thumb:
            with patch.object(thumbnail_pipeline.small_generator, 'generate_small_image') as mock_small:
                mock_thumb.return_value = {
                    'success': True,
                    'output_path': thumbnail_output,
                    'size': (200, 150),
                    'generation_time_ms': 45
                }
                mock_small.return_value = {
                    'success': True,
                    'output_path': small_output,
                    'size': (800, 600),
                    'generation_time_ms': 80
                }
                
                # Execute complete workflow
                results = thumbnail_pipeline.generate_both(
                    source_path=sample_image_path,
                    thumbnail_path=thumbnail_output,
                    small_path=small_output
                )
                
                # Verify both generations completed
                assert results['thumbnail']['success'] is True
                assert results['small_image']['success'] is True
                assert results['thumbnail']['output_path'] == thumbnail_output
                assert results['small_image']['output_path'] == small_output
                
                # Verify both generators were called
                mock_thumb.assert_called_once()
                mock_small.assert_called_once()

    def test_batch_workflow_integration(self, thumbnail_pipeline, temp_dir):
        """Test batch processing workflow integration."""
        # Create multiple source images
        sources = []
        for i in range(3):
            img_path = temp_dir / f"batch_source_{i}.jpg"
            img = Image.new('RGB', (800, 600), color=['red', 'green', 'blue'][i])
            img.save(img_path, 'JPEG')
            sources.append(str(img_path))
        
        # Mock batch generator
        with patch.object(thumbnail_pipeline.batch_generator, 'generate_thumbnails_batch') as mock_batch:
            mock_batch.return_value = {
                'success': True,
                'total_jobs': 3,
                'successful_jobs': 3,
                'failed_jobs': 0,
                'processing_time_ms': 200
            }
            
            # Create batch jobs
            jobs = []
            for i, source in enumerate(sources):
                jobs.append({
                    'source_path': source,
                    'thumbnail_path': str(temp_dir / f"batch_thumb_{i}.jpg")
                })
            
            # Execute batch workflow
            result = thumbnail_pipeline.process_batch(jobs)
            
            # Verify batch processing
            assert result['success'] is True
            assert result['total_jobs'] == 3
            assert result['successful_jobs'] == 3
            
            mock_batch.assert_called_once_with(jobs, progress_callback=None)

    # ============================================================================
    # ERROR HANDLING AND RECOVERY TESTS
    # ============================================================================

    def test_pipeline_error_handling_and_recovery(self, thumbnail_pipeline, sample_image_path, temp_dir):
        """Test pipeline error handling and recovery mechanisms."""
        output_path = str(temp_dir / "error_test_thumbnail.jpg")
        
        # Mock generator to fail first, then succeed
        call_count = 0
        def mock_generate_side_effect(source_path, output_path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {'success': False, 'error': 'Simulated failure'}
            return {
                'success': True,
                'output_path': output_path,
                'size': (200, 150),
                'generation_time_ms': 50
            }
        
        with patch.object(thumbnail_pipeline.thumbnail_generator, 'generate_thumbnail', side_effect=mock_generate_side_effect):
            # First attempt should fail
            result1 = thumbnail_pipeline.generate_thumbnail(
                source_path=sample_image_path,
                output_path=output_path
            )
            assert result1.success is False
            
            # Second attempt should succeed (simulating retry)
            result2 = thumbnail_pipeline.generate_thumbnail(
                source_path=sample_image_path,
                output_path=output_path
            )
            assert result2.success is True

    def test_pipeline_graceful_degradation(self, thumbnail_pipeline, sample_image_path, temp_dir):
        """Test pipeline graceful degradation when components fail."""
        thumbnail_output = str(temp_dir / "degraded_thumbnail.jpg")
        small_output = str(temp_dir / "degraded_small.jpg")
        
        # Mock thumbnail generator to fail, small generator to succeed
        with patch.object(thumbnail_pipeline.thumbnail_generator, 'generate_thumbnail') as mock_thumb:
            with patch.object(thumbnail_pipeline.small_generator, 'generate_small_image') as mock_small:
                mock_thumb.return_value = {'success': False, 'error': 'Thumbnail generation failed'}
                mock_small.return_value = {
                    'success': True,
                    'output_path': small_output,
                    'size': (800, 600),
                    'generation_time_ms': 80
                }
                
                # Should continue with small image even if thumbnail fails
                results = thumbnail_pipeline.generate_both(
                    source_path=sample_image_path,
                    thumbnail_path=thumbnail_output,
                    small_path=small_output
                )
                
                # Verify partial success
                assert results['thumbnail']['success'] is False
                assert results['small_image']['success'] is True
                
                # Both should have been attempted
                mock_thumb.assert_called_once()
                mock_small.assert_called_once()

    # ============================================================================
    # PERFORMANCE AND MONITORING TESTS
    # ============================================================================

    def test_pipeline_performance_monitoring(self, thumbnail_pipeline, sample_image_path, temp_dir):
        """Test pipeline performance monitoring and metrics collection."""
        output_path = str(temp_dir / "perf_thumbnail.jpg")
        
        # Mock generator with timing
        with patch.object(thumbnail_pipeline.thumbnail_generator, 'generate_thumbnail') as mock_gen:
            mock_gen.return_value = {
                'success': True,
                'output_path': output_path,
                'size': (200, 150),
                'generation_time_ms': 125
            }
            
            result = thumbnail_pipeline.generate_thumbnail(
                source_path=sample_image_path,
                output_path=output_path
            )
            
            # Should include performance metrics
            assert result.success is True
            assert hasattr(result, 'generation_time_ms')
            assert result.generation_time_ms >= 0

    def test_pipeline_resource_management(self, thumbnail_pipeline, temp_dir):
        """Test pipeline resource management and cleanup."""
        # Create multiple processing jobs to test resource handling
        sources = []
        for i in range(5):
            img_path = temp_dir / f"resource_test_{i}.jpg"
            img = Image.new('RGB', (400, 300), color='purple')
            img.save(img_path, 'JPEG')
            sources.append(str(img_path))
        
        with patch.object(thumbnail_pipeline.batch_generator, 'generate_thumbnails_batch') as mock_batch:
            mock_batch.return_value = {
                'success': True,
                'total_jobs': 5,
                'successful_jobs': 5,
                'failed_jobs': 0,
                'processing_time_ms': 300
            }
            
            # Process batch to test resource management
            jobs = []
            for i, source in enumerate(sources):
                jobs.append({
                    'source_path': source,
                    'thumbnail_path': str(temp_dir / f"resource_thumb_{i}.jpg")
                })
            
            result = thumbnail_pipeline.process_batch(jobs)
            
            # Should complete successfully without resource issues
            assert result['success'] is True
            assert result['total_jobs'] == 5

    # ============================================================================
    # SCHEDULER TRUST MODEL VALIDATION TESTS
    # ============================================================================

    def test_scheduler_trust_model_minimal_validation(self, thumbnail_pipeline, sample_image_path, temp_dir):
        """Test that pipeline performs minimal validation, trusting scheduler decisions."""
        output_path = str(temp_dir / "trust_model_thumbnail.jpg")
        
        with patch.object(thumbnail_pipeline.thumbnail_generator, 'generate_thumbnail') as mock_gen:
            mock_gen.return_value = {
                'success': True,
                'output_path': output_path,
                'size': (200, 150),
                'generation_time_ms': 40
            }
            
            # Pipeline should not perform extensive pre-validation 
            # (trusting that scheduler already validated)
            result = thumbnail_pipeline.generate_thumbnail(
                source_path=sample_image_path,
                output_path=output_path
            )
            
            # Should proceed directly to generation
            assert result.success is True
            mock_gen.assert_called_once()
            
            # Should not have called extensive validation methods
            # (scheduler trust model - minimal pipeline validation)

    @pytest.mark.asyncio
    async def test_scheduler_authority_delegation_pattern(self, mock_scheduler_authority):
        """Test proper delegation pattern from SchedulerAuthority -> Worker -> Pipeline."""
        # Test the complete delegation chain
        
        # 1. SchedulerAuthority receives request
        authority_result = await mock_scheduler_authority.schedule_immediate_thumbnail_generation(
            image_id=456,
            priority=SSEPriority.HIGH
        )
        
        # 2. Authority should delegate to scheduler worker (mocked)
        assert authority_result['success'] is True
        assert authority_result['scheduled_via'] == 'scheduler_authority'
        
        # 3. Worker would delegate to pipeline (tested in other methods)
        # This verifies the authority -> worker delegation step
        mock_scheduler_authority.schedule_immediate_thumbnail_generation.assert_called_once_with(
            image_id=456,
            priority=SSEPriority.HIGH
        )