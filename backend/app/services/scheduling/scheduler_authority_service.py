# backend/app/services/scheduling/scheduler_authority_service.py
"""
Scheduler Authority Service - Async Interface for Scheduler Authority

Provides async API layer over SchedulerWorker to enforce the scheduler-centric model.
This service acts as the single point of authority for ALL timing decisions in the system.

Core Philosophy: "Scheduler should say 'jump' and pipelines should say 'how high'"

Architecture:
- Wraps SchedulerWorker with async interface
- Provides clean API for immediate scheduling operations
- Maintains scheduler supremacy over all timing decisions
- Supports both regular intervals and one-time immediate operations
"""

import asyncio
from typing import Any, Dict, Optional

from ...database.core import AsyncDatabase
from ...enums import LoggerName, SSEPriority
from ...services.logger import get_service_logger
from ...services.settings_service import SettingsService
from ...workers.scheduler_worker import SchedulerWorker
from .capture_timing_service import CaptureTimingService

logger = get_service_logger(LoggerName.SCHEDULING_SERVICE)


class SchedulerAuthorityService:
    """
    Async interface for scheduler authority operations.

    This service provides a clean async API over the SchedulerWorker while
    maintaining the scheduler-centric philosophy where all timing decisions
    must go through the scheduler authority.

    Key Responsibilities:
    - Immediate capture scheduling (bypassing workers)
    - Immediate video generation scheduling
    - Immediate overlay generation scheduling
    - Immediate thumbnail generation scheduling
    - Scheduler status monitoring and health checks
    - Job lifecycle management
    """

    def __init__(
        self,
        scheduler_worker: SchedulerWorker,
        async_db: Optional[AsyncDatabase] = None,
        settings_service: Optional[SettingsService] = None,
        timing_service: Optional[CaptureTimingService] = None,
    ):
        """
        Initialize SchedulerAuthorityService with dependencies.

        Args:
            scheduler_worker: The underlying SchedulerWorker instance
            async_db: Optional async database for direct operations
            settings_service: Optional async settings service
            timing_service: Optional capture timing service
        """
        self.scheduler_worker = scheduler_worker
        self.async_db = async_db
        self.settings_service = settings_service
        self.timing_service = timing_service

        logger.info("🕐 SchedulerAuthorityService initialized with scheduler authority")

    async def schedule_immediate_capture(
        self, camera_id: int, timelapse_id: int, priority: str = SSEPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Schedule immediate capture through the scheduler authority.

        This is the primary entry point for all immediate capture requests.
        Enforces scheduler-centric model where NO captures bypass scheduler validation.

        Args:
            camera_id: Camera to capture from
            timelapse_id: Timelapse context for capture
            priority: Priority level (high, normal, low)

        Returns:
            Dict containing success status and scheduling details
        """
        try:
            logger.info(
                f"⚡ SchedulerAuthorityService: Immediate capture request for camera {camera_id}, timelapse {timelapse_id}"
            )

            # Delegate to scheduler worker async method directly
            success = await self.scheduler_worker.schedule_immediate_capture(
                camera_id,
                timelapse_id,
                priority,
            )

            if success:
                return {
                    "success": True,
                    "message": f"Immediate capture scheduled for camera {camera_id}, timelapse {timelapse_id}",
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "priority": priority,
                    "scheduled_via": "scheduler_authority",
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to schedule immediate capture",
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "priority": priority,
                }

        except Exception as e:
            logger.error(f"Error in SchedulerAuthorityService immediate capture: {e}")
            return {
                "success": False,
                "error": str(e),
                "camera_id": camera_id,
                "timelapse_id": timelapse_id,
                "priority": priority,
            }

    async def schedule_immediate_video_generation(
        self,
        timelapse_id: int,
        video_settings: Optional[Dict] = None,
        priority: str = SSEPriority.NORMAL,
    ) -> Dict[str, Any]:
        """
        Schedule immediate video generation through the scheduler authority.

        Args:
            timelapse_id: Timelapse to generate video for
            video_settings: Optional video generation settings override
            priority: Priority level (high, normal, low)

        Returns:
            Dict containing success status and scheduling details
        """
        try:
            logger.info(
                f"⚡ SchedulerAuthorityService: Immediate video generation request for timelapse {timelapse_id}"
            )

            # Delegate to scheduler worker async method directly
            success = await self.scheduler_worker.schedule_immediate_video_generation(
                timelapse_id,
                video_settings,
                priority,
            )

            if success:
                return {
                    "success": True,
                    "message": f"Immediate video generation scheduled for timelapse {timelapse_id}",
                    "timelapse_id": timelapse_id,
                    "priority": priority,
                    "video_settings": video_settings,
                    "scheduled_via": "scheduler_authority",
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to schedule immediate video generation",
                    "timelapse_id": timelapse_id,
                    "priority": priority,
                }

        except Exception as e:
            logger.error(
                f"Error in SchedulerAuthorityService immediate video generation: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "timelapse_id": timelapse_id,
                "priority": priority,
            }

    async def schedule_immediate_overlay_generation(
        self, image_id: int, priority: str = SSEPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Schedule immediate overlay generation through the scheduler authority.

        Args:
            image_id: Image to generate overlay for
            priority: Priority level (high, normal, low)

        Returns:
            Dict containing success status and scheduling details
        """
        try:
            logger.info(
                f"⚡ SchedulerAuthorityService: Immediate overlay generation request for image {image_id}"
            )

            # Delegate to scheduler worker async method directly
            success = await self.scheduler_worker.schedule_immediate_overlay_generation(
                image_id,
                priority,
            )

            if success:
                return {
                    "success": True,
                    "message": f"Immediate overlay generation scheduled for image {image_id}",
                    "image_id": image_id,
                    "priority": priority,
                    "scheduled_via": "scheduler_authority",
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to schedule immediate overlay generation",
                    "image_id": image_id,
                    "priority": priority,
                }

        except Exception as e:
            logger.error(
                f"Error in SchedulerAuthorityService immediate overlay generation: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "image_id": image_id,
                "priority": priority,
            }

    async def schedule_immediate_thumbnail_generation(
        self, image_id: int, priority: str = SSEPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Schedule immediate thumbnail generation through the scheduler authority.

        Args:
            image_id: Image to generate thumbnails for
            priority: Priority level (high, normal, low)

        Returns:
            Dict containing success status and scheduling details
        """
        try:
            logger.info(
                f"⚡ SchedulerAuthorityService: Immediate thumbnail generation request for image {image_id}"
            )

            # Delegate to scheduler worker async method directly
            success = (
                await self.scheduler_worker.schedule_immediate_thumbnail_generation(
                    image_id,
                    priority,
                )
            )

            if success:
                return {
                    "success": True,
                    "message": f"Immediate thumbnail generation scheduled for image {image_id}",
                    "image_id": image_id,
                    "priority": priority,
                    "scheduled_via": "scheduler_authority",
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to schedule immediate thumbnail generation",
                    "image_id": image_id,
                    "priority": priority,
                }

        except Exception as e:
            logger.error(
                f"Error in SchedulerAuthorityService immediate thumbnail generation: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "image_id": image_id,
                "priority": priority,
            }

    async def schedule_immediate_video_cancellation(
        self, video_id: int, job_id: str, priority: str = SSEPriority.CRITICAL
    ) -> Dict[str, Any]:
        """
        Schedule immediate video generation cancellation through the scheduler authority.

        This method cancels video generation by removing the job from the scheduler.
        Video cancellation is treated as a high-priority operation to ensure
        immediate response to user requests.

        Args:
            video_id: Video ID to cancel generation for
            job_id: APScheduler job ID associated with the video generation
            priority: Priority level (defaults to HIGH for cancellations)

        Returns:
            Dict containing success status and cancellation details
        """
        try:
            logger.info(
                f"⚡ SchedulerAuthorityService: Video generation cancellation request for video {video_id}, job {job_id}"
            )

            # Use scheduler worker's remove_job method to cancel the video generation
            # This will remove the job from APScheduler and the job registry
            await asyncio.get_event_loop().run_in_executor(
                None, self.scheduler_worker.remove_job, job_id
            )

            logger.info(f"Video generation job {job_id} cancelled for video {video_id}")

            return {
                "success": True,
                "message": f"Video generation cancelled for video {video_id}",
                "video_id": video_id,
                "job_id": job_id,
                "priority": priority,
                "scheduled_via": "scheduler_authority",
                "action": "job_cancelled",
            }

        except Exception as e:
            logger.error(f"Error in SchedulerAuthorityService video cancellation: {e}")
            return {
                "success": False,
                "error": str(e),
                "video_id": video_id,
                "job_id": job_id,
                "priority": priority,
            }

    async def get_scheduler_status(self) -> Dict[str, Any]:
        """
        Get comprehensive scheduler status and health information.

        Returns:
            Dict containing scheduler status, job counts, and health metrics
        """
        try:
            # Get job info from scheduler worker
            job_info = await asyncio.get_event_loop().run_in_executor(
                None, self.scheduler_worker.get_job_info
            )

            # Combine status information
            scheduler_status = {
                "scheduler_authority": {
                    "name": "SchedulerAuthorityService",
                    "worker_name": self.scheduler_worker.name,
                    "scheduler_running": job_info.get("scheduler_running", False),
                    "worker_running": self.scheduler_worker.running,
                },
                "job_summary": {
                    "total_jobs": job_info.get("total_jobs", 0),
                    "timelapse_jobs_count": len(
                        [
                            jid
                            for jid in job_info.get("job_ids", [])
                            if jid.startswith("timelapse_capture_")
                        ]
                    ),
                    "standard_jobs_count": len(
                        [
                            jid
                            for jid in job_info.get("job_ids", [])
                            if not jid.startswith("timelapse_capture_")
                        ]
                    ),
                    "job_ids": job_info.get("job_ids", []),
                },
                "health": {
                    "status": (
                        "healthy"
                        if job_info.get("scheduler_running", False)
                        else "unhealthy"
                    ),
                    "authority_active": True,
                    "dependencies": {
                        "async_db": self.async_db is not None,
                        "settings_service": self.settings_service is not None,
                        "timing_service": self.timing_service is not None,
                    },
                },
            }

            return scheduler_status

        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {
                "scheduler_authority": {
                    "name": "SchedulerAuthorityService",
                    "status": "error",
                    "error": str(e),
                },
                "job_summary": {
                    "total_jobs": 0,
                    "timelapse_jobs_count": 0,
                    "standard_jobs_count": 0,
                },
                "health": {
                    "status": "unhealthy",
                    "authority_active": False,
                    "error": str(e),
                },
            }

    async def add_timelapse_job(
        self, timelapse_id: int, capture_interval_seconds: int
    ) -> Dict[str, Any]:
        """
        Add a timelapse capture job through the scheduler authority.

        Args:
            timelapse_id: Timelapse ID to schedule captures for
            capture_interval_seconds: Interval between captures

        Returns:
            Dict containing success status and job details
        """
        try:
            logger.info(
                f"🕐 SchedulerAuthorityService: Adding timelapse job for timelapse {timelapse_id}"
            )

            success = await asyncio.get_event_loop().run_in_executor(
                None,
                self.scheduler_worker.add_timelapse_job,
                timelapse_id,
                capture_interval_seconds,
            )

            if success:
                return {
                    "success": True,
                    "message": f"Timelapse job added for timelapse {timelapse_id}",
                    "timelapse_id": timelapse_id,
                    "capture_interval_seconds": capture_interval_seconds,
                    "job_id": f"timelapse_{timelapse_id}_capture",
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to add timelapse job",
                    "timelapse_id": timelapse_id,
                    "capture_interval_seconds": capture_interval_seconds,
                }

        except Exception as e:
            logger.error(f"Error adding timelapse job: {e}")
            return {
                "success": False,
                "error": str(e),
                "timelapse_id": timelapse_id,
                "capture_interval_seconds": capture_interval_seconds,
            }

    async def remove_timelapse_job(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Remove a timelapse capture job through the scheduler authority.

        Args:
            timelapse_id: Timelapse ID to remove job for

        Returns:
            Dict containing success status and removal details
        """
        try:
            logger.info(
                f"🕐 SchedulerAuthorityService: Removing timelapse job for timelapse {timelapse_id}"
            )

            # SchedulerWorker.remove_timelapse_job returns None, so we assume success if no exception
            await asyncio.get_event_loop().run_in_executor(
                None, self.scheduler_worker.remove_timelapse_job, timelapse_id
            )

            return {
                "success": True,
                "message": f"Timelapse job removed for timelapse {timelapse_id}",
                "timelapse_id": timelapse_id,
                "job_id": f"timelapse_capture_{timelapse_id}",
            }

        except Exception as e:
            logger.error(f"Error removing timelapse job: {e}")
            return {"success": False, "error": str(e), "timelapse_id": timelapse_id}

    async def update_timelapse_job(
        self, timelapse_id: int, capture_interval_seconds: int
    ) -> Dict[str, Any]:
        """
        Update a timelapse capture job interval through the scheduler authority.

        Updates by removing the existing job and adding a new one with the new interval.

        Args:
            timelapse_id: Timelapse ID to update job for
            capture_interval_seconds: New interval between captures

        Returns:
            Dict containing success status and update details
        """
        try:
            logger.info(
                f"🕐 SchedulerAuthorityService: Updating timelapse job for timelapse {timelapse_id}"
            )

            # Remove existing job and add new one with updated interval
            await asyncio.get_event_loop().run_in_executor(
                None, self.scheduler_worker.remove_timelapse_job, timelapse_id
            )

            success = await asyncio.get_event_loop().run_in_executor(
                None,
                self.scheduler_worker.add_timelapse_job,
                timelapse_id,
                capture_interval_seconds,
            )

            if success:
                return {
                    "success": True,
                    "message": f"Timelapse job updated for timelapse {timelapse_id}",
                    "timelapse_id": timelapse_id,
                    "capture_interval_seconds": capture_interval_seconds,
                    "job_id": f"timelapse_capture_{timelapse_id}",
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to update timelapse job",
                    "timelapse_id": timelapse_id,
                    "capture_interval_seconds": capture_interval_seconds,
                }

        except Exception as e:
            logger.error(f"Error updating timelapse job: {e}")
            return {
                "success": False,
                "error": str(e),
                "timelapse_id": timelapse_id,
                "capture_interval_seconds": capture_interval_seconds,
            }

    async def sync_running_timelapses(self) -> Dict[str, Any]:
        """
        Synchronize scheduler with currently running timelapses.

        Returns:
            Dict containing sync results and statistics
        """
        try:
            logger.info(
                "🕐 SchedulerAuthorityService: Synchronizing running timelapses"
            )

            # Execute sync method in executor since it's not async
            await asyncio.get_event_loop().run_in_executor(
                None, self.scheduler_worker.sync_running_timelapses
            )

            return {
                "success": True,
                "message": "Timelapse synchronization completed successfully",
            }

        except Exception as e:
            logger.error(f"Error synchronizing timelapses: {e}")
            return {"success": False, "error": str(e)}

    def get_scheduler_worker(self) -> SchedulerWorker:
        """
        Get the underlying SchedulerWorker instance.

        This should only be used for advanced operations or testing.
        Most operations should go through the SchedulerAuthorityService methods.

        Returns:
            SchedulerWorker instance
        """
        return self.scheduler_worker


def create_scheduler_authority_service(
    scheduler_worker: SchedulerWorker,
    async_db: Optional[AsyncDatabase] = None,
    settings_service: Optional[SettingsService] = None,
    timing_service: Optional[CaptureTimingService] = None,
) -> SchedulerAuthorityService:
    """
    Factory function to create a SchedulerAuthorityService instance.

    Args:
        scheduler_worker: Initialized SchedulerWorker instance
        async_db: Optional async database connection
        settings_service: Optional async settings service
        timing_service: Optional capture timing service

    Returns:
        Configured SchedulerAuthorityService instance
    """
    return SchedulerAuthorityService(
        scheduler_worker=scheduler_worker,
        async_db=async_db,
        settings_service=settings_service,
        timing_service=timing_service,
    )


# Backwards compatibility aliases for existing imports
SchedulerService = SchedulerAuthorityService
AsyncSchedulerService = SchedulerAuthorityService
