"""
Services module for Timelapser v4.

This module contains all business logic services that coordinate between
the data layer and API layer. Services handle complex operations and
orchestrate multiple database operations.

Available Services:
- ImageCaptureService: Handles RTSP image capture with corruption detection
- VideoGenerationService: Creates timelapse videos from images
- VideoAutomationService: Manages automated video generation workflows
- CorruptionDetection: Analyzes image quality and corruption (in corruption_detection/)
- WeatherService: Manages weather data integration (in weather/)
"""

# Service exports for easy importing
from .image_capture_service import ImageCaptureService as image_capture
from .video_service import VideoService, SyncVideoService
from .video_automation_service import VideoAutomationService as video_automation
from .rtsp_capture_service import RTSPCapture
from .camera_service import CameraService, SyncCameraService
from .corruption_service import CorruptionService
from .timelapse_service import TimelapseService
from .image_service import ImageService

# Note: Corruption detection and weather services are in their respective subdirectories
# Import them as:
# from app.services.corruption_detection import CorruptionController
# from app.services.weather.service import WeatherManager

__all__ = [
    "image_capture", 
    "VideoService", 
    "SyncVideoService",
    "video_automation", 
    "RTSPCapture",
    "CameraService",
    "SyncCameraService",
    "CorruptionService",
    "TimelapseService",
    "ImageService"
]
