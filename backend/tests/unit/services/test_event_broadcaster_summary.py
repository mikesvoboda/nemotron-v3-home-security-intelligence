"""Unit tests for EventBroadcaster.broadcast_summary_update method (NEM-2893).

Tests cover:
- Broadcasting summary updates with both hourly and daily summaries
- Broadcasting summary updates with only hourly summary
- Broadcasting summary updates with only daily summary
- Validation error handling for invalid summary data
- Empty summary handling (both null)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.event_broadcaster import EventBroadcaster

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_hourly_summary() -> dict[str, Any]:
    """Create valid hourly summary data for testing."""
    return {
        "id": 1,
        "content": (
            "Over the past hour, one critical event occurred at 2:15 PM "
            "when an unrecognized person approached the front door."
        ),
        "event_count": 1,
        "window_start": "2026-01-18T14:00:00Z",
        "window_end": "2026-01-18T15:00:00Z",
        "generated_at": "2026-01-18T14:55:00Z",
    }


@pytest.fixture
def valid_daily_summary() -> dict[str, Any]:
    """Create valid daily summary data for testing."""
    return {
        "id": 2,
        "content": (
            "Today has seen minimal high-priority activity. "
            "The only notable event was at 2:15 PM at the front door. "
            "Morning and evening periods have been quiet with routine traffic only."
        ),
        "event_count": 1,
        "window_start": "2026-01-18T00:00:00Z",
        "window_end": "2026-01-18T15:00:00Z",
        "generated_at": "2026-01-18T14:55:00Z",
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
    broadcaster = EventBroadcaster.__new__(EventBroadcaster)
    broadcaster._redis = mock_redis_client
    broadcaster._channel_name = "test_channel"
    broadcaster._connections = set()
    broadcaster._is_listening = False
    broadcaster._listener_task = None
    broadcaster._listener_healthy = True
    broadcaster._is_degraded = False
    broadcaster._pubsub = None
    broadcaster._recovery_attempts = 0
    broadcaster._message_buffer = MagicMock()
    broadcaster._circuit_breaker = MagicMock()

    return broadcaster


# =============================================================================
# Broadcast Summary Update Tests
# =============================================================================


class TestBroadcastSummaryUpdate:
    """Tests for broadcast_summary_update method."""

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_with_both(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
        valid_daily_summary: dict[str, Any],
    ) -> None:
        """Test broadcasting summary update with both hourly and daily summaries."""
        subscriber_count = await broadcaster.broadcast_summary_update(
            hourly=valid_hourly_summary,
            daily=valid_daily_summary,
        )

        assert subscriber_count == 2
        broadcaster._redis.publish.assert_called_once()

        # Verify message format
        call_args = broadcaster._redis.publish.call_args
        channel, message = call_args[0]
        assert channel == "test_channel"
        assert message["type"] == "summary_update"
        assert message["data"]["hourly"]["id"] == valid_hourly_summary["id"]
        assert message["data"]["hourly"]["content"] == valid_hourly_summary["content"]
        assert message["data"]["hourly"]["event_count"] == valid_hourly_summary["event_count"]
        assert message["data"]["daily"]["id"] == valid_daily_summary["id"]
        assert message["data"]["daily"]["content"] == valid_daily_summary["content"]

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_with_only_hourly(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
    ) -> None:
        """Test broadcasting summary update with only hourly summary."""
        subscriber_count = await broadcaster.broadcast_summary_update(
            hourly=valid_hourly_summary,
            daily=None,
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "summary_update"
        assert message["data"]["hourly"]["id"] == valid_hourly_summary["id"]
        assert message["data"]["daily"] is None

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_with_only_daily(
        self,
        broadcaster: EventBroadcaster,
        valid_daily_summary: dict[str, Any],
    ) -> None:
        """Test broadcasting summary update with only daily summary."""
        subscriber_count = await broadcaster.broadcast_summary_update(
            hourly=None,
            daily=valid_daily_summary,
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "summary_update"
        assert message["data"]["hourly"] is None
        assert message["data"]["daily"]["id"] == valid_daily_summary["id"]

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_with_no_summaries(
        self,
        broadcaster: EventBroadcaster,
    ) -> None:
        """Test broadcasting summary update with no summaries (both null)."""
        subscriber_count = await broadcaster.broadcast_summary_update(
            hourly=None,
            daily=None,
        )

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "summary_update"
        assert message["data"]["hourly"] is None
        assert message["data"]["daily"] is None

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_missing_required_field_raises_error(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
    ) -> None:
        """Test that missing required fields raise ValueError."""
        del valid_hourly_summary["content"]

        with pytest.raises(ValueError) as exc_info:
            await broadcaster.broadcast_summary_update(hourly=valid_hourly_summary)

        assert "Invalid hourly summary format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_invalid_event_count_raises_error(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
    ) -> None:
        """Test that negative event_count raises ValueError."""
        valid_hourly_summary["event_count"] = -1

        with pytest.raises(ValueError) as exc_info:
            await broadcaster.broadcast_summary_update(hourly=valid_hourly_summary)

        assert "Invalid hourly summary format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_invalid_daily_raises_error(
        self,
        broadcaster: EventBroadcaster,
        valid_daily_summary: dict[str, Any],
    ) -> None:
        """Test that invalid daily summary raises ValueError."""
        del valid_daily_summary["id"]

        with pytest.raises(ValueError) as exc_info:
            await broadcaster.broadcast_summary_update(daily=valid_daily_summary)

        assert "Invalid daily summary format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_redis_error_raises(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
    ) -> None:
        """Test that Redis errors are propagated."""
        broadcaster._redis.publish = AsyncMock(side_effect=ConnectionError("Redis down"))

        with pytest.raises(ConnectionError):
            await broadcaster.broadcast_summary_update(hourly=valid_hourly_summary)

    @pytest.mark.asyncio
    async def test_broadcast_summary_update_with_zero_event_count(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
    ) -> None:
        """Test broadcasting summary with zero events (all clear message)."""
        valid_hourly_summary["event_count"] = 0
        valid_hourly_summary["content"] = "All clear. No high-priority events in the past hour."

        subscriber_count = await broadcaster.broadcast_summary_update(hourly=valid_hourly_summary)

        assert subscriber_count == 2

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["data"]["hourly"]["event_count"] == 0
        assert "All clear" in message["data"]["hourly"]["content"]


class TestBroadcastSummaryUpdateMessageFormat:
    """Tests for verifying the correct message format."""

    @pytest.mark.asyncio
    async def test_message_contains_all_required_fields(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
        valid_daily_summary: dict[str, Any],
    ) -> None:
        """Test that the broadcast message contains all required fields."""
        await broadcaster.broadcast_summary_update(
            hourly=valid_hourly_summary,
            daily=valid_daily_summary,
        )

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]

        # Verify top-level structure
        assert "type" in message
        assert "data" in message
        assert message["type"] == "summary_update"

        # Verify hourly summary fields
        hourly = message["data"]["hourly"]
        assert "id" in hourly
        assert "content" in hourly
        assert "event_count" in hourly
        assert "window_start" in hourly
        assert "window_end" in hourly
        assert "generated_at" in hourly

        # Verify daily summary fields
        daily = message["data"]["daily"]
        assert "id" in daily
        assert "content" in daily
        assert "event_count" in daily
        assert "window_start" in daily
        assert "window_end" in daily
        assert "generated_at" in daily

    @pytest.mark.asyncio
    async def test_message_type_is_summary_update(
        self,
        broadcaster: EventBroadcaster,
        valid_hourly_summary: dict[str, Any],
    ) -> None:
        """Test that the message type is always 'summary_update'."""
        await broadcaster.broadcast_summary_update(hourly=valid_hourly_summary)

        call_args = broadcaster._redis.publish.call_args
        _, message = call_args[0]
        assert message["type"] == "summary_update"
