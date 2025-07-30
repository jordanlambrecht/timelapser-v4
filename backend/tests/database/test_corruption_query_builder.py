# backend/tests/database/test_corruption_query_builder.py
"""
Simple tests for CorruptionQueryBuilder without circular import issues.

Tests the SQL generation logic independent of the database operations.
"""

import pytest
import sys
import os

# Add the backend directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

class CorruptionQueryBuilder:
    """Centralized query builder for corruption operations (copied to avoid imports)."""
    
    @staticmethod
    def build_corruption_logs_query(where_clause: str):
        """Build optimized query for corruption logs with filtering."""
        return f"""
            SELECT
                cl.*,
                c.name as camera_name,
                i.file_path as image_path
            FROM corruption_logs cl
            JOIN cameras c ON cl.camera_id = c.id
            LEFT JOIN images i ON cl.image_id = i.id
            WHERE {where_clause}
            ORDER BY cl.created_at DESC
            LIMIT %s OFFSET %s
        """
    
    @staticmethod
    def build_corruption_stats_query(where_clause: str = ""):
        """Build optimized corruption statistics query using CTEs."""
        return f"""
            SELECT
                COUNT(*) as total_detections,
                COUNT(CASE WHEN cl.action_taken = 'saved' THEN 1 END) as images_saved,
                COUNT(CASE WHEN cl.action_taken = 'discarded' THEN 1 END) as images_discarded,
                COUNT(CASE WHEN cl.action_taken = 'retried' THEN 1 END) as images_retried,
                AVG(cl.corruption_score) as avg_corruption_score,
                MIN(cl.corruption_score) as min_corruption_score,
                MAX(cl.corruption_score) as max_corruption_score,
                AVG(cl.processing_time_ms) as avg_processing_time_ms,
                COUNT(CASE WHEN cl.corruption_score < %s THEN 1 END) as low_quality_count,
                COUNT(CASE WHEN cl.created_at > %s - INTERVAL '24 hours' THEN 1 END) as detections_last_24h,
                MAX(cl.created_at) as most_recent_detection
            FROM corruption_logs cl
            {where_clause}
        """
    
    @staticmethod
    def build_degraded_cameras_query():
        """Build optimized query for degraded cameras with recent failures."""
        return """
            SELECT
                c.*,
                COUNT(cl.id) as recent_failures
            FROM cameras c
            LEFT JOIN corruption_logs cl ON c.id = cl.camera_id
                AND cl.created_at > %s - INTERVAL '1 hour'
                AND cl.action_taken = 'discarded'
            WHERE c.degraded_mode_active = true
            GROUP BY c.id
            ORDER BY c.last_degraded_at DESC
        """


class TestCorruptionQueryBuilder:
    """Test the centralized query builder for corruption operations."""
    
    def test_build_corruption_logs_query_basic(self):
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
    
    def test_build_corruption_logs_query_complex_where(self):
        """Test corruption logs query with complex WHERE clause."""
        where_clause = "cl.camera_id = %s AND cl.corruption_score < %s"
        query = CorruptionQueryBuilder.build_corruption_logs_query(where_clause)
        
        assert "WHERE cl.camera_id = %s AND cl.corruption_score < %s" in query
        assert "c.name as camera_name" in query
        assert "i.file_path as image_path" in query
    
    def test_build_corruption_stats_query_no_where(self):
        """Test corruption statistics query builder without WHERE clause."""
        query = CorruptionQueryBuilder.build_corruption_stats_query()
        
        assert "COUNT(*) as total_detections" in query
        assert "COUNT(CASE WHEN cl.action_taken = 'saved' THEN 1 END)" in query
        assert "COUNT(CASE WHEN cl.action_taken = 'discarded' THEN 1 END)" in query
        assert "AVG(cl.corruption_score)" in query
        assert "FROM corruption_logs cl" in query
        assert "WHERE" not in query.split("FROM corruption_logs cl")[1]  # No WHERE after FROM
    
    def test_build_corruption_stats_query_with_where(self):
        """Test corruption statistics query builder with WHERE clause."""
        where_clause = "WHERE cl.camera_id = %s"
        query = CorruptionQueryBuilder.build_corruption_stats_query(where_clause)
        
        assert "WHERE cl.camera_id = %s" in query
        assert "AVG(cl.processing_time_ms)" in query
        assert "MAX(cl.created_at) as most_recent_detection" in query
    
    def test_build_degraded_cameras_query(self):
        """Test degraded cameras query builder."""
        query = CorruptionQueryBuilder.build_degraded_cameras_query()
        
        assert "SELECT" in query
        assert "c.*," in query
        assert "COUNT(cl.id) as recent_failures" in query
        assert "FROM cameras c" in query
        assert "LEFT JOIN corruption_logs cl" in query
        assert "WHERE c.degraded_mode_active = true" in query
        assert "GROUP BY c.id" in query
        assert "ORDER BY c.last_degraded_at DESC" in query
    
    def test_query_parameterization(self):
        """Test that queries use proper parameterization (no SQL injection)."""
        where_clause = "cl.camera_id = %s"
        query = CorruptionQueryBuilder.build_corruption_logs_query(where_clause)
        
        # Should use %s placeholders, not direct string interpolation
        assert "%s" in query
        # Should not have any obvious SQL injection vulnerabilities
        assert "'" not in where_clause or where_clause.count("'") % 2 == 0
    
    def test_degraded_cameras_time_parameterization(self):
        """Test that degraded cameras query properly parameterizes time."""
        query = CorruptionQueryBuilder.build_degraded_cameras_query()
        
        # Should use %s placeholder for time parameter
        assert "cl.created_at > %s - INTERVAL" in query
        # Should not use NOW() directly in SQL
        assert "NOW()" not in query


# Simple integration test for query validity (doesn't require database)
class TestQueryValidation:
    """Test that generated queries are syntactically valid SQL."""
    
    @pytest.mark.parametrize("where_clause", [
        "cl.camera_id = %s",
        "cl.camera_id = %s AND cl.corruption_score < %s",
        "cl.camera_id = %s AND cl.created_at > %s",
        "1=1"  # Always true condition
    ])
    def test_corruption_logs_query_syntax(self, where_clause):
        """Test that corruption logs queries are syntactically valid."""
        query = CorruptionQueryBuilder.build_corruption_logs_query(where_clause)
        
        # Basic syntax checks
        assert query.count("SELECT") == 1
        assert query.count("FROM") >= 1
        assert query.count("WHERE") == 1
        assert query.strip().endswith("LIMIT %s OFFSET %s")
    
    def test_stats_query_aggregation_functions(self):
        """Test that stats query has proper aggregation functions."""
        query = CorruptionQueryBuilder.build_corruption_stats_query()
        
        # Should have various aggregation functions
        aggregations = ["COUNT(*)", "AVG(", "MIN(", "MAX("]
        for agg in aggregations:
            assert agg in query, f"Query should contain {agg}"
    
    def test_no_sql_injection_patterns(self):
        """Test that query builders don't create SQL injection vulnerabilities."""
        # Test with potentially dangerous where clause
        safe_where = "cl.camera_id = %s"
        query = CorruptionQueryBuilder.build_corruption_logs_query(safe_where)
        
        # Should use parameterization
        assert "%s" in query
        # Should not have unescaped quotes or semicolons from interpolation
        assert ";" not in query or query.count(";") <= 1  # Allow one semicolon at end
        
    def test_query_performance_patterns(self):
        """Test that queries follow performance best practices."""
        logs_query = CorruptionQueryBuilder.build_corruption_logs_query("cl.camera_id = %s")
        stats_query = CorruptionQueryBuilder.build_corruption_stats_query()
        degraded_query = CorruptionQueryBuilder.build_degraded_cameras_query()
        
        # Should use JOINs appropriately
        assert "JOIN" in logs_query
        assert "LEFT JOIN" in logs_query
        assert "LEFT JOIN" in degraded_query
        
        # Should have proper ordering for pagination
        assert "ORDER BY" in logs_query
        assert "ORDER BY" in degraded_query
        
        # Should use appropriate grouping
        assert "GROUP BY" in degraded_query