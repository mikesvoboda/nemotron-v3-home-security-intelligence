"""Centralized logging configuration for the application.

This module provides:
- Unified logger setup with console, file, and database handlers
- Structured JSON logging with contextual fields
- Request ID context propagation via contextvars
- Helper functions for getting configured loggers
- Error message sanitization for secure logging
"""

import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from backend.core.config import get_settings

# Patterns for sensitive data sanitization
_PATH_PATTERN = re.compile(r"(/[^\s:]+)+")
_CREDENTIAL_PATTERNS = [
    re.compile(r"(password|secret|token|api[_-]?key|auth)[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]

# Context variable for request ID propagation
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

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


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
