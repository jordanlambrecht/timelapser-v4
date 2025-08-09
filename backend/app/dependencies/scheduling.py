# backend/app/dependencies/scheduling.py
"""
Scheduling service dependencies using the factory pattern.

These services handle timing, scheduling, and job queue management
for the timelapse capture system.
"""

from typing import TYPE_CHECKING

from ..database import async_db, sync_db
from .base import AsyncServiceFactory, SyncServiceFactory
from .registry import get_scheduler_worker

if TYPE_CHECKING:
    from ..services.scheduling.capture_timing_service import (
        CaptureTimingService,
        SyncCaptureTimingService,
    )
    from ..services.scheduling.job_queue_service import (
        JobQueueService,
        SyncJobQueueService,
    )
    from ..services.scheduling.scheduler_authority_service import SchedulerService
    from ..services.scheduling.time_window_service import (
        SyncTimeWindowService,
        TimeWindowService,
    )


# Async Time Window Service Factory (Singleton)
async def _create_time_window_service():
    """Factory for creating TimeWindowService."""
    from ..services.scheduling.time_window_service import TimeWindowService
    from .async_services import get_settings_service

    settings_service = await get_settings_service()
    return TimeWindowService(async_db, settings_service)


from .registry import get_async_singleton_service, register_singleton_factory
register_singleton_factory("async_time_window_service", _create_time_window_service)


async def get_time_window_service() -> "TimeWindowService":
    """Get TimeWindowService singleton with async database dependency injection."""
    return await get_async_singleton_service("async_time_window_service")


# Async Scheduling Service Factory (Singleton)
async def _create_scheduling_service():
    """Factory for creating CaptureTimingService."""
    from ..services.scheduling.capture_timing_service import CaptureTimingService
    from .async_services import get_settings_service

    time_window_service = await get_time_window_service()
    settings_service = await get_settings_service()
    return CaptureTimingService(async_db, time_window_service, settings_service)


register_singleton_factory("async_capture_timing_service", _create_scheduling_service)


async def get_scheduling_service() -> "CaptureTimingService":
    """Get CaptureTimingService singleton with async database dependency injection."""
    return await get_async_singleton_service("async_capture_timing_service")


# Async Job Queue Service Factory
async def get_job_queue_service() -> "JobQueueService":
    """Get JobQueueService with async database dependency injection."""
    factory = AsyncServiceFactory(
        service_module="app.services.scheduling.job_queue_service",
        service_class="JobQueueService",
        needs_settings=False,
    )
    return await factory.get_service()


# Sync Time Window Service Factory
def get_sync_time_window_service() -> "SyncTimeWindowService":
    """Get SyncTimeWindowService with sync database dependency injection."""
    factory = SyncServiceFactory(
        service_module="app.services.scheduling.time_window_service",
        service_class="SyncTimeWindowService",
    )
    return factory.get_service()


# Sync Scheduling Service Factory
def get_sync_scheduling_service() -> "SyncCaptureTimingService":
    """Get SyncCaptureTimingService with sync database dependency injection."""
    from ..services.scheduling.capture_timing_service import SyncCaptureTimingService
    from .sync_services import get_sync_settings_service

    sync_time_window_service = get_sync_time_window_service()
    sync_settings_service = get_sync_settings_service()
    return SyncCaptureTimingService(
        sync_db, async_db, sync_time_window_service, sync_settings_service
    )


# Sync Job Queue Service Factory
def get_sync_job_queue_service() -> "SyncJobQueueService":
    """Get SyncJobQueueService with sync database dependency injection."""
    factory = SyncServiceFactory(
        service_module="app.services.scheduling.job_queue_service",
        service_class="SyncJobQueueService",
        needs_settings=False,
    )
    return factory.get_service()


# Scheduler Authority Service Factory (Singleton)
async def _create_scheduler_service():
    """Factory for creating SchedulerService."""
    from ..services.scheduling.scheduler_authority_service import SchedulerService

    scheduler_worker = get_scheduler_worker()
    if scheduler_worker is None:
        raise RuntimeError("SchedulerWorker not initialized")

    return SchedulerService(scheduler_worker)


register_singleton_factory("scheduler_service", _create_scheduler_service)


async def get_scheduler_service() -> "SchedulerService":
    """
    Get SchedulerService singleton with dependency injection.

    This service coordinates the timing and execution of scheduled tasks.
    It uses the scheduler worker for task execution.
    """
    return await get_async_singleton_service("scheduler_service")
