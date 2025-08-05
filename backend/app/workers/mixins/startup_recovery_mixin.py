# backend/app/workers/mixins/startup_recovery_mixin.py
"""
StartupRecoveryMixin for standardized stuck job recovery.

Eliminates repetitive startup recovery patterns across job processing workers
while maintaining consistent logging and error handling.

This mixin provides:
- Standard stuck job recovery pattern
- Consistent recovery result logging
- Proper error handling during recovery
- Configurable recovery parameters
"""

from typing import Dict, Any, Optional
from ...services.logger import get_service_logger
from ...enums import LoggerName, LogSource, LogEmoji

# Initialize mixin logger
recovery_logger = get_service_logger(LoggerName.SYSTEM, LogSource.WORKER)


class StartupRecoveryMixin:
    """
    Mixin for standardized startup recovery of stuck jobs.

    Provides consistent stuck job recovery patterns for job processing workers:
    - Standard recovery logging with proper context
    - Consistent error handling during recovery operations
    - Configurable recovery parameters
    - Proper result interpretation and logging

    Usage:
        class MyJobWorker(StartupRecoveryMixin, JobProcessingMixin, BaseWorker):
            async def initialize(self) -> None:
                # ... other initialization ...

                # Perform startup recovery
                self.perform_startup_recovery(
                    job_service=self.job_service,
                    job_type_name="thumbnail",
                    max_processing_age_minutes=30
                )
    """

    def perform_startup_recovery(
        self,
        job_service: Any,
        job_type_name: str,
        max_processing_age_minutes: int = 30,
        logger: Optional[Any] = None,
    ) -> Dict[str, int]:
        """
        Standard stuck job recovery pattern.

        Performs standardized recovery of jobs that may have been left in
        'processing' state due to worker crashes or unexpected shutdowns.

        Args:
            job_service: Service that has recover_stuck_jobs method
            job_type_name: Human-readable name of job type for logging
            max_processing_age_minutes: Maximum age of processing jobs to consider stuck
            logger: Optional specific logger (uses recovery_logger if None)

        Returns:
            Dictionary with recovery results:
            - stuck_jobs_found: Number of stuck jobs discovered
            - stuck_jobs_recovered: Number of jobs successfully recovered
        """
        if logger is None:
            logger = recovery_logger

        try:
            logger.info(
                f"🔄 Performing startup recovery for stuck {job_type_name} jobs...",
                emoji=LogEmoji.TASK,
                extra_context={
                    "operation": "startup_recovery",
                    "job_type": job_type_name,
                    "max_processing_age_minutes": max_processing_age_minutes,
                },
            )

            # Call the job service's recovery method
            recovery_results = job_service.recover_stuck_jobs(
                max_processing_age_minutes=max_processing_age_minutes
            )

            # Extract results with proper defaults
            stuck_jobs_recovered = recovery_results.get("stuck_jobs_recovered", 0)
            stuck_jobs_found = recovery_results.get("stuck_jobs_found", 0)

            # Log results based on recovery outcome
            if stuck_jobs_recovered > 0:
                logger.info(
                    f"✅ Recovered {stuck_jobs_recovered} stuck {job_type_name} jobs on startup",
                    emoji=LogEmoji.SUCCESS,
                    extra_context={
                        "operation": "startup_recovery_success",
                        "job_type": job_type_name,
                        "stuck_jobs_recovered": stuck_jobs_recovered,
                        "stuck_jobs_found": stuck_jobs_found,
                    },
                )
            elif stuck_jobs_found > 0:
                logger.warning(
                    f"Found {stuck_jobs_found} stuck {job_type_name} jobs but only recovered {stuck_jobs_recovered}",
                    extra_context={
                        "operation": "startup_recovery_partial",
                        "job_type": job_type_name,
                        "stuck_jobs_recovered": stuck_jobs_recovered,
                        "stuck_jobs_found": stuck_jobs_found,
                    },
                )
            else:
                logger.debug(
                    f"No stuck {job_type_name} jobs found during startup recovery",
                    extra_context={
                        "operation": "startup_recovery_none",
                        "job_type": job_type_name,
                        "stuck_jobs_found": 0,
                    },
                )

            return recovery_results

        except Exception as e:
            logger.error(
                f"Error during startup recovery for {job_type_name} jobs: {e}",
                store_in_db=False
            )
            # Return empty results on error
            return {"stuck_jobs_found": 0, "stuck_jobs_recovered": 0}

    def get_recovery_stats(self, recovery_results: Dict[str, int]) -> Dict[str, Any]:
        """
        Get formatted recovery statistics for status reporting.

        Args:
            recovery_results: Results from perform_startup_recovery

        Returns:
            Dictionary with formatted recovery statistics
        """
        return {
            "last_recovery_found": recovery_results.get("stuck_jobs_found", 0),
            "last_recovery_recovered": recovery_results.get("stuck_jobs_recovered", 0),
            "last_recovery_success": recovery_results.get("stuck_jobs_recovered", 0)
            > 0,
            "last_recovery_error": recovery_results.get("error"),
        }
