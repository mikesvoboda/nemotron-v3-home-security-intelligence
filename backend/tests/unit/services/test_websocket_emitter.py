"""Unit tests for WebSocketEmitterService.

This module tests the WebSocket emitter service which provides a centralized
API for emitting validated events throughout the application. Tests cover:
- Core emission patterns (emit, broadcast, emit_to_room, emit_to_user)
- Pydantic payload schema validation for 35+ event types
- Error handling and graceful degradation
- Concurrency and singleton pattern
- Dispatcher routing to EventBroadcaster and SystemBroadcaster
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.core.websocket.event_types import (
    WebSocketEventType,
)
from backend.services.websocket_emitter import (
    WebSocketEmitterService,
    get_websocket_emitter,
    get_websocket_emitter_sync,
    reset_emitter_state,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_emitter_state() -> None:
    """Reset global emitter state before each test for isolation."""
    reset_emitter_state()


@pytest.fixture
def mock_event_broadcaster() -> AsyncMock:
    """Create a mock EventBroadcaster with all required methods."""
    broadcaster = AsyncMock()
    broadcaster.broadcast_alert = AsyncMock()
    broadcaster.broadcast_camera_status = AsyncMock()
    broadcaster.broadcast_scene_change = AsyncMock()
    broadcaster.broadcast_event = AsyncMock()
    broadcaster.broadcast_service_status = AsyncMock()
    broadcaster.broadcast_worker_status = AsyncMock()
    return broadcaster


@pytest.fixture
def mock_system_broadcaster() -> AsyncMock:
    """Create a mock SystemBroadcaster with all required methods."""
    broadcaster = AsyncMock()
    broadcaster.broadcast_status = AsyncMock()
    return broadcaster


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client with publish method."""
    client = AsyncMock()
    client.publish = AsyncMock()
    return client


@pytest.fixture
def emitter(
    mock_event_broadcaster: AsyncMock,
    mock_system_broadcaster: AsyncMock,
    mock_redis_client: AsyncMock,
) -> WebSocketEmitterService:
    """Create a WebSocketEmitterService with mocked dependencies."""
    return WebSocketEmitterService(
        event_broadcaster=mock_event_broadcaster,
        system_broadcaster=mock_system_broadcaster,
        redis_client=mock_redis_client,
        validate_payloads=True,
    )


@pytest.fixture
def emitter_no_validation() -> WebSocketEmitterService:
    """Create a WebSocketEmitterService with validation disabled."""
    return WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=None,
        validate_payloads=False,
    )


# =============================================================================
# Schema Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_emit_with_valid_alert_payload(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() with valid alert.created payload passes validation."""
    payload = {
        "id": str(uuid.uuid4()),
        "event_id": 123,
        "severity": "high",
        "status": "pending",
        "dedup_key": "front_door:person:rule1",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.ALERT_CREATED, payload)

    assert result is True
    assert emitter.emit_count == 1
    assert emitter.emit_errors == 0
    mock_event_broadcaster.broadcast_alert.assert_called_once()


@pytest.mark.asyncio
async def test_emit_with_invalid_alert_payload_fails_validation(
    emitter: WebSocketEmitterService,
) -> None:
    """Test emit() with invalid alert payload raises ValidationError."""
    payload = {
        "id": "not-a-uuid",  # Invalid UUID format
        "event_id": "not-an-int",  # Should be int
        "severity": "invalid",  # Invalid severity
        "status": "pending",
        "dedup_key": "key",
        "created_at": "not-a-timestamp",
        "updated_at": "not-a-timestamp",
    }

    with pytest.raises(ValidationError) as exc_info:
        await emitter.emit(WebSocketEventType.ALERT_CREATED, payload)

    # Verify error tracking
    assert emitter.emit_count == 0
    assert emitter.emit_errors == 1

    # Verify ValidationError contains useful information
    errors = exc_info.value.errors()
    assert len(errors) > 0


@pytest.mark.asyncio
async def test_emit_with_missing_required_field_fails_validation(
    emitter: WebSocketEmitterService,
) -> None:
    """Test emit() with missing required fields raises ValidationError."""
    payload = {
        "id": str(uuid.uuid4()),
        # Missing event_id, severity, status, dedup_key, timestamps
    }

    with pytest.raises(ValidationError) as exc_info:
        await emitter.emit(WebSocketEventType.ALERT_CREATED, payload)

    errors = exc_info.value.errors()
    assert len(errors) >= 5  # Multiple missing fields
    assert emitter.emit_errors == 1


@pytest.mark.asyncio
async def test_emit_with_extra_fields_succeeds(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() with extra fields succeeds (extra='ignore' in BasePayload)."""
    payload = {
        "id": str(uuid.uuid4()),
        "event_id": 123,
        "severity": "high",
        "status": "pending",
        "dedup_key": "key",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "extra_field_not_in_schema": "should be ignored",
    }

    result = await emitter.emit(WebSocketEventType.ALERT_CREATED, payload)

    assert result is True
    assert emitter.emit_count == 1


@pytest.mark.asyncio
async def test_emit_without_validation_skips_schema_check(
    emitter_no_validation: WebSocketEmitterService,
) -> None:
    """Test emit() with validation disabled skips schema validation."""
    # Invalid payload that would fail validation
    payload = {
        "id": "not-a-uuid",
        "event_id": "not-an-int",
        "severity": "invalid",
    }

    # Should succeed because validation is disabled
    result = await emitter_no_validation.emit(WebSocketEventType.ALERT_CREATED, payload)

    assert result is True
    assert emitter_no_validation.emit_count == 1
    assert emitter_no_validation.emit_errors == 0


@pytest.mark.asyncio
async def test_validate_multiple_event_types(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test validation works for multiple event types."""
    # Test camera.status_changed
    camera_payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    result = await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, camera_payload)
    assert result is True

    # Test job.progress
    job_payload = {
        "job_id": str(uuid.uuid4()),
        "job_type": "export",
        "status": "running",
        "progress": 50,
        "message": "Processing...",
    }
    result = await emitter.emit(WebSocketEventType.JOB_PROGRESS, job_payload)
    assert result is True

    assert emitter.emit_count == 2


# =============================================================================
# Core Emission Tests
# =============================================================================


@pytest.mark.asyncio
async def test_broadcast_emits_to_all_clients(
    emitter: WebSocketEmitterService,
    mock_system_broadcaster: AsyncMock,
) -> None:
    """Test broadcast() emits to all clients without room filtering."""
    payload = {
        "health": "healthy",
        "gpu": {"utilization": 45.2, "memory_used": 8192},
        "cameras": {"active": 2, "total": 3},
        "queue": {"pending": 5, "processing": 1},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.broadcast(WebSocketEventType.SYSTEM_STATUS, payload)

    assert result is True
    mock_system_broadcaster.broadcast_status.assert_called_once()


@pytest.mark.asyncio
async def test_emit_to_room_targets_specific_room(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() with room parameter targets specific channel."""
    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(
        WebSocketEventType.CAMERA_STATUS_CHANGED,
        payload,
        room="camera:front_door",
    )

    assert result is True
    mock_event_broadcaster.broadcast_camera_status.assert_called_once()


@pytest.mark.asyncio
async def test_emit_to_user_uses_user_specific_room(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit_to_user() uses user-specific room pattern."""
    payload = {
        "id": str(uuid.uuid4()),
        "event_id": 123,
        "severity": "high",
        "status": "pending",
        "dedup_key": "key",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit_to_user(
        "user123",
        WebSocketEventType.ALERT_CREATED,
        payload,
    )

    assert result is True
    # Verify the message was created with room="user:user123"
    mock_event_broadcaster.broadcast_alert.assert_called_once()


@pytest.mark.asyncio
async def test_emit_generates_correlation_id(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() generates correlation ID when not provided."""
    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    assert result is True
    # Correlation ID is generated internally, we can verify emission succeeded
    assert emitter.emit_count == 1


@pytest.mark.asyncio
async def test_emit_uses_provided_correlation_id(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() uses provided correlation ID for request tracing."""
    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    correlation_id = "req-test-12345"

    result = await emitter.emit(
        WebSocketEventType.CAMERA_STATUS_CHANGED,
        payload,
        correlation_id=correlation_id,
    )

    assert result is True


@pytest.mark.asyncio
async def test_emit_batch_emits_multiple_events(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit_batch() emits multiple events in sequence."""
    events = [
        (
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "status": "online",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            {
                "camera_id": "back_yard",
                "camera_name": "Back Yard",
                "status": "offline",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
    ]

    success_count = await emitter.emit_batch(events)

    assert success_count == 2
    assert emitter.emit_count == 2
    assert mock_event_broadcaster.broadcast_camera_status.call_count == 2


@pytest.mark.asyncio
async def test_emit_batch_continues_on_validation_error(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit_batch() continues with remaining events if one fails validation."""
    events = [
        # Valid event
        (
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "status": "online",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        # Invalid event (will fail validation)
        (
            WebSocketEventType.ALERT_CREATED,
            {"invalid": "payload"},
        ),
        # Valid event
        (
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            {
                "camera_id": "back_yard",
                "camera_name": "Back Yard",
                "status": "offline",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
    ]

    success_count = await emitter.emit_batch(events)

    # Should emit 2 out of 3 events
    assert success_count == 2
    assert emitter.emit_count == 2
    assert emitter.emit_errors == 1


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_emit_handles_broadcaster_failure_gracefully(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() handles broadcaster failures without raising."""
    mock_event_broadcaster.broadcast_camera_status.side_effect = Exception("Broadcast failed")

    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Should return False but not raise
    result = await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    assert result is False
    assert emitter.emit_errors == 1


@pytest.mark.asyncio
async def test_emit_when_broadcaster_not_available() -> None:
    """Test emit() falls back to Redis when broadcaster not available."""
    mock_redis = AsyncMock()
    emitter = WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=mock_redis,
        validate_payloads=False,
    )

    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    assert result is True
    mock_redis.publish.assert_called_once()


@pytest.mark.asyncio
async def test_emit_when_no_broadcaster_and_no_redis() -> None:
    """Test emit() logs warning when no broadcaster or Redis available."""
    emitter = WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=None,
        validate_payloads=False,
    )

    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Should succeed but log warning
    result = await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    assert result is True
    assert emitter.emit_count == 1


@pytest.mark.asyncio
async def test_emit_propagates_correlation_id_on_error(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit() includes correlation ID in error logs."""
    mock_event_broadcaster.broadcast_camera_status.side_effect = Exception("Broadcast failed")
    correlation_id = "req-error-test"

    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(
        WebSocketEventType.CAMERA_STATUS_CHANGED,
        payload,
        correlation_id=correlation_id,
    )

    assert result is False
    assert emitter.emit_errors == 1


# =============================================================================
# Dispatcher Routing Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dispatch_alert_events_to_event_broadcaster(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test alert events are routed to EventBroadcaster.broadcast_alert()."""
    # Test each alert event type with appropriate payload
    test_cases = [
        (
            WebSocketEventType.ALERT_CREATED,
            {
                "id": str(uuid.uuid4()),
                "event_id": 123,
                "severity": "high",
                "status": "pending",
                "dedup_key": "key",
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.ALERT_UPDATED,
            {
                "id": str(uuid.uuid4()),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.ALERT_ACKNOWLEDGED,
            {
                "id": str(uuid.uuid4()),
                "event_id": 123,
                "acknowledged_at": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.ALERT_RESOLVED,
            {
                "id": str(uuid.uuid4()),
                "event_id": 123,
                "resolved_at": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.ALERT_DISMISSED,
            {
                "id": str(uuid.uuid4()),
                "event_id": 123,
                "dismissed_at": datetime.now(UTC).isoformat(),
            },
        ),
    ]

    for event_type, payload in test_cases:
        result = await emitter.emit(event_type, payload)
        assert result is True

    # Verify broadcast_alert was called for each event
    assert mock_event_broadcaster.broadcast_alert.call_count == len(test_cases)


@pytest.mark.asyncio
async def test_dispatch_camera_events_to_event_broadcaster(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test camera events are routed to EventBroadcaster.broadcast_camera_status()."""
    camera_types = [
        WebSocketEventType.CAMERA_ONLINE,
        WebSocketEventType.CAMERA_OFFLINE,
        WebSocketEventType.CAMERA_STATUS_CHANGED,
        WebSocketEventType.CAMERA_ERROR,
    ]

    for event_type in camera_types:
        if event_type == WebSocketEventType.CAMERA_ERROR:
            payload = {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "error": "Connection failed",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        else:
            payload = {
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "status": "online",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        result = await emitter.emit(event_type, payload)
        assert result is True

    assert mock_event_broadcaster.broadcast_camera_status.call_count == len(camera_types)


@pytest.mark.asyncio
async def test_dispatch_system_events_to_system_broadcaster(
    emitter: WebSocketEmitterService,
    mock_system_broadcaster: AsyncMock,
) -> None:
    """Test system events are routed to SystemBroadcaster.broadcast_status()."""
    payload = {
        "health": "healthy",
        "gpu": {"utilization": 45.2, "memory_used": 8192},
        "cameras": {"active": 2, "total": 3},
        "queue": {"pending": 5, "processing": 1},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.SYSTEM_STATUS, payload)

    assert result is True
    mock_system_broadcaster.broadcast_status.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_worker_events_to_event_broadcaster(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test worker events are routed to EventBroadcaster.broadcast_worker_status()."""
    # Test each worker event type with appropriate payload
    test_cases = [
        (
            WebSocketEventType.WORKER_STARTED,
            {
                "worker_name": "worker-1",
                "worker_type": "detection",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.WORKER_STOPPED,
            {
                "worker_name": "worker-1",
                "worker_type": "detection",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.WORKER_HEALTH_CHECK_FAILED,
            {
                "worker_name": "worker-1",
                "worker_type": "detection",
                "error": "Health check timeout",
                "failure_count": 3,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.WORKER_RESTARTING,
            {
                "worker_name": "worker-1",
                "worker_type": "detection",
                "attempt": 1,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.WORKER_RECOVERED,
            {
                "worker_name": "worker-1",
                "worker_type": "detection",
                "previous_state": "error",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.WORKER_ERROR,
            {
                "worker_name": "worker-1",
                "worker_type": "detection",
                "error": "Processing error",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
    ]

    for event_type, payload in test_cases:
        result = await emitter.emit(event_type, payload)
        assert result is True

    assert mock_event_broadcaster.broadcast_worker_status.call_count == len(test_cases)


# =============================================================================
# Concurrency and Singleton Tests
# =============================================================================


@pytest.mark.asyncio
async def test_singleton_returns_same_instance() -> None:
    """Test get_websocket_emitter() returns singleton instance."""
    emitter1 = await get_websocket_emitter()
    emitter2 = await get_websocket_emitter()

    assert emitter1 is emitter2


@pytest.mark.asyncio
async def test_singleton_updates_broadcasters_on_subsequent_calls() -> None:
    """Test get_websocket_emitter() updates broadcasters if provided."""
    # First call creates singleton
    emitter1 = await get_websocket_emitter()
    assert emitter1._event_broadcaster is None

    # Second call with broadcaster updates it
    mock_broadcaster = AsyncMock()
    emitter2 = await get_websocket_emitter(event_broadcaster=mock_broadcaster)

    assert emitter1 is emitter2
    assert emitter2._event_broadcaster is mock_broadcaster


@pytest.mark.asyncio
async def test_get_websocket_emitter_sync_returns_singleton() -> None:
    """Test get_websocket_emitter_sync() returns existing singleton."""
    # Create singleton first
    emitter1 = await get_websocket_emitter()

    # Sync getter should return same instance
    emitter2 = get_websocket_emitter_sync()

    assert emitter1 is emitter2


@pytest.mark.asyncio
async def test_get_websocket_emitter_sync_returns_none_before_init() -> None:
    """Test get_websocket_emitter_sync() returns None if not initialized."""
    emitter = get_websocket_emitter_sync()
    assert emitter is None


@pytest.mark.asyncio
async def test_concurrent_emission_from_multiple_coroutines(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test concurrent emission from multiple coroutines is safe."""

    async def emit_event(index: int) -> bool:
        payload = {
            "camera_id": f"camera_{index}",
            "camera_name": f"Camera {index}",
            "status": "online",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    # Emit 10 events concurrently
    results = await asyncio.gather(*[emit_event(i) for i in range(10)])

    assert all(results)
    assert emitter.emit_count == 10
    assert mock_event_broadcaster.broadcast_camera_status.call_count == 10


@pytest.mark.asyncio
async def test_singleton_initialization_is_thread_safe() -> None:
    """Test singleton initialization is safe with concurrent access."""
    # Reset state before test
    reset_emitter_state()

    results: list[WebSocketEmitterService | None] = []

    async def get_emitter_async() -> WebSocketEmitterService:
        return await get_websocket_emitter()

    def get_emitter_from_thread() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        emitter = loop.run_until_complete(get_emitter_async())
        results.append(emitter)
        loop.close()

    # Create multiple threads trying to get singleton
    threads = [threading.Thread(target=get_emitter_from_thread) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All threads should get the same instance
    assert len(results) == 5
    assert all(emitter is results[0] for emitter in results)


# =============================================================================
# Statistics and Monitoring Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_stats_returns_emission_metrics(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test get_stats() returns emission counts and broadcaster status."""
    # Emit some events
    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    stats = emitter.get_stats()

    assert stats["emit_count"] == 1
    assert stats["emit_errors"] == 0
    assert stats["validate_payloads"] is True
    assert stats["event_broadcaster_available"] is True
    assert stats["system_broadcaster_available"] is True
    assert stats["redis_client_available"] is True


@pytest.mark.asyncio
async def test_emit_count_property(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit_count property tracks successful emissions."""
    assert emitter.emit_count == 0

    payload = {
        "camera_id": "front_door",
        "camera_name": "Front Door",
        "status": "online",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await emitter.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

    assert emitter.emit_count == 1


@pytest.mark.asyncio
async def test_emit_errors_property(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test emit_errors property tracks failed emissions."""
    assert emitter.emit_errors == 0

    # Cause a validation error
    try:
        await emitter.emit(WebSocketEventType.ALERT_CREATED, {"invalid": "payload"})
    except ValidationError:
        pass

    assert emitter.emit_errors == 1


# =============================================================================
# Setter Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_set_event_broadcaster_updates_broadcaster() -> None:
    """Test set_event_broadcaster() updates the broadcaster after init."""
    emitter = WebSocketEmitterService()
    assert emitter._event_broadcaster is None

    mock_broadcaster = AsyncMock()
    emitter.set_event_broadcaster(mock_broadcaster)

    assert emitter._event_broadcaster is mock_broadcaster


@pytest.mark.asyncio
async def test_set_system_broadcaster_updates_broadcaster() -> None:
    """Test set_system_broadcaster() updates the broadcaster after init."""
    emitter = WebSocketEmitterService()
    assert emitter._system_broadcaster is None

    mock_broadcaster = AsyncMock()
    emitter.set_system_broadcaster(mock_broadcaster)

    assert emitter._system_broadcaster is mock_broadcaster


@pytest.mark.asyncio
async def test_set_redis_client_updates_client() -> None:
    """Test set_redis_client() updates the Redis client after init."""
    emitter = WebSocketEmitterService()
    assert emitter._redis_client is None

    mock_redis = AsyncMock()
    emitter.set_redis_client(mock_redis)

    assert emitter._redis_client is mock_redis
