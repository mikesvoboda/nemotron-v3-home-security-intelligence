"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/security.db",
        description="SQLAlchemy database URL for async SQLite",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Application settings
    app_name: str = "Home Security Intelligence"
    app_version: str = "0.1.0"
    debug: bool = False

    # API settings
    api_host: str = "0.0.0.0"  # noqa: S104
    api_port: int = 8000

    # CORS settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )

    # File watching settings
    foscam_base_path: str = Field(
        default="/export/foscam",
        description="Base path for Foscam FTP uploads",
    )

    # Retention settings
    retention_days: int = Field(
        default=30,
        description="Number of days to retain events and detections",
    )

    # Batch processing settings
    batch_window_seconds: int = Field(
        default=90,
        description="Time window for batch processing detections",
    )
    batch_idle_timeout_seconds: int = Field(
        default=30,
        description="Idle timeout before processing incomplete batch",
    )

    # AI service endpoints
    rtdetr_url: str = Field(
        default="http://localhost:8001",
        description="RT-DETRv2 detection service URL",
    )
    nemotron_url: str = Field(
        default="http://localhost:8002",
        description="Nemotron reasoning service URL",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database directory exists for SQLite."""
        if v.startswith("sqlite"):
            # Extract path from SQLite URL
            db_path = v.split("///")[-1] if "///" in v else v.split("//")[-1]
            if db_path and db_path != ":memory:":
                # Create data directory if it doesn't exist
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
