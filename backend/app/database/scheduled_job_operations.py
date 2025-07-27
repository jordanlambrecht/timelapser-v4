# backend/app/database/scheduled_job_operations.py
"""
Scheduled Job Operations - Database layer for scheduled job management.

This module provides database operations for the scheduled_jobs table,
supporting the hybrid scheduling approach where APScheduler remains the
execution engine but the database provides visibility, audit trails,
and recovery capabilities.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import psycopg
import json

from .core import AsyncDatabase, SyncDatabase
from ..models.scheduled_job_model import (
    ScheduledJob,
    ScheduledJobCreate,
    ScheduledJobUpdate,
    ScheduledJobExecution,
    ScheduledJobExecutionCreate,
    ScheduledJobStatistics,
)
from ..enums import JobStatus
from ..utils.time_utils import utc_now


class ScheduledJobOperations:
    """
    Async database operations for scheduled job management.

    Provides database operations for tracking APScheduler jobs,
    enabling visibility, persistence, and recovery across restarts.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance."""
        self.db = db

    async def create_or_update_job(
        self, job_data: ScheduledJobCreate
    ) -> Optional[ScheduledJob]:
        """
        Create a new scheduled job or update existing one.

        Uses UPSERT (ON CONFLICT) to handle both creation and updates
        since APScheduler may recreate jobs with the same ID.

        Args:
            job_data: Job creation data

        Returns:
            Created or updated ScheduledJob instance
        """
        try:
            query = """
                INSERT INTO scheduled_jobs (
                    job_id, job_type, schedule_pattern, interval_seconds,
                    next_run_time, entity_id, entity_type, config, status
                ) VALUES (
                    %(job_id)s, %(job_type)s, %(schedule_pattern)s, %(interval_seconds)s,
                    %(next_run_time)s, %(entity_id)s, %(entity_type)s, %(config)s, %(status)s
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    job_type = EXCLUDED.job_type,
                    schedule_pattern = EXCLUDED.schedule_pattern,
                    interval_seconds = EXCLUDED.interval_seconds,
                    next_run_time = EXCLUDED.next_run_time,
                    entity_id = EXCLUDED.entity_id,
                    entity_type = EXCLUDED.entity_type,
                    config = EXCLUDED.config,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                RETURNING *
            """

            config_json = json.dumps(job_data.config) if job_data.config else None

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        query,
                        {
                            "job_id": job_data.job_id,
                            "job_type": job_data.job_type,
                            "schedule_pattern": job_data.schedule_pattern,
                            "interval_seconds": job_data.interval_seconds,
                            "next_run_time": job_data.next_run_time,
                            "entity_id": job_data.entity_id,
                            "entity_type": job_data.entity_type,
                            "config": config_json,
                            "status": job_data.status or "active",
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        return self._row_to_scheduled_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Error creating/updating scheduled job {job_data.job_id}: {e}"
            )
            return None

    async def get_job_by_id(self, job_id: str) -> Optional[ScheduledJob]:
        """Get scheduled job by job_id."""
        try:
            query = "SELECT * FROM scheduled_jobs WHERE job_id = %s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (job_id,))
                    row = await cur.fetchone()

                    if row:
                        return self._row_to_scheduled_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting scheduled job {job_id}: {e}")
            return None

    async def get_jobs_by_type(
        self, job_type: str, status: Optional[str] = None
    ) -> List[ScheduledJob]:
        """Get scheduled jobs by type and optionally by status."""
        try:
            if status:
                query = "SELECT * FROM scheduled_jobs WHERE job_type = %s AND status = %s ORDER BY created_at"
                params = (job_type, status)
            else:
                query = "SELECT * FROM scheduled_jobs WHERE job_type = %s ORDER BY created_at"
                params = (job_type,)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    return [self._row_to_scheduled_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting scheduled jobs by type {job_type}: {e}")
            return []

    async def get_jobs_by_entity(
        self, entity_type: str, entity_id: int
    ) -> List[ScheduledJob]:
        """Get scheduled jobs for a specific entity."""
        try:
            query = """
                SELECT * FROM scheduled_jobs
                WHERE entity_type = %s AND entity_id = %s
                ORDER BY created_at
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (entity_type, entity_id))
                    rows = await cur.fetchall()

                    return [self._row_to_scheduled_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Error getting scheduled jobs for {entity_type} {entity_id}: {e}"
            )
            return []

    async def get_active_jobs(self) -> List[ScheduledJob]:
        """Get all active scheduled jobs."""
        try:
            query = "SELECT * FROM scheduled_jobs WHERE status = 'active' ORDER BY job_type, created_at"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    rows = await cur.fetchall()

                    return [self._row_to_scheduled_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting active scheduled jobs: {e}")
            return []

    async def update_job_status(self, job_id: str, status: str) -> bool:
        """Update job status."""
        try:
            query = """
                UPDATE scheduled_jobs
                SET status = %s, updated_at = NOW()
                WHERE job_id = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (status, job_id))
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error updating job status for {job_id}: {e}")
            return False

    async def update_job_timing(
        self,
        job_id: str,
        next_run_time: Optional[datetime] = None,
        last_run_time: Optional[datetime] = None,
        last_success_time: Optional[datetime] = None,
        last_failure_time: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job timing and execution information."""
        try:
            # Build dynamic query based on provided parameters
            updates = ["updated_at = NOW()"]
            params = []

            if next_run_time is not None:
                updates.append("next_run_time = %s")
                params.append(next_run_time)

            if last_run_time is not None:
                updates.append("last_run_time = %s")
                params.append(last_run_time)

            if last_success_time is not None:
                updates.append("last_success_time = %s")
                updates.append("success_count = success_count + 1")
                params.append(last_success_time)

            if last_failure_time is not None:
                updates.append("last_failure_time = %s")
                updates.append("failure_count = failure_count + 1")
                params.append(last_failure_time)

            if error_message is not None:
                updates.append("last_error_message = %s")
                params.append(error_message)

            # Always increment execution count
            updates.append("execution_count = execution_count + 1")
            params.append(job_id)

            query = f"""
                UPDATE scheduled_jobs
                SET {', '.join(updates)}
                WHERE job_id = %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error updating job timing for {job_id}: {e}")
            return False

    async def delete_job(self, job_id: str) -> bool:
        """Delete scheduled job."""
        try:
            query = "DELETE FROM scheduled_jobs WHERE job_id = %s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (job_id,))
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error deleting scheduled job {job_id}: {e}")
            return False

    async def cleanup_old_jobs(self, max_age_days: int = 30) -> int:
        """Clean up old disabled/error jobs."""
        try:
            query = """
                DELETE FROM scheduled_jobs
                WHERE status IN ('disabled', 'error')
                    AND updated_at < NOW() - INTERVAL '%s days'
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (max_age_days,))
                    return cur.rowcount or 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error cleaning up old scheduled jobs: {e}")
            return 0

    async def log_job_execution(
        self, execution_data: ScheduledJobExecutionCreate
    ) -> Optional[ScheduledJobExecution]:
        """Log a job execution."""
        try:
            # First get the scheduled_job_id
            job_query = "SELECT id FROM scheduled_jobs WHERE job_id = %s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(job_query, (execution_data.job_id,))
                    job_row = await cur.fetchone()

                    if not job_row:
                        logger.warning(
                            f"Cannot log execution for unknown job {execution_data.job_id}"
                        )
                        return None

                    scheduled_job_id = (
                        job_row["id"] if isinstance(job_row, dict) else job_row[0]
                    )

                    # Insert execution log
                    insert_query = """
                        INSERT INTO scheduled_job_executions (
                            job_id, scheduled_job_id, execution_start, execution_end,
                            status, result_message, error_message, execution_duration_ms, metadata
                        ) VALUES (
                            %(job_id)s, %(scheduled_job_id)s, %(execution_start)s, %(execution_end)s,
                            %(status)s, %(result_message)s, %(error_message)s, %(execution_duration_ms)s, %(metadata)s
                        )
                        RETURNING *
                    """

                    metadata_json = (
                        json.dumps(execution_data.metadata)
                        if execution_data.metadata
                        else None
                    )

                    await cur.execute(
                        insert_query,
                        {
                            "job_id": execution_data.job_id,
                            "scheduled_job_id": scheduled_job_id,
                            "execution_start": execution_data.execution_start,
                            "execution_end": execution_data.execution_end,
                            "status": execution_data.status,
                            "result_message": execution_data.result_message,
                            "error_message": execution_data.error_message,
                            "execution_duration_ms": execution_data.execution_duration_ms,
                            "metadata": metadata_json,
                        },
                    )

                    row = await cur.fetchone()
                    if row:
                        return self._row_to_execution(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Error logging job execution for {execution_data.job_id}: {e}"
            )
            return None

    def _row_to_scheduled_job(self, row: Dict[str, Any]) -> ScheduledJob:
        """Convert database row to ScheduledJob model."""
        config = json.loads(row["config"]) if row["config"] else {}

        return ScheduledJob(
            id=row["id"],
            job_id=row["job_id"],
            job_type=row["job_type"],
            schedule_pattern=row["schedule_pattern"],
            interval_seconds=row["interval_seconds"],
            next_run_time=row["next_run_time"],
            last_run_time=row["last_run_time"],
            last_success_time=row["last_success_time"],
            last_failure_time=row["last_failure_time"],
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            config=config,
            status=row["status"],
            execution_count=row["execution_count"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            last_error_message=row["last_error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_execution(self, row: Dict[str, Any]) -> ScheduledJobExecution:
        """Convert database row to ScheduledJobExecution model."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return ScheduledJobExecution(
            id=row["id"],
            job_id=row["job_id"],
            scheduled_job_id=row["scheduled_job_id"],
            execution_start=row["execution_start"],
            execution_end=row["execution_end"],
            status=row["status"],
            result_message=row["result_message"],
            error_message=row["error_message"],
            execution_duration_ms=row["execution_duration_ms"],
            metadata=metadata,
            created_at=row["created_at"],
        )

    async def get_jobs_filtered(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        include_disabled: bool = False,
    ) -> List[ScheduledJob]:
        """Get filtered list of scheduled jobs."""
        try:
            conditions = []
            params = []

            if job_type:
                conditions.append("job_type = %s")
                params.append(job_type)
            if status:
                conditions.append("status = %s")
                params.append(status)
            if entity_type:
                conditions.append("entity_type = %s")
                params.append(entity_type)
            if entity_id:
                conditions.append("entity_id = %s")
                params.append(entity_id)
            if not include_disabled:
                conditions.append("status != 'disabled'")

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT * FROM scheduled_jobs{where_clause} ORDER BY job_type, created_at"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()
                    return [self._row_to_scheduled_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting filtered jobs: {e}")
            return []

    async def get_job_executions(
        self, job_id: str, limit: int = 50, offset: int = 0
    ) -> List[ScheduledJobExecution]:
        """Get execution history for a job."""
        try:
            query = """
                SELECT * FROM scheduled_job_executions 
                WHERE job_id = %s 
                ORDER BY execution_start DESC 
                LIMIT %s OFFSET %s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (job_id, limit, offset))
                    rows = await cur.fetchall()
                    return [
                        self._row_to_scheduled_job_execution(dict(row)) for row in rows
                    ]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting job executions for {job_id}: {e}")
            return []

    async def get_job_execution_count(self, job_id: str) -> int:
        """Get total execution count for a job."""
        try:
            query = "SELECT COUNT(*) as count FROM scheduled_job_executions WHERE job_id = %s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (job_id,))
                    row = await cur.fetchone()
                    return row["count"] if row else 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting execution count for {job_id}: {e}")
            return 0

    async def get_job_statistics(self) -> ScheduledJobStatistics:
        """Get comprehensive job statistics."""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_jobs,
                    COUNT(*) FILTER (WHERE status = 'active') as active_jobs,
                    COUNT(*) FILTER (WHERE status = 'paused') as paused_jobs,
                    COUNT(*) FILTER (WHERE status = 'disabled') as disabled_jobs,
                    COUNT(*) FILTER (WHERE status = 'error') as error_jobs,
                    COUNT(DISTINCT job_type) as unique_job_types,
                    COALESCE(SUM(execution_count), 0) as total_executions,
                    COALESCE(SUM(success_count), 0) as total_successes,
                    COALESCE(SUM(failure_count), 0) as total_failures
                FROM scheduled_jobs
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    row = await cur.fetchone()

                    if row:
                        return ScheduledJobStatistics(
                            total_jobs=int(row["total_jobs"] or 0),
                            active_jobs=int(row["active_jobs"] or 0),
                            paused_jobs=int(row["paused_jobs"] or 0),
                            disabled_jobs=int(row["disabled_jobs"] or 0),
                            error_jobs=int(row["error_jobs"] or 0),
                            unique_job_types=int(row["unique_job_types"] or 0),
                            total_executions=int(row["total_executions"] or 0),
                            total_successes=int(row["total_successes"] or 0),
                            total_failures=int(row["total_failures"] or 0),
                        )

                    return ScheduledJobStatistics()

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting job statistics: {e}")
            return ScheduledJobStatistics()

    async def get_job_type_statistics(self) -> Dict[str, Any]:
        """Get statistics broken down by job type."""
        try:
            query = """
                SELECT 
                    job_type,
                    COUNT(*) as count,
                    COUNT(*) FILTER (WHERE status = 'active') as active_count,
                    COUNT(*) FILTER (WHERE status = 'error') as error_count,
                    COALESCE(AVG(execution_count), 0) as avg_executions,
                    COALESCE(AVG(CASE WHEN execution_count > 0 THEN
                        (success_count::float / execution_count::float) * 100
                        ELSE 0 END), 0) as avg_success_rate
                FROM scheduled_jobs
                GROUP BY job_type
                ORDER BY job_type
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    rows = await cur.fetchall()

                    return {
                        row["job_type"]: {
                            "count": int(row["count"]),
                            "active_count": int(row["active_count"]),
                            "error_count": int(row["error_count"]),
                            "avg_executions": float(row["avg_executions"]),
                            "avg_success_rate": float(row["avg_success_rate"]),
                        }
                        for row in rows
                    }

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting job type statistics: {e}")
            return {}

    async def update_job(self, job_id: str, update_data: "ScheduledJobUpdate") -> bool:
        """Update a scheduled job with new data."""
        try:
            # Build dynamic update query
            updates = []
            params = []

            if update_data.schedule_pattern is not None:
                updates.append("schedule_pattern = %s")
                params.append(update_data.schedule_pattern)
            if update_data.interval_seconds is not None:
                updates.append("interval_seconds = %s")
                params.append(update_data.interval_seconds)
            if update_data.next_run_time is not None:
                updates.append("next_run_time = %s")
                params.append(update_data.next_run_time)
            if update_data.entity_id is not None:
                updates.append("entity_id = %s")
                params.append(update_data.entity_id)
            if update_data.entity_type is not None:
                updates.append("entity_type = %s")
                params.append(update_data.entity_type)
            if update_data.config is not None:
                updates.append("config = %s")
                params.append(json.dumps(update_data.config))
            if update_data.status is not None:
                updates.append("status = %s")
                params.append(update_data.status)

            if not updates:
                return True  # Nothing to update

            updates.append("updated_at = NOW()")
            params.append(job_id)

            query = f"UPDATE scheduled_jobs SET {', '.join(updates)} WHERE job_id = %s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error updating job {job_id}: {e}")
            return False

    async def bulk_update_job_status(
        self, job_ids: List[str], status: str
    ) -> Dict[str, bool]:
        """Update status for multiple jobs."""
        results = {}

        try:
            async with self.db.get_connection() as conn:
                for job_id in job_ids:
                    try:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "UPDATE scheduled_jobs SET status = %s, updated_at = NOW() WHERE job_id = %s",
                                (status, job_id),
                            )
                            results[job_id] = cur.rowcount > 0
                    except Exception as e:
                        logger.warning(f"Failed to update job {job_id}: {e}")
                        results[job_id] = False

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error in bulk update: {e}")
            # Mark all as failed if there was a connection error
            for job_id in job_ids:
                results[job_id] = False

        return results

    def _row_to_scheduled_job_execution(
        self, row: Dict[str, Any]
    ) -> ScheduledJobExecution:
        """Convert database row to ScheduledJobExecution model."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return ScheduledJobExecution(
            id=row["id"],
            scheduled_job_id=row["scheduled_job_id"],
            job_id=row["job_id"],
            execution_start=row["execution_start"],
            execution_end=row["execution_end"],
            status=row["status"],
            result_message=row["result_message"],
            error_message=row["error_message"],
            execution_duration_ms=row["execution_duration_ms"],
            metadata=metadata,
            created_at=row["created_at"],
        )


class SyncScheduledJobOperations:
    """
    Sync database operations for scheduled job management.

    Provides synchronous versions for use in sync contexts.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance."""
        self.db = db

    def create_or_update_job(
        self, job_data: ScheduledJobCreate
    ) -> Optional[ScheduledJob]:
        """Create or update scheduled job (sync version)."""
        try:
            query = """
                INSERT INTO scheduled_jobs (
                    job_id, job_type, schedule_pattern, interval_seconds,
                    next_run_time, entity_id, entity_type, config, status
                ) VALUES (
                    %(job_id)s, %(job_type)s, %(schedule_pattern)s, %(interval_seconds)s,
                    %(next_run_time)s, %(entity_id)s, %(entity_type)s, %(config)s, %(status)s
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    job_type = EXCLUDED.job_type,
                    schedule_pattern = EXCLUDED.schedule_pattern,
                    interval_seconds = EXCLUDED.interval_seconds,
                    next_run_time = EXCLUDED.next_run_time,
                    entity_id = EXCLUDED.entity_id,
                    entity_type = EXCLUDED.entity_type,
                    config = EXCLUDED.config,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                RETURNING *
            """

            config_json = json.dumps(job_data.config) if job_data.config else None

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        {
                            "job_id": job_data.job_id,
                            "job_type": job_data.job_type,
                            "schedule_pattern": job_data.schedule_pattern,
                            "interval_seconds": job_data.interval_seconds,
                            "next_run_time": job_data.next_run_time,
                            "entity_id": job_data.entity_id,
                            "entity_type": job_data.entity_type,
                            "config": config_json,
                            "status": job_data.status or "active",
                        },
                    )

                    row = cur.fetchone()
                    if row:
                        return self._row_to_scheduled_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(
                f"Error creating/updating scheduled job {job_data.job_id}: {e}"
            )
            return None

    def get_active_jobs(self) -> List[ScheduledJob]:
        """Get all active scheduled jobs (sync version)."""
        try:
            query = "SELECT * FROM scheduled_jobs WHERE status = 'active' ORDER BY job_type, created_at"

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    rows = cur.fetchall()

                    return [self._row_to_scheduled_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error getting active scheduled jobs: {e}")
            return []

    def delete_job(self, job_id: str) -> bool:
        """Delete scheduled job (sync version)."""
        try:
            query = "DELETE FROM scheduled_jobs WHERE job_id = %s"

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (job_id,))
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error deleting scheduled job {job_id}: {e}")
            return False

    def update_job_timing(
        self,
        job_id: str,
        next_run_time: Optional[datetime] = None,
        last_run_time: Optional[datetime] = None,
        last_success_time: Optional[datetime] = None,
        last_failure_time: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job timing and execution information (sync version)."""
        try:
            # Build dynamic query based on provided parameters
            updates = ["updated_at = NOW()"]
            params = []

            if next_run_time is not None:
                updates.append("next_run_time = %s")
                params.append(next_run_time)
            if last_run_time is not None:
                updates.append("last_run_time = %s")
                params.append(last_run_time)
            if last_success_time is not None:
                updates.append("last_success_time = %s")
                params.append(last_success_time)
            if last_failure_time is not None:
                updates.append("last_failure_time = %s")
                params.append(last_failure_time)
            if error_message is not None:
                updates.append("error_message = %s")
                params.append(error_message)

            # If no updates besides updated_at, return True without querying
            if len(updates) == 1:
                return True

            query = f"UPDATE scheduled_jobs SET {', '.join(updates)} WHERE job_id = %s"
            params.append(job_id)

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError) as e:
            logger.error(f"Error updating job timing for {job_id}: {e}")
            return False

    def _row_to_scheduled_job(self, row: Dict[str, Any]) -> ScheduledJob:
        """Convert database row to ScheduledJob model."""
        config = json.loads(row["config"]) if row["config"] else {}

        return ScheduledJob(
            id=row["id"],
            job_id=row["job_id"],
            job_type=row["job_type"],
            schedule_pattern=row["schedule_pattern"],
            interval_seconds=row["interval_seconds"],
            next_run_time=row["next_run_time"],
            last_run_time=row["last_run_time"],
            last_success_time=row["last_success_time"],
            last_failure_time=row["last_failure_time"],
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            config=config,
            status=row["status"],
            execution_count=row["execution_count"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            last_error_message=row["last_error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
