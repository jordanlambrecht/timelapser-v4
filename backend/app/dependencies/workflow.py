# backend/app/dependencies/workflow.py
"""
Workflow service dependencies using the factory pattern.

These services handle complex workflow orchestration and processing.
"""

from typing import TYPE_CHECKING

from .base import PipelineFactory

if TYPE_CHECKING:
    from ..services.capture_pipeline import (
        AsyncRTSPService,
        WorkflowOrchestratorService,
    )


# Async RTSP Service Factory
async def get_async_rtsp_service() -> "AsyncRTSPService":
    """Get capture pipeline AsyncRTSPService with wrapped sync RTSP service."""
    from ..services.capture_pipeline import AsyncRTSPService
    from .sync_services import get_rtsp_service

    sync_rtsp_service = get_rtsp_service()
    return AsyncRTSPService(sync_rtsp_service)


# Workflow Orchestrator Service Factory
def get_workflow_orchestrator_service() -> "WorkflowOrchestratorService":
    """Get WorkflowOrchestratorService with complete dependency injection through factory pattern."""
    factory = PipelineFactory(
        factory_module="app.services.capture_pipeline",
        factory_function="create_capture_pipeline",
    )
    return factory.get_service()
