"""
Worker module for Timelapser v4.

This module contains modularized worker classes for different responsibilities:
- CaptureWorker: Image capture from RTSP cameras
- HealthWorker: Camera health monitoring and connectivity testing
- WeatherWorker: Weather data refresh and management
- VideoWorker: Video automation processing
- SchedulerWorker: Job scheduling and interval management
- SSEWorker: SSE events cleanup and maintenance
- CleanupWorker: Scheduled cleanup of old data based on retention policies
- ThumbnailWorker: Background thumbnail generation processing
- OverlayWorker: Background overlay generation processing

Architecture follows dependency injection patterns for testability and maintainability.
"""

from .base_worker import BaseWorker
from .capture_worker import CaptureWorker
from .health_worker import HealthWorker
from .weather_worker import WeatherWorker
from .video_worker import VideoWorker
from .scheduler_worker import SchedulerWorker
from .sse_worker import SSEWorker
from .cleanup_worker import CleanupWorker
from .thumbnail_worker import ThumbnailWorker
from .overlay_worker import OverlayWorker

__all__ = [
    "BaseWorker",
    "CaptureWorker",
    "HealthWorker",
    "WeatherWorker",
    "VideoWorker",
    "SchedulerWorker",
    "SSEWorker",
    "CleanupWorker",
    "ThumbnailWorker",
    "OverlayWorker",
]
