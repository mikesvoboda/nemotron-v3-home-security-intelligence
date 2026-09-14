"""Nested configuration settings with env_nested_delimiter (NEM-3778).

This module provides nested Pydantic Settings models that support configuration
via environment variables using double-underscore as a nested delimiter.

For example, the environment variable REDIS__POOL__SIZE=50 maps to
settings.redis.pool.size = 50.

This pattern allows for better organization of complex configuration while
maintaining simple environment variable-based configuration.

Usage:
    from backend.core.config_nested import get_nested_settings

    settings = get_nested_settings()
    print(settings.redis.pool.size)  # 50
    print(settings.database.pool_size)  # 20

Environment Variables:
    DATABASE__URL - Database connection URL
    DATABASE__POOL_SIZE - Database connection pool size
    REDIS__URL - Redis connection URL
    REDIS__POOL__SIZE - Redis pool size
    AI__DETECTOR__URL - AI detector service URL
    NOTIFICATION__SMTP__HOST - SMTP server host
"""

from __future__ import annotations

from functools import cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "AIServiceSettings",
    "DatabaseSettings",
    "DetectorSettings",
    "LLMSettings",
    "NestedSettings",
    "NotificationSettings",
    "RedisPoolSettings",
    "RedisSSLSettings",
    "RedisSettings",
    "SMTPSettings",
    "WebhookSettings",
    "get_nested_settings",
]


# =============================================================================
# Redis Settings
# =============================================================================


class RedisPoolSettings(BaseSettings):
    """Redis connection pool configuration.

    Environment variables use REDIS__POOL__ prefix:
    - REDIS__POOL__SIZE
    - REDIS__POOL__TIMEOUT
    - REDIS__POOL__RETRY_ON_TIMEOUT
    - REDIS__POOL__MAX_CONNECTIONS
    """

    model_config = SettingsConfigDict(
        env_prefix="REDIS__POOL__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of connections to maintain in the pool",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        description="Timeout in seconds for pool operations",
    )
    retry_on_timeout: bool = Field(
        default=True,
        description="Retry operations on timeout",
    )
    max_connections: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum total connections allowed",
    )


class RedisSSLSettings(BaseSettings):
    """Redis SSL/TLS configuration.

    Environment variables use REDIS__SSL__ prefix:
    - REDIS__SSL__ENABLED
    - REDIS__SSL__CERT_PATH
    - REDIS__SSL__KEY_PATH
    - REDIS__SSL__VERIFY_MODE
    """

    model_config = SettingsConfigDict(
        env_prefix="REDIS__SSL__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable SSL/TLS for Redis connections",
    )
    cert_path: str | None = Field(
        default=None,
        description="Path to SSL certificate file",
    )
    key_path: str | None = Field(
        default=None,
        description="Path to SSL private key file",
    )
    ca_path: str | None = Field(
        default=None,
        description="Path to CA certificate file",
    )
    verify_mode: str = Field(
        default="required",
        description="SSL verification mode: none, optional, required",
    )


class RedisSettings(BaseSettings):
    """Redis configuration with nested pool and SSL settings.

    Environment variables use REDIS__ prefix:
    - REDIS__URL
    - REDIS__PASSWORD
    - REDIS__DATABASE
    - REDIS__POOL__* (nested pool settings)
    - REDIS__SSL__* (nested SSL settings)
    """

    model_config = SettingsConfigDict(
        env_prefix="REDIS__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    password: SecretStr | None = Field(
        default=None,
        description="Redis password for authentication",
    )
    database: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number",
    )
    pool: RedisPoolSettings = Field(
        default_factory=RedisPoolSettings,
        description="Connection pool settings",
    )
    ssl: RedisSSLSettings = Field(
        default_factory=RedisSSLSettings,
        description="SSL/TLS settings",
    )


# =============================================================================
# Database Settings
# =============================================================================


class DatabaseSettings(BaseSettings):
    """Database configuration with pool settings.

    Environment variables use DATABASE__ prefix:
    - DATABASE__URL
    - DATABASE__POOL_SIZE
    - DATABASE__POOL_OVERFLOW
    - DATABASE__POOL_TIMEOUT
    - DATABASE__POOL_RECYCLE
    - DATABASE__ECHO
    """

    model_config = SettingsConfigDict(
        env_prefix="DATABASE__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="",
        description="Database connection URL (PostgreSQL)",
    )
    pool_size: int = Field(
        default=20,
        ge=5,
        le=200,
        description="Number of connections in the pool",
    )
    pool_overflow: int = Field(
        default=30,
        ge=0,
        le=100,
        description="Additional connections beyond pool_size",
    )
    pool_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Seconds to wait for available connection",
    )
    pool_recycle: int = Field(
        default=1800,
        ge=300,
        le=7200,
        description="Seconds before connections are recycled",
    )
    echo: bool = Field(
        default=False,
        description="Log all SQL statements",
    )


# =============================================================================
# AI Service Settings
# =============================================================================


class DetectorSettings(BaseSettings):
    """AI detector service configuration.

    Environment variables use AI__DETECTOR__ prefix:
    - AI__DETECTOR__URL
    - AI__DETECTOR__TIMEOUT
    - AI__DETECTOR__RETRY_COUNT
    - AI__DETECTOR__RETRY_DELAY
    """

    model_config = SettingsConfigDict(
        env_prefix="AI__DETECTOR__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="http://localhost:8090",
        description="Detector service URL",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        description="Request timeout in seconds",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts on failure",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Delay between retries in seconds",
    )


class LLMSettings(BaseSettings):
    """AI LLM service configuration.

    Environment variables use AI__LLM__ prefix:
    - AI__LLM__URL
    - AI__LLM__TIMEOUT
    - AI__LLM__MAX_TOKENS
    - AI__LLM__TEMPERATURE
    """

    model_config = SettingsConfigDict(
        env_prefix="AI__LLM__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="http://localhost:8091",
        description="LLM service URL",
    )
    timeout: float = Field(
        default=60.0,
        gt=0,
        le=600.0,
        description="Request timeout in seconds",
    )
    max_tokens: int = Field(
        default=4096,
        ge=100,
        le=128000,
        description="Maximum tokens in response",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation",
    )


class AIServiceSettings(BaseSettings):
    """AI services configuration with nested detector and LLM settings.

    Environment variables use AI__ prefix:
    - AI__DETECTOR__* (nested detector settings)
    - AI__LLM__* (nested LLM settings)
    """

    model_config = SettingsConfigDict(
        env_prefix="AI__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    detector: DetectorSettings = Field(
        default_factory=DetectorSettings,
        description="Object detector service settings",
    )
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="LLM service settings",
    )


# =============================================================================
# Notification Settings
# =============================================================================


class SMTPSettings(BaseSettings):
    """SMTP configuration for email notifications.

    Environment variables use NOTIFICATION__SMTP__ prefix:
    - NOTIFICATION__SMTP__HOST
    - NOTIFICATION__SMTP__PORT
    - NOTIFICATION__SMTP__USERNAME
    - NOTIFICATION__SMTP__PASSWORD
    - NOTIFICATION__SMTP__USE_TLS
    """

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION__SMTP__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(
        default="localhost",
        description="SMTP server hostname",
    )
    port: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP server port",
    )
    username: str | None = Field(
        default=None,
        description="SMTP username for authentication",
    )
    password: SecretStr | None = Field(
        default=None,
        description="SMTP password for authentication",
    )
    use_tls: bool = Field(
        default=True,
        description="Use TLS/STARTTLS for SMTP connection",
    )
    from_address: str = Field(
        default="noreply@localhost",
        description="Default from address for emails",
    )


class WebhookSettings(BaseSettings):
    """Webhook configuration for notifications.

    Environment variables use NOTIFICATION__WEBHOOK__ prefix:
    - NOTIFICATION__WEBHOOK__URL
    - NOTIFICATION__WEBHOOK__TIMEOUT
    - NOTIFICATION__WEBHOOK__SECRET
    """

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION__WEBHOOK__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="",
        description="Webhook endpoint URL",
    )
    timeout: float = Field(
        default=10.0,
        gt=0,
        le=60.0,
        description="Webhook request timeout in seconds",
    )
    secret: SecretStr | None = Field(
        default=None,
        description="Secret for signing webhook payloads",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts on failure",
    )


class NotificationSettings(BaseSettings):
    """Notification configuration with nested SMTP and webhook settings.

    Environment variables use NOTIFICATION__ prefix:
    - NOTIFICATION__ENABLED
    - NOTIFICATION__SMTP__* (nested SMTP settings)
    - NOTIFICATION__WEBHOOK__* (nested webhook settings)
    """

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable notification system",
    )
    smtp: SMTPSettings | None = Field(
        default=None,
        description="SMTP settings for email notifications",
    )
    webhook: WebhookSettings | None = Field(
        default=None,
        description="Webhook settings for HTTP notifications",
    )


# =============================================================================
# Main Nested Settings
# =============================================================================


class NestedSettings(BaseSettings):
    """Root settings class with all nested configuration groups.

    This class aggregates all nested settings groups and supports
    configuration via environment variables with double-underscore
    as the nested delimiter.

    Environment Variables:
        DATABASE__* - Database settings
        REDIS__* - Redis settings (with nested REDIS__POOL__* and REDIS__SSL__*)
        AI__* - AI service settings (with nested AI__DETECTOR__* and AI__LLM__*)
        NOTIFICATION__* - Notification settings (with nested SMTP and webhook)

    Example:
        # Environment variables:
        # DATABASE__POOL_SIZE=30
        # REDIS__POOL__SIZE=80
        # AI__DETECTOR__TIMEOUT=45.0

        settings = NestedSettings()
        assert settings.database.pool_size == 30
        assert settings.redis.pool.size == 80
        assert settings.ai.detector.timeout == 45.0
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database configuration",
    )
    redis: RedisSettings = Field(
        default_factory=RedisSettings,
        description="Redis configuration",
    )
    ai: AIServiceSettings = Field(
        default_factory=AIServiceSettings,
        description="AI services configuration",
    )
    notification: NotificationSettings = Field(
        default_factory=NotificationSettings,
        description="Notification configuration",
    )


@cache
def get_nested_settings() -> NestedSettings:
    """Get cached nested settings instance.

    Returns a cached singleton instance of NestedSettings.
    Use cache_clear() to reset the cache if needed.

    Returns:
        Cached NestedSettings instance

    Example:
        settings = get_nested_settings()
        print(settings.redis.pool.size)
    """
    return NestedSettings()
