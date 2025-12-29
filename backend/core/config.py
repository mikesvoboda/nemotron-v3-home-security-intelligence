"""Application configuration using Pydantic Settings."""

import os
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
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/security",
        description="PostgreSQL database URL (format: postgresql+asyncpg://user:pass@host:port/db)",
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

    # AI service endpoints (validated as URLs, stored as strings for compatibility)
    rtdetr_url: str = Field(
        default="http://localhost:8090",
        description="RT-DETRv2 detection service URL",
        pattern=r"^https?://.*",
    )
    nemotron_url: str = Field(
        default="http://localhost:8091",
        description="Nemotron reasoning service URL (llama.cpp server)",
        pattern=r"^https?://.*",
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
        description="Enable writing logs to database",
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

    # Queue backpressure settings
    queue_max_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum queue size before backpressure is applied",
    )
    queue_backpressure_threshold: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Queue fill ratio (0.0-1.0) at which warnings are logged",
    )
    queue_overflow_policy: str = Field(
        default="reject",
        description="Policy when queue is full: 'reject' (return error), 'dlq' (move oldest to DLQ), 'drop_oldest' (silent trim with warning)",
    )

    # Video processing settings
    video_frame_interval_seconds: float = Field(
        default=2.0,
        ge=0.5,
        le=30.0,
        description="Interval in seconds between extracted frames for video detection",
    )
    video_max_frames: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum number of frames to extract from a single video",
    )
    video_thumbnails_dir: str = Field(
        default="data/thumbnails",
        description="Directory for storing video thumbnails and extracted frames",
    )

    # TLS/HTTPS settings
    tls_mode: str = Field(
        default="disabled",
        description="TLS mode: 'disabled' (HTTP only), 'self_signed' (auto-generate certs), 'provided' (use existing certs)",
    )
    tls_cert_path: str | None = Field(
        default=None,
        description="Path to TLS certificate file (PEM format)",
    )
    tls_key_path: str | None = Field(
        default=None,
        description="Path to TLS private key file (PEM format)",
    )
    tls_ca_path: str | None = Field(
        default=None,
        description="Path to CA certificate for client verification (optional)",
    )
    tls_verify_client: bool = Field(
        default=False,
        description="Require and verify client certificates (mTLS)",
    )
    tls_min_version: str = Field(
        default="TLSv1.2",
        description="Minimum TLS version: 'TLSv1.2' or 'TLSv1.3'",
    )

    @field_validator("tls_mode")
    @classmethod
    def validate_tls_mode(cls, v: str) -> str:
        """Validate TLS mode is a valid option."""
        valid_modes = {"disabled", "self_signed", "provided"}
        if v not in valid_modes:
            raise ValueError(f"tls_mode must be one of: {', '.join(valid_modes)}")
        return v

    @field_validator("tls_min_version")
    @classmethod
    def validate_tls_min_version(cls, v: str) -> str:
        """Validate TLS minimum version."""
        valid_versions = {"TLSv1.2", "TLSv1.3", "1.2", "1.3"}
        if v not in valid_versions:
            raise ValueError(f"tls_min_version must be one of: {', '.join(valid_versions)}")
        return v

    @field_validator("log_file_path")
    @classmethod
    def validate_log_file_path(cls, v: str) -> str:
        """Ensure log directory exists."""
        Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate PostgreSQL database URL format."""
        if not v.startswith("postgresql"):
            raise ValueError(
                "Only PostgreSQL is supported. "
                "URL must start with 'postgresql+asyncpg://' or 'postgresql://'"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    # `_env_file` is evaluated at call time (unlike `model_config.env_file`, which is bound at
    # import time). This lets tests and deployments override runtime config cleanly.
    return Settings(_env_file=(".env", runtime_env_path))
