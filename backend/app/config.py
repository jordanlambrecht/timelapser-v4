# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Union, List
from pathlib import Path
import os


def get_project_root() -> Path:
    """Get project root directory - ONLY use for initial config setup"""
    return Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    environment: str = "development"
    # Database
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # CORS - use Union to handle both string and list inputs
    cors_origins: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ]

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert cors_origins to a list of strings"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins

    # Frontend URL for SSE events
    frontend_url: str = "http://localhost:3000"

    # ============= PATH CONFIGURATION (AI-CONTEXT COMPLIANT) =============
    # CRITICAL: All file operations MUST use these settings

    # Base data directory - defaults to relative path, can be overridden via environment
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
    capture_interval: int = 300  # 5 minutes default
    max_concurrent_captures: int = 4
    health_check_interval: int = 120  # 2 minutes

    # Video generation
    video_generation_max_concurrent: int = 3
    video_generation_timeout_minutes: int = 30

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Weather integration (optional)
    openweather_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Global settings instance
settings = Settings()  # type: ignore[call-arg]

# Ensure directories exist on import
settings.ensure_directories()
