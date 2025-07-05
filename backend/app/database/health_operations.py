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
import time
from loguru import logger

from app.models.health_model import ApplicationMetrics
from .core import AsyncDatabase, SyncDatabase
from ..constants import DEFAULT_CORRUPTION_HISTORY_HOURS


class HealthOperations:
    """Health monitoring database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db

    async def test_database_connectivity(self) -> Tuple[bool, Optional[float], Optional[str]]:
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
        except Exception as e:
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
            if hasattr(self.db, 'get_pool_stats'):
                return await self.db.get_pool_stats()
            else:
                # Fallback basic stats
                return {
                    "status": "healthy",
                    "note": "Basic pool monitoring - detailed stats not available"
                }
        except Exception as e:
            logger.error(f"Failed to get connection pool stats: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_application_metrics(self) -> ApplicationMetrics:
        """
        Get application-specific health metrics from database.
        
        Returns:
            ApplicationMetrics model with current system statistics
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Get camera statistics
                    await cur.execute("""
                        SELECT 
                            COUNT(*) as total_cameras,
                            COUNT(CASE WHEN status = 'active' THEN 1 END) as active_cameras
                        FROM cameras
                    """)
                    camera_stats = await cur.fetchone()

                    # Get timelapse statistics
                    await cur.execute("""
                        SELECT COUNT(*) as running_timelapses
                        FROM timelapses 
                        WHERE status = 'running'
                    """)
                    timelapse_stats = await cur.fetchone()

                    # Get recent activity
                    await cur.execute(f"""
                        SELECT COUNT(*) as images_last_24h
                        FROM images 
                        WHERE captured_at > NOW() - INTERVAL '{DEFAULT_CORRUPTION_HISTORY_HOURS} hours'
                    """)
                    activity_stats = await cur.fetchone()

                    # Get video generation queue
                    await cur.execute("""
                        SELECT 
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_jobs,
                            COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_jobs
                        FROM video_generation_jobs
                    """)
                    video_stats = await cur.fetchone()

                    return ApplicationMetrics(
                        total_cameras=camera_stats['total_cameras'],
                        active_cameras=camera_stats['active_cameras'],
                        running_timelapses=timelapse_stats['running_timelapses'],
                        images_last_24h=activity_stats['images_last_24h'],
                        pending_video_jobs=video_stats['pending_jobs'],
                        processing_video_jobs=video_stats['processing_jobs']
                    )

        except Exception as e:
            logger.error(f"Failed to get application metrics: {e}")
            # Return safe defaults in case of error
            return ApplicationMetrics(
                total_cameras=0,
                active_cameras=0,
                running_timelapses=0,
                images_last_24h=0,
                pending_video_jobs=0,
                processing_video_jobs=0
            )

    async def check_database_integrity(self) -> Dict[str, Any]:
        """
        Perform basic database integrity checks.
        
        Returns:
            Dictionary with integrity check results
        """
        try:
            checks = {}
            
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # Check for orphaned images (images without valid timelapse)
                    await cur.execute("""
                        SELECT COUNT(*) as orphaned_images
                        FROM images i 
                        LEFT JOIN timelapses t ON i.timelapse_id = t.id 
                        WHERE t.id IS NULL
                    """)
                    orphaned_result = await cur.fetchone()
                    checks['orphaned_images'] = orphaned_result['orphaned_images']

                    # Check for cameras without active timelapse but status active
                    await cur.execute("""
                        SELECT COUNT(*) as cameras_without_timelapse
                        FROM cameras c 
                        WHERE c.status = 'active' 
                        AND c.active_timelapse_id IS NULL
                    """)
                    camera_result = await cur.fetchone()
                    checks['cameras_without_active_timelapse'] = camera_result['cameras_without_timelapse']

                    # Check for video generation jobs without valid timelapse
                    await cur.execute("""
                        SELECT COUNT(*) as orphaned_video_jobs
                        FROM video_generation_jobs vgj
                        LEFT JOIN timelapses t ON vgj.timelapse_id = t.id
                        WHERE t.id IS NULL
                    """)
                    job_result = await cur.fetchone()
                    checks['orphaned_video_jobs'] = job_result['orphaned_video_jobs']

            return {
                "status": "healthy",
                "checks": checks,
                "warnings": [
                    f"Found {checks['orphaned_images']} orphaned images" 
                    if checks['orphaned_images'] > 0 else None,
                    f"Found {checks['cameras_without_active_timelapse']} active cameras without timelapse"
                    if checks['cameras_without_active_timelapse'] > 0 else None,
                    f"Found {checks['orphaned_video_jobs']} orphaned video jobs"
                    if checks['orphaned_video_jobs'] > 0 else None
                ]
            }

        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
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
        except Exception as e:
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
                "note": "Sync pool monitoring - detailed stats not available"
            }
        except Exception as e:
            logger.error(f"Failed to get sync connection pool stats: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
