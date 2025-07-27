# backend/app/database/recovery_operations.py
"""
Recovery Operations - Database operations for job recovery across all job types.

This module provides database operations for recovering stuck jobs, following the
standard operations layer pattern. Handles both async and sync database operations
for consistent recovery behavior across all job systems.
"""

from typing import Dict, Any, Optional
from datetime import timedelta
from loguru import logger

from .core import AsyncDatabase, SyncDatabase
from ..enums import JobStatus, SSEEvent, SSEEventSource
from ..utils.time_utils import utc_now


class RecoveryOperations:
    """
    Async database operations for job recovery across all job types.

    Provides generic recovery methods that work with any job table following
    the standard pattern with 'status', 'created_at', and 'updated_at' columns.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database instance."""
        self.db = db

    async def recover_stuck_jobs_for_table(
        self,
        table_name: str,
        max_processing_age_minutes: int = 30,
        job_type_name: str = "jobs",
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generic recovery method for any job table (async version).

        Finds jobs stuck in 'processing' status for longer than the specified
        time and resets them to 'pending' status for retry.

        Args:
            table_name: Name of the job table (e.g., 'thumbnail_generation_jobs')
            max_processing_age_minutes: Maximum time a job can be in processing
            job_type_name: Human-readable job type for logging (e.g., 'thumbnail jobs')
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with recovery statistics
        """
        recovery_start_time = utc_now()

        try:
            # Calculate cutoff time for stuck jobs
            cutoff_time = recovery_start_time - timedelta(
                minutes=max_processing_age_minutes
            )

            # Find stuck jobs
            find_query = f"""
                SELECT id, created_at, updated_at
                FROM {table_name}
                WHERE status = %s
                    AND updated_at < %s
                ORDER BY updated_at ASC
            """

            stuck_jobs = []
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        find_query, (JobStatus.PROCESSING.value, cutoff_time)
                    )
                    stuck_jobs = await cur.fetchall()

            if not stuck_jobs:
                logger.debug(f"🔄 No stuck {job_type_name} found for recovery")
                return {
                    "stuck_jobs_found": 0,
                    "stuck_jobs_recovered": 0,
                    "stuck_jobs_failed": 0,
                    "recovery_duration_seconds": 0.0,
                    "cutoff_time": cutoff_time.isoformat(),
                    "recovery_successful": True,
                }

            logger.info(f"🔄 Found {len(stuck_jobs)} stuck {job_type_name} to recover")

            # Broadcast recovery start event
            if sse_broadcaster:
                try:
                    await sse_broadcaster.broadcast_event(
                        event_type=SSEEvent.SYSTEM_WARNING,
                        data={
                            "message": f"Starting recovery of {len(stuck_jobs)} stuck {job_type_name}",
                            "job_type": job_type_name,
                            "stuck_count": len(stuck_jobs),
                            "table_name": table_name,
                        },
                        source=SSEEventSource.SYSTEM,
                    )
                except Exception as e:
                    logger.warning(f"Failed to broadcast recovery start event: {e}")

            # Reset stuck jobs to pending
            update_query = f"""
                UPDATE {table_name}
                SET status = %s,
                    error_message = %s,
                    updated_at = %s
                WHERE status = %s
                    AND updated_at < %s
            """

            current_time = utc_now()
            error_message = f"Job recovered from stuck processing state on {current_time.isoformat()} - reset to pending for retry"

            recovered_count = 0
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        update_query,
                        (
                            JobStatus.PENDING.value,
                            error_message,
                            current_time,
                            JobStatus.PROCESSING.value,
                            cutoff_time,
                        ),
                    )
                    recovered_count = cur.rowcount

            # Calculate recovery statistics
            recovery_end_time = utc_now()
            recovery_duration = (
                recovery_end_time - recovery_start_time
            ).total_seconds()

            # Broadcast recovery completion event
            if sse_broadcaster:
                try:
                    await sse_broadcaster.broadcast_event(
                        event_type=SSEEvent.SYSTEM_INFO,
                        data={
                            "message": f"Recovery completed: {recovered_count}/{len(stuck_jobs)} {job_type_name} recovered",
                            "job_type": job_type_name,
                            "recovered_count": recovered_count,
                            "total_stuck": len(stuck_jobs),
                            "table_name": table_name,
                            "recovery_duration": recovery_duration,
                        },
                        source=SSEEventSource.SYSTEM,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to broadcast recovery completion event: {e}"
                    )

            result = {
                "stuck_jobs_found": len(stuck_jobs),
                "stuck_jobs_recovered": recovered_count,
                "stuck_jobs_failed": len(stuck_jobs) - recovered_count,
                "recovery_duration_seconds": recovery_duration,
                "cutoff_time": cutoff_time.isoformat(),
                "recovery_successful": True,
            }

            if recovered_count > 0:
                logger.info(
                    f"✅ Recovered {recovered_count} stuck {job_type_name} in {recovery_duration:.2f}s"
                )
            else:
                logger.warning(
                    f"⚠️ Failed to recover any of the {len(stuck_jobs)} stuck {job_type_name}"
                )

            return result

        except Exception as e:
            recovery_end_time = utc_now()
            recovery_duration = (
                recovery_end_time - recovery_start_time
            ).total_seconds()

            logger.error(f"❌ Recovery failed for {job_type_name}: {e}")

            return {
                "stuck_jobs_found": 0,
                "stuck_jobs_recovered": 0,
                "stuck_jobs_failed": 0,
                "recovery_duration_seconds": recovery_duration,
                "recovery_successful": False,
                "error": str(e),
            }


class SyncRecoveryOperations:
    """
    Sync database operations for job recovery across all job types.

    Provides sync versions of recovery operations for use in worker processes
    and other sync contexts.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance."""
        self.db = db

    def recover_stuck_jobs_for_table(
        self,
        table_name: str,
        max_processing_age_minutes: int = 30,
        job_type_name: str = "jobs",
        sse_broadcaster: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generic recovery method for any job table (sync version).

        Finds jobs stuck in 'processing' status for longer than the specified
        time and resets them to 'pending' status for retry.

        Args:
            table_name: Name of the job table (e.g., 'thumbnail_generation_jobs')
            max_processing_age_minutes: Maximum time a job can be in processing
            job_type_name: Human-readable job type for logging (e.g., 'thumbnail jobs')
            sse_broadcaster: Optional SSE broadcaster for real-time updates

        Returns:
            Dictionary with recovery statistics
        """
        recovery_start_time = utc_now()

        try:
            # Calculate cutoff time for stuck jobs
            cutoff_time = recovery_start_time - timedelta(
                minutes=max_processing_age_minutes
            )

            # Find stuck jobs
            find_query = f"""
                SELECT id, created_at, updated_at
                FROM {table_name}
                WHERE status = %s
                    AND updated_at < %s
                ORDER BY updated_at ASC
            """

            stuck_jobs = []
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(find_query, (JobStatus.PROCESSING.value, cutoff_time))
                    stuck_jobs = cur.fetchall()

            if not stuck_jobs:
                logger.debug(f"🔄 No stuck {job_type_name} found for recovery")
                return {
                    "stuck_jobs_found": 0,
                    "stuck_jobs_recovered": 0,
                    "stuck_jobs_failed": 0,
                    "recovery_duration_seconds": 0.0,
                    "cutoff_time": cutoff_time.isoformat(),
                    "recovery_successful": True,
                }

            logger.info(f"🔄 Found {len(stuck_jobs)} stuck {job_type_name} to recover")

            # Broadcast recovery start event (sync broadcaster)
            if sse_broadcaster:
                try:
                    sse_broadcaster.broadcast_event(
                        event_type=SSEEvent.SYSTEM_WARNING,
                        data={
                            "message": f"Starting recovery of {len(stuck_jobs)} stuck {job_type_name}",
                            "job_type": job_type_name,
                            "stuck_count": len(stuck_jobs),
                            "table_name": table_name,
                        },
                        source=SSEEventSource.SYSTEM,
                    )
                except Exception as e:
                    logger.warning(f"Failed to broadcast recovery start event: {e}")

            # Reset stuck jobs to pending
            update_query = f"""
                UPDATE {table_name}
                SET status = %s,
                    error_message = %s,
                    updated_at = %s
                WHERE status = %s
                    AND updated_at < %s
            """

            current_time = utc_now()
            error_message = f"Job recovered from stuck processing state on {current_time.isoformat()} - reset to pending for retry"

            recovered_count = 0
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        update_query,
                        (
                            JobStatus.PENDING.value,
                            error_message,
                            current_time,
                            JobStatus.PROCESSING.value,
                            cutoff_time,
                        ),
                    )
                    recovered_count = cur.rowcount

            # Calculate recovery statistics
            recovery_end_time = utc_now()
            recovery_duration = (
                recovery_end_time - recovery_start_time
            ).total_seconds()

            # Broadcast recovery completion event (sync broadcaster)
            if sse_broadcaster:
                try:
                    sse_broadcaster.broadcast_event(
                        event_type=SSEEvent.SYSTEM_INFO,
                        data={
                            "message": f"Recovery completed: {recovered_count}/{len(stuck_jobs)} {job_type_name} recovered",
                            "job_type": job_type_name,
                            "recovered_count": recovered_count,
                            "total_stuck": len(stuck_jobs),
                            "table_name": table_name,
                            "recovery_duration": recovery_duration,
                        },
                        source=SSEEventSource.SYSTEM,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to broadcast recovery completion event: {e}"
                    )

            result = {
                "stuck_jobs_found": len(stuck_jobs),
                "stuck_jobs_recovered": recovered_count,
                "stuck_jobs_failed": len(stuck_jobs) - recovered_count,
                "recovery_duration_seconds": recovery_duration,
                "cutoff_time": cutoff_time.isoformat(),
                "recovery_successful": True,
            }

            if recovered_count > 0:
                logger.info(
                    f"✅ Recovered {recovered_count} stuck {job_type_name} in {recovery_duration:.2f}s"
                )
            else:
                logger.warning(
                    f"⚠️ Failed to recover any of the {len(stuck_jobs)} stuck {job_type_name}"
                )

            return result

        except Exception as e:
            recovery_end_time = utc_now()
            recovery_duration = (
                recovery_end_time - recovery_start_time
            ).total_seconds()

            logger.error(f"❌ Recovery failed for {job_type_name}: {e}")

            return {
                "stuck_jobs_found": 0,
                "stuck_jobs_recovered": 0,
                "stuck_jobs_failed": 0,
                "recovery_duration_seconds": recovery_duration,
                "recovery_successful": False,
                "error": str(e),
            }
