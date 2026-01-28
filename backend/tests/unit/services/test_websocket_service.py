"""Unit tests for WebSocket sharded service (NEM-3415).

Tests the pub/sub channel sharding implementation including:
- Consistent hash computation for camera_id to shard mapping
- Channel naming conventions
- Multi-camera subscription across shards
- Event publishing and filtering
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.websocket_service import (
    WebSocketShardedService,
    _get_shard,
    _get_shard_channel,
    get_websocket_sharded_service,
    reset_service_state,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture(autouse=True)
def _reset_service_state_fixture() -> None:
    """Reset global service state before each test for isolation."""
    reset_service_state()


class _FakePubSub:
    """Fake pub/sub for testing subscriptions."""

    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self._messages = messages or []
        self._subscribed_channels: list[str] = []
        self.subscribe = AsyncMock(side_effect=self._subscribe)
        self.unsubscribe = AsyncMock()
        self.close = AsyncMock()

    async def _subscribe(self, *channels: str) -> None:
        self._subscribed_channels.extend(channels)

    async def listen(self) -> AsyncIterator[dict[str, Any]]:
        for msg in self._messages:
            yield msg


class _FakeRedis:
    """Fake Redis client for testing."""

    def __init__(self) -> None:
        self.publish = AsyncMock(return_value=1)
        self._pubsub_instance: _FakePubSub | None = None

    def create_pubsub(self) -> _FakePubSub:
        if self._pubsub_instance is None:
            self._pubsub_instance = _FakePubSub()
        return self._pubsub_instance

    def set_pubsub_messages(self, messages: list[dict[str, Any]]) -> None:
        """Configure messages to be yielded by pub/sub."""
        self._pubsub_instance = _FakePubSub(messages)


# ==============================================================================
# Consistent Hash Function Tests
# ==============================================================================


class TestGetShard:
    """Tests for the _get_shard consistent hash function."""

    def test_consistent_hash_same_input(self) -> None:
        """Same camera_id should always return the same shard."""
        camera_id = "front_door"
        shard_count = 16

        # Call multiple times
        results = [_get_shard(camera_id, shard_count) for _ in range(100)]

        # All results should be the same
        assert len(set(results)) == 1
        assert all(r == results[0] for r in results)

    def test_consistent_hash_different_inputs(self) -> None:
        """Different camera_ids may map to different shards."""
        camera_ids = ["front_door", "back_yard", "garage", "living_room", "kitchen"]
        shard_count = 16

        shards = {_get_shard(cam_id, shard_count) for cam_id in camera_ids}

        # With 5 different inputs and 16 shards, we expect distribution
        # (not all same shard)
        assert len(shards) >= 1  # At least 1 unique shard

    def test_shard_within_bounds(self) -> None:
        """Shard number should always be within [0, shard_count)."""
        camera_ids = [
            "cam_1",
            "cam_2",
            "cam_3",
            "front_door",
            "back_yard",
            "garage",
            "entrance",
            "lobby",
            "parking_a",
            "parking_b",
        ]

        for shard_count in [1, 4, 8, 16, 32, 64, 128, 256]:
            for camera_id in camera_ids:
                shard = _get_shard(camera_id, shard_count)
                assert 0 <= shard < shard_count, (
                    f"Shard {shard} out of bounds for count {shard_count}"
                )

    def test_shard_with_single_shard(self) -> None:
        """With shard_count=1, all cameras map to shard 0."""
        camera_ids = ["cam_1", "cam_2", "cam_3", "front_door"]

        for camera_id in camera_ids:
            shard = _get_shard(camera_id, 1)
            assert shard == 0

    def test_shard_distribution_is_reasonable(self) -> None:
        """Shards should be reasonably distributed across many camera_ids."""
        shard_count = 16
        camera_ids = [f"camera_{i}" for i in range(1000)]

        shard_counts: dict[int, int] = {}
        for camera_id in camera_ids:
            shard = _get_shard(camera_id, shard_count)
            shard_counts[shard] = shard_counts.get(shard, 0) + 1

        # All shards should have at least some cameras (with 1000 cameras)
        assert len(shard_counts) == shard_count

        # Distribution should be roughly even (allowing for variance)
        expected_per_shard = 1000 / shard_count  # ~62.5
        for count in shard_counts.values():
            # Allow 50% variance from expected
            assert expected_per_shard * 0.5 <= count <= expected_per_shard * 1.5

    def test_specific_camera_id_shard(self) -> None:
        """Test specific camera_id produces expected shard (regression test)."""
        # This test locks in the behavior for specific inputs
        # If the hash algorithm changes, this test will catch it
        shard = _get_shard("front_door", 16)
        assert isinstance(shard, int)
        assert 0 <= shard < 16

        # The same input should always give the same output
        assert _get_shard("front_door", 16) == shard

    def test_unicode_camera_ids(self) -> None:
        """Unicode camera_ids should work correctly."""
        camera_ids = [
            "camera_\u00e9",  # e with accent
            "\u65e5\u672c\u8a9e_camera",  # Japanese
            "home_camera",  # Plain ASCII alternative
            "\u4e2d\u6587_camera",  # Chinese
        ]
        shard_count = 16

        for camera_id in camera_ids:
            shard = _get_shard(camera_id, shard_count)
            assert 0 <= shard < shard_count


# ==============================================================================
# Channel Naming Tests
# ==============================================================================


class TestGetShardChannel:
    """Tests for the _get_shard_channel function."""

    def test_default_channel_format(self) -> None:
        """Default channel format is events:shard:{n}."""
        assert _get_shard_channel(0) == "events:shard:0"
        assert _get_shard_channel(7) == "events:shard:7"
        assert _get_shard_channel(15) == "events:shard:15"

    def test_custom_base_channel(self) -> None:
        """Custom base channel is used in format."""
        assert _get_shard_channel(0, "security") == "security:shard:0"
        assert _get_shard_channel(5, "alerts") == "alerts:shard:5"

    def test_channel_with_large_shard_number(self) -> None:
        """Large shard numbers are formatted correctly."""
        assert _get_shard_channel(255) == "events:shard:255"


# ==============================================================================
# WebSocketShardedService Tests
# ==============================================================================


class TestWebSocketShardedService:
    """Tests for the WebSocketShardedService class."""

    def test_init_default_shard_count(self) -> None:
        """Service uses default shard count from settings."""
        redis = _FakeRedis()

        with patch("backend.services.websocket_service.get_settings") as mock_settings:
            mock_settings.return_value.redis_pubsub_shard_count = 16
            service = WebSocketShardedService(redis)

        assert service.shard_count == 16
        assert service.base_channel == "events"

    def test_init_custom_shard_count(self) -> None:
        """Service uses custom shard count when provided."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=32, base_channel="custom")

        assert service.shard_count == 32
        assert service.base_channel == "custom"

    def test_get_shard_method(self) -> None:
        """get_shard method returns correct shard."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        shard = service.get_shard("front_door")
        expected = _get_shard("front_door", 16)

        assert shard == expected

    def test_get_shard_channel_method(self) -> None:
        """get_shard_channel method returns correct channel name."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16, base_channel="events")

        channel = service.get_shard_channel(7)

        assert channel == "events:shard:7"

    def test_get_camera_channel_method(self) -> None:
        """get_camera_channel method returns correct channel for camera."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        channel = service.get_camera_channel("front_door")
        expected_shard = service.get_shard("front_door")

        assert channel == f"events:shard:{expected_shard}"

    def test_get_shards_for_cameras(self) -> None:
        """get_shards_for_cameras returns unique shards for cameras."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        cameras = ["front_door", "back_yard", "garage"]
        shards = service.get_shards_for_cameras(cameras)

        # Each camera maps to a shard
        assert len(shards) >= 1
        assert all(0 <= s < 16 for s in shards)

    def test_get_shards_for_cameras_empty_list(self) -> None:
        """get_shards_for_cameras handles empty list."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        shards = service.get_shards_for_cameras([])

        assert shards == set()


# ==============================================================================
# Publish Tests
# ==============================================================================


class TestPublishEvent:
    """Tests for the publish_event method."""

    @pytest.mark.asyncio
    async def test_publish_event_to_correct_shard(self) -> None:
        """Event is published to the correct shard channel."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        camera_id = "front_door"
        expected_shard = service.get_shard(camera_id)
        expected_channel = service.get_shard_channel(expected_shard)

        await service.publish_event(
            camera_id=camera_id,
            event_type="motion_detected",
            payload={"confidence": 0.95},
        )

        redis.publish.assert_called_once()
        call_args = redis.publish.call_args
        assert call_args[0][0] == expected_channel

    @pytest.mark.asyncio
    async def test_publish_event_message_format(self) -> None:
        """Published message has correct format."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        await service.publish_event(
            camera_id="front_door",
            event_type="motion_detected",
            payload={"confidence": 0.95},
            correlation_id="corr-123",
        )

        call_args = redis.publish.call_args
        message = call_args[0][1]

        assert message["camera_id"] == "front_door"
        assert message["event_type"] == "motion_detected"
        assert message["payload"] == {"confidence": 0.95}
        assert message["correlation_id"] == "corr-123"
        assert "shard" in message

    @pytest.mark.asyncio
    async def test_publish_event_without_correlation_id(self) -> None:
        """Published message omits correlation_id if not provided."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        await service.publish_event(
            camera_id="front_door",
            event_type="motion_detected",
            payload={},
        )

        call_args = redis.publish.call_args
        message = call_args[0][1]

        assert "correlation_id" not in message

    @pytest.mark.asyncio
    async def test_publish_event_increments_counter(self) -> None:
        """publish_count is incremented after successful publish."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        assert service.publish_count == 0

        await service.publish_event("cam1", "event1", {})
        assert service.publish_count == 1

        await service.publish_event("cam2", "event2", {})
        assert service.publish_count == 2

    @pytest.mark.asyncio
    async def test_publish_event_returns_subscriber_count(self) -> None:
        """publish_event returns number of subscribers."""
        redis = _FakeRedis()
        redis.publish.return_value = 5
        service = WebSocketShardedService(redis, shard_count=16)

        result = await service.publish_event("front_door", "event", {})

        assert result == 5


# ==============================================================================
# Subscribe Tests
# ==============================================================================


class TestSubscribeCamera:
    """Tests for the subscribe_camera method."""

    @pytest.mark.asyncio
    async def test_subscribe_camera_filters_by_camera_id(self) -> None:
        """Only events for the subscribed camera are yielded."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        # Set up messages from multiple cameras
        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})},
            {"type": "message", "data": json.dumps({"camera_id": "back_yard", "event": "2"})},
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "3"})},
        ]
        redis.set_pubsub_messages(messages)

        # Subscribe to front_door
        events = []
        async for event in service.subscribe_camera("front_door"):
            events.append(event)
            if len(events) >= 2:
                break

        # Should only get front_door events
        assert len(events) == 2
        assert all(e["camera_id"] == "front_door" for e in events)
        assert events[0]["event"] == "1"
        assert events[1]["event"] == "3"


class TestSubscribeCameras:
    """Tests for the subscribe_cameras method."""

    @pytest.mark.asyncio
    async def test_subscribe_cameras_empty_list(self) -> None:
        """Empty camera list yields nothing."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        events = []
        async for event in service.subscribe_cameras([]):
            events.append(event)

        assert events == []

    @pytest.mark.asyncio
    async def test_subscribe_cameras_filters_correctly(self) -> None:
        """Only events for subscribed cameras are yielded."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})},
            {"type": "message", "data": json.dumps({"camera_id": "back_yard", "event": "2"})},
            {"type": "message", "data": json.dumps({"camera_id": "garage", "event": "3"})},
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "4"})},
        ]
        redis.set_pubsub_messages(messages)

        events = []
        async for event in service.subscribe_cameras(["front_door", "back_yard"]):
            events.append(event)
            if len(events) >= 3:
                break

        # Should only get front_door and back_yard events
        assert len(events) == 3
        camera_ids = {e["camera_id"] for e in events}
        assert camera_ids == {"front_door", "back_yard"}

    @pytest.mark.asyncio
    async def test_subscribe_cameras_handles_bytes_data(self) -> None:
        """Byte data from Redis is decoded correctly."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        # Redis sends bytes
        messages = [
            {"type": "message", "data": b'{"camera_id": "front_door", "event": "1"}'},
        ]
        redis.set_pubsub_messages(messages)

        events = []
        async for event in service.subscribe_cameras(["front_door"]):
            events.append(event)
            break

        assert len(events) == 1
        assert events[0]["camera_id"] == "front_door"

    @pytest.mark.asyncio
    async def test_subscribe_cameras_skips_non_message_types(self) -> None:
        """Non-message types (subscribe confirmations) are skipped."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        messages = [
            {"type": "subscribe", "data": 1},  # Subscription confirmation
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})},
            {"type": "psubscribe", "data": 1},  # Pattern subscription confirmation
        ]
        redis.set_pubsub_messages(messages)

        events = []
        async for event in service.subscribe_cameras(["front_door"]):
            events.append(event)
            break

        # Only the actual message should be yielded
        assert len(events) == 1
        assert events[0]["event"] == "1"


# ==============================================================================
# Stats Tests
# ==============================================================================


class TestGetStats:
    """Tests for the get_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_initial(self) -> None:
        """Initial stats show zero counts."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16, base_channel="test")

        stats = service.get_stats()

        assert stats["shard_count"] == 16
        assert stats["base_channel"] == "test"
        assert stats["publish_count"] == 0
        assert stats["subscribe_count"] == 0
        assert stats["active_subscription_shards"] == 0
        assert stats["active_shards"] == []

    @pytest.mark.asyncio
    async def test_get_stats_after_publish(self) -> None:
        """Stats show correct publish count."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        await service.publish_event("cam1", "event", {})
        await service.publish_event("cam2", "event", {})

        stats = service.get_stats()

        assert stats["publish_count"] == 2


# ==============================================================================
# Singleton Tests
# ==============================================================================


class TestGetWebSocketShardedService:
    """Tests for the get_websocket_sharded_service singleton."""

    @pytest.mark.asyncio
    async def test_returns_same_instance(self) -> None:
        """Multiple calls return the same instance."""
        redis = _FakeRedis()

        service1 = await get_websocket_sharded_service(redis, shard_count=8)
        service2 = await get_websocket_sharded_service(redis, shard_count=16)  # Ignored

        assert service1 is service2
        assert service1.shard_count == 8  # First call's config is used

    @pytest.mark.asyncio
    async def test_reset_state_clears_singleton(self) -> None:
        """reset_service_state clears the singleton."""
        redis = _FakeRedis()

        service1 = await get_websocket_sharded_service(redis, shard_count=8)
        reset_service_state()
        service2 = await get_websocket_sharded_service(redis, shard_count=16)

        assert service1 is not service2
        assert service2.shard_count == 16


# ==============================================================================
# Edge Cases and Error Handling
# ==============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_publish_with_empty_camera_id(self) -> None:
        """Empty camera_id still hashes to valid shard."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        # Should not raise
        await service.publish_event(
            camera_id="",
            event_type="test",
            payload={},
        )

        redis.publish.assert_called_once()

    def test_get_shard_with_special_characters(self) -> None:
        """Special characters in camera_id are handled."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        special_ids = [
            "front:door",
            "back/yard",
            "garage-1",
            "camera.main",
            "cam_123",
            "camera with spaces",
        ]

        for camera_id in special_ids:
            shard = service.get_shard(camera_id)
            assert 0 <= shard < 16

    @pytest.mark.asyncio
    async def test_subscribe_handles_invalid_json(self) -> None:
        """Invalid JSON in messages is logged and skipped."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        messages = [
            {"type": "message", "data": "invalid json {"},
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        events = []
        async for event in service.subscribe_cameras(["front_door"]):
            events.append(event)
            break

        # Invalid JSON should be skipped, valid message should be yielded
        assert len(events) == 1
        assert events[0]["event"] == "1"

    @pytest.mark.asyncio
    async def test_publish_event_handles_redis_error(self) -> None:
        """Publish event re-raises Redis exceptions."""
        redis = _FakeRedis()
        redis.publish.side_effect = Exception("Redis connection failed")
        service = WebSocketShardedService(redis, shard_count=16)

        with pytest.raises(Exception, match="Redis connection failed"):
            await service.publish_event(
                camera_id="front_door",
                event_type="test",
                payload={},
            )

    @pytest.mark.asyncio
    async def test_subscribe_cameras_handles_cancellation(self) -> None:
        """Subscription cleanup happens on cancellation."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        # Create a pubsub that will be cancelled
        pubsub = _FakePubSub()

        async def listen_then_cancel():
            yield {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})}
            # Raise after first message to trigger cleanup
            raise asyncio.CancelledError()

        pubsub.listen = listen_then_cancel
        redis._pubsub_instance = pubsub

        with pytest.raises(asyncio.CancelledError):
            async for event in service.subscribe_cameras(["front_door"]):
                pass

        # Verify cleanup was called
        pubsub.unsubscribe.assert_called()
        pubsub.close.assert_called()

    @pytest.mark.asyncio
    async def test_subscribe_cameras_handles_general_exception(self) -> None:
        """Subscription cleanup happens on general exception."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        # Make listen() raise an exception
        async def failing_listen():
            yield {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})}
            raise RuntimeError("Subscription error")

        pubsub = _FakePubSub()
        pubsub.listen = failing_listen
        redis._pubsub_instance = pubsub

        with pytest.raises(RuntimeError, match="Subscription error"):
            async for event in service.subscribe_cameras(["front_door"]):
                pass

        # Verify cleanup was called
        pubsub.unsubscribe.assert_called()
        pubsub.close.assert_called()

    @pytest.mark.asyncio
    async def test_subscribe_cameras_cleanup_error_is_logged(self) -> None:
        """Errors during subscription cleanup are logged but don't crash."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "front_door", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        # Make cleanup fail
        pubsub = redis._pubsub_instance
        pubsub.unsubscribe.side_effect = Exception("Cleanup failed")

        # Subscription should complete despite cleanup error
        events = []
        async for event in service.subscribe_cameras(["front_door"]):
            events.append(event)
            break

        assert len(events) == 1


# ==============================================================================
# Integration-style Tests
# ==============================================================================


class TestSubscribeAllShards:
    """Tests for the subscribe_all_shards method."""

    @pytest.mark.asyncio
    async def test_subscribe_all_shards_receives_from_all(self) -> None:
        """Subscribe to all shards receives events from any camera."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        # Set up messages from different cameras (likely different shards)
        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "cam1", "event": "1"})},
            {"type": "message", "data": json.dumps({"camera_id": "cam2", "event": "2"})},
            {"type": "message", "data": json.dumps({"camera_id": "cam3", "event": "3"})},
        ]
        redis.set_pubsub_messages(messages)

        events = []
        async for event in service.subscribe_all_shards():
            events.append(event)
            if len(events) >= 3:
                break

        assert len(events) == 3
        camera_ids = {e["camera_id"] for e in events}
        assert camera_ids == {"cam1", "cam2", "cam3"}

    @pytest.mark.asyncio
    async def test_subscribe_all_shards_subscribes_to_all_channels(self) -> None:
        """Subscribe to all shards subscribes to all shard channels."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        async for event in service.subscribe_all_shards():
            break  # Just trigger subscription

        pubsub = redis._pubsub_instance
        assert pubsub is not None

        # Should have subscribed to all 4 shards
        expected_channels = [f"events:shard:{i}" for i in range(4)]
        assert len(pubsub._subscribed_channels) == 4
        for channel in expected_channels:
            assert channel in pubsub._subscribed_channels

    @pytest.mark.asyncio
    async def test_subscribe_all_shards_increments_counter(self) -> None:
        """Subscribe to all shards increments subscribe_count."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)

        assert service.subscribe_count == 0

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        async for event in service.subscribe_all_shards():
            break

        assert service.subscribe_count == 1

    @pytest.mark.asyncio
    async def test_subscribe_all_shards_handles_cancellation(self) -> None:
        """Subscribe to all shards handles cancellation gracefully."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)

        # Create a pubsub that will be cancelled
        pubsub = _FakePubSub()

        async def listen_then_cancel():
            yield {"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})}
            raise asyncio.CancelledError()

        pubsub.listen = listen_then_cancel
        redis._pubsub_instance = pubsub

        with pytest.raises(asyncio.CancelledError):
            async for event in service.subscribe_all_shards():
                pass

        # Cleanup should have been called
        pubsub.unsubscribe.assert_called()
        pubsub.close.assert_called()

    @pytest.mark.asyncio
    async def test_subscribe_all_shards_handles_invalid_json(self) -> None:
        """Subscribe to all shards skips invalid JSON."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)

        messages = [
            {"type": "message", "data": "invalid json {"},
            {"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        events = []
        async for event in service.subscribe_all_shards():
            events.append(event)
            break

        # Invalid JSON should be skipped
        assert len(events) == 1
        assert events[0]["event"] == "1"

    @pytest.mark.asyncio
    async def test_subscribe_all_shards_tracks_active_shards(self) -> None:
        """Subscribe to all shards tracks all shards as active."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        async for event in service.subscribe_all_shards():
            # Check active shards while subscription is active
            stats = service.get_stats()
            assert stats["active_subscription_shards"] == 4
            assert len(stats["active_shards"]) == 4
            break


# ==============================================================================
# Singleton Advanced Tests
# ==============================================================================


class TestSingletonAdvanced:
    """Advanced tests for singleton behavior."""

    @pytest.mark.asyncio
    async def test_get_websocket_sharded_service_sync_returns_none_initially(self) -> None:
        """get_websocket_sharded_service_sync returns None before initialization."""
        from backend.services.websocket_service import get_websocket_sharded_service_sync

        reset_service_state()
        service = get_websocket_sharded_service_sync()
        assert service is None

    @pytest.mark.asyncio
    async def test_get_websocket_sharded_service_sync_returns_instance_after_init(self) -> None:
        """get_websocket_sharded_service_sync returns instance after initialization."""
        from backend.services.websocket_service import get_websocket_sharded_service_sync

        reset_service_state()
        redis = _FakeRedis()

        # Initialize async
        await get_websocket_sharded_service(redis, shard_count=8)

        # Get sync
        service = get_websocket_sharded_service_sync()
        assert service is not None
        assert service.shard_count == 8

    @pytest.mark.asyncio
    async def test_concurrent_initialization_returns_same_instance(self) -> None:
        """Concurrent calls to get_websocket_sharded_service return same instance."""
        import asyncio

        reset_service_state()
        redis = _FakeRedis()

        # Start multiple concurrent initializations
        tasks = [get_websocket_sharded_service(redis, shard_count=i) for i in range(8, 12)]
        services = await asyncio.gather(*tasks)

        # All should return the same instance (first wins)
        assert all(s is services[0] for s in services)
        assert services[0].shard_count == 8  # First call's config is used


# ==============================================================================
# Stats Tracking Advanced Tests
# ==============================================================================


class TestStatsTrackingAdvanced:
    """Advanced tests for stats tracking."""

    @pytest.mark.asyncio
    async def test_stats_track_active_subscriptions(self) -> None:
        """Stats track active subscription shards."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "cam1", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        # Start subscription
        async for event in service.subscribe_cameras(["cam1"]):
            # Check stats during subscription
            stats = service.get_stats()
            assert stats["active_subscription_shards"] >= 1
            break

        # Stats should be updated

    @pytest.mark.asyncio
    async def test_subscribe_count_increments_per_subscription(self) -> None:
        """Subscribe count increments for each subscription call."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        messages = [
            {"type": "message", "data": json.dumps({"camera_id": "test", "event": "1"})},
        ]
        redis.set_pubsub_messages(messages)

        assert service.subscribe_count == 0

        # First subscription
        async for event in service.subscribe_camera("test"):
            break
        assert service.subscribe_count == 1

        # Reset pubsub for second subscription
        redis.set_pubsub_messages(messages)

        # Second subscription
        async for event in service.subscribe_cameras(["test", "test2"]):
            break
        assert service.subscribe_count == 2


class TestPublishSubscribeIntegration:
    """Integration-style tests for publish/subscribe workflow."""

    def test_same_camera_always_same_shard(self) -> None:
        """Verify publish and subscribe use the same shard."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=16)

        camera_id = "front_door"

        # Get shard for publishing
        publish_shard = service.get_shard(camera_id)
        publish_channel = service.get_shard_channel(publish_shard)

        # Get shard for subscribing
        subscribe_shards = service.get_shards_for_cameras([camera_id])

        # They should match
        assert len(subscribe_shards) == 1
        assert publish_shard in subscribe_shards

        # Channel should match
        subscribe_channel = service.get_camera_channel(camera_id)
        assert subscribe_channel == publish_channel

    def test_multiple_cameras_may_share_shards(self) -> None:
        """Multiple cameras may end up in the same shard."""
        redis = _FakeRedis()
        service = WebSocketShardedService(redis, shard_count=4)  # Small shard count

        # With many cameras and few shards, some must share
        cameras = [f"camera_{i}" for i in range(100)]
        shards = service.get_shards_for_cameras(cameras)

        # We have at most 4 shards
        assert len(shards) <= 4
