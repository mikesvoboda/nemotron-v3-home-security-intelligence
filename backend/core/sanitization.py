"""Sanitization utilities for secure input handling.

This module provides comprehensive sanitization functions to prevent:
- Command injection in shell scripts (container names)
- Path disclosure in error messages
- Metric label cardinality explosion
- Exception message information leakage
- SSRF attacks via URL validation

All sanitization follows allowlist-based approaches where possible.

Note: This module is imported by config.py, so it MUST NOT import from config
or logging to avoid circular imports. Use standard logging if needed.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from urllib.parse import urlparse

# Use standard logging instead of backend.core.logging to avoid circular imports
# (config.py imports this module, and logging.py imports from config.py)
logger = logging.getLogger(__name__)


# =============================================================================
# Container Name Sanitization (NEM-1124)
# =============================================================================

# Allowlist pattern for container names: alphanumeric, hyphens, underscores
# This is the Docker/Podman container naming convention
CONTAINER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
CONTAINER_NAME_MAX_LENGTH = 128


def sanitize_container_name(name: str) -> str:
    """Sanitize a container name to prevent command injection.

    Only allows alphanumeric characters, hyphens, and underscores.
    Names must start with an alphanumeric character.

    Args:
        name: The container name to sanitize

    Returns:
        The sanitized container name, or empty string if invalid

    Raises:
        ValueError: If the name is empty, too long, or contains invalid characters
    """
    if not name:
        raise ValueError("Container name cannot be empty")

    # Remove any leading/trailing whitespace
    name = name.strip()

    if not name:
        raise ValueError("Container name cannot be empty after trimming")

    if len(name) > CONTAINER_NAME_MAX_LENGTH:
        raise ValueError(
            f"Container name exceeds maximum length of {CONTAINER_NAME_MAX_LENGTH}: {len(name)}"
        )

    if not CONTAINER_NAME_PATTERN.match(name):
        raise ValueError(
            f"Container name contains invalid characters. "
            f"Only alphanumeric, hyphens, and underscores allowed. "
            f"Must start with alphanumeric. Got: '{name[:50]}...'"
            if len(name) > 50
            else f"Only alphanumeric, hyphens, and underscores allowed. "
            f"Must start with alphanumeric. Got: '{name}'"
        )

    return name


def validate_container_names(names: list[str]) -> list[str]:
    """Validate a list of container names.

    Args:
        names: List of container names to validate

    Returns:
        List of validated container names

    Raises:
        ValueError: If any name is invalid
    """
    validated = []
    for name in names:
        validated.append(sanitize_container_name(name))
    return validated


# =============================================================================
# Filename Sanitization for Error Messages (NEM-1078)
# =============================================================================


def sanitize_path_for_error(path: str) -> str:
    """Sanitize a file path for safe inclusion in error messages.

    Removes the directory path and returns only the filename to prevent
    information disclosure about internal file system structure.

    Args:
        path: Full file path

    Returns:
        Just the filename portion, or '[unknown]' if path is empty
    """
    if not path:
        return "[unknown]"

    # Extract just the filename
    parts = path.replace("\\", "/").rsplit("/", 1)
    filename = parts[1] if len(parts) == 2 else parts[0]

    # Remove any remaining path-like characters that could leak structure
    if not filename:
        return "[unknown]"

    # Limit length to prevent very long filenames in logs
    if len(filename) > 100:
        filename = filename[:97] + "..."

    return filename


def sanitize_error_for_response(error: Exception, context: str = "") -> str:
    """Sanitize an exception for safe inclusion in API responses.

    Removes potentially sensitive information like:
    - Full file paths (keeps only filename)
    - Stack traces
    - Internal module names
    - Database connection details
    - URL credentials (user:password@host)
    - JSON password values
    - Windows paths

    Args:
        error: The exception to sanitize
        context: Optional context string (e.g., "processing image")

    Returns:
        A safe, user-friendly error message
    """
    # Get the error message
    error_msg = str(error)
    sanitized = error_msg

    # FIRST: Handle URL credentials BEFORE path sanitization
    # This preserves URL structure while redacting credentials
    # Pattern matches: protocol://user:pass@host  # pragma: allowlist secret
    url_credentials_pattern = re.compile(
        r"([a-zA-Z][a-zA-Z0-9+.-]*://)?([^:@\s/]+):([^@\s/]+)@([^\s]+)", re.IGNORECASE
    )

    def replace_url_credentials(match: re.Match[str]) -> str:
        protocol = match.group(1) or ""
        # Groups 2 and 3 are user and password - we don't use them, just redact
        host_and_rest = match.group(4)
        return f"{protocol}[CREDENTIALS_REDACTED]@{host_and_rest}"

    sanitized = url_credentials_pattern.sub(replace_url_credentials, sanitized)

    # Pattern to match Unix file paths (must start with / but NOT //)
    # The negative lookbehind prevents matching after protocol:// or other scheme
    unix_path_pattern = re.compile(r"(?<![a-zA-Z0-9:])(/(?!/)[^\s:]+)+")

    # Pattern to match Windows paths (C:\, D:\, etc.)
    windows_path_pattern = re.compile(r"[A-Za-z]:\\[^\s]+")

    # Replace Unix paths with just filename
    def replace_unix_path(match: re.Match[str]) -> str:
        path = match.group(0)
        return sanitize_path_for_error(path)

    # Replace Windows paths with just filename
    def replace_windows_path(match: re.Match[str]) -> str:
        path = match.group(0)
        # For Windows paths, use rsplit on backslash
        parts = path.rsplit("\\", 1)
        filename = parts[-1] if parts else "[unknown]"
        if not filename:
            return "[unknown]"
        if len(filename) > 100:
            filename = filename[:97] + "..."
        return filename

    sanitized = unix_path_pattern.sub(replace_unix_path, sanitized)
    sanitized = windows_path_pattern.sub(replace_windows_path, sanitized)

    # Remove common sensitive patterns
    # Order matters - more specific patterns should come first
    sensitive_patterns = [
        # JSON-style pw values: "pw": "value"  # pragma: allowlist secret
        (
            re.compile(r'(["\'])password\1\s*:\s*["\'][^"\']*["\']', re.IGNORECASE),
            '"password": "[REDACTED]"',
        ),
        # Key-value password patterns: password=value or password: value
        (re.compile(r"password[=:]\s*\S+", re.IGNORECASE), "password=[REDACTED]"),
        # Bearer tokens
        (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer [REDACTED]"),
        # API keys in various formats
        (re.compile(r"api[_-]?key[=:]\s*\S+", re.IGNORECASE), "api_key=[REDACTED]"),
        # Secret/token values
        (re.compile(r"secret[=:]\s*\S+", re.IGNORECASE), "secret=[REDACTED]"),
        (re.compile(r"token[=:]\s*\S+", re.IGNORECASE), "token=[REDACTED]"),
        # IPv4 addresses (comes last to not interfere with URL patterns)
        (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP_REDACTED]"),
    ]

    for pattern, replacement in sensitive_patterns:
        sanitized = pattern.sub(replacement, sanitized)

    # Truncate very long messages
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."

    # Add context if provided
    if context:
        return f"Error {context}: {sanitized}"

    return sanitized


# =============================================================================
# Prometheus Metric Label Sanitization (NEM-1064)
# =============================================================================

# Maximum length for metric labels to prevent cardinality explosion
METRIC_LABEL_MAX_LENGTH = 64

# Pattern for valid Prometheus label values (printable ASCII, no special chars)
# Note: Prometheus accepts any UTF-8, but we limit for safety
METRIC_LABEL_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./: ]+$")

# Allowlist of known good values for common label types
KNOWN_OBJECT_CLASSES = frozenset(
    {
        "person",
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
        "dog",
        "cat",
        "bird",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
        "backpack",
        "umbrella",
        "handbag",
        "suitcase",
        "sports ball",
        "skateboard",
        "surfboard",
        "tennis racket",
        "bottle",
        "wine glass",
        "cup",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "pizza",
        "donut",
        "cake",
        "chair",
        "couch",
        "potted plant",
        "bed",
        "dining table",
        "toilet",
        "tv",
        "laptop",
        "mouse",
        "remote",
        "keyboard",
        "cell phone",
        "microwave",
        "oven",
        "toaster",
        "sink",
        "refrigerator",
        "book",
        "clock",
        "vase",
        "scissors",
        "teddy bear",
        "hair drier",
        "toothbrush",
        "unknown",
    }
)

KNOWN_ERROR_TYPES = frozenset(
    {
        "connection_error",
        "timeout_error",
        "validation_error",
        "processing_error",
        "rtdetr_connection_error",
        "rtdetr_timeout",
        "rtdetr_server_error",
        "rtdetr_client_error",
        "rtdetr_unexpected_error",
        "nemotron_connection_error",
        "nemotron_timeout",
        "nemotron_server_error",
        "nemotron_client_error",
        "file_not_found",
        "invalid_image",
        "malformed_response",
        "detection_processing_error",
        "queue_overflow",
        "database_error",
        "redis_error",
        "unknown_error",
    }
)

KNOWN_RISK_LEVELS = frozenset({"low", "medium", "high", "critical", "unknown"})

KNOWN_PIPELINE_STAGES = frozenset(
    {
        "detect",
        "batch",
        "analyze",
        "watch",
        "enrich",
        "store",
        "watch_to_detect",
        "detect_to_batch",
        "batch_to_analyze",
        "total_pipeline",
    }
)


def sanitize_metric_label(
    value: str,
    label_name: str = "",
    allowlist: frozenset[str] | None = None,
    max_length: int = METRIC_LABEL_MAX_LENGTH,
) -> str:
    """Sanitize a value for use as a Prometheus metric label.

    Prevents cardinality explosion by:
    1. Limiting length
    2. Normalizing to lowercase
    3. Replacing special characters
    4. Using allowlist when available

    Args:
        value: The label value to sanitize
        label_name: Optional label name for context-aware allowlist selection
        allowlist: Optional explicit allowlist of allowed values
        max_length: Maximum allowed length (default 64)

    Returns:
        Sanitized label value, or 'unknown' if invalid
    """
    if not value:
        return "unknown"

    # Normalize to lowercase
    value = str(value).lower().strip()

    if not value:
        return "unknown"

    # Select allowlist based on label name if not explicitly provided
    if allowlist is None:
        if label_name in ("object_class", "class"):
            allowlist = KNOWN_OBJECT_CLASSES
        elif label_name in ("error_type", "error"):
            allowlist = KNOWN_ERROR_TYPES
        elif label_name in ("level", "risk_level", "severity"):
            allowlist = KNOWN_RISK_LEVELS
        elif label_name in ("stage", "pipeline_stage"):
            allowlist = KNOWN_PIPELINE_STAGES

    # If we have an allowlist, use it
    if allowlist is not None:
        if value in allowlist:
            return value
        # Log unknown values for monitoring
        logger.debug(f"Unknown metric label value for {label_name}: {value[:50]}")
        return "other"

    # For labels without allowlist, sanitize the value
    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]

    # Replace characters that could cause issues
    # Only allow alphanumeric, underscore, hyphen, dot, colon, slash, and space
    if not METRIC_LABEL_PATTERN.match(value):
        # Replace invalid chars with underscore
        sanitized = ""
        for char in value:
            if char.isalnum() or char in "_-./: ":
                sanitized += char
            else:
                sanitized += "_"
        value = sanitized

    # Collapse multiple underscores
    value = re.sub(r"_+", "_", value).strip("_")

    if not value:
        return "unknown"

    return value


def sanitize_object_class(object_class: str) -> str:
    """Sanitize an object class for use in metrics.

    Uses allowlist of known COCO dataset classes.

    Args:
        object_class: The detected object class

    Returns:
        Sanitized class name, or 'other' if not in allowlist
    """
    return sanitize_metric_label(object_class, label_name="object_class")


def sanitize_error_type(error_type: str) -> str:
    """Sanitize an error type for use in metrics.

    Uses allowlist of known error types.

    Args:
        error_type: The error type string

    Returns:
        Sanitized error type, or 'other' if not in allowlist
    """
    return sanitize_metric_label(error_type, label_name="error_type")


def sanitize_risk_level(level: str) -> str:
    """Sanitize a risk level for use in metrics.

    Uses allowlist of known risk levels.

    Args:
        level: The risk level string

    Returns:
        Sanitized risk level, or 'unknown' if not in allowlist
    """
    return sanitize_metric_label(level, label_name="level")


def sanitize_camera_id(camera_id: str, max_length: int = 64) -> str:
    """Sanitize a camera ID for use in metrics.

    Camera IDs are user-defined so we can't use an allowlist,
    but we can limit length and normalize characters.

    Args:
        camera_id: The camera identifier
        max_length: Maximum allowed length

    Returns:
        Sanitized camera ID
    """
    if not camera_id:
        return "unknown"

    # Normalize
    camera_id = str(camera_id).strip()

    # Limit length
    if len(camera_id) > max_length:
        camera_id = camera_id[:max_length]

    # Only allow safe characters
    sanitized = ""
    for char in camera_id:
        if char.isalnum() or char in "_-":
            sanitized += char
        else:
            sanitized += "_"

    # Collapse multiple underscores and trim
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")

    return sanitized if sanitized else "unknown"


# =============================================================================
# URL Validation for Settings (NEM-1077)
# =============================================================================

# Blocked IP ranges for SSRF protection
BLOCKED_IP_NETWORKS = [
    # IPv4 Private Networks (RFC 1918)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Loopback (RFC 990)
    ipaddress.ip_network("127.0.0.0/8"),
    # Link-Local (RFC 3927) - includes cloud metadata
    ipaddress.ip_network("169.254.0.0/16"),
    # IPv6 Loopback
    ipaddress.ip_network("::1/128"),
    # IPv6 Link-Local
    ipaddress.ip_network("fe80::/10"),
]

# Known safe internal hosts (Docker/Podman internal networking)
ALLOWED_INTERNAL_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "host.docker.internal",
        "host.containers.internal",
        "grafana",  # Docker service name
    }
)


class URLValidationError(Exception):
    """Raised when URL validation fails."""

    pass


def validate_monitoring_url(
    url: str,
    *,
    allow_internal: bool = True,
    require_https: bool = False,
) -> str:
    """Validate a monitoring service URL (like Grafana).

    This validates that the URL:
    1. Is a well-formed HTTP/HTTPS URL
    2. Does not point to dangerous cloud metadata endpoints
    3. Optionally allows internal/private IPs (for local deployments)

    Args:
        url: The URL to validate
        allow_internal: If True, allow private/internal IPs (default True for monitoring)
        require_https: If True, require HTTPS scheme

    Returns:
        The validated URL

    Raises:
        URLValidationError: If the URL fails validation
    """
    if not url:
        raise URLValidationError("URL cannot be empty")

    url = url.strip()

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Invalid URL format: {e}") from e

    # Validate scheme
    if require_https:
        if parsed.scheme != "https":
            raise URLValidationError("Only HTTPS URLs are allowed")
    elif parsed.scheme not in ("http", "https"):
        raise URLValidationError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed")

    # Validate hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must have a hostname")

    # Always block cloud metadata endpoints (169.254.169.254)
    if hostname == "169.254.169.254":
        raise URLValidationError("Cloud metadata endpoint is not allowed")

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)

        # Always block link-local (metadata service)
        if ip in ipaddress.ip_network("169.254.0.0/16"):
            raise URLValidationError("Link-local addresses are not allowed")

        if not allow_internal:
            # Check against blocked networks
            for network in BLOCKED_IP_NETWORKS:
                if ip in network:
                    raise URLValidationError(
                        f"Private/internal IP addresses are not allowed: {hostname}"
                    )

    except ValueError:
        # Not an IP address, it's a hostname
        hostname_lower = hostname.lower()

        # Block dangerous hostnames
        dangerous_hostnames = {"metadata.google.internal", "metadata", "instance-data"}
        if hostname_lower in dangerous_hostnames:
            raise URLValidationError(
                f"Hostname '{hostname}' is blocked for security reasons"
            ) from None

    # Validate port if specified
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise URLValidationError(f"Invalid port number: {parsed.port}")

    # Remove trailing slash for consistency
    url = url.rstrip("/")

    return url


def validate_grafana_url(url: str) -> str:
    """Validate a Grafana dashboard URL.

    Allows internal URLs since Grafana is typically deployed alongside
    the application on the same network.

    Args:
        url: The Grafana URL to validate

    Returns:
        The validated URL

    Raises:
        URLValidationError: If the URL fails validation
    """
    return validate_monitoring_url(url, allow_internal=True, require_https=False)
