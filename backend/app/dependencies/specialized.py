# backend/app/dependencies/specialized.py
"""
Specialized service dependencies that don't fit into other categories.

These are typically database operations or other specialized services.
"""

from typing import TYPE_CHECKING

from ..database import async_db

if TYPE_CHECKING:
    from ..database.scheduled_job_operations import ScheduledJobOperations


# Scheduled Job Operations Factory
async def get_scheduled_job_operations() -> "ScheduledJobOperations":
    """Get ScheduledJobOperations with async database dependency injection."""
    from ..database.scheduled_job_operations import ScheduledJobOperations

    return ScheduledJobOperations(async_db)
