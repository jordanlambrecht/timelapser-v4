# backend/app/services/scheduling/__init__.py
"""
Scheduling Services Module

This module contains all scheduling-related services organized for clarity and
consistency. These services handle different aspects of the timing subsystem:

- capture_timing_service: Mathematical timing calculations for captures
- scheduler_authority_service: Central scheduling authority interface
- time_window_service: Camera operational time window management
- job_queue_service: Centralized background job queue management

All services follow the composition pattern and provide both async and sync
interfaces where appropriate.
"""

from .capture_timing_service import SchedulingService, SyncSchedulingService
from .job_queue_service import JobQueueService, SyncJobQueueService
from .scheduler_authority_service import SchedulerService
from .time_window_service import SyncTimeWindowService, TimeWindowService

# Export all services
__all__ = [
    # Capture timing services (renamed for clarity)
    "SchedulingService",
    "SyncSchedulingService",
    # Scheduler authority service
    "SchedulerService",
    # Time window services
    "TimeWindowService",
    "SyncTimeWindowService",
    # Job queue services
    "JobQueueService",
    "SyncJobQueueService",
]

# Backwards compatibility aliases for existing imports
# These maintain compatibility during the transition period
CaptureTimingService = SchedulingService
SyncCaptureTimingService = SyncSchedulingService
SchedulerAuthorityService = SchedulerService
