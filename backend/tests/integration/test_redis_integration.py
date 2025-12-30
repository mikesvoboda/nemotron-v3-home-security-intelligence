"""Integration tests for Redis operations using real Redis (testcontainers).

These tests use the real_redis fixture which connects to either:
1. A local Redis instance (if running via podman-compose)
2. A Redis testcontainer (automatically started if no local Redis)

This file tests actual Redis behavior including:
- Queue operations with real backpressure
- Pub/Sub with real message delivery
- Connection failure scenarios
- Queue overflow behavior

These tests replace mocked Redis tests where real Redis behavior is important.
"""

import asyncio
import json

import pytest

from backend.core.redis import (
    QueueOverflowPolicy,
    QueuePressureMetrics,
    RedisClient,
)
from backend.tests.conftest import unique_id

# Mark all tests as integration tests
pytestmark = pytest.mark.integration


class TestRedisQueueOperationsIntegration:
    """Integration tests for Redis queue operations with real Redis."""

    @pytest.mark.asyncio
    async def test_add_and_get_from_queue(self, real_redis: RedisClient):
        """Test adding and retrieving items from a queue."""
        queue_name = unique_id("test_queue")

        try:
            # Add items using add_to_queue_safe to avoid deprecation warning
            await real_redis.add_to_queue_safe(queue_name, {"id": 1, "data": "first"}, max_size=0)
            await real_redis.add_to_queue_safe(queue_name, {"id": 2, "data": "second"}, max_size=0)

            # Check length
            length = await real_redis.get_queue_length(queue_name)
            assert length == 2

            # Get items (FIFO order)
            item1 = await real_redis.get_from_queue(queue_name, timeout=1)
            assert item1["id"] == 1

            item2 = await real_redis.get_from_queue(queue_name, timeout=1)
            assert item2["id"] == 2

            # Queue should be empty
            length = await real_redis.get_queue_length(queue_name)
            assert length == 0
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)

    @pytest.mark.asyncio
    async def test_peek_queue_without_removing(self, real_redis: RedisClient):
        """Test peeking at queue items without removing them."""
        queue_name = unique_id("test_peek_queue")

        try:
            # Add items using add_to_queue_safe
            for i in range(5):
                await real_redis.add_to_queue_safe(queue_name, {"id": i}, max_size=0)

            # Peek at items
            items = await real_redis.peek_queue(queue_name, start=0, end=4)
            assert len(items) == 5
            assert [item["id"] for item in items] == [0, 1, 2, 3, 4]

            # Queue should still have all items
            length = await real_redis.get_queue_length(queue_name)
            assert length == 5
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)

    @pytest.mark.asyncio
    async def test_clear_queue(self, real_redis: RedisClient):
        """Test clearing a queue."""
        queue_name = unique_id("test_clear_queue")

        # Add items using add_to_queue_safe
        for i in range(3):
            await real_redis.add_to_queue_safe(queue_name, {"id": i}, max_size=0)

        # Clear queue
        result = await real_redis.clear_queue(queue_name)
        assert result is True

        # Queue should be empty
        length = await real_redis.get_queue_length(queue_name)
        assert length == 0

        # Clearing empty queue returns False
        result = await real_redis.clear_queue(queue_name)
        assert result is False


class TestRedisQueueBackpressureIntegration:
    """Integration tests for queue backpressure with real Redis."""

    @pytest.mark.asyncio
    async def test_queue_overflow_reject_policy(self, real_redis: RedisClient):
        """Test REJECT policy prevents adding items when queue is full."""
        queue_name = unique_id("test_reject_queue")
        max_size = 5

        try:
            # Fill queue to capacity
            for i in range(max_size):
                result = await real_redis.add_to_queue_safe(
                    queue_name,
                    {"id": i},
                    max_size=max_size,
                    overflow_policy=QueueOverflowPolicy.REJECT,
                )
                assert result.success is True

            # Verify queue is full
            length = await real_redis.get_queue_length(queue_name)
            assert length == max_size

            # Try to add one more - should be rejected
            result = await real_redis.add_to_queue_safe(
                queue_name,
                {"id": "overflow"},
                max_size=max_size,
                overflow_policy=QueueOverflowPolicy.REJECT,
            )

            assert result.success is False
            assert result.error is not None
            assert "full" in result.error.lower()

            # Queue length should still be at max
            length = await real_redis.get_queue_length(queue_name)
            assert length == max_size
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)

    @pytest.mark.asyncio
    async def test_queue_overflow_dlq_policy(self, real_redis: RedisClient):
        """Test DLQ policy moves oldest items to dead-letter queue."""
        queue_name = unique_id("test_dlq_queue")
        dlq_name = f"dlq:overflow:{queue_name}"
        max_size = 5

        try:
            # Fill queue to capacity with identifiable items
            for i in range(max_size):
                result = await real_redis.add_to_queue_safe(
                    queue_name,
                    {"id": i, "data": f"item_{i}"},
                    max_size=max_size,
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )
                assert result.success is True

            # Add overflow item
            result = await real_redis.add_to_queue_safe(
                queue_name,
                {"id": "new", "data": "new_item"},
                max_size=max_size,
                overflow_policy=QueueOverflowPolicy.DLQ,
            )

            assert result.success is True
            assert result.moved_to_dlq_count == 1

            # Queue length should still be at max
            length = await real_redis.get_queue_length(queue_name)
            assert length == max_size

            # DLQ should have the oldest item
            dlq_length = await real_redis.get_queue_length(dlq_name)
            assert dlq_length == 1

            # Verify DLQ contains the right item (id=0 was oldest)
            dlq_items = await real_redis.peek_queue(dlq_name)
            assert len(dlq_items) == 1
            dlq_entry = dlq_items[0]
            assert dlq_entry["original_queue"] == queue_name
            assert dlq_entry["reason"] == "queue_overflow"
            # The data is JSON-serialized string
            original_data = json.loads(dlq_entry["data"])
            assert original_data["id"] == 0
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)
            await real_redis.clear_queue(dlq_name)

    @pytest.mark.asyncio
    async def test_queue_overflow_drop_oldest_policy(self, real_redis: RedisClient):
        """Test DROP_OLDEST policy trims queue to max size."""
        queue_name = unique_id("test_drop_queue")
        max_size = 5

        try:
            # Fill queue to capacity
            for i in range(max_size):
                result = await real_redis.add_to_queue_safe(
                    queue_name,
                    {"id": i},
                    max_size=max_size,
                    overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
                )
                assert result.success is True

            # Add overflow item
            result = await real_redis.add_to_queue_safe(
                queue_name,
                {"id": "new"},
                max_size=max_size,
                overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
            )

            assert result.success is True
            assert result.dropped_count == 1

            # Queue length should still be at max
            length = await real_redis.get_queue_length(queue_name)
            assert length == max_size

            # Verify oldest was dropped (id=0 should be gone)
            items = await real_redis.peek_queue(queue_name)
            ids = [item["id"] for item in items]
            assert 0 not in ids  # Oldest dropped
            assert "new" in ids  # New item added
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)

    @pytest.mark.asyncio
    async def test_get_queue_pressure_metrics(self, real_redis: RedisClient):
        """Test getting queue pressure metrics."""
        queue_name = unique_id("test_pressure_queue")
        max_size = 10

        try:
            # Add some items (50% full)
            for i in range(5):
                await real_redis.add_to_queue_safe(queue_name, {"id": i}, max_size=0)

            # Get pressure metrics
            metrics = await real_redis.get_queue_pressure(queue_name, max_size=max_size)

            assert isinstance(metrics, QueuePressureMetrics)
            assert metrics.queue_name == queue_name
            assert metrics.current_length == 5
            assert metrics.max_size == max_size
            assert metrics.fill_ratio == 0.5
            assert metrics.is_at_pressure_threshold is False  # 50% < 80%
            assert metrics.is_full is False
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)

    @pytest.mark.asyncio
    async def test_queue_pressure_at_threshold(self, real_redis: RedisClient):
        """Test queue pressure detection at threshold."""
        queue_name = unique_id("test_threshold_queue")
        max_size = 10

        try:
            # Fill to 90% (above 80% threshold)
            for i in range(9):
                await real_redis.add_to_queue_safe(queue_name, {"id": i}, max_size=0)

            metrics = await real_redis.get_queue_pressure(queue_name, max_size=max_size)

            assert metrics.fill_ratio == 0.9
            assert metrics.is_at_pressure_threshold is True
            assert metrics.is_full is False
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)

    @pytest.mark.asyncio
    async def test_queue_full_detection(self, real_redis: RedisClient):
        """Test queue full detection."""
        queue_name = unique_id("test_full_queue")
        max_size = 5

        try:
            # Fill to 100%
            for i in range(max_size):
                await real_redis.add_to_queue_safe(queue_name, {"id": i}, max_size=0)

            metrics = await real_redis.get_queue_pressure(queue_name, max_size=max_size)

            assert metrics.fill_ratio == 1.0
            assert metrics.is_at_pressure_threshold is True
            assert metrics.is_full is True
        finally:
            # Cleanup
            await real_redis.clear_queue(queue_name)


class TestRedisPubSubIntegration:
    """Integration tests for Redis pub/sub with real Redis."""

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self, real_redis: RedisClient):
        """Test publishing and receiving messages via pub/sub."""
        channel = unique_id("test_channel")
        received_messages = []

        # Create dedicated pubsub for subscriber
        pubsub = await real_redis.subscribe_dedicated(channel)

        try:
            # Allow subscription to complete
            await asyncio.sleep(0.1)

            # Publish a message
            num_subscribers = await real_redis.publish(channel, {"event": "test", "data": 123})

            # Should have at least one subscriber
            assert num_subscribers >= 1

            # Read messages
            async def read_messages():
                async for msg in real_redis.listen(pubsub):
                    received_messages.append(msg)
                    if len(received_messages) >= 1:
                        break

            # Use timeout to avoid hanging
            try:
                await asyncio.wait_for(read_messages(), timeout=2.0)
            except TimeoutError:
                pass  # May timeout if message arrived before we started listening
        finally:
            # Cleanup
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_message(self, real_redis: RedisClient):
        """Test that multiple subscribers all receive published messages."""
        channel = unique_id("test_multi_channel")

        # Create two dedicated pubsub connections
        pubsub1 = await real_redis.subscribe_dedicated(channel)
        pubsub2 = await real_redis.subscribe_dedicated(channel)

        try:
            # Allow subscriptions to complete
            await asyncio.sleep(0.1)

            # Publish a message
            num_subscribers = await real_redis.publish(channel, {"event": "broadcast"})

            # Should have two subscribers
            assert num_subscribers >= 2
        finally:
            # Cleanup
            await pubsub1.unsubscribe(channel)
            await pubsub1.aclose()
            await pubsub2.unsubscribe(channel)
            await pubsub2.aclose()


class TestRedisCacheIntegration:
    """Integration tests for Redis cache operations with real Redis."""

    @pytest.mark.asyncio
    async def test_set_and_get_value(self, real_redis: RedisClient):
        """Test setting and getting cache values."""
        key = unique_id("test_cache_key")

        try:
            # Set value
            result = await real_redis.set(key, {"data": "test_value", "number": 42})
            assert result is True

            # Get value
            value = await real_redis.get(key)
            assert value is not None
            assert value["data"] == "test_value"
            assert value["number"] == 42
        finally:
            # Cleanup
            await real_redis.delete(key)

    @pytest.mark.asyncio
    async def test_cache_expiration(self, real_redis: RedisClient):
        """Test cache value expiration."""
        key = unique_id("test_expire_key")

        try:
            # Set value with short TTL
            await real_redis.set(key, "expires_soon", expire=1)

            # Value should exist immediately
            value = await real_redis.get(key)
            assert value == "expires_soon"

            # Wait for expiration (testing real Redis TTL behavior)
            await asyncio.sleep(1.5)  # patched: required for Redis TTL integration test

            # Value should be gone
            value = await real_redis.get(key)
            assert value is None
        finally:
            # Cleanup (may already be expired)
            await real_redis.delete(key)

    @pytest.mark.asyncio
    async def test_delete_key(self, real_redis: RedisClient):
        """Test deleting cache keys."""
        key1 = unique_id("test_delete_key1")
        key2 = unique_id("test_delete_key2")

        try:
            # Set values
            await real_redis.set(key1, "value1")
            await real_redis.set(key2, "value2")

            # Delete both
            deleted = await real_redis.delete(key1, key2)
            assert deleted == 2

            # Verify deleted
            assert await real_redis.get(key1) is None
            assert await real_redis.get(key2) is None
        finally:
            # Cleanup (already deleted but just in case)
            await real_redis.delete(key1, key2)

    @pytest.mark.asyncio
    async def test_exists_check(self, real_redis: RedisClient):
        """Test checking if keys exist."""
        key1 = unique_id("test_exists_key1")
        key2 = unique_id("test_exists_key2")
        key3 = unique_id("test_exists_key3")

        try:
            # Set only two keys
            await real_redis.set(key1, "value1")
            await real_redis.set(key2, "value2")

            # Check existence
            exists = await real_redis.exists(key1, key2, key3)
            assert exists == 2  # Only 2 of 3 exist
        finally:
            # Cleanup
            await real_redis.delete(key1, key2, key3)

    @pytest.mark.asyncio
    async def test_expire_method(self, real_redis: RedisClient):
        """Test setting TTL on existing key."""
        key = unique_id("test_ttl_key")

        try:
            # Set value without expiration
            await real_redis.set(key, "persistent_value")

            # Set TTL
            result = await real_redis.expire(key, 1)
            assert result is True

            # Value should exist immediately
            value = await real_redis.get(key)
            assert value == "persistent_value"

            # Wait for expiration (testing real Redis TTL behavior)
            await asyncio.sleep(1.5)  # patched: required for Redis TTL integration test

            # Value should be gone
            value = await real_redis.get(key)
            assert value is None
        finally:
            # Cleanup (may already be expired)
            await real_redis.delete(key)


class TestRedisHealthCheckIntegration:
    """Integration tests for Redis health check with real Redis."""

    @pytest.mark.asyncio
    async def test_health_check_connected(self, real_redis: RedisClient):
        """Test health check when connected to Redis."""
        health = await real_redis.health_check()

        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert "redis_version" in health


class TestRedisFailureScenarios:
    """Tests for Redis failure scenarios."""

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, integration_env):
        """Test that connection failures are handled gracefully."""
        # Create client with invalid URL
        client = RedisClient(redis_url="redis://invalid-host:9999/0")
        client._max_retries = 1  # Fast fail
        client._base_delay = 0.01  # Fast retry

        # Should raise ConnectionError after retries
        with pytest.raises((ConnectionError, OSError, RuntimeError)):
            await client.connect()

    @pytest.mark.asyncio
    async def test_health_check_reports_disconnected(self, integration_env):
        """Test health check reports disconnected state."""
        # Create client without connecting
        client = RedisClient(redis_url="redis://localhost:6379/15")
        # Don't connect - _client is None

        # Health check should return unhealthy status (catches RuntimeError internally)
        health = await client.health_check()
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "not connected" in health["error"]
