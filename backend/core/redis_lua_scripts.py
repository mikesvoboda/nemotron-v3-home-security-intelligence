"""Lua scripts for atomic Redis operations.

This module provides Lua scripts for complex atomic operations in Redis (NEM-3766).
Lua scripts execute atomically on the Redis server, ensuring consistency without
the need for distributed locks.

Benefits of Lua scripts:
- Atomicity: Multiple commands execute as a single atomic operation
- Performance: Reduces network round-trips for complex operations
- Consistency: No race conditions between read-modify-write operations

Usage:
    redis = await init_redis()
    scripts = RedisLuaScripts(redis)

    # Conditional increment
    result = await scripts.conditional_increment("counter", 5, max_value=100)

    # Rate limiting
    allowed = await scripts.rate_limit_check("user:123", limit=100, window=60)
"""

from dataclasses import dataclass
from typing import Any

from backend.core.logging import get_logger
from backend.core.redis import RedisClient

logger = get_logger(__name__)


class LuaScriptError(Exception):
    """Exception raised when a Lua script execution fails."""

    pass


@dataclass(slots=True)
class ConditionalUpdateResult:
    """Result of a conditional update operation."""

    success: bool
    old_value: Any | None
    new_value: Any | None
    condition_met: bool


@dataclass(slots=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    current_count: int
    remaining: int
    reset_at: int  # Unix timestamp


class RedisLuaScripts:
    """Collection of Lua scripts for atomic Redis operations.

    All scripts are loaded once and executed using EVALSHA for efficiency.
    Scripts are designed to be idempotent where possible.
    """

    # Script: Conditional increment with maximum value
    # Returns: [success, old_value, new_value]  # noqa: ERA001
    CONDITIONAL_INCREMENT = """
    local key = KEYS[1]
    local increment = tonumber(ARGV[1])
    local max_value = tonumber(ARGV[2])

    local current = tonumber(redis.call('GET', key) or '0')
    local new_value = current + increment

    if max_value > 0 and new_value > max_value then
        return {0, current, current}  -- Would exceed max, no change
    end

    redis.call('SET', key, new_value)
    return {1, current, new_value}
    """

    # Script: Conditional set if value matches expected
    # Returns: [success, old_value]  # noqa: ERA001
    COMPARE_AND_SET = """
    local key = KEYS[1]
    local expected = ARGV[1]
    local new_value = ARGV[2]
    local ttl = tonumber(ARGV[3])

    local current = redis.call('GET', key)

    if current == expected then
        if ttl > 0 then
            redis.call('SETEX', key, ttl, new_value)
        else
            redis.call('SET', key, new_value)
        end
        return {1, current}
    end

    return {0, current}
    """

    # Script: Sliding window rate limiter
    # Returns: [allowed, current_count, remaining, reset_at]  # noqa: ERA001
    RATE_LIMIT_SLIDING_WINDOW = """
    local key = KEYS[1]
    local limit = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])

    -- Remove expired entries
    local min_score = now - window
    redis.call('ZREMRANGEBYSCORE', key, '-inf', min_score)

    -- Count current requests in window
    local count = redis.call('ZCARD', key)

    if count >= limit then
        -- Rate limited
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local reset_at = now + window
        if #oldest > 1 then
            reset_at = tonumber(oldest[2]) + window
        end
        return {0, count, 0, reset_at}
    end

    -- Add current request
    redis.call('ZADD', key, now, now .. ':' .. math.random())
    redis.call('EXPIRE', key, window)

    return {1, count + 1, limit - count - 1, now + window}
    """

    # Script: Get and set with TTL refresh on access
    # Returns: [value, is_refreshed]  # noqa: ERA001
    GET_AND_REFRESH = """
    local key = KEYS[1]
    local ttl = tonumber(ARGV[1])

    local value = redis.call('GET', key)

    if value then
        redis.call('EXPIRE', key, ttl)
        return {value, 1}
    end

    return {nil, 0}
    """

    # Script: Atomic queue rotation (move items between queues)
    # Returns: [moved_count]  # noqa: ERA001
    QUEUE_ROTATE = """
    local source = KEYS[1]
    local dest = KEYS[2]
    local count = tonumber(ARGV[1])

    local moved = 0
    for i = 1, count do
        local item = redis.call('LPOP', source)
        if not item then
            break
        end
        redis.call('RPUSH', dest, item)
        moved = moved + 1
    end

    return moved
    """

    # Script: Increment with expiry (atomic INCR + EXPIRE)
    # Returns: new_value  # noqa: ERA001
    INCR_WITH_EXPIRE = """
    local key = KEYS[1]
    local ttl = tonumber(ARGV[1])

    local value = redis.call('INCR', key)
    if value == 1 then
        redis.call('EXPIRE', key, ttl)
    end

    return value
    """

    # Script: Hash field conditional update
    # Returns: [success, old_value, new_value]  # noqa: ERA001
    HASH_CONDITIONAL_SET = """
    local key = KEYS[1]
    local field = ARGV[1]
    local expected = ARGV[2]
    local new_value = ARGV[3]

    local current = redis.call('HGET', key, field)

    if current == expected or (current == false and expected == '') then
        redis.call('HSET', key, field, new_value)
        return {1, current or '', new_value}
    end

    return {0, current or '', current or ''}
    """

    # Script: Atomic multi-key update
    # Returns: updated_count  # noqa: ERA001
    MULTI_KEY_SET = """
    local ttl = tonumber(ARGV[1])
    local count = 0

    for i = 1, #KEYS do
        local key = KEYS[i]
        local value = ARGV[i + 1]
        if ttl > 0 then
            redis.call('SETEX', key, ttl, value)
        else
            redis.call('SET', key, value)
        end
        count = count + 1
    end

    return count
    """

    # Script: Cache stampede protection (get with lock and refresh)
    # Returns: [value, lock_acquired, cache_hit]  # noqa: ERA001
    GET_WITH_LOCK = """
    local cache_key = KEYS[1]
    local lock_key = KEYS[2]
    local lock_ttl = tonumber(ARGV[1])
    local lock_value = ARGV[2]

    -- Try to get cached value
    local value = redis.call('GET', cache_key)
    if value then
        return {value, 0, 1}  -- Cache hit, no lock needed
    end

    -- Try to acquire lock
    local lock_acquired = redis.call('SET', lock_key, lock_value, 'NX', 'EX', lock_ttl)
    if lock_acquired then
        return {nil, 1, 0}  -- No cache, lock acquired
    end

    return {nil, 0, 0}  -- No cache, lock not acquired (another request is loading)
    """

    def __init__(self, redis_client: RedisClient):
        """Initialize Lua scripts manager.

        Args:
            redis_client: Connected Redis client
        """
        self._redis = redis_client
        self._script_shas: dict[str, str] = {}

    async def _get_script_sha(self, script_name: str, script_body: str) -> str:
        """Get or load a script's SHA1 hash for EVALSHA.

        Args:
            script_name: Name of the script for caching
            script_body: The Lua script code

        Returns:
            SHA1 hash of the script
        """
        if script_name not in self._script_shas:
            client = self._redis._ensure_connected()
            sha = await client.script_load(script_body)
            self._script_shas[script_name] = sha
            logger.debug(f"Loaded Lua script '{script_name}': {sha}")
        return self._script_shas[script_name]

    async def _eval_script(
        self,
        script_name: str,
        script_body: str,
        keys: list[str],
        args: list[Any],
    ) -> Any:
        """Execute a Lua script.

        Args:
            script_name: Name of the script (for SHA caching)
            script_body: The Lua script code
            keys: List of Redis keys
            args: List of arguments

        Returns:
            Script execution result

        Raises:
            LuaScriptError: If script execution fails
        """
        client = self._redis._ensure_connected()

        try:
            # Try EVALSHA first (faster)
            sha: str = await self._get_script_sha(script_name, script_body)  # type: ignore[misc]
            return await client.evalsha(sha, len(keys), *keys, *args)  # type: ignore[misc]
        except Exception as e:
            # If NOSCRIPT, the script was flushed - reload and retry
            if "NOSCRIPT" in str(e):
                del self._script_shas[script_name]
                sha = await self._get_script_sha(script_name, script_body)  # type: ignore[misc]
                return await client.evalsha(sha, len(keys), *keys, *args)  # type: ignore[misc]
            raise LuaScriptError(f"Lua script '{script_name}' failed: {e}") from e

    async def conditional_increment(
        self,
        key: str,
        increment: int = 1,
        max_value: int = 0,
    ) -> ConditionalUpdateResult:
        """Atomically increment a counter with optional maximum value.

        Args:
            key: Redis key
            increment: Amount to increment by
            max_value: Maximum allowed value (0 = no limit)

        Returns:
            ConditionalUpdateResult with success and values
        """
        result = await self._eval_script(
            "conditional_increment",
            self.CONDITIONAL_INCREMENT,
            keys=[key],
            args=[increment, max_value],
        )

        return ConditionalUpdateResult(
            success=bool(result[0]),
            old_value=result[1],
            new_value=result[2],
            condition_met=bool(result[0]),
        )

    async def compare_and_set(
        self,
        key: str,
        expected: str | None,
        new_value: str,
        ttl: int = 0,
    ) -> ConditionalUpdateResult:
        """Atomically set value only if current value matches expected.

        Args:
            key: Redis key
            expected: Expected current value (None for "key doesn't exist")
            new_value: Value to set if condition is met
            ttl: Optional TTL in seconds

        Returns:
            ConditionalUpdateResult with success and values
        """
        expected_str = expected if expected is not None else ""
        result = await self._eval_script(
            "compare_and_set",
            self.COMPARE_AND_SET,
            keys=[key],
            args=[expected_str, new_value, ttl],
        )

        old_value = result[1] if result[1] else None
        return ConditionalUpdateResult(
            success=bool(result[0]),
            old_value=old_value,
            new_value=new_value if result[0] else old_value,
            condition_met=bool(result[0]),
        )

    async def rate_limit_check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        """Check rate limit using sliding window algorithm.

        Args:
            key: Rate limit key (e.g., "ratelimit:user:123")
            limit: Maximum requests allowed in window
            window: Time window in seconds

        Returns:
            RateLimitResult with allowed status and metadata
        """
        import time

        now = int(time.time())
        result = await self._eval_script(
            "rate_limit_sliding_window",
            self.RATE_LIMIT_SLIDING_WINDOW,
            keys=[key],
            args=[limit, window, now],
        )

        return RateLimitResult(
            allowed=bool(result[0]),
            current_count=int(result[1]),
            remaining=int(result[2]),
            reset_at=int(result[3]),
        )

    async def get_and_refresh(self, key: str, ttl: int) -> tuple[Any | None, bool]:
        """Get value and refresh TTL atomically.

        Useful for cache entries that should be refreshed on access.

        Args:
            key: Redis key
            ttl: New TTL to set on access

        Returns:
            Tuple of (value, was_refreshed)
        """
        result = await self._eval_script(
            "get_and_refresh",
            self.GET_AND_REFRESH,
            keys=[key],
            args=[ttl],
        )

        return result[0], bool(result[1])

    async def queue_rotate(
        self,
        source_queue: str,
        dest_queue: str,
        count: int,
    ) -> int:
        """Atomically move items from one queue to another.

        Args:
            source_queue: Source list key
            dest_queue: Destination list key
            count: Maximum items to move

        Returns:
            Number of items actually moved
        """
        result = await self._eval_script(
            "queue_rotate",
            self.QUEUE_ROTATE,
            keys=[source_queue, dest_queue],
            args=[count],
        )

        return int(result)

    async def incr_with_expire(self, key: str, ttl: int) -> int:
        """Atomically increment and set expiry (only on first increment).

        Useful for counters that should auto-expire.

        Args:
            key: Redis key
            ttl: TTL in seconds (set only when counter is created)

        Returns:
            New counter value
        """
        result = await self._eval_script(
            "incr_with_expire",
            self.INCR_WITH_EXPIRE,
            keys=[key],
            args=[ttl],
        )

        return int(result)

    async def hash_conditional_set(
        self,
        key: str,
        field: str,
        expected: str,
        new_value: str,
    ) -> ConditionalUpdateResult:
        """Atomically update hash field only if it matches expected value.

        Args:
            key: Hash key
            field: Field name
            expected: Expected field value (empty string for "field doesn't exist")
            new_value: New value to set

        Returns:
            ConditionalUpdateResult with success and values
        """
        result = await self._eval_script(
            "hash_conditional_set",
            self.HASH_CONDITIONAL_SET,
            keys=[key],
            args=[field, expected, new_value],
        )

        return ConditionalUpdateResult(
            success=bool(result[0]),
            old_value=result[1] or None,
            new_value=result[2] or None,
            condition_met=bool(result[0]),
        )

    async def multi_key_set(
        self,
        key_value_pairs: dict[str, str],
        ttl: int = 0,
    ) -> int:
        """Atomically set multiple keys with optional TTL.

        Args:
            key_value_pairs: Dictionary of key -> value
            ttl: Optional TTL in seconds (0 = no expiry)

        Returns:
            Number of keys set
        """
        keys = list(key_value_pairs.keys())
        args = [ttl, *list(key_value_pairs.values())]

        result = await self._eval_script(
            "multi_key_set",
            self.MULTI_KEY_SET,
            keys=keys,
            args=args,
        )

        return int(result)

    async def get_with_lock(
        self,
        cache_key: str,
        lock_key: str,
        lock_ttl: int = 30,
    ) -> tuple[Any | None, bool, bool]:
        """Get cached value or acquire lock for population.

        Implements cache stampede protection in a single atomic operation.

        Args:
            cache_key: Key for the cached value
            lock_key: Key for the distributed lock
            lock_ttl: Lock TTL in seconds

        Returns:
            Tuple of (cached_value, lock_acquired, cache_hit)
        """
        import uuid

        lock_value = str(uuid.uuid4())
        result = await self._eval_script(
            "get_with_lock",
            self.GET_WITH_LOCK,
            keys=[cache_key, lock_key],
            args=[lock_ttl, lock_value],
        )

        return result[0], bool(result[1]), bool(result[2])


# Singleton instance
_lua_scripts: RedisLuaScripts | None = None


async def get_lua_scripts() -> RedisLuaScripts:
    """Get or create the Lua scripts singleton.

    Returns:
        RedisLuaScripts instance
    """
    global _lua_scripts  # noqa: PLW0603
    if _lua_scripts is None:
        from backend.core.redis import init_redis

        redis = await init_redis()
        _lua_scripts = RedisLuaScripts(redis)
    return _lua_scripts


async def reset_lua_scripts() -> None:
    """Reset the Lua scripts singleton (for testing)."""
    global _lua_scripts  # noqa: PLW0603
    _lua_scripts = None
