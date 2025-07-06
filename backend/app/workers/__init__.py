"""
Worker module for Timelapser v4.

This module contains modularized worker classes for different responsibilities:
- CaptureWorker: Image capture and health monitoring
- WeatherWorker: Weather data refresh and management
- VideoWorker: Video automation processing
- SchedulerWorker: Job scheduling and interval management
- CleanupWorker: Scheduled cleanup of old data based on retention policies

Architecture follows dependency injection patterns for testability and maintainability.
"""

from .base_worker import BaseWorker
from .capture_worker import CaptureWorker
from .weather_worker import WeatherWorker
from .video_worker import VideoWorker
from .scheduler_worker import SchedulerWorker
from .sse_worker import SSEWorker
from .cleanup_worker import CleanupWorker

__all__ = [
    "BaseWorker",
    "CaptureWorker",
    "WeatherWorker",
    "VideoWorker",
    "SchedulerWorker",
    "SSEWorker",
    "CleanupWorker",
]
