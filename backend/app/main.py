# backend/app/main.py
"""
FastAPI application entry point for Timelapser v4.

IMPORTANT: This file should ONLY handle HTTP request/response logic.
DO NOT initialize background workers (ThumbnailWorker, OverlayWorker, etc.) here.

All background workers are managed by the separate worker.py process to maintain
clean separation between the web server and background job processing.

If you're tempted to add a worker here, add it to worker.py instead!
"""

from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import full overlay router with complete functionality
# from app.middleware.trailing_slash import TrailingSlashRedirectMiddleware
from app.routers import admin_routers as admin
from app.routers import camera_crop_router as camera_crop
from app.routers import camera_routers as cameras
from app.routers import corruption_routers as corruption
from app.routers import dashboard_routers as dashboard
from app.routers import health_routers as health
from app.routers import image_routers as images
from app.routers import log_routers as logs
from app.routers import monitoring_routers as monitoring
from app.routers import overlay_routers as overlay
from app.routers import settings_routers as settings_router
from app.routers import sse_routers as sse
from app.routers import thumbnail_routers as thumbnails
from app.routers import timelapse_routers as timelapses
from app.routers import video_automation_routers as video_automation
from app.routers import video_routers as videos
from app.routers import weather_routers as weather
from app.utils.ascii_text import print_welcome_message

from .config import settings
from .constants import DEFAULT_TIMEZONE
from .database import async_db, sync_db
from .enums import LogEmoji, LogSource, LoggerName
from .middleware import ErrorHandlerMiddleware, RequestLoggerMiddleware
from .services.logger import get_service_logger, initialize_global_logger

logger: Any = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle application startup and shutdown"""
    # Initialize the global logger first
    await initialize_global_logger(
        async_db=async_db,
        sync_db=sync_db,
        enable_console=True,
        enable_file_logging=True,
        enable_sse_broadcasting=False,
        enable_batching=True,
    )

    # Get the system logger
    global logger
    logger = get_service_logger(LoggerName.SYSTEM, LogSource.SYSTEM)

    # Get the global logger service instance for app state
    from .services.logger.logger_service import log

    _app.state.logger_service = log()

    _app.state.logger_service = log()

    # Startup
    logger.info(
        "Starting FastAPI application",
        extra_context={
            "operation": "application_startup",
            "environment": settings.environment,
            "api_host": settings.api_host,
            "api_port": settings.api_port,
        },
    )

    # Initialize database with hybrid approach
    from .database.migrations import DatabaseInitializationError, initialize_database

    try:
        result = initialize_database()
        logger.info(
            f"Database initialized successfully: {result['method']}",
            extra_context={
                "operation": "database_initialization",
                "initialization_method": result["method"],
                "database_url": (
                    settings.database_url.split("@")[-1]
                    if "@" in settings.database_url
                    else "local"
                ),
            },
        )

        # Initialize async and sync databases
        await async_db.initialize()
        sync_db.initialize()

        # Validate database timezone configuration
        from app.utils.time_utils import validate_database_timezone_config

        is_valid, db_timezone = validate_database_timezone_config()
        if not is_valid:
            logger.warning(
                f"Database timezone configuration warning: {db_timezone}",
                extra_context={
                    "operation": "timezone_validation",
                    "db_timezone": db_timezone,
                    "expected": DEFAULT_TIMEZONE,
                    "severity": "warning",
                },
            )
            # Don't fail startup, but log warning for operations team
        else:
            logger.info(
                f"Database timezone validated: {db_timezone}",
                extra_context={
                    "operation": "timezone_validation",
                    "db_timezone": db_timezone,
                    "status": "valid",
                },
            )

    except DatabaseInitializationError as e:
        logger.error(
            f"Database initialization failed: {e}",
            extra_context={
                "operation": "database_initialization",
                "error_type": type(e).__name__,
            },
        )
        raise RuntimeError(f"Cannot start application: {e}") from e

    # Log successful logger initialization
    logger.info(
        "Centralized LoggerService initialized with batching enabled",
        extra_context={
            "operation": "logger_service_initialization",
            "batching_enabled": True,
        },
    )

    # Log startup success with the new system
    _app.state.logger_service.info(
        message="FastAPI application started with centralized logging system",
        emoji=LogEmoji.STARTUP,
        store_in_db=True,
        broadcast_sse=True,
    )

    # ⚠️ IMPORTANT: DO NOT START WORKERS HERE! ⚠️
    # Background workers (ThumbnailWorker, OverlayWorker, CaptureWorker, etc.)
    # are managed by the separate worker.py process. Starting workers here would:
    # - Create duplicate instances competing for the same jobs
    # - Violate separation of concerns between web server and job processing
    # - Lead to race conditions and confusing logs
    #
    # If you need to add a new worker, add it to worker.py instead!

    yield

    # Shutdown
    logger.info(
        "Shutting down FastAPI application",
        extra_context={
            "operation": "application_shutdown",
            "environment": settings.environment,
        },
    )

    # Gracefully shutdown LoggerService with final flush
    try:
        if hasattr(app.state, "logger_service"):
            app.state.logger_service.info(
                message="FastAPI application shutting down",
                emoji=LogEmoji.SHUTDOWN,
                store_in_db=True,
                broadcast_sse=True,
            )
            # Ensure all batched logs are written before shutdown
            await _app.state.logger_service.shutdown()
            logger.info(
                "LoggerService shutdown complete",
                extra_context={"operation": "logger_service_shutdown", "success": True},
            )
    except Exception as e:
        logger.error(
            f"Error during LoggerService shutdown: {e}",
            extra_context={
                "operation": "logger_service_shutdown",
                "error_type": type(e).__name__,
                "success": False,
            },
        )

    # Database cleanup
    await async_db.close()
    sync_db.close()
    logger.info(
        "Database connections closed",
        extra_context={"operation": "database_shutdown", "success": True},
    )


app = FastAPI(
    title="Timelapser API",
    redirect_slashes=True,
    description="API for managing RTSP camera timelapses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware to normalize trailing slashes for /api/* GET requests
# app.add_middleware(TrailingSlashRedirectMiddleware)

# Add middleware stack (order matters: last added = first executed)
# 1. Error handling (outermost - catches all errors)
app.add_middleware(ErrorHandlerMiddleware)

# 2. Request logging (logs all requests with correlation IDs)
app.add_middleware(RequestLoggerMiddleware)

# 3. CORS middleware (innermost - handles CORS before business logic)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Removed old exception handlers - now handled by ErrorHandlerMiddleware


# Include routers - Updated 2025-07-06 to force reload v2
app.include_router(cameras.router, prefix="/api", tags=["cameras"])
app.include_router(
    camera_crop.router, tags=["camera-crop"]
)  # Camera crop/rotation settings
app.include_router(timelapses.router, prefix="/api", tags=["timelapses"])
app.include_router(videos.router, prefix="/api", tags=["videos"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(images.router, prefix="/api", tags=["images"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(thumbnails.router, prefix="/api", tags=["thumbnails"])
app.include_router(overlay.router, prefix="/api/overlays", tags=["overlays"])
# Add image serving endpoints for thumbnail display
# from app.routers import image_serving_routers

# app.include_router(image_serving_routers.router, tags=["image-serving"])
app.include_router(corruption.router, prefix="/api", tags=["corruption"])
app.include_router(video_automation.router, prefix="/api", tags=["video-automation"])
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])
app.include_router(sse.router, prefix="/api", tags=["sse"])
app.include_router(admin.router, prefix="/api", tags=["admin"])


# NOTE: Legacy SSE endpoint removed - now handled by sse_routers.py
# The new database-driven SSE implementation is at /api/events via sse_routers


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Timelapser API", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    print_welcome_message()

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
