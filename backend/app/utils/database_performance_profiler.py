# backend/app/utils/performance_profiler.py
"""
Database Performance Profiler

Comprehensive performance analysis tool for database operations.
Identifies bottlenecks, provides optimization recommendations, and tracks performance trends.
"""

import time
from typing import Any, Dict, List, Optional

from ..database.camera_operations import AsyncCameraOperations
from ..database.core import AsyncDatabase
from ..database.image_operations import AsyncImageOperations
from ..enums import LoggerName
from ..services.logger import get_service_logger
from .database_helpers import DatabaseBenchmark
from .time_utils import utc_now

logger = get_service_logger(LoggerName.SYSTEM)


class DatabasePerformanceProfiler:
    """
    Advanced database performance profiler.

    Provides comprehensive performance analysis including:
    - Operation benchmarking
    - Query optimization recommendations
    - Connection pool performance analysis
    - Micro-optimization opportunities identification
    """

    def __init__(self, db: AsyncDatabase, settings_service=None):
        """Initialize profiler with database instance and optional settings service."""
        self.db = db
        self.settings_service = settings_service
        self.benchmark = DatabaseBenchmark()
        self.profiles = {}
        self.baseline_metrics = {}
        self._settings_ops = None

    async def profile_camera_operations(self) -> Dict[str, Any]:
        """
        Profile camera database operations for performance bottlenecks.

        Returns:
            Dictionary containing performance metrics and recommendations
        """
        camera_ops = AsyncCameraOperations(self.db, None)
        results = {}

        # Profile get_cameras operation
        result, metrics = await self.benchmark.benchmark_operation(
            "get_cameras", camera_ops.get_cameras
        )
        results["get_cameras"] = {
            "metrics": metrics,
            "result_count": len(result) if result else 0,
            "recommendations": self._analyze_get_cameras_performance(
                metrics, len(result) if result else 0
            ),
        }

        # Profile get_active_cameras operation
        result, metrics = await self.benchmark.benchmark_operation(
            "get_active_cameras", camera_ops.get_active_cameras
        )
        results["get_active_cameras"] = {
            "metrics": metrics,
            "result_count": len(result) if result else 0,
            "recommendations": self._analyze_active_cameras_performance(
                metrics, len(result) if result else 0
            ),
        }

        # Profile individual camera lookup
        if result and len(result) > 0:
            camera_id = result[0].id
            result, metrics = await self.benchmark.benchmark_operation(
                "get_camera_by_id", camera_ops.get_camera_by_id, camera_id
            )
            results["get_camera_by_id"] = {
                "metrics": metrics,
                "found": result is not None,
                "recommendations": self._analyze_single_camera_performance(metrics),
            }

        return results

    async def profile_image_operations(self) -> Dict[str, Any]:
        """
        Profile image database operations for performance analysis.

        Returns:
            Dictionary containing performance metrics and recommendations
        """
        image_ops = AsyncImageOperations(self.db)
        results = {}

        # Profile get_images with pagination
        result, metrics = await self.benchmark.benchmark_operation(
            "get_images_paginated",
            image_ops.get_images,
            None,  # timelapse_id
            1,  # page
            50,  # page_size
        )
        results["get_images_paginated"] = {
            "metrics": metrics,
            "result_count": len(result) if result else 0,
            "recommendations": self._analyze_pagination_performance(metrics, 50),
        }

        return results

    async def profile_settings_operations(self) -> Dict[str, Any]:
        """
        Profile settings database operations.

        Returns:
            Dictionary containing performance metrics and recommendations
        """
        # For profiling, we need direct access to SettingsOperations to benchmark it
        # This is one of the few legitimate uses of direct instantiation
        if self._settings_ops is None:
            from ..database.settings_operations import SettingsOperations

            self._settings_ops = SettingsOperations(self.db)

        results = {}

        # Profile get_all_settings
        result, metrics = await self.benchmark.benchmark_operation(
            "get_all_settings", self._settings_ops.get_all_settings
        )
        results["get_all_settings"] = {
            "metrics": metrics,
            "settings_count": len(result) if result else 0,
            "recommendations": self._analyze_settings_performance(
                metrics, len(result) if result else 0
            ),
        }

        return results

    async def profile_connection_pool(self) -> Dict[str, Any]:
        """
        Profile database connection pool performance.

        Returns:
            Dictionary containing connection pool analysis and recommendations
        """
        # Get pool statistics
        pool_stats = await self.db.get_pool_stats()

        # Test connection acquisition performance
        connection_times = []
        for i in range(10):
            start_time = time.time()
            try:
                async with self.db.get_connection() as conn:
                    # Simple query to test connection
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        await cur.fetchone()
                connection_time = (time.time() - start_time) * 1000
                connection_times.append(connection_time)
            except Exception as e:
                logger.error(f"Connection test failed: {e}")
                connection_times.append(999999)  # Penalty for failed connection

        avg_connection_time = sum(connection_times) / len(connection_times)
        max_connection_time = max(connection_times)
        min_connection_time = min(connection_times)

        return {
            "pool_stats": pool_stats,
            "connection_performance": {
                "average_time_ms": round(avg_connection_time, 2),
                "max_time_ms": round(max_connection_time, 2),
                "min_time_ms": round(min_connection_time, 2),
                "all_times": [round(t, 2) for t in connection_times],
            },
            "recommendations": self._analyze_connection_pool_performance(
                pool_stats, avg_connection_time, max_connection_time
            ),
        }

    async def run_comprehensive_profile(self) -> Dict[str, Any]:
        """
        Run a comprehensive performance profile of all database operations.

        Returns:
            Complete performance analysis with recommendations
        """
        logger.info("Starting comprehensive database performance profiling...")

        start_time = time.time()

        try:
            # Profile different operation categories
            camera_profile = await self.profile_camera_operations()
            image_profile = await self.profile_image_operations()
            settings_profile = await self.profile_settings_operations()
            pool_profile = await self.profile_connection_pool()

            total_time = time.time() - start_time

            # Generate comprehensive analysis
            analysis = {
                "profile_summary": {
                    "timestamp": utc_now().isoformat(),
                    "total_profile_time_seconds": round(total_time, 2),
                    "categories_analyzed": [
                        "cameras",
                        "images",
                        "settings",
                        "connection_pool",
                    ],
                },
                "camera_operations": camera_profile,
                "image_operations": image_profile,
                "settings_operations": settings_profile,
                "connection_pool": pool_profile,
                "overall_recommendations": self._generate_overall_recommendations(
                    camera_profile, image_profile, settings_profile, pool_profile
                ),
                "performance_benchmarks": self.benchmark.get_performance_summary(),
            }

            logger.info(f"Performance profiling completed in {total_time:.2f} seconds")
            return analysis

        except Exception as e:
            logger.error(f"Performance profiling failed: {e}")
            raise

    def _analyze_get_cameras_performance(
        self, metrics: Dict[str, Any], result_count: int
    ) -> List[str]:
        """Analyze get_cameras operation performance and provide recommendations."""
        recommendations = []

        execution_time = metrics.get("execution_time_ms", 0)

        if execution_time > 500:  # 500ms threshold
            recommendations.append(
                f"get_cameras is slow ({execution_time:.2f}ms) - consider query optimization"
            )

        if result_count > 100:
            recommendations.append(
                f"Large result set ({result_count} cameras) - consider pagination or filtering"
            )

        if execution_time > 100 and result_count < 10:
            recommendations.append(
                "Query appears inefficient for small result set - check query plan"
            )

        if not recommendations:
            recommendations.append("Performance is within acceptable limits")

        return recommendations

    def _analyze_active_cameras_performance(
        self, metrics: Dict[str, Any], result_count: int
    ) -> List[str]:
        """Analyze get_active_cameras operation performance."""
        recommendations = []

        execution_time = metrics.get("execution_time_ms", 0)

        if execution_time > 200:  # 200ms threshold for active cameras
            recommendations.append(
                f"get_active_cameras is slow ({execution_time:.2f}ms) - this is a critical path"
            )

        if result_count == 0:
            recommendations.append(
                "No active cameras found - verify camera configuration"
            )

        if not recommendations:
            recommendations.append("Active camera query performance is good")

        return recommendations

    def _analyze_single_camera_performance(self, metrics: Dict[str, Any]) -> List[str]:
        """Analyze single camera lookup performance."""
        recommendations = []

        execution_time = metrics.get("execution_time_ms", 0)

        if execution_time > 50:  # 50ms threshold for single record
            recommendations.append(
                f"Single camera lookup is slow ({execution_time:.2f}ms) - check indexes"
            )

        if not recommendations:
            recommendations.append("Single camera lookup performance is optimal")

        return recommendations

    def _analyze_pagination_performance(
        self, metrics: Dict[str, Any], page_size: int
    ) -> List[str]:
        """Analyze pagination query performance."""
        recommendations = []

        execution_time = metrics.get("execution_time_ms", 0)

        if execution_time > 200:
            recommendations.append(
                f"Pagination query is slow ({execution_time:.2f}ms) for page_size {page_size}"
            )

        if execution_time > 100 and page_size <= 50:
            recommendations.append(
                "Consider using LIMIT/OFFSET optimization or cursor-based pagination"
            )

        if not recommendations:
            recommendations.append("Pagination performance is acceptable")

        return recommendations

    def _analyze_settings_performance(
        self, metrics: Dict[str, Any], settings_count: int
    ) -> List[str]:
        """Analyze settings operations performance."""
        recommendations = []

        execution_time = metrics.get("execution_time_ms", 0)

        if execution_time > 100:
            recommendations.append(
                f"Settings query is slow ({execution_time:.2f}ms) - consider caching"
            )

        if settings_count > 1000:
            recommendations.append(
                "Large number of settings - consider cleanup or archival"
            )

        if not recommendations:
            recommendations.append("Settings performance is good")

        return recommendations

    def _analyze_connection_pool_performance(
        self, pool_stats: Dict[str, Any], avg_time: float, max_time: float
    ) -> List[str]:
        """Analyze connection pool performance."""
        recommendations = []

        if avg_time > 50:  # 50ms average threshold
            recommendations.append(
                f"High average connection time ({avg_time:.2f}ms) - consider pool tuning"
            )

        if max_time > 200:  # 200ms max threshold
            recommendations.append(
                f"Connection spikes detected ({max_time:.2f}ms) - investigate pool contention"
            )

        success_rate = pool_stats.get("success_rate", 100)
        if success_rate < 95:
            recommendations.append(
                f"Low connection success rate ({success_rate:.1f}%) - check pool configuration"
            )

        if pool_stats.get("status") != "healthy":
            recommendations.append(
                "Pool health issues detected - immediate attention required"
            )

        if not recommendations:
            recommendations.append("Connection pool performance is optimal")

        return recommendations

    def _generate_overall_recommendations(
        self,
        camera_profile: Dict[str, Any],
        image_profile: Dict[str, Any],
        settings_profile: Dict[str, Any],
        pool_profile: Dict[str, Any],
    ) -> List[str]:
        """Generate overall optimization recommendations."""
        recommendations = []

        # Analyze overall trends
        all_times = []

        # Collect execution times
        for profile in [camera_profile, image_profile, settings_profile]:
            for operation, data in profile.items():
                if "metrics" in data and "execution_time_ms" in data["metrics"]:
                    all_times.append(data["metrics"]["execution_time_ms"])

        if all_times:
            avg_time = sum(all_times) / len(all_times)
            max_time = max(all_times)

            if avg_time > 100:
                recommendations.append(
                    f"Overall database performance needs attention (avg: {avg_time:.2f}ms)"
                )

            if max_time > 1000:
                recommendations.append(
                    f"Critical performance issues detected (max: {max_time:.2f}ms)"
                )

        # Connection pool recommendations
        pool_avg = pool_profile.get("connection_performance", {}).get(
            "average_time_ms", 0
        )
        if pool_avg > 50:
            recommendations.append("Consider connection pool optimization")

        if not recommendations:
            recommendations.append("Overall database performance is good")

        return recommendations


# Global instance for use across the application
performance_profiler: Optional[DatabasePerformanceProfiler] = None


def initialize_performance_profiler(db: AsyncDatabase) -> None:
    """Initialize the global performance profiler instance."""
    global performance_profiler
    performance_profiler = DatabasePerformanceProfiler(db)


def get_performance_profiler() -> Optional[DatabasePerformanceProfiler]:
    """Get the global performance profiler instance."""
    return performance_profiler
