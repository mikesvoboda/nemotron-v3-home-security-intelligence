"""Unit tests for PostgreSQL LISTEN/NOTIFY listener service.

Tests for the PgNotifyListener service that listens to PostgreSQL NOTIFY events
and bridges them to Redis pub/sub for WebSocket distribution.

Following TDD approach - comprehensive unit tests for all service functionality.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.pg_notify_listener import (
    PgNotifyChannel,
    PgNotifyListener,
    PgNotifyPayload,
    get_pg_notify_listener,
    stop_pg_notify_listener,
)

# =============================================================================
# PgNotifyPayload Tests
# =============================================================================


class TestPgNotifyPayload:
    """Tests for the PgNotifyPayload dataclass."""

    def test_payload_creation(self) -> None:
        """Test creating a payload directly."""
        payload = PgNotifyPayload(
            channel="events_new",
            operation="INSERT",
            table="events",
            data={"id": 1, "batch_id": "batch_123"},
        )

        assert payload.channel == "events_new"
        assert payload.operation == "INSERT"
        assert payload.table == "events"
        assert payload.data == {"id": 1, "batch_id": "batch_123"}

    def test_payload_from_json_valid(self) -> None:
        """Test parsing a valid JSON payload."""
        json_str = json.dumps(
            {
                "operation": "INSERT",
                "table": "events",
                "data": {"id": 1, "camera_id": "front_door", "risk_score": 75},
            }
        )

        payload = PgNotifyPayload.from_json("events_new", json_str)

        assert payload.channel == "events_new"
        assert payload.operation == "INSERT"
        assert payload.table == "events"
        assert payload.data["id"] == 1
        assert payload.data["camera_id"] == "front_door"
        assert payload.data["risk_score"] == 75

    def test_payload_from_json_missing_fields(self) -> None:
        """Test parsing JSON with missing optional fields."""
        json_str = json.dumps({"data": {"id": 1}})

        payload = PgNotifyPayload.from_json("events_new", json_str)

        assert payload.channel == "events_new"
        assert payload.operation == "UNKNOWN"
        assert payload.table == "unknown"
        assert payload.data == {"id": 1}

    def test_payload_from_json_invalid(self) -> None:
        """Test parsing invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON payload"):
            PgNotifyPayload.from_json("events_new", "not valid json")

    def test_payload_from_json_empty_object(self) -> None:
        """Test parsing empty JSON object."""
        payload = PgNotifyPayload.from_json("events_new", "{}")

        assert payload.channel == "events_new"
        assert payload.operation == "UNKNOWN"
        assert payload.table == "unknown"
        assert payload.data == {}


# =============================================================================
# PgNotifyChannel Enum Tests
# =============================================================================


class TestPgNotifyChannel:
    """Tests for the PgNotifyChannel enum."""

    def test_channel_values(self) -> None:
        """Test that all expected channels exist."""
        assert PgNotifyChannel.EVENTS_NEW.value == "events_new"
        assert PgNotifyChannel.EVENTS_UPDATE.value == "events_update"
        assert PgNotifyChannel.DETECTIONS_NEW.value == "detections_new"
        assert PgNotifyChannel.ALERTS_NEW.value == "alerts_new"

    def test_channel_is_string_enum(self) -> None:
        """Test that channels can be used as strings."""
        channel = PgNotifyChannel.EVENTS_NEW
        assert isinstance(channel.value, str)
        assert str(channel.value) == "events_new"


# =============================================================================
# PgNotifyListener Initialization Tests
# =============================================================================


class TestPgNotifyListenerInit:
    """Tests for PgNotifyListener initialization."""

    def test_init_default_channels(self) -> None:
        """Test initialization with default channels."""
        listener = PgNotifyListener()

        assert len(listener._channels) == 4
        assert PgNotifyChannel.EVENTS_NEW in listener._channels
        assert PgNotifyChannel.EVENTS_UPDATE in listener._channels
        assert PgNotifyChannel.DETECTIONS_NEW in listener._channels
        assert PgNotifyChannel.ALERTS_NEW in listener._channels

    def test_init_custom_channels(self) -> None:
        """Test initialization with custom channels."""
        channels = [PgNotifyChannel.EVENTS_NEW]
        listener = PgNotifyListener(channels=channels)

        assert listener._channels == channels
        assert len(listener._channels) == 1

    def test_init_with_redis_client(self) -> None:
        """Test initialization with Redis client."""
        mock_redis = MagicMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        assert listener._redis is mock_redis

    def test_init_with_broadcaster(self) -> None:
        """Test initialization with EventBroadcaster."""
        mock_broadcaster = MagicMock()
        listener = PgNotifyListener(broadcaster=mock_broadcaster)

        assert listener._broadcaster is mock_broadcaster

    def test_init_state(self) -> None:
        """Test initial state values."""
        listener = PgNotifyListener()

        assert listener._connection is None
        assert listener._listener_task is None
        assert listener._is_running is False
        assert listener._is_healthy is False
        assert listener._reconnect_attempts == 0


# =============================================================================
# PgNotifyListener Connection Tests
# =============================================================================


class TestPgNotifyListenerConnection:
    """Tests for PgNotifyListener database connection."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful database connection."""
        listener = PgNotifyListener()
        mock_connection = AsyncMock()

        with (
            patch("backend.services.pg_notify_listener.asyncpg.connect") as mock_connect,
            patch("backend.services.pg_notify_listener.get_settings") as mock_settings,
        ):
            mock_settings.return_value.database_url = "postgresql+asyncpg://user:pass@localhost/db"  # pragma: allowlist secret  # pragma: allowlist secret
            mock_connect.return_value = mock_connection

            await listener._connect()

            assert listener._connection is mock_connection
            assert listener._is_healthy is True
            assert listener._reconnect_attempts == 0
            # Should add listener for each channel
            assert mock_connection.add_listener.call_count == 4

    @pytest.mark.asyncio
    async def test_connect_retry_on_failure(self) -> None:
        """Test connection retry with exponential backoff."""
        listener = PgNotifyListener()
        mock_connection = AsyncMock()

        attempt_count = 0

        async def connect_with_failures(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Connection refused")
            return mock_connection

        with (
            patch(
                "backend.services.pg_notify_listener.asyncpg.connect",
                side_effect=connect_with_failures,
            ),
            patch("backend.services.pg_notify_listener.get_settings") as mock_settings,
            patch("asyncio.sleep") as mock_sleep,
        ):
            mock_settings.return_value.database_url = (
                "postgresql+asyncpg://user:pass@localhost/db"  # pragma: allowlist secret
            )

            await listener._connect()

            assert listener._connection is mock_connection
            assert listener._is_healthy is True
            # Should have slept twice (attempts 1 and 2 failed)
            assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_connect_max_retries_exceeded(self) -> None:
        """Test that connection gives up after max retries."""
        listener = PgNotifyListener()
        listener.MAX_RECONNECT_ATTEMPTS = 3

        with (
            patch(
                "backend.services.pg_notify_listener.asyncpg.connect",
                side_effect=ConnectionError("Connection refused"),
            ),
            patch("backend.services.pg_notify_listener.get_settings") as mock_settings,
            patch("asyncio.sleep"),
        ):
            mock_settings.return_value.database_url = (
                "postgresql+asyncpg://user:pass@localhost/db"  # pragma: allowlist secret
            )

            with pytest.raises(ConnectionError):
                await listener._connect()

            assert listener._is_healthy is False
            assert listener._reconnect_attempts == 3


# =============================================================================
# PgNotifyListener Start/Stop Tests
# =============================================================================


class TestPgNotifyListenerStartStop:
    """Tests for starting and stopping the listener."""

    @pytest.mark.asyncio
    async def test_start_success(self) -> None:
        """Test successful listener start."""
        listener = PgNotifyListener()

        with patch.object(listener, "_connect") as mock_connect:
            await listener.start()

            assert listener._is_running is True
            mock_connect.assert_called_once()
            assert listener._listener_task is not None

        # Cleanup
        await listener.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self) -> None:
        """Test starting when already running is a no-op."""
        listener = PgNotifyListener()
        listener._is_running = True

        with patch.object(listener, "_connect") as mock_connect:
            await listener.start()

            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_cleanup(self) -> None:
        """Test that stop properly cleans up resources."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._is_healthy = True

        mock_connection = AsyncMock()
        listener._connection = mock_connection

        # Create a proper task that raises CancelledError when awaited after cancel
        async def dummy_task():
            await asyncio.sleep(100)

        real_task = asyncio.create_task(dummy_task())
        listener._listener_task = real_task

        await listener.stop()

        assert listener._is_running is False
        assert listener._is_healthy is False
        assert listener._connection is None
        assert listener._listener_task is None
        mock_connection.close.assert_called_once()


# =============================================================================
# PgNotifyListener Notification Handling Tests
# =============================================================================


class TestPgNotifyListenerHandlers:
    """Tests for notification handlers."""

    @pytest.mark.asyncio
    async def test_handle_event_new(self) -> None:
        """Test handling new event notifications."""
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="events_new",
            operation="INSERT",
            table="events",
            data={
                "id": 1,
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected",
                "started_at": "2026-01-23T12:00:00Z",
            },
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_event_new(payload)

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args
            assert call_args[0][0] == "security_events"

            message = call_args[0][1]
            assert message["type"] == "event"
            assert message["source"] == "pg_notify"
            assert message["data"]["id"] == 1
            assert message["data"]["camera_id"] == "front_door"
            assert message["data"]["risk_score"] == 75

    @pytest.mark.asyncio
    async def test_handle_event_update(self) -> None:
        """Test handling event update notifications."""
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="events_update",
            operation="UPDATE",
            table="events",
            data={
                "id": 1,
                "risk_score": 85,
                "risk_level": "critical",
                "summary": "Person with weapon detected",
                "reviewed": True,
            },
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_event_update(payload)

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args

            message = call_args[0][1]
            assert message["type"] == "event_update"
            assert message["data"]["reviewed"] is True

    @pytest.mark.asyncio
    async def test_handle_event_update_redis_error(self) -> None:
        """Test handling Redis publish errors in event update."""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis connection lost")
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="events_update",
            operation="UPDATE",
            table="events",
            data={"id": 1, "risk_score": 85},
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            # Should not raise, just log the error
            await listener._handle_event_update(payload)

    @pytest.mark.asyncio
    async def test_handle_detection_new(self) -> None:
        """Test handling new detection notifications."""
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="detections_new",
            operation="INSERT",
            table="detections",
            data={
                "id": 100,
                "camera_id": "back_yard",
                "object_type": "person",
                "confidence": 0.95,
                "detected_at": "2026-01-23T12:30:00Z",
            },
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_detection_new(payload)

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args

            message = call_args[0][1]
            assert message["type"] == "detection.new"
            assert message["data"]["detection_id"] == 100
            assert message["data"]["label"] == "person"
            assert message["data"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_handle_detection_new_redis_error(self) -> None:
        """Test handling Redis publish errors in detection new."""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis unavailable")
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="detections_new",
            operation="INSERT",
            table="detections",
            data={"id": 100, "camera_id": "back_yard"},
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            # Should not raise, just log the error
            await listener._handle_detection_new(payload)

    @pytest.mark.asyncio
    async def test_handle_alert_new(self) -> None:
        """Test handling new alert notifications."""
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="alerts_new",
            operation="INSERT",
            table="alerts",
            data={
                "id": "alert-uuid-123",
                "event_id": 1,
                "rule_id": "rule-uuid-456",
                "severity": "high",
                "status": "pending",
            },
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await listener._handle_alert_new(payload)

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args

            message = call_args[0][1]
            assert message["type"] == "alert_created"
            assert message["data"]["id"] == "alert-uuid-123"
            assert message["data"]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_handle_alert_new_redis_error(self) -> None:
        """Test handling Redis publish errors in alert new."""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis connection failed")
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="alerts_new",
            operation="INSERT",
            table="alerts",
            data={"id": "alert-uuid-123", "event_id": 1},
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            # Should not raise, just log the error
            await listener._handle_alert_new(payload)

    @pytest.mark.asyncio
    async def test_handle_notification_no_redis(self) -> None:
        """Test notification handling when no Redis client is configured."""
        listener = PgNotifyListener(redis_client=None)

        payload = PgNotifyPayload(
            channel="events_new",
            operation="INSERT",
            table="events",
            data={"id": 1},
        )

        # Should not raise an error
        await listener._handle_event_new(payload)

    @pytest.mark.asyncio
    async def test_handle_notification_redis_error(self) -> None:
        """Test graceful handling of Redis publish errors."""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis unavailable")
        listener = PgNotifyListener(redis_client=mock_redis)

        payload = PgNotifyPayload(
            channel="events_new",
            operation="INSERT",
            table="events",
            data={"id": 1},
        )

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            # Should not raise, just log the error
            await listener._handle_event_new(payload)

    @pytest.mark.asyncio
    async def test_handle_notification_invalid_payload(self) -> None:
        """Test handling invalid payload gracefully."""
        listener = PgNotifyListener()

        # Should not raise, just log the error
        await listener._handle_notification("events_new", "not valid json")

    @pytest.mark.asyncio
    async def test_handle_notification_unknown_channel(self) -> None:
        """Test handling unknown channel gracefully."""
        listener = PgNotifyListener()

        payload_json = json.dumps({"operation": "INSERT", "table": "unknown", "data": {}})

        # Should not raise, just log a warning
        await listener._handle_notification("unknown_channel", payload_json)

    @pytest.mark.asyncio
    async def test_handle_notification_routes_to_event_new(self) -> None:
        """Test that notifications are routed to _handle_event_new."""
        listener = PgNotifyListener()

        payload_json = json.dumps({"operation": "INSERT", "table": "events", "data": {"id": 1}})

        with patch.object(listener, "_handle_event_new") as mock_handler:
            await listener._handle_notification(PgNotifyChannel.EVENTS_NEW.value, payload_json)

            mock_handler.assert_called_once()
            payload = mock_handler.call_args[0][0]
            assert payload.channel == PgNotifyChannel.EVENTS_NEW.value

    @pytest.mark.asyncio
    async def test_handle_notification_routes_to_event_update(self) -> None:
        """Test that notifications are routed to _handle_event_update."""
        listener = PgNotifyListener()

        payload_json = json.dumps({"operation": "UPDATE", "table": "events", "data": {"id": 1}})

        with patch.object(listener, "_handle_event_update") as mock_handler:
            await listener._handle_notification(PgNotifyChannel.EVENTS_UPDATE.value, payload_json)

            mock_handler.assert_called_once()
            payload = mock_handler.call_args[0][0]
            assert payload.channel == PgNotifyChannel.EVENTS_UPDATE.value

    @pytest.mark.asyncio
    async def test_handle_notification_routes_to_detection_new(self) -> None:
        """Test that notifications are routed to _handle_detection_new."""
        listener = PgNotifyListener()

        payload_json = json.dumps({"operation": "INSERT", "table": "detections", "data": {"id": 1}})

        with patch.object(listener, "_handle_detection_new") as mock_handler:
            await listener._handle_notification(PgNotifyChannel.DETECTIONS_NEW.value, payload_json)

            mock_handler.assert_called_once()
            payload = mock_handler.call_args[0][0]
            assert payload.channel == PgNotifyChannel.DETECTIONS_NEW.value

    @pytest.mark.asyncio
    async def test_handle_notification_routes_to_alert_new(self) -> None:
        """Test that notifications are routed to _handle_alert_new."""
        listener = PgNotifyListener()

        payload_json = json.dumps(
            {"operation": "INSERT", "table": "alerts", "data": {"id": "uuid-123"}}
        )

        with patch.object(listener, "_handle_alert_new") as mock_handler:
            await listener._handle_notification(PgNotifyChannel.ALERTS_NEW.value, payload_json)

            mock_handler.assert_called_once()
            payload = mock_handler.call_args[0][0]
            assert payload.channel == PgNotifyChannel.ALERTS_NEW.value

    @pytest.mark.asyncio
    async def test_handle_notification_handles_handler_exception(self) -> None:
        """Test that exceptions in handlers are caught and logged."""
        listener = PgNotifyListener()

        payload_json = json.dumps({"operation": "INSERT", "table": "events", "data": {"id": 1}})

        with patch.object(listener, "_handle_event_new", side_effect=RuntimeError("Handler error")):
            # Should not raise, just log the error
            await listener._handle_notification(PgNotifyChannel.EVENTS_NEW.value, payload_json)


# =============================================================================
# PgNotifyListener Notification Callback Tests
# =============================================================================


class TestPgNotifyListenerCallback:
    """Tests for the asyncpg notification callback."""

    def test_notification_callback_creates_task(self) -> None:
        """Test that callback schedules async handler."""
        listener = PgNotifyListener()

        mock_connection = MagicMock()
        payload = json.dumps({"operation": "INSERT", "table": "events", "data": {"id": 1}})

        with patch("asyncio.create_task") as mock_create_task:
            listener._notification_callback(mock_connection, 12345, "events_new", payload)

            mock_create_task.assert_called_once()


# =============================================================================
# PgNotifyListener Health Check Tests
# =============================================================================


class TestPgNotifyListenerHealth:
    """Tests for health check functionality."""

    def test_is_healthy_false_when_not_running(self) -> None:
        """Test health check returns False when not running."""
        listener = PgNotifyListener()

        assert listener.is_healthy() is False

    def test_is_healthy_false_when_unhealthy(self) -> None:
        """Test health check returns False when not healthy."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._is_healthy = False

        assert listener.is_healthy() is False

    def test_is_healthy_true_when_running_and_healthy(self) -> None:
        """Test health check returns True when running and healthy."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._is_healthy = True

        assert listener.is_healthy() is True

    def test_get_status(self) -> None:
        """Test get_status returns complete status info."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._is_healthy = True
        listener._reconnect_attempts = 2

        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        listener._connection = mock_connection

        status = listener.get_status()

        assert status["running"] is True
        assert status["healthy"] is True
        assert status["connected"] is True
        assert status["reconnect_attempts"] == 2
        assert len(status["channels"]) == 4

    def test_get_status_no_connection(self) -> None:
        """Test get_status when connection is None."""
        listener = PgNotifyListener()

        status = listener.get_status()

        assert status["connected"] is False


# =============================================================================
# PgNotifyListener Listen Loop Tests
# =============================================================================


class TestPgNotifyListenerLoop:
    """Tests for the main listen loop."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_listen_loop_handles_cancellation(self) -> None:
        """Test that listen loop handles cancellation gracefully."""
        listener = PgNotifyListener()
        listener._is_running = True

        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = False
        listener._connection = mock_connection

        async def cancel_after_sleep(*args):
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=cancel_after_sleep):
            # Should not raise
            await listener._listen_loop()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_listen_loop_reconnects_on_closed_connection(self) -> None:
        """Test that listen loop reconnects when connection is closed."""
        listener = PgNotifyListener()
        listener._is_running = True

        # Connection that is closed
        mock_connection = MagicMock()
        mock_connection.is_closed.return_value = True
        listener._connection = mock_connection

        reconnect_called = False

        async def mock_connect():
            nonlocal reconnect_called
            reconnect_called = True
            listener._is_running = False  # Stop loop after reconnect

        with (
            patch.object(listener, "_connect", side_effect=mock_connect),
            patch("asyncio.sleep"),
        ):
            await listener._listen_loop()

            assert reconnect_called
            assert listener._is_healthy is False  # Set before reconnect

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_listen_loop_reconnects_on_none_connection(self) -> None:
        """Test that listen loop reconnects when connection is None."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._connection = None

        reconnect_called = False

        async def mock_connect():
            nonlocal reconnect_called
            reconnect_called = True
            listener._is_running = False  # Stop loop

        with (
            patch.object(listener, "_connect", side_effect=mock_connect),
            patch("asyncio.sleep"),
        ):
            await listener._listen_loop()

            assert reconnect_called

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_listen_loop_handles_exception_with_reconnect(self) -> None:
        """Test that listen loop handles exceptions and attempts reconnection."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._is_healthy = True

        mock_connection = MagicMock()
        call_count = 0

        def is_closed_raises():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Unexpected error")
            # After error, stop the loop
            listener._is_running = False
            return False

        mock_connection.is_closed.side_effect = is_closed_raises
        listener._connection = mock_connection

        with patch("asyncio.sleep") as mock_sleep:
            await listener._listen_loop()

            # Should have marked unhealthy
            assert listener._is_healthy is False
            # Should have incremented reconnect attempts
            assert listener._reconnect_attempts == 1
            # Should have slept for exponential backoff
            assert mock_sleep.call_count > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_listen_loop_stops_after_max_reconnect_attempts(self) -> None:
        """Test that listen loop stops after max reconnection attempts."""
        listener = PgNotifyListener()
        listener._is_running = True
        listener._reconnect_attempts = 0
        listener.MAX_RECONNECT_ATTEMPTS = 3

        mock_connection = MagicMock()

        def is_closed_raises():
            raise RuntimeError("Persistent error")

        mock_connection.is_closed.side_effect = is_closed_raises
        listener._connection = mock_connection

        with patch("asyncio.sleep") as mock_sleep:
            await listener._listen_loop()

            # Should have stopped after max attempts
            # Note: It increments to MAX and then breaks, so final count equals MAX
            assert listener._reconnect_attempts >= listener.MAX_RECONNECT_ATTEMPTS
            # Should have slept MAX-1 times (doesn't sleep after the final increment)
            assert mock_sleep.call_count == listener.MAX_RECONNECT_ATTEMPTS - 1


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalInstance:
    """Tests for global listener instance management."""

    @pytest.mark.asyncio
    async def test_get_pg_notify_listener_creates_instance(self) -> None:
        """Test that get_pg_notify_listener creates a new instance."""
        # Reset global state
        import backend.services.pg_notify_listener as module

        module._listener = None

        listener = await get_pg_notify_listener()

        assert listener is not None
        assert isinstance(listener, PgNotifyListener)

        # Cleanup
        module._listener = None

    @pytest.mark.asyncio
    async def test_get_pg_notify_listener_returns_same_instance(self) -> None:
        """Test that get_pg_notify_listener returns the same instance."""
        import backend.services.pg_notify_listener as module

        module._listener = None

        listener1 = await get_pg_notify_listener()
        listener2 = await get_pg_notify_listener()

        assert listener1 is listener2

        # Cleanup
        module._listener = None

    @pytest.mark.asyncio
    async def test_stop_pg_notify_listener(self) -> None:
        """Test stopping the global listener instance."""
        import backend.services.pg_notify_listener as module

        mock_listener = AsyncMock()
        module._listener = mock_listener

        await stop_pg_notify_listener()

        mock_listener.stop.assert_called_once()
        assert module._listener is None


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestPgNotifyListenerIntegration:
    """Integration-style tests for PgNotifyListener."""

    @pytest.mark.asyncio
    async def test_full_notification_flow(self) -> None:
        """Test the full notification flow from callback to Redis publish."""
        mock_redis = AsyncMock()
        listener = PgNotifyListener(redis_client=mock_redis)

        payload_data = {
            "operation": "INSERT",
            "table": "events",
            "data": {
                "id": 42,
                "batch_id": "batch_xyz",
                "camera_id": "garage",
                "risk_score": 90,
                "risk_level": "critical",
                "summary": "Armed intruder detected",
                "started_at": "2026-01-23T15:00:00Z",
            },
        }
        payload_json = json.dumps(payload_data)

        with patch("backend.services.pg_notify_listener.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            # Simulate notification callback
            await listener._handle_notification(PgNotifyChannel.EVENTS_NEW.value, payload_json)

            # Verify Redis publish was called with correct data
            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args

            assert call_args[0][0] == "security_events"
            message = call_args[0][1]
            assert message["type"] == "event"
            assert message["data"]["id"] == 42
            assert message["data"]["risk_score"] == 90
            assert message["data"]["risk_level"] == "critical"
