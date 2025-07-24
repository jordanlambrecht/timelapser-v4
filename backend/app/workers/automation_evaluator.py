# backend/app/workers/automation_evaluator.py
"""
Automation Evaluator

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE: Implements SCHEDULER-CENTRIC automation triggers for intelligent video generation

┌─ AutomationEvaluator (this file) ────────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ MILESTONE AUTOMATION ───────────┐     ┌─ SCHEDULED AUTOMATION ────────────────── │
│  │ • Image count-based triggers     │     │ • Daily scheduled generation           │ │
│  │ • Per-timelapse configuration     │     │ • Time window evaluation               │ │
│  │ • Duplicate detection & prevention│     │ • Timezone-aware scheduling           │ │
│  └───────────────────────────────────┘     └────────────────────────────────────────┘ │
│                                                                                      │
│  ┌─ SCHEDULER AUTHORITY ────────────────────────────────────────────────────────────┐ │
│  │ • ALL timing decisions flow through this evaluator                              │ │
│  │ • Workers trust scheduler decisions (no redundant validation)                   │ │
│  │ • Centralized automation logic prevents conflicts and duplication              │ │
│  └──────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                   ┌────────────────────────┼────────────────────────┐
                   ▼                        ▼                        ▼

┌─ USES UTILITIES ──────┐   ┌─ COORDINATES WITH ────┐   ┌─ TRIGGERS JOBS ───────┐
│ • SchedulerTimeUtils   │   │ • TimelapseOperations  │   │ • ImmediateJobManager │
│ • Database operations  │   │ • VideoOperations      │   │ • Video generation    │
│ • SSE event creation   │   │ • Settings service     │   │ • SSE notifications   │
└────────────────────────┘   └────────────────────────┘   └───────────────────────┘

RELATIONSHIP TO SCHEDULER ECOSYSTEM:
• PARENT: SchedulerWorker creates and injects schedule_immediate_video_func
• SIBLINGS: StandardJobManager (calls this), ImmediateJobManager (executes results)
• CHILDREN: None - this is a decision-making component that triggers actions

SCHEDULER-CENTRIC DESIGN PRINCIPLES:
🎯 AUTHORITY: This component makes ALL automation timing decisions
🎯 TRUST: Workers execute decisions without re-validation
🎯 CENTRALIZATION: No distributed automation logic across multiple components
🎯 CONSISTENCY: All automation triggers follow the same evaluation patterns

AUTOMATION EVALUATION CYCLE:
1. StandardJobManager calls evaluate_automation_triggers() every 5 minutes
2. AutomationEvaluator queries all active timelapses with automation enabled
3. For each timelapse, evaluates milestone and scheduled conditions
4. If conditions are met, calls ImmediateJobManager to queue video generation
5. Emits SSE events for real-time UI updates
6. Returns job IDs for monitoring and logging

PROBLEM SOLVED:
• Original code had automation logic scattered across multiple workers
• No single source of truth for when automated videos should be generated
• Race conditions between different automation triggers
• Inconsistent automation evaluation patterns
"""

import time
from typing import Dict, Optional, List, Callable
from loguru import logger

from .utils import SchedulerTimeUtils
from ..database.core import SyncDatabase
from ..database.timelapse_operations import SyncTimelapseOperations
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..constants import JOB_PRIORITY, EVENT_VIDEO_JOB_QUEUED
from ..enums import SSEPriority


class AutomationEvaluator:
    """Evaluates and triggers automation for milestone and scheduled video generation."""

    def __init__(
        self,
        db: SyncDatabase,
        time_utils: SchedulerTimeUtils,
        logger_prefix: str = "AutomationEvaluator",
    ):
        """Initialize automation evaluator."""
        self.db = db
        self.time_utils = time_utils
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.sse_ops = SyncSSEEventsOperations(db)
        self.logger_prefix = logger_prefix

        # External function references (injected by parent)
        self.schedule_immediate_video_func: Optional[Callable] = None

    def log_info(self, message: str) -> None:
        """Log info message with prefix."""
        logger.info(f"{self.logger_prefix}: {message}")

    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message with prefix."""
        if exception:
            logger.error(f"{self.logger_prefix}: {message}: {exception}")
        else:
            logger.error(f"{self.logger_prefix}: {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message with prefix."""
        logger.warning(f"{self.logger_prefix}: {message}")

    def log_debug(self, message: str) -> None:
        """Log debug message with prefix."""
        logger.debug(f"{self.logger_prefix}: {message}")

    def evaluate_automation_triggers(self) -> Dict[str, List[str]]:
        """
        🎯 SCHEDULER-CENTRIC: Evaluate automation triggers for milestone and scheduled videos.

        This method centralizes all timing decisions for automated video generation,
        enforcing the scheduler authority pattern.

        Returns:
            Dictionary with job IDs for milestone and scheduled jobs created
        """
        result = {"milestone_jobs": [], "scheduled_jobs": []}

        try:
            # Evaluate milestone automation triggers
            milestone_jobs = self._evaluate_milestone_triggers()
            result["milestone_jobs"] = milestone_jobs

            # Evaluate scheduled automation triggers
            scheduled_jobs = self._evaluate_scheduled_triggers()
            result["scheduled_jobs"] = scheduled_jobs

            total_jobs = len(milestone_jobs) + len(scheduled_jobs)
            if total_jobs > 0:
                self.log_info(
                    f"🎯 Automation evaluation complete: {len(milestone_jobs)} milestone, "
                    f"{len(scheduled_jobs)} scheduled jobs created"
                )
            else:
                self.log_debug(
                    "🎯 Automation evaluation complete: No triggers activated"
                )

        except Exception as e:
            self.log_error("Error evaluating automation triggers", e)

        return result

    def _evaluate_milestone_triggers(self) -> List[str]:
        """
        Evaluate milestone automation triggers for all active timelapses.

        Returns:
            List of job IDs created for milestone videos
        """
        if not self.schedule_immediate_video_func:
            self.log_warning("No video scheduling function configured")
            return []

        try:
            job_ids = []

            # Get all active timelapses with milestone automation enabled
            active_timelapses = (
                self.timelapse_ops.get_active_timelapses_with_milestone_automation()
            )

            for timelapse in active_timelapses:
                try:
                    # Check if milestone threshold reached
                    if self._should_create_milestone_video_authority(timelapse):
                        # 🎯 SCHEDULER AUTHORITY: Command immediate video generation
                        success = self.schedule_immediate_video_func(
                            timelapse_id=timelapse.id,
                            video_settings={"trigger_type": "milestone"},
                            priority=JOB_PRIORITY.MEDIUM,
                        )

                        if success:
                            job_id = f"milestone_{timelapse.id}_{int(time.time())}"
                            job_ids.append(job_id)
                            self.log_info(
                                f"✅ Scheduler authority: Created milestone video for timelapse {timelapse.id}"
                            )

                            # Emit SSE event for real-time updates
                            try:
                                self.sse_ops.create_event(
                                    event_type=EVENT_VIDEO_JOB_QUEUED,
                                    event_data={
                                        "timelapse_id": timelapse.id,
                                        "trigger_type": "milestone",
                                        "priority": JOB_PRIORITY.MEDIUM,
                                        "job_id": job_id,
                                    },
                                    priority=SSEPriority.NORMAL,
                                    source="scheduler_worker",
                                )
                            except Exception as sse_error:
                                self.log_warning(
                                    f"Failed to emit SSE event for milestone video job: {sse_error}"
                                )
                        else:
                            self.log_warning(
                                f"❌ Failed to schedule milestone video for timelapse {timelapse.id}"
                            )

                except Exception as e:
                    self.log_error(
                        f"Error evaluating milestone trigger for timelapse {timelapse.id}",
                        e,
                    )

            return job_ids

        except Exception as e:
            self.log_error("Error evaluating milestone automation triggers", e)
            return []

    def _evaluate_scheduled_triggers(self) -> List[str]:
        """
        Evaluate scheduled automation triggers for all active timelapses.

        Returns:
            List of job IDs created for scheduled videos
        """
        if not self.schedule_immediate_video_func:
            self.log_warning("No video scheduling function configured")
            return []

        try:
            job_ids = []

            # Get all active timelapses with scheduled automation enabled
            active_timelapses = (
                self.timelapse_ops.get_active_timelapses_with_scheduled_automation()
            )

            for timelapse in active_timelapses:
                try:
                    # Check if scheduled video is due
                    if self._should_create_scheduled_video_authority(timelapse):
                        # 🎯 SCHEDULER AUTHORITY: Command immediate video generation
                        success = self.schedule_immediate_video_func(
                            timelapse_id=timelapse.id,
                            video_settings={"trigger_type": "scheduled"},
                            priority=JOB_PRIORITY.LOW,
                        )

                        if success:
                            job_id = f"scheduled_{timelapse.id}_{int(time.time())}"
                            job_ids.append(job_id)
                            self.log_info(
                                f"✅ Scheduler authority: Created scheduled video for timelapse {timelapse.id}"
                            )

                            # Emit SSE event for real-time updates
                            try:
                                self.sse_ops.create_event(
                                    event_type=EVENT_VIDEO_JOB_QUEUED,
                                    event_data={
                                        "timelapse_id": timelapse.id,
                                        "trigger_type": "scheduled",
                                        "priority": JOB_PRIORITY.LOW,
                                        "job_id": job_id,
                                    },
                                    priority=SSEPriority.NORMAL,
                                    source="scheduler_worker",
                                )
                            except Exception as sse_error:
                                self.log_warning(
                                    f"Failed to emit SSE event for scheduled video job: {sse_error}"
                                )
                        else:
                            self.log_warning(
                                f"❌ Failed to schedule scheduled video for timelapse {timelapse.id}"
                            )

                except Exception as e:
                    self.log_error(
                        f"Error evaluating scheduled trigger for timelapse {timelapse.id}",
                        e,
                    )

            return job_ids

        except Exception as e:
            self.log_error("Error evaluating scheduled automation triggers", e)
            return []

    def _should_create_milestone_video_authority(self, timelapse) -> bool:
        """
        🎯 SCHEDULER AUTHORITY: Check if milestone video should be created.

        Args:
            timelapse: Timelapse object with milestone automation settings

        Returns:
            bool: True if scheduler authority determines milestone video should be created
        """
        try:
            # Check if milestone automation is enabled
            if not timelapse.milestone_config:
                return False

            # Parse milestone configuration
            try:
                milestone_interval = timelapse.milestone_config.get("interval", 0)
            except (AttributeError, TypeError):
                # Handle case where milestone_config is a string or other type
                return False

            if milestone_interval <= 0:
                return False

            # Get current image count
            current_count = self.timelapse_ops.get_timelapse_image_count(timelapse.id)

            # Check if we've reached a milestone
            if current_count > 0 and current_count % milestone_interval == 0:
                # Check if we already generated a video for this milestone
                try:
                    # Import video operations for milestone checking
                    from ..database.video_operations import SyncVideoOperations

                    video_ops = SyncVideoOperations(self.db)

                    last_milestone_video = video_ops.get_last_milestone_video(
                        timelapse.id
                    )
                    if last_milestone_video:
                        last_milestone_count = getattr(
                            last_milestone_video, "image_count", 0
                        )
                        if last_milestone_count >= current_count:
                            return False  # Already generated video for this milestone
                except Exception as e:
                    self.log_warning(
                        f"Could not check last milestone video for timelapse {timelapse.id}: {e}"
                    )
                    # Continue with milestone creation if we can't check (safe approach)

                self.log_debug(
                    f"🎯 Milestone trigger: Scheduler authority approves timelapse {timelapse.id} at {current_count} images"
                )
                return True

            return False

        except Exception as e:
            self.log_error(
                f"Error checking milestone trigger for timelapse {timelapse.id}", e
            )
            return False

    def _should_create_scheduled_video_authority(self, timelapse) -> bool:
        """
        🎯 SCHEDULER AUTHORITY: Check if scheduled video should be created.

        Args:
            timelapse: Timelapse object with scheduled automation settings

        Returns:
            bool: True if scheduler authority determines scheduled video should be created
        """
        try:
            # Check if scheduled automation is enabled
            if not timelapse.generation_schedule:
                return False

            # Parse generation schedule
            try:
                schedule_type = timelapse.generation_schedule.get("type")
                schedule_time = timelapse.generation_schedule.get("time")
            except (AttributeError, TypeError):
                # Handle case where generation_schedule is a string or other type
                return False

            if schedule_type != "daily" or not schedule_time:
                return False

            # Get current timezone-aware time
            current_time = self.time_utils.get_current_time()

            # Check if we already generated a video today
            try:
                # Import video operations for scheduled checking
                from ..database.video_operations import SyncVideoOperations

                video_ops = SyncVideoOperations(self.db)

                last_scheduled_video = video_ops.get_last_scheduled_video(timelapse.id)
                if last_scheduled_video:
                    last_video_date = last_scheduled_video.created_at.date()
                    if last_video_date >= current_time.date():
                        return False  # Already generated video today
            except Exception as e:
                self.log_warning(
                    f"Could not check last scheduled video for timelapse {timelapse.id}: {e}"
                )
                # Continue with scheduled creation if we can't check (safe approach)

            # Check if current time matches schedule
            try:
                scheduled_hour, scheduled_minute = map(int, schedule_time.split(":"))
                if (
                    current_time.hour == scheduled_hour
                    and current_time.minute >= scheduled_minute
                    and current_time.minute < scheduled_minute + 5
                ):  # 5-minute window
                    self.log_debug(
                        f"🎯 Scheduled trigger: Scheduler authority approves timelapse {timelapse.id} daily at {schedule_time}"
                    )
                    return True
            except Exception as e:
                self.log_error(
                    f"Error parsing schedule time '{schedule_time}' for timelapse {timelapse.id}: {e}"
                )
                return False

            # Note: Weekly schedule support can be added here in the future if needed

            return False

        except Exception as e:
            self.log_error(
                f"Error checking scheduled trigger for timelapse {timelapse.id}", e
            )
            return False
