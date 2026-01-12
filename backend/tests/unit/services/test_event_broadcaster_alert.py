"""Unit tests for EventBroadcaster.broadcast_alert method (NEM-1981, NEM-2294).

Tests cover:
- Broadcasting alert created events
- Broadcasting alert updated events (NEM-2294)
- Broadcasting alert acknowledged events
- Broadcasting alert resolved events (NEM-2294)
- Validation error handling
- Unknown event type handling
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.services.event_broadcaster import EventBroadcaster

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_alert_data() -> dict[str, Any]:
    """Create valid alert data for testing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "event_id": 123,
        "rule_id": "550e8400-e29b-41d4-a716-446655440001",
        "severity": "high",
        "status": "pending",
        "dedup_key": "front_door:person:rule1",
        "created_at": "2026-01-09T12:00:00Z",
        "updated_at": "2026-01-09T12:00:00Z",
    }


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=2)  # 2 subscribers
    return redis


@pytest.fixture
def broadcaster(mock_redis_client: AsyncMock) -> EventBroadcaster:
    """Create an EventBroadcaster with mocked Redis."""
    # Reset singleton for testing
    EventBroadcaster._instance = None

    broadcaster = EventBroadcaster.__new__(EventBroadcaster)
    broadcaster._redis = mock_redis_client
    broadcaster._channel_name = "test_channel"
    broadcaster._connections = set()
    broadcaster._is_listening = False
    broadcaster._listener_task = None
    broadcaster._listener_healthy = True
    broadcaster._is_degraded = False
    broadcaster._lock = MagicMock()
    broadcaster._pubsub = None
    broadcaster._recovery_in_progress = False
    broadcaster._recovery_attempts = 0
    broadcaster._last_recovery_time = None
    broadcaster._message_buffer = MagicMock()
    broadcaster._circuit_breaker = MagicMock()

    return broadcaster


# =============================================================================
# Broadcast Alert Tests
# =============================================================================


class TestBroadcastAlert:
    """Tests for broadcast_alert method."""

    @pytest.mark.asyncio
    async def test_broadcast_alert_created(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting an alert created event."""
        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
        )

        assert subscriber_count == 2
        broadcaster._redis.publish.assert_called_once()

        # Verify message format
        call_args = broadcaster._redis.publish.call_args
        channel, message = call_args[0]
        assert channel == "test_channel"
        assert message["type"] == "alert_created"
        assert message["data"]["id"] == valid_alert_data["id"]
        assert message["data"]["event_id"] == valid_alert_data["event_id"]

    @pytest.mark.asyncio
    async def test_broadcast_alert_acknowledged(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting an alert acknowledged event."""
        valid_alert_data["status"] = "acknowledged"

        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_ACKNOWLEDGED
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "alert_acknowledged"
        assert message["data"]["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_broadcast_alert_updated(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting an alert updated event (NEM-2294)."""
        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_UPDATED
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "alert_updated"
        assert message["data"]["id"] == valid_alert_data["id"]

    @pytest.mark.asyncio
    async def test_broadcast_alert_resolved(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting an alert resolved event (NEM-2294)."""
        valid_alert_data["status"] = "dismissed"

        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_RESOLVED
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "alert_resolved"
        assert message["data"]["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_broadcast_alert_without_rule_id(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting an alert without a rule_id."""
        valid_alert_data["rule_id"] = None

        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["data"]["rule_id"] is None

    @pytest.mark.asyncio
    async def test_broadcast_alert_missing_required_field_raises_error(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that missing required fields raise ValueError."""
        del valid_alert_data["id"]

        with pytest.raises(ValueError) as exc_info:
            await broadcaster.broadcast_alert(
                valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
            )

        assert "Invalid alert message format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_alert_invalid_severity_raises_error(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that invalid severity raises ValueError."""
        valid_alert_data["severity"] = "invalid_severity"

        with pytest.raises(ValueError) as exc_info:
            await broadcaster.broadcast_alert(
                valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
            )

        assert "Invalid alert message format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_alert_invalid_status_raises_error(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that invalid status raises ValueError."""
        valid_alert_data["status"] = "invalid_status"

        with pytest.raises(ValueError) as exc_info:
            await broadcaster.broadcast_alert(
                valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
            )

        assert "Invalid alert message format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_alert_all_severity_levels(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting alerts with all severity levels."""
        for severity in ["low", "medium", "high", "critical"]:
            valid_alert_data["severity"] = severity

            subscriber_count = await broadcaster.broadcast_alert(
                valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
            )

            assert subscriber_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_alert_all_status_values(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting alerts with all status values."""
        for status in ["pending", "delivered", "acknowledged", "dismissed"]:
            valid_alert_data["status"] = status

            subscriber_count = await broadcaster.broadcast_alert(
                valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
            )

            assert subscriber_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_alert_redis_error_propagates(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that Redis errors are propagated."""
        broadcaster._redis.publish = AsyncMock(side_effect=Exception("Redis error"))

        with pytest.raises(Exception) as exc_info:
            await broadcaster.broadcast_alert(
                valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
            )

        assert "Redis error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_alert_returns_subscriber_count(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that broadcast_alert returns the subscriber count."""
        broadcaster._redis.publish = AsyncMock(return_value=5)

        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
        )

        assert subscriber_count == 5

    @pytest.mark.asyncio
    async def test_broadcast_alert_zero_subscribers(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test broadcasting when no subscribers are connected."""
        broadcaster._redis.publish = AsyncMock(return_value=0)

        subscriber_count = await broadcaster.broadcast_alert(
            valid_alert_data, WebSocketAlertEventType.ALERT_CREATED
        )

        assert subscriber_count == 0


class TestBroadcastAlertMessageFormat:
    """Tests for broadcast_alert message format validation."""

    @pytest.mark.asyncio
    async def test_message_has_correct_type_field(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that the broadcast message has the correct type field."""
        await broadcaster.broadcast_alert(valid_alert_data, WebSocketAlertEventType.ALERT_CREATED)

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]

        assert "type" in message
        assert message["type"] == "alert_created"

    @pytest.mark.asyncio
    async def test_message_has_data_field(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that the broadcast message has a data field."""
        await broadcaster.broadcast_alert(valid_alert_data, WebSocketAlertEventType.ALERT_CREATED)

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]

        assert "data" in message
        assert isinstance(message["data"], dict)

    @pytest.mark.asyncio
    async def test_data_field_contains_all_alert_fields(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that the data field contains all expected alert fields."""
        await broadcaster.broadcast_alert(valid_alert_data, WebSocketAlertEventType.ALERT_CREATED)

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        data = message["data"]

        expected_fields = [
            "id",
            "event_id",
            "rule_id",
            "severity",
            "status",
            "dedup_key",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_severity_is_lowercase_string(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that severity is serialized as lowercase string."""
        valid_alert_data["severity"] = "HIGH"  # Uppercase input

        await broadcaster.broadcast_alert(valid_alert_data, WebSocketAlertEventType.ALERT_CREATED)

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]

        assert message["data"]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_status_is_lowercase_string(
        self, broadcaster: EventBroadcaster, valid_alert_data: dict[str, Any]
    ) -> None:
        """Test that status is serialized as lowercase string."""
        valid_alert_data["status"] = "PENDING"  # Uppercase input

        await broadcaster.broadcast_alert(valid_alert_data, WebSocketAlertEventType.ALERT_CREATED)

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]

        assert message["data"]["status"] == "pending"
