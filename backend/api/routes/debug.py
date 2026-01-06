"""Debug API endpoints for pipeline inspection and runtime debugging.

This module provides debug endpoints for:
- Pipeline state inspection (queue depths, worker status, recent errors)
- Log level runtime override
- Correlation ID propagation testing

These endpoints are designed for debugging and should be protected in production
environments via the DEBUG_MODE setting.

NEM-1470: Pipeline state inspection
NEM-1471: Log level runtime override
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.logging import get_logger, get_request_id
from backend.core.redis import RedisClient, get_redis_optional

logger = get_logger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])

# Valid log levels
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# =============================================================================
# Pydantic Models
# =============================================================================


class QueueDepths(BaseModel):
    """Queue depth information for AI pipeline."""

    detection_queue: int = Field(description="Number of items in detection queue")
    analysis_queue: int = Field(description="Number of items in analysis queue")


class WorkerStatus(BaseModel):
    """Status of a pipeline worker."""

    name: str = Field(description="Worker name")
    running: bool = Field(description="Whether worker is currently running")
    last_activity: str | None = Field(default=None, description="ISO timestamp of last activity")
    error_count: int = Field(default=0, description="Number of recent errors")


class WorkersStatus(BaseModel):
    """Status of all pipeline workers."""

    file_watcher: WorkerStatus = Field(description="File watcher status")
    detector: WorkerStatus = Field(description="Detector worker status")
    analyzer: WorkerStatus = Field(description="Analyzer worker status")


class RecentError(BaseModel):
    """Recent error information."""

    timestamp: str = Field(description="ISO timestamp of error")
    error_type: str = Field(description="Type of error")
    component: str = Field(description="Component that generated error")
    message: str | None = Field(default=None, description="Error message")


class PipelineStateResponse(BaseModel):
    """Response for pipeline state inspection."""

    queue_depths: QueueDepths = Field(description="Current queue depths")
    workers: WorkersStatus = Field(description="Worker status")
    recent_errors: list[RecentError] = Field(
        default_factory=list, description="Recent errors (last 10)"
    )
    timestamp: str = Field(description="ISO timestamp of response")
    correlation_id: str | None = Field(default=None, description="Correlation ID from request")


class LogLevelRequest(BaseModel):
    """Request to change log level."""

    level: str = Field(description="New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")


class LogLevelResponse(BaseModel):
    """Response for log level operations."""

    level: str = Field(description="Current log level")
    previous_level: str | None = Field(default=None, description="Previous log level (on change)")
    timestamp: str = Field(description="ISO timestamp of response")


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_queue_depths(redis: RedisClient | None) -> QueueDepths:
    """Get current queue depths from Redis.

    Args:
        redis: Redis client instance or None if unavailable
    """
    if redis is None:
        return QueueDepths(detection_queue=0, analysis_queue=0)

    try:
        detection_depth = await redis.llen(DETECTION_QUEUE)
        analysis_depth = await redis.llen(ANALYSIS_QUEUE)
        return QueueDepths(
            detection_queue=detection_depth or 0,
            analysis_queue=analysis_depth or 0,
        )
    except Exception as e:
        logger.warning(f"Failed to get queue depths: {e}")
        return QueueDepths(detection_queue=0, analysis_queue=0)


async def _get_workers_status(redis: RedisClient | None) -> WorkersStatus:
    """Get status of pipeline workers.

    Args:
        redis: Redis client instance or None if unavailable
    """
    # Default statuses
    file_watcher = WorkerStatus(name="file_watcher", running=False)
    detector = WorkerStatus(name="detector", running=False)
    analyzer = WorkerStatus(name="analyzer", running=False)

    if redis is None:
        return WorkersStatus(file_watcher=file_watcher, detector=detector, analyzer=analyzer)

    try:
        # Check worker heartbeats in Redis
        fw_heartbeat = await redis.get("worker:file_watcher:heartbeat")
        det_heartbeat = await redis.get("worker:detector:heartbeat")
        ana_heartbeat = await redis.get("worker:analyzer:heartbeat")

        # Get error counts
        fw_errors = await redis.get("worker:file_watcher:error_count")
        det_errors = await redis.get("worker:detector:error_count")
        ana_errors = await redis.get("worker:analyzer:error_count")

        file_watcher = WorkerStatus(
            name="file_watcher",
            running=fw_heartbeat is not None,
            last_activity=fw_heartbeat,
            error_count=int(fw_errors) if fw_errors else 0,
        )
        detector = WorkerStatus(
            name="detector",
            running=det_heartbeat is not None,
            last_activity=det_heartbeat,
            error_count=int(det_errors) if det_errors else 0,
        )
        analyzer = WorkerStatus(
            name="analyzer",
            running=ana_heartbeat is not None,
            last_activity=ana_heartbeat,
            error_count=int(ana_errors) if ana_errors else 0,
        )
    except Exception as e:
        logger.warning(f"Failed to get worker status: {e}")

    return WorkersStatus(file_watcher=file_watcher, detector=detector, analyzer=analyzer)


async def _get_recent_errors(redis: RedisClient | None, _limit: int = 10) -> list[RecentError]:
    """Get recent errors from Redis error log.

    Args:
        redis: Redis client instance or None if unavailable
        _limit: Maximum number of errors to return (unused in placeholder)

    Note: This currently returns an empty list as a placeholder.
    The full implementation would require adding lrange support to RedisClient
    or using a different data structure for error tracking.
    """
    if redis is None:
        return []

    # Placeholder: In a full implementation, we would store and retrieve
    # recent errors from Redis. For now, we return an empty list since
    # the pipeline error tracking is done via metrics/logging.
    return []


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/pipeline-state", response_model=PipelineStateResponse)
async def get_pipeline_state(
    request: Request,
    response: Response,
    redis: RedisClient | None = Depends(get_redis_optional),
) -> PipelineStateResponse:
    """Get current state of the AI processing pipeline.

    Returns queue depths, worker status, and recent errors for debugging
    pipeline issues and monitoring system health.

    NEM-1470: Debug endpoint for pipeline state inspection
    """
    # Get correlation ID from request or context
    correlation_id = request.headers.get("X-Correlation-ID") or get_request_id()

    # Echo correlation ID in response headers
    if correlation_id:
        response.headers["X-Correlation-ID"] = correlation_id

    # Gather pipeline state
    queue_depths = await _get_queue_depths(redis)
    workers = await _get_workers_status(redis)
    recent_errors = await _get_recent_errors(redis)

    return PipelineStateResponse(
        queue_depths=queue_depths,
        workers=workers,
        recent_errors=recent_errors,
        timestamp=datetime.now(UTC).isoformat(),
        correlation_id=correlation_id,
    )


@router.get("/log-level", response_model=LogLevelResponse)
async def get_log_level() -> LogLevelResponse:
    """Get current log level.

    NEM-1471: Log level inspection endpoint
    """
    root_logger = logging.getLogger()
    level_name = logging.getLevelName(root_logger.level)

    return LogLevelResponse(
        level=level_name,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.post("/log-level", response_model=LogLevelResponse)
async def set_log_level(request: LogLevelRequest) -> LogLevelResponse:
    """Set log level at runtime for debugging.

    Allows changing the log level without restarting the application.
    Useful for temporarily enabling DEBUG logging to investigate issues.

    NEM-1471: Log level runtime override

    Args:
        request: Log level request with new level

    Returns:
        Current and previous log level

    Raises:
        HTTPException: If the log level is invalid
    """
    level = request.level.upper()

    if level not in VALID_LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level: {request.level}. "
            f"Valid levels: {', '.join(sorted(VALID_LOG_LEVELS))}",
        )

    root_logger = logging.getLogger()
    previous_level = logging.getLevelName(root_logger.level)

    # Set new log level
    new_level = getattr(logging, level)
    root_logger.setLevel(new_level)

    # Also update all handlers
    for handler in root_logger.handlers:
        handler.setLevel(new_level)

    logger.info(
        f"Log level changed: {previous_level} -> {level}",
        extra={"previous_level": previous_level, "new_level": level},
    )

    return LogLevelResponse(
        level=level,
        previous_level=previous_level,
        timestamp=datetime.now(UTC).isoformat(),
    )
