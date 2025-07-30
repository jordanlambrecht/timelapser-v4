# backend/tests/database/test_corruption_operations.py
"""
Simple tests for corruption operations focusing on key optimizations.

Tests the database layer optimizations we implemented:
- Caching behavior with @cached_response decorators
- ETag generation for collections 
- Query builder SQL generation
- Time management with utc_now()
- Basic CRUD operations
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List

from app.database.corruption_operations import (
    CorruptionOperations, 
    SyncCorruptionOperations,
    CorruptionQueryBuilder
)
from app.models.corruption_model import (
    CorruptionLogEntry,
    CorruptionAnalysisStats,
    CameraWithCorruption
)


class TestCorruptionQueryBuilder:
    """Test the centralized query builder for corruption operations."""
    
    def test_build_corruption_logs_query(self):
        """Test corruption logs query builder produces valid SQL."""
        where_clause = "cl.camera_id = %s"
        query = CorruptionQueryBuilder.build_corruption_logs_query(where_clause)
        
        # Basic SQL structure checks
        assert "SELECT" in query
        assert "FROM corruption_logs cl" in query
        assert "JOIN cameras c ON cl.camera_id = c.id" in query
        assert "WHERE cl.camera_id = %s" in query
        assert "ORDER BY cl.created_at DESC" in query
        assert "LIMIT %s OFFSET %s" in query
    
    def test_build_corruption_stats_query(self):
        """Test corruption statistics query builder."""
        query = CorruptionQueryBuilder.build_corruption_stats_query()
        
        assert "COUNT(*) as total_detections" in query
        assert "COUNT(CASE WHEN cl.action_taken = 'saved' THEN 1 END)" in query
        assert "AVG(cl.corruption_score)" in query
        assert "FROM corruption_logs cl" in query
    
    def test_build_degraded_cameras_query(self):
        """Test degraded cameras query builder."""
        query = CorruptionQueryBuilder.build_degraded_cameras_query()
        
        assert "SELECT" in query
        assert "FROM cameras c" in query
        assert "LEFT JOIN corruption_logs cl" in query
        assert "WHERE c.degraded_mode_active = true" in query
        assert "GROUP BY c.id" in query


class TestCorruptionOperations:
    """Test async corruption operations with focus on caching and ETag behavior."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock async database connection."""
        db = Mock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        # Setup mock connection context managers
        db.get_connection.return_value.__aenter__ = AsyncMock(return_value=conn)
        db.get_connection.return_value.__aexit__ = AsyncMock(return_value=None)
        conn.cursor.return_value.__aenter__ = AsyncMock(return_value=cursor)
        conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
        
        return db, conn, cursor
    
    @pytest.fixture
    def corruption_ops(self, mock_db):
        """Create CorruptionOperations instance with mocked database."""
        db, _, _ = mock_db
        return CorruptionOperations(db)
    
    @pytest.mark.asyncio
    async def test_get_corruption_logs_basic(self, corruption_ops, mock_db):
        """Test basic corruption logs retrieval."""
        db, conn, cursor = mock_db
        
        # Mock database results
        cursor.fetchall.side_effect = [
            [{"total_count": 2}],  # Count query
            [
                {
                    "id": 1,
                    "camera_id": 1,
                    "corruption_score": 85,
                    "action_taken": "saved",
                    "created_at": datetime.now()
                },
                {
                    "id": 2, 
                    "camera_id": 1,
                    "corruption_score": 45,
                    "action_taken": "discarded",
                    "created_at": datetime.now()
                }
            ]
        ]
        
        # Test the method
        result = await corruption_ops.get_corruption_logs(camera_id=1, page=1, page_size=10)
        
        # Verify results
        assert result.total_count == 2
        assert result.page == 1
        assert result.page_size == 10
        assert len(result.logs) == 2
        assert result.logs[0].corruption_score == 85
        assert result.logs[1].action_taken == "discarded"
        
        # Verify database calls
        assert cursor.execute.call_count == 2  # Count + data queries
    
    @pytest.mark.asyncio
    async def test_get_degraded_cameras_caching(self, corruption_ops, mock_db):
        """Test that degraded cameras method has caching decorator."""
        # Check that the method has @cached_response decorator
        method = corruption_ops.get_degraded_cameras
        
        # The cached_response decorator should wrap the original method
        assert hasattr(method, '__wrapped__')  # Indicates it's decorated
    
    @pytest.mark.asyncio 
    async def test_get_camera_corruption_history_caching(self, corruption_ops, mock_db):
        """Test that camera history method has caching decorator."""
        method = corruption_ops.get_camera_corruption_history
        
        # Should have caching decorator
        assert hasattr(method, '__wrapped__')
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_called(self, corruption_ops, mock_db):
        """Test that cache invalidation is called on updates."""
        db, conn, cursor = mock_db
        cursor.rowcount = 1  # Simulate successful update
        
        # Call a method that should invalidate cache
        result = await corruption_ops.reset_camera_degraded_mode(camera_id=123)
        
        # Verify the method succeeded
        assert result is True
        
        # Verify cache clearing was attempted (we can't easily test the actual cache clearing without more setup)
        assert cursor.execute.called
    
    @pytest.mark.asyncio
    async def test_utc_now_usage(self, corruption_ops, mock_db):
        """Test that methods use utc_now() instead of NOW() in SQL."""
        db, conn, cursor = mock_db
        cursor.fetchall.return_value = []
        
        # Call a method that should use utc_now()
        await corruption_ops.get_camera_corruption_history(camera_id=1, hours=24)
        
        # Check that execute was called (we can't easily inspect the exact SQL without more complex mocking)
        assert cursor.execute.called
        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        
        # Should not contain NOW() in SQL
        assert "NOW()" not in sql
        # Should have parameters (including timestamp from utc_now())
        assert len(params) >= 2


class TestSyncCorruptionOperations:
    """Test sync corruption operations for worker processes."""
    
    @pytest.fixture
    def mock_sync_db(self):
        """Mock sync database connection."""
        db = Mock()
        conn = Mock()
        cursor = Mock()
        
        # Setup mock connection context managers
        db.get_connection.return_value.__enter__ = Mock(return_value=conn)
        db.get_connection.return_value.__exit__ = Mock(return_value=None)
        conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
        conn.cursor.return_value.__exit__ = Mock(return_value=None)
        
        return db, conn, cursor
    
    @pytest.fixture
    def sync_corruption_ops(self, mock_sync_db):
        """Create SyncCorruptionOperations instance."""
        db, _, _ = mock_sync_db
        return SyncCorruptionOperations(db)
    
    def test_log_corruption_detection(self, sync_corruption_ops, mock_sync_db):
        """Test logging corruption detection results."""
        db, conn, cursor = mock_sync_db
        
        # Mock successful database insert
        cursor.fetchall.return_value = [{
            "id": 123,
            "camera_id": 1,
            "corruption_score": 75,
            "action_taken": "saved",
            "created_at": datetime.now()
        }]
        
        # Test the method
        result = sync_corruption_ops.log_corruption_detection(
            camera_id=1,
            image_id=456,
            corruption_score=75,
            fast_score=80,
            heavy_score=70,
            detection_details={"test": "data"},
            action_taken="saved",
            processing_time_ms=150
        )
        
        # Verify result
        assert isinstance(result, CorruptionLogEntry)
        assert result.corruption_score == 75
        assert result.action_taken == "saved"
        
        # Verify database interaction
        assert cursor.execute.called
    
    def test_get_corruption_settings(self, sync_corruption_ops, mock_sync_db):
        """Test getting corruption settings."""
        db, conn, cursor = mock_sync_db
        
        # Mock settings data
        cursor.fetchall.return_value = [
            {"key": "corruption_threshold", "value": "80"},
            {"key": "corruption_enabled", "value": "true"}
        ]
        
        # Test the method
        settings = sync_corruption_ops.get_corruption_settings()
        
        # Verify results
        assert settings["corruption_threshold"] == 80  # Should be converted to int
        assert settings["corruption_enabled"] is True  # Should be converted to bool
        
        # Verify database query
        assert cursor.execute.called
        sql = cursor.execute.call_args[0][0]
        assert "WHERE key LIKE 'corruption_%'" in sql


@pytest.mark.integration
class TestCorruptionOperationsIntegration:
    """
    Integration tests that would run against a real test database.
    
    These are marked with @pytest.mark.integration so they can be run separately
    when a test database is available.
    """
    
    @pytest.mark.skip(reason="Requires test database setup")
    def test_full_corruption_workflow(self):
        """Test complete corruption detection workflow end-to-end."""
        # This would test:
        # 1. Create test camera and timelapse
        # 2. Log corruption detection
        # 3. Verify statistics are updated
        # 4. Test cache invalidation
        # 5. Clean up test data
        pass
    
    @pytest.mark.skip(reason="Requires test database setup") 
    def test_cache_performance(self):
        """Test that caching actually improves performance."""
        # This would test:
        # 1. Time first call (cache miss)
        # 2. Time second call (cache hit)
        # 3. Verify cache hit is significantly faster
        pass


# Utility functions for test data generation
def create_mock_corruption_log(**kwargs) -> dict:
    """Create mock corruption log data for testing."""
    defaults = {
        "id": 1,
        "camera_id": 1,
        "image_id": 100,
        "corruption_score": 85,
        "fast_score": 80,
        "heavy_score": 90,
        "detection_details": {"test": "data"},
        "action_taken": "saved",
        "processing_time_ms": 150,
        "created_at": datetime.now()
    }
    defaults.update(kwargs)
    return defaults


def create_mock_camera_with_corruption(**kwargs) -> dict:
    """Create mock camera with corruption data for testing."""
    defaults = {
        "id": 1,
        "name": "Test Camera",
        "degraded_mode_active": True,
        "consecutive_corruption_failures": 3,
        "recent_failures": 5
    }
    defaults.update(kwargs)
    return defaults