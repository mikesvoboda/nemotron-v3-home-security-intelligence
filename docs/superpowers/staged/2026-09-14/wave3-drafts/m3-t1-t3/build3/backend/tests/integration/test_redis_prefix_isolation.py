"""Integration tests for Redis key prefix isolation in pytest-xdist.

M3 Task 3 (audit 1.3): moved from backend/tests/unit/ — every test here
carried @pytest.mark.integration and was therefore permanently skipped under
/unit/ by the root-conftest skip rule (conftest.py:438-441). In the
integration tier redis_prefix / real_redis / prefixed_redis resolve from
integration/conftest.py.

The mock-only PrefixedRedis tests stay in
`backend/tests/unit/test_redis_prefix_isolation.py`.
"""

import pytest

from backend.tests.integration.conftest import PrefixedRedis


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