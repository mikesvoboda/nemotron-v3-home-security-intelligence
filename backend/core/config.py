"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator
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
    redis_event_channel: str = Field(
        default="security_events",
        description="Redis pub/sub channel for security events",
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
    rtdetr_url: AnyHttpUrl = Field(
        default="http://localhost:8090",
        description="RT-DETRv2 detection service URL",
    )
    nemotron_url: AnyHttpUrl = Field(
        default="http://localhost:8091",
        description="Nemotron reasoning service URL (llama.cpp server)",
    )

    # Detection settings
    detection_confidence_threshold: float = Field(
        default=0.5,
        description="Minimum confidence threshold for object detections (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    # Fast path settings
    fast_path_confidence_threshold: float = Field(
        default=0.90,
        description="Confidence threshold for fast path high-priority analysis (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    fast_path_object_types: list[str] = Field(
        default=["person"],
        description="Object types that trigger fast path analysis when confidence threshold is met",
    )

    # GPU monitoring settings
    gpu_poll_interval_seconds: float = Field(
        default=5.0,
        description="GPU stats polling interval in seconds",
        ge=1.0,
        le=60.0,
    )
    gpu_stats_history_minutes: int = Field(
        default=60,
        description="Number of minutes of GPU stats history to retain in memory",
        ge=1,
        le=1440,
    )

    # Authentication settings
    api_key_enabled: bool = Field(
        default=False,
        description="Enable API key authentication (default: False for development)",
    )
    api_keys: list[str] = Field(
        default=[],
        description="List of valid API keys (plain text, hashed on startup)",
    )

    # File deduplication settings
    dedupe_ttl_seconds: int = Field(
        default=300,
        description="TTL for file dedupe entries in Redis (seconds)",
        ge=60,
        le=3600,
    )

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file_path: str = Field(
        default="data/logs/security.log",
        description="Path for rotating log file",
    )
    log_file_max_bytes: int = Field(
        default=10485760,  # 10MB
        description="Maximum size of each log file in bytes",
    )
    log_file_backup_count: int = Field(
        default=7,
        description="Number of backup log files to keep",
    )
    log_db_enabled: bool = Field(
        default=True,
        description="Enable writing logs to SQLite database",
    )
    log_db_min_level: str = Field(
        default="DEBUG",
        description="Minimum log level to write to database",
    )
    log_retention_days: int = Field(
        default=7,
        description="Number of days to retain logs",
    )

    # DLQ settings
    max_requeue_iterations: int = Field(
        default=10000,
        ge=1,
        le=100000,
        description="Maximum iterations for requeue-all operations",
    )

    @field_validator("log_file_path")
    @classmethod
    def validate_log_file_path(cls, v: str) -> str:
        """Ensure log directory exists."""
        Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v

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
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    # `_env_file` is evaluated at call time (unlike `model_config.env_file`, which is bound at
    # import time). This lets tests and deployments override runtime config cleanly.
    return Settings(_env_file=(".env", runtime_env_path))
