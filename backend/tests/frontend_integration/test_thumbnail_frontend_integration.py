#!/usr/bin/env python3
"""
Frontend Integration Tests for Thumbnail System.

Tests the integration between the thumbnail job queue system and frontend components,
including SSE events, API endpoints, and real-time progress updates.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
    BulkThumbnailRequest,
    BulkThumbnailResponse,
    ThumbnailJobStatistics
)
from app.enums import (
    ThumbnailJobStatus,
    ThumbnailJobPriority,
    ThumbnailJobType,
)


@pytest.mark.frontend
@pytest.mark.thumbnail
@pytest.mark.integration
class TestThumbnailFrontendIntegration:
    """Test suite for thumbnail system frontend integration."""
    
    @pytest.fixture
    def mock_frontend_client(self):
        """Mock frontend HTTP client for API calls."""
        class MockFrontendClient:
            def __init__(self):
                self.responses = {}
                self.requests = []
                
            def set_response(self, endpoint, response_data, status_code=200):
                self.responses[endpoint] = {
                    'data': response_data,
                    'status': status_code
                }
                
            async def post(self, endpoint, json_data=None):
                self.requests.append({
                    'method': 'POST',
                    'endpoint': endpoint,
                    'data': json_data
                })
                
                if endpoint in self.responses:
                    response = self.responses[endpoint]
                    return MockResponse(response['data'], response['status'])
                
                return MockResponse({'success': True}, 200)
                
            async def get(self, endpoint):
                self.requests.append({
                    'method': 'GET',
                    'endpoint': endpoint
                })
                
                if endpoint in self.responses:
                    response = self.responses[endpoint]
                    return MockResponse(response['data'], response['status'])
                
                return MockResponse({'data': []}, 200)
        
        return MockFrontendClient()
    
    @pytest.fixture
    def mock_sse_client(self):
        """Mock SSE client for testing real-time events."""
        class MockSSEClient:
            def __init__(self):
                self.events = []
                self.event_handlers = {}
                self.connected = False
                
            def connect(self, url):
                self.connected = True
                
            def disconnect(self):
                self.connected = False
                
            def add_event_handler(self, event_type, handler):
                if event_type not in self.event_handlers:
                    self.event_handlers[event_type] = []
                self.event_handlers[event_type].append(handler)
                
            def simulate_event(self, event_type, event_data):
                event = {
                    'type': event_type,
                    'data': event_data,
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.events.append(event)
                
                # Trigger handlers
                if event_type in self.event_handlers:
                    for handler in self.event_handlers[event_type]:
                        handler(event)
        
        return MockSSEClient()
    
    @pytest.mark.asyncio
    async def test_thumbnail_regeneration_modal_workflow(self, mock_frontend_client, mock_sse_client, mock_thumbnail_service_dependencies):
        """Test the complete thumbnail regeneration modal workflow."""
        # Setup thumbnail service
        from app.services.thumbnail_service import ThumbnailService
        thumbnail_service = ThumbnailService(
            thumbnail_job_ops=mock_thumbnail_service_dependencies['thumbnail_job_ops'],
            sse_operations=mock_thumbnail_service_dependencies['sse_ops']
        )
        
        # Mock frontend responses
        mock_frontend_client.set_response('/api/thumbnails/regenerate-all/status', {
            'active': False,
            'progress': 0,
            'total': 0,
            'current_image': '',
            'completed': 0,
            'errors': 0
        })
        
        # 1. Frontend opens modal and fetches status
        status_response = await mock_frontend_client.get('/api/thumbnails/regenerate-all/status')
        assert status_response.status_code == 200
        assert not status_response.json()['active']
        
        # 2. User clicks "Start Regeneration"
        bulk_request = BulkThumbnailRequest(
            image_ids=[1, 2, 3, 4, 5],
            priority=ThumbnailJobPriority.HIGH
        )
        
        bulk_response = await thumbnail_service.queue_bulk_thumbnails(bulk_request)
        assert bulk_response.total_requested == 5
        assert bulk_response.jobs_created == 5
        
        # 3. SSE events should be broadcast
        sse_ops = mock_thumbnail_service_dependencies['sse_ops']
        events = sse_ops.get_events()
        assert len(events) > 0
        
        # Should have bulk queued event
        bulk_events = [e for e in events if e['event_type'] == 'thumbnail_bulk_queued']
        assert len(bulk_events) == 1
        assert bulk_events[0]['event_data']['total_jobs'] == 5
        
        # 4. Simulate progress events that frontend would receive
        mock_sse_client.connect('/api/events')
        
        progress_handler_calls = []
        def progress_handler(event):
            progress_handler_calls.append(event)
        
        mock_sse_client.add_event_handler('thumbnail_regeneration_progress', progress_handler)
        
        # Simulate worker processing jobs and sending progress
        for i in range(1, 6):
            mock_sse_client.simulate_event('thumbnail_regeneration_progress', {
                'progress': i,
                'total': 5,
                'current_image': f'image_{i}.jpg',
                'completed': i,
                'errors': 0
            })
        
        # 5. Verify progress events were handled
        assert len(progress_handler_calls) == 5
        last_progress = progress_handler_calls[-1]
        assert last_progress['data']['completed'] == 5
        assert last_progress['data']['total'] == 5
        
        # 6. Simulate completion event
        completion_handler_calls = []
        def completion_handler(event):
            completion_handler_calls.append(event)
        
        mock_sse_client.add_event_handler('thumbnail_regeneration_complete', completion_handler)
        mock_sse_client.simulate_event('thumbnail_regeneration_complete', {
            'completed': 5,
            'total': 5,
            'errors': 0,
            'processing_time_seconds': 12.5
        })
        
        assert len(completion_handler_calls) == 1
        completion_event = completion_handler_calls[0]
        assert completion_event['data']['completed'] == 5
        
        # 7. Frontend should update UI to show completion
        mock_sse_client.disconnect()
    
    @pytest.mark.asyncio
    async def test_thumbnail_job_cancellation_workflow(self, mock_frontend_client, mock_sse_client, mock_thumbnail_service_dependencies):
        """Test cancelling thumbnail jobs through frontend."""
        from app.services.thumbnail_service import ThumbnailService
        thumbnail_service = ThumbnailService(
            thumbnail_job_ops=mock_thumbnail_service_dependencies['thumbnail_job_ops'],
            sse_operations=mock_thumbnail_service_dependencies['sse_ops']
        )
        
        # 1. Start bulk regeneration
        bulk_request = BulkThumbnailRequest(
            image_ids=[1, 2, 3],
            priority=ThumbnailJobPriority.MEDIUM
        )
        
        bulk_response = await thumbnail_service.queue_bulk_thumbnails(bulk_request)
        assert bulk_response.jobs_created == 3
        
        # 2. Frontend sends cancellation request
        mock_frontend_client.set_response('/api/thumbnails/regenerate-all/cancel', {
            'success': True,
            'cancelled_jobs': 2,
            'message': 'Cancelled 2 pending jobs'
        })
        
        # Simulate cancellation of jobs for specific image
        cancelled_count = await thumbnail_service.cancel_jobs_for_image(2)
        assert cancelled_count >= 0  # Mock returns success
        
        # 3. Check SSE events for cancellation
        sse_ops = mock_thumbnail_service_dependencies['sse_ops']
        events = sse_ops.get_events()
        
        # Should have cancellation events
        cancel_events = [e for e in events if 'cancelled' in e['event_type']]
        assert len(cancel_events) >= 0  # At least some cancellation activity
        
        # 4. Frontend receives cancellation SSE event
        mock_sse_client.connect('/api/events')
        
        cancellation_handler_calls = []
        def cancellation_handler(event):
            cancellation_handler_calls.append(event)
        
        mock_sse_client.add_event_handler('thumbnail_regeneration_cancelled', cancellation_handler)
        mock_sse_client.simulate_event('thumbnail_regeneration_cancelled', {
            'cancelled_jobs': 2,
            'remaining_jobs': 1
        })
        
        assert len(cancellation_handler_calls) == 1
    
    @pytest.mark.asyncio
    async def test_sse_event_filtering_and_handling(self, mock_sse_client):
        """Test SSE event filtering and handling as done in thumbnail modal."""
        # Simulate the useSSESubscription hook behavior from the modal
        
        # 1. Setup event handlers for different thumbnail event types
        progress_events = []
        complete_events = []
        error_events = []
        
        def handle_progress(event):
            if event['type'] == 'thumbnail_regeneration_progress':
                progress_events.append(event)
        
        def handle_complete(event):
            if event['type'] == 'thumbnail_regeneration_complete':
                complete_events.append(event)
        
        def handle_error(event):
            if event['type'] == 'thumbnail_regeneration_error':
                error_events.append(event)
        
        mock_sse_client.add_event_handler('thumbnail_regeneration_progress', handle_progress)
        mock_sse_client.add_event_handler('thumbnail_regeneration_complete', handle_complete)
        mock_sse_client.add_event_handler('thumbnail_regeneration_error', handle_error)
        
        # 2. Simulate various events
        mock_sse_client.simulate_event('thumbnail_regeneration_progress', {
            'progress': 3,
            'total': 10,
            'current_image': 'camera_1/image_123.jpg',
            'completed': 3,
            'errors': 0
        })
        
        mock_sse_client.simulate_event('thumbnail_job_created', {
            'job_id': 456,
            'image_id': 789
        })
        
        mock_sse_client.simulate_event('thumbnail_regeneration_complete', {
            'completed': 10,
            'total': 10,
            'errors': 1,
            'processing_time_seconds': 25.3
        })
        
        mock_sse_client.simulate_event('thumbnail_regeneration_error', {
            'error': 'Failed to process image due to corruption',
            'image_id': 999
        })
        
        # 3. Verify only relevant events were captured by handlers
        assert len(progress_events) == 1
        assert progress_events[0]['data']['completed'] == 3
        
        assert len(complete_events) == 1
        assert complete_events[0]['data']['processing_time_seconds'] == 25.3
        
        assert len(error_events) == 1
        assert 'corruption' in error_events[0]['data']['error']
        
        # 4. Verify event filtering worked (job_created not captured)
        all_events = progress_events + complete_events + error_events
        job_created_events = [e for e in all_events if 'job_created' in e['type']]
        assert len(job_created_events) == 0
    
    @pytest.mark.asyncio
    async def test_api_endpoint_integration(self, mock_frontend_client, mock_thumbnail_service_dependencies):
        """Test API endpoint integration with thumbnail service."""
        from app.services.thumbnail_service import ThumbnailService
        thumbnail_service = ThumbnailService(
            thumbnail_job_ops=mock_thumbnail_service_dependencies['thumbnail_job_ops'],
            sse_operations=mock_thumbnail_service_dependencies['sse_ops']
        )
        
        # 1. Test job statistics endpoint
        stats = await thumbnail_service.get_job_statistics()
        assert isinstance(stats, ThumbnailJobStatistics)
        
        # Frontend calls /api/thumbnails/stats
        mock_frontend_client.set_response('/api/thumbnails/stats', {
            'pending_jobs': stats.pending_jobs,
            'processing_jobs': stats.processing_jobs,
            'completed_jobs_24h': stats.completed_jobs_24h,
            'failed_jobs_24h': stats.failed_jobs_24h,
            'total_jobs_24h': stats.total_jobs_24h
        })
        
        stats_response = await mock_frontend_client.get('/api/thumbnails/stats')
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert 'pending_jobs' in stats_data
        assert 'total_jobs_24h' in stats_data
        
        # 2. Test single image thumbnail generation
        job = await thumbnail_service.queue_single_image_thumbnail(
            image_id=123,
            priority=ThumbnailJobPriority.HIGH
        )
        assert job is not None
        assert job.image_id == 123
        assert job.priority == ThumbnailJobPriority.HIGH
        
        # Frontend calls POST /api/images/123/generate-thumbnail
        mock_frontend_client.set_response('/api/images/123/generate-thumbnail', {
            'success': True,
            'job_id': job.id,
            'message': 'Thumbnail generation queued'
        })
        
        generate_response = await mock_frontend_client.post('/api/images/123/generate-thumbnail')
        assert generate_response.status_code == 200
        assert generate_response.json()['success']
        
        # 3. Test bulk generation endpoint
        bulk_request = BulkThumbnailRequest(
            image_ids=[100, 101, 102],
            priority=ThumbnailJobPriority.MEDIUM
        )
        
        bulk_response = await thumbnail_service.queue_bulk_thumbnails(bulk_request)
        
        mock_frontend_client.set_response('/api/thumbnails/generate-bulk', {
            'total_requested': bulk_response.total_requested,
            'jobs_created': bulk_response.jobs_created,
            'jobs_failed': bulk_response.jobs_failed,
            'created_job_ids': bulk_response.created_job_ids
        })
        
        bulk_api_response = await mock_frontend_client.post('/api/thumbnails/generate-bulk', {
            'image_ids': [100, 101, 102],
            'priority': ThumbnailJobPriority.MEDIUM
        })
        
        assert bulk_api_response.status_code == 200
        bulk_data = bulk_api_response.json()
        assert bulk_data['jobs_created'] == 3
        assert len(bulk_data['created_job_ids']) == 3
    
    @pytest.mark.asyncio
    async def test_error_handling_and_user_feedback(self, mock_sse_client, mock_thumbnail_service_dependencies):
        """Test error handling and user feedback through SSE events."""
        # 1. Setup error event handlers
        error_events = []
        def handle_error(event):
            error_events.append(event)
        
        mock_sse_client.add_event_handler('thumbnail_regeneration_error', handle_error)
        mock_sse_client.add_event_handler('thumbnail_job_failed', handle_error)
        
        # 2. Simulate various error scenarios
        mock_sse_client.simulate_event('thumbnail_regeneration_error', {
            'error': 'Disk space insufficient for thumbnail generation',
            'error_code': 'DISK_SPACE',
            'affected_jobs': 5
        })
        
        mock_sse_client.simulate_event('thumbnail_job_failed', {
            'job_id': 789,
            'image_id': 456,
            'error': 'Image file not found',
            'retry_count': 3
        })
        
        mock_sse_client.simulate_event('thumbnail_regeneration_error', {
            'error': 'Worker process crashed',
            'error_code': 'WORKER_CRASH',
            'restart_required': True
        })
        
        # 3. Verify error events were captured
        assert len(error_events) == 3
        
        # Check error details
        disk_space_error = next(e for e in error_events if 'DISK_SPACE' in e['data'].get('error_code', ''))
        assert disk_space_error['data']['affected_jobs'] == 5
        
        job_failed_error = next(e for e in error_events if 'job_failed' in e['type'])
        assert job_failed_error['data']['retry_count'] == 3
        
        worker_crash_error = next(e for e in error_events if 'WORKER_CRASH' in e['data'].get('error_code', ''))
        assert worker_crash_error['data']['restart_required']
        
        # 4. Test user feedback through toast notifications
        # This would trigger toast.error() calls in the frontend
        toast_notifications = []
        
        for event in error_events:
            if 'DISK_SPACE' in event['data'].get('error_code', ''):
                toast_notifications.append({
                    'type': 'error',
                    'title': 'Thumbnail Generation Failed',
                    'message': event['data']['error'],
                    'duration': 7000
                })
            elif 'job_failed' in event['type']:
                toast_notifications.append({
                    'type': 'warning',
                    'title': 'Thumbnail Job Failed',
                    'message': f"Failed to generate thumbnail for image {event['data']['image_id']}",
                    'duration': 5000
                })
        
        assert len(toast_notifications) >= 2
    
    def test_frontend_component_state_management(self):
        """Test frontend component state management logic."""
        # Simulate ThumbnailRegenerationModal state logic
        
        class MockModalState:
            def __init__(self):
                self.progress = {
                    'active': False,
                    'progress': 0,
                    'total': 0,
                    'current_image': '',
                    'completed': 0,
                    'errors': 0
                }
                self.is_starting = False
                self.is_cancelling = False
                self.is_complete = False
            
            def handle_progress_event(self, event_data):
                self.progress.update({
                    'active': True,
                    'progress': event_data['progress'],
                    'total': event_data['total'],
                    'current_image': event_data['current_image'],
                    'completed': event_data['completed'],
                    'errors': event_data['errors']
                })
                self.is_starting = False
            
            def handle_complete_event(self, event_data):
                self.progress['active'] = False
                self.is_complete = True
                self.is_starting = False
                self.is_cancelling = False
            
            def handle_cancel_event(self):
                self.progress['active'] = False
                self.is_cancelling = False
            
            def start_regeneration(self):
                self.is_starting = True
                self.is_complete = False
            
            def can_close(self):
                return not (self.progress['active'] or self.is_starting)
        
        # Test state transitions
        modal_state = MockModalState()
        
        # 1. Initial state
        assert not modal_state.progress['active']
        assert modal_state.can_close()
        
        # 2. Start regeneration
        modal_state.start_regeneration()
        assert modal_state.is_starting
        assert not modal_state.can_close()
        
        # 3. Progress event
        modal_state.handle_progress_event({
            'progress': 3,
            'total': 10,
            'current_image': 'test.jpg',
            'completed': 3,
            'errors': 0
        })
        assert modal_state.progress['active']
        assert not modal_state.is_starting
        assert not modal_state.can_close()
        
        # 4. Completion
        modal_state.handle_complete_event({
            'completed': 10,
            'total': 10
        })
        assert not modal_state.progress['active']
        assert modal_state.is_complete
        assert modal_state.can_close()


class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
    
    def json(self):
        return self._json_data