# backend/app/services/corruption_pipeline/corruption_pipeline.py
"""
Main Corruption Pipeline Class

Provides unified interface for all corruption detection functionality
with proper dependency injection and backward compatibility.
"""

from typing import Any, Dict, Optional

from ...database.core import AsyncDatabase, SyncDatabase
from ...enums import LoggerName
from ...services.logger import get_service_logger
from .services import (
    CorruptionEvaluationService,
    CorruptionHealthService,
    CorruptionStatisticsService,
    SyncCorruptionEvaluationService,
    SyncCorruptionHealthService,
    SyncCorruptionStatisticsService,
)

logger = get_service_logger(LoggerName.CORRUPTION_PIPELINE)


class CorruptionPipeline:
    """
    Main corruption detection pipeline providing unified access to all
    corruption detection functionality with proper dependency injection.
    """

    def __init__(
        self,
        evaluation_service: Optional[CorruptionEvaluationService] = None,
        health_service: Optional[CorruptionHealthService] = None,
        statistics_service: Optional[CorruptionStatisticsService] = None,
        database: Optional[SyncDatabase] = None,
        async_database: Optional[AsyncDatabase] = None,
    ):
        """
        Initialize corruption pipeline with injected services.

        Args:
            evaluation_service: Async evaluation service (for API endpoints)
            health_service: Async health service (for API endpoints)
            statistics_service: Async statistics service (for API endpoints)
            database: Sync database instance (for creating sync services)
            async_database: Async database instance (for async services)
        """
        self.evaluation_service = evaluation_service
        self.health_service = health_service
        self.statistics_service = statistics_service
        self.database = database
        self.async_database = async_database

        # Create sync services if sync database provided - use dependency injection to avoid cascade multiplication
        if database:
            # Use singleton factories to prevent database connection multiplication
            from ...dependencies.sync_services import (
                get_sync_corruption_evaluation_service,
                # Note: Other sync corruption services not yet available in DI system
            )
            try:
                # Use singleton for available services
                self.sync_evaluation_service = get_sync_corruption_evaluation_service()
                
                # Use singletons to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_corruption_health_service, get_sync_corruption_statistics_service
                self.sync_health_service = get_sync_corruption_health_service()
                self.sync_statistics_service = get_sync_corruption_statistics_service()
            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to use DI for corruption services, falling back to direct instantiation: {e}")
                # Fallback: still use singletons to prevent connection multiplication
                from ...dependencies.sync_services import get_sync_corruption_evaluation_service, get_sync_corruption_health_service, get_sync_corruption_statistics_service
                self.sync_evaluation_service = get_sync_corruption_evaluation_service()
                self.sync_health_service = get_sync_corruption_health_service()
                self.sync_statistics_service = get_sync_corruption_statistics_service()
        else:
            self.sync_evaluation_service = None
            self.sync_health_service = None
            self.sync_statistics_service = None

    def evaluate_image(
        self, camera_id: int, image_path: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Backward compatibility method for image evaluation.

        Args:
            camera_id: Camera ID
            image_path: Path to image
            **kwargs: Additional arguments

        Returns:
            Evaluation result dictionary
        """
        if self.sync_evaluation_service:
            result = self.sync_evaluation_service.evaluate_captured_image(
                camera_id=camera_id, file_path=image_path, **kwargs
            )
            return {
                "is_valid": result.is_valid,
                "corruption_score": result.corruption_score,
                "action_taken": result.action_taken,
            }
        else:
            logger.error("No sync evaluation service available")
            return {
                "is_valid": False,
                "corruption_score": 100.0,
                "action_taken": "error",
                "error": "No evaluation service available",
            }

    async def evaluate_image_async(
        self, camera_id: int, image_path: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Async image evaluation method.

        Args:
            camera_id: Camera ID
            image_path: Path to image
            **kwargs: Additional arguments

        Returns:
            Evaluation result dictionary
        """
        if self.evaluation_service:
            result = await self.evaluation_service.evaluate_image_quality(
                image_path=image_path, camera_id=camera_id, **kwargs
            )
            return {
                "is_valid": result.is_valid,
                "corruption_score": result.corruption_score,
                "action_taken": result.action_taken,
            }
        else:
            logger.error("No async evaluation service available")
            return {
                "is_valid": False,
                "corruption_score": 100.0,
                "action_taken": "error",
                "error": "No evaluation service available",
            }
