"""
Timelapser v4 Pydantic Models Package

This package contains all Pydantic models used throughout the Timelapser v4 application
for data validation, serialization, and API documentation. Models are organized by
domain and follow the entity-based architecture patterns.

Architecture Role:
    - API Layer: Uses models for request/response validation and OpenAPI documentation
    - Service Layer: Receives and returns model instances for type safety
    - Database Layer: Converts between database records and model instances

Model Organization:
    
    Core Entity Models:
        - camera_model: Camera lifecycle, configuration, and statistics models
        - timelapse_model: Timelapse entity models following entity-based architecture  
        - video_model: Video generation and metadata models
        - image_model: Image capture and metadata models
        - settings_model: System configuration and user preference models
        - log_model: Application logging and audit trail models
        
    Shared Models:
        - shared_models: Common enums, settings, and cross-domain models used
          throughout the application (VideoAutomationMode, CorruptionSettings, etc.)

Usage Patterns:
    - Import from this package for all model needs: `from app.models import Camera`
    - Models support inheritance patterns (camera → timelapse settings)
    - Optional variants (e.g., VideoGenerationSettingsOptional) for partial updates
    - Statistics models provide aggregated data views
    - WithDetails variants include related entity data

Example:
    ```python
    from app.models import Camera, CameraCreate, CameraWithTimelapse
    
    # API endpoint validation
    @router.post("/cameras", response_model=Camera)
    async def create_camera(camera_data: CameraCreate) -> Camera:
        pass
    ```

Notes:
    - All models use Pydantic v2 for validation and serialization
    - Models are timezone-aware using the system timezone configuration  
    - Enums and constants are defined in shared_models for consistency
    - Database operations return model instances for type safety
"""

from .camera_model import (
    Camera,
    CameraCreate,
    CameraUpdate,
    CameraWithTimelapse,
    CameraWithLastImage,
    CameraWithStats,
    CameraStats,
    CameraDetailsResponse,
    LogForCamera,
)
from .timelapse_model import (
    Timelapse,
    TimelapseCreate,
    TimelapseUpdate,
    TimelapseWithDetails,
)
from .video_model import Video, VideoCreate, VideoUpdate, VideoWithDetails
from .image_model import Image, ImageCreate, ImageWithDetails
from .settings_model import Setting, SettingCreate, SettingUpdate, BulkSettingsUpdate, WeatherSettingUpdate
from .log_model import Log, LogCreate
from .shared_models import (
    VideoGenerationMode,
    VideoAutomationMode,
    VideoGenerationSettings,
    VideoGenerationSettingsOptional,
    VideoAutomationSettings,
    VideoAutomationSettingsOptional,
    CorruptionDetectionSettings,
    CorruptionDetectionSettingsOptional,
    BaseStats,
    CameraHealthStatus,
    TimelapseStatistics,
    CameraStatistics,
    VideoGenerationJob,
    VideoGenerationJobWithDetails,
    VideoGenerationJobCreate,
    VideoStatistics,
    TimelapseForCleanup,
    TimelapseVideoSettings,
    CorruptionSettings,
    GenerationSchedule,
    MilestoneConfig,
)

__all__ = [
    # Core Models
    "Camera",
    "CameraCreate",
    "CameraUpdate",
    "CameraWithTimelapse",
    "CameraWithLastImage",
    "CameraWithStats",
    "CameraStats",
    "CameraDetailsResponse",
    "LogForCamera",
    "Timelapse",
    "TimelapseCreate",
    "TimelapseUpdate",
    "TimelapseWithDetails",
    "Video",
    "VideoCreate",
    "VideoUpdate",
    "VideoWithDetails",
    "Image",
    "ImageCreate",
    "ImageWithDetails",
    "Setting",
    "SettingCreate",
    "SettingUpdate",
    "BulkSettingsUpdate",
    "WeatherSettingUpdate",
    "Log",
    "LogCreate",
    # Shared Models
    "VideoGenerationMode",
    "VideoAutomationMode",
    "VideoGenerationSettings",
    "VideoGenerationSettingsOptional",
    "VideoAutomationSettings",
    "VideoAutomationSettingsOptional",
    "CorruptionDetectionSettings",
    "CorruptionDetectionSettingsOptional",
    "BaseStats",
    "CameraHealthStatus",
    "TimelapseStatistics",
    "CameraStatistics",
    "VideoGenerationJob",
    "VideoGenerationJobWithDetails",
    "VideoGenerationJobCreate",
    "VideoStatistics",
    "TimelapseForCleanup",
    "TimelapseVideoSettings",
    "CorruptionSettings",
    "GenerationSchedule",
    "MilestoneConfig",
]
