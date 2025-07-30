# backend/tests/database/conftest.py
"""
Shared fixtures and configuration for database operations tests.

Provides common mocking utilities and test data factories for database tests.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone
from typing import Dict, Any, List

# Note: Avoiding direct import of utc_now to prevent circular imports in tests


@pytest.fixture
def mock_async_db():
    """
    Mock async database connection for testing database operations.
    
    Returns:
        tuple: (db_mock, connection_mock, cursor_mock) for easy access in tests
    """
    db = Mock()
    conn = AsyncMock()
    cursor = AsyncMock()
    
    # Setup async context managers
    db.get_connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    db.get_connection.return_value.__aexit__ = AsyncMock(return_value=None)
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=cursor)
    conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    
    return db, conn, cursor


@pytest.fixture
def mock_sync_db():
    """
    Mock sync database connection for testing sync database operations.
    
    Returns:
        tuple: (db_mock, connection_mock, cursor_mock) for easy access in tests
    """
    db = Mock()
    conn = Mock()
    cursor = Mock()
    
    # Setup sync context managers
    db.get_connection.return_value.__enter__ = Mock(return_value=conn)
    db.get_connection.return_value.__exit__ = Mock(return_value=None)
    conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = Mock(return_value=None)
    
    return db, conn, cursor


@pytest.fixture
def mock_current_time():
    """Mock current time for consistent testing."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# Test data factories
class TestDataFactory:
    """Factory for creating consistent test data across database operation tests."""
    
    @staticmethod
    def create_camera_data(**overrides) -> Dict[str, Any]:
        """Create mock camera data."""
        defaults = {
            "id": 1,
            "name": "Test Camera",
            "enabled": True,
            "degraded_mode_active": False,
            "consecutive_corruption_failures": 0,
            "lifetime_glitch_count": 5,
            "corruption_detection_heavy": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        defaults.update(overrides)
        return defaults
    
    @staticmethod
    def create_image_data(**overrides) -> Dict[str, Any]:
        """Create mock image data."""
        defaults = {
            "id": 100,
            "camera_id": 1,
            "timelapse_id": 10,
            "file_path": "/test/image.jpg",
            "file_size": 1024000,
            "corruption_score": 85,
            "is_flagged": False,
            "captured_at": utc_now(),
            "created_at": datetime.now(timezone.utc)
        }
        defaults.update(overrides)
        return defaults
    
    @staticmethod
    def create_corruption_log_data(**overrides) -> Dict[str, Any]:
        """Create mock corruption log data."""
        defaults = {
            "id": 1,
            "camera_id": 1,
            "image_id": 100,
            "corruption_score": 75,
            "fast_score": 80,
            "heavy_score": 70,
            "detection_details": {"algorithm": "fast", "threshold": 80},
            "action_taken": "saved",
            "processing_time_ms": 150,
            "created_at": datetime.now(timezone.utc)
        }
        defaults.update(overrides)
        return defaults
    
    @staticmethod
    def create_timelapse_data(**overrides) -> Dict[str, Any]:
        """Create mock timelapse data."""
        defaults = {
            "id": 10,
            "camera_id": 1,
            "name": "Test Timelapse",
            "status": "running",
            "interval_seconds": 60,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        defaults.update(overrides)
        return defaults


@pytest.fixture
def test_data():
    """Provide test data factory to tests."""
    return TestDataFactory


# Custom pytest markers for organizing tests
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", 
        "integration: marks tests as integration tests (may require database)"
    )
    config.addinivalue_line(
        "markers",
        "caching: marks tests that specifically test caching behavior"
    )
    config.addinivalue_line(
        "markers",
        "query_builder: marks tests for SQL query builders"
    )


# Helper functions for common test patterns
def assert_has_caching_decorator(method):
    """Assert that a method has the @cached_response decorator."""
    assert hasattr(method, '__wrapped__'), f"Method {method.__name__} should have caching decorator"


def assert_sql_contains_patterns(sql: str, patterns: List[str]):
    """Assert that SQL contains all required patterns."""
    for pattern in patterns:
        assert pattern in sql, f"SQL should contain '{pattern}'"


def assert_sql_not_contains(sql: str, forbidden_patterns: List[str]):
    """Assert that SQL does not contain forbidden patterns."""
    for pattern in forbidden_patterns:
        assert pattern not in sql, f"SQL should not contain '{pattern}'"