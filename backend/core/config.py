"""Application configuration using Pydantic Settings."""

__all__ = [
    # Classes
    "OrchestratorSettings",
    "Settings",
    "TranscodeCacheSettings",
    # Functions
    "get_settings",
]

import os
import sys
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.sanitization import URLValidationError, validate_grafana_url
from backend.core.url_validation import SSRFValidationError
from backend.core.url_validation import validate_webhook_url as validate_webhook_url_ssrf


def _get_default_inference_limit() -> int:
    """Get default inference limit based on Python capabilities.

    Returns a higher concurrency limit when running on free-threaded Python
    (3.13t/3.14t with GIL disabled) to leverage true thread parallelism.

    Returns:
        Default limit: 20 for free-threaded Python, 4 for standard Python.
    """
    # Python 3.13+ exposes sys._is_gil_enabled() to check GIL status
    if hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled():
        return 20  # Higher limit with true parallelism
    return 4  # Conservative limit with GIL


class TranscodeCacheSettings(BaseSettings):
    """Transcoding cache configuration for disk-based video transcode caching.

    This settings model configures the transcode cache service that provides
    LRU-based caching of transcoded videos to avoid repeated transcoding.

    Environment variables use the TRANSCODE_CACHE_ prefix (e.g., TRANSCODE_CACHE_DIR).
    """

    model_config = SettingsConfigDict(
        env_prefix="TRANSCODE_CACHE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Cache location
    cache_dir: str = Field(
        default="data/transcode_cache",
        description="Directory for storing transcoded video cache files. "
        "Relative paths are resolved from the application root.",
    )

    # Size limits
    max_cache_size_gb: float = Field(
        default=10.0,
        ge=0.1,
        le=1000.0,
        description="Maximum cache size in gigabytes. When exceeded, LRU eviction "
        "removes least recently accessed files until below cleanup_target_percent.",
    )
    max_file_age_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Maximum age in days before a cached file is eligible for eviction, "
        "regardless of LRU status. Files older than this are evicted first.",
    )

    # Cleanup thresholds
    cleanup_threshold_percent: float = Field(
        default=0.9,
        ge=0.5,
        le=0.99,
        description="Trigger cleanup when cache reaches this percentage of max_cache_size_gb. "
        "Default: 0.9 (90%). Cleanup removes files until below cleanup_target_percent.",
    )
    cleanup_target_percent: float = Field(
        default=0.8,
        ge=0.3,
        le=0.95,
        description="Target percentage of max_cache_size_gb after cleanup. "
        "Default: 0.8 (80%). Must be less than cleanup_threshold_percent.",
    )

    # Locking
    lock_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout in seconds for cache operation locks. "
        "Prevents deadlocks when multiple processes access the cache.",
    )

    # Feature flag
    enabled: bool = Field(
        default=True,
        description="Enable transcoding cache. When disabled, all transcode operations "
        "bypass the cache and transcode on every request.",
    )


class OrchestratorSettings(BaseSettings):
    """Container orchestrator configuration for Docker/Podman container management.

    This settings model configures the container orchestrator service that provides
    health monitoring and self-healing capabilities for AI containers (YOLO26,
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

    # Container service port configuration
    # Infrastructure services
    postgres_port: int = Field(
        5432,
        ge=1,
        le=65535,
        description="PostgreSQL container service port for health checks.",
    )
    redis_port: int = Field(
        6379,
        ge=1,
        le=65535,
        description="Redis container service port for health checks.",
    )

    # AI services
    yolo26_port: int = Field(
        8095,
        ge=1,
        le=65535,
        description="YOLO26 (ai-yolo26) container service port for health checks.",
    )
    nemotron_port: int = Field(
        8091,
        ge=1,
        le=65535,
        description="Nemotron (ai-llm) container service port for health checks.",
    )
    florence_port: int = Field(
        8092,
        ge=1,
        le=65535,
        description="Florence-2 (ai-florence) container service port for health checks.",
    )
    clip_port: int = Field(
        8093,
        ge=1,
        le=65535,
        description="CLIP (ai-clip) container service port for health checks.",
    )
    enrichment_port: int = Field(
        8094,
        ge=1,
        le=65535,
        description="Enrichment (ai-enrichment) container service port for health checks.",
    )

    # Monitoring services
    prometheus_port: int = Field(
        9090,
        ge=1,
        le=65535,
        description="Prometheus container service port for health checks.",
    )
    grafana_port: int = Field(
        3000,
        ge=1,
        le=65535,
        description="Grafana container service port for health checks.",
    )
    redis_exporter_port: int = Field(
        9121,
        ge=1,
        le=65535,
        description="Redis Exporter container service port for health checks.",
    )
    json_exporter_port: int = Field(
        7979,
        ge=1,
        le=65535,
        description="JSON Exporter container service port for health checks.",
    )
    alertmanager_port: int = Field(
        9093,
        ge=1,
        le=65535,
        description="Alertmanager container service port for health checks.",
    )
    blackbox_exporter_port: int = Field(
        9115,
        ge=1,
        le=65535,
        description="Blackbox Exporter container service port for health checks.",
    )
    jaeger_port: int = Field(
        16686,
        ge=1,
        le=65535,
        description="Jaeger UI container service port for health checks.",
    )
    frontend_port: int = Field(
        8080,
        ge=1,
        le=65535,
        description="Frontend container internal service port for health checks.",
    )

    # Monitoring feature flag
    monitoring_enabled: bool = Field(
        True,
        description="Enable monitoring services management. When True, orchestrator "
        "will manage monitoring containers (prometheus, grafana, exporters).",
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
    # Development: postgresql+asyncpg://user:pass@localhost:5432/security (local dev on standard port 5432)  # pragma: allowlist secret
    # Docker: postgresql+asyncpg://user:pass@postgres:5432/security (container network with standard port 5432)  # pragma: allowlist secret
    # Example: postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret
    database_url: str = Field(
        default="",
        description="PostgreSQL database URL (format: postgresql+asyncpg://user:pass@host:port/db). Development: localhost:5432, Docker: postgres:5432",  # pragma: allowlist secret
    )

    # Read replica configuration (NEM-3392)
    # Optional read replica URL for routing read-heavy operations to replicas
    # If not set, all operations use the primary database_url
    # Example: postgresql+asyncpg://security:password@replica-host:5432/security  # pragma: allowlist secret
    database_url_read: str | None = Field(
        default=None,
        description="Optional PostgreSQL read replica URL for read-heavy operations. "
        "If not set, read operations use the primary database. "
        "Format: postgresql+asyncpg://user:pass@replica-host:port/db",  # pragma: allowlist secret
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
    use_pgbouncer: bool = Field(
        default=False,
        description="Enable PgBouncer transaction mode compatibility. When True, disables "
        "prepared statement cache (statement_cache_size=0) since PgBouncer in transaction "
        "mode doesn't support prepared statements. Required when connecting through PgBouncer "
        "for connection multiplexing. NEM-3419.",
    )

    # Connection pool warming (NEM-3757)
    # Pre-establishes database connections at startup to reduce cold-start latency
    database_pool_warming_enabled: bool = Field(
        default=True,
        description="Enable connection pool warming on startup. When enabled, pre-establishes "
        "a configurable number of database connections during application startup to reduce "
        "cold-start latency for the first requests. Recommended for production deployments.",
    )
    database_pool_warming_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of connections to pre-establish during pool warming. Should be "
        "less than or equal to database_pool_size. Higher values reduce cold-start latency "
        "but increase startup time. Recommended: 5-10 for most deployments.",
    )
    database_pool_warming_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Maximum time in seconds to wait for pool warming to complete. If pool "
        "warming exceeds this timeout, startup continues with partially warmed pool.",
    )
    # Prepared statement cache configuration (NEM-3760)
    prepared_statement_cache_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum number of prepared statements to cache for query plan reuse. "
        "Higher values can improve performance for applications with many distinct queries. "
        "Automatically disabled when use_pgbouncer=True. NEM-3760.",
    )

    # Redis configuration
    # Development: redis://localhost:6379/0 (local dev)
    # Docker: redis://redis:6379/0 (container network with standard port 6379)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL. Development: redis://localhost:6379/0, Docker: redis://redis:6379/0",
    )
    redis_password: SecretStr | None = Field(
        default=None,
        description="Redis password for authentication. Optional for local development (no password). "
        "Set via REDIS_PASSWORD environment variable for production deployments. "
        "Must match the `requirepass` value configured in Redis.",
    )
    redis_event_channel: str = Field(
        default="security_events",
        description="Redis pub/sub channel for security events",
    )
    redis_pubsub_shard_count: int = Field(
        default=16,
        ge=1,
        le=256,
        description="Number of shards for Redis pub/sub channel distribution (NEM-3415). "
        "Events are distributed across shards using consistent hashing on camera_id. "
        "More shards reduce per-channel load but increase subscription complexity. "
        "Default: 16 shards. Recommended: 8-32 for most deployments.",
    )
    redis_key_prefix: str = Field(
        default="hsi",
        description="Global prefix for all Redis keys. Enables key isolation for "
        "multi-instance deployments and blue-green deployments. All cache keys, "
        "queue names, and other Redis keys will be prefixed with '{prefix}:'.",
    )

    # Redis connection pool settings (NEM-3368)
    # Pool size should be tuned based on concurrent operations (file watcher, workers, API)
    redis_pool_size: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Total pool size when dedicated pools are disabled.",
    )
    redis_pool_dedicated_enabled: bool = Field(
        default=True,
        description="Enable dedicated connection pools by workload type.",
    )
    redis_pool_size_cache: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Max connections for cache operations.",
    )
    redis_pool_size_queue: int = Field(
        default=15,
        ge=3,
        le=100,
        description="Max connections for queue operations.",
    )
    redis_pool_size_pubsub: int = Field(
        default=10,
        ge=2,
        le=50,
        description="Max connections for pub/sub operations.",
    )
    redis_pool_size_ratelimit: int = Field(
        default=10,
        ge=2,
        le=50,
        description="Max connections for rate limiting operations.",
    )

    # Redis Sentinel settings for high availability (NEM-3413)
    redis_use_sentinel: bool = Field(
        default=False,
        description="Enable Redis Sentinel for high availability. "
        "When True, connects via Sentinel for automatic failover. "
        "Requires redis_sentinel_hosts to be configured.",
    )
    redis_sentinel_master_name: str = Field(
        default="mymaster",
        description="Name of the Redis master as configured in Sentinel. "
        "Must match the 'sentinel monitor <master-name>' directive in sentinel.conf.",
    )
    redis_sentinel_hosts: str = Field(
        default="sentinel1:26379,sentinel2:26379,sentinel3:26379",
        description="Comma-separated list of Sentinel host:port pairs. "
        "Example: 'sentinel1:26379,sentinel2:26379,sentinel3:26379'. "
        "At least 3 Sentinels recommended for quorum.",
    )
    redis_sentinel_socket_timeout: float = Field(
        default=0.1,
        ge=0.05,
        le=5.0,
        description="Socket timeout in seconds for Sentinel connections. "
        "Low value (0.1s) enables fast failover detection. "
        "Increase if experiencing false failovers due to network latency.",
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

    # Redis memory optimization settings (NEM-3416)
    redis_memory_limit_mb: int = Field(
        default=0,
        ge=0,
        le=131072,
        description="Redis maximum memory limit in megabytes. "
        "Set to 0 to disable memory limit (use Redis server defaults). "
        "Development: 256MB recommended. Production: 1024-4096MB depending on workload. "
        "When limit is reached, eviction policy determines behavior.",
    )
    redis_memory_policy: str = Field(
        default="volatile-lru",
        description="Redis eviction policy when memory limit is reached. Options: "
        "'volatile-lru' (evict keys with TTL using LRU, default, protects persistent data), "
        "'allkeys-lru' (evict any key using LRU), "
        "'volatile-ttl' (evict keys with shortest TTL), "
        "'volatile-random' (random eviction of keys with TTL), "
        "'allkeys-random' (random eviction of any key), "
        "'noeviction' (return errors when memory full). "
        "Recommended: 'volatile-lru' for cache-heavy workloads with TTL-based expiration.",
    )
    redis_memory_apply_on_startup: bool = Field(
        default=False,
        description="Apply memory settings to Redis server on application startup. "
        "When True, sends CONFIG SET commands to configure maxmemory and maxmemory-policy. "
        "Requires Redis ACL permissions for CONFIG command. "
        "Set to False if Redis is configured externally (e.g., via redis.conf).",
    )

    # Redis Cluster settings for horizontal scalability (NEM-3761)
    redis_cluster_enabled: bool = Field(
        default=False,
        description="Enable Redis Cluster mode for horizontal scalability. "
        "When True, connects to a Redis Cluster instead of a single instance. "
        "Requires redis_cluster_nodes to be configured with cluster node addresses.",
    )
    redis_cluster_nodes: str = Field(
        default="redis-node1:6379,redis-node2:6379,redis-node3:6379",
        description="Comma-separated list of Redis Cluster node host:port pairs. "
        "Example: 'redis-node1:6379,redis-node2:6379,redis-node3:6379'. "
        "At least 3 master nodes recommended for high availability.",
    )
    redis_cluster_read_from_replicas: bool = Field(
        default=True,
        description="Allow read operations from cluster replica nodes. "
        "When True, distributes read load across replicas for better performance. "
        "Set to False if strong read consistency is required.",
    )
    redis_cluster_max_connections_per_node: int = Field(
        default=10,
        ge=2,
        le=50,
        description="Maximum connections per cluster node. "
        "Total connections = max_connections_per_node * number_of_nodes.",
    )

    # HyperLogLog settings for unique entity counting (NEM-3414)
    hll_ttl_seconds: int = Field(
        default=86400,
        ge=3600,
        le=604800,
        description="TTL in seconds for HyperLogLog keys used for unique counting. "
        "Default: 86400 (24 hours). Max: 604800 (7 days). "
        "Longer TTL provides better historical analysis but uses more memory (~12KB per HLL).",
    )
    hll_key_prefix: str = Field(
        default="hll",
        description="Prefix for HyperLogLog keys. Keys are formatted as {prefix}:{metric}:{time_window}. "
        "Example: hll:unique_cameras:2024-01-15 for daily unique camera counts.",
    )

    # Cache TTL settings (NEM-2519)
    cache_default_ttl: int = Field(
        default=300,
        ge=10,
        le=86400,
        description="Default cache TTL in seconds (5 minutes). Used when no specific TTL is provided.",
    )
    cache_short_ttl: int = Field(
        default=60,
        ge=5,
        le=3600,
        description="Short cache TTL in seconds (1 minute). Used for frequently changing data.",
    )
    cache_long_ttl: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Long cache TTL in seconds (1 hour). Used for rarely changing data.",
    )

    # Stale-While-Revalidate (SWR) cache settings (NEM-3367)
    cache_swr_stale_ttl: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Stale TTL in seconds for SWR pattern. After TTL expires but within "
        "stale_ttl, cached data is returned while revalidating in background.",
    )
    cache_swr_enabled: bool = Field(
        default=True,
        description="Enable Stale-While-Revalidate caching pattern. When enabled, "
        "stale cached data is returned immediately while refreshing in background.",
    )

    snapshot_cache_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="TTL in seconds for cached camera snapshots extracted from videos. Default: 1 hour.",
    )

    # Cache warming settings (NEM-3762)
    cache_warming_enabled: bool = Field(
        default=True,
        description="Enable cache warming on application startup. "
        "Pre-populates frequently accessed cache keys to reduce cold-start latency.",
    )
    cache_warming_strategy: str = Field(
        default="parallel",
        description="Cache warming strategy: "
        "'parallel' (warm all caches concurrently, faster startup), "
        "'sequential' (warm one cache at a time, lower resource usage), "
        "'eager' (alias for parallel), "
        "'lazy' (disable warming, caches populated on first access).",
    )
    cache_warming_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Maximum time in seconds to wait for cache warming to complete. "
        "Warming failures don't block startup but are logged.",
    )

    # Internal service timeout settings (NEM-2519)
    degradation_health_check_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Timeout (seconds) for degradation manager health checks. "
        "Default: 10.0 seconds. Applies to service health monitoring during degradation.",
    )
    ai_broadcast_health_timeout: float = Field(
        default=1.0,
        ge=0.5,
        le=10.0,
        description="Timeout (seconds) for AI service health checks in system broadcaster. "
        "Keep short to avoid blocking the broadcast loop. Default: 1.0 seconds.",
    )

    # Job management settings (NEM-2519)
    completed_job_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="TTL in seconds for completed/failed jobs in Redis. "
        "Default: 3600 (1 hour). Jobs are cleaned up after this period.",
    )
    default_job_timeout: int = Field(
        default=600,
        ge=60,
        le=86400,
        description="Default timeout (seconds) for background jobs without specific timeout. "
        "Default: 600 (10 minutes).",
    )

    # Pagination settings (NEM-2591)
    pagination_max_limit: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum allowed limit for paginated API endpoints. "
        "Requests with limit values exceeding this will receive a 400 error. "
        "Default: 1000. Configurable via PAGINATION_MAX_LIMIT env var.",
    )
    pagination_default_limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Default limit for paginated API endpoints when not specified. "
        "Default: 50. Configurable via PAGINATION_DEFAULT_LIMIT env var.",
    )

    # Application settings
    app_name: str = "Home Security Intelligence"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = Field(
        default="production",
        description="Deployment environment: 'production', 'staging', or 'development'. "
        "Used for log tagging and environment-specific behavior. "
        "Set via ENVIRONMENT env var.",
    )

    # Admin endpoints settings
    # SECURITY: Admin endpoints require BOTH debug=True AND admin_enabled=True
    # This provides defense-in-depth against accidentally exposing admin endpoints
    admin_enabled: bool = Field(
        default=False,
        description="Enable admin endpoints (requires debug=True as well). "
        "SECURITY: Must be explicitly enabled - provides protection against "
        "accidentally enabling admin endpoints in production.",
    )
    admin_api_key: SecretStr | None = Field(
        default=None,
        description="Optional API key required for admin endpoints. "
        "When set, all admin requests must include X-Admin-API-Key header.",
    )

    # API settings
    # Backend always runs on port 8000 (standard for FastAPI development)
    # Development: 0.0.0.0:8000 (accessible from host machine)
    # Docker: 0.0.0.0:8000 (standard port 8000 within container, mapped externally in compose file)
    api_host: str = Field(
        default="0.0.0.0",  # noqa: S104
        description="API server host address. Development/Docker: 0.0.0.0 (all interfaces)",
    )
    api_port: int = Field(
        default=8000,
        gt=0,
        le=65535,
        description="API server port. Standard: 8000 (development and Docker container)",
    )

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
    file_watcher_max_concurrent_queue: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum concurrent Redis queue operations from file watcher. "
        "Limits connection usage during bulk file uploads to prevent pool exhaustion.",
    )
    file_watcher_queue_delay_ms: int = Field(
        default=50,
        ge=0,
        le=1000,
        description="Delay in milliseconds between queue operations during bulk processing. "
        "Helps spread load when many files are detected simultaneously.",
    )

    # Retention settings
    retention_days: int = Field(
        default=30,
        gt=0,
        description="Number of days to retain events and detections",
    )

    # Batch processing settings
    batch_window_seconds: int = Field(
        default=90,
        gt=0,
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
    batch_max_detections: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum detections per batch before splitting (NEM-1726). "
        "When a batch reaches this limit, it is closed and a new batch is created. "
        "Prevents memory exhaustion and LLM timeouts with large batches.",
    )

    # AI service endpoints (validated as URLs using Pydantic AnyHttpUrl)
    # Stored as str after validation for compatibility with httpx clients
    # YOLO26 Detector Settings
    # Development: http://localhost:8095 (local dev)
    # Docker: http://ai-yolo26:8095 (container network)
    yolo26_url: str = Field(
        default="http://ai-yolo26:8095",
        description="URL of the YOLO26 detection service",
    )
    # Development: http://localhost:8091 (local dev)
    # Docker: http://ai-llm:8091 (container network)
    nemotron_url: str = Field(
        default="http://localhost:8091",
        description="Nemotron reasoning service URL (llama.cpp server). Development: http://localhost:8091, Docker: http://ai-llm:8091",
    )

    # AI service authentication
    # Security: API keys for authenticating with AI services
    yolo26_api_key: SecretStr | None = Field(
        default=None,
        description="Optional API key for YOLO26 service authentication",
    )
    nemotron_api_key: SecretStr | None = Field(
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
    yolo26_read_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Read timeout for YOLO26 inference requests (seconds)",
    )
    yolo26_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="YOLO26 detection confidence threshold",
    )
    nemotron_read_timeout: float = Field(
        default=120.0,
        ge=30.0,
        le=600.0,
        description="Maximum time (seconds) to wait for Nemotron LLM response",
    )
    florence_read_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Maximum time (seconds) to wait for Florence-2 vision-language response. "
        "Florence-2 is faster than LLMs but processes images, so 30s default allows for "
        "complex operations like dense captioning and OCR.",
    )
    clip_read_timeout: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Maximum time (seconds) to wait for CLIP embedding generation. "
        "CLIP is fast for single embeddings but batch operations may take longer.",
    )
    enrichment_read_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=180.0,
        description="Maximum time (seconds) to wait for enrichment service response. "
        "The enrichment service handles multiple AI models (vehicle classification, "
        "pet classification, clothing analysis, depth estimation, pose analysis), "
        "so longer timeout accommodates complex multi-model operations.",
    )

    # AI service retry settings
    detector_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for YOLO26 detector on transient failures. "
        "Uses exponential backoff (2^attempt seconds, capped at 30s). Default: 3 attempts.",
    )
    nemotron_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for Nemotron LLM on transient failures. "
        "Uses exponential backoff (2^attempt seconds, capped at 30s). Default: 3 attempts.",
    )

    # Nemotron context window settings (NEM-1723)
    nemotron_context_window: int = Field(
        default=131072,
        ge=1000,
        le=131072,
        description="Nemotron context window size in tokens. "
        "Production (Nemotron-3-Nano-30B-A3B): 131,072 tokens (128K). "
        "Development (Nemotron Mini 4B): 4,096 tokens. "
        "Prompts exceeding (context_window - max_output_tokens) will be truncated.",
    )
    nemotron_max_output_tokens: int = Field(
        default=1536,
        ge=100,
        le=8192,
        description="Maximum tokens reserved for Nemotron LLM output. "
        "Input prompts are validated against (context_window - max_output_tokens). "
        "Default: 1536 tokens.",
    )

    # Nemotron Structured Generation Settings (NEM-3726)
    # NVIDIA NIM's guided_json parameter enforces valid JSON output
    nemotron_use_guided_json: bool = Field(
        default=True,
        description="Enable NVIDIA NIM structured generation via guided_json parameter. "
        "When enabled and the endpoint supports it, the LLM response will be constrained "
        "to the RISK_ANALYSIS_JSON_SCHEMA, ensuring valid JSON output. "
        "If the endpoint doesn't support guided_json, falls back to regex parsing.",
    )
    nemotron_guided_json_fallback: bool = Field(
        default=True,
        description="Enable fallback to regex parsing when guided_json is not supported "
        "by the endpoint or when guided_json request fails. "
        "When disabled and guided_json fails, the request will raise an error.",
    )

    enrichment_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for enrichment service on transient failures "
        "(ConnectError, TimeoutException). Uses exponential backoff with jitter "
        "(2^attempt seconds with +/-10% jitter, capped at 30s). Default: 3 attempts.",
    )

    # AI service concurrency settings (NEM-1463)
    # Default dynamically set based on Python runtime (free-threading support)
    ai_max_concurrent_inferences: int = Field(
        default_factory=_get_default_inference_limit,
        ge=1,
        le=32,
        description="Maximum concurrent AI inference operations (YOLO26 detection + Nemotron analysis). "
        "Limits GPU/AI service load under high traffic. Set lower for constrained GPU VRAM, "
        "higher for distributed AI services. Default: 20 for free-threaded Python, 4 for standard Python.",
    )

    context_utilization_warning_threshold: float = Field(
        default=0.80,
        ge=0.5,
        le=0.95,
        description="Log warning when context utilization exceeds this threshold (0.5-0.95). "
        "Helps identify prompts approaching context limits before truncation occurs.",
    )
    context_truncation_enabled: bool = Field(
        default=True,
        description="Enable intelligent truncation of enrichment data when approaching context limits. "
        "When enabled, less critical enrichment data is removed to fit within context window. "
        "When disabled, prompts exceeding limits will fail with an error.",
    )
    llm_tokenizer_encoding: str = Field(
        default="cl100k_base",
        description="Tiktoken encoding to use for token counting. Options: 'cl100k_base' (GPT-4/ChatGPT), "
        "'p50k_base' (Codex), 'r50k_base' (GPT-2). cl100k_base is a reasonable default for most LLMs.",
    )

    # AI Model Cold Start and Warmup Settings (NEM-1670)
    ai_warmup_enabled: bool = Field(
        default=True,
        description="Enable model warmup on service startup. Sends test inference to preload "
        "model weights into GPU memory, reducing first-request latency. Default: enabled.",
    )
    ai_cold_start_threshold_seconds: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Seconds since last inference before model is considered 'cold'. "
        "Cold models may have slower first inference due to GPU memory paging. "
        "Default: 300 seconds (5 minutes).",
    )
    nemotron_warmup_prompt: str = Field(
        default="Hello, please respond with 'ready' to confirm you are operational.",
        description="Test prompt used for Nemotron warmup. Should be simple and quick to process.",
    )

    @field_validator("yolo26_url", "nemotron_url", mode="before")
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
    # Development: http://localhost:8092, http://localhost:8093, http://localhost:8094 (local dev)
    # Docker: http://ai-florence:8092, http://ai-clip:8093, http://ai-enrichment:8094 (container network)
    florence_url: str = Field(
        default="http://localhost:8092",
        description="Florence-2 vision-language service URL. Development: http://localhost:8092, Docker: http://ai-florence:8092",
    )
    clip_url: str = Field(
        default="http://localhost:8093",
        description="CLIP embedding service URL for re-identification. Development: http://localhost:8093, Docker: http://ai-clip:8093",
    )
    enrichment_url: str = Field(
        default="http://localhost:8094",
        description="Heavy enrichment service URL for vehicle, clothing, demographics, action models. Development: http://localhost:8094, Docker: http://ai-enrichment:8094",
    )
    enrichment_light_url: str = Field(
        default="http://localhost:8096",
        description="Light enrichment service URL for pose, threat, reid, pet, depth models. Development: http://localhost:8096, Docker: http://ai-enrichment-light:8096",
    )
    use_enrichment_service: bool = Field(
        default=True,
        description="Use HTTP enrichment service instead of local models for vehicle/pet/clothing classification",
    )

    # Enrichment Model Assignment Configuration
    # Each model can be assigned to "heavy" (GPU 0, ai-enrichment:8094) or "light" (GPU 1, ai-enrichment-light:8096)
    # This allows flexible distribution of models across GPUs based on VRAM and compute requirements
    enrichment_pose_service: str = Field(
        default="light",
        description="Service for pose estimation model: 'heavy' or 'light'. YOLOv8n-pose (~300MB) recommended for light.",
    )
    enrichment_threat_service: str = Field(
        default="light",
        description="Service for threat detection model: 'heavy' or 'light'. YOLOv8n (~400MB) recommended for light.",
    )
    enrichment_reid_service: str = Field(
        default="light",
        description="Service for person re-ID model: 'heavy' or 'light'. OSNet-x0.25 (~100MB) recommended for light.",
    )
    enrichment_pet_service: str = Field(
        default="light",
        description="Service for pet classification model: 'heavy' or 'light'. ResNet-18 (~200MB) recommended for light.",
    )
    enrichment_depth_service: str = Field(
        default="light",
        description="Service for depth estimation model: 'heavy' or 'light'. DepthAnything-small (~150MB) recommended for light.",
    )
    enrichment_vehicle_service: str = Field(
        default="heavy",
        description="Service for vehicle classification model: 'heavy' or 'light'. ResNet-50 (~1.5GB) recommended for heavy.",
    )
    enrichment_clothing_service: str = Field(
        default="heavy",
        description="Service for clothing classification model: 'heavy' or 'light'. FashionCLIP (~800MB) recommended for heavy.",
    )
    enrichment_action_service: str = Field(
        default="heavy",
        description="Service for action recognition model: 'heavy' or 'light'. X-CLIP (~1.5GB) recommended for heavy.",
    )
    enrichment_demographics_service: str = Field(
        default="heavy",
        description="Service for demographics model: 'heavy' or 'light'. FairFace (~500MB) recommended for heavy.",
    )

    @field_validator(
        "enrichment_pose_service",
        "enrichment_threat_service",
        "enrichment_reid_service",
        "enrichment_pet_service",
        "enrichment_depth_service",
        "enrichment_vehicle_service",
        "enrichment_clothing_service",
        "enrichment_action_service",
        "enrichment_demographics_service",
        mode="before",
    )
    @classmethod
    def validate_enrichment_service_assignment(cls, v: Any) -> str:
        """Validate enrichment service assignment is 'heavy' or 'light'."""
        if v is None:
            return "heavy"  # Default to heavy service
        value = str(v).lower().strip()
        if value not in ("heavy", "light"):
            raise ValueError(f"Invalid service assignment '{v}'. Must be 'heavy' or 'light'.")
        return value

    def get_enrichment_url_for_model(self, model: str) -> str:
        """Get the enrichment service URL for a specific model.

        Args:
            model: Model name (pose, threat, reid, pet, depth, vehicle, clothing, action, demographics)

        Returns:
            The URL for the service hosting that model
        """
        service_map = {
            "pose": self.enrichment_pose_service,
            "threat": self.enrichment_threat_service,
            "reid": self.enrichment_reid_service,
            "pet": self.enrichment_pet_service,
            "depth": self.enrichment_depth_service,
            "vehicle": self.enrichment_vehicle_service,
            "clothing": self.enrichment_clothing_service,
            "action": self.enrichment_action_service,
            "demographics": self.enrichment_demographics_service,
        }
        service = service_map.get(model, "heavy")
        return self.enrichment_light_url if service == "light" else self.enrichment_url

    def get_models_for_service(self, service: str) -> list[str]:
        """Get list of models assigned to a specific service.

        Args:
            service: Service name ('heavy' or 'light')

        Returns:
            List of model names assigned to that service
        """
        all_models = {
            "pose": self.enrichment_pose_service,
            "threat": self.enrichment_threat_service,
            "reid": self.enrichment_reid_service,
            "pet": self.enrichment_pet_service,
            "depth": self.enrichment_depth_service,
            "vehicle": self.enrichment_vehicle_service,
            "clothing": self.enrichment_clothing_service,
            "action": self.enrichment_action_service,
            "demographics": self.enrichment_demographics_service,
        }
        return [model for model, svc in all_models.items() if svc == service]

    # Monitoring URLs
    # Note: Default /grafana uses nginx proxy for remote access compatibility.
    # Override with GRAFANA_URL env var if accessing Grafana directly (e.g., http://localhost:3002)
    grafana_url: str = Field(
        default="/grafana",
        description="Grafana dashboard URL for frontend embed (use /grafana for proxied access)",
    )

    @field_validator("grafana_url", mode="before")
    @classmethod
    def validate_grafana_url_field(cls, v: Any) -> str:
        """Validate Grafana URL with SSRF protection (NEM-1077).

        This validates that the Grafana URL:
        1. Is a valid HTTP/HTTPS URL or relative path (e.g., /grafana)
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
            return "/grafana"  # Default to proxied path for remote access

        url_str = str(v)

        # Allow relative paths like /grafana for nginx proxy
        if url_str.startswith("/"):
            return url_str

        try:
            return validate_grafana_url(url_str)
        except URLValidationError as e:
            raise ValueError(f"Invalid Grafana URL: {e}") from None

    prometheus_url: str = Field(
        default="http://prometheus:9090",
        description="Prometheus server URL for monitoring health checks. "
        "Development: http://localhost:9090 (local dev on standard port 9090). "
        "Docker: http://prometheus:9090 (container network, standard port 9090)",
    )

    # Frontend URL for health checks (internal Docker network URL)
    # Development: http://localhost:5173 (local Vite dev server)
    # Docker: http://frontend:8080 (nginx-unprivileged on container network with internal port 8080)
    frontend_url: str = Field(
        default="http://frontend:8080",
        description="Frontend container URL for health checks. "
        "Development: http://localhost:5173 (Vite dev server on standard port 5173). "
        "Docker: http://frontend:8080 (nginx-unprivileged on standard internal port 8080)",
    )

    @field_validator(
        "florence_url", "clip_url", "enrichment_url", "enrichment_light_url", mode="before"
    )
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

    # Florence-2 feature toggles (granular control)
    florence_scene_captions_enabled: bool = Field(
        default=True,
        description="Enable Florence-2 detailed scene captions. When enabled, generates rich "
        "scene descriptions using DETAILED_CAPTION_TASK for enhanced LLM context. "
        "Disable to reduce API calls if scene captions are not needed.",
    )
    florence_detection_captions_enabled: bool = Field(
        default=True,
        description="Enable Florence-2 captions for individual detections (vehicles, persons). "
        "When enabled, generates descriptive captions for each detected object. "
        "Disable to reduce API calls when only structured attributes are needed.",
    )
    florence_vqa_enabled: bool = Field(
        default=True,
        description="Enable Florence-2 Visual Question Answering for detailed attribute extraction. "
        "When enabled, uses VQA to extract vehicle color, type, person clothing, etc. "
        "Disable to rely only on basic captions for attribute extraction.",
    )

    image_quality_enabled: bool = Field(
        default=True,
        description="Enable BRISQUE image quality assessment (CPU-based). "
        "Provides quality scores to help identify blurry, noisy, or degraded images.",
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
    api_keys: list[SecretStr] = Field(
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

    # OpenTelemetry settings (NEM-1629)
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry distributed tracing. When enabled, traces are "
        "collected and exported to the configured OTLP endpoint (e.g., Jaeger, Tempo).",
    )
    otel_service_name: str = Field(
        default="nemotron-backend",
        description="Service name for OpenTelemetry traces. Used to identify this service "
        "in distributed tracing dashboards.",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC endpoint for trace export. Default uses Jaeger's OTLP port. "
        "Examples: 'http://jaeger:4317' (Docker), 'http://localhost:4317' (local dev).",
    )
    otel_exporter_otlp_insecure: bool = Field(
        default=True,
        description="Use insecure (non-TLS) connection to OTLP endpoint. Set to False "
        "for production deployments with TLS-enabled collectors.",
    )
    otel_trace_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate (0.0-1.0). Set to 1.0 to trace all requests, "
        "lower values for high-traffic production environments to reduce overhead.",
    )

    # BatchSpanProcessor tuning for high-throughput scenarios (NEM-3433)
    # These settings optimize trace export for production workloads (100+ spans/sec)
    otel_batch_max_queue_size: int = Field(
        default=8192,
        ge=512,
        le=65536,
        description="Maximum number of spans queued before dropping. Higher values "
        "allow more buffering during traffic spikes but use more memory. "
        "Default: 8192 (suitable for 100+ spans/sec).",
    )
    otel_batch_max_export_batch_size: int = Field(
        default=1024,
        ge=64,
        le=8192,
        description="Maximum number of spans exported per batch. Larger batches "
        "reduce export overhead but increase latency and memory usage. "
        "Default: 1024 (balanced for high-throughput).",
    )
    otel_batch_schedule_delay_ms: int = Field(
        default=2000,
        ge=100,
        le=30000,
        description="Delay in milliseconds between batch exports. Lower values "
        "reduce trace latency but increase export frequency. "
        "Default: 2000ms (2 seconds).",
    )
    otel_batch_export_timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="Timeout in milliseconds for exporting a batch of spans. "
        "Default: 30000ms (30 seconds).",
    )

    # Priority-based sampling settings (NEM-3793)
    # These settings control intelligent trace sampling to reduce telemetry volume
    # while preserving important traces (errors, high-risk events, critical endpoints)
    otel_sampling_error_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for error traces (0.0-1.0). "
        "Default: 1.0 (always sample errors for debugging).",
    )
    otel_sampling_high_risk_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for high-risk security events (0.0-1.0). "
        "Default: 1.0 (always sample high-risk events with risk_score >= 70).",
    )
    otel_sampling_high_priority_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for high-priority endpoints like /api/events, /api/alerts (0.0-1.0). "
        "Default: 1.0 (always sample critical API endpoints).",
    )
    otel_sampling_medium_priority_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sampling rate for medium-priority endpoints like /api/timeline (0.0-1.0). "
        "Default: 0.5 (sample 50% of medium-priority requests).",
    )
    otel_sampling_background_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Sampling rate for background tasks like /health, /metrics (0.0-1.0). "
        "Default: 0.1 (sample 10% of background tasks to reduce noise).",
    )
    otel_sampling_default_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Default sampling rate for unclassified spans (0.0-1.0). "
        "Default: 0.1 (sample 10% of unclassified requests).",
    )

    # Logging settings
    log_level: str = Field(
        default="WARNING",
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

    # Request timing settings (NEM-1469)
    slow_request_threshold_ms: int = Field(
        default=500,
        ge=1,
        le=60000,
        description="Threshold in milliseconds for logging slow API requests. "
        "Requests exceeding this duration are logged at WARNING level with "
        "method, path, status code, and duration for performance monitoring.",
    )

    # Slow query EXPLAIN logging settings
    slow_query_threshold_ms: float = Field(
        default=100.0,
        ge=10.0,
        le=10000.0,
        description="Threshold in milliseconds for slow query detection. "
        "Queries exceeding this threshold will have EXPLAIN ANALYZE logged. "
        "Set via SLOW_QUERY_THRESHOLD_MS environment variable.",
    )
    slow_query_explain_enabled: bool = Field(
        default=True,
        description="Enable EXPLAIN ANALYZE logging for slow queries. "
        "Set to False in production to disable performance overhead. "
        "Set via SLOW_QUERY_EXPLAIN_ENABLED environment variable.",
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

    # Enrichment circuit breaker settings
    enrichment_cb_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of Enrichment service failures before opening circuit breaker",
    )
    enrichment_cb_recovery_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Seconds to wait before attempting Enrichment service calls again after circuit opens",
    )
    enrichment_cb_half_open_max_calls: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum test calls allowed when Enrichment circuit is half-open",
    )

    # CLIP circuit breaker settings
    clip_cb_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of CLIP service failures before opening circuit breaker",
    )
    clip_cb_recovery_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Seconds to wait before attempting CLIP service calls again after circuit opens",
    )
    clip_cb_half_open_max_calls: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum test calls allowed when CLIP circuit is half-open",
    )

    # Florence circuit breaker settings
    florence_cb_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of Florence service failures before opening circuit breaker",
    )
    florence_cb_recovery_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Seconds to wait before attempting Florence service calls again after circuit opens",
    )
    florence_cb_half_open_max_calls: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum test calls allowed when Florence circuit is half-open",
    )

    # Redis compression settings (Python 3.14 compression.zstd)
    redis_compression_enabled: bool = Field(
        default=True,
        description="Enable Zstd compression for Redis queue payloads. "
        "Uses Python 3.14's native compression.zstd module for better compression "
        "ratio and faster compression/decompression than gzip/zlib.",
    )
    redis_compression_threshold: int = Field(
        default=1024,
        ge=0,
        le=1048576,
        description="Minimum payload size in bytes before compression is applied. "
        "Payloads smaller than this threshold are stored uncompressed to avoid "
        "compression overhead. Default: 1024 bytes (1KB). Set to 0 to compress all payloads.",
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
        default=4.0,  # Optimized: was 2.0, now 4.0 for ~50% reduction in frames
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
        default=100,
        ge=1,
        le=400,
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
    rate_limit_ai_inference_requests_per_minute: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Maximum AI inference requests per minute per client IP. "
        "Strict limit to prevent abuse of computationally expensive AI endpoints "
        "like prompt testing which runs LLM inference.",
    )
    rate_limit_ai_inference_burst: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Burst allowance for AI inference rate limiting. "
        "Allows short bursts of requests while maintaining overall rate limit.",
    )
    rate_limit_bulk_requests_per_minute: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Maximum bulk operation requests per minute per client IP. "
        "Strict limit to prevent abuse of bulk endpoints (create, update, delete) "
        "which can process up to 100 items per request.",
    )
    rate_limit_bulk_burst: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Burst allowance for bulk operation rate limiting. "
        "Allows short bursts of bulk requests while maintaining overall rate limit.",
    )
    trusted_proxy_ips: list[str] = Field(
        default=["127.0.0.1", "::1"],
        description="List of trusted proxy IP addresses. X-Forwarded-For headers are only "
        "processed from these IPs. Use CIDR notation for ranges (e.g., '10.0.0.0/8'). "
        "Common values: '127.0.0.1' (localhost), '10.0.0.0/8' (private), "
        "'172.16.0.0/12' (private), '192.168.0.0/16' (private)",
    )

    # Idempotency settings (NEM-2018)
    idempotency_enabled: bool = Field(
        default=True,
        description="Enable Idempotency-Key header support for mutation endpoints (POST, PUT, PATCH, DELETE). "
        "When enabled, requests with Idempotency-Key headers are cached to prevent duplicate operations.",
    )
    idempotency_ttl_seconds: int = Field(
        default=86400,
        ge=60,
        le=604800,
        description="Time-to-live in seconds for idempotency key cache entries. "
        "Default: 86400 (24 hours). Max: 604800 (7 days). "
        "After TTL expires, the same idempotency key can be reused.",
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
    websocket_token: SecretStr | None = Field(
        default=None,
        description="Optional token for WebSocket authentication. When set, WebSocket "
        "connections must include this token as a query parameter (?token=<value>). "
        "Leave empty/unset to disable token authentication (single-user mode).",
    )

    # WebSocket compression settings (NEM-3154)
    websocket_compression_enabled: bool = Field(
        default=True,
        description="Enable per-message deflate compression for WebSocket messages. "
        "Compression is negotiated during the WebSocket handshake (RFC 7692). "
        "Reduces bandwidth usage especially for large detection payloads with base64 images.",
    )
    websocket_compression_threshold: int = Field(
        default=1024,
        ge=0,
        le=1048576,
        description="Minimum message size in bytes before compression is applied (default: 1KB). "
        "Messages smaller than this threshold are sent uncompressed to avoid CPU overhead. "
        "Set to 0 to compress all messages regardless of size.",
    )
    websocket_compression_level: int = Field(
        default=6,
        ge=1,
        le=9,
        description="Compression level for deflate algorithm (1-9). "
        "1 = fastest (least compression), 9 = slowest (best compression). "
        "Default: 6 (good balance between speed and compression ratio).",
    )

    # WebSocket message batching settings (NEM-3738)
    websocket_batch_interval_ms: int = Field(
        default=100,
        ge=10,
        le=5000,
        description="Interval in milliseconds for batching high-frequency WebSocket messages. "
        "Messages on batch channels are collected over this interval and sent as a single batch. "
        "Lower values reduce latency, higher values improve batching efficiency. Default: 100ms.",
    )
    websocket_batch_max_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of messages per batch before immediate flush. "
        "When a channel accumulates this many messages, the batch is sent immediately "
        "without waiting for the interval timer. Default: 50 messages.",
    )
    websocket_batch_channels: list[str] = Field(
        default=["detections", "alerts"],
        description="List of WebSocket channels to apply batching to. "
        "Messages on these channels are batched; other channels send immediately. "
        "Default: ['detections', 'alerts'] for high-frequency detection events.",
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
    smtp_password: SecretStr | None = Field(
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

    # Hardware acceleration settings for video transcoding (NEM-2682)
    hardware_acceleration_enabled: bool = Field(
        default=True,
        description="Enable NVIDIA NVENC hardware acceleration for video transcoding. "
        "When enabled, uses GPU-based H.264 encoding (h264_nvenc) for faster clip generation. "
        "Automatically falls back to software encoding (libx264) if NVENC is unavailable.",
    )
    nvenc_preset: str = Field(
        default="p4",
        description="NVENC encoding preset. Options: p1 (fastest) to p7 (slowest/best quality). "
        "p4 provides good balance. Only used when hardware acceleration is enabled and available.",
    )
    nvenc_cq: int = Field(
        default=23,
        ge=0,
        le=51,
        description="NVENC constant quality (CQ) value. Lower = higher quality, larger files. "
        "Range: 0-51. Default: 23 (similar to libx264 CRF 23). Only used with hardware acceleration.",
    )

    @field_validator("nvenc_preset")
    @classmethod
    def validate_nvenc_preset(cls, v: str) -> str:
        """Validate NVENC preset is a valid option."""
        valid_presets = {"p1", "p2", "p3", "p4", "p5", "p6", "p7"}
        if v not in valid_presets:
            raise ValueError(f"nvenc_preset must be one of: {', '.join(sorted(valid_presets))}")
        return v

    # Video thumbnails settings
    video_thumbnails_dir: str = Field(
        default="data/thumbnails",
        description="Directory for storing video thumbnails and extracted frames",
    )
    video_max_frames: int = Field(
        default=20,  # Optimized: was 30, reduced for faster processing
        ge=1,
        le=300,
        description="Maximum number of frames to extract from a video",
    )

    # Image processing settings (NEM-2520)
    thumbnail_width: int = Field(
        default=320,
        ge=64,
        le=1920,
        description="Width of generated thumbnails in pixels. Used for detection preview images.",
    )
    thumbnail_height: int = Field(
        default=240,
        ge=48,
        le=1080,
        description="Height of generated thumbnails in pixels. Used for detection preview images.",
    )
    thumbnail_quality: int = Field(
        default=85,
        ge=1,
        le=100,
        description="JPEG quality for thumbnails (1-100). Higher values = better quality but larger files. "
        "Recommended: 75-90 for balance between quality and size.",
    )
    thumbnail_font_size: int = Field(
        default=14,
        ge=8,
        le=48,
        description="Font size in points for bounding box labels on thumbnails.",
    )
    scene_change_resize_width: int = Field(
        default=640,
        ge=128,
        le=1920,
        description="Width to resize frames to for scene change comparison (SSIM). "
        "Smaller values are faster but less accurate. Height is calculated to maintain aspect ratio.",
    )

    # Service health monitor settings
    ai_restart_enabled: bool = Field(
        default=True,
        description="Enable automatic restart of AI services (YOLO26, Nemotron) on health check failure. "
        "Set to False in containerized deployments where restart scripts are not available. "
        "Health monitoring and status broadcasts still occur when disabled.",
    )

    # Worker Supervisor settings (NEM-2460)
    # Controls the asyncio worker supervisor that monitors and auto-restarts crashed workers
    worker_supervisor_check_interval: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Interval in seconds between worker health checks by the supervisor.",
    )
    worker_supervisor_max_restarts: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of restart attempts for a crashed worker before giving up.",
    )
    worker_supervisor_restart_window: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Time window in seconds for counting restart attempts.",
    )

    # Container orchestrator settings (for Docker/Podman container management)
    # Environment variables use ORCHESTRATOR_ prefix (e.g., ORCHESTRATOR_ENABLED)
    orchestrator: OrchestratorSettings = Field(
        default_factory=OrchestratorSettings,
        description="Container orchestrator configuration for health monitoring and self-healing",
    )

    # Transcode cache settings (for disk-based video transcode caching)
    # Environment variables use TRANSCODE_CACHE_ prefix (e.g., TRANSCODE_CACHE_DIR)
    transcode_cache: TranscodeCacheSettings = Field(
        default_factory=TranscodeCacheSettings,
        description="Transcode cache configuration for LRU-based video transcode caching",
    )

    # Background evaluation settings
    # Run AI audit evaluations automatically when GPU is idle
    background_evaluation_enabled: bool = Field(
        default=True,
        description="Enable automatic background AI audit evaluation when GPU is idle. "
        "Full evaluations (self-critique, rubric scoring, consistency check, prompt improvement) "
        "run automatically instead of requiring manual 'Run Evaluation' clicks.",
    )
    background_evaluation_gpu_idle_threshold: int = Field(
        default=20,
        ge=0,
        le=100,
        description="GPU utilization percentage below which GPU is considered idle. "
        "Background evaluations only run when utilization is at or below this threshold.",
    )
    background_evaluation_idle_duration: int = Field(
        default=5,
        ge=1,
        le=300,
        description="Seconds GPU must remain idle before background evaluation starts. "
        "Prevents evaluation from starting during brief pauses in detection pipeline.",
    )
    background_evaluation_poll_interval: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="How often (in seconds) to check if conditions are met for background evaluation.",
    )

    # Worker supervisor settings (NEM-2492)
    worker_health_check_interval: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Interval in seconds between worker health checks. "
        "Lower values detect crashes faster but increase overhead.",
    )
    worker_max_restart_attempts: int = Field(
        default=5,
        ge=0,
        le=100,
        description="Maximum number of restart attempts before circuit breaker opens. "
        "Set to 0 to disable automatic restarts entirely.",
    )
    worker_restart_backoff_base: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay in seconds for exponential backoff on restarts. "
        "Actual delay = base * (2 ** (restart_count - 1)).",
    )

    # Orphan file cleanup settings (NEM-2260)
    # Periodic cleanup of files on disk without corresponding database records
    orphan_cleanup_enabled: bool = Field(
        default=True,
        description="Enable periodic cleanup of orphaned files. "
        "When enabled, files in clips_directory without database records are deleted "
        "after the age threshold is reached.",
    )
    orphan_cleanup_scan_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="How often (in hours) to scan for orphaned files. Default: 24 hours (daily).",
    )
    orphan_cleanup_age_threshold_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="Minimum age (in hours) before an orphaned file can be deleted. "
        "Files younger than this threshold are skipped to allow for incomplete processing. "
        "Default: 24 hours.",
    )

    # Performance profiling settings (NEM-1644)
    # Enable deep performance debugging with cProfile
    profiling_enabled: bool = Field(
        default=False,
        description="Enable performance profiling for deep debugging. "
        "When enabled, the profile_if_enabled decorator will profile decorated functions. "
        "Profile data is saved as .prof files that can be analyzed with snakeviz or py-spy.",
    )
    profiling_output_dir: str = Field(
        default="data/profiles",
        description="Directory for storing profiling output files (.prof format). "
        "Files can be analyzed with 'snakeviz <file>.prof' or converted to flamegraphs.",
    )

    # Request logging settings (NEM-1963)
    # Enable structured request/response logging for observability
    request_logging_enabled: bool = Field(
        default=True,
        description="Enable structured request/response logging middleware. "
        "When enabled, HTTP requests are logged with timing, status codes, and correlation IDs. "
        "Health check and metrics endpoints are excluded by default to reduce noise.",
    )

    # Request recording settings (NEM-1646)
    # Enable request recording for debugging production issues
    request_recording_enabled: bool = Field(
        default=False,
        description="Enable request recording for debugging. When enabled, requests can be "
        "recorded based on error status, sampling rate, or X-Debug-Record header. "
        "SECURITY: Disabled by default. Enable only in debug/development environments.",
    )
    request_recording_sample_rate: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Fraction of successful requests to sample for recording (0.0-1.0). "
        "Error responses (5xx) are always recorded when request_recording_enabled is True. "
        "Default: 0.01 (1% of successful requests).",
    )
    request_recording_max_body_size: int = Field(
        default=10_000,
        ge=0,
        le=1_000_000,
        description="Maximum request/response body size to record in bytes. "
        "Bodies exceeding this limit are truncated. Default: 10KB. Max: 1MB.",
    )

    # HSTS (HTTP Strict Transport Security) settings
    hsts_preload: bool = Field(
        default=False,
        description="Enable HSTS preload directive for inclusion in browser preload lists. "
        "CAUTION: Only enable for public deployments registered at hstspreload.org. "
        "Once registered, your domain will be hardcoded into browsers to always use HTTPS. "
        "Requires: max-age >= 1 year, includeSubDomains, and serving valid HTTPS on all subdomains.",
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

    @field_validator("tls_cert_path", "tls_key_path", "tls_ca_path")
    @classmethod
    def validate_tls_cert_path(cls, v: str | None) -> str | None:
        """Validate TLS certificate file paths exist (NEM-2024).

        This validates that if a TLS certificate path is provided,
        the file actually exists on the filesystem and is a regular file.
        This catches configuration errors at startup rather than at runtime
        when TLS connections fail.

        Args:
            v: The file path to validate (can be None)

        Returns:
            The validated path, or None if not provided

        Raises:
            ValueError: If the file path is provided but does not exist or is not a file
        """
        if v is None:
            return v
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Certificate file not found: {v}")
        if not path.is_file():
            raise ValueError(f"Certificate path is not a file: {v}")
        return v

    @field_validator("tls_key_path", mode="after")
    @classmethod
    def validate_tls_key_permissions(cls, v: str | None) -> str | None:
        """Warn if TLS private key file has insecure permissions (NEM-2024).

        This checks if the TLS private key file is readable by group or others,
        which is a security risk. A warning is emitted rather than an error
        to allow for development/testing scenarios.

        Args:
            v: The validated file path (can be None, already validated by validate_tls_cert_path)

        Returns:
            The path unchanged

        Warns:
            UserWarning: If the key file is readable by group or others (mode & 0o044)
        """
        if v is None:
            return v
        import warnings

        path = Path(v)
        # Check if file exists (should already be validated, but be defensive)
        if not path.exists():
            return v
        # Check if group or others have read permissions (mode & 0o044)
        # 0o040 = group read, 0o004 = others read
        mode = path.stat().st_mode
        if mode & 0o044:
            warnings.warn(
                f"TLS key file {v} is readable by others. "
                "Consider restricting permissions to owner only (chmod 600).",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is a known value."""
        valid_environments = {"production", "staging", "development", "dev", "prod", "test"}
        v_lower = v.lower()
        if v_lower not in valid_environments:
            raise ValueError(
                f"environment must be one of: {', '.join(sorted(valid_environments))}. Got: '{v}'"
            )
        # Normalize common aliases
        if v_lower == "dev":
            return "development"
        if v_lower == "prod":
            return "production"
        return v_lower

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

    @field_validator("redis_memory_policy")
    @classmethod
    def validate_redis_memory_policy(cls, v: str) -> str:
        """Validate Redis memory eviction policy (NEM-3416)."""
        valid_policies = {
            "volatile-lru",
            "allkeys-lru",
            "volatile-ttl",
            "volatile-random",
            "allkeys-random",
            "noeviction",
            # Also support shorter aliases without volatile-/allkeys- prefix
            "lru",
            "ttl",
            "random",
        }
        v_lower = v.lower()
        if v_lower not in valid_policies:
            raise ValueError(
                f"redis_memory_policy must be one of: volatile-lru, allkeys-lru, "
                f"volatile-ttl, volatile-random, allkeys-random, noeviction. Got: '{v}'"
            )
        # Map short aliases to full names (default to volatile- prefix for safety)
        alias_map = {
            "lru": "volatile-lru",
            "ttl": "volatile-ttl",
            "random": "volatile-random",
        }
        return alias_map.get(v_lower, v_lower)

    @field_validator("redis_ssl_certfile", "redis_ssl_keyfile", "redis_ssl_ca_certs")
    @classmethod
    def validate_redis_ssl_path(cls, v: str | None) -> str | None:
        """Validate Redis SSL certificate file paths exist.

        This validates that if a Redis SSL certificate path is provided,
        the file actually exists on the filesystem. This catches configuration
        errors at startup rather than at runtime when Redis connections fail.

        Args:
            v: The file path to validate (can be None)

        Returns:
            The validated path, or None if not provided

        Raises:
            ValueError: If the file path is provided but does not exist
        """
        if v is None:
            return v
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Redis SSL file not found: {v}")
        return v

    @model_validator(mode="after")
    def validate_redis_ssl_consistency(self) -> Settings:
        """Validate Redis SSL configuration consistency.

        For mutual TLS (mTLS), both the client certificate (certfile) and
        private key (keyfile) must be provided together. Having only one
        of them is a configuration error.

        CA certificates can be provided alone for verify-only mode where
        the server certificate is verified but no client certificate is sent.

        Returns:
            self: The validated Settings instance

        Raises:
            ValueError: If only one of redis_ssl_certfile/redis_ssl_keyfile is provided
        """
        ssl_fields = [self.redis_ssl_certfile, self.redis_ssl_keyfile]
        provided = sum(1 for f in ssl_fields if f is not None)
        if provided > 0 and provided < 2:
            raise ValueError(
                "Both redis_ssl_certfile and redis_ssl_keyfile must be provided together "
                "for mutual TLS. Provide both, or neither (CA certs alone are allowed for "
                "server certificate verification without client authentication)."
            )
        return self

    @model_validator(mode="after")
    def validate_production_passwords(self) -> Settings:
        """Validate that production environments don't use weak/default passwords (NEM-3141).

        This security check ensures that known weak passwords (like development defaults)
        are not used in production or staging environments. Weak passwords include:
        - Common default passwords (password, admin, root, etc.)
        - Old hardcoded development defaults (security_dev_password, ftp_dev_password)
        - Passwords shorter than 16 characters

        Returns:
            self: The validated Settings instance

        Raises:
            ValueError: If a weak password is detected in production/staging environment
        """
        # Only enforce in production and staging environments
        # Skip validation for development, test, and local environments
        if self.environment not in ("production", "staging"):
            return self

        # Also skip if environment looks like a test/CI environment
        if self.environment.lower() in ("test", "testing", "ci", "local"):
            return self

        # Known weak/default passwords that should never be used in production
        # These include old hardcoded defaults and common weak passwords
        weak_passwords = {
            "security_dev_password",
            "ftp_dev_password",
            "password",
            "postgres",
            "admin",
            "root",
            "123456",
            "changeme",
            "secret",
        }

        def is_weak(password: str | None) -> bool:
            """Check if a password is considered weak."""
            if password is None or password == "":
                return False  # Empty passwords are handled elsewhere
            if len(password) < 16:
                return True
            return password.lower() in weak_passwords

        # Extract password from DATABASE_URL if present
        db_password = None
        if self.database_url and "@" in self.database_url:
            # Format: postgresql+asyncpg://user:password@host:port/db  # pragma: allowlist secret
            try:
                # Extract the part between :// and @
                auth_part = self.database_url.split("://")[1].split("@")[0]
                if ":" in auth_part:
                    db_password = auth_part.split(":", 1)[1]
            except (IndexError, AttributeError):
                pass  # Can't parse, skip validation

        # Check database password in URL
        if db_password and is_weak(db_password):
            raise ValueError(
                f"Weak database password detected in DATABASE_URL for {self.environment} environment. "
                "Production/staging deployments must use strong, unique passwords. "
                "Run ./setup.sh to generate secure credentials or set DATABASE_URL with a strong password."
            )

        return self

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

    def __repr__(self) -> str:
        """Auto-redact sensitive fields in repr output.

        Prevents accidental exposure of secrets when logging settings objects.
        Uses redact_url() for URL fields and [REDACTED] for sensitive values.
        """
        # Import here to avoid circular import
        from backend.core.logging import SENSITIVE_FIELD_NAMES, redact_url

        safe_dict: dict[str, Any] = {}
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name, None)
            field_lower = field_name.lower()

            # Check if field name matches sensitive patterns
            is_sensitive = field_lower in SENSITIVE_FIELD_NAMES or any(
                pattern in field_lower
                for pattern in ("password", "secret", "key", "token", "credential")
            )

            if is_sensitive and value is not None:
                # Use redact_url for URL fields, [REDACTED] for others
                if "url" in field_lower and isinstance(value, str):
                    safe_dict[field_name] = redact_url(value)
                else:
                    safe_dict[field_name] = "[REDACTED]"
            else:
                safe_dict[field_name] = value

        return f"Settings({safe_dict})"

    def __str__(self) -> str:
        """Return redacted string representation."""
        return self.__repr__()


@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    # `_env_file` is evaluated at call time (unlike `model_config.env_file`, which is bound at
    # import time). This lets tests and deployments override runtime config cleanly.
    return Settings(_env_file=(".env", runtime_env_path))
