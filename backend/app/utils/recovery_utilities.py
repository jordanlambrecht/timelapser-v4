# backend/app/utils/recovery_utilities.py
"""
Recovery Utilities - Pure utility functions for recovery operations.

This module provides pure utility functions for recovery operations
without any database dependencies, following CLAUDE.md architecture guidelines.

All database operations have been moved to recovery_operations.py in the database layer.
"""

from datetime import timedelta
from typing import Any, Dict


def calculate_recovery_cutoff_time(
    recovery_start_time, max_processing_age_minutes: int
):
    """
    Calculate cutoff time for identifying stuck jobs.

    Args:
        recovery_start_time: Start time of recovery operation
        max_processing_age_minutes: Maximum age in minutes for processing jobs

    Returns:
        Cutoff datetime - jobs updated before this time are considered stuck
    """
    return recovery_start_time - timedelta(minutes=max_processing_age_minutes)


def create_recovery_error_message(recovery_time) -> str:
    """
    Create standardized error message for recovered jobs.

    Args:
        recovery_time: Time when recovery occurred

    Returns:
        Formatted error message string
    """
    return f"Job recovered from stuck processing state on {recovery_time.isoformat()} - reset to pending for retry"


def calculate_recovery_statistics(
    recovery_start_time,
    recovery_end_time,
    stuck_jobs_found: int,
    stuck_jobs_recovered: int,
    cutoff_time,
) -> Dict[str, Any]:
    """
    Calculate comprehensive recovery statistics.

    Args:
        recovery_start_time: When recovery started
        recovery_end_time: When recovery completed
        stuck_jobs_found: Number of stuck jobs found
        stuck_jobs_recovered: Number of jobs successfully recovered
        cutoff_time: Cutoff time used for stuck job identification

    Returns:
        Dictionary with recovery statistics
    """
    recovery_duration = (recovery_end_time - recovery_start_time).total_seconds()

    return {
        "stuck_jobs_found": stuck_jobs_found,
        "stuck_jobs_recovered": stuck_jobs_recovered,
        "stuck_jobs_failed": stuck_jobs_found - stuck_jobs_recovered,
        "recovery_duration_seconds": recovery_duration,
        "cutoff_time": cutoff_time.isoformat(),
        "recovery_successful": True,
    }


def create_failed_recovery_statistics(
    recovery_start_time,
    recovery_end_time,
    error: str,
) -> Dict[str, Any]:
    """
    Create statistics for failed recovery operations.

    Args:
        recovery_start_time: When recovery started
        recovery_end_time: When recovery failed
        error: Error message

    Returns:
        Dictionary with failure statistics
    """
    recovery_duration = (recovery_end_time - recovery_start_time).total_seconds()

    return {
        "stuck_jobs_found": 0,
        "stuck_jobs_recovered": 0,
        "stuck_jobs_failed": 0,
        "recovery_duration_seconds": recovery_duration,
        "recovery_successful": False,
        "error": error,
    }


def create_empty_recovery_statistics(cutoff_time) -> Dict[str, Any]:
    """
    Create statistics when no stuck jobs are found.

    Args:
        cutoff_time: Cutoff time used for stuck job identification

    Returns:
        Dictionary with empty recovery statistics
    """
    return {
        "stuck_jobs_found": 0,
        "stuck_jobs_recovered": 0,
        "stuck_jobs_failed": 0,
        "recovery_duration_seconds": 0.0,
        "cutoff_time": cutoff_time.isoformat(),
        "recovery_successful": True,
    }


def format_recovery_log_message(
    recovered_count: int,
    total_stuck: int,
    job_type_name: str,
    recovery_duration: float,
) -> str:
    """
    Format log message for recovery completion.

    Args:
        recovered_count: Number of jobs recovered
        total_stuck: Total number of stuck jobs found
        job_type_name: Human-readable job type name
        recovery_duration: Duration of recovery in seconds

    Returns:
        Formatted log message
    """
    if recovered_count > 0:
        return f"✅ Recovered {recovered_count} stuck {job_type_name} in {recovery_duration:.2f}s"
    else:
        return f"⚠️ Failed to recover any of the {total_stuck} stuck {job_type_name}"


def validate_recovery_parameters(
    table_name: str,
    max_processing_age_minutes: int,
    job_type_name: str,
) -> None:
    """
    Validate parameters for recovery operations.

    Args:
        table_name: Database table name
        max_processing_age_minutes: Maximum processing age
        job_type_name: Job type name for logging

    Raises:
        ValueError: If parameters are invalid
    """
    if not table_name or not isinstance(table_name, str):
        raise ValueError("table_name must be a non-empty string")

    if (
        not isinstance(max_processing_age_minutes, int)
        or max_processing_age_minutes <= 0
    ):
        raise ValueError("max_processing_age_minutes must be a positive integer")

    if not job_type_name or not isinstance(job_type_name, str):
        raise ValueError("job_type_name must be a non-empty string")


def should_broadcast_recovery_event(sse_broadcaster) -> bool:
    """
    Check if recovery events should be broadcast.

    Args:
        sse_broadcaster: SSE broadcaster instance (can be None)

    Returns:
        True if events should be broadcast, False otherwise
    """
    return sse_broadcaster is not None


def log_recovery_start(job_type_name: str, stuck_count: int) -> None:
    """
    Log recovery start message.

    Args:
        job_type_name: Human-readable job type name
        stuck_count: Number of stuck jobs found
    """
    if stuck_count > 0:
        pass
    else:
        pass


def log_recovery_completion(
    recovered_count: int,
    total_stuck: int,
    job_type_name: str,
    recovery_duration: float,
) -> None:
    """
    Log recovery completion message.

    Args:
        recovered_count: Number of jobs recovered
        total_stuck: Total number of stuck jobs found
        job_type_name: Human-readable job type name
        recovery_duration: Duration of recovery in seconds
    """
    message = format_recovery_log_message(
        recovered_count, total_stuck, job_type_name, recovery_duration
    )

    if recovered_count > 0:
        print(message)  # Log the recovery message for successful recovery
    else:
        print(message)  # Log the recovery message for failed recovery


def log_recovery_error(job_type_name: str, error: Exception) -> None:
    """
    Log recovery error message.

    Args:
        job_type_name: Human-readable job type name
        error: Exception that occurred
    """
    pass
