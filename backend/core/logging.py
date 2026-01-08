"""Centralized logging configuration for the application.

This module provides:
- Unified logger setup with console, file, and database handlers
- Structured JSON logging with contextual fields
- Request ID context propagation via contextvars
- Helper functions for getting configured loggers
- Error message sanitization for secure logging
- URL redaction utilities for safe logging of connection strings
"""

__all__ = [
    # Constants
    "CONSOLE_FORMAT",
    "FILE_FORMAT",
    "SENSITIVE_FIELD_NAMES",
    # Classes
    "ContextFilter",
    "CustomJsonFormatter",
    "DatabaseHandler",
    "SQLiteHandler",  # Backwards compatibility alias
    # Functions
    "get_current_trace_context",
    "get_log_context",
    "get_logger",
    "get_request_id",
    "log_context",
    "log_error",
    "log_exception_with_context",
    "mask_ip",
    "redact_sensitive_value",
    "redact_url",
    "sanitize_error",
    "sanitize_log_value",
    "set_request_id",
    "setup_logging",
]

import logging
import re
import sys
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from pythonjsonlogger.json import JsonFormatter

from backend.core.config import get_settings

# Patterns for sensitive data sanitization
_PATH_PATTERN = re.compile(r"(/[^\s:]+)+")
_CREDENTIAL_PATTERNS = [
    re.compile(r"(password|secret|token|api[_-]?key|auth)[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]

# List of sensitive field names (for Settings redaction)
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "secret",
        "key",
        "token",
        "credential",
        "api_key",
        "api_keys",
        "admin_api_key",
        "rtdetr_api_key",
        "nemotron_api_key",
        "smtp_password",
        "database_url",
        "redis_url",
    }
)

# Context variable for request ID propagation
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Context variable for structured log context propagation (NEM-1645)
# Stores a dict of context fields that are automatically added to all logs within scope
# Note: Using None default to avoid mutable default (B039 linting rule)
_log_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, Any]:
    """Get the current structured log context.

    Returns:
        A copy of the current context dictionary. Returns empty dict if no context is set.

    Example:
        with log_context(camera_id="front_door", operation="detect"):
            ctx = get_log_context()
            # ctx == {"camera_id": "front_door", "operation": "detect"}
    """
    ctx = _log_context.get()
    return dict(ctx) if ctx is not None else {}


def _get_otel_current_span() -> Any:
    """Get the current OpenTelemetry span from context.

    This is a helper function that safely attempts to get the current span
    from OpenTelemetry's trace context. Returns None if OpenTelemetry is
    not installed or if no span is currently active.

    Returns:
        The current span object if available, None otherwise.
    """
    try:
        from opentelemetry import trace

        return trace.get_current_span()
    except ImportError:
        return None
    except Exception:
        return None


def get_current_trace_context() -> dict[str, str | None]:
    """Get the current OpenTelemetry trace context for log correlation.

    This function extracts trace_id and span_id from the active OpenTelemetry
    span context, enabling log-to-trace correlation in observability platforms
    like Grafana, Jaeger, or Tempo.

    The trace IDs are formatted as lowercase hexadecimal strings (32 chars for
    trace_id, 16 chars for span_id), which is the standard W3C Trace Context format.

    Returns:
        Dict with 'trace_id' and 'span_id' keys. Values are hex strings if a
        valid span is active, None otherwise.

    Example:
        ctx = get_current_trace_context()
        # If OTel is active: {'trace_id': '1234...', 'span_id': 'abcd...'}
        # If OTel is not active: {'trace_id': None, 'span_id': None}

    NEM-1638: Enhanced structured logging with trace context.
    """
    result: dict[str, str | None] = {"trace_id": None, "span_id": None}

    try:
        span = _get_otel_current_span()
        if span is None:
            return result

        # Get span context
        span_context = span.get_span_context()
        if not span_context or not span_context.is_valid:
            return result

        # Format trace_id and span_id as lowercase hex strings
        # trace_id is 128-bit (32 hex chars), span_id is 64-bit (16 hex chars)
        result["trace_id"] = format(span_context.trace_id, "032x")
        result["span_id"] = format(span_context.span_id, "016x")

    except (ImportError, AttributeError, TypeError):
        # OpenTelemetry not installed or span context not valid
        pass
    except Exception:  # noqa: S110 - Intentionally silent to not break logging
        # Any other error - don't let tracing break logging
        pass

    return result


@contextmanager
def log_context(**kwargs: Any) -> Generator[None]:
    """Context manager for enriched logging within a scope.

    All logs made within this context will automatically include the provided
    keyword arguments as extra fields. This is useful for adding consistent
    context (like camera_id, operation, retry_count) to all log messages
    without repeating them in each log call.

    Nested contexts are supported: inner contexts inherit and can override
    outer context fields. When the inner context exits, the outer context
    is restored.

    Args:
        **kwargs: Key-value pairs to add to all log records in this scope.
            Common fields include:
            - camera_id: Camera identifier
            - event_id: Event identifier
            - detection_id: Detection identifier
            - operation: Current operation being performed
            - retry_count: Current retry attempt number
            - service: External service name

    Yields:
        None

    Example:
        with log_context(camera_id="front_door", operation="detect"):
            logger.info("Starting detection")  # Includes camera_id and operation
            try:
                result = await detect_objects(image_path)
            except TimeoutError as e:
                logger.error("Detection timed out")  # Also includes camera_id and operation
                raise

        # Nested context example:
        with log_context(camera_id="front_door"):
            with log_context(operation="detect", retry_count=1):
                logger.info("Processing")
                # Includes camera_id, operation, and retry_count
    """
    # Get the current context and merge with new values
    current = _log_context.get() or {}
    # Create a new dict that combines current context with new values
    # New values override existing ones with the same key
    merged = {**current, **kwargs}

    # Set the merged context
    token = _log_context.set(merged)
    try:
        yield
    finally:
        # Restore the previous context
        _log_context.reset(token)


def redact_url(url: str) -> str:
    """Redact sensitive information from a URL for safe logging.

    Masks the password component of URLs while preserving the structure
    for debugging purposes. Works with database URLs, Redis URLs, and
    general HTTP URLs with authentication.

    Args:
        url: The URL to redact (e.g., postgresql://user:***@host:port/db)

    Returns:
        The URL with password replaced by [REDACTED], or the original URL
        if parsing fails or no password is present.

    Examples:
        >>> redact_url("postgresql+asyncpg://user:pass123@localhost:5432/db")  # pragma: allowlist secret
        'postgresql+asyncpg://user:[REDACTED]@localhost:5432/db'
        >>> redact_url("redis://default:redispass@redis-host:6379/0")  # pragma: allowlist secret
        'redis://default:[REDACTED]@redis-host:6379/0'
        >>> redact_url("http://localhost:8000")
        'http://localhost:8000'
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)

        # If there's no password, return as-is
        if not parsed.password:
            return url

        # Reconstruct netloc with redacted password
        # Format: [user[:password]@]host[:port]
        if parsed.username:
            redacted_netloc = f"{parsed.username}:[REDACTED]@{parsed.hostname}"
        else:
            redacted_netloc = f"[REDACTED]@{parsed.hostname}"

        if parsed.port:
            redacted_netloc = f"{redacted_netloc}:{parsed.port}"

        # Rebuild the URL with redacted netloc
        redacted = urlunparse(
            (
                parsed.scheme,
                redacted_netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )
        return redacted
    except Exception:
        # If parsing fails, return a safe fallback
        return "[URL REDACTED - PARSE ERROR]"


def redact_sensitive_value(field_name: str, value: Any) -> Any:
    """Redact a value if the field name indicates it's sensitive.

    This function checks if a field name matches known sensitive patterns
    and returns a redacted version of the value if so.

    Args:
        field_name: The name of the field (e.g., 'database_url', 'api_key')
        value: The value to potentially redact

    Returns:
        '[REDACTED]' if the field is sensitive, or the original value otherwise.
        For URL fields (database_url, redis_url), returns redacted URL preserving structure.
    """
    field_lower = field_name.lower()

    # Check if field name matches sensitive patterns
    is_sensitive = field_lower in SENSITIVE_FIELD_NAMES or any(
        pattern in field_lower for pattern in ("password", "secret", "key", "token", "credential")
    )

    if not is_sensitive:
        return value

    # For URL fields, use redact_url to preserve structure
    if field_lower in ("database_url", "redis_url") and isinstance(value, str):
        return redact_url(value)

    # For list values (like api_keys), redact each item
    if isinstance(value, list):
        return ["[REDACTED]"] * len(value) if value else []

    # For other sensitive values, fully redact
    return "[REDACTED]"


# Standard log format for console/file
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return _request_id.get()


def set_request_id(request_id: str | None) -> None:
    """Set the request ID in context."""
    _request_id.set(request_id)


class ContextFilter(logging.Filter):
    """Filter that adds contextual information to log records.

    This filter automatically injects:
    - request_id: From the request context (set by middleware)
    - correlation_id: From the correlation context (set by middleware) (NEM-1638)
    - trace_id: From OpenTelemetry span context (NEM-1638)
    - span_id: From OpenTelemetry span context (NEM-1638)
    - connection_id: From WebSocket connection context (NEM-1640)
    - log_context fields: From the log_context context manager (NEM-1645)

    The log_context fields are merged with any explicit extra= fields passed
    to the log call, with explicit extra values taking precedence.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add contextual fields to the log record for observability.

        This method enriches every log record with:
        1. request_id from the request context (for request correlation)
        2. correlation_id from correlation context (for cross-service tracing)
        3. trace_id and span_id from OpenTelemetry (for log-to-trace correlation)
        4. connection_id from WebSocket context (for WebSocket connection tracing)
        5. All fields from the current log_context (for structured error context)

        Log context fields are set as attributes on the record, making them
        available to formatters and handlers. Explicit extra= values passed to
        the log call take precedence over context values.

        Args:
            record: The log record to enrich

        Returns:
            True (always allows the record through)

        NEM-1638: Enhanced structured logging with trace context.
        """
        # Add request_id from context (only if not explicitly provided via extra=)
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()  # type: ignore[attr-defined]

        # Add correlation_id from middleware context (NEM-1638)
        # Only set if not explicitly provided via extra=
        if not hasattr(record, "correlation_id"):
            try:
                from backend.api.middleware.request_id import get_correlation_id

                record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
            except ImportError:
                # Module not yet available during startup
                record.correlation_id = None  # type: ignore[attr-defined]

        # Add OpenTelemetry trace context (NEM-1638)
        # Only set trace_id if not explicitly provided via extra=
        if not hasattr(record, "trace_id"):
            trace_ctx = get_current_trace_context()
            record.trace_id = trace_ctx["trace_id"]  # type: ignore[attr-defined]
            # span_id only set if trace_id was set from context
            if not hasattr(record, "span_id"):
                record.span_id = trace_ctx["span_id"]  # type: ignore[attr-defined]
        elif not hasattr(record, "span_id"):
            # trace_id was explicit, but span_id might not be
            trace_ctx = get_current_trace_context()
            record.span_id = trace_ctx["span_id"]  # type: ignore[attr-defined]

        # Add connection_id from async_context module (NEM-1640)
        # Imported lazily to avoid circular imports during startup
        # Only set if not explicitly provided via extra=
        if not hasattr(record, "connection_id"):
            try:
                from backend.core.async_context import get_connection_id

                record.connection_id = get_connection_id()  # type: ignore[attr-defined]
            except ImportError:
                # Module not yet available during startup
                record.connection_id = None  # type: ignore[attr-defined]

        # Add log_context fields (NEM-1645)
        # These are set via the log_context context manager
        context = get_log_context()
        for key, value in context.items():
            # Only set if not already present (explicit extra= takes precedence)
            if not hasattr(record, key):
                setattr(record, key, value)

        return True


class CustomJsonFormatter(JsonFormatter):
    """Custom JSON formatter with ISO timestamp, trace context, and extra fields.

    NEM-1638: Enhanced to include trace_id, span_id, and correlation_id for
    log aggregation and log-to-trace correlation in observability platforms.
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the JSON log record.

        Fields added:
        - timestamp: ISO 8601 formatted timestamp with timezone
        - level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - component: Logger name (typically module path)
        - request_id: Request correlation ID (if present)
        - correlation_id: Cross-service correlation ID (if present) (NEM-1638)
        - trace_id: OpenTelemetry trace ID for log-to-trace correlation (NEM-1638)
        - span_id: OpenTelemetry span ID for log-to-trace correlation (NEM-1638)
        - Structured context fields: camera_id, event_id, detection_id, etc.
        """
        super().add_fields(log_record, record, message_dict)

        # ISO timestamp for log aggregation (Loki, ELK, etc.)
        log_record["timestamp"] = datetime.now(UTC).isoformat()
        log_record["level"] = record.levelname
        log_record["component"] = record.name

        # Add request_id if present (for request correlation)
        if hasattr(record, "request_id") and record.request_id:
            log_record["request_id"] = record.request_id

        # Add correlation_id if present (for cross-service tracing) (NEM-1638)
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_record["correlation_id"] = record.correlation_id

        # Add OpenTelemetry trace context if present (NEM-1638)
        # These fields enable log-to-trace correlation in Grafana/Tempo/Jaeger
        if hasattr(record, "trace_id") and record.trace_id:
            log_record["trace_id"] = record.trace_id
        if hasattr(record, "span_id") and record.span_id:
            log_record["span_id"] = record.span_id

        # Add structured context fields commonly used in this application
        # These support filtering and aggregation in log management systems
        context_fields = [
            "camera_id",
            "event_id",
            "detection_id",
            "duration_ms",
            "connection_id",
            "detection_count",
        ]
        for field in context_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None:
                    log_record[field] = value


class DatabaseHandler(logging.Handler):
    """Custom handler that writes logs to PostgreSQL database.

    Uses synchronous database sessions to avoid blocking async context.
    Falls back gracefully if database is unavailable.
    """

    def __init__(self, min_level: str = "DEBUG") -> None:
        super().__init__()
        self.min_level = getattr(logging, min_level.upper(), logging.DEBUG)
        self._db_available = True
        self._engine: Any = None
        self._session_factory: Any = None

    def _get_session(self) -> Any:
        """Get a sync session for database writes."""
        if self._session_factory is None:
            try:
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker

                settings = get_settings()
                # Convert async URL to sync URL for PostgreSQL
                sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql")

                self._engine = create_engine(sync_url)
                self._session_factory = sessionmaker(bind=self._engine)
            except Exception:
                self._db_available = False
                return None

        return self._session_factory()

    def emit(self, record: logging.LogRecord) -> None:
        """Write log record to database."""
        if record.levelno < self.min_level:
            return

        if not self._db_available:
            return

        try:
            # Import here to avoid circular imports
            from backend.models.log import Log

            session = self._get_session()
            if session is None:
                return

            # Extract extra fields from record
            extra_data: dict[str, Any] = {}
            for key in ["camera_id", "event_id", "detection_id", "duration_ms", "file_path"]:
                if hasattr(record, key):
                    val = getattr(record, key)
                    if val is not None:
                        extra_data[key] = val

            # Get structured extra if passed via extra dict
            if hasattr(record, "extra") and isinstance(record.extra, dict):  # type: ignore[attr-defined]
                extra_data.update(record.extra)  # type: ignore[attr-defined]

            log_entry = Log(
                timestamp=datetime.now(UTC),
                level=record.levelname,
                component=record.name,
                message=self.format(record),
                camera_id=getattr(record, "camera_id", None),
                event_id=getattr(record, "event_id", None),
                request_id=getattr(record, "request_id", None),
                detection_id=getattr(record, "detection_id", None),
                duration_ms=getattr(record, "duration_ms", None),
                extra=extra_data if extra_data else None,
                source="backend",
            )

            try:
                session.add(log_entry)
                session.commit()
            finally:
                session.close()

        except Exception:
            # Don't let logging failures crash the application
            # Disable DB logging if it fails repeatedly
            self._db_available = False


# Backwards compatibility alias
SQLiteHandler = DatabaseHandler


def setup_logging() -> None:
    """Configure application-wide logging.

    Sets up:
    - Console handler (StreamHandler) with plain text for development
    - File handler (RotatingFileHandler) with plain text for grep/tail
    - Database handler (PostgreSQL) for admin UI queries
    """
    settings = get_settings()

    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add context filter to root logger
    context_filter = ContextFilter()
    root_logger.addFilter(context_filter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (rotating)
    try:
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(FILE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        root_logger.warning(f"Could not set up file logging: {e}")

    # Database handler (if enabled)
    if settings.log_db_enabled:
        try:
            db_handler = DatabaseHandler(min_level=settings.log_db_min_level)
            db_handler.setLevel(log_level)
            db_handler.setFormatter(logging.Formatter("%(message)s"))
            root_logger.addHandler(db_handler)
        except Exception as e:
            root_logger.warning(f"Could not set up database logging: {e}")

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)

    root_logger.info(
        f"Logging configured: level={settings.log_level}, "
        f"file={settings.log_file_path}, db_enabled={settings.log_db_enabled}"
    )


def sanitize_error(error: Exception, max_length: int = 500) -> str:
    """Sanitize error message for secure logging.

    Removes potentially sensitive information from error messages:
    - Full file paths (keeps only filename)
    - Credentials/tokens/API keys
    - Truncates long error messages

    Args:
        error: The exception to sanitize
        max_length: Maximum length of the sanitized message (default 500)

    Returns:
        Sanitized error message safe for logging
    """
    msg = str(error)

    # Remove credential patterns
    for pattern in _CREDENTIAL_PATTERNS:
        msg = pattern.sub("[REDACTED]", msg)

    # Simplify file paths - keep only the filename for context
    def _simplify_path(match: re.Match[str]) -> str:
        path = match.group(0)
        # Keep the filename portion
        parts = path.rsplit("/", 1)
        if len(parts) == 2:
            return f".../{parts[1]}"
        return path

    msg = _PATH_PATTERN.sub(_simplify_path, msg)

    # Truncate long messages
    if len(msg) > max_length:
        msg = msg[:max_length] + "...[truncated]"

    return msg


def mask_ip(ip: str) -> str:
    """Mask an IP address for safe logging.

    Preserves the first octet (IPv4) or first segment (IPv6) for debugging
    while protecting user privacy by masking the rest.

    Args:
        ip: IP address string to mask

    Returns:
        Masked IP address safe for logging

    Examples:
        >>> mask_ip("192.168.1.100")
        '192.xxx.xxx.xxx'
        >>> mask_ip("2001:0db8:85a3::8a2e")
        '2001:xxxx:xxxx:xxxx'
        >>> mask_ip("unknown")
        'unknown'
    """
    if not ip or ip == "unknown":
        return ip or "unknown"

    # IPv6 detection
    if ":" in ip:
        parts = ip.split(":")
        if len(parts) >= 2:
            return f"{parts[0]}:xxxx:xxxx:xxxx"
        return "xxxx:xxxx:xxxx:xxxx"

    # IPv4
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.xxx.xxx.xxx"

    # Fallback for invalid format
    return "xxx.xxx.xxx.xxx"


def sanitize_log_value(value: Any) -> str:
    """Sanitize a value for safe inclusion in log messages.

    Removes or escapes characters that could enable log injection attacks:
    - Newline characters (\\n, \\r) that could forge log entries
    - Control characters that could manipulate terminal output
    - Null bytes that could truncate logs

    This function helps prevent CWE-117 (Log Injection) vulnerabilities.

    Args:
        value: The value to sanitize for logging

    Returns:
        String representation safe for inclusion in log messages

    Examples:
        >>> sanitize_log_value("normal value")
        'normal value'
        >>> sanitize_log_value("line1\\nFAKE_LOG_ENTRY")
        'line1 FAKE_LOG_ENTRY'
        >>> sanitize_log_value(None)
        'None'
    """
    if value is None:
        return "None"

    # Convert to string
    str_value = str(value)

    # Remove or replace dangerous characters:
    # - Newlines and carriage returns (log injection)
    # - Null bytes (log truncation)
    # - Other control characters (terminal manipulation)
    sanitized = str_value.replace("\n", " ").replace("\r", " ").replace("\x00", "")

    # Remove other control characters (ASCII 0-31 except tab and space)
    sanitized = "".join(char if ord(char) >= 32 or char == "\t" else " " for char in sanitized)

    return sanitized


@lru_cache(maxsize=128)
def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    The returned logger will have the ContextFilter attached to ensure
    request_id and other context variables are included in log records.

    Results are cached to avoid repeated filter checks and logger lookups.
    The cache size of 128 accommodates most module hierarchies while
    bounding memory usage.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured logger instance with context filter
    """
    logger = logging.getLogger(name)

    # Ensure ContextFilter is added to this logger if not already present
    # This handles loggers created before setup_logging() is called
    has_context_filter = any(isinstance(f, ContextFilter) for f in logger.filters)
    if not has_context_filter:
        logger.addFilter(ContextFilter())

    return logger


def log_exception_with_context(
    logger: logging.Logger,
    exception: Exception,
    message: str,
    *,
    include_traceback: bool = True,
    level: int = logging.ERROR,
    **extra_context: Any,
) -> None:
    """Log an exception with structured context for debugging.

    This helper function logs exceptions with rich contextual information
    including error type, sanitized message, and any additional context
    provided by the caller. It automatically includes the request_id from
    context if available.

    Args:
        logger: The logger instance to use
        exception: The exception to log
        message: Human-readable description of what failed
        include_traceback: Whether to include the full stack trace (default: True)
        level: Log level to use (default: logging.ERROR)
        **extra_context: Additional context fields to include in the log record
            (e.g., camera_id="front_door", operation="detection")

    Example:
        try:
            result = await detect_objects(image_path)
        except TimeoutError as e:
            log_exception_with_context(
                logger,
                e,
                "Detection request timed out",
                camera_id=camera_id,
                service="rtdetr",
                timeout_seconds=30,
            )
    """
    # Build structured extra dict with error context
    extra: dict[str, Any] = {
        "error_type": type(exception).__name__,
        "error_message_sanitized": sanitize_error(exception),
        **extra_context,
    }

    # Log with or without traceback
    logger.log(
        level,
        message,
        extra=extra,
        exc_info=include_traceback,
    )


def log_error(
    logger: logging.Logger,
    message: str,
    *,
    error: Exception | None = None,
    request_id: str | None = None,
    extra: dict[str, Any] | None = None,
    exc_info: bool = False,
) -> None:
    """Log an error with consistent structure and automatic request context.

    This is a simplified error logging helper that automatically includes
    the request ID from context (if not explicitly provided) and structures
    error information consistently. It's designed for cases where you want
    to log an error with optional exception details, without requiring an
    exception object.

    The function builds a structured extra dict containing:
    - request_id: From context or explicitly provided
    - error_type: Exception class name (if error provided)
    - Any additional fields from the extra parameter

    Args:
        logger: The logger instance to use
        message: Human-readable description of the error
        error: Optional exception that caused the error (default: None)
        request_id: Optional explicit request ID, defaults to context value
        extra: Optional dict of additional fields to include in the log
        exc_info: Whether to include traceback info (default: False)

    Example:
        # Log error without exception
        log_error(logger, "Database connection pool exhausted")

        # Log error with exception
        try:
            await process_image(path)
        except TimeoutError as e:
            log_error(
                logger,
                "Image processing timed out",
                error=e,
                extra={"camera_id": "front_door", "timeout_ms": 5000},
            )

        # Log error with explicit request ID
        log_error(
            logger,
            "Failed to validate token",
            request_id="req-abc123",
            extra={"user_agent": "Mozilla/5.0..."},
        )
    """
    # Build structured extra dict
    log_extra: dict[str, Any] = {
        "request_id": request_id if request_id is not None else get_request_id(),
        "error_type": type(error).__name__ if error else None,
    }

    # Merge any additional extra fields
    if extra:
        log_extra.update(extra)

    # Add sanitized error message if exception provided
    if error:
        log_extra["error_message_sanitized"] = sanitize_error(error)

    logger.error(message, extra=log_extra, exc_info=exc_info)
