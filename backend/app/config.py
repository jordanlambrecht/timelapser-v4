from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ]

    # File storage
    data_directory: str = "./data"
    images_directory: str = "./data/cameras"
    videos_directory: str = "./data/videos"

    # Worker settings
    capture_interval: int = 300  # 5 minutes default
    max_concurrent_captures: int = 4
    health_check_interval: int = 120  # 2 minutes

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
