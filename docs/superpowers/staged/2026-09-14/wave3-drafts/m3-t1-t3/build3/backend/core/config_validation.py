"""Configuration validation and startup summary logging (NEM-2026).

This module provides utilities for validating application configuration at startup
and logging a summary table of configuration status. It performs comprehensive checks
on required settings, URL formats, port ranges, and path existence.

Key features:
- Validates database and Redis connection string formats
- Checks AI service URL formats
- Validates port numbers are in valid ranges
- Warns on missing required paths (e.g., foscam_base_path)
- Logs a formatted summary table at startup
- Distinguishes between errors (critical) and warnings (non-blocking)

Usage:
    from backend.core.config_validation import validate_config, log_config_summary

    settings = get_settings()
    result = validate_config(settings)
    log_config_summary(result)

    if not result.valid:
        # Handle critical configuration errors
        raise ConfigurationError("Configuration validation failed")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

if TYPE_CHECKING:
    from backend.core.config import Settings

# Status type for validation items
ValidationStatus = Literal["ok", "warning", "error", "info"]


@dataclass
class ValidationItem:
    """A single configuration validation result item.

    Attributes:
        name: The setting name being validated (e.g., "database_url")
        status: Validation status - "ok", "warning", "error", or "info"
        message: Human-readable description of the validation result
    """

    name: str
    status: ValidationStatus
    message: str


@dataclass
class ConfigValidationResult:
    """Result of configuration validation containing all check results.

    Attributes:
        valid: True if no critical errors were found (warnings are acceptable)
        items: List of all validation items with their status and messages
        warnings: List of warning messages (non-blocking issues)
        errors: List of error messages (critical issues that should block startup)
    """

    valid: bool
    items: list[ValidationItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _validate_database_url(settings: Settings) -> ValidationItem:
    """Validate database URL format.

    Checks that:
    - URL is not empty
    - URL starts with postgresql:// or postgresql+asyncpg://
    - URL has basic structure (host, database)
    """
    if not settings.database_url:
        return ValidationItem(
            name="database_url",
            status="error",
            message="DATABASE_URL is required but not set",
        )

    url = settings.database_url
    if not url.startswith(("postgresql://", "postgresql+asyncpg://")):
        return ValidationItem(
            name="database_url",
            status="error",
            message="DATABASE_URL must use postgresql:// or postgresql+asyncpg:// scheme",
        )

    # Parse and validate structure
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return ValidationItem(
                name="database_url",
                status="error",
                message="DATABASE_URL is missing hostname",
            )
        if not parsed.path or parsed.path == "/":
            return ValidationItem(
                name="database_url",
                status="warning",
                message="DATABASE_URL is missing database name",
            )
    except Exception as e:
        return ValidationItem(
            name="database_url",
            status="error",
            message=f"DATABASE_URL parse error: {e}",
        )

    return ValidationItem(
        name="database_url",
        status="ok",
        message="PostgreSQL URL format valid",
    )


def _validate_redis_url(settings: Settings) -> ValidationItem:
    """Validate Redis URL format.

    Checks that:
    - URL starts with redis:// or rediss:// (TLS)
    - URL has a hostname
    """
    url = settings.redis_url

    if not url:
        return ValidationItem(
            name="redis_url",
            status="error",
            message="REDIS_URL is required but not set",
        )

    if not url.startswith(("redis://", "rediss://")):
        return ValidationItem(
            name="redis_url",
            status="error",
            message="REDIS_URL must use redis:// or rediss:// scheme",
        )

    # Parse and validate structure
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return ValidationItem(
                name="redis_url",
                status="error",
                message="REDIS_URL is missing hostname",
            )
    except Exception as e:
        return ValidationItem(
            name="redis_url",
            status="error",
            message=f"REDIS_URL parse error: {e}",
        )

    # Note: TLS settings should be validated separately if redis_ssl_enabled
    scheme_info = "TLS enabled" if url.startswith("rediss://") else "standard connection"
    return ValidationItem(
        name="redis_url",
        status="ok",
        message=f"Redis URL format valid ({scheme_info})",
    )


def _validate_ai_service_url(name: str, url: str) -> ValidationItem:
    """Validate AI service URL format.

    Checks that:
    - URL starts with http:// or https://
    - URL has a hostname
    """
    if not url:
        return ValidationItem(
            name=name,
            status="error",
            message=f"{name.upper()} is required but not set",
        )

    if not url.startswith(("http://", "https://")):
        return ValidationItem(
            name=name,
            status="error",
            message=f"{name.upper()} must use http:// or https:// scheme",
        )

    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return ValidationItem(
                name=name,
                status="error",
                message=f"{name.upper()} is missing hostname",
            )
    except Exception as e:
        return ValidationItem(
            name=name,
            status="error",
            message=f"{name.upper()} parse error: {e}",
        )

    # Determine status and message based on URL characteristics
    is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    is_https = url.startswith("https://")

    if is_localhost:
        status: ValidationStatus = "info"
        message = "URL valid (localhost development mode)"
    elif is_https:
        status = "ok"
        message = "URL valid (HTTPS)"
    else:
        status = "warning"
        message = "URL valid but using HTTP (consider HTTPS for production)"

    return ValidationItem(name=name, status=status, message=message)


def _validate_port(name: str, port: int) -> ValidationItem:
    """Validate port number is in valid range.

    Valid port range: 1-65535
    Common ports: 0 is special (OS-assigned), 1-1023 are privileged
    """
    if port < 0:
        return ValidationItem(
            name=name,
            status="error",
            message=f"Port must be positive (got {port})",
        )

    if port == 0:
        return ValidationItem(
            name=name,
            status="warning",
            message="Port 0 will be assigned by OS (usually not intended)",
        )

    if port > 65535:
        return ValidationItem(
            name=name,
            status="error",
            message=f"Port must be <= 65535 (got {port})",
        )

    if port < 1024:
        return ValidationItem(
            name=name,
            status="info",
            message=f"Port {port} is a privileged port (requires root/admin)",
        )

    return ValidationItem(
        name=name,
        status="ok",
        message=f"Port {port} is valid",
    )


def _validate_path_exists(name: str, path: str, required: bool = False) -> ValidationItem:
    """Validate that a filesystem path exists.

    Args:
        name: Setting name
        path: Path to check
        required: If True, missing path is an error; otherwise it's a warning
    """
    if not path:
        if required:
            return ValidationItem(
                name=name,
                status="error",
                message=f"{name.upper()} is required but not set",
            )
        return ValidationItem(
            name=name,
            status="ok",
            message=f"{name.upper()} not configured (optional)",
        )

    path_obj = Path(path)
    if path_obj.exists():
        path_type = "directory" if path_obj.is_dir() else "file"
        return ValidationItem(
            name=name,
            status="ok",
            message=f"Path exists ({path_type})",
        )
    else:
        if required:
            return ValidationItem(
                name=name,
                status="error",
                message=f"Path does not exist: {path}",
            )
        return ValidationItem(
            name=name,
            status="warning",
            message=f"Path does not exist: {path}",
        )


def _collect_item(
    item: ValidationItem,
    items: list[ValidationItem],
    warnings: list[str],
    errors: list[str],
) -> None:
    """Collect a validation item and categorize by status."""
    items.append(item)
    if item.status == "error":
        errors.append(f"{item.name}: {item.message}")
    elif item.status == "warning":
        warnings.append(f"{item.name}: {item.message}")


def validate_config(settings: Settings) -> ConfigValidationResult:
    """Validate application configuration settings.

    Performs comprehensive validation of all critical configuration settings:
    - Database URL format and structure
    - Redis URL format and structure
    - AI service URLs (YOLO26, Nemotron)
    - Port numbers are in valid ranges
    - Required paths exist

    This function does NOT fail on warnings - only on critical errors.
    Warnings indicate potential issues that won't prevent startup.

    Args:
        settings: Application settings instance to validate

    Returns:
        ConfigValidationResult containing all validation results
    """
    items: list[ValidationItem] = []
    warnings: list[str] = []
    errors: list[str] = []

    # Validate database URL
    _collect_item(_validate_database_url(settings), items, warnings, errors)

    # Validate Redis URL
    _collect_item(_validate_redis_url(settings), items, warnings, errors)

    # Validate AI service URLs
    _collect_item(
        _validate_ai_service_url("yolo26_url", settings.yolo26_url),
        items,
        warnings,
        errors,
    )
    _collect_item(
        _validate_ai_service_url("nemotron_url", settings.nemotron_url),
        items,
        warnings,
        errors,
    )

    # Validate port numbers
    _collect_item(_validate_port("api_port", settings.api_port), items, warnings, errors)
    _collect_item(_validate_port("smtp_port", settings.smtp_port), items, warnings, errors)

    # Validate paths
    _collect_item(
        _validate_path_exists(
            "foscam_base_path",
            settings.foscam_base_path,
            required=False,  # Not required - cameras may be added later
        ),
        items,
        warnings,
        errors,
    )

    # Determine overall validity (valid if no errors)
    valid = len(errors) == 0

    return ConfigValidationResult(
        valid=valid,
        items=items,
        warnings=warnings,
        errors=errors,
    )


def log_config_summary(result: ConfigValidationResult) -> None:
    """Log configuration validation summary.

    Logs a formatted summary of configuration validation results:
    - INFO level: Overall status and individual OK items
    - WARNING level: Items with warnings
    - ERROR level: Items with errors

    The summary is designed to be easily readable in logs while also
    providing structured data for log aggregation systems.

    Args:
        result: Configuration validation result to log
    """
    logger = logging.getLogger("backend.core.config_validation")

    # Status indicators for different validation states
    status_indicators = {
        "ok": "[OK]",
        "warning": "[WARN]",
        "error": "[ERROR]",
        "info": "[INFO]",
    }

    # Log header
    overall_status = "VALID" if result.valid else "INVALID"
    logger.info(
        f"Configuration Validation Summary: {overall_status}",
        extra={
            "validation_valid": result.valid,
            "warning_count": len(result.warnings),
            "error_count": len(result.errors),
        },
    )

    # Log each validation item at appropriate level
    for item in result.items:
        indicator = status_indicators.get(item.status, "[?]")
        log_message = f"  {indicator} {item.name}: {item.message}"

        extra = {
            "validation_item": item.name,
            "validation_status": item.status,
            "validation_message": item.message,
        }

        if item.status == "error":
            logger.error(log_message, extra=extra)
        elif item.status == "warning":
            logger.warning(log_message, extra=extra)
        elif item.status == "info":
            logger.info(log_message, extra=extra)
        else:
            logger.info(log_message, extra=extra)

    # Log summary counts
    if result.errors:
        logger.error(
            f"Configuration has {len(result.errors)} error(s) that must be fixed",
            extra={"error_count": len(result.errors)},
        )

    if result.warnings:
        logger.warning(
            f"Configuration has {len(result.warnings)} warning(s) to review",
            extra={"warning_count": len(result.warnings)},
        )


__all__ = [
    "ConfigValidationResult",
    "ValidationItem",
    "ValidationStatus",
    "log_config_summary",
    "validate_config",
]
