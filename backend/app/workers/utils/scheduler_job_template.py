# backend/app/workers/utils/scheduler_job_template.py
"""
Scheduler Job Template

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE: Provides STANDARDIZED job scheduling patterns with consistent configuration

┌─ SchedulerJobTemplate (this file) ───────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ INTERVAL JOBS ─────────────────┐     ┌─ CRON JOBS ──────────────────────────── │
│  │ • Recurring every N seconds     │     │ • Time-based triggers (hourly, daily) │ │
│  │ • Health checks, syncing        │     │ • Weather refresh, automation          │ │
│  │ • Standard configuration        │     │ • Timezone-aware scheduling           │ │
│  └──────────────────────────────────┘     └────────────────────────────────────────┘ │
│                                                                                      │
│  ┌─ IMMEDIATE JOBS ─────────────────────────────────────────────────────────────────┐ │
│  │ • One-time execution (now or delayed)                                           │ │
│  │ • Used by ImmediateJobManager for on-demand operations                          │ │
│  │ • Startup tasks, manual triggers                                                │ │
│  └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            │ (Used by all job managers)
                                            ▼

┌─ TEMPLATE CONSUMERS ────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  • StandardJobManager → Uses for health, weather, automation recurring jobs       │
│  • ImmediateJobManager → Uses for immediate job execution patterns                 │
│  • Future managers → Common patterns available for any new job type                │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

PROBLEM SOLVED:
• Original code had job scheduling logic duplicated in multiple managers
• Inconsistent APScheduler configuration across different job types
• Different error handling patterns for similar job operations
• No standardized approach for job registry management

DESIGN PATTERN: Template Method Pattern
• Common configuration applied automatically (max_instances, coalesce, misfire_grace_time)
• Consistent error handling and logging across all job types
• Registry management handled uniformly
• Extensible for new job patterns without code duplication

CONFIGURATION STANDARDS:
• max_instances: SCHEDULER_MAX_INSTANCES (prevents job overlap)
• coalesce: True (combines missed executions)
• misfire_grace_time: 30 seconds (tolerance for late execution)
• Consistent job removal before re-adding (prevents conflicts)
"""

import asyncio
from typing import Dict, Any, Callable
from loguru import logger

from .scheduler_time_utils import SchedulerTimeUtils
from ...constants import SCHEDULER_MAX_INSTANCES


class SchedulerJobTemplate:
    """Template for common job scheduling patterns with consistent configuration."""

    def __init__(
        self, scheduler, job_registry: Dict[str, Any], time_utils: SchedulerTimeUtils
    ):
        """Initialize with scheduler components."""
        self.scheduler = scheduler
        self.job_registry = job_registry
        self.time_utils = time_utils

    def schedule_interval_job(
        self, job_id: str, func: Callable, interval_seconds: int, **kwargs
    ) -> bool:
        """Schedule an interval-based job with standard configuration."""
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                del self.job_registry[job_id]

            # Set default values
            kwargs.setdefault("max_instances", SCHEDULER_MAX_INSTANCES)
            kwargs.setdefault("coalesce", True)
            kwargs.setdefault("misfire_grace_time", 30)

            job = self.scheduler.add_job(
                func=func,
                trigger="interval",
                seconds=interval_seconds,
                id=job_id,
                **kwargs,
            )

            if job:
                self.job_registry[job_id] = job
                logger.debug(
                    f"Scheduled interval job {job_id} (every {interval_seconds}s)"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to schedule interval job {job_id}: {e}")
            return False

    def schedule_cron_job(self, job_id: str, func: Callable, **cron_kwargs) -> bool:
        """Schedule a cron-based job with standard configuration."""
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                del self.job_registry[job_id]

            # Set default values
            job_kwargs = {
                "max_instances": SCHEDULER_MAX_INSTANCES,
                "coalesce": True,
                "misfire_grace_time": 30,
            }

            job = self.scheduler.add_job(
                func=func, trigger="cron", id=job_id, **cron_kwargs, **job_kwargs
            )

            if job:
                self.job_registry[job_id] = job
                logger.debug(f"Scheduled cron job {job_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to schedule cron job {job_id}: {e}")
            return False

    def schedule_immediate_job(
        self, job_id: str, wrapper_func: Callable, delay_seconds: int = 0
    ) -> bool:
        """Schedule an immediate job with optional delay."""
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                self.scheduler.remove_job(job_id)
                del self.job_registry[job_id]

            if delay_seconds > 0:
                # Use date trigger for delayed execution
                import datetime

                run_date = datetime.datetime.now() + datetime.timedelta(
                    seconds=delay_seconds
                )

                job = self.scheduler.add_job(
                    func=wrapper_func,
                    trigger="date",
                    run_date=run_date,
                    id=job_id,
                    max_instances=1,
                )
            else:
                # Use date trigger for immediate execution
                job = self.scheduler.add_job(
                    func=wrapper_func,
                    trigger="date",
                    id=job_id,
                    max_instances=1,
                )

            if job:
                self.job_registry[job_id] = job
                logger.debug(
                    f"Scheduled immediate job {job_id}"
                    + (f" (delay: {delay_seconds}s)" if delay_seconds > 0 else "")
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to schedule immediate job {job_id}: {e}")
            return False
