"""Unit tests for WebSocket emitter service.

This module tests the WebSocketEmitterService including:
- Event emission with validation
- Broadcast functionality
- User-targeted emission
- Batch emission
- Integration with existing broadcasters
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from backend.core.websocket import WebSocketEventType
from backend.services.websocket_emitter import (
    WebSocketEmitterService,
    get_websocket_emitter,
    get_websocket_emitter_sync,
    reset_emitter_state,
)


@pytest.fixture
def mock_event_broadcaster():
    """Create a mock EventBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.broadcast_event = AsyncMock(return_value=1)
    broadcaster.broadcast_alert = AsyncMock(return_value=1)
    broadcaster.broadcast_camera_status = AsyncMock(return_value=1)
    broadcaster.broadcast_scene_change = AsyncMock(return_value=1)
    broadcaster.broadcast_service_status = AsyncMock(return_value=1)
    return broadcaster


@pytest.fixture
def mock_system_broadcaster():
    """Create a mock SystemBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.broadcast_status = AsyncMock()
    return broadcaster


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def emitter_service(mock_event_broadcaster, mock_system_broadcaster, mock_redis_client):
    """Create a WebSocketEmitterService with mocked dependencies."""
    return WebSocketEmitterService(
        event_broadcaster=mock_event_broadcaster,
        system_broadcaster=mock_system_broadcaster,
        redis_client=mock_redis_client,
        validate_payloads=True,
    )


@pytest.fixture
def emitter_no_validation(mock_event_broadcaster, mock_system_broadcaster):
    """Create a WebSocketEmitterService with validation disabled."""
    return WebSocketEmitterService(
        event_broadcaster=mock_event_broadcaster,
        system_broadcaster=mock_system_broadcaster,
        validate_payloads=False,
    )


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global emitter state before and after each test."""
    reset_emitter_state()
    yield
    reset_emitter_state()


class TestWebSocketEmitterServiceInit:
    """Tests for WebSocketEmitterService initialization."""

    def test_init_with_all_dependencies(
        self, mock_event_broadcaster, mock_system_broadcaster, mock_redis_client
    ):
        """Test initialization with all dependencies."""
        emitter = WebSocketEmitterService(
            event_broadcaster=mock_event_broadcaster,
            system_broadcaster=mock_system_broadcaster,
            redis_client=mock_redis_client,
        )
        assert emitter._event_broadcaster is mock_event_broadcaster
        assert emitter._system_broadcaster is mock_system_broadcaster
        assert emitter._redis_client is mock_redis_client
        assert emitter._validate_payloads is True

    def test_init_with_no_dependencies(self):
        """Test initialization with no dependencies."""
        emitter = WebSocketEmitterService()
        assert emitter._event_broadcaster is None
        assert emitter._system_broadcaster is None
        assert emitter._redis_client is None

    def test_init_with_validation_disabled(self):
        """Test initialization with payload validation disabled."""
        emitter = WebSocketEmitterService(validate_payloads=False)
        assert emitter._validate_payloads is False

    def test_set_event_broadcaster(self, mock_event_broadcaster):
        """Test setting event broadcaster after init."""
        emitter = WebSocketEmitterService()
        emitter.set_event_broadcaster(mock_event_broadcaster)
        assert emitter._event_broadcaster is mock_event_broadcaster

    def test_set_system_broadcaster(self, mock_system_broadcaster):
        """Test setting system broadcaster after init."""
        emitter = WebSocketEmitterService()
        emitter.set_system_broadcaster(mock_system_broadcaster)
        assert emitter._system_broadcaster is mock_system_broadcaster

    def test_set_redis_client(self, mock_redis_client):
        """Test setting Redis client after init."""
        emitter = WebSocketEmitterService()
        emitter.set_redis_client(mock_redis_client)
        assert emitter._redis_client is mock_redis_client


class TestEmitMethod:
    """Tests for emit() method."""

    @pytest.mark.asyncio
    async def test_emit_alert_created_success(self, emitter_service, mock_event_broadcaster):
        """Test successful alert.created emission."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "front_door:person:rule1",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit(WebSocketEventType.ALERT_CREATED, payload)

        assert result is True
        assert emitter_service.emit_count == 1
        assert emitter_service.emit_errors == 0
        mock_event_broadcaster.broadcast_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_emit_with_invalid_payload_raises_validation_error(self, emitter_service):
        """Test that invalid payload raises ValidationError."""
        payload = {
            "id": "123",
            # Missing required fields
        }
        with pytest.raises(ValidationError):
            await emitter_service.emit(WebSocketEventType.ALERT_CREATED, payload)

        assert emitter_service.emit_errors == 1

    @pytest.mark.asyncio
    async def test_emit_with_validation_disabled_skips_validation(self, emitter_no_validation):
        """Test that validation is skipped when disabled."""
        payload = {"id": "123"}  # Invalid payload
        result = await emitter_no_validation.emit(WebSocketEventType.ALERT_CREATED, payload)

        # Should succeed without validation
        assert result is True

    @pytest.mark.asyncio
    async def test_emit_with_custom_room(self, emitter_service, mock_event_broadcaster):
        """Test emission with custom room."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "test",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit(
            WebSocketEventType.ALERT_CREATED,
            payload,
            room="custom_room",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_emit_with_correlation_id(self, emitter_service, mock_event_broadcaster):
        """Test emission with correlation ID."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "test",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit(
            WebSocketEventType.ALERT_CREATED,
            payload,
            correlation_id="req-abc123",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_emit_camera_status_changed(self, emitter_service, mock_event_broadcaster):
        """Test camera.status_changed emission."""
        payload = {
            "camera_id": "front_door",
            "camera_name": "Front Door Camera",
            "status": "online",
            "previous_status": "offline",
            "timestamp": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit(WebSocketEventType.CAMERA_STATUS_CHANGED, payload)

        assert result is True
        mock_event_broadcaster.broadcast_camera_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_emit_job_progress(self, emitter_service, mock_event_broadcaster):
        """Test job.progress emission."""
        payload = {
            "job_id": "job-123",
            "job_type": "export",
            "progress": 50,
            "status": "running",
        }
        result = await emitter_service.emit(WebSocketEventType.JOB_PROGRESS, payload)

        assert result is True

    @pytest.mark.asyncio
    async def test_emit_system_status(self, emitter_service, mock_system_broadcaster):
        """Test system.status emission routes to system broadcaster."""
        payload = {
            "gpu": {"utilization": 45.5},
            "cameras": {"active": 4, "total": 6},
            "queue": {"pending": 2, "processing": 1},
            "health": "healthy",
            "timestamp": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit(WebSocketEventType.SYSTEM_STATUS, payload)

        assert result is True
        mock_system_broadcaster.broadcast_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_emit_event_type_without_schema(self, emitter_service):
        """Test emission of event type without payload schema."""
        # PING and PONG don't have schemas
        result = await emitter_service.emit(WebSocketEventType.PING, {})

        assert result is True


class TestBroadcastMethod:
    """Tests for broadcast() method."""

    @pytest.mark.asyncio
    async def test_broadcast_calls_emit_without_room(self, emitter_service):
        """Test broadcast calls emit with room=None."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "test",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.broadcast(WebSocketEventType.ALERT_CREATED, payload)

        assert result is True
        assert emitter_service.emit_count == 1


class TestEmitToUserMethod:
    """Tests for emit_to_user() method."""

    @pytest.mark.asyncio
    async def test_emit_to_user_uses_user_room_pattern(self, emitter_service):
        """Test emit_to_user creates user-specific room."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "test",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit_to_user(
            "user-123",
            WebSocketEventType.ALERT_CREATED,
            payload,
        )

        assert result is True


class TestEmitBatchMethod:
    """Tests for emit_batch() method."""

    @pytest.mark.asyncio
    async def test_emit_batch_multiple_events(self, emitter_no_validation):
        """Test batch emission of multiple events."""
        events = [
            (
                WebSocketEventType.JOB_STARTED,
                {"job_id": "1", "job_type": "export", "started_at": "2026-01-09T12:00:00Z"},
            ),
            (
                WebSocketEventType.JOB_PROGRESS,
                {"job_id": "1", "job_type": "export", "progress": 50, "status": "running"},
            ),
            (
                WebSocketEventType.JOB_COMPLETED,
                {"job_id": "1", "job_type": "export", "completed_at": "2026-01-09T12:05:00Z"},
            ),
        ]
        success_count = await emitter_no_validation.emit_batch(events)

        assert success_count == 3
        assert emitter_no_validation.emit_count == 3

    @pytest.mark.asyncio
    async def test_emit_batch_with_shared_correlation_id(self, emitter_no_validation):
        """Test batch emission with shared correlation ID."""
        events = [
            (
                WebSocketEventType.JOB_STARTED,
                {"job_id": "1", "job_type": "export", "started_at": "2026-01-09T12:00:00Z"},
            ),
            (
                WebSocketEventType.JOB_COMPLETED,
                {"job_id": "1", "job_type": "export", "completed_at": "2026-01-09T12:05:00Z"},
            ),
        ]
        success_count = await emitter_no_validation.emit_batch(
            events,
            correlation_id="batch-123",
        )

        assert success_count == 2

    @pytest.mark.asyncio
    async def test_emit_batch_continues_on_validation_error(self, emitter_service):
        """Test batch emission continues after validation error."""
        events = [
            (
                WebSocketEventType.JOB_PROGRESS,
                {"job_id": "1", "job_type": "export", "progress": 50, "status": "running"},
            ),
            (WebSocketEventType.ALERT_CREATED, {"invalid": "payload"}),  # Will fail
            (
                WebSocketEventType.JOB_PROGRESS,
                {"job_id": "2", "job_type": "cleanup", "progress": 75, "status": "running"},
            ),
        ]
        success_count = await emitter_service.emit_batch(events)

        # Should succeed for 2 out of 3 (the second fails validation)
        assert success_count == 2


class TestGetStats:
    """Tests for get_stats() method."""

    @pytest.mark.asyncio
    async def test_get_stats_initial(self, emitter_service):
        """Test stats are correct initially."""
        stats = emitter_service.get_stats()

        assert stats["emit_count"] == 0
        assert stats["emit_errors"] == 0
        assert stats["validate_payloads"] is True
        assert stats["event_broadcaster_available"] is True
        assert stats["system_broadcaster_available"] is True
        assert stats["redis_client_available"] is True

    @pytest.mark.asyncio
    async def test_get_stats_after_emissions(self, emitter_no_validation):
        """Test stats are updated after emissions."""
        await emitter_no_validation.emit(
            WebSocketEventType.JOB_PROGRESS,
            {"job_id": "1", "job_type": "export", "progress": 50, "status": "running"},
        )
        await emitter_no_validation.emit(
            WebSocketEventType.JOB_COMPLETED,
            {"job_id": "1", "job_type": "export", "completed_at": "2026-01-09T12:05:00Z"},
        )

        stats = emitter_no_validation.get_stats()
        assert stats["emit_count"] == 2

    def test_get_stats_without_broadcasters(self):
        """Test stats when broadcasters not available."""
        emitter = WebSocketEmitterService()
        stats = emitter.get_stats()

        assert stats["event_broadcaster_available"] is False
        assert stats["system_broadcaster_available"] is False
        assert stats["redis_client_available"] is False


class TestGlobalEmitterSingleton:
    """Tests for global emitter singleton functions."""

    @pytest.mark.asyncio
    async def test_get_websocket_emitter_creates_singleton(self):
        """Test get_websocket_emitter creates singleton on first call."""
        emitter1 = await get_websocket_emitter()
        emitter2 = await get_websocket_emitter()

        assert emitter1 is emitter2

    @pytest.mark.asyncio
    async def test_get_websocket_emitter_accepts_broadcasters(
        self, mock_event_broadcaster, mock_system_broadcaster
    ):
        """Test get_websocket_emitter accepts broadcaster dependencies."""
        emitter = await get_websocket_emitter(
            event_broadcaster=mock_event_broadcaster,
            system_broadcaster=mock_system_broadcaster,
        )

        assert emitter._event_broadcaster is mock_event_broadcaster
        assert emitter._system_broadcaster is mock_system_broadcaster

    @pytest.mark.asyncio
    async def test_get_websocket_emitter_updates_existing(
        self, mock_event_broadcaster, mock_system_broadcaster
    ):
        """Test get_websocket_emitter updates existing singleton."""
        # Create initial emitter
        emitter1 = await get_websocket_emitter()
        assert emitter1._event_broadcaster is None

        # Update with broadcaster
        emitter2 = await get_websocket_emitter(
            event_broadcaster=mock_event_broadcaster,
        )

        assert emitter1 is emitter2
        assert emitter1._event_broadcaster is mock_event_broadcaster

    def test_get_websocket_emitter_sync_before_init(self):
        """Test get_websocket_emitter_sync returns None before init."""
        emitter = get_websocket_emitter_sync()
        assert emitter is None

    @pytest.mark.asyncio
    async def test_get_websocket_emitter_sync_after_init(self):
        """Test get_websocket_emitter_sync returns singleton after init."""
        await get_websocket_emitter()
        emitter = get_websocket_emitter_sync()

        assert emitter is not None

    def test_reset_emitter_state_clears_singleton(self):
        """Test reset_emitter_state clears the singleton."""
        reset_emitter_state()
        emitter = get_websocket_emitter_sync()

        assert emitter is None


class TestEventDispatchRouting:
    """Tests for event dispatch routing logic."""

    @pytest.mark.asyncio
    async def test_alert_events_route_to_event_broadcaster(
        self, emitter_no_validation, mock_event_broadcaster
    ):
        """Test alert events route through EventBroadcaster."""
        await emitter_no_validation.emit(
            WebSocketEventType.ALERT_CREATED,
            {"id": "123", "event_id": 1, "severity": "high", "status": "pending"},
        )

        mock_event_broadcaster.broadcast_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_camera_events_route_to_event_broadcaster(
        self, emitter_no_validation, mock_event_broadcaster
    ):
        """Test camera events route through EventBroadcaster."""
        await emitter_no_validation.emit(
            WebSocketEventType.CAMERA_ONLINE,
            {"camera_id": "front_door", "camera_name": "Front Door"},
        )

        mock_event_broadcaster.broadcast_camera_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_events_route_to_system_broadcaster(
        self, emitter_no_validation, mock_system_broadcaster
    ):
        """Test system events route through SystemBroadcaster."""
        await emitter_no_validation.emit(
            WebSocketEventType.SYSTEM_STATUS,
            {"health": "healthy", "gpu": {}, "cameras": {}, "queue": {}},
        )

        mock_system_broadcaster.broadcast_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scene_change_routes_to_event_broadcaster(
        self, emitter_no_validation, mock_event_broadcaster
    ):
        """Test scene change events route through EventBroadcaster."""
        await emitter_no_validation.emit(
            WebSocketEventType.SCENE_CHANGE_DETECTED,
            {"id": 1, "camera_id": "front_door", "change_type": "view_blocked"},
        )

        mock_event_broadcaster.broadcast_scene_change.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_security_events_route_to_event_broadcaster(
        self, emitter_no_validation, mock_event_broadcaster
    ):
        """Test security events route through EventBroadcaster."""
        await emitter_no_validation.emit(
            WebSocketEventType.EVENT_CREATED,
            {"id": 1, "camera_id": "front_door", "risk_score": 75},
        )

        mock_event_broadcaster.broadcast_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_to_redis_when_no_broadcaster(self, mock_redis_client):
        """Test fallback to Redis when no broadcaster available."""
        emitter = WebSocketEmitterService(
            redis_client=mock_redis_client,
            validate_payloads=False,
        )
        await emitter.emit(
            WebSocketEventType.DETECTION_NEW,
            {"detection_id": "123", "label": "person"},
        )

        mock_redis_client.publish.assert_awaited()


class TestPayloadValidation:
    """Tests for payload validation logic."""

    @pytest.mark.asyncio
    async def test_valid_alert_payload_passes_validation(self, emitter_service):
        """Test valid alert payload passes validation."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "front_door:person:rule1",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = await emitter_service.emit(WebSocketEventType.ALERT_CREATED, payload)

        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_severity_fails_validation(self, emitter_service):
        """Test invalid severity value fails validation."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "invalid_severity",  # Invalid
            "status": "pending",
            "dedup_key": "test",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        with pytest.raises(ValidationError):
            await emitter_service.emit(WebSocketEventType.ALERT_CREATED, payload)

    @pytest.mark.asyncio
    async def test_missing_required_field_fails_validation(self, emitter_service):
        """Test missing required field fails validation."""
        payload = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            # Missing event_id, severity, status, etc.
        }
        with pytest.raises(ValidationError):
            await emitter_service.emit(WebSocketEventType.ALERT_CREATED, payload)

    @pytest.mark.asyncio
    async def test_job_progress_validates_range(self, emitter_service):
        """Test job progress validates progress range (0-100)."""
        # Valid progress
        payload = {
            "job_id": "job-123",
            "job_type": "export",
            "progress": 50,
            "status": "running",
        }
        result = await emitter_service.emit(WebSocketEventType.JOB_PROGRESS, payload)
        assert result is True

        # Invalid progress (over 100)
        invalid_payload = {
            "job_id": "job-123",
            "job_type": "export",
            "progress": 150,  # Invalid
            "status": "running",
        }
        with pytest.raises(ValidationError):
            await emitter_service.emit(WebSocketEventType.JOB_PROGRESS, invalid_payload)


class TestEmitterProperties:
    """Tests for emitter property accessors."""

    def test_emit_count_property(self, emitter_service):
        """Test emit_count property."""
        assert emitter_service.emit_count == 0

    def test_emit_errors_property(self, emitter_service):
        """Test emit_errors property."""
        assert emitter_service.emit_errors == 0

    @pytest.mark.asyncio
    async def test_emit_count_increments(self, emitter_no_validation):
        """Test emit_count increments on successful emit."""
        await emitter_no_validation.emit(
            WebSocketEventType.PING,
            {},
        )
        assert emitter_no_validation.emit_count == 1

    @pytest.mark.asyncio
    async def test_emit_errors_increments_on_validation_failure(self, emitter_service):
        """Test emit_errors increments on validation failure."""
        try:
            await emitter_service.emit(
                WebSocketEventType.ALERT_CREATED,
                {"invalid": "payload"},
            )
        except ValidationError:
            pass

        assert emitter_service.emit_errors == 1
