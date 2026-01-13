"""Unit tests for EventBroadcaster worker status broadcasting (NEM-2461).

Tests the broadcast_worker_status method and related worker event functionality.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from backend.services.event_broadcaster import (
    EventBroadcaster,
    reset_broadcaster_state,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture(autouse=True)
def _enable_log_capture(caplog: pytest.LogCaptureFixture) -> None:
    """Automatically enable INFO-level log capture for all tests."""
    caplog.set_level(logging.INFO)


@pytest.fixture(autouse=True)
def _reset_broadcaster_state() -> None:
    """Reset global broadcaster state before each test for isolation."""
    reset_broadcaster_state()


class _FakePubSub:
    """Fake PubSub for testing."""

    pass


class _FakeRedis:
    """Fake Redis client for testing."""

    def __init__(self) -> None:
        self.subscribe = AsyncMock(return_value=_FakePubSub())
        self.unsubscribe = AsyncMock(return_value=None)
        self.publish = AsyncMock(return_value=1)

    async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        """Default: no messages - empty async generator pattern."""
        for _ in []:
            yield {}


# ==============================================================================
# Worker Status Broadcast Tests (NEM-2461)
# ==============================================================================


def _create_valid_worker_status_data(
    event_type: str = "worker.started",
    worker_name: str = "detection_worker",
    worker_type: str = "detection",
    timestamp: str = "2026-01-13T10:30:00Z",
    error: str | None = None,
    error_type: str | None = None,
    failure_count: int | None = None,
    items_processed: int | None = None,
    reason: str | None = None,
    previous_state: str | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """Create valid worker status data for testing."""
    data: dict[str, Any] = {
        "event_type": event_type,
        "worker_name": worker_name,
        "worker_type": worker_type,
        "timestamp": timestamp,
    }
    # Only include optional fields if they have values
    if error is not None:
        data["error"] = error
    if error_type is not None:
        data["error_type"] = error_type
    if failure_count is not None:
        data["failure_count"] = failure_count
    if items_processed is not None:
        data["items_processed"] = items_processed
    if reason is not None:
        data["reason"] = reason
    if previous_state is not None:
        data["previous_state"] = previous_state
    if attempt is not None:
        data["attempt"] = attempt
    if max_attempts is not None:
        data["max_attempts"] = max_attempts
    return data


@pytest.mark.asyncio
async def test_broadcast_worker_status_wraps_missing_type() -> None:
    """Test that broadcast_worker_status wraps payload missing 'type' key."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Use valid worker status data - will be wrapped with {"type": "worker_status", "data": ...}
    payload = _create_valid_worker_status_data()
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    channel, published = redis.publish.await_args.args
    assert channel == broadcaster.CHANNEL_NAME
    assert published["type"] == "worker_status"
    # Data should be validated and serialized
    assert published["data"]["worker_name"] == "detection_worker"
    assert published["data"]["worker_type"] == "detection"
    assert published["data"]["event_type"] == "worker.started"


@pytest.mark.asyncio
async def test_broadcast_worker_status_with_valid_envelope() -> None:
    """Test that broadcast_worker_status validates and preserves valid envelope."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(),
        "timestamp": "2026-01-13T10:30:00Z",
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    channel, published = redis.publish.await_args.args
    assert channel == broadcaster.CHANNEL_NAME
    assert published["type"] == "worker_status"
    assert published["data"]["worker_name"] == "detection_worker"


@pytest.mark.asyncio
async def test_broadcast_worker_started_event() -> None:
    """Test broadcasting a worker started event."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(
            event_type="worker.started",
            worker_name="analysis_worker",
            worker_type="analysis",
        ),
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["event_type"] == "worker.started"
    assert published["data"]["worker_name"] == "analysis_worker"
    assert published["data"]["worker_type"] == "analysis"


@pytest.mark.asyncio
async def test_broadcast_worker_stopped_event() -> None:
    """Test broadcasting a worker stopped event."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(
            event_type="worker.stopped",
            worker_name="timeout_worker",
            worker_type="timeout",
            reason="graceful_shutdown",
            items_processed=100,
        ),
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["event_type"] == "worker.stopped"
    assert published["data"]["reason"] == "graceful_shutdown"
    assert published["data"]["items_processed"] == 100


@pytest.mark.asyncio
async def test_broadcast_worker_error_event() -> None:
    """Test broadcasting a worker error event."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(
            event_type="worker.error",
            worker_name="detection_worker",
            worker_type="detection",
            error="Connection timeout to detector service",
            error_type="connection_error",
        ),
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["event_type"] == "worker.error"
    assert published["data"]["error"] == "Connection timeout to detector service"
    assert published["data"]["error_type"] == "connection_error"


@pytest.mark.asyncio
async def test_broadcast_worker_health_check_failed_event() -> None:
    """Test broadcasting a worker health check failed event."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(
            event_type="worker.health_check_failed",
            worker_name="analysis_worker",
            worker_type="analysis",
            error="Health check timeout",
            failure_count=3,
        ),
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["event_type"] == "worker.health_check_failed"
    assert published["data"]["failure_count"] == 3


@pytest.mark.asyncio
async def test_broadcast_worker_restarting_event() -> None:
    """Test broadcasting a worker restarting event."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(
            event_type="worker.restarting",
            worker_name="detection_worker",
            worker_type="detection",
            attempt=2,
            max_attempts=5,
            reason="previous_error",
        ),
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["event_type"] == "worker.restarting"
    assert published["data"]["attempt"] == 2
    assert published["data"]["max_attempts"] == 5


@pytest.mark.asyncio
async def test_broadcast_worker_recovered_event() -> None:
    """Test broadcasting a worker recovered event."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(
            event_type="worker.recovered",
            worker_name="timeout_worker",
            worker_type="timeout",
            previous_state="error",
        ),
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["event_type"] == "worker.recovered"
    assert published["data"]["previous_state"] == "error"


@pytest.mark.asyncio
async def test_broadcast_worker_status_invalid_worker_type_raises() -> None:
    """Test that broadcast_worker_status raises ValueError for invalid worker_type."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {
        "type": "worker_status",
        "data": {
            "event_type": "worker.started",
            "worker_name": "unknown_worker",
            "worker_type": "invalid_type",  # Invalid worker type
            "timestamp": "2026-01-13T10:30:00Z",
        },
    }

    with pytest.raises(ValueError) as exc_info:
        await broadcaster.broadcast_worker_status(payload)

    assert "Invalid worker status message format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_broadcast_worker_status_missing_required_field_raises() -> None:
    """Test that broadcast_worker_status raises ValueError for missing required fields."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Missing worker_name
    payload = {
        "type": "worker_status",
        "data": {
            "event_type": "worker.started",
            "worker_type": "detection",
            "timestamp": "2026-01-13T10:30:00Z",
        },
    }

    with pytest.raises(ValueError) as exc_info:
        await broadcaster.broadcast_worker_status(payload)

    assert "Invalid worker status message format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_broadcast_worker_status_all_worker_types() -> None:
    """Test broadcasting worker status for all valid worker types."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    worker_types = ["detection", "analysis", "timeout", "metrics"]

    for worker_type in worker_types:
        redis.publish.reset_mock()
        payload = {
            "type": "worker_status",
            "data": _create_valid_worker_status_data(
                worker_name=f"{worker_type}_worker",
                worker_type=worker_type,
            ),
        }
        count = await broadcaster.broadcast_worker_status(payload)
        assert count == 1
        _, published = redis.publish.await_args.args
        assert published["data"]["worker_type"] == worker_type


@pytest.mark.asyncio
async def test_broadcast_worker_status_preserves_timestamp() -> None:
    """Test that broadcast_worker_status preserves the timestamp field."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    timestamp = "2026-01-13T15:45:30.123Z"
    payload = {
        "type": "worker_status",
        "data": _create_valid_worker_status_data(timestamp=timestamp),
        "timestamp": timestamp,
    }
    count = await broadcaster.broadcast_worker_status(payload)

    assert count == 1
    _, published = redis.publish.await_args.args
    assert published["data"]["timestamp"] == timestamp
    assert published["timestamp"] == timestamp
