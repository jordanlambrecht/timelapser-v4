# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger

from .config import settings
from .database import async_db, sync_db
from .routers import (
    cameras,
    timelapses,
    videos,
    settings as settings_router,
    logs,
    images,
    health,
    dashboard,
    thumbnails,
    corruption,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting FastAPI application")
    await async_db.initialize()
    sync_db.initialize()
    logger.info("Database connections initialized")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application")
    await async_db.close()
    sync_db.close()
    logger.info("Database connections closed")


app = FastAPI(
    title="Timelapser API",
    description="API for managing RTSP camera timelapses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(_request, exc):
    """Handle validation errors"""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(_request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Include routers
app.include_router(cameras.router, prefix="/api/cameras", tags=["cameras"])
app.include_router(timelapses.router, prefix="/api/timelapses", tags=["timelapses"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(thumbnails.router, prefix="/api/thumbnails", tags=["thumbnails"])
app.include_router(corruption.router, prefix="/api/corruption", tags=["corruption"])


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
