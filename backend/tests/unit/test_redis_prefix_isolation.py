"""Tests for Redis key prefix isolation in pytest-xdist parallel execution.

This module tests the PrefixedRedis wrapper and redis_prefix fixture to ensure
proper key isolation when running integration tests in parallel.

Note: The tests in TestPrefixedRedisUnit use mocks and can run without services.
The tests in TestPrefixedRedisIntegration require real Redis and PostgreSQL.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.tests.integration.conftest import PrefixedRedis


class TestPrefixedRedisUnit:
    """Unit tests for PrefixedRedis that don't require real Redis."""

    def test_prefix_property(self) -> None:
        """Verify the prefix property returns the configured prefix."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")
        assert prefixed.prefix == "test:gw0:"

    def test_prefixed_key_single(self) -> None:
        """Verify _prefixed_key correctly prefixes a single key."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        assert prefixed._prefixed_key("foo") == "test:gw0:foo"
        assert prefixed._prefixed_key("bar:baz") == "test:gw0:bar:baz"
        assert prefixed._prefixed_key("") == "test:gw0:"

    def test_prefixed_keys_multiple(self) -> None:
        """Verify _prefixed_keys correctly prefixes multiple keys."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:gw1:")

        keys = prefixed._prefixed_keys("a", "b", "c")
        assert keys == ["test:gw1:a", "test:gw1:b", "test:gw1:c"]

    def test_prefixed_keys_empty(self) -> None:
        """Verify _prefixed_keys handles empty input."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:main:")

        keys = prefixed._prefixed_keys()
        assert keys == []

    @pytest.mark.asyncio
    async def test_get_calls_client_with_prefix(self) -> None:
        """Verify get calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value={"data": "value"})
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.get("my_key")

        mock_client.get.assert_called_once_with("test:gw0:my_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_set_calls_client_with_prefix(self) -> None:
        """Verify set calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.set = AsyncMock(return_value=True)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.set("my_key", {"value": 42}, expire=300)

        mock_client.set.assert_called_once_with("test:gw0:my_key", {"value": 42}, 300, nx=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_calls_client_with_prefixed_keys(self) -> None:
        """Verify delete calls the underlying client with prefixed keys."""
        mock_client = MagicMock()
        mock_client.delete = AsyncMock(return_value=2)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.delete("key1", "key2")

        mock_client.delete.assert_called_once_with("test:gw0:key1", "test:gw0:key2")
        assert result == 2

    @pytest.mark.asyncio
    async def test_exists_calls_client_with_prefixed_keys(self) -> None:
        """Verify exists calls the underlying client with prefixed keys."""
        mock_client = MagicMock()
        mock_client.exists = AsyncMock(return_value=1)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.exists("key1", "key2")

        mock_client.exists.assert_called_once_with("test:gw0:key1", "test:gw0:key2")
        assert result == 1

    @pytest.mark.asyncio
    async def test_lpush_calls_client_with_prefix(self) -> None:
        """Verify lpush calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.lpush = AsyncMock(return_value=2)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.lpush("my_list", "a", "b")

        mock_client.lpush.assert_called_once_with("test:gw0:my_list", "a", "b")
        assert result == 2

    @pytest.mark.asyncio
    async def test_zadd_calls_client_with_prefix(self) -> None:
        """Verify zadd calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.zadd = AsyncMock(return_value=2)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.zadd("my_zset", {"a": 1.0, "b": 2.0})

        mock_client.zadd.assert_called_once_with("test:gw0:my_zset", {"a": 1.0, "b": 2.0})
        assert result == 2

    @pytest.mark.asyncio
    async def test_publish_calls_client_with_prefix(self) -> None:
        """Verify publish calls the underlying client with prefixed channel."""
        mock_client = MagicMock()
        mock_client.publish = AsyncMock(return_value=1)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.publish("my_channel", {"event": "data"})

        mock_client.publish.assert_called_once_with("test:gw0:my_channel", {"event": "data"})
        assert result == 1

    @pytest.mark.asyncio
    async def test_health_check_passes_through(self) -> None:
        """Verify health_check doesn't modify anything (passthrough)."""
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(return_value={"status": "healthy", "connected": True})
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.health_check()

        mock_client.health_check.assert_called_once_with()
        assert result == {"status": "healthy", "connected": True}

    @pytest.mark.asyncio
    async def test_add_to_queue_safe_prefixes_queue_and_dlq(self) -> None:
        """Verify add_to_queue_safe prefixes both queue name and DLQ name."""
        mock_client = MagicMock()
        mock_client.add_to_queue_safe = AsyncMock(return_value=MagicMock(success=True))
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        await prefixed.add_to_queue_safe("my_queue", {"data": 1}, dlq_name="my_dlq")

        mock_client.add_to_queue_safe.assert_called_once_with(
            "test:gw0:my_queue",
            {"data": 1},
            None,
            None,
            "test:gw0:my_dlq",
        )

    @pytest.mark.asyncio
    async def test_add_to_queue_safe_with_no_dlq(self) -> None:
        """Verify add_to_queue_safe handles None DLQ correctly."""
        mock_client = MagicMock()
        mock_client.add_to_queue_safe = AsyncMock(return_value=MagicMock(success=True))
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        await prefixed.add_to_queue_safe("my_queue", {"data": 1})

        mock_client.add_to_queue_safe.assert_called_once_with(
            "test:gw0:my_queue",
            {"data": 1},
            None,
            None,
            None,  # DLQ should be None, not prefixed
        )

    @pytest.mark.asyncio
    async def test_cleanup_scans_and_deletes_prefixed_keys(self) -> None:
        """Verify cleanup scans for prefixed keys and deletes them."""
        mock_redis_client = MagicMock()

        # Mock the internal Redis client with scan_iter
        mock_internal_client = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            for key in ["test:gw0:key1", "test:gw0:key2", "test:gw0:list1"]:
                yield key

        mock_internal_client.scan_iter = mock_scan_iter
        mock_internal_client.delete = AsyncMock(return_value=3)

        mock_redis_client._client = mock_internal_client

        prefixed = PrefixedRedis(mock_redis_client, prefix="test:gw0:")
        deleted = await prefixed.cleanup()

        mock_internal_client.delete.assert_called_once_with(
            "test:gw0:key1", "test:gw0:key2", "test:gw0:list1"
        )
        assert deleted == 3


class TestRedisPrefixFixture:
    """Tests for the redis_prefix session fixture.

    These tests require the redis_prefix fixture which depends on integration
    test infrastructure (PostgreSQL). Skip in environments without services.
    """

    @pytest.mark.integration
    def test_redis_prefix_format(self, redis_prefix: str) -> None:
        """Verify redis_prefix follows expected format."""
        assert redis_prefix.startswith("test:")
        assert redis_prefix.endswith(":")
        # Should be "test:gw0:", "test:gw1:", or "test:main:"
        parts = redis_prefix.split(":")
        assert len(parts) == 3
        assert parts[0] == "test"
        assert parts[2] == ""  # Trailing colon

    @pytest.mark.integration
    def test_redis_prefix_is_session_scoped(
        self, redis_prefix: str, request: pytest.FixtureRequest
    ) -> None:
        """Verify redis_prefix is consistent within a session (stored for later check)."""
        # Store the prefix in the session-level cache for consistency verification
        # This can be checked by running multiple tests with the same prefix
        if hasattr(request.session, "_test_redis_prefix"):
            assert request.session._test_redis_prefix == redis_prefix
        else:
            request.session._test_redis_prefix = redis_prefix


class TestPrefixedRedisIntegration:
    """Integration tests for PrefixedRedis that require real Redis.

    These tests verify the full behavior with a real Redis instance.
    Skip in environments without services by using the @pytest.mark.integration marker.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prefixed_key_generation(self, real_redis, redis_prefix: str) -> None:
        """Verify keys are correctly prefixed."""
        prefixed = PrefixedRedis(real_redis, prefix=redis_prefix)

        assert prefixed._prefixed_key("foo") == f"{redis_prefix}foo"
        assert prefixed._prefixed_key("bar:baz") == f"{redis_prefix}bar:baz"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prefixed_keys_generation(self, real_redis, redis_prefix: str) -> None:
        """Verify multiple keys are correctly prefixed."""
        prefixed = PrefixedRedis(real_redis, prefix=redis_prefix)

        keys = prefixed._prefixed_keys("a", "b", "c")
        assert keys == [f"{redis_prefix}a", f"{redis_prefix}b", f"{redis_prefix}c"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_and_get(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify set and get operations with prefix."""
        await prefixed_redis.set("test_key", {"value": 42})
        result = await prefixed_redis.get("test_key")
        assert result == {"value": 42}

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_with_expire(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify set with expiration works."""
        await prefixed_redis.set("expiring_key", "test_value", expire=300)
        result = await prefixed_redis.get("expiring_key")
        assert result == "test_value"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify delete operation with prefix."""
        await prefixed_redis.set("delete_me", "value")
        assert await prefixed_redis.get("delete_me") == "value"

        deleted = await prefixed_redis.delete("delete_me")
        assert deleted == 1
        assert await prefixed_redis.get("delete_me") is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_exists(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify exists operation with prefix."""
        assert await prefixed_redis.exists("nonexistent") == 0

        await prefixed_redis.set("exists_key", "value")
        assert await prefixed_redis.exists("exists_key") == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_operations(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify list operations with prefix."""
        # lpush
        await prefixed_redis.lpush("my_list", "a", "b")
        assert await prefixed_redis.llen("my_list") == 2

        # rpush
        await prefixed_redis.rpush("my_list", "c")
        assert await prefixed_redis.llen("my_list") == 3

        # lrange
        values = await prefixed_redis.lrange("my_list", 0, -1)
        assert len(values) == 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sorted_set_operations(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify sorted set operations with prefix."""
        # zadd
        await prefixed_redis.zadd("my_zset", {"member1": 1.0, "member2": 2.0})
        assert await prefixed_redis.zcard("my_zset") == 2

        # zscore
        score = await prefixed_redis.zscore("my_zset", "member1")
        assert score == 1.0

        # zrange
        members = await prefixed_redis.zrange("my_zset", 0, -1)
        assert len(members) == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hyperloglog_operations(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify HyperLogLog operations with prefix."""
        await prefixed_redis.pfadd("my_hll", "a", "b", "c", "a")  # 'a' counted once
        count = await prefixed_redis.pfcount("my_hll")
        assert count == 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cleanup(self, real_redis, redis_prefix: str) -> None:
        """Verify cleanup removes all prefixed keys."""
        prefixed = PrefixedRedis(real_redis, prefix=redis_prefix)

        # Create multiple keys
        await prefixed.set("key1", "value1")
        await prefixed.set("key2", "value2")
        await prefixed.lpush("list1", "item")
        await prefixed.zadd("zset1", {"member": 1.0})

        # Verify keys exist
        assert await prefixed.exists("key1", "key2") == 2

        # Cleanup
        deleted = await prefixed.cleanup()
        assert deleted >= 4  # At least our 4 keys

        # Verify keys are gone
        assert await prefixed.exists("key1", "key2") == 0


class TestKeyIsolation:
    """Tests verifying key isolation between different prefixes."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_different_prefixes_are_isolated(self, real_redis) -> None:
        """Verify that different prefixes don't see each other's keys."""
        prefix1 = "test:worker1:"
        prefix2 = "test:worker2:"

        client1 = PrefixedRedis(real_redis, prefix=prefix1)
        client2 = PrefixedRedis(real_redis, prefix=prefix2)

        try:
            # Set keys with different prefixes
            await client1.set("shared_key", "value_from_worker1")
            await client2.set("shared_key", "value_from_worker2")

            # Each should see their own value
            assert await client1.get("shared_key") == "value_from_worker1"
            assert await client2.get("shared_key") == "value_from_worker2"

            # Cleanup one shouldn't affect the other
            await client1.cleanup()
            assert await client1.get("shared_key") is None
            assert await client2.get("shared_key") == "value_from_worker2"
        finally:
            # Cleanup both
            await client1.cleanup()
            await client2.cleanup()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prefix_property(self, prefixed_redis: PrefixedRedis) -> None:
        """Verify the prefix property is accessible."""
        assert prefixed_redis.prefix.startswith("test:")
        assert prefixed_redis.prefix.endswith(":")
