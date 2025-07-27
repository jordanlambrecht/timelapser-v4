# backend/app/main.py
"""
FastAPI application entry point for Timelapser v4.

IMPORTANT: This file should ONLY handle HTTP request/response logic.
DO NOT initialize background workers (ThumbnailWorker, OverlayWorker, etc.) here.

All background workers are managed by the separate worker.py process to maintain
clean separation between the web server and background job processing.

If you're tempted to add a worker here, add it to worker.py instead!
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger

from backend.app.services.logger.logger_service import LoggerService

from .config import settings
from .database import async_db, sync_db
from .enums import LogLevel

from .middleware import ErrorHandlerMiddleware, RequestLoggerMiddleware

# from app.middleware.trailing_slash import TrailingSlashRedirectMiddleware
from app.routers import (
    camera_routers as cameras,
    timelapse_routers as timelapses,
    video_routers as videos,
    settings_routers as settings_router,
    log_routers as logs,
    image_routers as images,
    health_routers as health,
    dashboard_routers as dashboard,
    thumbnail_routers as thumbnails,
    corruption_routers as corruption,
    video_automation_routers as video_automation,
    monitoring_routers as monitoring,
    sse_routers as sse,
    camera_crop_router as camera_crop,
    admin_routers as admin,
)

# Import full overlay router with complete functionality
from app.routers import overlay_routers as overlay

from app.utils.ascii_text import print_welcome_message


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting FastAPI application")
    await async_db.initialize()
    sync_db.initialize()
    logger.info("Database connections initialized")

    # Initialize centralized LoggerService for application logging
    try:

        # Create global logger service instance with batching enabled
        global_logger_service = LoggerService(
            async_db=async_db,
            sync_db=sync_db,
            enable_console=True,
            enable_file_logging=True,
            enable_sse_broadcasting=True,
            enable_batching=True,  # Enable batching for performance
        )

        # Store in app state for access by middleware and routes
        _app.state.logger_service = global_logger_service

        # Log startup success with the new system
        await global_logger_service.log_system(
            message="🚀 FastAPI application started with centralized logging system",
            level=LogLevel.INFO,
            store_in_db=True,
            broadcast_sse=True,
        )

        logger.info("Centralized LoggerService initialized with batching enabled")
    except Exception as e:
        logger.error(f"Failed to initialize LoggerService: {e}")

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
    logger.info("Shutting down FastAPI application")

    # Gracefully shutdown LoggerService with final flush
    try:
        if hasattr(_app.state, "logger_service"):
            await _app.state.logger_service.log_system(
                message="🛑 FastAPI application shutting down",
                level=LogLevel.INFO,
                store_in_db=True,
                broadcast_sse=True,
            )
            # Ensure all batched logs are written before shutdown
            await _app.state.logger_service.shutdown()
            logger.info("LoggerService shutdown complete")
    except Exception as e:
        logger.error(f"Error during LoggerService shutdown: {e}")

    await async_db.close()
    sync_db.close()
    logger.info("Database connections closed")


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
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(images.router, prefix="/api", tags=["images"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(thumbnails.router, prefix="/api", tags=["thumbnails"])
app.include_router(overlay.router, prefix="/api", tags=["overlays"])
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
