# backend/app/routers/health_routers.py
"""
System health and monitoring HTTP endpoints.

Role: System health and monitoring HTTP endpoints
Responsibilities: Health check aggregation, system status reporting, database pool
                 monitoring, filesystem health validation
Interactions: Uses HealthChecker for system validation, coordinates multiple services
             for comprehensive health status
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, status
from loguru import logger

from ..dependencies import (
    CameraServiceDep,
    StatisticsServiceDep,
    SettingsServiceDep,
)
from ..utils.router_helpers import handle_exceptions, create_success_response

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
@handle_exceptions("health check")
async def health_check():
    """
    Quick health check endpoint for load balancers and monitoring.

    Returns basic health status without detailed diagnostics.
    Use /detailed for comprehensive health information.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "timelapser-api",
        "version": "4.0.0",
    }


@router.get("/detailed")
@handle_exceptions("detailed health check")
async def detailed_health_check(
    camera_service: CameraServiceDep,
    statistics_service: StatisticsServiceDep,
    settings_service: SettingsServiceDep,
):
    """
    Comprehensive health check with detailed system diagnostics.

    Checks database connectivity, service health, and system resources.
    """
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "timelapser-api",
        "version": "4.0.0",
        "components": {},
    }

    overall_healthy = True

    # Check database connectivity via services
    try:
        # Test camera service (which uses database)
        await camera_service.get_cameras_with_images()
        health_data["components"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful",
        }
    except Exception as e:
        overall_healthy = False
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }

    # Check camera service health
    try:
        camera_stats = await statistics_service.get_camera_performance_stats()
        health_data["components"]["camera_service"] = {
            "status": "healthy",
            "message": "Camera service operational",
        }
    except Exception as e:
        overall_healthy = False
        health_data["components"]["camera_service"] = {
            "status": "unhealthy",
            "message": f"Camera service error: {str(e)}",
        }

    # Check settings service
    try:
        await settings_service.get_setting("timezone")
        health_data["components"]["settings_service"] = {
            "status": "healthy",
            "message": "Settings service operational",
        }
    except Exception as e:
        overall_healthy = False
        health_data["components"]["settings_service"] = {
            "status": "unhealthy",
            "message": f"Settings service error: {str(e)}",
        }

    # Set overall status
    health_data["status"] = "healthy" if overall_healthy else "unhealthy"

    # Return appropriate HTTP status
    if not overall_healthy:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_data
        )

    return health_data


@router.get("/database")
@handle_exceptions("database health check")
async def database_health_check(camera_service: CameraServiceDep):
    """Check database connectivity and performance"""
    try:
        # Test database connectivity via camera service
        start_time = datetime.now(timezone.utc)
        await camera_service.get_cameras_with_images()
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "status": "healthy",
            "response_time_seconds": response_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Database connectivity confirmed",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Database connectivity failed",
            },
        )


@router.get("/services")
@handle_exceptions("services health check")
async def services_health_check(
    camera_service: CameraServiceDep,
    statistics_service: StatisticsServiceDep,
    settings_service: SettingsServiceDep,
):
    """Check health of all application services"""
    services_status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {},
    }

    # Test camera service
    try:
        await camera_service.get_cameras_with_images()
        services_status["services"]["camera_service"] = {
            "status": "healthy",
            "message": "Camera service operational",
        }
    except Exception as e:
        services_status["services"]["camera_service"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Test statistics service
    try:
        stats = await statistics_service.get_dashboard_stats()
        # Use .model_dump() for Pydantic v2 compatibility
        services_status["services"]["statistics_service"] = {
            "status": "healthy",
            "message": "Statistics service operational",
            "data": stats.model_dump() if hasattr(stats, "model_dump") else stats.dict(),
        }
    except Exception as e:
        services_status["services"]["statistics_service"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Test settings service
    try:
        await settings_service.get_all_settings()
        services_status["services"]["settings_service"] = {
            "status": "healthy",
            "message": "Settings service operational",
        }
    except Exception as e:
        services_status["services"]["settings_service"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Determine overall status
    all_healthy = all(
        service.get("status") == "healthy"
        for service in services_status["services"].values()
    )
    services_status["overall_status"] = "healthy" if all_healthy else "degraded"

    return services_status


@router.get("/readiness")
@handle_exceptions("readiness check")
async def readiness_check(camera_service: CameraServiceDep):
    """
    Kubernetes-style readiness probe.

    Returns 200 if the service is ready to accept traffic.
    """
    try:
        # Quick database connectivity test
        await camera_service.get_cameras_with_images()

        return {"ready": True, "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ready": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get("/liveness")
@handle_exceptions("liveness check")
async def liveness_check():
    """
    Kubernetes-style liveness probe.

    Returns 200 if the service is alive and should not be restarted.
    """
    return {
        "alive": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_check": "ok",
    }
