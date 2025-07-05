# backend/app/routers/health_routers.py
"""
System health and monitoring HTTP endpoints.

Role: System health and monitoring HTTP endpoints
Responsibilities: Health check aggregation, system status reporting, database pool
                 monitoring, filesystem health validation
Interactions: Uses HealthService for system validation, coordinates multiple services
             for comprehensive health status

Follows architectural patterns:
- Dependency injection for services
- Standardized error handling
- Proper Pydantic models
- ResponseFormatter for consistent responses
"""

from fastapi import APIRouter, status, HTTPException
from typing import Dict, Any

from app.dependencies import HealthServiceDep
from app.models.health_model import (
    BasicHealthCheck,
    DetailedHealthCheck,
    DatabaseHealth,
    FilesystemHealth,
    SystemMetrics,
    ApplicationMetrics,
    HealthStatus
)
from app.utils.router_helpers import handle_exceptions, ResponseFormatter
from app.constants import APPLICATION_NAME, APPLICATION_VERSION

# TODO: CACHING STRATEGY - MINIMAL/NO CACHE
# Health endpoints are critical monitoring data that changes frequently:
# - Basic health (/health, /readiness, /liveness): No cache - load balancers need real-time status
# - Detailed health/metrics: Very short cache (30-60 seconds max) or SSE broadcasting
# - System/application metrics: SSE broadcasting for real-time monitoring dashboards
router = APIRouter(tags=["health"])


@router.get("/health", response_model=Dict[str, Any])
@handle_exceptions("basic health check")
async def health_check(health_service: HealthServiceDep) -> Dict[str, Any]:
    """
    Quick health check endpoint for load balancers and monitoring.

    Returns basic health status without detailed diagnostics.
    Use /health/detailed for comprehensive health information.
    """
    basic_health = await health_service.get_basic_health()
    
    # Convert to dict for ResponseFormatter
    health_data = basic_health.model_dump()
    
    # Return error status code if unhealthy
    if basic_health.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )
    elif basic_health.status == HealthStatus.DEGRADED:
        return ResponseFormatter.success(
            data=health_data,
            message="Service degraded - some components need attention"
        )
    
    return ResponseFormatter.success(
        data=health_data,
        message="Service healthy"
    )


@router.get("/health/detailed", response_model=Dict[str, Any])
@handle_exceptions("detailed health check")
async def detailed_health_check(health_service: HealthServiceDep) -> Dict[str, Any]:
    """
    Comprehensive health check with detailed system diagnostics.

    Checks database connectivity, service health, and system resources.
    """
    detailed_health = await health_service.get_detailed_health()
    
    # Convert to dict for ResponseFormatter
    health_data = detailed_health.model_dump()
    
    # Return error status code if unhealthy
    if detailed_health.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System health check failed"
        )
    elif detailed_health.status == HealthStatus.DEGRADED:
        # Return 200 but with warning message for degraded status
        return ResponseFormatter.success(
            data=health_data,
            message="System health degraded - some components need attention"
        )
    
    return ResponseFormatter.success(
        data=health_data,
        message="System health check completed successfully"
    )


@router.get("/health/database", response_model=Dict[str, Any])
@handle_exceptions("database health check")
async def database_health_check(health_service: HealthServiceDep) -> Dict[str, Any]:
    """Get detailed database health information."""
    db_health = await health_service.get_database_health()
    health_data = db_health.model_dump()
    
    if db_health.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed"
        )
    elif db_health.status == HealthStatus.DEGRADED:
        return ResponseFormatter.success(
            data=health_data,
            message="Database health degraded - performance issues detected"
        )
    
    return ResponseFormatter.success(
        data=health_data,
        message="Database health check completed"
    )


@router.get("/health/filesystem", response_model=Dict[str, Any])
@handle_exceptions("filesystem health check")
async def filesystem_health_check(health_service: HealthServiceDep) -> Dict[str, Any]:
    """Get detailed filesystem health information."""
    fs_health = await health_service.get_filesystem_health()
    health_data = fs_health.model_dump()
    
    if fs_health.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Filesystem health check failed"
        )
    elif fs_health.status == HealthStatus.DEGRADED:
        return ResponseFormatter.success(
            data=health_data,
            message="Filesystem health degraded - storage issues detected"
        )
    
    return ResponseFormatter.success(
        data=health_data,
        message="Filesystem health check completed"
    )


@router.get("/health/system", response_model=Dict[str, Any])
@handle_exceptions("system metrics check")
async def system_metrics_check(health_service: HealthServiceDep) -> Dict[str, Any]:
    """Get current system performance metrics."""
    metrics = await health_service.get_system_metrics()
    metrics_data = metrics.model_dump()
    
    return ResponseFormatter.success(
        data=metrics_data,
        message="System metrics retrieved successfully"
    )


@router.get("/health/application", response_model=Dict[str, Any])
@handle_exceptions("application metrics check")
async def application_metrics_check(health_service: HealthServiceDep) -> Dict[str, Any]:
    """Get application-specific health metrics."""
    metrics = await health_service.get_application_metrics()
    metrics_data = metrics.model_dump()
    
    return ResponseFormatter.success(
        data=metrics_data,
        message="Application metrics retrieved successfully"
    )


# Kubernetes-style health endpoints
@router.get("/health/readiness", response_model=Dict[str, Any])
@handle_exceptions("readiness probe")
async def readiness_probe(health_service: HealthServiceDep) -> Dict[str, Any]:
    """
    Kubernetes readiness probe endpoint.
    
    Checks if the service is ready to receive traffic.
    """
    basic_health = await health_service.get_basic_health()
    
    if basic_health.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )
    elif basic_health.status == HealthStatus.DEGRADED:
        return {
            "status": "ready_degraded", 
            "timestamp": basic_health.timestamp.isoformat(),
            "message": "Service ready but degraded"
        }
    
    return {"status": "ready", "timestamp": basic_health.timestamp.isoformat()}


@router.get("/health/liveness", response_model=Dict[str, Any])
@handle_exceptions("liveness probe")
async def liveness_probe() -> Dict[str, Any]:
    """
    Kubernetes liveness probe endpoint.
    
    Simple endpoint to check if the service is alive.
    """
    return {
        "status": "alive",
        "service": APPLICATION_NAME,
        "version": APPLICATION_VERSION
    }
