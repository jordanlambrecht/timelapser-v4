# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import asyncio
from loguru import logger

from .config import settings
from .database import async_db, sync_db

from .middleware import ErrorHandlerMiddleware, RequestLoggerMiddleware

# Worker imports
from .workers.thumbnail_worker import ThumbnailWorker
from .services.thumbnail_job_service import SyncThumbnailJobService
from .services.thumbnail_service import ThumbnailService
from .database.sse_events_operations import SyncSSEEventsOperations
from .services.settings_service import SyncSettingsService

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
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting FastAPI application")
    await async_db.initialize()
    sync_db.initialize()
    logger.info("Database connections initialized")

    # Setup database logging for FastAPI
    try:
        from app.logging.database_handler import setup_database_logging

        setup_database_logging(sync_db)
        logger.info("Database logging enabled for FastAPI")
    except Exception as e:
        logger.error(f"Failed to enable database logging: {e}")

    # Start ThumbnailWorker
    thumbnail_worker = None
    thumbnail_worker_task = None
    try:
        logger.info("🚀 Starting ThumbnailWorker...")

        # Create worker dependencies using proper services
        settings_service = SyncSettingsService(sync_db)
        thumbnail_job_service = SyncThumbnailJobService(sync_db, settings_service)
        thumbnail_service = ThumbnailService(async_db, sync_db)
        sse_ops = SyncSSEEventsOperations(sync_db)

        # Create and start thumbnail worker
        thumbnail_worker = ThumbnailWorker(
            thumbnail_job_service=thumbnail_job_service,
            thumbnail_service=thumbnail_service,
            sse_ops=sse_ops,
        )

        await thumbnail_worker.start()
        await thumbnail_worker.initialize()

        # Run worker in background
        thumbnail_worker_task = asyncio.create_task(thumbnail_worker.run())
        logger.info("✅ ThumbnailWorker started successfully")

    except Exception as e:
        logger.error(f"❌ Failed to start ThumbnailWorker: {e}")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application")

    # Stop ThumbnailWorker
    if thumbnail_worker_task:
        try:
            logger.info("🛑 Stopping ThumbnailWorker...")
            if thumbnail_worker:
                await thumbnail_worker.stop()
                await thumbnail_worker.cleanup()
            thumbnail_worker_task.cancel()
            try:
                await thumbnail_worker_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ ThumbnailWorker stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping ThumbnailWorker: {e}")

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
app.include_router(timelapses.router, prefix="/api", tags=["timelapses"])
app.include_router(videos.router, prefix="/api", tags=["videos"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(images.router, prefix="/api", tags=["images"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(thumbnails.router, prefix="/api", tags=["thumbnails"])
# Add image serving endpoints for thumbnail display
from app.routers import image_serving_routers

app.include_router(image_serving_routers.router, tags=["image-serving"])
app.include_router(corruption.router, prefix="/api", tags=["corruption"])
app.include_router(video_automation.router, prefix="/api", tags=["video-automation"])
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])
app.include_router(sse.router, prefix="/api", tags=["sse"])

# Development and testing routers
from app.routers import cache_test_routers

app.include_router(cache_test_routers.router, prefix="/api", tags=["cache-testing"])


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
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
