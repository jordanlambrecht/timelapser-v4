# backend/app/database/scheduled_job_operations.py
"""
Scheduled Job Operations - Database layer for scheduled job management.

This module provides database operations for the scheduled_jobs table,
supporting the hybrid scheduling approach where APScheduler remains the
execution engine but the database provides visibility, audit trails,
and recovery capabilities.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg

from ..models.scheduled_job_model import (
    ScheduledJob,
    ScheduledJobCreate,
    ScheduledJobExecution,
    ScheduledJobExecutionCreate,
    ScheduledJobStatistics,
    ScheduledJobUpdate,
)
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import cache, cached_response, generate_composite_etag
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import ScheduledJobOperationError


class ScheduledJobQueryBuilder:
    """Centralized query builder for scheduled job operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE UNIQUE INDEX idx_scheduled_jobs_job_id ON scheduled_jobs(job_id);
    - CREATE INDEX idx_scheduled_jobs_job_type ON scheduled_jobs(job_type);
    - CREATE INDEX idx_scheduled_jobs_status ON scheduled_jobs(status);
    - CREATE INDEX idx_scheduled_jobs_entity ON scheduled_jobs(entity_type, entity_id);
    - CREATE INDEX idx_scheduled_jobs_next_run ON scheduled_jobs(next_run_time) WHERE status = 'active';
    - CREATE INDEX idx_scheduled_jobs_status_type ON scheduled_jobs(status, job_type);
    - CREATE INDEX idx_scheduled_jobs_entity_status ON scheduled_jobs(entity_type, entity_id, status);
    - CREATE INDEX idx_scheduled_jobs_created_at ON scheduled_jobs(created_at DESC);
    - CREATE INDEX idx_scheduled_jobs_updated_at ON scheduled_jobs(updated_at DESC);
    - CREATE INDEX idx_scheduled_jobs_active_next_run ON scheduled_jobs(next_run_time, job_type) WHERE status = 'active';
    - CREATE INDEX idx_scheduled_job_executions_job_id ON scheduled_job_executions(job_id);
    - CREATE INDEX idx_scheduled_job_executions_start ON scheduled_job_executions(execution_start DESC);
    - CREATE INDEX idx_scheduled_job_executions_status ON scheduled_job_executions(status);
    """

    @staticmethod
    def get_base_fields():
        """Get standard fields for scheduled job queries."""
        return """
            id, job_id, job_type, schedule_pattern, interval_seconds,
            next_run_time, last_run_time, last_success_time, last_failure_time,
            entity_id, entity_type, config, status, execution_count,
            success_count, failure_count, last_error_message, created_at, updated_at
        """

    @staticmethod
    def build_upsert_query():
        """Build optimized upsert query for job creation/update using named parameters."""
        return """
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
                updated_at = %(updated_at)s
            RETURNING *
        """

    @staticmethod
    def build_filtered_query(where_conditions: List[str]):
        """Build filtered query for scheduled jobs."""
        fields = ScheduledJobQueryBuilder.get_base_fields()
        where_clause = (
            " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        )
        return f"""
            SELECT {fields}
            FROM scheduled_jobs
            {where_clause}
            ORDER BY job_type, created_at
        """

    @staticmethod
    def build_statistics_query():
        """Build optimized statistics query using CTEs."""
        return """
            WITH job_stats AS (
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
            )
            SELECT * FROM job_stats
        """

    @staticmethod
    def build_type_statistics_query():
        """Build query for job type statistics."""
        return """
            SELECT
                job_type,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE status = 'active') as active_count,
                COUNT(*) FILTER (WHERE status = 'error') as error_count,
                COALESCE(AVG(execution_count), 0) as avg_executions,
                COALESCE(AVG(CASE
                    WHEN execution_count > 0 THEN
                        (success_count::float / execution_count::float) * 100
                    ELSE 0
                END), 0) as avg_success_rate
            FROM scheduled_jobs
            GROUP BY job_type
            ORDER BY job_type
        """

    @staticmethod
    def build_bulk_status_update_query(job_count: int):
        """Build optimized bulk status update query using named parameters."""
        case_conditions = []
        for i in range(job_count):
            case_conditions.append(f"WHEN job_id = %(job_id_{i})s THEN %(status_{i})s")

        return f"""
            UPDATE scheduled_jobs
            SET status = CASE {' '.join(case_conditions)} END,
                updated_at = %(updated_at)s
            WHERE job_id IN ({','.join([f'%(job_id_{i})s' for i in range(job_count)])})
        """


class ScheduledJobOperations:
    """
    Async database operations for scheduled job management.

    Provides database operations for tracking APScheduler jobs,
    enabling visibility, persistence, and recovery across restarts.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with async database instance."""
        self.db = db
        self.cache_invalidation = CacheInvalidationService()

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
            # Use optimized query builder
            query = ScheduledJobQueryBuilder.build_upsert_query()
            config_json = json.dumps(job_data.config) if job_data.config else None

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    params = {
                        "job_id": job_data.job_id,
                        "job_type": job_data.job_type,
                        "schedule_pattern": job_data.schedule_pattern,
                        "interval_seconds": job_data.interval_seconds,
                        "next_run_time": job_data.next_run_time,
                        "entity_id": job_data.entity_id,
                        "entity_type": job_data.entity_type,
                        "config": config_json,
                        "status": job_data.status or "active",
                        "updated_at": utc_now(),
                    }
                    await cur.execute(query, params)

                    row = await cur.fetchone()
                    if row:
                        # Clear related caches since job data changed
                        await self._clear_job_caches(
                            job_data.job_id, updated_at=utc_now()
                        )
                        return self._row_to_scheduled_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=60, key_prefix="scheduled_job")
    async def get_job_by_id(self, job_id: str) -> Optional[ScheduledJob]:
        """Get scheduled job by job_id with sophisticated caching using named parameters."""
        try:
            fields = ScheduledJobQueryBuilder.get_base_fields()
            query = f"SELECT {fields} FROM scheduled_jobs WHERE job_id = %(job_id)s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, {"job_id": job_id})
                    row = await cur.fetchone()

                    if row:
                        job = self._row_to_scheduled_job(dict(row))
                        return job

                    return None

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=60, key_prefix="scheduled_job")
    async def get_jobs_by_type(
        self, job_type: str, status: Optional[str] = None
    ) -> List[ScheduledJob]:
        """Get scheduled jobs by type and optionally by status using named parameters."""
        try:
            conditions = ["job_type = %(job_type)s"]
            params = {"job_type": job_type}

            if status:
                conditions.append("status = %(status)s")
                params["status"] = status

            # Use optimized query builder
            query = ScheduledJobQueryBuilder.build_filtered_query(conditions)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    jobs = [self._row_to_scheduled_job(dict(row)) for row in rows]
                    return jobs

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=60, key_prefix="scheduled_job")
    async def get_jobs_by_entity(
        self, entity_type: str, entity_id: int
    ) -> List[ScheduledJob]:
        """Get scheduled jobs for a specific entity using named parameters."""
        try:
            # Use optimized query builder
            conditions = ["entity_type = %(entity_type)s", "entity_id = %(entity_id)s"]
            params = {"entity_type": entity_type, "entity_id": entity_id}
            query = ScheduledJobQueryBuilder.build_filtered_query(conditions)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    jobs = [self._row_to_scheduled_job(dict(row)) for row in rows]
                    return jobs

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=30, key_prefix="scheduled_job")
    async def get_active_jobs(self) -> List[ScheduledJob]:
        """Get all active scheduled jobs using named parameters."""
        try:
            # Use optimized query builder
            conditions = ["status = %(status)s"]
            params = {"status": "active"}
            query = ScheduledJobQueryBuilder.build_filtered_query(conditions)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    jobs = [self._row_to_scheduled_job(dict(row)) for row in rows]
                    return jobs

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def update_job_status(self, job_id: str, status: str) -> bool:
        """Update job status using named parameters."""
        try:
            query = """
                UPDATE scheduled_jobs
                SET status = %(status)s, updated_at = %(updated_at)s
                WHERE job_id = %(job_id)s
            """

            current_time = utc_now()
            params = {"status": status, "updated_at": current_time, "job_id": job_id}

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    success = cur.rowcount > 0

                    # Clear related caches if update was successful
                    if success:
                        await self._clear_job_caches(job_id, updated_at=current_time)

                    return success

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def update_job_timing(
        self,
        job_id: str,
        next_run_time: Optional[datetime] = None,
        last_run_time: Optional[datetime] = None,
        last_success_time: Optional[datetime] = None,
        last_failure_time: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job timing and execution information using named parameters."""
        try:
            # Build dynamic query using safe field mapping
            current_time = utc_now()
            params = {
                "updated_at": current_time,
                "job_id": job_id,
            }

            # Build safe UPDATE fields
            update_fields = ["updated_at = %(updated_at)s"]

            if next_run_time is not None:
                update_fields.append("next_run_time = %(next_run_time)s")
                params["next_run_time"] = next_run_time

            if last_run_time is not None:
                update_fields.append("last_run_time = %(last_run_time)s")
                params["last_run_time"] = last_run_time

            if last_success_time is not None:
                update_fields.append("last_success_time = %(last_success_time)s")
                update_fields.append("success_count = success_count + 1")
                params["last_success_time"] = last_success_time

            if last_failure_time is not None:
                update_fields.append("last_failure_time = %(last_failure_time)s")
                update_fields.append("failure_count = failure_count + 1")
                params["last_failure_time"] = last_failure_time

            if error_message is not None:
                update_fields.append("last_error_message = %(error_message)s")
                params["error_message"] = error_message

            # Always increment execution count
            update_fields.append("execution_count = execution_count + 1")

            # Use safe field construction - fields are hardcoded, not user input
            query = f"""
                UPDATE scheduled_jobs
                SET {', '.join(update_fields)}
                WHERE job_id = %(job_id)s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    success = cur.rowcount > 0

                    # Clear related caches if update was successful
                    if success:
                        await self._clear_job_caches(job_id, updated_at=current_time)

                    return success

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def delete_job(self, job_id: str) -> bool:
        """Delete scheduled job using named parameters."""
        try:
            query = "DELETE FROM scheduled_jobs WHERE job_id = %(job_id)s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, {"job_id": job_id})
                    success = cur.rowcount > 0

                    # Clear related caches if deletion was successful
                    if success:
                        await self._clear_job_caches(job_id)

                    return success

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def cleanup_old_jobs(self, max_age_days: int = 30) -> int:
        """Clean up old disabled/error jobs using safe date calculation."""
        try:
            # Calculate cutoff time safely in Python instead of dangerous SQL interpolation
            from datetime import timedelta

            cutoff_time = utc_now() - timedelta(days=max_age_days)

            query = """
                DELETE FROM scheduled_jobs
                WHERE status IN ('disabled', 'error')
                    AND updated_at < %(cutoff_time)s
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, {"cutoff_time": cutoff_time})
                    return cur.rowcount or 0

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def log_job_execution(
        self, execution_data: ScheduledJobExecutionCreate
    ) -> Optional[ScheduledJobExecution]:
        """Log a job execution."""
        try:
            # First get the scheduled_job_id using named parameters
            job_query = "SELECT id FROM scheduled_jobs WHERE job_id = %(job_id)s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(job_query, {"job_id": execution_data.job_id})
                    job_row = await cur.fetchone()

                    if not job_row:
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

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

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

    @cached_response(ttl_seconds=60, key_prefix="scheduled_job")
    async def get_jobs_filtered(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        include_disabled: bool = False,
    ) -> List[ScheduledJob]:
        """Get filtered list of scheduled jobs with sophisticated caching."""
        try:
            conditions = []
            params = {}

            if job_type:
                conditions.append("job_type = %(job_type)s")
                params["job_type"] = job_type
            if status:
                conditions.append("status = %(status)s")
                params["status"] = status
            if entity_type:
                conditions.append("entity_type = %(entity_type)s")
                params["entity_type"] = entity_type
            if entity_id:
                conditions.append("entity_id = %(entity_id)s")
                params["entity_id"] = entity_id
            if not include_disabled:
                conditions.append("status != 'disabled'")

            # Use optimized query builder
            query = ScheduledJobQueryBuilder.build_filtered_query(conditions)

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()

                    jobs = [self._row_to_scheduled_job(dict(row)) for row in rows]
                    return jobs

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=30, key_prefix="scheduled_job")
    async def get_job_executions(
        self, job_id: str, limit: int = 50, offset: int = 0
    ) -> List[ScheduledJobExecution]:
        """Get execution history for a job using named parameters."""
        try:
            query = """
                SELECT * FROM scheduled_job_executions
                WHERE job_id = %(job_id)s
                ORDER BY execution_start DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """

            params = {"job_id": job_id, "limit": limit, "offset": offset}

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()
                    executions = [
                        self._row_to_scheduled_job_execution(dict(row)) for row in rows
                    ]
                    return executions

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=60, key_prefix="scheduled_job")
    async def get_job_execution_count(self, job_id: str) -> int:
        """Get total execution count for a job using named parameters."""
        try:
            query = "SELECT COUNT(*) as count FROM scheduled_job_executions WHERE job_id = %(job_id)s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, {"job_id": job_id})
                    row = await cur.fetchone()
                    count = row["count"] if row else 0
                    return count

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=60, key_prefix="scheduled_job")
    async def get_job_statistics(self) -> ScheduledJobStatistics:
        """Get comprehensive job statistics with sophisticated caching."""
        try:
            # Use optimized CTE-based query
            query = ScheduledJobQueryBuilder.build_statistics_query()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    row = await cur.fetchone()

                    if row:
                        stats_dict = dict(row)
                        result = ScheduledJobStatistics(
                            total_jobs=int(stats_dict["total_jobs"] or 0),
                            active_jobs=int(stats_dict["active_jobs"] or 0),
                            paused_jobs=int(stats_dict["paused_jobs"] or 0),
                            disabled_jobs=int(stats_dict["disabled_jobs"] or 0),
                            error_jobs=int(stats_dict["error_jobs"] or 0),
                            unique_job_types=int(stats_dict["unique_job_types"] or 0),
                            total_executions=int(stats_dict["total_executions"] or 0),
                            total_successes=int(stats_dict["total_successes"] or 0),
                            total_failures=int(stats_dict["total_failures"] or 0),
                        )
                        return result

                    default_stats = ScheduledJobStatistics()
                    return default_stats

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    @cached_response(ttl_seconds=120, key_prefix="scheduled_job")
    async def get_job_type_statistics(self) -> Dict[str, Any]:
        """Get statistics broken down by job type with sophisticated caching."""
        try:
            # Use optimized query builder
            query = ScheduledJobQueryBuilder.build_type_statistics_query()

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    rows = await cur.fetchall()

                    result = {
                        row["job_type"]: {
                            "count": int(row["count"]),
                            "active_count": int(row["active_count"]),
                            "error_count": int(row["error_count"]),
                            "avg_executions": float(row["avg_executions"]),
                            "avg_success_rate": float(row["avg_success_rate"]),
                        }
                        for row in rows
                    }
                    return result

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def update_job(self, job_id: str, update_data: "ScheduledJobUpdate") -> bool:
        """Update a scheduled job with new data using named parameters."""
        try:
            # Build dynamic update query using safe field mapping
            current_time = utc_now()
            params = {
                "updated_at": current_time,
                "job_id": job_id,
            }

            # Build safe UPDATE fields
            update_fields = ["updated_at = %(updated_at)s"]

            if update_data.schedule_pattern is not None:
                update_fields.append("schedule_pattern = %(schedule_pattern)s")
                params["schedule_pattern"] = update_data.schedule_pattern
            if update_data.interval_seconds is not None:
                update_fields.append("interval_seconds = %(interval_seconds)s")
                params["interval_seconds"] = update_data.interval_seconds
            if update_data.next_run_time is not None:
                update_fields.append("next_run_time = %(next_run_time)s")
                params["next_run_time"] = update_data.next_run_time
            if update_data.entity_id is not None:
                update_fields.append("entity_id = %(entity_id)s")
                params["entity_id"] = update_data.entity_id
            if update_data.entity_type is not None:
                update_fields.append("entity_type = %(entity_type)s")
                params["entity_type"] = update_data.entity_type
            if update_data.config is not None:
                update_fields.append("config = %(config)s")
                params["config"] = json.dumps(update_data.config)
            if update_data.status is not None:
                update_fields.append("status = %(status)s")
                params["status"] = update_data.status

            if len(update_fields) == 1:  # Only updated_at
                return True  # Nothing to update

            # Use safe field construction - fields are hardcoded, not user input
            query = f"UPDATE scheduled_jobs SET {', '.join(update_fields)} WHERE job_id = %(job_id)s"

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    success = cur.rowcount > 0

                    # Clear related caches if update was successful
                    if success:
                        await self._clear_job_caches(job_id, updated_at=current_time)

                    return success

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    async def bulk_update_job_status(
        self, job_ids: List[str], status: str
    ) -> Dict[str, bool]:
        """Update status for multiple jobs using optimized bulk query with safe IN clause."""
        if not job_ids:
            return {}

        results = {}

        try:
            # Use safe placeholder generation for IN clause - create named parameters
            current_time = utc_now()
            params = {"status": status, "updated_at": current_time}

            # Create safe named placeholders for each job_id
            job_placeholders = []
            for i, job_id in enumerate(job_ids):
                placeholder = f"job_id_{i}"
                job_placeholders.append(f"%({placeholder})s")
                params[placeholder] = job_id

            # Safe construction - job_placeholders contains only validated named parameters
            query = f"""
                UPDATE scheduled_jobs
                SET status = %(status)s, updated_at = %(updated_at)s
                WHERE job_id IN ({','.join(job_placeholders)})
                RETURNING job_id
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    updated_rows = await cur.fetchall()

                    # Track which jobs were successfully updated
                    updated_job_ids = {row["job_id"] for row in updated_rows}

                    # Set results for all requested jobs
                    for job_id in job_ids:
                        results[job_id] = job_id in updated_job_ids

                        # Clear cache for updated jobs
                        if job_id in updated_job_ids:
                            await self._clear_job_caches(
                                job_id, updated_at=current_time
                            )

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

        return results

    async def _clear_job_caches(
        self, job_id: str, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to a specific job using sophisticated cache system."""
        # Clear scheduled job caches using advanced cache manager
        cache_patterns = [
            f"scheduled_job:get_job_by_id:{job_id}",
            "scheduled_job:get_active_jobs",
            "scheduled_job:get_job_statistics",
            "scheduled_job:get_job_type_statistics",
            "scheduled_job:get_jobs_filtered",
            "scheduled_job:get_jobs_by_type",
            "scheduled_job:get_jobs_by_entity",
            f"scheduled_job:get_job_executions:{job_id}",
            f"scheduled_job:get_job_execution_count:{job_id}",
        ]

        # Use ETag-aware invalidation if timestamp provided
        if updated_at:
            etag = generate_composite_etag(job_id, updated_at)
            await self.cache_invalidation.invalidate_with_etag_validation(
                f"scheduled_job:metadata:{job_id}", etag
            )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

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

    def __init__(self, db: SyncDatabase) -> None:
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
                    updated_at = %(updated_at)s
                RETURNING *
            """

            config_json = json.dumps(job_data.config) if job_data.config else None

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    params = {
                        "job_id": job_data.job_id,
                        "job_type": job_data.job_type,
                        "schedule_pattern": job_data.schedule_pattern,
                        "interval_seconds": job_data.interval_seconds,
                        "next_run_time": job_data.next_run_time,
                        "entity_id": job_data.entity_id,
                        "entity_type": job_data.entity_type,
                        "config": config_json,
                        "status": job_data.status or "active",
                        "updated_at": utc_now(),
                    }
                    cur.execute(query, params)

                    row = cur.fetchone()
                    if row:
                        return self._row_to_scheduled_job(dict(row))
                    return None

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    def get_active_jobs(self) -> List[ScheduledJob]:
        """Get all active scheduled jobs (sync version)."""
        try:
            query = "SELECT * FROM scheduled_jobs WHERE status = 'active' ORDER BY job_type, created_at"

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    rows = cur.fetchall()

                    return [self._row_to_scheduled_job(dict(row)) for row in rows]

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    def delete_job(self, job_id: str) -> bool:
        """Delete scheduled job (sync version) using named parameters."""
        try:
            query = "DELETE FROM scheduled_jobs WHERE job_id = %(job_id)s"

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, {"job_id": job_id})
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

    def update_job_timing(
        self,
        job_id: str,
        next_run_time: Optional[datetime] = None,
        last_run_time: Optional[datetime] = None,
        last_success_time: Optional[datetime] = None,
        last_failure_time: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job timing and execution information (sync version) using named parameters."""
        try:
            # Build dynamic query using safe field mapping
            current_time = utc_now()
            params = {
                "updated_at": current_time,
                "job_id": job_id,
            }

            # Build safe UPDATE fields
            update_fields = ["updated_at = %(updated_at)s"]

            if next_run_time is not None:
                update_fields.append("next_run_time = %(next_run_time)s")
                params["next_run_time"] = next_run_time
            if last_run_time is not None:
                update_fields.append("last_run_time = %(last_run_time)s")
                params["last_run_time"] = last_run_time
            if last_success_time is not None:
                update_fields.append("last_success_time = %(last_success_time)s")
                params["last_success_time"] = last_success_time
            if last_failure_time is not None:
                update_fields.append("last_failure_time = %(last_failure_time)s")
                params["last_failure_time"] = last_failure_time
            if error_message is not None:
                update_fields.append("last_error_message = %(error_message)s")
                params["error_message"] = error_message

            # If no updates besides updated_at, return True without querying
            if len(update_fields) == 1:  # Only updated_at
                return True

            # Use safe field construction - fields are hardcoded, not user input
            query = f"UPDATE scheduled_jobs SET {', '.join(update_fields)} WHERE job_id = %(job_id)s"

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.rowcount > 0

        except (psycopg.Error, KeyError, ValueError):
            raise ScheduledJobOperationError(
                "Failed to perform operation",
                operation="scheduled_job_operation",
            )

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
