# backend/app/services/health_service.py
"""
Health monitoring service for comprehensive system health checks.

Provides detailed health monitoring for all system components including
database connections, file system, external dependencies, and performance metrics.

Design Decision: This service intentionally does NOT integrate with SSE (Server-Sent Events).
Health monitoring is better served by HTTP caching + periodic polling rather than real-time
streaming. Health status typically changes slowly and is checked every few minutes, making
SSE overhead unnecessary. The current HTTP approach with ETag caching provides optimal
balance between freshness and performance.

Follows architectural patterns:
- Composition pattern with database operations
- Timezone-aware using settings cache
- Proper Pydantic models
- Standardized error handling
"""

import asyncio
import psutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.database.core import AsyncDatabase
from app.database.health_operations import HealthOperations
from app.database.statistics_operations import StatisticsOperations
from app.services.logger import Log
from app.enums import LogLevel, LogSource, LoggerName
from app.models.health_model import (
    HealthStatus,
    BasicHealthCheck,
    DetailedHealthCheck,
    ComponentHealth,
    DatabaseHealth,
    FilesystemHealth,
    SystemMetrics,
    ApplicationMetrics,
)
from app.utils.time_utils import get_timezone_aware_timestamp_async
from .logger import get_service_logger
from .video_pipeline import ffmpeg_utils
from app.config import settings
from app.constants import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    HEALTH_DB_LATENCY_WARNING,
    HEALTH_DB_LATENCY_ERROR,
    HEALTH_CPU_WARNING,
    HEALTH_CPU_ERROR,
    HEALTH_MEMORY_WARNING,
    HEALTH_MEMORY_ERROR,
    HEALTH_DISK_WARNING,
    HEALTH_DISK_ERROR,
    HEALTH_VIDEO_QUEUE_WARNING,
    HEALTH_VIDEO_QUEUE_ERROR,
)

logger = get_service_logger(LoggerName.HEALTH_WORKER, LogSource.HEALTH)


class HealthService:
    """
    Comprehensive health monitoring service using composition pattern.

    Monitors database connections, file system health, system resources,
    external dependencies, and provides detailed diagnostic information.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with database instance using composition pattern."""
        self.db = db
        self.health_ops = HealthOperations(db)
        self.stats_ops = StatisticsOperations(db)
        self.start_time: Optional[datetime] = None

    async def get_basic_health(self) -> BasicHealthCheck:
        """
        Get basic health check response.

        Returns:
            BasicHealthCheck model with essential health information
        """
        try:
            # Get timezone-aware timestamp
            current_time = await get_timezone_aware_timestamp_async(self.db)

            # Initialize start time if not set
            if self.start_time is None:
                self.start_time = current_time

            # Quick database connectivity test
            db_healthy, _, _ = await self.health_ops.test_database_connectivity()
            overall_status = (
                HealthStatus.HEALTHY if db_healthy else HealthStatus.UNHEALTHY
            )

            return BasicHealthCheck(
                status=overall_status,
                timestamp=current_time,
                service=APPLICATION_NAME,
                version=APPLICATION_VERSION,
            )

        except Exception as e:
            logger.error(
                f"Basic health check failed",
                extra_context={"operation": "basic_health_check"},
                exception=e,
            )
            return BasicHealthCheck(
                status=HealthStatus.UNKNOWN,
                timestamp=await get_timezone_aware_timestamp_async(self.db),
                service=APPLICATION_NAME,
                version=APPLICATION_VERSION,
            )

    async def get_detailed_health(self) -> DetailedHealthCheck:
        """
        Get comprehensive system health status.

        Returns:
            DetailedHealthCheck model with complete health information
        """
        try:
            # Get timezone-aware timestamp
            current_time = await get_timezone_aware_timestamp_async(self.db)

            # Initialize start time if not set
            if self.start_time is None:
                self.start_time = current_time

            # Run all health checks concurrently
            health_results = await asyncio.gather(
                self._check_database_health(),
                self._check_filesystem_health(),
                self._check_system_resources(),
                self._check_external_dependencies(),
                self._check_application_health(),
                return_exceptions=True,
            )

            # Process results
            components = {}
            warnings = []
            overall_healthy = True

            component_names = [
                "database",
                "filesystem",
                "system",
                "dependencies",
                "application",
            ]

            for i, result in enumerate(health_results):
                name = component_names[i]

                if isinstance(result, Exception):
                    components[name] = ComponentHealth(
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check failed: {str(result)}",
                        response_time_seconds=None,
                        error=str(result),
                        details=None,
                    )
                    overall_healthy = False
                    warnings.append(f"{name.title()} health check failed")
                elif isinstance(result, ComponentHealth):
                    components[name] = result
                    if result.status != HealthStatus.HEALTHY:
                        overall_healthy = False
                        if result.status == HealthStatus.UNHEALTHY:
                            warnings.append(f"{name.title()} is unhealthy")
                        elif result.status == HealthStatus.DEGRADED:
                            warnings.append(f"{name.title()} is degraded")
                else:
                    # Unexpected result type - treat as error
                    components[name] = ComponentHealth(
                        status=HealthStatus.UNHEALTHY,
                        message=f"Unexpected result type for {name} health check",
                        response_time_seconds=None,
                        error=f"Got {type(result)} instead of ComponentHealth",
                        details=None,
                    )
                    overall_healthy = False
                    warnings.append(
                        f"{name.title()} health check returned unexpected result"
                    )

            # Determine overall status
            if overall_healthy:
                overall_status = HealthStatus.HEALTHY
            elif any(
                comp.status == HealthStatus.UNHEALTHY for comp in components.values()
            ):
                overall_status = HealthStatus.UNHEALTHY
            else:
                overall_status = HealthStatus.DEGRADED

            uptime_seconds = (current_time - self.start_time).total_seconds()

            return DetailedHealthCheck(
                status=overall_status,
                timestamp=current_time,
                service=APPLICATION_NAME,
                version=APPLICATION_VERSION,
                uptime_seconds=uptime_seconds,
                components=components,
                warnings=warnings if warnings else None,
            )

        except Exception as e:
            logger.error(
                f"Detailed health check failed",
                extra_context={"operation": "detailed_health_check"},
                exception=e,
            )
            return DetailedHealthCheck(
                status=HealthStatus.UNKNOWN,
                timestamp=await get_timezone_aware_timestamp_async(self.db),
                service=APPLICATION_NAME,
                version=APPLICATION_VERSION,
                uptime_seconds=0,
                components={},
                warnings=[f"Health check system error: {str(e)}"],
            )

    async def _check_database_health(self) -> ComponentHealth:
        """Check database connection health and performance."""
        try:
            # Test connectivity and measure latency
            success, latency_ms, error = (
                await self.health_ops.test_database_connectivity()
            )

            if not success:
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message="Database connection failed",
                    response_time_seconds=None,
                    error=error or "Unknown database error",
                    details=None,
                )

            # Get pool statistics
            pool_stats = await self.health_ops.get_connection_pool_stats()

            # Determine status based on latency (with None check)
            if latency_ms is not None:
                if latency_ms > HEALTH_DB_LATENCY_ERROR:
                    status = HealthStatus.UNHEALTHY
                    message = f"Critical database latency: {latency_ms:.2f}ms"
                elif latency_ms > HEALTH_DB_LATENCY_WARNING:
                    status = HealthStatus.DEGRADED
                    message = f"High database latency: {latency_ms:.2f}ms"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Database healthy (latency: {latency_ms:.2f}ms)"

                response_time = latency_ms / 1000
            else:
                status = HealthStatus.UNKNOWN
                message = "Database latency measurement failed"
                response_time = None

            return ComponentHealth(
                status=status,
                message=message,
                response_time_seconds=response_time,
                error=None,
                details={
                    "latency_ms": (
                        round(latency_ms, 2) if latency_ms is not None else None
                    ),
                    "pool_status": pool_stats,
                },
            )

        except Exception as e:
            logger.error(
                "Database health check failed",
                extra_context={"operation": "database_health_check"},
                exception=e,
            )
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="Database health check failed",
                response_time_seconds=None,
                error=str(e),
                details=None,
            )

    async def _check_filesystem_health(self) -> ComponentHealth:
        """Check file system health and storage capacity."""
        try:
            data_directory = Path(settings.data_directory)
            details = {}
            warnings = []

            # Check directory existence and permissions
            if not data_directory.exists():
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Data directory does not exist: {data_directory}",
                    response_time_seconds=None,
                    error="Data directory missing",
                    details=None,
                )

            if not data_directory.is_dir():
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Data directory is not a directory: {data_directory}",
                    response_time_seconds=None,
                    error="Data directory invalid",
                    details=None,
                )

            # Test write permissions
            test_file = data_directory / ".health_check_test"
            try:
                test_file.write_text("health_check")
                test_file.unlink()
                details["write_permissions"] = True
            except Exception as e:
                details["write_permissions"] = False
                warnings.append(f"Write permission test failed: {str(e)}")

            # Check disk usage
            disk_usage = psutil.disk_usage(str(data_directory))
            free_percent = (disk_usage.free / disk_usage.total) * 100
            used_percent = 100 - free_percent

            details.update(
                {
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                    "free_gb": round(disk_usage.free / (1024**3), 2),
                    "used_gb": round(disk_usage.used / (1024**3), 2),
                    "free_percent": round(free_percent, 2),
                    "used_percent": round(used_percent, 2),
                }
            )

            # Determine status based on disk usage
            if used_percent > HEALTH_DISK_ERROR:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {used_percent:.1f}% used"
            elif used_percent > HEALTH_DISK_WARNING:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {used_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Filesystem healthy ({free_percent:.1f}% free)"

            # Check write permissions impact on status
            if not details["write_permissions"] and status == HealthStatus.HEALTHY:
                status = HealthStatus.DEGRADED
                message += " (write permissions issue)"

            return ComponentHealth(
                status=status,
                message=message,
                response_time_seconds=None,
                error=None,
                details=details,
            )

        except Exception as e:
            logger.error(
                "Filesystem health check failed",
                extra_context={"operation": "filesystem_health_check"},
                exception=e,
            )
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="Filesystem health check failed",
                response_time_seconds=None,
                error=str(e),
                details=None,
            )

    async def _check_system_resources(self) -> ComponentHealth:
        """Check system resource utilization."""
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Get memory usage
            memory = psutil.virtual_memory()

            # Get load average (Unix-like systems)
            load_avg = None
            try:
                load_avg_tuple = psutil.getloadavg()
                load_avg = {
                    "1min": load_avg_tuple[0],
                    "5min": load_avg_tuple[1],
                    "15min": load_avg_tuple[2],
                }
            except AttributeError:
                # Windows doesn't have load average
                pass

            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "load_average": load_avg,
            }

            # Determine status based on resource usage
            warnings = []
            status = HealthStatus.HEALTHY

            if cpu_percent > HEALTH_CPU_ERROR:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Critical CPU usage: {cpu_percent}%")
            elif cpu_percent > HEALTH_CPU_WARNING:
                status = HealthStatus.DEGRADED
                warnings.append(f"High CPU usage: {cpu_percent}%")

            if memory.percent > HEALTH_MEMORY_ERROR:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Critical memory usage: {memory.percent}%")
            elif memory.percent > HEALTH_MEMORY_WARNING:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                warnings.append(f"High memory usage: {memory.percent}%")

            message = "System resources healthy"
            if warnings:
                message = "; ".join(warnings)

            return ComponentHealth(
                status=status,
                message=message,
                response_time_seconds=None,
                error=None,
                details=details,
            )

        except Exception as e:
            logger.error(
                "System resources check failed",
                extra_context={"operation": "system_resources_check"},
                exception=e,
            )
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="System resources check failed",
                response_time_seconds=None,
                error=str(e),
                details=None,
            )

    async def _check_external_dependencies(self) -> ComponentHealth:
        """Check external dependencies like FFmpeg."""
        try:
            dependencies = {}
            warnings = []
            status = HealthStatus.HEALTHY

            # Check FFmpeg availability
            ffmpeg_available, ffmpeg_version = ffmpeg_utils.test_ffmpeg_available()
            dependencies["ffmpeg"] = {
                "available": ffmpeg_available,
                "version": ffmpeg_version if ffmpeg_available else None,
                "status": "healthy" if ffmpeg_available else "unhealthy",
            }

            if not ffmpeg_available:
                status = HealthStatus.DEGRADED
                warnings.append("FFmpeg not available - video generation disabled")

            message = "External dependencies healthy"
            if warnings:
                message = "; ".join(warnings)

            return ComponentHealth(
                status=status,
                message=message,
                response_time_seconds=None,
                error=None,
                details={"dependencies": dependencies},
            )

        except Exception as e:
            logger.error(
                "External dependencies check failed",
                extra_context={"operation": "external_dependencies_check"},
                exception=e,
            )
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="External dependencies check failed",
                response_time_seconds=None,
                error=str(e),
                details=None,
            )

    async def _check_application_health(self) -> ComponentHealth:
        """Check application-specific health metrics."""
        try:
            # Get application metrics using database operations
            app_metrics = await self.health_ops.get_application_metrics()

            warnings = []
            status = HealthStatus.HEALTHY

            # Check for potential issues
            if app_metrics.active_cameras == 0 and app_metrics.total_cameras > 0:
                status = HealthStatus.DEGRADED
                warnings.append("No active cameras")

            if app_metrics.pending_video_jobs > HEALTH_VIDEO_QUEUE_ERROR:
                status = HealthStatus.UNHEALTHY
                warnings.append(
                    f"Critical video queue backlog: {app_metrics.pending_video_jobs} pending jobs"
                )
            elif app_metrics.pending_video_jobs > HEALTH_VIDEO_QUEUE_WARNING:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                warnings.append(
                    f"High video queue backlog: {app_metrics.pending_video_jobs} pending jobs"
                )

            message = "Application healthy"
            if warnings:
                message = "; ".join(warnings)

            # Convert Pydantic model to dict for details
            details = app_metrics.model_dump()

            return ComponentHealth(
                status=status,
                message=message,
                response_time_seconds=None,
                error=None,
                details={"metrics": details},
            )

        except Exception as e:
            logger.error(
                "Application health check failed",
                extra_context={"operation": "application_health_check"},
                exception=e,
            )
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="Application health check failed",
                response_time_seconds=None,
                error=str(e),
                details=None,
            )

    async def get_database_health(self) -> DatabaseHealth:
        """Get detailed database health information."""
        try:
            # Test async connectivity
            success, latency_ms, error = (
                await self.health_ops.test_database_connectivity()
            )

            if not success:
                return DatabaseHealth(
                    status=HealthStatus.UNHEALTHY,
                    async_latency_ms=None,
                    sync_latency_ms=None,
                    pool_status=None,
                    error=error or "Database connection failed",
                )

            # Get pool stats
            pool_stats = await self.health_ops.get_connection_pool_stats()

            # Determine status (with None check)
            if latency_ms is not None:
                if latency_ms > HEALTH_DB_LATENCY_ERROR:
                    status = HealthStatus.UNHEALTHY
                elif latency_ms > HEALTH_DB_LATENCY_WARNING:
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.UNKNOWN

            return DatabaseHealth(
                status=status,
                async_latency_ms=(
                    round(latency_ms, 2) if latency_ms is not None else None
                ),
                sync_latency_ms=None,  # Would need sync database test
                pool_status=pool_stats,
                error=None,
            )

        except Exception as e:
            logger.error(
                "Database health check failed",
                extra_context={"operation": "database_health_detailed"},
                exception=e,
            )
            return DatabaseHealth(
                status=HealthStatus.UNHEALTHY,
                async_latency_ms=None,
                sync_latency_ms=None,
                pool_status=None,
                error=str(e),
            )

    async def get_filesystem_health(self) -> FilesystemHealth:
        """Get detailed filesystem health information."""
        try:
            data_directory = Path(settings.data_directory)

            # Basic checks
            if not data_directory.exists() or not data_directory.is_dir():
                return FilesystemHealth(
                    status=HealthStatus.UNHEALTHY,
                    data_directory_accessible=False,
                    write_permissions=False,
                    disk_usage_percent=None,
                    free_space_gb=None,
                    error="Data directory not accessible",
                )

            # Test write permissions
            write_permissions = True
            try:
                test_file = data_directory / ".health_check_test"
                test_file.write_text("health_check")
                test_file.unlink()
            except Exception:
                write_permissions = False

            # Get disk usage
            disk_usage = psutil.disk_usage(str(data_directory))
            used_percent = (disk_usage.used / disk_usage.total) * 100
            free_gb = disk_usage.free / (1024**3)

            # Determine status
            if used_percent > HEALTH_DISK_ERROR:
                status = HealthStatus.UNHEALTHY
            elif used_percent > HEALTH_DISK_WARNING or not write_permissions:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return FilesystemHealth(
                status=status,
                data_directory_accessible=True,
                write_permissions=write_permissions,
                disk_usage_percent=round(used_percent, 2),
                free_space_gb=round(free_gb, 2),
                error=None,
            )

        except Exception as e:
            logger.error(
                "Filesystem health check failed",
                extra_context={"operation": "filesystem_health_detailed"},
                exception=e,
            )
            return FilesystemHealth(
                status=HealthStatus.UNHEALTHY,
                data_directory_accessible=False,
                write_permissions=False,
                disk_usage_percent=None,
                free_space_gb=None,
                error=str(e),
            )

    async def get_system_metrics(self) -> SystemMetrics:
        """Get detailed system performance metrics."""
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Get memory usage
            memory = psutil.virtual_memory()

            # Get disk usage for data directory
            data_directory = Path(settings.data_directory)
            disk_usage_percent = None
            if data_directory.exists():
                disk_usage = psutil.disk_usage(str(data_directory))
                disk_usage_percent = (disk_usage.used / disk_usage.total) * 100

            # Get load average (Unix-like systems)
            load_avg = None
            try:
                load_avg_tuple = psutil.getloadavg()
                load_avg = {
                    "1min": load_avg_tuple[0],
                    "5min": load_avg_tuple[1],
                    "15min": load_avg_tuple[2],
                }
            except AttributeError:
                # Windows doesn't have load average
                pass

            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_total_gb=round(memory.total / (1024**3), 2),
                memory_available_gb=round(memory.available / (1024**3), 2),
                disk_usage_percent=(
                    round(disk_usage_percent, 2) if disk_usage_percent else None
                ),
                load_average=load_avg,
            )

        except Exception as e:
            logger.error(
                "System metrics check failed",
                extra_context={"operation": "system_metrics_check"},
                exception=e,
            )
            # Return safe defaults
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_total_gb=0.0,
                memory_available_gb=0.0,
                disk_usage_percent=None,
                load_average=None,
            )

    async def get_application_metrics(self) -> ApplicationMetrics:
        """Get application-specific metrics."""
        return await self.health_ops.get_application_metrics()
