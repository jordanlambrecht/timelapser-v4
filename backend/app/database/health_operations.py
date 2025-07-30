# backend/app/database/health_operations.py
"""
Health monitoring database operations module - Composition Pattern.

This module handles health-specific database operations including:
- Database connectivity tests
- Connection pool statistics
- Application health metrics
- Health check queries
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import time
from loguru import logger
import psycopg

from app.models.health_model import ApplicationMetrics
from .core import AsyncDatabase, SyncDatabase
from ..constants import DEFAULT_CORRUPTION_HISTORY_HOURS
from ..utils.time_utils import utc_now
from ..utils.cache_manager import (
    cache,
    cached_response,
    generate_timestamp_etag,
)
from ..utils.cache_invalidation import CacheInvalidationService


class HealthQueryBuilder:
    """Centralized query builder for health monitoring operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_cameras_status ON cameras(status) WHERE status = 'active';
    - CREATE INDEX idx_timelapses_status ON timelapses(status) WHERE status = 'running';
    - CREATE INDEX idx_images_captured_at ON images(captured_at DESC);
    - CREATE INDEX idx_video_jobs_status ON video_generation_jobs(status);
    - CREATE INDEX idx_images_timelapse_id ON images(timelapse_id);
    - CREATE INDEX idx_video_jobs_timelapse_id ON video_generation_jobs(timelapse_id);
    - CREATE INDEX idx_cameras_active_timelapse ON cameras(active_timelapse_id) WHERE status = 'active';
    """

    @staticmethod
    def build_application_metrics_query():
        """Build optimized query for application metrics using named parameters and FILTER clauses."""
        return """
            WITH camera_stats AS (
                SELECT
                    COUNT(*) as total_cameras,
                    COUNT(*) FILTER (WHERE status = 'active') as active_cameras
                FROM cameras
            ),
            timelapse_stats AS (
                SELECT COUNT(*) as running_timelapses
                FROM timelapses
                WHERE status = 'running'
            ),
            activity_stats AS (
                SELECT COUNT(*) as images_last_24h
                FROM images
                WHERE captured_at > %(current_time)s - INTERVAL %(hours)s * INTERVAL '1 hour'
            ),
            video_stats AS (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_jobs
                FROM video_generation_jobs
            )
            SELECT
                cs.total_cameras,
                cs.active_cameras,
                ts.running_timelapses,
                acts.images_last_24h,
                vs.pending_jobs,
                vs.processing_jobs
            FROM camera_stats cs
            CROSS JOIN timelapse_stats ts
            CROSS JOIN activity_stats acts
            CROSS JOIN video_stats vs
        """

    @staticmethod
    def build_integrity_checks_query():
        """Build optimized query for database integrity checks using modern PostgreSQL features."""
        return """
            WITH orphaned_images AS (
                SELECT COUNT(*) as count
                FROM images i
                WHERE NOT EXISTS (
                    SELECT 1 FROM timelapses t WHERE t.id = i.timelapse_id
                )
            ),
            cameras_without_timelapse AS (
                SELECT COUNT(*) as count
                FROM cameras c
                WHERE c.status = 'active'
                    AND c.active_timelapse_id IS NULL
            ),
            orphaned_video_jobs AS (
                SELECT COUNT(*) as count
                FROM video_generation_jobs vgj
                WHERE NOT EXISTS (
                    SELECT 1 FROM timelapses t WHERE t.id = vgj.timelapse_id
                )
            )
            SELECT
                oi.count as orphaned_images,
                cwt.count as cameras_without_timelapse,
                ovj.count as orphaned_video_jobs
            FROM orphaned_images oi
            CROSS JOIN cameras_without_timelapse cwt
            CROSS JOIN orphaned_video_jobs ovj
        """

    @staticmethod
    def build_database_size_query():
        """Build optimized query for database size statistics."""
        return """
            SELECT
                pg_database_size(current_database()) as total_size_bytes,
                (
                    SELECT SUM(pg_total_relation_size(schemaname||'.'||tablename))
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                ) as tables_size_bytes,
                (
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                ) as table_count
        """


class HealthOperations:
    """Health monitoring database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db
        self.cache_invalidation = CacheInvalidationService()

    async def _clear_health_caches(self, updated_at: Optional[datetime] = None) -> None:
        """Clear caches related to health operations using sophisticated cache system."""
        # Clear health-related caches using advanced cache manager
        cache_patterns = [
            "health:get_application_metrics",
            "health:get_database_health",
            "health:test_database_connectivity",
        ]

        # Use ETag-aware invalidation if timestamp provided
        if updated_at:
            etag = generate_timestamp_etag(updated_at)
            await self.cache_invalidation.invalidate_with_etag_validation(
                "health:metadata", etag
            )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    @cached_response(ttl_seconds=10, key_prefix="health")
    async def test_database_connectivity(
        self,
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Test database connectivity and measure latency.

        Returns:
            Tuple of (success, latency_ms, error_message)
        """
        try:
            start_time = time.time()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()
            latency_ms = (time.time() - start_time) * 1000
            return True, latency_ms, None
        except (psycopg.Error, ConnectionError, OSError) as e:
            logger.error(f"Database connectivity test failed: {e}")
            return False, None, str(e)

    async def get_connection_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        try:
            # Try to get pool stats if the method exists
            if hasattr(self.db, "get_pool_stats"):
                return await self.db.get_pool_stats()
            # Fallback basic stats
            return {
                "status": "healthy",
                "note": "Basic pool monitoring - detailed stats not available",
            }
        except (psycopg.Error, AttributeError, ConnectionError) as e:
            logger.error(f"Failed to get connection pool stats: {e}")
            return {"status": "error", "error": str(e)}

    @cached_response(ttl_seconds=30, key_prefix="health")
    async def get_application_metrics(self) -> ApplicationMetrics:
        """
        Get application-specific health metrics from database with 30s caching.

        Returns:
            ApplicationMetrics model with current system statistics
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use centralized query builder with named parameters
                    query = HealthQueryBuilder.build_application_metrics_query()
                    params = {
                        "current_time": utc_now(),
                        "hours": DEFAULT_CORRUPTION_HISTORY_HOURS,
                    }
                    await cur.execute(query, params)
                    metrics = await cur.fetchone()

                    return ApplicationMetrics(
                        total_cameras=metrics["total_cameras"],
                        active_cameras=metrics["active_cameras"],
                        running_timelapses=metrics["running_timelapses"],
                        images_last_24h=metrics["images_last_24h"],
                        pending_video_jobs=metrics["pending_jobs"],
                        processing_video_jobs=metrics["processing_jobs"],
                    )

        except (psycopg.Error, ConnectionError, KeyError) as e:
            logger.error(f"Failed to get application metrics: {e}")
            # Return safe defaults in case of error
            return ApplicationMetrics(
                total_cameras=0,
                active_cameras=0,
                running_timelapses=0,
                images_last_24h=0,
                pending_video_jobs=0,
                processing_video_jobs=0,
            )

    @cached_response(ttl_seconds=60, key_prefix="health")
    async def check_database_integrity(self) -> Dict[str, Any]:
        """
        Perform basic database integrity checks with 60s caching.

        Returns:
            Dictionary with integrity check results
        """

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Use centralized query builder for batch integrity checks
                    query = HealthQueryBuilder.build_integrity_checks_query()
                    await cur.execute(query)
                    checks_data = await cur.fetchone()

                    checks = {
                        "orphaned_images": checks_data["orphaned_images"],
                        "cameras_without_active_timelapse": checks_data[
                            "cameras_without_timelapse"
                        ],
                        "orphaned_video_jobs": checks_data["orphaned_video_jobs"],
                    }

                    result = {
                        "status": "healthy",
                        "checks": checks,
                        "warnings": [
                            warning
                            for warning in [
                                (
                                    f"Found {checks['orphaned_images']} orphaned images"
                                    if checks["orphaned_images"] > 0
                                    else None
                                ),
                                (
                                    f"Found {checks['cameras_without_active_timelapse']} "
                                    f"active cameras without timelapse"
                                    if checks["cameras_without_active_timelapse"] > 0
                                    else None
                                ),
                                (
                                    f"Found {checks['orphaned_video_jobs']} orphaned video jobs"
                                    if checks["orphaned_video_jobs"] > 0
                                    else None
                                ),
                            ]
                            if warning is not None
                        ],
                    }

                    return result

        except (psycopg.Error, ConnectionError, KeyError) as e:
            logger.error(f"Database integrity check failed: {e}")
            return {"status": "error", "error": str(e)}

    @cached_response(ttl_seconds=120, key_prefix="health")
    async def get_database_size_stats(self) -> Dict[str, Any]:
        """
        Get database size statistics with 2-minute caching.

        Returns:
            Dictionary with database size information
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    query = HealthQueryBuilder.build_database_size_query()
                    await cur.execute(query)
                    size_data = await cur.fetchone()

                    return {
                        "total_size_bytes": size_data["total_size_bytes"] or 0,
                        "total_size_mb": round(
                            (size_data["total_size_bytes"] or 0) / (1024 * 1024), 2
                        ),
                        "tables_size_bytes": size_data["tables_size_bytes"] or 0,
                        "tables_size_mb": round(
                            (size_data["tables_size_bytes"] or 0) / (1024 * 1024), 2
                        ),
                        "table_count": size_data["table_count"] or 0,
                    }
        except (psycopg.Error, ConnectionError, KeyError) as e:
            logger.error(f"Failed to get database size stats: {e}")
            return {
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "tables_size_bytes": 0,
                "tables_size_mb": 0.0,
                "table_count": 0,
                "error": str(e),
            }

    async def get_comprehensive_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check combining multiple metrics efficiently.

        Returns:
            Dictionary with complete health assessment
        """
        try:
            # Run connectivity test first as it's fastest
            connectivity_ok, latency, conn_error = (
                await self.test_database_connectivity()
            )

            if not connectivity_ok:
                return {
                    "status": "critical",
                    "connectivity": {"status": "failed", "error": conn_error},
                    "metrics": None,
                    "integrity": None,
                    "pool_stats": None,
                }

            # If connectivity is OK, run other checks in parallel would be ideal,
            # but for now run sequentially to avoid overwhelming the database

            metrics = await self.get_application_metrics()
            integrity = await self.check_database_integrity()
            pool_stats = await self.get_connection_pool_stats()

            overall_status = "healthy"
            if integrity.get("warnings"):
                overall_status = "warning"

            return {
                "status": overall_status,
                "connectivity": {
                    "status": "ok",
                    "latency_ms": round(latency, 2) if latency else None,
                },
                "metrics": (
                    metrics.model_dump()
                    if hasattr(metrics, "model_dump")
                    else metrics.__dict__
                ),
                "integrity": integrity,
                "pool_stats": pool_stats,
                "timestamp": utc_now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Comprehensive health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": utc_now().isoformat(),
            }


class SyncHealthOperations:
    """Sync version of health operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def test_database_connectivity(self) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Test sync database connectivity and measure latency.

        Returns:
            Tuple of (success, latency_ms, error_message)
        """
        try:
            start_time = time.time()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            latency_ms = (time.time() - start_time) * 1000
            return True, latency_ms, None
        except (psycopg.Error, ConnectionError, OSError) as e:
            logger.error(f"Sync database connectivity test failed: {e}")
            return False, None, str(e)

    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """
        Get sync connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        try:
            # Sync database typically doesn't have detailed pool stats
            return {
                "status": "healthy",
                "note": "Sync pool monitoring - detailed stats not available",
            }
        except (psycopg.Error, AttributeError, ConnectionError) as e:
            logger.error(f"Failed to get sync connection pool stats: {e}")
            return {"status": "error", "error": str(e)}

    def get_application_metrics(self) -> ApplicationMetrics:
        """
        Get application-specific health metrics from database (sync version).

        Returns:
            ApplicationMetrics model with current system statistics
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use centralized query builder with named parameters
                    query = HealthQueryBuilder.build_application_metrics_query()
                    params = {
                        "current_time": utc_now(),
                        "hours": DEFAULT_CORRUPTION_HISTORY_HOURS,
                    }
                    cur.execute(query, params)
                    metrics = cur.fetchone()

                    return ApplicationMetrics(
                        total_cameras=metrics["total_cameras"],
                        active_cameras=metrics["active_cameras"],
                        running_timelapses=metrics["running_timelapses"],
                        images_last_24h=metrics["images_last_24h"],
                        pending_video_jobs=metrics["pending_jobs"],
                        processing_video_jobs=metrics["processing_jobs"],
                    )

        except (psycopg.Error, ConnectionError, KeyError) as e:
            logger.error(f"Failed to get sync application metrics: {e}")
            # Return safe defaults in case of error
            return ApplicationMetrics(
                total_cameras=0,
                active_cameras=0,
                running_timelapses=0,
                images_last_24h=0,
                pending_video_jobs=0,
                processing_video_jobs=0,
            )

    def check_database_integrity(self) -> Dict[str, Any]:
        """
        Perform basic database integrity checks (sync version).

        Returns:
            Dictionary with integrity check results
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use centralized query builder for batch integrity checks
                    query = HealthQueryBuilder.build_integrity_checks_query()
                    cur.execute(query)
                    checks_data = cur.fetchone()

                    checks = {
                        "orphaned_images": checks_data["orphaned_images"],
                        "cameras_without_active_timelapse": checks_data[
                            "cameras_without_timelapse"
                        ],
                        "orphaned_video_jobs": checks_data["orphaned_video_jobs"],
                    }

                    result = {
                        "status": "healthy",
                        "checks": checks,
                        "warnings": [
                            warning
                            for warning in [
                                (
                                    f"Found {checks['orphaned_images']} orphaned images"
                                    if checks["orphaned_images"] > 0
                                    else None
                                ),
                                (
                                    f"Found {checks['cameras_without_active_timelapse']} "
                                    f"active cameras without timelapse"
                                    if checks["cameras_without_active_timelapse"] > 0
                                    else None
                                ),
                                (
                                    f"Found {checks['orphaned_video_jobs']} orphaned video jobs"
                                    if checks["orphaned_video_jobs"] > 0
                                    else None
                                ),
                            ]
                            if warning is not None
                        ],
                    }

                    return result

        except (psycopg.Error, ConnectionError, KeyError) as e:
            logger.error(f"Sync database integrity check failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_database_size_stats(self) -> Dict[str, Any]:
        """
        Get database size statistics (sync version).

        Returns:
            Dictionary with database size information
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = HealthQueryBuilder.build_database_size_query()
                    cur.execute(query)
                    size_data = cur.fetchone()

                    return {
                        "total_size_bytes": size_data["total_size_bytes"] or 0,
                        "total_size_mb": round(
                            (size_data["total_size_bytes"] or 0) / (1024 * 1024), 2
                        ),
                        "tables_size_bytes": size_data["tables_size_bytes"] or 0,
                        "tables_size_mb": round(
                            (size_data["tables_size_bytes"] or 0) / (1024 * 1024), 2
                        ),
                        "table_count": size_data["table_count"] or 0,
                    }
        except (psycopg.Error, ConnectionError, KeyError) as e:
            logger.error(f"Failed to get sync database size stats: {e}")
            return {
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "tables_size_bytes": 0,
                "tables_size_mb": 0.0,
                "table_count": 0,
                "error": str(e),
            }
