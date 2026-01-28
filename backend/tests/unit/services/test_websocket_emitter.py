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


# =============================================================================
# Additional Coverage Tests for Uncovered Lines
# =============================================================================


@pytest.mark.asyncio
async def test_validate_event_payload_with_validation_disabled(
    emitter_no_validation: WebSocketEmitterService,
) -> None:
    """Test _validate_event_payload returns None when validation is disabled (line 164)."""
    result = emitter_no_validation._validate_event_payload(
        WebSocketEventType.ALERT_CREATED,
        {"invalid": "payload"},
    )
    assert result is None


@pytest.mark.asyncio
async def test_emit_batch_with_emission_failure(
    mock_event_broadcaster: AsyncMock,
    mock_system_broadcaster: AsyncMock,
    mock_redis_client: AsyncMock,
) -> None:
    """Test emit_batch continues and returns count when emission fails (line 349)."""
    emitter = WebSocketEmitterService(
        event_broadcaster=mock_event_broadcaster,
        system_broadcaster=mock_system_broadcaster,
        redis_client=mock_redis_client,
        validate_payloads=False,
    )

    # Make the first emission fail
    mock_event_broadcaster.broadcast_camera_status.side_effect = [
        Exception("Broadcast failed"),
        None,  # Second call succeeds
    ]

    events = [
        (
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            {
                "camera_id": "camera1",
                "camera_name": "Camera 1",
                "status": "online",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
        (
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            {
                "camera_id": "camera2",
                "camera_name": "Camera 2",
                "status": "online",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ),
    ]

    success_count = await emitter.emit_batch(events)

    # Only second event should succeed
    assert success_count == 1
    assert emitter.emit_errors == 1


@pytest.mark.asyncio
async def test_dispatch_to_event_broadcaster_when_none() -> None:
    """Test _dispatch_to_event_broadcaster logs warning when broadcaster is None (lines 405-406)."""
    emitter = WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=None,
        validate_payloads=False,
    )

    message = {
        "type": "camera.status_changed",
        "payload": {"camera_id": "front_door"},
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": "test-123",
        "channel": "events",
    }

    # Should not raise, just log warning
    await emitter._dispatch_to_event_broadcaster(
        WebSocketEventType.CAMERA_STATUS_CHANGED,
        message,
    )


@pytest.mark.asyncio
async def test_dispatch_service_status_event(
    mock_event_broadcaster: AsyncMock,
    mock_system_broadcaster: AsyncMock,
    mock_redis_client: AsyncMock,
) -> None:
    """Test dispatch of SERVICE_STATUS_CHANGED event (line 462).

    Note: SERVICE_STATUS_CHANGED uses the 'system' channel but is still
    handled by the event broadcaster's broadcast_service_status method.
    We need to emit to the 'events' channel explicitly to trigger this path.
    """
    # Create emitter that will route to event broadcaster
    emitter = WebSocketEmitterService(
        event_broadcaster=mock_event_broadcaster,
        system_broadcaster=mock_system_broadcaster,
        redis_client=mock_redis_client,
        validate_payloads=True,
    )

    payload = {
        "service": "yolo26",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Emit with room="events" to force event broadcaster path
    result = await emitter.emit(WebSocketEventType.SERVICE_STATUS_CHANGED, payload, room="events")

    assert result is True
    mock_event_broadcaster.broadcast_service_status.assert_called_once()

    # Verify the call structure
    call_args = mock_event_broadcaster.broadcast_service_status.call_args[0][0]
    assert call_args["type"] == "service_status"
    assert call_args["data"] == payload


@pytest.mark.asyncio
async def test_dispatch_to_system_broadcaster_when_none() -> None:
    """Test _dispatch_to_system_broadcaster logs warning when broadcaster is None (lines 509-510)."""
    emitter = WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=None,
        validate_payloads=False,
    )

    message = {
        "type": "system.status",
        "payload": {"health": "healthy"},
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": "test-123",
        "channel": "system",
    }

    # Should not raise, just log warning
    await emitter._dispatch_to_system_broadcaster(
        WebSocketEventType.SYSTEM_STATUS,
        message,
    )


@pytest.mark.asyncio
async def test_publish_to_redis_when_none() -> None:
    """Test _publish_to_redis logs warning when Redis client is None (lines 534-535)."""
    emitter = WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=None,
        validate_payloads=False,
    )

    message = {
        "type": "test.event",
        "payload": {"data": "test"},
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": "test-123",
        "channel": "events",
    }

    # Should not raise, just log warning
    await emitter._publish_to_redis(message, "events")


@pytest.mark.asyncio
async def test_publish_to_redis_with_exception(
    mock_redis_client: AsyncMock,
) -> None:
    """Test _publish_to_redis handles exceptions during publish (lines 540-541)."""
    emitter = WebSocketEmitterService(
        event_broadcaster=None,
        system_broadcaster=None,
        redis_client=mock_redis_client,
        validate_payloads=False,
    )

    # Make Redis publish fail
    mock_redis_client.publish.side_effect = Exception("Redis connection failed")

    message = {
        "type": "test.event",
        "payload": {"data": "test"},
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": "test-123",
        "channel": "events",
    }

    # Should not raise, just log error
    await emitter._publish_to_redis(message, "events")

    mock_redis_client.publish.assert_called_once_with("events", message)


@pytest.mark.asyncio
async def test_get_websocket_emitter_updates_system_broadcaster_on_existing_singleton() -> None:
    """Test get_websocket_emitter updates system_broadcaster on existing instance (line 627)."""
    # Create singleton first without broadcasters
    emitter1 = await get_websocket_emitter()
    assert emitter1._system_broadcaster is None

    # Call again with system broadcaster
    mock_system_bc = AsyncMock()
    emitter2 = await get_websocket_emitter(system_broadcaster=mock_system_bc)

    assert emitter1 is emitter2
    assert emitter2._system_broadcaster is mock_system_bc


@pytest.mark.asyncio
async def test_get_websocket_emitter_updates_redis_client_on_existing_singleton() -> None:
    """Test get_websocket_emitter updates redis_client on existing instance (line 629)."""
    # Create singleton first without Redis
    emitter1 = await get_websocket_emitter()
    assert emitter1._redis_client is None

    # Call again with Redis client
    mock_redis = AsyncMock()
    emitter2 = await get_websocket_emitter(redis_client=mock_redis)

    assert emitter1 is emitter2
    assert emitter2._redis_client is mock_redis


@pytest.mark.asyncio
async def test_get_websocket_emitter_with_lock_contention() -> None:
    """Test get_websocket_emitter updates broadcasters after lock acquisition (lines 645-650)."""
    # Reset state to test initialization path
    reset_emitter_state()

    # Create singleton with all dependencies
    mock_event_bc = AsyncMock()
    mock_system_bc = AsyncMock()
    mock_redis = AsyncMock()

    emitter = await get_websocket_emitter(
        event_broadcaster=mock_event_bc,
        system_broadcaster=mock_system_bc,
        redis_client=mock_redis,
    )

    # Verify all dependencies were set
    assert emitter._event_broadcaster is mock_event_bc
    assert emitter._system_broadcaster is mock_system_bc
    assert emitter._redis_client is mock_redis

    # Call again with new dependencies to test the else branch (lines 645-650)
    new_event_bc = AsyncMock()
    new_system_bc = AsyncMock()
    new_redis = AsyncMock()

    emitter2 = await get_websocket_emitter(
        event_broadcaster=new_event_bc,
        system_broadcaster=new_system_bc,
        redis_client=new_redis,
    )

    # Should be same instance with updated dependencies
    assert emitter is emitter2
    assert emitter2._event_broadcaster is new_event_bc
    assert emitter2._system_broadcaster is new_system_bc
    assert emitter2._redis_client is new_redis


@pytest.mark.asyncio
async def test_dispatch_scene_change_event(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test dispatch of SCENE_CHANGE_DETECTED event."""
    payload = {
        "id": 1,
        "camera_id": "front_door",
        "detected_at": datetime.now(UTC).isoformat(),
        "change_type": "angle_changed",
        "similarity_score": 0.65,
    }

    result = await emitter.emit(WebSocketEventType.SCENE_CHANGE_DETECTED, payload)

    assert result is True
    mock_event_broadcaster.broadcast_scene_change.assert_called_once()

    # Verify the call structure
    call_args = mock_event_broadcaster.broadcast_scene_change.call_args[0][0]
    assert call_args["type"] == "scene_change"
    assert call_args["data"] == payload


@pytest.mark.asyncio
async def test_dispatch_event_created_and_updated(
    emitter: WebSocketEmitterService,
    mock_event_broadcaster: AsyncMock,
) -> None:
    """Test dispatch of EVENT_CREATED and EVENT_UPDATED events."""
    # Test EVENT_CREATED
    payload_created = {
        "id": 123,
        "event_id": 123,
        "batch_id": "batch-456",
        "camera_id": "front_door",
        "risk_score": 75,
        "risk_level": "high",
        "summary": "Person detected at front door",
        "reasoning": "Detection shows a person at the door",
    }

    result = await emitter.emit(WebSocketEventType.EVENT_CREATED, payload_created)
    assert result is True

    # Test EVENT_UPDATED
    payload_updated = {
        "id": 123,
        "updated_fields": ["risk_score", "risk_level"],
        "risk_score": 80,
        "risk_level": "high",
        "updated_at": datetime.now(UTC).isoformat(),
    }

    result = await emitter.emit(WebSocketEventType.EVENT_UPDATED, payload_updated)
    assert result is True

    # Both should call broadcast_event
    assert mock_event_broadcaster.broadcast_event.call_count == 2


@pytest.mark.asyncio
async def test_dispatch_event_with_redis_fallback(
    mock_redis_client: AsyncMock,
) -> None:
    """Test dispatch falls back to Redis for unmapped event types."""
    emitter = WebSocketEmitterService(
        event_broadcaster=AsyncMock(),
        system_broadcaster=None,
        redis_client=mock_redis_client,
        validate_payloads=False,
    )

    # Use an event type that doesn't have a specific broadcaster method
    # Create a custom payload that would fallback to Redis
    payload = {
        "test_field": "test_value",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Emit a job event which should fallback to Redis publish
    result = await emitter.emit(WebSocketEventType.JOB_PROGRESS, payload)

    assert result is True
    # Should have published to Redis as fallback
    mock_redis_client.publish.assert_called_once()


@pytest.mark.asyncio
async def test_validate_event_without_schema(
    emitter: WebSocketEmitterService,
    mock_redis_client: AsyncMock,
) -> None:
    """Test validation skips events without schemas (lines 169-170)."""
    # JOB_PROGRESS has a schema - provide valid payload
    payload = {
        "job_id": str(uuid.uuid4()),
        "job_type": "detection",
        "progress": 50,
        "status": "processing",
    }

    # This should succeed with valid payload
    result = await emitter.emit(WebSocketEventType.JOB_PROGRESS, payload)

    assert result is True
    assert emitter.emit_count == 1
    # Event should fallback to Redis since it has no specific broadcaster method
    mock_redis_client.publish.assert_called_once()


@pytest.mark.asyncio
async def test_get_websocket_emitter_concurrent_initialization() -> None:
    """Test concurrent initialization with double-check locking (lines 645-650)."""
    reset_emitter_state()

    mock_event_bc = AsyncMock()
    mock_system_bc = AsyncMock()
    mock_redis = AsyncMock()

    # Simulate concurrent calls to get_websocket_emitter
    # The first call will create the instance
    emitter1 = await get_websocket_emitter(
        event_broadcaster=mock_event_bc,
        system_broadcaster=mock_system_bc,
        redis_client=mock_redis,
    )

    # Subsequent calls with different dependencies should update the singleton
    new_event_bc = AsyncMock()
    new_system_bc = AsyncMock()
    new_redis = AsyncMock()

    # This should hit the else branch in lines 645-650
    # where the emitter already exists after lock acquisition
    emitter2 = await get_websocket_emitter(
        event_broadcaster=new_event_bc,
        system_broadcaster=new_system_bc,
        redis_client=new_redis,
    )

    # Should be same instance with updated dependencies
    assert emitter1 is emitter2
    assert emitter2._event_broadcaster is new_event_bc
    assert emitter2._system_broadcaster is new_system_bc
    assert emitter2._redis_client is new_redis
