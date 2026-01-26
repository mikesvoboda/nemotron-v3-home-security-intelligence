"""Unit tests for Redis Lua scripts (NEM-3766)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis_lua_scripts import (
    ConditionalUpdateResult,
    RateLimitResult,
    RedisLuaScripts,
    get_lua_scripts,
    reset_lua_scripts,
)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = MagicMock()
    client._client = AsyncMock()
    client._client.script_load = AsyncMock(return_value="abc123sha")
    client._client.evalsha = AsyncMock()
    return client


@pytest.fixture
def lua_scripts(mock_redis_client):
    """Create Lua scripts instance for testing."""
    # Make _ensure_connected return the mock client
    mock_redis_client._ensure_connected = MagicMock(return_value=mock_redis_client._client)
    return RedisLuaScripts(mock_redis_client)


class TestConditionalUpdateResult:
    """Tests for ConditionalUpdateResult dataclass."""

    def test_result_success(self):
        """Test successful conditional update result."""
        result = ConditionalUpdateResult(
            success=True,
            old_value=5,
            new_value=10,
            condition_met=True,
        )
        assert result.success is True
        assert result.old_value == 5
        assert result.new_value == 10

    def test_result_failure(self):
        """Test failed conditional update result."""
        result = ConditionalUpdateResult(
            success=False,
            old_value=5,
            new_value=5,  # Unchanged
            condition_met=False,
        )
        assert result.success is False
        assert result.old_value == result.new_value


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_result_allowed(self):
        """Test rate limit result when allowed."""
        result = RateLimitResult(
            allowed=True,
            current_count=50,
            remaining=50,
            reset_at=1706300000,
        )
        assert result.allowed is True
        assert result.remaining == 50

    def test_result_denied(self):
        """Test rate limit result when denied."""
        result = RateLimitResult(
            allowed=False,
            current_count=100,
            remaining=0,
            reset_at=1706300000,
        )
        assert result.allowed is False
        assert result.remaining == 0


class TestRedisLuaScripts:
    """Tests for RedisLuaScripts class."""

    @pytest.mark.asyncio
    async def test_script_sha_caching(self, lua_scripts, mock_redis_client):
        """Test that script SHAs are cached."""
        mock_redis_client._client.evalsha.return_value = [1, 0, 5]

        # First call should load script
        await lua_scripts.conditional_increment("key1", 5)
        assert mock_redis_client._client.script_load.await_count == 1

        # Second call should reuse SHA
        await lua_scripts.conditional_increment("key2", 3)
        assert mock_redis_client._client.script_load.await_count == 1  # No additional load

    @pytest.mark.asyncio
    async def test_conditional_increment_success(self, lua_scripts, mock_redis_client):
        """Test conditional increment when under max."""
        mock_redis_client._client.evalsha.return_value = [1, 5, 10]

        result = await lua_scripts.conditional_increment("counter", 5, max_value=100)

        assert result.success is True
        assert result.old_value == 5
        assert result.new_value == 10

    @pytest.mark.asyncio
    async def test_conditional_increment_at_max(self, lua_scripts, mock_redis_client):
        """Test conditional increment when at max."""
        mock_redis_client._client.evalsha.return_value = [0, 100, 100]

        result = await lua_scripts.conditional_increment("counter", 5, max_value=100)

        assert result.success is False
        assert result.old_value == 100
        assert result.new_value == 100  # Unchanged

    @pytest.mark.asyncio
    async def test_conditional_increment_no_max(self, lua_scripts, mock_redis_client):
        """Test conditional increment with no max (max=0)."""
        mock_redis_client._client.evalsha.return_value = [1, 1000, 1005]

        result = await lua_scripts.conditional_increment("counter", 5, max_value=0)

        assert result.success is True
        assert result.new_value == 1005

    @pytest.mark.asyncio
    async def test_compare_and_set_success(self, lua_scripts, mock_redis_client):
        """Test compare-and-set when value matches."""
        mock_redis_client._client.evalsha.return_value = [1, "old_value"]

        result = await lua_scripts.compare_and_set(
            "key", expected="old_value", new_value="new_value", ttl=300
        )

        assert result.success is True
        assert result.old_value == "old_value"
        assert result.new_value == "new_value"

    @pytest.mark.asyncio
    async def test_compare_and_set_failure(self, lua_scripts, mock_redis_client):
        """Test compare-and-set when value doesn't match."""
        mock_redis_client._client.evalsha.return_value = [0, "different_value"]

        result = await lua_scripts.compare_and_set(
            "key", expected="old_value", new_value="new_value"
        )

        assert result.success is False
        assert result.old_value == "different_value"

    @pytest.mark.asyncio
    async def test_compare_and_set_expected_none(self, lua_scripts, mock_redis_client):
        """Test compare-and-set with expected None (key doesn't exist)."""
        mock_redis_client._client.evalsha.return_value = [1, None]

        result = await lua_scripts.compare_and_set("key", expected=None, new_value="new_value")

        # Verify empty string is passed for None
        call_args = mock_redis_client._client.evalsha.call_args
        assert call_args[0][3] == ""  # expected arg should be empty string

    @pytest.mark.asyncio
    async def test_rate_limit_check_allowed(self, lua_scripts, mock_redis_client):
        """Test rate limit check when under limit."""
        mock_redis_client._client.evalsha.return_value = [1, 50, 50, 1706300000]

        result = await lua_scripts.rate_limit_check("user:123", limit=100, window=60)

        assert result.allowed is True
        assert result.current_count == 50
        assert result.remaining == 50

    @pytest.mark.asyncio
    async def test_rate_limit_check_denied(self, lua_scripts, mock_redis_client):
        """Test rate limit check when at limit."""
        mock_redis_client._client.evalsha.return_value = [0, 100, 0, 1706300060]

        result = await lua_scripts.rate_limit_check("user:123", limit=100, window=60)

        assert result.allowed is False
        assert result.current_count == 100
        assert result.remaining == 0
        assert result.reset_at == 1706300060

    @pytest.mark.asyncio
    async def test_get_and_refresh(self, lua_scripts, mock_redis_client):
        """Test get and refresh TTL."""
        mock_redis_client._client.evalsha.return_value = ["cached_value", 1]

        value, refreshed = await lua_scripts.get_and_refresh("key", ttl=300)

        assert value == "cached_value"
        assert refreshed is True

    @pytest.mark.asyncio
    async def test_get_and_refresh_miss(self, lua_scripts, mock_redis_client):
        """Test get and refresh when key doesn't exist."""
        mock_redis_client._client.evalsha.return_value = [None, 0]

        value, refreshed = await lua_scripts.get_and_refresh("missing_key", ttl=300)

        assert value is None
        assert refreshed is False

    @pytest.mark.asyncio
    async def test_queue_rotate(self, lua_scripts, mock_redis_client):
        """Test atomic queue rotation."""
        mock_redis_client._client.evalsha.return_value = 5

        moved = await lua_scripts.queue_rotate("source", "dest", count=10)

        assert moved == 5

    @pytest.mark.asyncio
    async def test_incr_with_expire(self, lua_scripts, mock_redis_client):
        """Test atomic increment with expiry."""
        mock_redis_client._client.evalsha.return_value = 1

        value = await lua_scripts.incr_with_expire("counter", ttl=3600)

        assert value == 1

    @pytest.mark.asyncio
    async def test_hash_conditional_set_success(self, lua_scripts, mock_redis_client):
        """Test hash field conditional set when value matches."""
        mock_redis_client._client.evalsha.return_value = [1, "old", "new"]

        result = await lua_scripts.hash_conditional_set(
            "hash_key", field="field1", expected="old", new_value="new"
        )

        assert result.success is True
        assert result.old_value == "old"
        assert result.new_value == "new"

    @pytest.mark.asyncio
    async def test_hash_conditional_set_failure(self, lua_scripts, mock_redis_client):
        """Test hash field conditional set when value doesn't match."""
        mock_redis_client._client.evalsha.return_value = [0, "different", "different"]

        result = await lua_scripts.hash_conditional_set(
            "hash_key", field="field1", expected="old", new_value="new"
        )

        assert result.success is False
        assert result.old_value == "different"

    @pytest.mark.asyncio
    async def test_multi_key_set(self, lua_scripts, mock_redis_client):
        """Test atomic multi-key set."""
        mock_redis_client._client.evalsha.return_value = 3

        count = await lua_scripts.multi_key_set(
            {"key1": "value1", "key2": "value2", "key3": "value3"},
            ttl=300,
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_get_with_lock_cache_hit(self, lua_scripts, mock_redis_client):
        """Test get with lock when cache hit."""
        mock_redis_client._client.evalsha.return_value = ["cached", 0, 1]

        value, lock_acquired, cache_hit = await lua_scripts.get_with_lock(
            "cache_key", "lock_key", lock_ttl=30
        )

        assert value == "cached"
        assert lock_acquired is False
        assert cache_hit is True

    @pytest.mark.asyncio
    async def test_get_with_lock_acquired(self, lua_scripts, mock_redis_client):
        """Test get with lock when lock acquired."""
        mock_redis_client._client.evalsha.return_value = [None, 1, 0]

        value, lock_acquired, cache_hit = await lua_scripts.get_with_lock(
            "cache_key", "lock_key", lock_ttl=30
        )

        assert value is None
        assert lock_acquired is True
        assert cache_hit is False

    @pytest.mark.asyncio
    async def test_get_with_lock_not_acquired(self, lua_scripts, mock_redis_client):
        """Test get with lock when another request has the lock."""
        mock_redis_client._client.evalsha.return_value = [None, 0, 0]

        value, lock_acquired, cache_hit = await lua_scripts.get_with_lock(
            "cache_key", "lock_key", lock_ttl=30
        )

        assert value is None
        assert lock_acquired is False
        assert cache_hit is False

    @pytest.mark.asyncio
    async def test_noscript_reload(self, lua_scripts, mock_redis_client):
        """Test script reloading on NOSCRIPT error."""
        # First evalsha fails with NOSCRIPT
        from redis.exceptions import ResponseError

        noscript_error = ResponseError("NOSCRIPT No matching script")
        mock_redis_client._client.evalsha.side_effect = [noscript_error, [1, 0, 5]]

        result = await lua_scripts.conditional_increment("key", 5)

        # Should have called script_load twice (initial + reload)
        assert mock_redis_client._client.script_load.await_count == 2
        assert result.success is True


class TestGetLuaScripts:
    """Tests for get_lua_scripts singleton function."""

    @pytest.mark.asyncio
    async def test_singleton_creation(self):
        """Test Lua scripts singleton is created."""
        await reset_lua_scripts()

        mock_redis = AsyncMock()

        with patch("backend.core.redis.init_redis", return_value=mock_redis):
            scripts1 = await get_lua_scripts()
            scripts2 = await get_lua_scripts()

        assert scripts1 is scripts2
        await reset_lua_scripts()

    @pytest.mark.asyncio
    async def test_singleton_reset(self):
        """Test Lua scripts singleton can be reset."""
        await reset_lua_scripts()

        mock_redis = AsyncMock()

        with patch("backend.core.redis.init_redis", return_value=mock_redis):
            scripts1 = await get_lua_scripts()
            await reset_lua_scripts()
            scripts2 = await get_lua_scripts()

        assert scripts1 is not scripts2
        await reset_lua_scripts()


class TestLuaScriptDefinitions:
    """Tests to verify Lua script syntax and structure."""

    def test_conditional_increment_script_exists(self):
        """Test conditional increment script is defined."""
        assert RedisLuaScripts.CONDITIONAL_INCREMENT
        assert "KEYS[1]" in RedisLuaScripts.CONDITIONAL_INCREMENT
        assert "ARGV[1]" in RedisLuaScripts.CONDITIONAL_INCREMENT

    def test_compare_and_set_script_exists(self):
        """Test compare-and-set script is defined."""
        assert RedisLuaScripts.COMPARE_AND_SET
        assert "SETEX" in RedisLuaScripts.COMPARE_AND_SET

    def test_rate_limit_script_exists(self):
        """Test rate limit script is defined."""
        assert RedisLuaScripts.RATE_LIMIT_SLIDING_WINDOW
        assert "ZREMRANGEBYSCORE" in RedisLuaScripts.RATE_LIMIT_SLIDING_WINDOW
        assert "ZADD" in RedisLuaScripts.RATE_LIMIT_SLIDING_WINDOW

    def test_get_and_refresh_script_exists(self):
        """Test get-and-refresh script is defined."""
        assert RedisLuaScripts.GET_AND_REFRESH
        assert "EXPIRE" in RedisLuaScripts.GET_AND_REFRESH

    def test_queue_rotate_script_exists(self):
        """Test queue rotate script is defined."""
        assert RedisLuaScripts.QUEUE_ROTATE
        assert "LPOP" in RedisLuaScripts.QUEUE_ROTATE
        assert "RPUSH" in RedisLuaScripts.QUEUE_ROTATE

    def test_incr_with_expire_script_exists(self):
        """Test incr-with-expire script is defined."""
        assert RedisLuaScripts.INCR_WITH_EXPIRE
        assert "INCR" in RedisLuaScripts.INCR_WITH_EXPIRE
        assert "EXPIRE" in RedisLuaScripts.INCR_WITH_EXPIRE

    def test_hash_conditional_set_script_exists(self):
        """Test hash conditional set script is defined."""
        assert RedisLuaScripts.HASH_CONDITIONAL_SET
        assert "HGET" in RedisLuaScripts.HASH_CONDITIONAL_SET
        assert "HSET" in RedisLuaScripts.HASH_CONDITIONAL_SET

    def test_multi_key_set_script_exists(self):
        """Test multi-key set script is defined."""
        assert RedisLuaScripts.MULTI_KEY_SET
        assert "SETEX" in RedisLuaScripts.MULTI_KEY_SET

    def test_get_with_lock_script_exists(self):
        """Test get-with-lock script is defined."""
        assert RedisLuaScripts.GET_WITH_LOCK
        assert "NX" in RedisLuaScripts.GET_WITH_LOCK
        assert "EX" in RedisLuaScripts.GET_WITH_LOCK
