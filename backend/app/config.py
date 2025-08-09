# backend/app/config.py
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .enums import LogLevel


def get_project_root() -> Path:
    """Get project root directory - ONLY use for initial config setup"""
    return Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    environment: str = "development"
    # Database
    database_url: str = Field(..., description="PostgreSQL connection string")
    db_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool size (optimized for concurrency)",
    )
    db_max_overflow: int = Field(
        default=30,
        ge=5,
        le=100,
        description="Maximum overflow connections (optimized for peak load)",
    )
    db_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Database connection timeout in seconds",
    )

    # API
    api_host: str = Field(default="0.0.0.0", description="API host to bind to")
    api_port: int = Field(
        default=8000, ge=1, le=65535, description="API port to bind to"
    )
    api_reload: bool = Field(
        default=False, description="Enable auto-reload for development"
    )

    # CORS - use Union to handle both string and list inputs
    # Can be set via CORS_ORIGINS env var as comma-separated string
    cors_origins: Union[str, List[str]] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
        ],
        description="Allowed CORS origins. Can be comma-separated string.",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert cors_origins to a list of strings"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins

    # Frontend URL for SSE events
    # Can be set via FRONTEND_URL env var
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for SSE events and CORS configuration",
    )

    # ============= PATH CONFIGURATION (AI-CONTEXT COMPLIANT) =============
    # CRITICAL: All file operations MUST use these settings

    # Base data directory - defaults to relative path, overrideable
    data_directory: str = "./data"

    @property
    def data_path(self) -> Path:
        """Get data directory as Path object"""
        return Path(self.data_directory)

    @property
    def images_directory(self) -> str:
        """Images subdirectory path"""
        return str(self.data_path / "cameras")

    @property
    def videos_directory(self) -> str:
        """Videos subdirectory path"""
        return str(self.data_path / "videos")

    @property
    def thumbnails_directory(self) -> str:
        """Thumbnails subdirectory path"""
        return str(self.data_path / "thumbnails")

    @property
    def logs_directory(self) -> str:
        """Logs subdirectory path"""
        return str(self.data_path / "logs")

    def ensure_directories(self):
        """Create all required directories if they don't exist"""
        directories = [
            self.data_path,
            Path(self.images_directory),
            Path(self.videos_directory),
            Path(self.thumbnails_directory),
            Path(self.logs_directory),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_full_file_path(self, relative_path: str) -> Path:
        """Convert relative path to full path using data_directory"""
        return self.data_path / relative_path

    def get_relative_path(self, full_path: Union[str, Path]) -> str:
        """Convert full path to relative path from data_directory"""
        full_path = Path(full_path)
        try:
            return str(full_path.relative_to(self.data_path))
        except ValueError:
            # If path is not under data_directory, return as-is
            return str(full_path)

    # Worker settings
    capture_interval: int = Field(
        default=300,
        ge=10,
        le=86400,
        description="Capture interval in seconds (10s to 24h)",
    )
    max_concurrent_captures: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum concurrent capture operations",
    )
    health_check_interval: int = Field(
        default=120,
        ge=30,
        le=3600,
        description="Health check interval in seconds",
    )

    # Video generation
    video_generation_max_concurrent: int = Field(
        default=3, ge=1, le=10, description="Maximum concurrent video generation jobs"
    )
    video_generation_timeout_minutes: int = Field(
        default=30, ge=5, le=180, description="Video generation timeout in minutes"
    )

    # Logging
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file: Optional[str] = Field(
        default=None, description="Log file path (optional)"
    )

    # Weather integration (optional)
    openweather_api_key: str = Field(
        default="", description="OpenWeather API key (optional)"
    )

    # Overlay Pipeline Configuration
    overlay_processing_batch_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of overlay jobs to process in each batch",
    )
    overlay_high_throughput_threshold: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Daily job count threshold for high throughput classification",
    )
    overlay_moderate_throughput_threshold: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Daily job count threshold for moderate throughput classification",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> LogLevel:
        """Validate log level is one of the allowed values"""
        allowed_levels = LogLevel.__members__.keys()
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(allowed_levels)}"
            )
        return LogLevel[v_upper]

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the allowed values"""
        allowed_envs = ["development", "staging", "production"]
        v_lower = v.lower()
        if v_lower not in allowed_envs:
            raise ValueError(
                f"Invalid environment '{v}'. Must be one of: {', '.join(allowed_envs)}"
            )
        return v_lower

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Global settings instance
settings = Settings()  # type: ignore[call-arg]

# Ensure directories exist on import
settings.ensure_directories()
