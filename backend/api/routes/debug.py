"""Debug API endpoints for pipeline inspection and runtime debugging.

This module provides debug endpoints for:
- Configuration inspection with sensitive value redaction
- Redis connection stats and pub/sub channels
- WebSocket connection states
- Circuit breaker states
- Pipeline state inspection (queue depths, worker status, recent errors)
- Log level runtime override
- Correlation ID propagation testing

SECURITY: All endpoints are gated by settings.debug == True.
When debug=False, endpoints return 404 Not Found to avoid revealing
the existence of debug functionality.

NEM-1470: Pipeline state inspection
NEM-1471: Log level runtime override
NEM-1642: Debug endpoints for runtime diagnostics
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.api.schemas.system import QueueDepths
from backend.core.config import get_settings
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.logging import get_logger, get_request_id, redact_sensitive_value
from backend.core.redis import RedisClient, get_redis_optional

logger = get_logger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])

# Valid log levels
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# =============================================================================
# Security: Debug Mode Gating
# =============================================================================


def require_debug_mode() -> None:
    """Verify debug mode is enabled, raise 404 if not.

    This function is used as a dependency for all debug endpoints to ensure
    they are only accessible when debug=True in settings.

    Returns 404 instead of 403 to avoid revealing the existence of debug
    endpoints to potential attackers scanning for vulnerabilities.

    Raises:
        HTTPException: 404 if debug mode is not enabled
    """
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(
            status_code=404,
            detail="Not Found",
        )


# =============================================================================
# Pydantic Models
# =============================================================================


class PipelineWorkerStatus(BaseModel):
    """Status of a pipeline worker."""

    name: str = Field(description="Worker name")
    running: bool = Field(description="Whether worker is currently running")
    last_activity: str | None = Field(default=None, description="ISO timestamp of last activity")
    error_count: int = Field(default=0, description="Number of recent errors")


class PipelineWorkersStatus(BaseModel):
    """Status of all pipeline workers."""

    file_watcher: PipelineWorkerStatus = Field(description="File watcher status")
    detector: PipelineWorkerStatus = Field(description="Detector worker status")
    analyzer: PipelineWorkerStatus = Field(description="Analyzer worker status")


class RecentError(BaseModel):
    """Recent error information."""

    timestamp: str = Field(description="ISO timestamp of error")
    error_type: str = Field(description="Type of error")
    component: str = Field(description="Component that generated error")
    message: str | None = Field(default=None, description="Error message")


class PipelineStateResponse(BaseModel):
    """Response for pipeline state inspection."""

    queue_depths: QueueDepths = Field(description="Current queue depths")
    workers: PipelineWorkersStatus = Field(description="Worker status")
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


class DebugConfigResponse(BaseModel):
    """Response for configuration inspection."""

    config: dict[str, Any] = Field(
        description="Current configuration with sensitive values redacted"
    )
    timestamp: str = Field(description="ISO timestamp of response")


class RedisInfoResponse(BaseModel):
    """Response for Redis connection stats."""

    status: str = Field(description="Redis connection status (connected, unavailable)")
    info: dict[str, Any] | None = Field(default=None, description="Redis INFO command output")
    pubsub: dict[str, Any] | None = Field(default=None, description="Pub/sub channel information")
    timestamp: str = Field(description="ISO timestamp of response")


class DebugWebSocketBroadcasterStatus(BaseModel):
    """Status of a WebSocket broadcaster."""

    connection_count: int = Field(description="Number of active connections")
    is_listening: bool = Field(description="Whether the broadcaster is listening for events")
    is_degraded: bool = Field(description="Whether the broadcaster is in degraded mode")
    circuit_state: str = Field(description="Circuit breaker state (CLOSED, OPEN, HALF_OPEN)")
    channel_name: str | None = Field(default=None, description="Redis channel being listened to")


class WebSocketConnectionsResponse(BaseModel):
    """Response for WebSocket connection states."""

    event_broadcaster: DebugWebSocketBroadcasterStatus = Field(
        description="Event broadcaster status"
    )
    system_broadcaster: DebugWebSocketBroadcasterStatus = Field(
        description="System broadcaster status"
    )
    timestamp: str = Field(description="ISO timestamp of response")


class DebugCircuitBreakersResponse(BaseModel):
    """Response for circuit breaker states."""

    circuit_breakers: dict[str, dict[str, Any]] = Field(
        description="All circuit breaker states keyed by name"
    )
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


async def _get_workers_status(redis: RedisClient | None) -> PipelineWorkersStatus:
    """Get status of pipeline workers.

    Args:
        redis: Redis client instance or None if unavailable
    """
    # Default statuses
    file_watcher = PipelineWorkerStatus(name="file_watcher", running=False)
    detector = PipelineWorkerStatus(name="detector", running=False)
    analyzer = PipelineWorkerStatus(name="analyzer", running=False)

    if redis is None:
        return PipelineWorkersStatus(
            file_watcher=file_watcher, detector=detector, analyzer=analyzer
        )

    try:
        # Check worker heartbeats in Redis
        fw_heartbeat = await redis.get("worker:file_watcher:heartbeat")
        det_heartbeat = await redis.get("worker:detector:heartbeat")
        ana_heartbeat = await redis.get("worker:analyzer:heartbeat")

        # Get error counts
        fw_errors = await redis.get("worker:file_watcher:error_count")
        det_errors = await redis.get("worker:detector:error_count")
        ana_errors = await redis.get("worker:analyzer:error_count")

        file_watcher = PipelineWorkerStatus(
            name="file_watcher",
            running=fw_heartbeat is not None,
            last_activity=fw_heartbeat,
            error_count=int(fw_errors) if fw_errors else 0,
        )
        detector = PipelineWorkerStatus(
            name="detector",
            running=det_heartbeat is not None,
            last_activity=det_heartbeat,
            error_count=int(det_errors) if det_errors else 0,
        )
        analyzer = PipelineWorkerStatus(
            name="analyzer",
            running=ana_heartbeat is not None,
            last_activity=ana_heartbeat,
            error_count=int(ana_errors) if ana_errors else 0,
        )
    except Exception as e:
        logger.warning(f"Failed to get worker status: {e}")

    return PipelineWorkersStatus(file_watcher=file_watcher, detector=detector, analyzer=analyzer)


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


def _get_redacted_config() -> dict[str, Any]:
    """Get current configuration with sensitive values redacted.

    Uses the redact_sensitive_value function from backend.core.logging
    to ensure consistent redaction patterns.

    Returns:
        Dictionary of configuration values with sensitive data redacted.
    """
    settings = get_settings()

    # Get all settings as a dict
    config_dict: dict[str, Any] = {}

    # Iterate over model fields and redact sensitive values
    # Access model_fields from the class, not the instance
    for field_name in type(settings).model_fields:
        value = getattr(settings, field_name, None)

        # Handle nested settings (like orchestrator)
        # Check if value has a __class__ with model_fields (Pydantic model)
        if value is not None and hasattr(type(value), "model_fields"):
            nested_dict = {}
            for nested_field in type(value).model_fields:
                nested_value = getattr(value, nested_field, None)
                nested_dict[nested_field] = redact_sensitive_value(nested_field, nested_value)
            config_dict[field_name] = nested_dict
        else:
            config_dict[field_name] = redact_sensitive_value(field_name, value)

    return config_dict


async def _get_redis_info(
    redis: RedisClient | None,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Get Redis connection info and pub/sub stats.

    Args:
        redis: Redis client instance or None if unavailable

    Returns:
        Tuple of (status, info_dict, pubsub_dict)
    """
    if redis is None:
        return "unavailable", None, None

    try:
        # Get Redis INFO
        info = await redis.info()

        # Extract relevant info
        info_dict = {
            "redis_version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
            "total_connections_received": info.get("total_connections_received", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
        }

        # Get pub/sub info
        try:
            channels = await redis.pubsub_channels()
            channel_names = [c.decode() if isinstance(c, bytes) else c for c in channels]

            # Get subscriber counts for each channel
            if channel_names:
                numsub = await redis.pubsub_numsub(*channel_names)
                channel_counts = {(k.decode() if isinstance(k, bytes) else k): v for k, v in numsub}
            else:
                channel_counts = {}

            pubsub_dict = {
                "channels": channel_names,
                "subscriber_counts": channel_counts,
            }
        except Exception as e:
            logger.warning(f"Failed to get pub/sub info: {e}")
            pubsub_dict = {"channels": [], "subscriber_counts": {}}

        return "connected", info_dict, pubsub_dict

    except Exception as e:
        logger.warning(f"Failed to get Redis info: {e}")
        return "error", {"error": str(e)}, None


def _get_websocket_broadcaster_status() -> tuple[
    DebugWebSocketBroadcasterStatus, DebugWebSocketBroadcasterStatus
]:
    """Get status of WebSocket broadcasters.

    Returns:
        Tuple of (event_broadcaster_status, system_broadcaster_status)
    """
    from backend.services.event_broadcaster import _broadcaster as event_broadcaster
    from backend.services.system_broadcaster import _system_broadcaster as system_broadcaster

    # Event broadcaster status
    if event_broadcaster is not None:
        event_status = DebugWebSocketBroadcasterStatus(
            connection_count=len(event_broadcaster._connections),
            is_listening=event_broadcaster._is_listening,
            is_degraded=event_broadcaster.is_degraded(),
            circuit_state=event_broadcaster.get_circuit_state().value,
            channel_name=event_broadcaster.channel_name,
        )
    else:
        event_status = DebugWebSocketBroadcasterStatus(
            connection_count=0,
            is_listening=False,
            is_degraded=False,
            circuit_state="UNKNOWN",
            channel_name=None,
        )

    # System broadcaster status
    if system_broadcaster is not None:
        system_status = DebugWebSocketBroadcasterStatus(
            connection_count=len(system_broadcaster.connections),
            is_listening=system_broadcaster._running,
            is_degraded=system_broadcaster._is_degraded,
            circuit_state=system_broadcaster._circuit_breaker.get_state().value,
            channel_name=None,  # System broadcaster uses multiple channels
        )
    else:
        system_status = DebugWebSocketBroadcasterStatus(
            connection_count=0,
            is_listening=False,
            is_degraded=False,
            circuit_state="UNKNOWN",
            channel_name=None,
        )

    return event_status, system_status


def _get_all_circuit_breakers() -> dict[str, dict[str, Any]]:
    """Get status of all registered circuit breakers.

    Returns:
        Dictionary mapping circuit breaker names to their status dictionaries.
    """
    from backend.services.circuit_breaker import _get_registry

    registry = _get_registry()
    return registry.get_all_status()


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/config",
    response_model=DebugConfigResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_config(
    _debug: None = Depends(require_debug_mode),
) -> DebugConfigResponse:
    """Get current configuration with sensitive values redacted.

    Returns all configuration settings with passwords, API keys, and other
    sensitive values replaced with [REDACTED]. URLs containing passwords
    will have only the password portion redacted, preserving the structure.

    NEM-1642: Debug endpoint for configuration inspection
    """
    config = _get_redacted_config()

    return DebugConfigResponse(
        config=config,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/redis/info",
    response_model=RedisInfoResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_redis_info(
    redis: RedisClient | None = Depends(get_redis_optional),
    _debug: None = Depends(require_debug_mode),
) -> RedisInfoResponse:
    """Get Redis connection stats and pub/sub channel information.

    Returns Redis server info, memory usage, connection stats, and
    active pub/sub channels with their subscriber counts.

    NEM-1642: Debug endpoint for Redis diagnostics
    """
    status, info, pubsub = await _get_redis_info(redis)

    return RedisInfoResponse(
        status=status,
        info=info,
        pubsub=pubsub,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/websocket/connections",
    response_model=WebSocketConnectionsResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_websocket_connections(
    _debug: None = Depends(require_debug_mode),
) -> WebSocketConnectionsResponse:
    """Get active WebSocket connection states.

    Returns connection counts and health status for both the event broadcaster
    (security event stream) and system broadcaster (system status stream).

    NEM-1642: Debug endpoint for WebSocket diagnostics
    """
    event_status, system_status = _get_websocket_broadcaster_status()

    return WebSocketConnectionsResponse(
        event_broadcaster=event_status,
        system_broadcaster=system_status,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/circuit-breakers",
    response_model=DebugCircuitBreakersResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_circuit_breakers(
    _debug: None = Depends(require_debug_mode),
) -> DebugCircuitBreakersResponse:
    """Get all circuit breaker states.

    Returns the current state and metrics for all registered circuit breakers,
    including failure counts, success counts, and configuration.

    NEM-1642: Debug endpoint for circuit breaker diagnostics
    """
    breakers = _get_all_circuit_breakers()

    return DebugCircuitBreakersResponse(
        circuit_breakers=breakers,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/pipeline-state",
    response_model=PipelineStateResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_pipeline_state(
    request: Request,
    response: Response,
    redis: RedisClient | None = Depends(get_redis_optional),
    _debug: None = Depends(require_debug_mode),
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


@router.get(
    "/log-level",
    response_model=LogLevelResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_log_level(
    _debug: None = Depends(require_debug_mode),
) -> LogLevelResponse:
    """Get current log level.

    NEM-1471: Log level inspection endpoint
    """
    root_logger = logging.getLogger()
    level_name = logging.getLevelName(root_logger.level)

    return LogLevelResponse(
        level=level_name,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.post(
    "/log-level",
    response_model=LogLevelResponse,
    responses={
        400: {"description": "Bad request - Invalid log level"},
        404: {"description": "Not found - Debug mode disabled"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def set_log_level(
    request: LogLevelRequest,
    _debug: None = Depends(require_debug_mode),
) -> LogLevelResponse:
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


# =============================================================================
# Profiling Endpoints (NEM-1644)
# =============================================================================


class ProfileStartResponse(BaseModel):
    """Response for starting profiling."""

    status: str = Field(description="Profiling status ('started' or 'already_running')")
    started_at: str = Field(description="ISO timestamp when profiling started")
    message: str = Field(description="Human-readable status message")


class ProfileStopResponse(BaseModel):
    """Response for stopping profiling."""

    status: str = Field(description="Profiling status ('stopped' or 'not_running')")
    profile_path: str | None = Field(default=None, description="Path to saved profile file")
    stopped_at: str = Field(description="ISO timestamp when profiling stopped")
    message: str = Field(description="Human-readable status message")


class ProfileStatsResponse(BaseModel):
    """Response for profiling statistics."""

    is_profiling: bool = Field(description="Whether profiling is currently active")
    stats_text: str | None = Field(default=None, description="Human-readable profiling statistics")
    last_profile_path: str | None = Field(default=None, description="Path to last saved profile")
    timestamp: str = Field(description="ISO timestamp of response")


@router.post(
    "/profile/start",
    response_model=ProfileStartResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def start_profiling(
    _debug: None = Depends(require_debug_mode),
) -> ProfileStartResponse:
    """Start performance profiling.

    Begins collecting profiling data for performance analysis.
    Profile data is saved to disk when stop is called.

    NEM-1644: Debug endpoint for performance profiling

    Returns:
        Profiling start status
    """
    from backend.core.profiling import get_profiling_manager

    manager = get_profiling_manager()

    if manager.is_profiling:
        started_at = manager.get_started_at()
        return ProfileStartResponse(
            status="already_running",
            started_at=started_at.isoformat() if started_at else "",
            message="Profiling is already running",
        )

    manager.start()

    return ProfileStartResponse(
        status="started",
        started_at=datetime.now(UTC).isoformat(),
        message="Profiling started successfully",
    )


@router.post(
    "/profile/stop",
    response_model=ProfileStopResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def stop_profiling(
    _debug: None = Depends(require_debug_mode),
) -> ProfileStopResponse:
    """Stop performance profiling and save results.

    Stops the profiler and saves the profile data to a .prof file.
    The file can be analyzed with snakeviz or py-spy.

    NEM-1644: Debug endpoint for performance profiling

    Returns:
        Profiling stop status with path to saved profile
    """
    from backend.core.profiling import get_profiling_manager

    manager = get_profiling_manager()

    if not manager.is_profiling:
        return ProfileStopResponse(
            status="not_running",
            profile_path=manager.last_profile_path,
            stopped_at=datetime.now(UTC).isoformat(),
            message="Profiling was not running",
        )

    manager.stop()

    return ProfileStopResponse(
        status="stopped",
        profile_path=manager.last_profile_path,
        stopped_at=datetime.now(UTC).isoformat(),
        message=f"Profiling stopped. Profile saved to: {manager.last_profile_path}",
    )


@router.get(
    "/profile/stats",
    response_model=ProfileStatsResponse,
    responses={
        404: {"description": "Not found - Debug mode disabled"},
        500: {"description": "Internal server error"},
    },
)
async def get_profile_stats(
    _debug: None = Depends(require_debug_mode),
) -> ProfileStatsResponse:
    """Get current profiling statistics.

    Returns the current profiling state and statistics from the last
    completed profiling session.

    NEM-1644: Debug endpoint for performance profiling

    Returns:
        Profiling status and statistics
    """
    from backend.core.profiling import get_profiling_manager

    manager = get_profiling_manager()

    return ProfileStatsResponse(
        is_profiling=manager.is_profiling,
        stats_text=manager.get_stats_text() if not manager.is_profiling else None,
        last_profile_path=manager.last_profile_path,
        timestamp=datetime.now(UTC).isoformat(),
    )
