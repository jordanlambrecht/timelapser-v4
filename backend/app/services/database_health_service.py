# backend/app/services/database_health_service.py
"""
Database Health Service - Monitors and maintains database connection health.

Provides health monitoring and automatic recovery capabilities for long-running
workers that need reliable database connectivity.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any, Optional

from ..database.core import AsyncDatabase, SyncDatabase
from ..utils.time_utils import utc_now


class DatabaseHealthMonitor:
    """
    Database health monitoring and recovery service for long-running workers.

    This service provides:
    - Periodic health checks for database connections
    - Automatic recovery when connections fail
    - Health statistics and monitoring
    - Configurable check intervals and retry policies
    """

    def __init__(
        self,
        database: SyncDatabase,
        check_interval_seconds: int = 300,  # 5 minutes
        max_consecutive_failures: int = 3,
        auto_recovery_enabled: bool = True,
        worker_name: str = "Unknown"
    ):
        """
        Initialize database health monitor.

        Args:
            database: Database instance to monitor
            check_interval_seconds: Seconds between health checks
            max_consecutive_failures: Max failures before marking unhealthy
            auto_recovery_enabled: Whether to attempt automatic recovery
            worker_name: Name of the worker for logging
        """
        self.database = database
        self.check_interval = check_interval_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self.auto_recovery_enabled = auto_recovery_enabled
        self.worker_name = worker_name

        # Health tracking
        self.consecutive_failures = 0
        self.total_health_checks = 0
        self.successful_checks = 0
        self.last_health_check = None
        self.last_successful_check = None
        self.last_recovery_attempt = None
        self.recovery_attempts = 0
        self.is_healthy = True

        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._should_stop = False

        self.logger = logging.getLogger(f"{__name__}.{worker_name}")

    def start_monitoring(self) -> None:
        """Start the background health monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self.logger.warning("Health monitoring already running")
            return

        self._should_stop = False
        # Note: This creates a task but doesn't await it - it runs in background
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info(
            f"Started database health monitoring (interval: {self.check_interval}s)"
        )

    async def stop_monitoring(self) -> None:
        """Stop the background health monitoring task."""
        self._should_stop = True
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Stopped database health monitoring")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs health checks periodically."""
        while not self._should_stop:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(
                    min(60, self.check_interval)
                )  # Short delay on error

    async def perform_health_check(self) -> bool:
        """
        Perform a health check on the database connection.

        Returns:
            True if healthy, False otherwise
        """
        self.total_health_checks += 1
        self.last_health_check = utc_now()

        try:
            # Use the database's built-in health check
            is_healthy = self.database.check_pool_health()

            if is_healthy:
                self.consecutive_failures = 0
                self.successful_checks += 1
                self.last_successful_check = self.last_health_check
                self.is_healthy = True

                # Log success occasionally to confirm monitoring is working
                if self.total_health_checks % 10 == 0:  # Every 10th check
                    self.logger.debug(
                        f"Database health check #{self.total_health_checks} passed"
                    )

            else:
                self.consecutive_failures += 1
                self.logger.warning(
                    f"Database health check failed (consecutive failures: "
                    f"{self.consecutive_failures})"
                )

                # Check if we should mark as unhealthy and attempt recovery
                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.is_healthy = False

                    if self.auto_recovery_enabled:
                        recovery_success = await self._attempt_recovery()
                        if recovery_success:
                            self.is_healthy = True
                            self.consecutive_failures = 0

            return self.is_healthy

        except Exception as e:
            self.consecutive_failures += 1
            self.logger.error(f"Health check error: {e}")
            self.is_healthy = False
            return False

    async def _attempt_recovery(self) -> bool:
        """
        Attempt to recover the database connection.

        Returns:
            True if recovery successful, False otherwise
        """
        self.recovery_attempts += 1
        self.last_recovery_attempt = utc_now()

        self.logger.info(
            f"Attempting database recovery (attempt #{self.recovery_attempts})"
        )

        try:
            # Use the database's built-in recovery
            recovery_success = self.database.recover_connection_pool()

            if recovery_success:
                self.logger.info("Database recovery successful")
                return True
            else:
                self.logger.error("Database recovery failed")
                return False

        except Exception as e:
            self.logger.error(f"Database recovery error: {e}")
            return False

    def get_health_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive health statistics.

        Returns:
            Dictionary with health monitoring statistics
        """
        success_rate = (self.successful_checks / max(self.total_health_checks, 1)) * 100

        stats = {
            "worker_name": self.worker_name,
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_health_checks": self.total_health_checks,
            "successful_checks": self.successful_checks,
            "success_rate_percent": round(success_rate, 2),
            "check_interval_seconds": self.check_interval,
            "max_consecutive_failures": self.max_consecutive_failures,
            "auto_recovery_enabled": self.auto_recovery_enabled,
            "recovery_attempts": self.recovery_attempts,
            "last_health_check": self.last_health_check,
            "last_successful_check": self.last_successful_check,
            "last_recovery_attempt": self.last_recovery_attempt,
            "monitoring_active": (
                self._monitoring_task is not None
                and not self._monitoring_task.done()
            ),
        }

        # Add database pool statistics if available
        try:
            pool_stats = self.database.get_pool_stats()
            stats["database_pool"] = pool_stats
        except Exception as e:
            stats["database_pool_error"] = str(e)

        return stats

    def force_health_check(self) -> bool:
        """
        Force an immediate health check (synchronous version).

        Returns:
            True if healthy, False otherwise
        """
        return asyncio.run(self.perform_health_check())

    def is_connection_stale(self, max_age_minutes: int = 60) -> bool:
        """
        Check if the connection might be stale based on last successful check.

        Args:
            max_age_minutes: Maximum minutes since last successful check

        Returns:
            True if connection might be stale
        """
        if not self.last_successful_check:
            return True

        age = utc_now() - self.last_successful_check
        return age > timedelta(minutes=max_age_minutes)


class AsyncDatabaseHealthMonitor:
    """Async version of DatabaseHealthMonitor for async database operations."""

    def __init__(
        self,
        database: AsyncDatabase,
        check_interval_seconds: int = 300,
        max_consecutive_failures: int = 3,
        auto_recovery_enabled: bool = True,
        worker_name: str = "Unknown"
    ):
        self.database = database
        self.check_interval = check_interval_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self.auto_recovery_enabled = auto_recovery_enabled
        self.worker_name = worker_name

        # Health tracking (same as sync version)
        self.consecutive_failures = 0
        self.total_health_checks = 0
        self.successful_checks = 0
        self.last_health_check = None
        self.last_successful_check = None
        self.last_recovery_attempt = None
        self.recovery_attempts = 0
        self.is_healthy = True

        self._monitoring_task: Optional[asyncio.Task] = None
        self._should_stop = False

        self.logger = logging.getLogger(f"{__name__}.{worker_name}")

    async def start_monitoring(self) -> None:
        """Start the background health monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self.logger.warning("Async health monitoring already running")
            return

        self._should_stop = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info(
            f"Started async database health monitoring (interval: "
            f"{self.check_interval}s)"
        )

    async def stop_monitoring(self) -> None:
        """Stop the background health monitoring task."""
        self._should_stop = True
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Stopped async database health monitoring")

    async def _monitoring_loop(self) -> None:
        """Main async monitoring loop."""
        while not self._should_stop:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in async health monitoring loop: {e}")
                await asyncio.sleep(min(60, self.check_interval))

    async def perform_health_check(self) -> bool:
        """Perform an async health check."""
        self.total_health_checks += 1
        self.last_health_check = utc_now()

        try:
            is_healthy = await self.database.check_pool_health()

            if is_healthy:
                self.consecutive_failures = 0
                self.successful_checks += 1
                self.last_successful_check = self.last_health_check
                self.is_healthy = True

                if self.total_health_checks % 10 == 0:
                    self.logger.debug(
                        f"Async database health check #{self.total_health_checks} "
                        f"passed"
                    )

            else:
                self.consecutive_failures += 1
                self.logger.warning(
                    f"Async database health check failed (consecutive failures: "
                    f"{self.consecutive_failures})"
                )

                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.is_healthy = False

                    if self.auto_recovery_enabled:
                        recovery_success = await self._attempt_recovery()
                        if recovery_success:
                            self.is_healthy = True
                            self.consecutive_failures = 0

            return self.is_healthy

        except Exception as e:
            self.consecutive_failures += 1
            self.logger.error(f"Async health check error: {e}")
            self.is_healthy = False
            return False

    async def _attempt_recovery(self) -> bool:
        """Attempt async database recovery."""
        self.recovery_attempts += 1
        self.last_recovery_attempt = utc_now()

        self.logger.info(
            f"Attempting async database recovery (attempt "
            f"#{self.recovery_attempts})"
        )

        try:
            recovery_success = await self.database.recover_connection_pool()

            if recovery_success:
                self.logger.info("Async database recovery successful")
                return True
            else:
                self.logger.error("Async database recovery failed")
                return False

        except Exception as e:
            self.logger.error(f"Async database recovery error: {e}")
            return False

    def get_health_stats(self) -> Dict[str, Any]:
        """Get async health statistics (same structure as sync version)."""
        success_rate = (self.successful_checks / max(self.total_health_checks, 1)) * 100

        stats = {
            "worker_name": self.worker_name,
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_health_checks": self.total_health_checks,
            "successful_checks": self.successful_checks,
            "success_rate_percent": round(success_rate, 2),
            "check_interval_seconds": self.check_interval,
            "max_consecutive_failures": self.max_consecutive_failures,
            "auto_recovery_enabled": self.auto_recovery_enabled,
            "recovery_attempts": self.recovery_attempts,
            "last_health_check": self.last_health_check,
            "last_successful_check": self.last_successful_check,
            "last_recovery_attempt": self.last_recovery_attempt,
            "monitoring_active": (
                self._monitoring_task is not None
                and not self._monitoring_task.done()
            ),
        }

        # Add database pool statistics if available
        try:
            pool_stats = self.database.get_pool_stats()
            stats["database_pool"] = pool_stats
        except Exception as e:
            stats["database_pool_error"] = str(e)

        return stats
