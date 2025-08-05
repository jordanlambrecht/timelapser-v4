#!/usr/bin/env python3
"""
SSE Event Integration Tests for Thumbnail System.

Tests the SSE event broadcasting and filtering for the thumbnail system,
ensuring events are properly formatted and reach the frontend correctly.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants import (
    THUMBNAIL_JOB_TYPE_BULK,
    THUMBNAIL_JOB_TYPE_SINGLE,
)
from app.database.sse_events_operations import SSEEventsOperations
from app.enums import JobPriority, JobStatus


@pytest.mark.frontend
@pytest.mark.thumbnail
@pytest.mark.integration
class TestSSEEventIntegration:
    """Test suite for SSE event integration with thumbnail system."""

    @pytest.fixture
    def mock_sse_event_stream(self):
        """Mock SSE event stream for testing."""

        class MockSSEEventStream:
            def __init__(self):
                self.events = []
                self.active_connections = []
                self.event_filters = {}

            def add_connection(self, connection_id, event_filter=None):
                """Add a client connection with optional event filter."""
                self.active_connections.append(
                    {
                        "id": connection_id,
                        "filter": event_filter or (lambda e: True),
                        "events_received": [],
                    }
                )

            def remove_connection(self, connection_id):
                """Remove a client connection."""
                self.active_connections = [
                    conn
                    for conn in self.active_connections
                    if conn["id"] != connection_id
                ]

            def broadcast_event(
                self, event_type, event_data, priority="normal", source="test"
            ):
                """Broadcast an event to all matching connections."""
                event = {
                    "type": event_type,
                    "data": event_data,
                    "priority": priority,
                    "source": source,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                self.events.append(event)

                # Send to matching connections
                for connection in self.active_connections:
                    if connection["filter"](event):
                        connection["events_received"].append(event)

            def get_connection_events(self, connection_id):
                """Get events received by a specific connection."""
                for connection in self.active_connections:
                    if connection["id"] == connection_id:
                        return connection["events_received"]
                return []

        return MockSSEEventStream()

    @pytest.mark.asyncio
    async def test_thumbnail_progress_event_format(
        self, mock_sse_event_stream, mock_thumbnail_service_dependencies
    ):
        """Test thumbnail progress events are properly formatted for frontend."""
        # Setup mock SSE operations
        sse_ops = mock_thumbnail_service_dependencies["sse_ops"]

        # Add frontend connection with thumbnail filter
        def thumbnail_filter(event):
            return "thumbnail" in event["type"]

        mock_sse_event_stream.add_connection("frontend-modal", thumbnail_filter)

        # Simulate thumbnail progress events
        progress_events = [
            {
                "event_type": "thumbnail_regeneration_progress",
                "event_data": {
                    "progress": 1,
                    "total": 10,
                    "current_image": "camera_1/timelapse_123/image_001.jpg",
                    "completed": 1,
                    "errors": 0,
                },
                "priority": "normal",
                "source": "thumbnail_worker",
            },
            {
                "event_type": "thumbnail_regeneration_progress",
                "event_data": {
                    "progress": 5,
                    "total": 10,
                    "current_image": "camera_1/timelapse_123/image_005.jpg",
                    "completed": 5,
                    "errors": 0,
                },
                "priority": "normal",
                "source": "thumbnail_worker",
            },
            {
                "event_type": "thumbnail_regeneration_complete",
                "event_data": {
                    "completed": 10,
                    "total": 10,
                    "errors": 0,
                    "processing_time_seconds": 25.7,
                },
                "priority": "normal",
                "source": "thumbnail_worker",
            },
        ]

        # Broadcast events through mock SSE operations
        for event in progress_events:
            await sse_ops.create_event(**event)
            mock_sse_event_stream.broadcast_event(**event)

        # Verify events were properly formatted and filtered
        frontend_events = mock_sse_event_stream.get_connection_events("frontend-modal")
        assert len(frontend_events) == 3

        # Check progress event format
        progress_event = frontend_events[0]
        assert progress_event["type"] == "thumbnail_regeneration_progress"
        assert progress_event["data"]["progress"] == 1
        assert progress_event["data"]["total"] == 10
        assert "current_image" in progress_event["data"]
        assert "timestamp" in progress_event

        # Check completion event format
        complete_event = frontend_events[2]
        assert complete_event["type"] == "thumbnail_regeneration_complete"
        assert complete_event["data"]["completed"] == 10
        assert complete_event["data"]["processing_time_seconds"] == 25.7

    @pytest.mark.asyncio
    async def test_thumbnail_job_lifecycle_events(
        self, mock_sse_event_stream, mock_thumbnail_service_dependencies
    ):
        """Test complete thumbnail job lifecycle SSE events."""
        sse_ops = mock_thumbnail_service_dependencies["sse_ops"]

        # Add connection interested in all thumbnail events
        mock_sse_event_stream.add_connection("admin-dashboard", lambda e: True)

        # Simulate complete job lifecycle
        lifecycle_events = [
            {
                "event_type": "thumbnail_job_created",
                "event_data": {
                    "job_id": 123,
                    "image_id": 456,
                    "priority": JobPriority.HIGH,
                    "job_type": THUMBNAIL_JOB_TYPE_SINGLE,
                },
            },
            {
                "event_type": "thumbnail_job_started",
                "event_data": {
                    "job_id": 123,
                    "image_id": 456,
                    "worker_id": "thumbnail_worker_1",
                },
            },
            {
                "event_type": "thumbnail_job_progress",
                "event_data": {
                    "job_id": 123,
                    "stage": "processing",
                    "progress_percentage": 50,
                },
            },
            {
                "event_type": "thumbnail_job_completed",
                "event_data": {
                    "job_id": 123,
                    "image_id": 456,
                    "thumbnail_path": "/data/camera_1/timelapse_123/thumbnails/thumb_456.jpg",
                    "small_path": "/data/camera_1/timelapse_123/thumbnails/small_456.jpg",
                    "processing_time_ms": 1250,
                },
            },
        ]

        # Broadcast lifecycle events
        for event in lifecycle_events:
            await sse_ops.create_event(
                **event, priority="normal", source="thumbnail_system"
            )
            mock_sse_event_stream.broadcast_event(
                **event, priority="normal", source="thumbnail_system"
            )

        # Verify all lifecycle events were received
        admin_events = mock_sse_event_stream.get_connection_events("admin-dashboard")
        assert len(admin_events) == 4

        # Verify event sequence
        event_types = [e["type"] for e in admin_events]
        assert event_types == [
            "thumbnail_job_created",
            "thumbnail_job_started",
            "thumbnail_job_progress",
            "thumbnail_job_completed",
        ]

        # Verify job completion event contains file paths
        completion_event = admin_events[3]
        assert "thumbnail_path" in completion_event["data"]
        assert "small_path" in completion_event["data"]
        assert completion_event["data"]["processing_time_ms"] == 1250

    @pytest.mark.asyncio
    async def test_bulk_operation_sse_events(
        self, mock_sse_event_stream, mock_thumbnail_service_dependencies
    ):
        """Test SSE events for bulk thumbnail operations."""
        sse_ops = mock_thumbnail_service_dependencies["sse_ops"]

        # Add connection for bulk operation monitoring
        mock_sse_event_stream.add_connection(
            "bulk-monitor", lambda e: "bulk" in e["type"] or "regeneration" in e["type"]
        )

        # Simulate bulk operation events
        bulk_events = [
            {
                "event_type": "thumbnail_bulk_queued",
                "event_data": {
                    "total_jobs": 50,
                    "failed_jobs": 0,
                    "priority": JobPriority.MEDIUM,
                    "operation_id": "bulk_op_789",
                },
            },
            {
                "event_type": "thumbnail_regeneration_started",
                "event_data": {
                    "total_images": 50,
                    "operation_id": "bulk_op_789",
                    "estimated_duration_minutes": 3,
                },
            },
            {
                "event_type": "thumbnail_regeneration_progress",
                "event_data": {
                    "progress": 25,
                    "total": 50,
                    "completed": 25,
                    "errors": 1,
                    "operation_id": "bulk_op_789",
                },
            },
            {
                "event_type": "thumbnail_regeneration_complete",
                "event_data": {
                    "completed": 49,
                    "total": 50,
                    "errors": 1,
                    "operation_id": "bulk_op_789",
                    "processing_time_seconds": 145.3,
                },
            },
        ]

        # Broadcast bulk events
        for event in bulk_events:
            await sse_ops.create_event(
                **event, priority="normal", source="thumbnail_service"
            )
            mock_sse_event_stream.broadcast_event(
                **event, priority="normal", source="thumbnail_service"
            )

        # Verify bulk events were received
        bulk_monitor_events = mock_sse_event_stream.get_connection_events(
            "bulk-monitor"
        )
        assert len(bulk_monitor_events) == 4

        # Check operation tracking
        operation_ids = [e["data"].get("operation_id") for e in bulk_monitor_events]
        assert all(op_id == "bulk_op_789" for op_id in operation_ids if op_id)

    @pytest.mark.asyncio
    async def test_error_event_handling(
        self, mock_sse_event_stream, mock_thumbnail_service_dependencies
    ):
        """Test SSE error event handling and formatting."""
        sse_ops = mock_thumbnail_service_dependencies["sse_ops"]

        # Add connection for error monitoring
        mock_sse_event_stream.add_connection(
            "error-monitor", lambda e: "error" in e["type"] or "failed" in e["type"]
        )

        # Simulate various error scenarios
        error_events = [
            {
                "event_type": "thumbnail_job_failed",
                "event_data": {
                    "job_id": 999,
                    "image_id": 888,
                    "error": "File not found: /data/missing_image.jpg",
                    "error_code": "FILE_NOT_FOUND",
                    "retry_count": 3,
                    "max_retries": 3,
                },
                "priority": "high",
            },
            {
                "event_type": "thumbnail_regeneration_error",
                "event_data": {
                    "error": "Insufficient disk space for thumbnail generation",
                    "error_code": "DISK_SPACE_INSUFFICIENT",
                    "affected_jobs": 15,
                    "disk_space_available_mb": 50,
                },
                "priority": "high",
            },
            {
                "event_type": "thumbnail_worker_error",
                "event_data": {
                    "worker_id": "thumbnail_worker_1",
                    "error": "Worker process crashed during image processing",
                    "error_code": "WORKER_CRASH",
                    "restart_required": True,
                    "jobs_in_progress": 3,
                },
                "priority": "critical",
            },
        ]

        # Broadcast error events
        for event in error_events:
            await sse_ops.create_event(**event, source="thumbnail_system")
            mock_sse_event_stream.broadcast_event(**event, source="thumbnail_system")

        # Verify error events were received
        error_monitor_events = mock_sse_event_stream.get_connection_events(
            "error-monitor"
        )
        assert len(error_monitor_events) == 3

        # Check error event structure
        job_failed_event = error_monitor_events[0]
        assert job_failed_event["data"]["error_code"] == "FILE_NOT_FOUND"
        assert job_failed_event["data"]["retry_count"] == 3
        assert job_failed_event["priority"] == "high"

        disk_space_event = error_monitor_events[1]
        assert disk_space_event["data"]["affected_jobs"] == 15
        assert disk_space_event["data"]["disk_space_available_mb"] == 50

        worker_crash_event = error_monitor_events[2]
        assert worker_crash_event["data"]["restart_required"]
        assert worker_crash_event["priority"] == "critical"

    def test_event_filtering_accuracy(self, mock_sse_event_stream):
        """Test SSE event filtering matches frontend filter logic."""
        # Simulate different frontend components with specific filters

        # Modal only wants regeneration events
        def modal_filter(event):
            return event["type"] in [
                "thumbnail_regeneration_progress",
                "thumbnail_regeneration_complete",
                "thumbnail_regeneration_cancelled",
                "thumbnail_regeneration_error",
            ]

        # Dashboard wants job statistics
        def dashboard_filter(event):
            return event["type"] in [
                "thumbnail_job_created",
                "thumbnail_job_completed",
                "thumbnail_job_failed",
                "thumbnail_bulk_queued",
            ]

        # Admin panel wants everything
        def admin_filter(event):
            return "thumbnail" in event["type"]

        mock_sse_event_stream.add_connection("modal", modal_filter)
        mock_sse_event_stream.add_connection("dashboard", dashboard_filter)
        mock_sse_event_stream.add_connection("admin", admin_filter)

        # Broadcast various events
        test_events = [
            ("thumbnail_regeneration_progress", {"progress": 5}),
            ("thumbnail_job_created", {"job_id": 123}),
            ("thumbnail_worker_heartbeat", {"worker_id": "w1"}),
            ("thumbnail_regeneration_complete", {"completed": 10}),
            ("thumbnail_job_failed", {"job_id": 456}),
            ("camera_status_update", {"camera_id": 1}),  # Non-thumbnail event
        ]

        for event_type, event_data in test_events:
            mock_sse_event_stream.broadcast_event(event_type, event_data)

        # Verify filtering
        modal_events = mock_sse_event_stream.get_connection_events("modal")
        dashboard_events = mock_sse_event_stream.get_connection_events("dashboard")
        admin_events = mock_sse_event_stream.get_connection_events("admin")

        # Modal should only get regeneration events
        modal_types = [e["type"] for e in modal_events]
        assert modal_types == [
            "thumbnail_regeneration_progress",
            "thumbnail_regeneration_complete",
        ]

        # Dashboard should only get job events
        dashboard_types = [e["type"] for e in dashboard_events]
        assert dashboard_types == ["thumbnail_job_created", "thumbnail_job_failed"]

        # Admin should get all thumbnail events
        admin_types = [e["type"] for e in admin_events]
        expected_admin_types = [
            "thumbnail_regeneration_progress",
            "thumbnail_job_created",
            "thumbnail_worker_heartbeat",
            "thumbnail_regeneration_complete",
            "thumbnail_job_failed",
        ]
        assert admin_types == expected_admin_types

    @pytest.mark.asyncio
    async def test_event_priority_handling(
        self, mock_sse_event_stream, mock_thumbnail_service_dependencies
    ):
        """Test that high priority events are handled correctly."""
        sse_ops = mock_thumbnail_service_dependencies["sse_ops"]

        # Add connection that processes events differently based on priority
        priority_events = {"low": [], "normal": [], "high": [], "critical": []}

        def priority_handler(event):
            priority = event.get("priority", "normal")
            if priority in priority_events:
                priority_events[priority].append(event)
            return True

        mock_sse_event_stream.add_connection("priority-handler", priority_handler)

        # Send events with different priorities
        test_events = [
            ("thumbnail_job_created", {"job_id": 1}, "low"),
            ("thumbnail_regeneration_progress", {"progress": 5}, "normal"),
            ("thumbnail_job_failed", {"job_id": 2}, "high"),
            ("thumbnail_worker_error", {"worker_id": "w1"}, "critical"),
        ]

        for event_type, event_data, priority in test_events:
            await sse_ops.create_event(
                event_type=event_type,
                event_data=event_data,
                priority=priority,
                source="test",
            )
            mock_sse_event_stream.broadcast_event(
                event_type, event_data, priority=priority
            )

        # Verify events were categorized by priority
        assert len(priority_events["low"]) == 1
        assert len(priority_events["normal"]) == 1
        assert len(priority_events["high"]) == 1
        assert len(priority_events["critical"]) == 1

        # Verify high priority event content
        high_priority_event = priority_events["high"][0]
        assert high_priority_event["type"] == "thumbnail_job_failed"
        assert high_priority_event["priority"] == "high"

        critical_event = priority_events["critical"][0]
        assert critical_event["type"] == "thumbnail_worker_error"
        assert critical_event["priority"] == "critical"
