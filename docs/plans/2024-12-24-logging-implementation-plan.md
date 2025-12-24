# Logging System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add comprehensive structured logging with console, file, and SQLite outputs, plus admin UI for viewing logs.

**Architecture:** Unified logger module writes to all destinations; frontend captures errors and key events; admin UI provides filtering and dashboard.

**Tech Stack:** Python logging + python-json-logger, SQLAlchemy, FastAPI, React + TypeScript + Tailwind

**Beads Epic:** `home_security_intelligence-cfd` (Logging System)

---

## Phase 1: Backend Foundation

### Task 1: Add logging configuration to Settings

**Bead:** `home_security_intelligence-cfd.1`

**Files:**

- Modify: `backend/core/config.py`
- Modify: `.env.example` (if exists)

**Step 1: Add logging settings to Settings class**

Add after the `api_keys` field (around line 122):

```python
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
        description="Enable writing logs to SQLite database",
    )
    log_db_min_level: str = Field(
        default="DEBUG",
        description="Minimum log level to write to database",
    )
    log_retention_days: int = Field(
        default=7,
        description="Number of days to retain logs",
    )

    @field_validator("log_file_path")
    @classmethod
    def validate_log_file_path(cls, v: str) -> str:
        """Ensure log directory exists."""
        Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v
```

**Step 2: Run tests to verify no regressions**

```bash
pytest backend/tests/unit/test_config.py -v
```

Expected: All existing tests pass

**Step 3: Commit**

```bash
git add backend/core/config.py
git commit -m "feat(logging): add logging configuration settings"
```

---

### Task 2: Create Log SQLAlchemy model

**Bead:** `home_security_intelligence-cfd.3`

**Files:**

- Create: `backend/models/log.py`
- Modify: `backend/models/__init__.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/test_log_model.py`:

```python
"""Unit tests for Log model."""

import pytest
from datetime import datetime, timezone

from backend.models.log import Log


class TestLogModel:
    """Tests for Log SQLAlchemy model."""

    def test_log_creation(self):
        """Test creating a log entry."""
        log = Log(
            level="INFO",
            component="test",
            message="Test message",
        )
        assert log.level == "INFO"
        assert log.component == "test"
        assert log.message == "Test message"
        assert log.source == "backend"

    def test_log_with_metadata(self):
        """Test log with optional metadata fields."""
        log = Log(
            level="ERROR",
            component="file_watcher",
            message="File not found",
            camera_id="front_door",
            request_id="abc-123",
            duration_ms=45,
            extra={"file_path": "/export/foscam/test.jpg"},
        )
        assert log.camera_id == "front_door"
        assert log.request_id == "abc-123"
        assert log.duration_ms == 45
        assert log.extra == {"file_path": "/export/foscam/test.jpg"}

    def test_log_repr(self):
        """Test string representation."""
        log = Log(
            id=1,
            level="WARNING",
            component="api",
            message="Slow query",
        )
        repr_str = repr(log)
        assert "WARNING" in repr_str
        assert "api" in repr_str
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_log_model.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'backend.models.log'"

**Step 3: Create the Log model**

Create `backend/models/log.py`:

```python
"""Log model for structured application logging."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class Log(Base):
    """Log model for storing structured application logs.

    Supports filtering by level, component, camera, and time range.
    Stores additional context in JSON extra field.
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured metadata (nullable, for filtering)
    camera_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance/debug fields
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Source tracking
    source: Mapped[str] = mapped_column(String(10), default="backend", nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_logs_timestamp", "timestamp"),
        Index("idx_logs_level", "level"),
        Index("idx_logs_component", "component"),
        Index("idx_logs_camera_id", "camera_id"),
        Index("idx_logs_source", "source"),
    )

    def __repr__(self) -> str:
        return (
            f"<Log(id={self.id}, level={self.level!r}, "
            f"component={self.component!r}, message={self.message[:50]!r}...)>"
        )
```

**Step 4: Update models **init**.py**

Add to `backend/models/__init__.py`:

```python
from .log import Log

__all__ = ["APIKey", "Base", "Camera", "Detection", "Event", "GPUStats", "Log"]
```

**Step 5: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_log_model.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/models/log.py backend/models/__init__.py backend/tests/unit/test_log_model.py
git commit -m "feat(logging): add Log SQLAlchemy model with indexes"
```

---

### Task 3: Create unified logger module

**Bead:** `home_security_intelligence-cfd.2`

**Files:**

- Create: `backend/core/logging.py`
- Modify: `backend/core/__init__.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/test_logging.py`:

```python
"""Unit tests for logging module."""

import logging
import pytest
from unittest.mock import patch, MagicMock

from backend.core.logging import setup_logging, get_logger, get_request_id, set_request_id


class TestLoggingSetup:
    """Tests for logging configuration."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_request_id_context(self):
        """Test request_id context variable management."""
        # Initially should be None or empty
        initial = get_request_id()

        # Set a request ID
        set_request_id("test-request-123")
        assert get_request_id() == "test-request-123"

        # Clear it
        set_request_id(None)
        assert get_request_id() is None

    def test_setup_logging_configures_root_logger(self):
        """Test that setup_logging configures the logging system."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="DEBUG",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
                debug=True,
            )

            # Should not raise
            setup_logging()

            # Root logger should have handlers
            root = logging.getLogger()
            assert len(root.handlers) > 0
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/unit/test_logging.py -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create the logging module**

Create `backend/core/logging.py`:

```python
"""Centralized logging configuration for the application.

This module provides:
- Unified logger setup with console, file, and SQLite handlers
- Structured JSON logging with contextual fields
- Request ID context propagation via contextvars
- Helper functions for getting configured loggers
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger

from backend.core.config import get_settings

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
        record.request_id = get_request_id()
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
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
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["component"] = record.name

        # Add request_id if present
        if hasattr(record, "request_id") and record.request_id:
            log_record["request_id"] = record.request_id


class SQLiteHandler(logging.Handler):
    """Custom handler that writes logs to SQLite database.

    Uses async database sessions via a queue to avoid blocking.
    Falls back gracefully if database is unavailable.
    """

    def __init__(self, min_level: str = "DEBUG"):
        super().__init__()
        self.min_level = getattr(logging, min_level.upper(), logging.DEBUG)
        self._db_available = True

    def emit(self, record: logging.LogRecord) -> None:
        """Write log record to database."""
        if record.levelno < self.min_level:
            return

        if not self._db_available:
            return

        try:
            # Import here to avoid circular imports
            from backend.core.database import sync_session_factory
            from backend.models.log import Log

            # Extract extra fields from record
            extra_data = {}
            for key in ["camera_id", "event_id", "detection_id", "duration_ms", "file_path"]:
                if hasattr(record, key):
                    extra_data[key] = getattr(record, key)

            # Get structured extra if passed via extra dict
            if hasattr(record, "extra") and isinstance(record.extra, dict):
                extra_data.update(record.extra)

            log_entry = Log(
                timestamp=datetime.now(timezone.utc),
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

            with sync_session_factory() as session:
                session.add(log_entry)
                session.commit()

        except Exception:
            # Don't let logging failures crash the application
            # Disable DB logging if it fails repeatedly
            self._db_available = False


def setup_logging() -> None:
    """Configure application-wide logging.

    Sets up:
    - Console handler (StreamHandler) with colored output for development
    - File handler (RotatingFileHandler) with plain text for grep/tail
    - SQLite handler (custom) for admin UI queries
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

    # SQLite handler (if enabled)
    if settings.log_db_enabled:
        try:
            sqlite_handler = SQLiteHandler(min_level=settings.log_db_min_level)
            sqlite_handler.setLevel(log_level)
            sqlite_handler.setFormatter(logging.Formatter("%(message)s"))
            root_logger.addHandler(sqlite_handler)
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


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
```

**Step 4: Update core **init**.py**

Add to `backend/core/__init__.py`:

```python
from .logging import get_logger, get_request_id, set_request_id, setup_logging

__all__ = [
    # ... existing exports ...
    "get_logger",
    "get_request_id",
    "set_request_id",
    "setup_logging",
]
```

**Step 5: Add python-json-logger dependency**

```bash
cd backend && pip install python-json-logger
# Or add to pyproject.toml: python-json-logger>=2.0.0
```

**Step 6: Run test to verify it passes**

```bash
pytest backend/tests/unit/test_logging.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add backend/core/logging.py backend/core/__init__.py backend/tests/unit/test_logging.py
git commit -m "feat(logging): add unified logger with console, file, and SQLite handlers"
```

---

### Task 4: Create logs API schemas

**Bead:** `home_security_intelligence-cfd.4`

**Files:**

- Create: `backend/api/schemas/logs.py`

**Step 1: Create the schemas file**

Create `backend/api/schemas/logs.py`:

```python
"""Pydantic schemas for logs API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LogEntry(BaseModel):
    """Schema for a single log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Log entry ID")
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    component: str = Field(..., description="Component/module name")
    message: str = Field(..., description="Log message")
    camera_id: str | None = Field(None, description="Associated camera ID")
    event_id: int | None = Field(None, description="Associated event ID")
    request_id: str | None = Field(None, description="Request correlation ID")
    detection_id: int | None = Field(None, description="Associated detection ID")
    duration_ms: int | None = Field(None, description="Operation duration in milliseconds")
    extra: dict[str, Any] | None = Field(None, description="Additional structured data")
    source: str = Field("backend", description="Log source (backend, frontend)")


class LogsResponse(BaseModel):
    """Schema for paginated logs response."""

    logs: list[LogEntry] = Field(..., description="List of log entries")
    count: int = Field(..., description="Total count matching filters")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class LogStats(BaseModel):
    """Schema for log statistics (dashboard)."""

    total_today: int = Field(..., description="Total logs today")
    errors_today: int = Field(..., description="Error count today")
    warnings_today: int = Field(..., description="Warning count today")
    by_component: dict[str, int] = Field(..., description="Counts by component")
    by_level: dict[str, int] = Field(..., description="Counts by level")
    top_component: str | None = Field(None, description="Most active component")


class FrontendLogCreate(BaseModel):
    """Schema for frontend log submission."""

    level: str = Field(..., description="Log level", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    component: str = Field(..., description="Frontend component name", max_length=50)
    message: str = Field(..., description="Log message", max_length=2000)
    extra: dict[str, Any] | None = Field(None, description="Additional context")
    user_agent: str | None = Field(None, description="Browser user agent")
    url: str | None = Field(None, description="Page URL where log occurred")
```

**Step 2: Commit**

```bash
git add backend/api/schemas/logs.py
git commit -m "feat(logging): add Pydantic schemas for logs API"
```

---

### Task 5: Create logs API routes

**Bead:** `home_security_intelligence-cfd.5`

**Files:**

- Create: `backend/api/routes/logs.py`
- Modify: `backend/api/routes/__init__.py`

**Step 1: Write the failing test**

Create `backend/tests/integration/test_logs_api.py`:

```python
"""Integration tests for logs API endpoints."""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

from backend.models.log import Log


@pytest.mark.asyncio
class TestLogsAPI:
    """Tests for /api/logs endpoints."""

    async def test_list_logs_empty(self, client: AsyncClient, db_session):
        """Test listing logs when database is empty."""
        response = await client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        assert data["count"] == 0

    async def test_list_logs_with_data(self, client: AsyncClient, db_session):
        """Test listing logs with data."""
        # Create test logs
        log1 = Log(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            component="test",
            message="Test message 1",
        )
        log2 = Log(
            timestamp=datetime.now(timezone.utc),
            level="ERROR",
            component="test",
            message="Test error",
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        response = await client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["logs"]) == 2

    async def test_list_logs_filter_by_level(self, client: AsyncClient, db_session):
        """Test filtering logs by level."""
        log1 = Log(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            component="test",
            message="Info message",
        )
        log2 = Log(
            timestamp=datetime.now(timezone.utc),
            level="ERROR",
            component="test",
            message="Error message",
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        response = await client.get("/api/logs?level=ERROR")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["logs"][0]["level"] == "ERROR"

    async def test_get_log_stats(self, client: AsyncClient, db_session):
        """Test getting log statistics."""
        response = await client.get("/api/logs/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_today" in data
        assert "errors_today" in data
        assert "by_component" in data

    async def test_post_frontend_log(self, client: AsyncClient, db_session):
        """Test submitting a frontend log."""
        payload = {
            "level": "ERROR",
            "component": "DashboardPage",
            "message": "Failed to load data",
            "extra": {"endpoint": "/api/events"},
        }
        response = await client.post("/api/logs/frontend", json=payload)
        assert response.status_code == 201

        # Verify it was stored
        response = await client.get("/api/logs?component=DashboardPage")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["logs"][0]["source"] == "frontend"
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/integration/test_logs_api.py -v
```

Expected: FAIL (route doesn't exist)

**Step 3: Create the routes file**

Create `backend/api/routes/logs.py`:

```python
"""API routes for logs management."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.logs import (
    FrontendLogCreate,
    LogEntry,
    LogsResponse,
    LogStats,
)
from backend.core.database import get_db
from backend.models.log import Log

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogsResponse)
async def list_logs(
    level: str | None = Query(None, description="Filter by log level"),
    component: str | None = Query(None, description="Filter by component name"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    source: str | None = Query(None, description="Filter by source (backend, frontend)"),
    search: str | None = Query(None, description="Search in message text"),
    start_date: datetime | None = Query(None, description="Filter from date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter to date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List logs with optional filtering and pagination."""
    query = select(Log)

    # Apply filters
    if level:
        query = query.where(Log.level == level.upper())
    if component:
        query = query.where(Log.component == component)
    if camera_id:
        query = query.where(Log.camera_id == camera_id)
    if source:
        query = query.where(Log.source == source)
    if search:
        query = query.where(Log.message.ilike(f"%{search}%"))
    if start_date:
        query = query.where(Log.timestamp >= start_date)
    if end_date:
        query = query.where(Log.timestamp <= end_date)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort and paginate
    query = query.order_by(Log.timestamp.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": logs,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=LogStats)
async def get_log_stats(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get log statistics for dashboard."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Total today
    total_query = select(func.count()).where(Log.timestamp >= today_start)
    total_result = await db.execute(total_query)
    total_today = total_result.scalar() or 0

    # Errors today
    errors_query = select(func.count()).where(
        Log.timestamp >= today_start,
        Log.level == "ERROR",
    )
    errors_result = await db.execute(errors_query)
    errors_today = errors_result.scalar() or 0

    # Warnings today
    warnings_query = select(func.count()).where(
        Log.timestamp >= today_start,
        Log.level == "WARNING",
    )
    warnings_result = await db.execute(warnings_query)
    warnings_today = warnings_result.scalar() or 0

    # By component (today)
    component_query = (
        select(Log.component, func.count().label("count"))
        .where(Log.timestamp >= today_start)
        .group_by(Log.component)
        .order_by(func.count().desc())
    )
    component_result = await db.execute(component_query)
    by_component = {row.component: row.count for row in component_result}

    # By level (today)
    level_query = (
        select(Log.level, func.count().label("count"))
        .where(Log.timestamp >= today_start)
        .group_by(Log.level)
    )
    level_result = await db.execute(level_query)
    by_level = {row.level: row.count for row in level_result}

    # Top component
    top_component = list(by_component.keys())[0] if by_component else None

    return {
        "total_today": total_today,
        "errors_today": errors_today,
        "warnings_today": warnings_today,
        "by_component": by_component,
        "by_level": by_level,
        "top_component": top_component,
    }


@router.get("/{log_id}", response_model=LogEntry)
async def get_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
) -> Log:
    """Get a single log entry by ID."""
    result = await db.execute(select(Log).where(Log.id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log {log_id} not found",
        )

    return log


@router.post("/frontend", status_code=status.HTTP_201_CREATED)
async def create_frontend_log(
    log_data: FrontendLogCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive and store a log from the frontend."""
    # Get user agent from request if not provided
    user_agent = log_data.user_agent or request.headers.get("user-agent")

    log = Log(
        timestamp=datetime.now(timezone.utc),
        level=log_data.level.upper(),
        component=log_data.component,
        message=log_data.message,
        extra=log_data.extra,
        source="frontend",
        user_agent=user_agent,
    )

    db.add(log)
    await db.commit()

    return {"status": "created"}
```

**Step 4: Register the router**

Add to `backend/api/routes/__init__.py`:

```python
from .logs import router as logs_router

# In the include_routers function or router list:
# app.include_router(logs_router)
```

**Step 5: Run test to verify it passes**

```bash
pytest backend/tests/integration/test_logs_api.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/api/routes/logs.py backend/api/routes/__init__.py backend/tests/integration/test_logs_api.py
git commit -m "feat(logging): add logs API routes with filtering and stats"
```

---

## Phase 2: Backend Integration

### Task 6: Add request_id middleware

**Bead:** `home_security_intelligence-cfd.6`

**Files:**

- Create: `backend/api/middleware/request_id.py`
- Modify: `backend/main.py`

**Step 1: Create the middleware**

Create `backend/api/middleware/request_id.py`:

```python
"""Middleware for request ID generation and propagation."""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging import set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates and propagates request IDs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Generate request ID and set it in context."""
        # Get existing request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

        # Set in context for logging
        set_request_id(request_id)

        try:
            response = await call_next(request)
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Clear context
            set_request_id(None)
```

**Step 2: Add middleware to main.py**

Add after CORS middleware:

```python
from backend.api.middleware.request_id import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

**Step 3: Commit**

```bash
git add backend/api/middleware/request_id.py backend/main.py
git commit -m "feat(logging): add request_id middleware for log correlation"
```

---

### Task 7: Initialize logging in main.py

**Bead:** `home_security_intelligence-cfd.7`

**Files:**

- Modify: `backend/main.py`

**Step 1: Add logging initialization**

At the top of `backend/main.py`, before FastAPI app creation:

```python
from backend.core.logging import setup_logging

# Initialize logging before anything else
setup_logging()
```

**Step 2: Register logs router**

```python
from backend.api.routes.logs import router as logs_router

app.include_router(logs_router)
```

**Step 3: Verify the app starts**

```bash
cd backend && python -m uvicorn backend.main:app --reload
# Check logs appear in console and data/logs/security.log
```

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(logging): initialize logging and register logs router in main.py"
```

---

### Task 8: Add log retention to cleanup service

**Bead:** `home_security_intelligence-cfd.8`

**Files:**

- Modify: `backend/services/cleanup_service.py`

**Step 1: Add log cleanup method**

Add to `CleanupService` class:

```python
async def cleanup_old_logs(self) -> int:
    """Delete logs older than retention period.

    Returns:
        Number of logs deleted
    """
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.log_retention_days)

    async with self._db_factory() as session:
        result = await session.execute(
            delete(Log).where(Log.timestamp < cutoff)
        )
        await session.commit()
        deleted = result.rowcount

    if deleted > 0:
        logger.info(f"Cleaned up {deleted} logs older than {settings.log_retention_days} days")

    return deleted
```

**Step 2: Call from main cleanup method**

Add to the `run_cleanup` method:

```python
await self.cleanup_old_logs()
```

**Step 3: Commit**

```bash
git add backend/services/cleanup_service.py
git commit -m "feat(logging): add log retention cleanup to cleanup service"
```

---

## Phase 3: Frontend Implementation

### Task 9: Create frontend logger service

**Bead:** `home_security_intelligence-cfd.11`

**Files:**

- Create: `frontend/src/services/logger.ts`

**Step 1: Create the logger service**

Create `frontend/src/services/logger.ts`:

```typescript
/**
 * Frontend logging service that captures errors and events,
 * batches them, and sends to the backend for storage.
 */

type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

interface LogEntry {
  level: LogLevel;
  component: string;
  message: string;
  extra?: Record<string, unknown>;
  timestamp: string;
}

interface LoggerConfig {
  batchSize: number;
  flushIntervalMs: number;
  endpoint: string;
  enabled: boolean;
}

const defaultConfig: LoggerConfig = {
  batchSize: 10,
  flushIntervalMs: 5000,
  endpoint: "/api/logs/frontend",
  enabled: true,
};

class Logger {
  private queue: LogEntry[] = [];
  private config: LoggerConfig;
  private flushTimer: ReturnType<typeof setInterval> | null = null;

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
    this.startFlushTimer();
    this.setupGlobalHandlers();
  }

  private startFlushTimer(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    this.flushTimer = setInterval(() => {
      void this.flush();
    }, this.config.flushIntervalMs);
  }

  private setupGlobalHandlers(): void {
    // Capture unhandled errors
    window.onerror = (message, source, lineno, colno, error) => {
      this.error("Unhandled error", {
        message: String(message),
        source,
        lineno,
        colno,
        stack: error?.stack,
      });
      return false; // Don't prevent default handling
    };

    // Capture unhandled promise rejections
    window.onunhandledrejection = (event) => {
      this.error("Unhandled promise rejection", {
        reason: String(event.reason),
        stack: event.reason?.stack,
      });
    };
  }

  private log(
    level: LogLevel,
    component: string,
    message: string,
    extra?: Record<string, unknown>,
  ): void {
    const entry: LogEntry = {
      level,
      component,
      message,
      extra: {
        ...extra,
        url: window.location.href,
      },
      timestamp: new Date().toISOString(),
    };

    // Always log to console in development
    const consoleMethod =
      level === "ERROR" || level === "CRITICAL"
        ? "error"
        : level === "WARNING"
          ? "warn"
          : "log";
    console[consoleMethod](`[${level}] ${component}: ${message}`, extra);

    if (!this.config.enabled) return;

    this.queue.push(entry);

    if (this.queue.length >= this.config.batchSize) {
      void this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.queue.length === 0) return;

    const entries = [...this.queue];
    this.queue = [];

    try {
      await Promise.all(
        entries.map((entry) =>
          fetch(this.config.endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              level: entry.level,
              component: entry.component,
              message: entry.message,
              extra: entry.extra,
            }),
          }),
        ),
      );
    } catch (err) {
      // Re-queue failed entries (but limit to prevent infinite growth)
      if (this.queue.length < 100) {
        this.queue.unshift(...entries);
      }
      console.error("Failed to flush logs:", err);
    }
  }

  debug(message: string, extra?: Record<string, unknown>): void {
    this.log("DEBUG", "frontend", message, extra);
  }

  info(message: string, extra?: Record<string, unknown>): void {
    this.log("INFO", "frontend", message, extra);
  }

  warn(message: string, extra?: Record<string, unknown>): void {
    this.log("WARNING", "frontend", message, extra);
  }

  error(message: string, extra?: Record<string, unknown>): void {
    this.log("ERROR", "frontend", message, extra);
  }

  /**
   * Log a user event (navigation, button click, etc.)
   */
  event(eventName: string, extra?: Record<string, unknown>): void {
    this.log("INFO", "user_event", eventName, extra);
  }

  /**
   * Log an API error with details
   */
  apiError(endpoint: string, status: number, message: string): void {
    this.log("ERROR", "api", `API error: ${endpoint}`, {
      endpoint,
      status,
      message,
    });
  }

  /**
   * Create a component-specific logger
   */
  forComponent(component: string): ComponentLogger {
    return new ComponentLogger(this, component);
  }

  destroy(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    void this.flush();
  }
}

class ComponentLogger {
  constructor(
    private logger: Logger,
    private component: string,
  ) {}

  debug(message: string, extra?: Record<string, unknown>): void {
    (this.logger as any).log("DEBUG", this.component, message, extra);
  }

  info(message: string, extra?: Record<string, unknown>): void {
    (this.logger as any).log("INFO", this.component, message, extra);
  }

  warn(message: string, extra?: Record<string, unknown>): void {
    (this.logger as any).log("WARNING", this.component, message, extra);
  }

  error(message: string, extra?: Record<string, unknown>): void {
    (this.logger as any).log("ERROR", this.component, message, extra);
  }
}

// Export singleton instance
export const logger = new Logger();
export type { LogLevel, LogEntry, ComponentLogger };
```

**Step 2: Commit**

```bash
git add frontend/src/services/logger.ts
git commit -m "feat(logging): add frontend logger service with batching and global handlers"
```

---

### Task 10-15: Create UI Components

**Beads:** `home_security_intelligence-cfd.12` through `home_security_intelligence-cfd.17`

For brevity, these follow the same patterns as existing components (`EventTimeline`, `EventCard`, etc.). Key files to create:

- `frontend/src/components/logs/LogStatsCards.tsx` - Stats cards matching GpuStats style
- `frontend/src/components/logs/LogFilters.tsx` - Filter panel matching EventTimeline
- `frontend/src/components/logs/LogsTable.tsx` - Table with level badges, pagination
- `frontend/src/components/logs/LogDetailModal.tsx` - Modal matching EventDetailModal
- `frontend/src/components/logs/LogsDashboard.tsx` - Main page assembling all components

**Navigation integration:**

- Add to `frontend/src/App.tsx`: `<Route path="/logs" element={<LogsDashboard />} />`
- Add to navigation component: Logs tab with FileText icon from lucide-react

---

### Task 16: Add API functions to api.ts

**Bead:** Part of `home_security_intelligence-cfd.17`

Add to `frontend/src/services/api.ts`:

```typescript
export interface LogEntry {
  id: number;
  timestamp: string;
  level: string;
  component: string;
  message: string;
  camera_id?: string;
  event_id?: number;
  request_id?: string;
  extra?: Record<string, unknown>;
  source: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  count: number;
  limit: number;
  offset: number;
}

export interface LogStats {
  total_today: number;
  errors_today: number;
  warnings_today: number;
  by_component: Record<string, number>;
  by_level: Record<string, number>;
  top_component: string | null;
}

export interface LogsQueryParams {
  level?: string;
  component?: string;
  camera_id?: string;
  source?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export async function fetchLogs(
  params: LogsQueryParams = {},
): Promise<LogsResponse> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) searchParams.set(key, String(value));
  });
  const response = await fetch(`${API_BASE}/logs?${searchParams}`);
  if (!response.ok) throw new Error("Failed to fetch logs");
  return response.json();
}

export async function fetchLogStats(): Promise<LogStats> {
  const response = await fetch(`${API_BASE}/logs/stats`);
  if (!response.ok) throw new Error("Failed to fetch log stats");
  return response.json();
}

export async function fetchLog(id: number): Promise<LogEntry> {
  const response = await fetch(`${API_BASE}/logs/${id}`);
  if (!response.ok) throw new Error("Failed to fetch log");
  return response.json();
}
```

---

## Phase 4: Testing & Verification

### Task 17: Write backend unit tests

**Bead:** `home_security_intelligence-cfd.9`

Expand `backend/tests/unit/test_logging.py` with comprehensive tests.

### Task 18: Write logs API integration tests

**Bead:** `home_security_intelligence-cfd.10`

Expand `backend/tests/integration/test_logs_api.py` with edge cases.

### Task 19: Write frontend component tests

**Bead:** `home_security_intelligence-cfd.18`

Create tests matching existing patterns in `frontend/src/components/`.

### Task 20: End-to-end verification

**Bead:** `home_security_intelligence-cfd.20`

Manual verification checklist:

- [ ] Backend logs appear in console with correct format
- [ ] Logs rotate correctly when file size exceeded
- [ ] Logs appear in SQLite database
- [ ] Frontend errors captured and sent to backend
- [ ] Admin UI loads and displays logs
- [ ] Filters work correctly
- [ ] Pagination works
- [ ] Stats cards show correct counts
- [ ] Log detail modal shows full information

---

## Execution Order

The beads dependencies ensure correct execution order:

1. **Config** (cfd.1) → **Logger module** (cfd.2)
2. **Log model** (cfd.3) → **Schemas** (cfd.4) → **Routes** (cfd.5)
3. **Logger module** (cfd.2) → **Middleware** (cfd.6)
4. **Routes + Middleware** → **main.py init** (cfd.7)
5. **Log model** → **Cleanup service** (cfd.8)
6. **Routes** → **Frontend logger** (cfd.11)
7. **Frontend components** (cfd.12-15) → **Dashboard** (cfd.16) → **Navigation** (cfd.17)
8. **All** → **E2E verification** (cfd.20)

Check ready tasks with:

```bash
bd ready --label logging
```
