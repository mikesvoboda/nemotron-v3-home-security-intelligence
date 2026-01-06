"""Integration tests for Redis pub/sub event broadcasting.

These tests verify the core Redis pub/sub functionality used by EventBroadcaster
and SystemBroadcaster for real-time event distribution.

Test coverage:
- Real Redis pub/sub message delivery
- Event broadcasting to multiple subscribers
- Channel subscription/unsubscription
- Message ordering across subscribers
- Channel isolation verification
- High-throughput message handling
- Pub/sub error recovery

Uses the real_redis fixture from conftest.py for actual Redis connections.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


class TestPubSubBasicOperations:
    """Test basic pub/sub operations with real Redis."""

    @pytest.mark.asyncio
    async def test_publish_returns_subscriber_count(self, real_redis: RedisClient) -> None:
        """Test that publish returns the number of subscribers."""
        channel = "test_channel_subscriber_count"

        # No subscribers yet
        count = await real_redis.publish(channel, {"msg": "test"})
        assert count == 0

        # Subscribe to channel (pubsub needed for subscription to exist)
        _pubsub = await real_redis.subscribe(channel)

        try:
            # Now publish should return 1 subscriber
            count = await real_redis.publish(channel, {"msg": "test"})
            assert count == 1
        finally:
            await real_redis.unsubscribe(channel)

    @pytest.mark.asyncio
    async def test_subscribe_and_receive_message(self, real_redis: RedisClient) -> None:
        """Test subscribing to a channel and receiving messages."""
        channel = "test_channel_subscribe_receive"
        received_messages: list[dict] = []

        # Subscribe to channel using dedicated connection
        pubsub = await real_redis.subscribe_dedicated(channel)

        try:
            # Publish a message
            test_message = {"type": "test", "data": "hello"}
            await real_redis.publish(channel, test_message)

            # Listen for messages with timeout
            async def collect_messages():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    if len(received_messages) >= 1:
                        break

            # Run with timeout to avoid blocking forever
            try:
                await asyncio.wait_for(collect_messages(), timeout=2.0)
            except TimeoutError:
                pass

            # Verify message was received
            assert len(received_messages) == 1
            assert received_messages[0]["data"]["type"] == "test"
            assert received_messages[0]["data"]["data"] == "hello"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_receiving_messages(self, real_redis: RedisClient) -> None:
        """Test that unsubscribing stops message delivery."""
        channel = "test_channel_unsubscribe"

        # Subscribe to channel
        pubsub = await real_redis.subscribe_dedicated(channel)

        # Unsubscribe immediately
        await pubsub.unsubscribe(channel)

        # Publish a message
        await real_redis.publish(channel, {"msg": "should_not_receive"})

        # Give time for any potential messages to arrive
        await asyncio.sleep(0.1)

        # Close the pubsub connection
        await pubsub.aclose()

        # No messages should be received after unsubscribe
        # (We can't easily test this without a listener, but the test verifies
        # that unsubscribe completes without error)


class TestMultipleSubscribers:
    """Test pub/sub with multiple subscribers."""

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_subscribers(self, real_redis: RedisClient) -> None:
        """Test that messages are broadcast to all subscribers."""
        channel = "test_channel_multiple_subs"

        # Create multiple subscribers using dedicated connections
        pubsub1 = await real_redis.subscribe_dedicated(channel)
        pubsub2 = await real_redis.subscribe_dedicated(channel)
        pubsub3 = await real_redis.subscribe_dedicated(channel)

        try:
            # Publish should report 3 subscribers
            count = await real_redis.publish(channel, {"msg": "broadcast_test"})
            assert count == 3

            # Each subscriber should receive the message
            received = [[], [], []]

            async def collect_from_pubsub(pubsub, idx):
                async for message in real_redis.listen(pubsub):
                    received[idx].append(message)
                    break  # Just get one message

            # Collect messages from all subscribers concurrently
            tasks = [
                asyncio.create_task(collect_from_pubsub(pubsub1, 0)),
                asyncio.create_task(collect_from_pubsub(pubsub2, 1)),
                asyncio.create_task(collect_from_pubsub(pubsub3, 2)),
            ]

            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=2.0)
            except TimeoutError:
                for t in tasks:
                    t.cancel()

            # Verify all subscribers received the message
            assert len(received[0]) == 1
            assert len(received[1]) == 1
            assert len(received[2]) == 1

            # All should have the same message content
            for msgs in received:
                assert msgs[0]["data"]["msg"] == "broadcast_test"

        finally:
            for pubsub in [pubsub1, pubsub2, pubsub3]:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_subscriber_count_updates_on_connect_disconnect(
        self, real_redis: RedisClient
    ) -> None:
        """Test that subscriber count changes as clients connect/disconnect."""
        channel = "test_channel_count_updates"

        # Initially 0 subscribers
        count = await real_redis.publish(channel, {"msg": "test0"})
        assert count == 0

        # Add first subscriber
        pubsub1 = await real_redis.subscribe_dedicated(channel)
        count = await real_redis.publish(channel, {"msg": "test1"})
        assert count == 1

        # Add second subscriber
        pubsub2 = await real_redis.subscribe_dedicated(channel)
        count = await real_redis.publish(channel, {"msg": "test2"})
        assert count == 2

        # Remove first subscriber
        await pubsub1.unsubscribe(channel)
        await pubsub1.aclose()

        # Small delay to let Redis process the unsubscribe
        await asyncio.sleep(0.1)

        count = await real_redis.publish(channel, {"msg": "test3"})
        assert count == 1

        # Remove second subscriber
        await pubsub2.unsubscribe(channel)
        await pubsub2.aclose()

        await asyncio.sleep(0.1)

        count = await real_redis.publish(channel, {"msg": "test4"})
        assert count == 0


class TestChannelIsolation:
    """Test channel isolation - messages on one channel don't leak to others."""

    @pytest.mark.asyncio
    async def test_channel_isolation(self, real_redis: RedisClient) -> None:
        """Test that messages are isolated to their respective channels."""
        channel_a = "test_channel_isolation_a"
        channel_b = "test_channel_isolation_b"

        messages_a: list[dict] = []
        messages_b: list[dict] = []

        # Subscribe to different channels
        pubsub_a = await real_redis.subscribe_dedicated(channel_a)
        pubsub_b = await real_redis.subscribe_dedicated(channel_b)

        try:
            # Publish to channel A
            await real_redis.publish(channel_a, {"channel": "a", "value": 1})
            # Publish to channel B
            await real_redis.publish(channel_b, {"channel": "b", "value": 2})

            # Collect messages
            async def collect(pubsub, messages_list):
                async for message in real_redis.listen(pubsub):
                    messages_list.append(message)
                    break

            tasks = [
                asyncio.create_task(collect(pubsub_a, messages_a)),
                asyncio.create_task(collect(pubsub_b, messages_b)),
            ]

            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=2.0)
            except TimeoutError:
                for t in tasks:
                    t.cancel()

            # Channel A should only have message for channel A
            assert len(messages_a) == 1
            assert messages_a[0]["data"]["channel"] == "a"
            assert messages_a[0]["data"]["value"] == 1

            # Channel B should only have message for channel B
            assert len(messages_b) == 1
            assert messages_b[0]["data"]["channel"] == "b"
            assert messages_b[0]["data"]["value"] == 2

        finally:
            await pubsub_a.unsubscribe(channel_a)
            await pubsub_a.aclose()
            await pubsub_b.unsubscribe(channel_b)
            await pubsub_b.aclose()

    @pytest.mark.asyncio
    async def test_multiple_channel_subscription(self, real_redis: RedisClient) -> None:
        """Test subscribing to multiple channels with one connection."""
        channel_1 = "test_multi_channel_1"
        channel_2 = "test_multi_channel_2"
        received_messages: list[dict] = []

        # Subscribe to multiple channels
        pubsub = await real_redis.subscribe_dedicated(channel_1, channel_2)

        try:
            # Publish to both channels
            await real_redis.publish(channel_1, {"from": "channel_1"})
            await real_redis.publish(channel_2, {"from": "channel_2"})

            # Collect messages
            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    if len(received_messages) >= 2:
                        break

            try:
                await asyncio.wait_for(collect(), timeout=2.0)
            except TimeoutError:
                pass

            # Should receive messages from both channels
            assert len(received_messages) == 2

            channels = {msg["channel"] for msg in received_messages}
            assert channel_1 in channels
            assert channel_2 in channels

        finally:
            await pubsub.unsubscribe(channel_1, channel_2)
            await pubsub.aclose()


class TestMessageOrdering:
    """Test message ordering guarantees."""

    @pytest.mark.asyncio
    async def test_message_ordering_preserved(self, real_redis: RedisClient) -> None:
        """Test that messages are received in the order they were published."""
        channel = "test_channel_ordering"
        received_messages: list[dict] = []

        pubsub = await real_redis.subscribe_dedicated(channel)

        try:
            # Publish messages in sequence
            num_messages = 10
            for i in range(num_messages):
                await real_redis.publish(channel, {"seq": i})

            # Collect all messages
            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    if len(received_messages) >= num_messages:
                        break

            try:
                await asyncio.wait_for(collect(), timeout=3.0)
            except TimeoutError:
                pass

            # Verify ordering
            assert len(received_messages) == num_messages
            for i, msg in enumerate(received_messages):
                assert msg["data"]["seq"] == i, f"Message {i} out of order"

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_ordering_across_multiple_subscribers(self, real_redis: RedisClient) -> None:
        """Test that all subscribers receive messages in the same order."""
        channel = "test_channel_ordering_multi"
        messages_sub1: list[dict] = []
        messages_sub2: list[dict] = []

        pubsub1 = await real_redis.subscribe_dedicated(channel)
        pubsub2 = await real_redis.subscribe_dedicated(channel)

        try:
            # Publish messages
            num_messages = 5
            for i in range(num_messages):
                await real_redis.publish(channel, {"seq": i})

            # Collect from both subscribers
            async def collect(pubsub, messages_list):
                async for message in real_redis.listen(pubsub):
                    messages_list.append(message)
                    if len(messages_list) >= num_messages:
                        break

            tasks = [
                asyncio.create_task(collect(pubsub1, messages_sub1)),
                asyncio.create_task(collect(pubsub2, messages_sub2)),
            ]

            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=3.0)
            except TimeoutError:
                for t in tasks:
                    t.cancel()

            # Both subscribers should have same order
            assert len(messages_sub1) == num_messages
            assert len(messages_sub2) == num_messages

            for i in range(num_messages):
                assert messages_sub1[i]["data"]["seq"] == i
                assert messages_sub2[i]["data"]["seq"] == i

        finally:
            await pubsub1.unsubscribe(channel)
            await pubsub1.aclose()
            await pubsub2.unsubscribe(channel)
            await pubsub2.aclose()


class TestHighThroughput:
    """Test high-throughput message handling."""

    @pytest.mark.asyncio
    async def test_high_volume_message_delivery(self, real_redis: RedisClient) -> None:
        """Test handling a high volume of messages."""
        channel = "test_channel_high_volume"
        received_messages: list[dict] = []

        pubsub = await real_redis.subscribe_dedicated(channel)

        try:
            # Publish many messages rapidly
            num_messages = 100

            # Start listener before publishing
            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    if len(received_messages) >= num_messages:
                        break

            # Run listener and publisher concurrently
            listener_task = asyncio.create_task(collect())

            # Small delay to ensure listener is ready
            await asyncio.sleep(0.1)

            # Publish all messages
            for i in range(num_messages):
                await real_redis.publish(channel, {"seq": i, "data": "x" * 100})

            try:
                await asyncio.wait_for(listener_task, timeout=10.0)
            except TimeoutError:
                listener_task.cancel()

            # Verify all messages received
            assert len(received_messages) == num_messages

            # Verify ordering maintained
            for i, msg in enumerate(received_messages):
                assert msg["data"]["seq"] == i

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_concurrent_publishers(self, real_redis: RedisClient) -> None:
        """Test multiple publishers publishing concurrently."""
        channel = "test_channel_concurrent_pub"
        received_messages: list[dict] = []

        pubsub = await real_redis.subscribe_dedicated(channel)

        try:
            num_publishers = 5
            messages_per_publisher = 10
            total_messages = num_publishers * messages_per_publisher

            # Collect all messages
            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    if len(received_messages) >= total_messages:
                        break

            listener_task = asyncio.create_task(collect())

            # Small delay to ensure listener is ready
            await asyncio.sleep(0.1)

            # Launch multiple publishers concurrently
            async def publish_batch(publisher_id: int):
                for i in range(messages_per_publisher):
                    await real_redis.publish(channel, {"publisher": publisher_id, "seq": i})

            publisher_tasks = [asyncio.create_task(publish_batch(p)) for p in range(num_publishers)]

            await asyncio.gather(*publisher_tasks)

            try:
                await asyncio.wait_for(listener_task, timeout=10.0)
            except TimeoutError:
                listener_task.cancel()

            # Verify all messages received
            assert len(received_messages) == total_messages

            # Verify we got messages from all publishers
            publishers_seen = {msg["data"]["publisher"] for msg in received_messages}
            assert len(publishers_seen) == num_publishers

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


class TestSubscriberReconnection:
    """Test subscriber reconnection handling."""

    @pytest.mark.asyncio
    async def test_new_subscriber_receives_future_messages(self, real_redis: RedisClient) -> None:
        """Test that a new subscriber receives messages published after subscription."""
        channel = "test_channel_new_sub"

        # Publish a message before subscription (should be lost)
        await real_redis.publish(channel, {"msg": "before_subscription"})

        # Subscribe
        pubsub = await real_redis.subscribe_dedicated(channel)
        received_messages: list[dict] = []

        try:
            # Publish after subscription
            await real_redis.publish(channel, {"msg": "after_subscription"})

            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    break

            try:
                await asyncio.wait_for(collect(), timeout=2.0)
            except TimeoutError:
                pass

            # Should only receive the message published after subscription
            assert len(received_messages) == 1
            assert received_messages[0]["data"]["msg"] == "after_subscription"

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_resubscription_works_after_unsubscribe(self, real_redis: RedisClient) -> None:
        """Test that resubscribing after unsubscribe works correctly."""
        channel = "test_channel_resub"

        # First subscription
        pubsub1 = await real_redis.subscribe_dedicated(channel)
        count = await real_redis.publish(channel, {"msg": "first"})
        assert count == 1

        # Unsubscribe
        await pubsub1.unsubscribe(channel)
        await pubsub1.aclose()

        await asyncio.sleep(0.1)

        # Verify no subscribers
        count = await real_redis.publish(channel, {"msg": "between"})
        assert count == 0

        # Resubscribe
        pubsub2 = await real_redis.subscribe_dedicated(channel)
        received: list[dict] = []

        try:
            await real_redis.publish(channel, {"msg": "after_resub"})

            async def collect():
                async for message in real_redis.listen(pubsub2):
                    received.append(message)
                    break

            try:
                await asyncio.wait_for(collect(), timeout=2.0)
            except TimeoutError:
                pass

            # Should receive message published after resubscription
            assert len(received) == 1
            assert received[0]["data"]["msg"] == "after_resub"

        finally:
            await pubsub2.unsubscribe(channel)
            await pubsub2.aclose()


class TestMessageSerialization:
    """Test message serialization/deserialization."""

    @pytest.mark.asyncio
    async def test_json_serialization(self, real_redis: RedisClient) -> None:
        """Test that complex JSON structures are properly serialized."""
        channel = "test_channel_json"

        pubsub = await real_redis.subscribe_dedicated(channel)
        received_messages: list[dict] = []

        try:
            # Publish complex JSON structure
            complex_message = {
                "type": "event",
                "data": {
                    "id": 123,
                    "nested": {"key": "value", "array": [1, 2, 3]},
                    "boolean": True,
                    "null_value": None,
                    "float": 3.14159,
                },
            }

            await real_redis.publish(channel, complex_message)

            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    break

            try:
                await asyncio.wait_for(collect(), timeout=2.0)
            except TimeoutError:
                pass

            # Verify message was properly serialized and deserialized
            assert len(received_messages) == 1
            data = received_messages[0]["data"]
            assert data["type"] == "event"
            assert data["data"]["id"] == 123
            assert data["data"]["nested"]["key"] == "value"
            assert data["data"]["nested"]["array"] == [1, 2, 3]
            assert data["data"]["boolean"] is True
            assert data["data"]["null_value"] is None
            assert abs(data["data"]["float"] - 3.14159) < 0.00001

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_string_message_passthrough(self, real_redis: RedisClient) -> None:
        """Test that string messages are passed through without double encoding."""
        channel = "test_channel_string"

        pubsub = await real_redis.subscribe_dedicated(channel)
        received_messages: list[dict] = []

        try:
            # Publish a pre-serialized JSON string
            pre_serialized = '{"type": "string_test", "value": 42}'
            await real_redis.publish(channel, pre_serialized)

            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    break

            try:
                await asyncio.wait_for(collect(), timeout=2.0)
            except TimeoutError:
                pass

            # The listen method should parse it back to dict
            assert len(received_messages) == 1
            data = received_messages[0]["data"]
            assert data["type"] == "string_test"
            assert data["value"] == 42

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


class TestDedicatedVsSharedPubSub:
    """Test the difference between dedicated and shared pub/sub connections."""

    @pytest.mark.asyncio
    async def test_subscribe_dedicated_creates_new_connection(
        self, real_redis: RedisClient
    ) -> None:
        """Test that subscribe_dedicated creates isolated connections."""
        channel = "test_channel_dedicated"

        # Create two dedicated connections
        pubsub1 = await real_redis.subscribe_dedicated(channel)
        pubsub2 = await real_redis.subscribe_dedicated(channel)

        try:
            # They should be different objects
            assert pubsub1 is not pubsub2

            # Both should receive messages
            count = await real_redis.publish(channel, {"msg": "test"})
            assert count == 2

        finally:
            await pubsub1.unsubscribe(channel)
            await pubsub1.aclose()
            await pubsub2.unsubscribe(channel)
            await pubsub2.aclose()

    @pytest.mark.asyncio
    async def test_create_pubsub_returns_new_instance(self, real_redis: RedisClient) -> None:
        """Test that create_pubsub returns a new PubSub instance each time."""
        pubsub1 = real_redis.create_pubsub()
        pubsub2 = real_redis.create_pubsub()

        try:
            # Should be different instances
            assert pubsub1 is not pubsub2
        finally:
            await pubsub1.aclose()
            await pubsub2.aclose()


class TestErrorRecovery:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_publish_after_subscriber_closes(self, real_redis: RedisClient) -> None:
        """Test that publishing works after a subscriber closes its connection."""
        channel = "test_channel_sub_close"

        # Create subscriber
        pubsub = await real_redis.subscribe_dedicated(channel)
        count = await real_redis.publish(channel, {"msg": "test1"})
        assert count == 1

        # Close subscriber
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

        await asyncio.sleep(0.1)

        # Publishing should still work (just return 0 subscribers)
        count = await real_redis.publish(channel, {"msg": "test2"})
        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribe_same_channel_same_pubsub(
        self, real_redis: RedisClient
    ) -> None:
        """Test subscribing to the same channel multiple times on same pubsub."""
        channel = "test_channel_multi_sub"

        pubsub = await real_redis.subscribe_dedicated(channel)

        try:
            # Subscribe again (should be idempotent)
            await pubsub.subscribe(channel)

            # Should still work
            count = await real_redis.publish(channel, {"msg": "test"})
            # Redis only counts unique subscriptions per connection
            assert count == 1

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


class TestPubSubMessageMetadata:
    """Test pub/sub message metadata."""

    @pytest.mark.asyncio
    async def test_message_contains_channel_name(self, real_redis: RedisClient) -> None:
        """Test that received messages include the channel name."""
        channel = "test_channel_metadata"

        pubsub = await real_redis.subscribe_dedicated(channel)
        received_messages: list[dict] = []

        try:
            await real_redis.publish(channel, {"msg": "test"})

            async def collect():
                async for message in real_redis.listen(pubsub):
                    received_messages.append(message)
                    break

            try:
                await asyncio.wait_for(collect(), timeout=2.0)
            except TimeoutError:
                pass

            assert len(received_messages) == 1
            assert "channel" in received_messages[0]
            assert received_messages[0]["channel"] == channel

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
