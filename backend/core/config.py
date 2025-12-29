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
    # PostgreSQL only - required for production and development
    # Example: postgresql+asyncpg://security:password@localhost:5432/security
    database_url: str = Field(
        default="postgresql+asyncpg://security:security_dev_password@localhost:5432/security",
        description="SQLAlchemy database URL (PostgreSQL with asyncpg driver)",
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
    file_watcher_polling: bool = Field(
        default=False,
        description="Use polling observer instead of native filesystem events. "
        "Enable for Docker Desktop/macOS volume mounts where inotify/FSEvents don't work.",
    )
    file_watcher_polling_interval: float = Field(
        default=1.0,
        description="Polling interval in seconds when using polling observer",
        ge=0.1,
        le=30.0,
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

    # Rate limiting settings
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting for API endpoints",
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Maximum requests per minute per client IP",
    )
    rate_limit_burst: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Additional burst allowance for short request spikes",
    )
    rate_limit_media_requests_per_minute: int = Field(
        default=120,
        ge=1,
        le=10000,
        description="Maximum media requests per minute per client IP (stricter tier)",
    )
    rate_limit_websocket_connections_per_minute: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum WebSocket connection attempts per minute per client IP",
    )
    rate_limit_search_requests_per_minute: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Maximum search requests per minute per client IP",
    )

    # Severity threshold settings (risk score 0-100)
    severity_low_max: int = Field(
        default=29,
        ge=0,
        le=100,
        description="Maximum risk score for LOW severity (0 to this value = LOW)",
    )
    severity_medium_max: int = Field(
        default=59,
        ge=0,
        le=100,
        description="Maximum risk score for MEDIUM severity",
    )
    severity_high_max: int = Field(
        default=84,
        ge=0,
        le=100,
        description="Maximum risk score for HIGH severity (above = CRITICAL)",
    )

    # Notification settings
    notification_enabled: bool = Field(
        default=True,
        description="Enable notification delivery for alerts",
    )

    # SMTP email settings (optional)
    smtp_host: str | None = Field(
        default=None,
        description="SMTP server hostname for email notifications",
    )
    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP server port (typically 587 for TLS, 465 for SSL)",
    )
    smtp_user: str | None = Field(
        default=None,
        description="SMTP authentication username",
    )
    smtp_password: str | None = Field(
        default=None,
        description="SMTP authentication password",
    )
    smtp_from_address: str | None = Field(
        default=None,
        description="Email sender address for notifications",
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection",
    )

    # Webhook settings (optional)
    default_webhook_url: str | None = Field(
        default=None,
        description="Default webhook URL for alert notifications",
    )
    webhook_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for webhook HTTP requests",
    )

    # Default notification recipients
    default_email_recipients: list[str] = Field(
        default=[],
        description="Default email recipients for notifications",
    )

    # Clip generation settings
    clips_directory: str = Field(
        default="data/clips",
        description="Directory to store generated event clips",
    )
    clip_pre_roll_seconds: int = Field(
        default=5,
        ge=0,
        le=60,
        description="Seconds before event start to include in clip",
    )
    clip_post_roll_seconds: int = Field(
        default=5,
        ge=0,
        le=60,
        description="Seconds after event end to include in clip",
    )
    clip_generation_enabled: bool = Field(
        default=True,
        description="Enable automatic clip generation for events",
    )

    # TLS/HTTPS settings
    tls_enabled: bool = Field(
        default=False,
        description="Enable TLS/HTTPS for the API server",
    )
    tls_cert_file: str | None = Field(
        default=None,
        description="Path to TLS certificate file (PEM format)",
    )
    tls_key_file: str | None = Field(
        default=None,
        description="Path to TLS private key file (PEM format)",
    )
    tls_ca_file: str | None = Field(
        default=None,
        description="Path to CA certificate for client verification (optional)",
    )
    tls_auto_generate: bool = Field(
        default=False,
        description="Auto-generate self-signed certificates if none provided",
    )
    tls_cert_dir: str = Field(
        default="data/certs",
        description="Directory for auto-generated certificates",
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
        """Validate PostgreSQL database URL format."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError(
                f"Invalid database URL. Expected postgresql:// or postgresql+asyncpg:// format, got: {v}"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    # `_env_file` is evaluated at call time (unlike `model_config.env_file`, which is bound at
    # import time). This lets tests and deployments override runtime config cleanly.
    return Settings(_env_file=(".env", runtime_env_path))
