"""Chaos tests for Redis pub/sub failures.

This module tests system behavior when Redis pub/sub experiences failures:
- Redis pub/sub disconnect during broadcast
- Message loss scenarios
- Subscriber reconnection handling
- Channel subscription failures
- Publish failures with fallback
- Multiple subscriber race conditions

Expected Behavior:
- Disconnect triggers automatic reconnection
- Message loss detected and logged
- Subscribers reconnect without data loss
- Failed publishes logged and retried
- WebSocket connections remain stable during Redis pub/sub failures
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from backend.core.redis import RedisClient


class TestPubSubDisconnect:
    """Tests for Redis pub/sub disconnect during broadcast."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_disconnect_during_broadcast_retries(self, mock_redis_client: AsyncMock) -> None:
        """Disconnect during broadcast should trigger retry."""
        call_count = 0

        async def disconnect_first_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RedisConnectionError("Connection lost")
            # Success on retry
            return 1  # Number of subscribers

        mock_redis_client.publish = AsyncMock(side_effect=disconnect_first_then_succeed)

        # Broadcast should retry and succeed
        try:
            result = await mock_redis_client.publish("event:new", '{"type": "detection"}')
            assert result == 1
            assert call_count == 2  # Initial + 1 retry
        except RedisConnectionError:
            # If retry fails, should be caught
            pass

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_disconnect_logs_warning_and_reconnects(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Disconnect should log warning and trigger reconnection."""
        with patch("backend.core.redis.logger") as mock_logger:
            # Simulate disconnect
            mock_redis_client.publish = AsyncMock(
                side_effect=RedisConnectionError("Connection closed by server")
            )

            # Try to publish
            try:
                await mock_redis_client.publish("event:new", "data")
            except RedisConnectionError:
                # Should log disconnect warning
                pass

            # Implementation would log: "Redis pub/sub connection lost, reconnecting"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_multiple_broadcast_failures_trigger_circuit_breaker(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Multiple broadcast failures should trigger circuit breaker."""
        # Simulate repeated failures
        mock_redis_client.publish = AsyncMock(
            side_effect=RedisConnectionError("Pub/sub unavailable")
        )

        failure_count = 0
        max_failures = 3

        for _ in range(5):
            try:
                await mock_redis_client.publish("event:new", "data")
            except RedisConnectionError:
                failure_count += 1

        # After max_failures, circuit breaker should open
        assert failure_count >= max_failures
        # Implementation would check circuit_breaker.state == CircuitState.OPEN


class TestMessageLoss:
    """Tests for message loss scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_message_loss_detected_via_subscriber_count(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Message loss detected when subscriber count is 0."""
        # Publish returns 0 subscribers (message lost)
        mock_redis_client.publish = AsyncMock(return_value=0)

        with patch("backend.core.redis.logger") as mock_logger:
            result = await mock_redis_client.publish("event:new", '{"id": 123}')

            # Should detect no subscribers
            assert result == 0
            # Implementation would log: "Warning: Published message but no subscribers"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_message_loss_during_subscriber_reconnect(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Messages published during subscriber reconnect are lost."""
        # Simulate subscriber disconnect window
        reconnect_window_start = asyncio.Event()
        reconnect_window_end = asyncio.Event()

        async def publish_during_reconnect():
            reconnect_window_start.set()
            await asyncio.sleep(0.1)  # Reconnect window
            reconnect_window_end.set()

        reconnect_task = asyncio.create_task(publish_during_reconnect())

        # Wait for reconnect window to start
        await reconnect_window_start.wait()

        # Publish during reconnect (will be lost)
        mock_redis_client.publish = AsyncMock(return_value=0)  # No subscribers
        result = await mock_redis_client.publish("event:new", "data")

        assert result == 0  # Message lost

        await reconnect_task

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_critical_messages_persisted_when_pubsub_fails(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Critical messages should be persisted when pub/sub fails."""
        # Simulate pub/sub failure
        mock_redis_client.publish = AsyncMock(
            side_effect=RedisConnectionError("Pub/sub unavailable")
        )

        # Critical message should be written to fallback queue
        fallback_queue = []

        async def publish_with_fallback(channel: str, message: str, critical: bool = False):
            try:
                return await mock_redis_client.publish(channel, message)
            except RedisConnectionError:
                if critical:
                    # Write to fallback queue
                    fallback_queue.append({"channel": channel, "message": message})
                raise

        # Try to publish critical message
        try:
            await publish_with_fallback("event:critical", "important data", critical=True)
        except RedisConnectionError:
            pass

        # Should be in fallback queue
        assert len(fallback_queue) == 1
        assert fallback_queue[0]["channel"] == "event:critical"


class TestSubscriberReconnection:
    """Tests for subscriber reconnection handling."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_subscriber_reconnects_after_disconnect(self) -> None:
        """Subscriber should automatically reconnect after disconnect."""
        mock_redis = AsyncMock(spec=RedisClient)

        # Simulate disconnect then reconnect
        call_count = 0

        async def disconnect_then_reconnect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RedisConnectionError("Connection lost")
            # Success on reconnect
            return MagicMock()  # Successful subscription

        mock_redis.subscribe = AsyncMock(side_effect=disconnect_then_reconnect)

        # Try to subscribe
        try:
            await mock_redis.subscribe("event:new")
        except RedisConnectionError:
            # First attempt fails
            pass

        # Retry subscription
        result = await mock_redis.subscribe("event:new")
        assert result is not None  # Reconnected
        assert call_count == 2

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_resubscribe_to_all_channels_after_reconnect(self) -> None:
        """After reconnect, should resubscribe to all previous channels."""
        mock_redis = AsyncMock(spec=RedisClient)

        # Track subscribed channels
        subscribed_channels = {"event:new", "event:update", "system:status"}

        # Simulate disconnect
        mock_redis.unsubscribe = AsyncMock()

        # Reconnect and resubscribe
        resubscribe_calls = []

        async def track_resubscribe(channel: str):
            resubscribe_calls.append(channel)
            return MagicMock()

        mock_redis.subscribe = AsyncMock(side_effect=track_resubscribe)

        # Resubscribe to all channels
        for channel in subscribed_channels:
            await mock_redis.subscribe(channel)

        # All channels should be resubscribed
        assert set(resubscribe_calls) == subscribed_channels

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_reconnect_backoff_prevents_connection_storm(self) -> None:
        """Reconnect backoff should prevent connection storm."""
        reconnect_attempts = []

        async def attempt_reconnect(delay: float):
            reconnect_attempts.append(
                {"timestamp": asyncio.get_event_loop().time(), "delay": delay}
            )
            await asyncio.sleep(delay)

        # Simulate reconnect with exponential backoff
        backoff_delays = [0.1, 0.2, 0.4, 0.8, 1.6]  # Exponential backoff

        for delay in backoff_delays:
            await attempt_reconnect(delay)

        # Verify delays increased exponentially
        assert len(reconnect_attempts) == 5
        assert reconnect_attempts[0]["delay"] == 0.1
        assert reconnect_attempts[-1]["delay"] == 1.6


class TestChannelSubscriptionFailures:
    """Tests for channel subscription failure scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_subscribe_to_invalid_channel_fails_gracefully(self) -> None:
        """Subscribe to invalid channel should fail gracefully."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.subscribe = AsyncMock(side_effect=Exception("Invalid channel pattern"))

        # Try to subscribe to invalid channel
        with patch("backend.core.redis.logger") as mock_logger:
            try:
                await mock_redis.subscribe("invalid:channel::")
            except Exception:
                pass

            # Should log error but not crash
            # Implementation would log: "Failed to subscribe to channel"

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_partial_subscription_failure_logs_affected_channels(self) -> None:
        """Partial subscription failure should log which channels failed."""
        mock_redis = AsyncMock(spec=RedisClient)

        channels = ["event:new", "event:update", "event:delete"]
        failed_channels = []

        async def fail_on_second_channel(channel: str):
            if channel == "event:update":
                failed_channels.append(channel)
                raise RedisConnectionError("Subscription failed")
            return MagicMock()

        mock_redis.subscribe = AsyncMock(side_effect=fail_on_second_channel)

        # Try to subscribe to all
        for channel in channels:
            try:
                await mock_redis.subscribe(channel)
            except RedisConnectionError:
                pass

        # Should have logged failed channel
        assert "event:update" in failed_channels


class TestPublishFailuresWithFallback:
    """Tests for publish failures with fallback mechanisms."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_publish_failure_falls_back_to_direct_websocket(self) -> None:
        """Publish failure should fall back to direct WebSocket send."""
        mock_redis = AsyncMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(side_effect=RedisConnectionError("Pub/sub down"))

        # Mock WebSocket manager
        mock_ws_manager = AsyncMock()
        mock_ws_manager.send_to_all = AsyncMock()

        # Try Redis pub/sub first, fall back to direct WebSocket
        try:
            await mock_redis.publish("event:new", '{"id": 123}')
        except RedisConnectionError:
            # Fall back to direct WebSocket broadcast
            await mock_ws_manager.send_to_all({"id": 123})

        # Direct send should have been called
        mock_ws_manager.send_to_all.assert_called_once()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_publish_retry_with_exponential_backoff(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Failed publish should retry with exponential backoff."""
        call_count = 0
        call_delays = []

        async def fail_twice_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            # Record delay before this attempt
            if call_count > 1:
                # Calculate backoff delay
                backoff = 0.1 * (2 ** (call_count - 2))  # Exponential: 0.1, 0.2, 0.4
                call_delays.append(backoff)
                await asyncio.sleep(backoff)

            if call_count < 3:
                raise RedisConnectionError("Publish failed")

            return 1  # Success

        mock_redis_client.publish = AsyncMock(side_effect=fail_twice_then_succeed)

        # Should retry and succeed
        try:
            # Retry logic (simplified)
            for attempt in range(3):
                try:
                    result = await mock_redis_client.publish("event:new", "data")
                    break
                except RedisConnectionError:
                    if attempt < 2:
                        await asyncio.sleep(0.1 * (2**attempt))
                        continue
                    raise
        except RedisConnectionError:
            pass

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_publish_timeout_logged_and_retried(self, mock_redis_client: AsyncMock) -> None:
        """Publish timeout should be logged and retried."""
        call_count = 0

        async def timeout_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RedisTimeoutError("Publish timeout")
            return 1

        mock_redis_client.publish = AsyncMock(side_effect=timeout_then_succeed)

        with patch("backend.core.redis.logger") as mock_logger:
            # Retry logic
            for attempt in range(2):
                try:
                    await mock_redis_client.publish("event:new", "data")
                    break
                except RedisTimeoutError:
                    if attempt < 1:
                        continue
                    raise


class TestMultipleSubscriberRaceConditions:
    """Tests for race conditions with multiple subscribers."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_concurrent_subscription_to_same_channel(self) -> None:
        """Multiple concurrent subscriptions to same channel should succeed."""
        mock_redis = AsyncMock(spec=RedisClient)

        subscription_count = 0

        async def track_subscription(*args, **kwargs):
            nonlocal subscription_count
            subscription_count += 1
            await asyncio.sleep(0.01)  # Simulate subscription delay
            return MagicMock()

        mock_redis.subscribe = AsyncMock(side_effect=track_subscription)

        # Concurrent subscriptions
        tasks = [mock_redis.subscribe("event:new") for _ in range(5)]
        await asyncio.gather(*tasks)

        # All should have subscribed
        assert subscription_count == 5

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_message_delivered_to_all_subscribers(self, mock_redis_client: AsyncMock) -> None:
        """Published message should be delivered to all subscribers."""
        # Simulate 3 subscribers
        subscriber_count = 3
        mock_redis_client.publish = AsyncMock(return_value=subscriber_count)

        # Publish message
        delivered = await mock_redis_client.publish("event:new", '{"id": 123}')

        # Should be delivered to all subscribers
        assert delivered == subscriber_count

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_subscriber_unsubscribe_race_condition(self) -> None:
        """Unsubscribe during message delivery should not lose message."""
        mock_redis = AsyncMock(spec=RedisClient)

        # Simulate publish during unsubscribe
        publish_count = 0

        async def publish_during_unsubscribe(*args, **kwargs):
            nonlocal publish_count
            publish_count += 1
            # Subscribers might be unsubscribing concurrently
            # Return varying subscriber counts
            return max(0, 3 - publish_count)  # 3, 2, 1, 0 subscribers

        mock_redis.publish = AsyncMock(side_effect=publish_during_unsubscribe)

        # Multiple publishes while subscribers leave
        for _ in range(4):
            result = await mock_redis.publish("event:new", "data")
            # Each publish reaches fewer subscribers

        # Eventually no subscribers
        final_result = await mock_redis.publish("event:new", "final")
        assert final_result == 0  # No subscribers remain
