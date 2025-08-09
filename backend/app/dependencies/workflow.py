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


# Async RTSP Service Factory (Singleton)
def _create_async_rtsp_service():
    """Factory for creating AsyncRTSPService."""
    from ..services.capture_pipeline import AsyncRTSPService
    from .sync_services import get_rtsp_service

    sync_rtsp_service = get_rtsp_service()
    return AsyncRTSPService(sync_rtsp_service)


from .registry import get_singleton_service, register_singleton_factory
register_singleton_factory("async_rtsp_service", _create_async_rtsp_service)


async def get_async_rtsp_service() -> "AsyncRTSPService":
    """Get capture pipeline AsyncRTSPService singleton with wrapped sync RTSP service."""
    return get_singleton_service("async_rtsp_service")


# Workflow Orchestrator Service Factory (Singleton)
def get_workflow_orchestrator_service() -> "WorkflowOrchestratorService":
    """Get WorkflowOrchestratorService singleton with complete dependency injection."""
    from .sync_services import get_workflow_orchestrator_service as _get_workflow_orchestrator
    return _get_workflow_orchestrator()
