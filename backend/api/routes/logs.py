"""Frontend logging API routes for browser-side log ingestion.

This module provides endpoints for receiving log entries from the frontend
application. Logs are written to the structured logging infrastructure (Loki)
with component="frontend" for easy filtering and analysis.

The frontend logger.ts service sends logs to these endpoints:
- Individual logs via POST /api/logs/frontend
- Batched logs via POST /api/logs/frontend/batch (preferred)

All frontend logs are tagged with:
- component: "frontend" (or the component name provided in the request)
- source: "frontend" (for Loki label filtering)
- url: The browser URL where the log was generated
- user_agent: The browser user agent string

Usage:
    # Single log entry
    POST /api/logs/frontend
    {
        "level": "ERROR",
        "message": "Failed to load dashboard data",
        "component": "Dashboard",
        "extra": {"error_code": "API_TIMEOUT"}
    }

    # Batch of log entries
    POST /api/logs/frontend/batch
    {
        "entries": [
            {"level": "INFO", "message": "Page loaded", "component": "App"},
            {"level": "ERROR", "message": "API call failed", "component": "API"}
        ]
    }
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request

from backend.api.schemas.logs import (
    FrontendLogBatchRequest,
    FrontendLogEntry,
    FrontendLogResponse,
)
from backend.core.logging import get_logger, sanitize_log_value

logger = get_logger(__name__)

# Dedicated logger for frontend logs - separate from the route handler logger
# This allows different log levels/routing for frontend logs vs route logs
frontend_logger = get_logger("frontend")

router = APIRouter(prefix="/api/logs", tags=["logs"])

# Map frontend log levels to Python logging levels
_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _log_frontend_entry(entry: FrontendLogEntry, request: Request | None = None) -> bool:
    """Write a single frontend log entry to structured logging.

    Args:
        entry: The frontend log entry to write
        request: Optional FastAPI request for additional context (user-agent, etc.)

    Returns:
        True if logging succeeded, False otherwise
    """
    try:
        # Build extra context for the log record
        extra: dict[str, str | None] = {
            "source": "frontend",
            "frontend_component": sanitize_log_value(entry.component)
            if entry.component
            else "unknown",
        }

        # Add URL if provided
        if entry.url:
            extra["frontend_url"] = sanitize_log_value(entry.url)

        # Add user agent from request or entry
        if entry.user_agent:
            extra["frontend_user_agent"] = sanitize_log_value(entry.user_agent)
        elif request:
            user_agent = request.headers.get("user-agent")
            if user_agent:
                extra["frontend_user_agent"] = sanitize_log_value(user_agent)

        # Add timestamp if provided (as ISO string for structured logging)
        if entry.timestamp:
            extra["frontend_timestamp"] = entry.timestamp.isoformat()
        else:
            extra["frontend_timestamp"] = datetime.now(UTC).isoformat()

        # Add any additional context from the entry
        if entry.context:
            # Flatten context into extra with prefix to avoid collisions
            for key, value in entry.context.items():
                # Skip None values and limit key length
                if value is not None and len(key) <= 50:
                    sanitized_key = sanitize_log_value(key)
                    # Prefix context keys to distinguish from system fields
                    extra[f"ctx_{sanitized_key}"] = sanitize_log_value(value)

        # Get the Python log level
        log_level = _LOG_LEVEL_MAP.get(entry.level.value, logging.INFO)

        # Sanitize the message to prevent log injection
        sanitized_message = sanitize_log_value(entry.message)

        # Log with the frontend logger
        frontend_logger.log(
            log_level,
            f"[{entry.component or 'frontend'}] {sanitized_message}",
            extra=extra,
        )

        return True

    except Exception as e:
        # Log the error but don't fail the request
        logger.warning(f"Failed to process frontend log entry: {e}")
        return False


@router.post(
    "/frontend",
    response_model=FrontendLogResponse,
    summary="Ingest single frontend log",
    description="Receive a single log entry from the frontend for structured logging.",
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def ingest_frontend_log(
    entry: FrontendLogEntry,
    request: Request,
) -> FrontendLogResponse:
    """Ingest a single frontend log entry.

    Receives a log entry from the frontend and writes it to the structured
    logging infrastructure (Loki). This endpoint is used as a fallback when
    the batch endpoint is not available.

    Args:
        entry: The frontend log entry to ingest
        request: FastAPI request object for additional context

    Returns:
        FrontendLogResponse with ingestion status
    """
    success = _log_frontend_entry(entry, request)

    return FrontendLogResponse(
        success=success,
        count=1 if success else 0,
        message="Successfully ingested 1 log entry" if success else "Failed to ingest log entry",
    )


@router.post(
    "/frontend/batch",
    response_model=FrontendLogResponse,
    summary="Ingest batch of frontend logs",
    description="Receive a batch of log entries from the frontend for structured logging.",
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def ingest_frontend_logs_batch(
    batch: FrontendLogBatchRequest,
    request: Request,
) -> FrontendLogResponse:
    """Ingest a batch of frontend log entries.

    Receives multiple log entries from the frontend and writes them to the
    structured logging infrastructure (Loki). This is the preferred endpoint
    as it reduces API calls and improves performance.

    Args:
        batch: Batch of frontend log entries to ingest
        request: FastAPI request object for additional context

    Returns:
        FrontendLogResponse with ingestion status and count
    """
    success_count = 0
    total_count = len(batch.entries)

    for entry in batch.entries:
        if _log_frontend_entry(entry, request):
            success_count += 1

    # Log summary at debug level
    if success_count < total_count:
        logger.warning(
            f"Frontend log batch partially processed: {success_count}/{total_count} entries"
        )
    else:
        logger.debug(f"Frontend log batch processed: {success_count} entries")

    return FrontendLogResponse(
        success=success_count > 0,
        count=success_count,
        message=f"Successfully ingested {success_count} log entry(ies)"
        if success_count > 0
        else "No log entries were ingested",
    )
