"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.sanitization import URLValidationError, validate_grafana_url
from backend.core.url_validation import SSRFValidationError
from backend.core.url_validation import validate_webhook_url as validate_webhook_url_ssrf


class OrchestratorSettings(BaseSettings):
    """Container orchestrator configuration for Docker/Podman container management.

    This settings model configures the container orchestrator service that provides
    health monitoring and self-healing capabilities for AI containers (RT-DETRv2,
    Nemotron, Florence-2, etc.).

    Environment variables use the ORCHESTRATOR_ prefix (e.g., ORCHESTRATOR_ENABLED).
    """

    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Feature flag
    enabled: bool = Field(
        True,
        description="Enable container orchestration. When enabled, the orchestrator "
        "monitors AI container health and can automatically restart unhealthy containers.",
    )

    # Docker connection
    docker_host: str | None = Field(
        None,
        description="Docker host URL. If None, uses DOCKER_HOST environment variable "
        "or Docker's default socket path. Examples: 'unix:///var/run/docker.sock', "
        "'tcp://localhost:2375', 'unix:///run/user/1000/podman/podman.sock' (rootless Podman).",
    )

    # Health monitoring
    health_check_interval: int = Field(
        30,
        ge=5,
        le=300,
        description="Seconds between container health checks. Lower values provide "
        "faster detection of unhealthy containers but increase system load.",
    )
    health_check_timeout: int = Field(
        5,
        ge=1,
        le=60,
        description="Timeout in seconds for individual health check HTTP requests. "
        "Should be lower than health_check_interval.",
    )
    startup_grace_period: int = Field(
        60,
        ge=10,
        le=600,
        description="Seconds to wait after container start before performing health checks. "
        "Allows time for AI models to load into GPU memory.",
    )

    # Self-healing limits
    max_consecutive_failures: int = Field(
        5,
        ge=1,
        le=50,
        description="Number of consecutive health check failures before disabling "
        "automatic restart for a container. Prevents restart loops.",
    )
    restart_backoff_base: float = Field(
        5.0,
        ge=1.0,
        le=60.0,
        description="Base backoff time in seconds for restart attempts. "
        "Actual delay = min(base * 2^attempt, max).",
    )
    restart_backoff_max: float = Field(
        300.0,
        ge=30.0,
        le=3600.0,
        description="Maximum backoff time in seconds between restart attempts (5 minutes default). "
        "Caps exponential backoff to prevent excessively long waits.",
    )


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
    # Example: postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret
    database_url: str = Field(
        default="",
        description="PostgreSQL database URL (format: postgresql+asyncpg://user:pass@host:port/db)",  # pragma: allowlist secret
    )

    # Database connection pool settings
    # Pool size should be tuned based on workload. Default 20 with 30 overflow = 50 max
    # connections, suitable for moderate workloads with multiple background workers.
    database_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Base number of database connections to maintain in pool",
    )
    database_pool_overflow: int = Field(
        default=30,
        ge=0,
        le=100,
        description="Additional connections beyond pool_size when under load",
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Seconds to wait for available connection before timeout error",
    )
    database_pool_recycle: int = Field(
        default=1800,
        ge=300,
        le=7200,
        description="Seconds after which connections are recycled (prevents stale connections)",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_password: str | None = Field(
        default=None,
        description="Redis password for authentication. Optional for local development (no password). "
        "Set via REDIS_PASSWORD environment variable for production deployments. "
        "Must match the `requirepass` value configured in Redis.",
    )
    redis_event_channel: str = Field(
        default="security_events",
        description="Redis pub/sub channel for security events",
    )

    # Redis SSL/TLS settings
    redis_ssl_enabled: bool = Field(
        default=False,
        description="Enable SSL/TLS encryption for Redis connections. "
        "When True, uses 'rediss://' scheme or adds SSL context to connection. "
        "Set to True for production environments to encrypt data in transit.",
    )
    redis_ssl_cert_reqs: str = Field(
        default="required",
        description="SSL certificate verification mode: 'none' (no verification), "
        "'optional' (verify if cert provided), 'required' (always verify). "
        "Use 'required' for production with proper CA certificates.",
    )
    redis_ssl_ca_certs: str | None = Field(
        default=None,
        description="Path to CA certificate file (PEM format) for verifying Redis server certificate. "
        "Required when redis_ssl_cert_reqs is 'required' or 'optional'.",
    )
    redis_ssl_certfile: str | None = Field(
        default=None,
        description="Path to client certificate file (PEM format) for mutual TLS (mTLS) authentication. "
        "Optional - only needed if Redis server requires client certificates.",
    )
    redis_ssl_keyfile: str | None = Field(
        default=None,
        description="Path to client private key file (PEM format) for mutual TLS (mTLS) authentication. "
        "Required if redis_ssl_certfile is provided.",
    )
    redis_ssl_check_hostname: bool = Field(
        default=True,
        description="Verify that the Redis server's certificate hostname matches. "
        "Should be True for production. Set to False only for testing with self-signed certs.",
    )

    # Application settings
    app_name: str = "Home Security Intelligence"
    app_version: str = "0.1.0"
    debug: bool = False

    # Admin endpoints settings
    # SECURITY: Admin endpoints require BOTH debug=True AND admin_enabled=True
    # This provides defense-in-depth against accidentally exposing admin endpoints
    admin_enabled: bool = Field(
        default=False,
        description="Enable admin endpoints (requires debug=True as well). "
        "SECURITY: Must be explicitly enabled - provides protection against "
        "accidentally enabling admin endpoints in production.",
    )
    admin_api_key: str | None = Field(
        default=None,
        description="Optional API key required for admin endpoints. "
        "When set, all admin requests must include X-Admin-API-Key header.",
    )

    # API settings
    api_host: str = "0.0.0.0"  # noqa: S104
    api_port: int = 8000

    # CORS settings
    # Includes common development ports and 0.0.0.0 (accept from any origin when bound to all interfaces)
    # For production, override via CORS_ORIGINS env var with specific allowed origins
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://0.0.0.0:3000",
            "http://0.0.0.0:5173",
        ],
        description="Allowed CORS origins. Set CORS_ORIGINS env var to override for your network.",
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
    batch_check_interval_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Interval (seconds) between batch timeout checks. "
        "Lower values reduce latency between timeout and batch close but increase CPU usage.",
    )

    # AI service endpoints (validated as URLs using Pydantic AnyHttpUrl)
    # Stored as str after validation for compatibility with httpx clients
    rtdetr_url: str = Field(
        default="http://localhost:8090",
        description="RT-DETRv2 detection service URL",
    )
    nemotron_url: str = Field(
        default="http://localhost:8091",
        description="Nemotron reasoning service URL (llama.cpp server)",
    )

    # AI service authentication
    # Security: API keys for authenticating with AI services
    rtdetr_api_key: str | None = Field(
        default=None,
        description="API key for RT-DETRv2 service authentication (optional, sent via X-API-Key header)",
    )
    nemotron_api_key: str | None = Field(
        default=None,
        description="API key for Nemotron service authentication (optional, sent via X-API-Key header)",
    )

    # AI service timeout settings
    ai_connect_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Maximum time (seconds) to establish connection to AI services",
    )
    ai_health_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Timeout (seconds) for AI service health checks",
    )
    rtdetr_read_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=300.0,
        description="Maximum time (seconds) to wait for RT-DETR detection response",
    )
    nemotron_read_timeout: float = Field(
        default=120.0,
        ge=30.0,
        le=600.0,
        description="Maximum time (seconds) to wait for Nemotron LLM response",
    )

    @field_validator("rtdetr_url", "nemotron_url", mode="before")
    @classmethod
    def validate_ai_service_urls(cls, v: Any) -> str:
        """Validate AI service URLs using Pydantic's AnyHttpUrl validator.

        This ensures URLs are well-formed HTTP/HTTPS URLs while returning
        a string for compatibility with httpx clients.

        Args:
            v: The URL value to validate

        Returns:
            The validated URL as a string

        Raises:
            ValueError: If the URL is not a valid HTTP/HTTPS URL
        """
        if v is None:
            raise ValueError("AI service URL cannot be None")

        # Convert to string if needed
        url_str = str(v)

        # Use AnyHttpUrl for validation (supports http and https)
        try:
            validated_url = AnyHttpUrl(url_str)
            # Return as string for httpx compatibility
            # Strip trailing slash to avoid double-slash when appending paths like /health
            return str(validated_url).rstrip("/")
        except Exception as e:
            raise ValueError(
                f"Invalid AI service URL '{url_str}': must be a valid HTTP/HTTPS URL. "
                f"Example: 'http://localhost:8090'. Error: {e}"
            ) from None

    # Florence-2, CLIP, and Enrichment service URLs
    florence_url: str = Field(
        default="http://localhost:8092",
        description="Florence-2 vision-language service URL",
    )
    clip_url: str = Field(
        default="http://localhost:8093",
        description="CLIP embedding service URL for re-identification",
    )
    enrichment_url: str = Field(
        default="http://localhost:8094",
        description="Combined enrichment service URL for vehicle, pet, and clothing classification",
    )

    # Monitoring URLs
    grafana_url: str = Field(
        default="http://localhost:3002",
        description="Grafana dashboard URL for frontend link",
    )

    @field_validator("grafana_url", mode="before")
    @classmethod
    def validate_grafana_url_field(cls, v: Any) -> str:
        """Validate Grafana URL with SSRF protection (NEM-1077).

        This validates that the Grafana URL:
        1. Is a valid HTTP/HTTPS URL
        2. Does not point to cloud metadata endpoints
        3. Allows internal IPs (since Grafana is typically local)

        Args:
            v: The URL value to validate

        Returns:
            The validated URL as a string

        Raises:
            ValueError: If the URL fails validation
        """
        if v is None or v == "":
            return "http://localhost:3002"  # Default

        url_str = str(v)

        try:
            return validate_grafana_url(url_str)
        except URLValidationError as e:
            raise ValueError(f"Invalid Grafana URL: {e}") from None

    # Frontend URL for health checks (internal Docker network URL)
    frontend_url: str = Field(
        default="http://frontend:80",
        description="Frontend container URL for health checks (Docker internal network). "
        "Use 'http://frontend:80' for Docker/Podman, or 'http://localhost:5173' for local dev.",
    )

    @field_validator("florence_url", "clip_url", "enrichment_url", mode="before")
    @classmethod
    def validate_vision_service_urls(cls, v: Any) -> str:
        """Validate vision service URLs using Pydantic's AnyHttpUrl validator.

        This ensures URLs are well-formed HTTP/HTTPS URLs while returning
        a string for compatibility with httpx clients.

        Args:
            v: The URL value to validate

        Returns:
            The validated URL as a string

        Raises:
            ValueError: If the URL is not a valid HTTP/HTTPS URL
        """
        if v is None:
            raise ValueError("Vision service URL cannot be None")

        # Convert to string if needed
        url_str = str(v)

        # Use AnyHttpUrl for validation (supports http and https)
        try:
            validated_url = AnyHttpUrl(url_str)
            # Return as string for httpx compatibility
            # Strip trailing slash to avoid double-slash when appending paths like /health
            return str(validated_url).rstrip("/")
        except Exception as e:
            raise ValueError(
                f"Invalid vision service URL '{url_str}': must be a valid HTTP/HTTPS URL. "
                f"Example: 'http://localhost:8092'. Error: {e}"
            ) from None

    # Vision extraction settings (Florence-2, CLIP re-id, scene analysis)
    vision_extraction_enabled: bool = Field(
        default=True,
        description="Enable Florence-2 vision extraction for vehicle/person attributes",
    )
    image_quality_enabled: bool = Field(
        default=False,
        description="Enable BRISQUE image quality assessment (CPU-based). "
        "Currently disabled by default because pyiqa is incompatible with NumPy 2.0 "
        "(np.sctypes was removed). Set to True only if using NumPy <2.0.",
    )
    reid_enabled: bool = Field(
        default=True,
        description="Enable CLIP re-identification for tracking entities across cameras",
    )
    scene_change_enabled: bool = Field(
        default=True,
        description="Enable SSIM-based scene change detection",
    )
    reid_similarity_threshold: float = Field(
        default=0.85,
        ge=0.5,
        le=1.0,
        description="Cosine similarity threshold for re-identification matching (0.5-1.0)",
    )
    reid_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Time-to-live for re-identification embeddings in Redis (hours)",
    )
    reid_max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent re-identification operations (embedding generation, "
        "storage, and matching). Prevents resource exhaustion from too many simultaneous "
        "CLIP/Redis operations. Recommended: 5-20 depending on hardware.",
    )
    reid_embedding_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Timeout (seconds) for ReID embedding generation operations. "
        "Prevents hanging when CLIP service is slow or unresponsive. Default: 30.0 seconds.",
    )
    reid_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for ReID embedding generation on transient failures. "
        "Uses exponential backoff (2^attempt seconds). Default: 3 attempts.",
    )
    scene_change_threshold: float = Field(
        default=0.90,
        ge=0.5,
        le=1.0,
        description="SSIM threshold for scene change detection (below = change detected)",
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
    gpu_http_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="HTTP timeout (seconds) for GPU stats collection from AI containers. "
        "Prevents hanging when AI services are unresponsive. Default: 5.0 seconds.",
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
    dlq_circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of DLQ write failures before opening circuit breaker",
    )
    dlq_circuit_breaker_recovery_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Seconds to wait before attempting DLQ writes again after circuit opens",
    )
    dlq_circuit_breaker_half_open_max_calls: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum test calls allowed when circuit is half-open",
    )
    dlq_circuit_breaker_success_threshold: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Successful DLQ writes needed to close circuit from half-open state",
    )

    # Queue settings
    queue_max_size: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum size of Redis queues",
    )
    queue_overflow_policy: str = Field(
        default="dlq",
        description="Policy when queue is full: 'dlq' (moves to dead-letter queue), 'reject' (fails operation), or 'drop_oldest' (silent data loss, not recommended)",
    )
    queue_backpressure_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=1.0,
        description="Queue fill ratio (0.0-1.0) at which to start backpressure warnings",
    )

    # Video processing settings
    video_frame_interval_seconds: float = Field(
        default=2.0,
        ge=0.1,
        le=60.0,
        description="Interval between extracted video frames in seconds",
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
    rate_limit_export_requests_per_minute: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum export requests per minute per client IP. "
        "Lower limit to prevent abuse of CSV export functionality which "
        "could overload the server or be used for data exfiltration.",
    )
    trusted_proxy_ips: list[str] = Field(
        default=["127.0.0.1", "::1"],
        description="List of trusted proxy IP addresses. X-Forwarded-For headers are only "
        "processed from these IPs. Use CIDR notation for ranges (e.g., '10.0.0.0/8'). "
        "Common values: '127.0.0.1' (localhost), '10.0.0.0/8' (private), "
        "'172.16.0.0/12' (private), '192.168.0.0/16' (private)",
    )

    # WebSocket settings
    websocket_idle_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="WebSocket idle timeout in seconds. Connections without activity will be closed.",
    )
    websocket_ping_interval_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Interval for sending WebSocket ping frames to keep connections alive",
    )
    websocket_max_message_size: int = Field(
        default=65536,
        ge=1024,
        le=1048576,
        description="Maximum WebSocket message size in bytes (default: 64KB)",
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

    @field_validator("default_webhook_url", mode="before")
    @classmethod
    def validate_default_webhook_url(cls, v: Any) -> str | None:
        """Validate webhook URL with SSRF protection.

        This validates that the default webhook URL:
        1. Is a valid HTTP/HTTPS URL
        2. Does not point to private IP ranges
        3. Does not point to cloud metadata endpoints
        4. Uses HTTPS (or HTTP for localhost in dev mode)

        Args:
            v: The URL value to validate (can be None)

        Returns:
            The validated URL as a string, or None if not provided

        Raises:
            ValueError: If the URL fails SSRF validation
        """
        if v is None or v == "":
            return None

        # Convert to string if needed
        url_str = str(v)

        # First validate it's a valid URL format
        try:
            validated_url = AnyHttpUrl(url_str)
            url_str = str(validated_url)
        except Exception as e:
            raise ValueError(
                f"Invalid webhook URL '{url_str}': must be a valid HTTP/HTTPS URL. "
                f"Example: 'https://hooks.example.com/webhook'. Error: {e}"
            ) from None

        # Now validate SSRF protection (allow localhost HTTP in dev, skip DNS for config)
        try:
            validate_webhook_url_ssrf(url_str, allow_dev_http=True, resolve_dns=False)
        except SSRFValidationError as e:
            raise ValueError(f"Webhook URL blocked for security: {e}") from None

        return url_str

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

    # Video thumbnails settings
    video_thumbnails_dir: str = Field(
        default="data/thumbnails",
        description="Directory for storing video thumbnails and extracted frames",
    )
    video_max_frames: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum number of frames to extract from a video",
    )

    # Service health monitor settings
    ai_restart_enabled: bool = Field(
        default=True,
        description="Enable automatic restart of AI services (RT-DETRv2, Nemotron) on health check failure. "
        "Set to False in containerized deployments where restart scripts are not available. "
        "Health monitoring and status broadcasts still occur when disabled.",
    )

    # Container orchestrator settings (for Docker/Podman container management)
    # Environment variables use ORCHESTRATOR_ prefix (e.g., ORCHESTRATOR_ENABLED)
    orchestrator: OrchestratorSettings = Field(
        default_factory=OrchestratorSettings,
        description="Container orchestrator configuration for health monitoring and self-healing",
    )

    # TLS/HTTPS settings (legacy - DEPRECATED, use TLS_MODE instead)
    # These fields are kept for backward compatibility but will be removed in a future version.
    # Migration guide:
    #   TLS_ENABLED=true + TLS_CERT_FILE + TLS_KEY_FILE -> TLS_MODE=provided + TLS_CERT_PATH + TLS_KEY_PATH
    #   TLS_AUTO_GENERATE=true -> TLS_MODE=self_signed
    tls_enabled: bool = Field(
        default=False,
        description="DEPRECATED: Use TLS_MODE instead. Enable TLS/HTTPS for the API server.",
    )
    tls_cert_file: str | None = Field(
        default=None,
        description="DEPRECATED: Use TLS_CERT_PATH instead. Path to TLS certificate file (PEM format).",
    )
    tls_key_file: str | None = Field(
        default=None,
        description="DEPRECATED: Use TLS_KEY_PATH instead. Path to TLS private key file (PEM format).",
    )
    tls_ca_file: str | None = Field(
        default=None,
        description="DEPRECATED: Use TLS_CA_PATH instead. Path to CA certificate for client verification.",
    )
    tls_auto_generate: bool = Field(
        default=False,
        description="DEPRECATED: Use TLS_MODE=self_signed instead. Auto-generate self-signed certificates.",
    )
    tls_cert_dir: str = Field(
        default="data/certs",
        description="Directory for auto-generated certificates",
    )

    # TLS/HTTPS settings (new mode-based configuration)
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

    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, v: Any) -> str:
        """Validate Redis URL format.

        Ensures the URL has a valid Redis scheme (redis:// or rediss:// for TLS).

        Args:
            v: The URL value to validate

        Returns:
            The validated URL as a string

        Raises:
            ValueError: If the URL is not a valid Redis URL
        """
        if v is None:
            raise ValueError("Redis URL cannot be None")

        url_str = str(v)

        # Check for valid Redis URL schemes
        if not url_str.startswith(("redis://", "rediss://")):
            raise ValueError(
                f"Invalid Redis URL '{url_str}': must start with 'redis://' or 'rediss://' (for TLS). "
                "Example: 'redis://localhost:6379/0' or 'rediss://redis-host:6379/0'"
            )

        # Basic structure validation: should have host after scheme
        # redis://[password@]host[:port][/database]
        scheme_end = url_str.find("://") + 3
        rest = url_str[scheme_end:]

        if not rest or rest.startswith("/"):
            raise ValueError(
                f"Invalid Redis URL '{url_str}': missing host. Example: 'redis://localhost:6379/0'"
            )

        return url_str

    @field_validator("redis_ssl_cert_reqs")
    @classmethod
    def validate_redis_ssl_cert_reqs(cls, v: str) -> str:
        """Validate Redis SSL certificate verification mode."""
        valid_modes = {"none", "optional", "required"}
        v_lower = v.lower()
        if v_lower not in valid_modes:
            raise ValueError(
                f"redis_ssl_cert_reqs must be one of: {', '.join(valid_modes)}. Got: '{v}'"
            )
        return v_lower

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate PostgreSQL database URL format."""
        if not v:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Set it in your .env file or environment. "
                "Example: DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname"  # pragma: allowlist secret
            )
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
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
