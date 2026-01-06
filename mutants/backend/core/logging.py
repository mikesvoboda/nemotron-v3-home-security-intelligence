"""Centralized logging configuration for the application.

This module provides:
- Unified logger setup with console, file, and database handlers
- Structured JSON logging with contextual fields
- Request ID context propagation via contextvars
- Helper functions for getting configured loggers
- Error message sanitization for secure logging
- URL redaction utilities for safe logging of connection strings
"""

import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
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


def redact_url(url: str) -> str:
    """Redact sensitive information from a URL for safe logging.

    Masks the password component of URLs while preserving the structure
    for debugging purposes. Works with database URLs, Redis URLs, and
    general HTTP URLs with authentication.

    Args:
        url: The URL to redact (e.g., postgresql://user:password@host:port/db)

    Returns:
        The URL with password replaced by [REDACTED], or the original URL
        if parsing fails or no password is present.

    Examples:
        >>> redact_url("postgresql+asyncpg://user:secret123@localhost:5432/db")
        'postgresql+asyncpg://user:[REDACTED]@localhost:5432/db'
        >>> redact_url("redis://default:mypassword@redis-host:6379/0")
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
    """Filter that adds contextual information to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id and other context to the log record."""
        record.request_id = get_request_id()  # type: ignore[attr-defined]
        return True


class CustomJsonFormatter(JsonFormatter):
    """Custom JSON formatter with ISO timestamp and extra fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the JSON log record."""
        super().add_fields(log_record, record, message_dict)

        # ISO timestamp
        log_record["timestamp"] = datetime.now(UTC).isoformat()
        log_record["level"] = record.levelname
        log_record["component"] = record.name

        # Add request_id if present
        if hasattr(record, "request_id") and record.request_id:
            log_record["request_id"] = record.request_id


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


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
