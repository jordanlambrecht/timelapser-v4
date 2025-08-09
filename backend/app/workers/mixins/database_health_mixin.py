# backend/app/workers/mixins/database_health_mixin.py
"""
Database Health Mixin for Workers.

Provides database connection health monitoring and recovery capabilities
for long-running worker processes.
"""

from typing import Dict, Any, Optional

from ...database.core import SyncDatabase
from ...services.database_health_service import DatabaseHealthMonitor


class DatabaseHealthMixin:
    """
    Mixin to add database health monitoring and recovery to worker classes.

    This mixin provides:
    - Automatic database health monitoring
    - Connection recovery on failures
    - Health statistics and reporting
    - Integration with worker lifecycle

    Usage:
        class MyWorker(BaseWorker, DatabaseHealthMixin):
            def __init__(self):
                super().__init__()
                self.setup_database_health_monitoring()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.health_monitor: Optional[DatabaseHealthMonitor] = None

    def setup_database_health_monitoring(
        self,
        database: Optional[SyncDatabase] = None,
        check_interval_seconds: int = 300,  # 5 minutes
        max_consecutive_failures: int = 3,
        auto_recovery_enabled: bool = True
    ) -> None:
        """
        Set up database health monitoring for this worker.

        Args:
            database: Database instance to monitor (uses self.database if None)
            check_interval_seconds: Seconds between health checks
            max_consecutive_failures: Max failures before attempting recovery
            auto_recovery_enabled: Whether to attempt automatic recovery
        """
        # Use provided database or try to find one on the worker instance
        if database is None:
            if hasattr(self, 'database') and self.database is not None:
                database = self.database
            else:
                raise ValueError(
                    "No database provided and worker has no database attribute"
                )

        # Get worker name for logging
        worker_name = getattr(self, 'worker_name', self.__class__.__name__)

        self.health_monitor = DatabaseHealthMonitor(
            database=database,
            check_interval_seconds=check_interval_seconds,
            max_consecutive_failures=max_consecutive_failures,
            auto_recovery_enabled=auto_recovery_enabled,
            worker_name=worker_name
        )

        # Log setup
        if hasattr(self, 'logger'):
            self.logger.info(
                f"Database health monitoring configured for {worker_name}"
            )

    def start_database_monitoring(self) -> bool:
        """
        Start database health monitoring.

        Returns:
            True if monitoring started successfully, False otherwise
        """
        if not self.health_monitor:
            if hasattr(self, 'logger'):
                self.logger.error("Database health monitoring not configured")
            return False

        try:
            self.health_monitor.start_monitoring()
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to start database monitoring: {e}")
            return False

    async def stop_database_monitoring(self) -> None:
        """Stop database health monitoring."""
        if self.health_monitor:
            await self.health_monitor.stop_monitoring()

    def check_database_health(self) -> bool:
        """
        Perform an immediate database health check.

        Returns:
            True if database is healthy, False otherwise
        """
        if not self.health_monitor:
            return False

        return self.health_monitor.force_health_check()

    def get_database_health_stats(self) -> Dict[str, Any]:
        """
        Get database health statistics.

        Returns:
            Dictionary with health monitoring statistics
        """
        if not self.health_monitor:
            return {"monitoring_enabled": False}

        stats = self.health_monitor.get_health_stats()
        stats["monitoring_enabled"] = True
        return stats

    def is_database_connection_stale(self, max_age_minutes: int = 60) -> bool:
        """
        Check if database connection might be stale.

        Args:
            max_age_minutes: Maximum minutes since last successful check

        Returns:
            True if connection might be stale
        """
        if not self.health_monitor:
            return True

        return self.health_monitor.is_connection_stale(max_age_minutes)

    def force_database_recovery(self) -> bool:
        """
        Force a database connection recovery attempt.

        Returns:
            True if recovery successful, False otherwise
        """
        if not self.health_monitor:
            return False

        # Use the database's recovery method directly
        if hasattr(self.health_monitor.database, 'recover_connection_pool'):
            try:
                result = self.health_monitor.database.recover_connection_pool()
                if hasattr(self, 'logger'):
                    if result:
                        self.logger.info("Manual database recovery successful")
                    else:
                        self.logger.warning("Manual database recovery failed")
                return result
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(f"Manual database recovery error: {e}")
                return False

        return False

    def get_enhanced_database_connection(
        self, auto_recover: bool = True, max_retries: int = 2
    ):
        """
        Get a database connection with enhanced recovery capabilities.

        Args:
            auto_recover: Whether to attempt automatic recovery on failures
            max_retries: Maximum number of recovery attempts

        Returns:
            Database connection context manager
        """
        database = None
        if self.health_monitor:
            database = self.health_monitor.database
        elif hasattr(self, 'database'):
            database = self.database
        else:
            raise ValueError("No database available for connection")

        return database.get_connection(
            auto_recover=auto_recover, max_retries=max_retries
        )

    def _integrate_health_stats_with_worker_stats(
        self, worker_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Helper method to integrate database health stats with worker statistics.

        Args:
            worker_stats: Existing worker statistics

        Returns:
            Enhanced statistics including database health information
        """
        health_stats = self.get_database_health_stats()

        # Add database health section to worker stats
        worker_stats["database_health"] = health_stats

        # Add key health indicators to top level for easy monitoring
        worker_stats["database_healthy"] = health_stats.get("is_healthy", False)
        worker_stats["database_connection_failures"] = health_stats.get(
            "consecutive_failures", 0
        )
        worker_stats["database_success_rate"] = health_stats.get(
            "success_rate_percent", 0
        )

        return worker_stats


class AsyncDatabaseHealthMixin:
    """
    Async version of DatabaseHealthMixin for async workers.

    Provides the same functionality as DatabaseHealthMixin but uses
    AsyncDatabaseHealthMonitor for async database operations.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.health_monitor = None

    async def setup_database_health_monitoring(
        self,
        database=None,
        check_interval_seconds: int = 300,
        max_consecutive_failures: int = 3,
        auto_recovery_enabled: bool = True
    ) -> None:
        """Set up async database health monitoring."""
        from ...services.database_health_service import (
            AsyncDatabaseHealthMonitor
        )

        # Use provided database or try to find one on the worker instance
        if database is None:
            if hasattr(self, 'database') and self.database is not None:
                database = self.database
            else:
                raise ValueError(
                    "No database provided and worker has no database attribute"
                )

        worker_name = getattr(self, 'worker_name', self.__class__.__name__)

        self.health_monitor = AsyncDatabaseHealthMonitor(
            database=database,
            check_interval_seconds=check_interval_seconds,
            max_consecutive_failures=max_consecutive_failures,
            auto_recovery_enabled=auto_recovery_enabled,
            worker_name=worker_name
        )

        if hasattr(self, 'logger'):
            self.logger.info(
                f"Async database health monitoring configured for "
                f"{worker_name}"
            )

    async def start_database_monitoring(self) -> bool:
        """Start async database health monitoring."""
        if not self.health_monitor:
            if hasattr(self, 'logger'):
                self.logger.error(
                    "Async database health monitoring not configured"
                )
            return False

        try:
            await self.health_monitor.start_monitoring()
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(
                    f"Failed to start async database monitoring: {e}"
                )
            return False

    async def stop_database_monitoring(self) -> None:
        """Stop async database health monitoring."""
        if self.health_monitor:
            await self.health_monitor.stop_monitoring()

    async def check_database_health(self) -> bool:
        """Perform an immediate async database health check."""
        if not self.health_monitor:
            return False

        return await self.health_monitor.perform_health_check()

    def get_database_health_stats(self) -> Dict[str, Any]:
        """Get async database health statistics."""
        if not self.health_monitor:
            return {"monitoring_enabled": False}

        stats = self.health_monitor.get_health_stats()
        stats["monitoring_enabled"] = True
        return stats

    async def force_database_recovery(self) -> bool:
        """Force an async database connection recovery attempt."""
        if not self.health_monitor:
            return False

        if hasattr(self.health_monitor.database, 'recover_connection_pool'):
            try:
                result = await self.health_monitor.database.recover_connection_pool()
                if hasattr(self, 'logger'):
                    if result:
                        self.logger.info(
                            "Manual async database recovery successful"
                        )
                    else:
                        self.logger.warning(
                            "Manual async database recovery failed"
                        )
                return result
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(
                        f"Manual async database recovery error: {e}"
                    )
                return False

        return False

    def get_enhanced_database_connection(
        self, auto_recover: bool = True, max_retries: int = 2
    ):
        """Get an async database connection with enhanced recovery capabilities."""
        database = None
        if self.health_monitor:
            database = self.health_monitor.database
        elif hasattr(self, 'database'):
            database = self.database
        else:
            raise ValueError("No database available for connection")

        return database.get_connection(
            auto_recover=auto_recover, max_retries=max_retries
        )
