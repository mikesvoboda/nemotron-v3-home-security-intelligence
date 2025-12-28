"""Unit tests for Redis connection and operations."""

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from backend.core.redis import (
    QueueAddResult,
    QueueOverflowPolicy,
    RedisClient,
    close_redis,
    get_redis,
    init_redis,
)

# Check if fakeredis is available for integration-style tests
try:
    import fakeredis.aioredis as fakeredis

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

# Fixtures


@pytest.fixture
def mock_redis_pool():
    """Mock Redis connection pool."""
    with patch("backend.core.redis.ConnectionPool") as mock_pool_class:
        # Create a mock instance that will be returned by from_url()
        mock_pool_instance = AsyncMock()
        mock_pool_instance.disconnect = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool_instance
        yield mock_pool_class


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with common operations."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    mock_client.info = AsyncMock(return_value={"redis_version": "7.0.0", "uptime_in_seconds": 3600})
    mock_client.rpush = AsyncMock(return_value=1)
    mock_client.ltrim = AsyncMock(return_value=True)
    mock_client.blpop = AsyncMock(return_value=None)
    mock_client.lpop = AsyncMock(return_value=None)  # Added for backpressure tests
    mock_client.llen = AsyncMock(return_value=0)
    mock_client.lrange = AsyncMock(return_value=[])
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.pubsub = MagicMock()
    return mock_client


@pytest.fixture
async def redis_client(mock_redis_pool, mock_redis_client):
    """Create a Redis client with mocked connection."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(redis_url="redis://localhost:6379/0")
        await client.connect()
        yield client
        await client.disconnect()


# Connection Tests


@pytest.mark.asyncio
async def test_redis_connection_success(mock_redis_pool, mock_redis_client):
    """Test successful Redis connection."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient()
        await client.connect()

        assert client._client is not None
        mock_redis_client.ping.assert_awaited_once()

        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connection_retry(mock_redis_pool):
    """Test Redis connection retry logic on failure."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(side_effect=[ConnectionError(), ConnectionError(), True])
    mock_client.close = AsyncMock()

    with patch("backend.core.redis.Redis", return_value=mock_client):
        client = RedisClient()
        client._base_delay = 0.01  # Speed up test
        client._max_delay = 0.1  # Speed up test
        await client.connect()

        # Should have retried 3 times
        assert mock_client.ping.await_count == 3
        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connection_failure_after_retries(mock_redis_pool):
    """Test Redis connection failure after all retries."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection failed"))
    mock_client.close = AsyncMock()

    with patch("backend.core.redis.Redis", return_value=mock_client):
        client = RedisClient()
        client._base_delay = 0.01  # Speed up test
        client._max_delay = 0.1  # Speed up test

        with pytest.raises(ConnectionError):
            await client.connect()


@pytest.mark.asyncio
async def test_redis_disconnect(redis_client):
    """Test Redis disconnection."""
    await redis_client.disconnect()

    assert redis_client._client is None
    assert redis_client._pool is None
    assert redis_client._pubsub is None


# Exponential Backoff Tests


def test_calculate_backoff_delay_first_attempt():
    """Test backoff delay calculation for first attempt."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.0  # Disable jitter for deterministic test

    delay = client._calculate_backoff_delay(1)

    # First attempt: 1.0 * 2^0 = 1.0
    assert delay == 1.0


def test_calculate_backoff_delay_second_attempt():
    """Test backoff delay calculation for second attempt."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.0  # Disable jitter for deterministic test

    delay = client._calculate_backoff_delay(2)

    # Second attempt: 1.0 * 2^1 = 2.0
    assert delay == 2.0


def test_calculate_backoff_delay_third_attempt():
    """Test backoff delay calculation for third attempt."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.0  # Disable jitter for deterministic test

    delay = client._calculate_backoff_delay(3)

    # Third attempt: 1.0 * 2^2 = 4.0
    assert delay == 4.0


def test_calculate_backoff_delay_exponential_growth():
    """Test that backoff delay grows exponentially."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 100.0  # High cap to test growth
    client._jitter_factor = 0.0  # Disable jitter for deterministic test

    delays = [client._calculate_backoff_delay(i) for i in range(1, 7)]

    # Expected: 1, 2, 4, 8, 16, 32
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]


def test_calculate_backoff_delay_max_cap():
    """Test that backoff delay is capped at max_delay."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.0  # Disable jitter for deterministic test

    # Attempt 6 would be 32s without cap, but should be capped at 30s
    delay = client._calculate_backoff_delay(6)

    assert delay == 30.0


def test_calculate_backoff_delay_max_cap_with_high_attempts():
    """Test that backoff delay stays capped for very high attempt numbers."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.0  # Disable jitter for deterministic test

    # Even at attempt 100, delay should be capped
    delay = client._calculate_backoff_delay(100)

    assert delay == 30.0


def test_calculate_backoff_delay_with_jitter():
    """Test that backoff delay includes jitter within expected range."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.25  # 25% jitter

    # Run multiple times to verify jitter behavior
    delays = [client._calculate_backoff_delay(1) for _ in range(100)]

    # Base delay is 1.0, jitter adds 0-25% (0-0.25s)
    # So delay should be between 1.0 and 1.25
    assert all(1.0 <= d <= 1.25 for d in delays)
    # Verify there's some variation (jitter is working)
    assert len(set(delays)) > 1  # Not all delays are identical


def test_calculate_backoff_delay_with_jitter_second_attempt():
    """Test that jitter scales with delay for second attempt."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.25  # 25% jitter

    delays = [client._calculate_backoff_delay(2) for _ in range(100)]

    # Base delay is 2.0, jitter adds 0-25% (0-0.5s)
    # So delay should be between 2.0 and 2.5
    assert all(2.0 <= d <= 2.5 for d in delays)


def test_calculate_backoff_delay_jitter_range_at_max():
    """Test that jitter is applied correctly when delay hits max cap."""
    client = RedisClient()
    client._base_delay = 1.0
    client._max_delay = 30.0
    client._jitter_factor = 0.25  # 25% jitter

    delays = [client._calculate_backoff_delay(10) for _ in range(100)]

    # Base delay is capped at 30.0, jitter adds 0-25% (0-7.5s)
    # So delay should be between 30.0 and 37.5
    assert all(30.0 <= d <= 37.5 for d in delays)


def test_calculate_backoff_delay_custom_base_delay():
    """Test backoff with custom base delay."""
    client = RedisClient()
    client._base_delay = 0.5
    client._max_delay = 30.0
    client._jitter_factor = 0.0

    delays = [client._calculate_backoff_delay(i) for i in range(1, 5)]

    # Expected: 0.5, 1.0, 2.0, 4.0
    assert delays == [0.5, 1.0, 2.0, 4.0]


def test_default_backoff_settings():
    """Test that default backoff settings are as expected."""
    client = RedisClient()

    assert client._base_delay == 1.0
    assert client._max_delay == 30.0
    assert client._jitter_factor == 0.25


@pytest.mark.asyncio
async def test_ensure_connected_raises_when_not_connected():
    """Test that operations raise RuntimeError when not connected."""
    client = RedisClient()

    with pytest.raises(RuntimeError, match="Redis client not connected"):
        client._ensure_connected()


# Health Check Tests


@pytest.mark.asyncio
async def test_health_check_success(redis_client, mock_redis_client):
    """Test health check when Redis is healthy."""
    health = await redis_client.health_check()

    assert health["status"] == "healthy"
    assert health["connected"] is True
    assert "redis_version" in health
    mock_redis_client.ping.assert_awaited()


@pytest.mark.asyncio
async def test_health_check_failure(redis_client, mock_redis_client):
    """Test health check when Redis is unhealthy."""
    mock_redis_client.ping.side_effect = ConnectionError("Connection lost")

    health = await redis_client.health_check()

    assert health["status"] == "unhealthy"
    assert health["connected"] is False
    assert "error" in health


# Queue Operation Tests


@pytest.mark.asyncio
async def test_add_to_queue_with_dict(redis_client, mock_redis_client):
    """Test adding a dictionary to a queue (default: no trimming)."""
    mock_redis_client.rpush.return_value = 1

    data = {"key": "value", "number": 42}
    result = await redis_client.add_to_queue("test_queue", data)

    assert result == 1
    mock_redis_client.rpush.assert_awaited_once()
    # Verify JSON serialization happened
    call_args = mock_redis_client.rpush.call_args[0]
    assert call_args[0] == "test_queue"
    assert '"key": "value"' in call_args[1]
    # By default, no trimming (backpressure=DISABLED)
    mock_redis_client.ltrim.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_to_queue_with_string(redis_client, mock_redis_client):
    """Test adding a string to a queue (default: no trimming)."""
    mock_redis_client.rpush.return_value = 2

    result = await redis_client.add_to_queue("test_queue", "simple_string")

    assert result == 2
    mock_redis_client.rpush.assert_awaited_once_with("test_queue", "simple_string")
    # By default, no trimming (backpressure=DISABLED)
    mock_redis_client.ltrim.assert_not_awaited()


@pytest.mark.skip(
    reason="API changed - add_to_queue_safe returns QueueAddResult, needs test rewrite"
)
@pytest.mark.asyncio
async def test_add_to_queue_with_drop_oldest_trims(redis_client, mock_redis_client):
    """Test adding to a queue with DROP_OLDEST strategy trims when over max_size."""
    mock_redis_client.rpush.return_value = 600  # Simulates queue over limit

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=500, overflow_policy=QueueOverflowPolicy.DROP_OLDEST
    )

    assert result == 500  # Returns trimmed size
    mock_redis_client.ltrim.assert_awaited_once_with("test_queue", -500, -1)


@pytest.mark.skip(
    reason="API changed - add_to_queue_safe returns QueueAddResult, needs test rewrite"
)
@pytest.mark.asyncio
async def test_add_to_queue_with_drop_oldest_no_trim_under_limit(redis_client, mock_redis_client):
    """Test DROP_OLDEST doesn't trim when queue is under max_size."""
    mock_redis_client.rpush.return_value = 100  # Under limit

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=500, overflow_policy=QueueOverflowPolicy.DROP_OLDEST
    )

    assert result == 100
    mock_redis_client.ltrim.assert_not_awaited()


@pytest.mark.skip(
    reason="API changed - add_to_queue_safe returns QueueAddResult, needs test rewrite"
)
@pytest.mark.asyncio
async def test_add_to_queue_disabled_skips_ltrim(redis_client, mock_redis_client):
    """Test that DISABLED backpressure skips trimming regardless of max_size."""
    mock_redis_client.rpush.return_value = 1

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=500, overflow_policy=QueueOverflowPolicy.REJECT
    )

    assert result == 1
    mock_redis_client.rpush.assert_awaited_once()
    # ltrim should NOT be called when backpressure=DISABLED
    mock_redis_client.ltrim.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_to_queue_safe_returns_detailed_result(redis_client, mock_redis_client):
    """Test add_to_queue_safe returns QueueAddResult with details."""
    mock_redis_client.rpush.return_value = 5

    result = await redis_client.add_to_queue_safe("test_queue", {"data": "value"})

    assert isinstance(result, QueueAddResult)
    assert result.queue_length == 5
    assert result.items_dropped == 0
    assert result.was_rejected is False


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_oldest_reports_dropped(redis_client, mock_redis_client):
    """Test DROP_OLDEST strategy reports how many items were dropped."""
    mock_redis_client.rpush.return_value = 105  # 5 over the limit

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=100, overflow_policy=QueueOverflowPolicy.DROP_OLDEST
    )

    assert result.queue_length == 100
    assert result.items_dropped == 5
    assert result.was_rejected is False


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_newest_rejects_when_full(redis_client, mock_redis_client):
    """Test DROP_NEWEST strategy rejects items when queue is full."""
    mock_redis_client.llen.return_value = 100  # Queue at capacity

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=100, overflow_policy=QueueOverflowPolicy.REJECT
    )

    assert result.queue_length == 100
    assert result.items_dropped == 0
    assert result.was_rejected is True
    # rpush should NOT be called when rejected
    mock_redis_client.rpush.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_newest_accepts_when_space(redis_client, mock_redis_client):
    """Test DROP_NEWEST strategy accepts items when queue has space."""
    mock_redis_client.llen.return_value = 50  # Queue has space
    mock_redis_client.rpush.return_value = 51

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=100, overflow_policy=QueueOverflowPolicy.REJECT
    )

    assert result.queue_length == 51
    assert result.items_dropped == 0
    assert result.was_rejected is False
    mock_redis_client.rpush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_from_queue_with_data(redis_client, mock_redis_client):
    """Test getting data from a queue."""
    mock_redis_client.blpop.return_value = ("test_queue", '{"key": "value"}')

    result = await redis_client.get_from_queue("test_queue", timeout=5)

    assert result == {"key": "value"}
    mock_redis_client.blpop.assert_awaited_once_with(["test_queue"], timeout=5)


@pytest.mark.asyncio
async def test_get_from_queue_empty(redis_client, mock_redis_client):
    """Test getting from an empty queue."""
    mock_redis_client.blpop.return_value = None

    result = await redis_client.get_from_queue("test_queue", timeout=1)

    assert result is None


@pytest.mark.asyncio
async def test_get_from_queue_plain_string(redis_client, mock_redis_client):
    """Test getting a plain string from queue (not JSON)."""
    mock_redis_client.blpop.return_value = ("test_queue", "plain_string")

    result = await redis_client.get_from_queue("test_queue")

    assert result == "plain_string"


@pytest.mark.asyncio
async def test_get_queue_length(redis_client, mock_redis_client):
    """Test getting queue length."""
    mock_redis_client.llen.return_value = 5

    length = await redis_client.get_queue_length("test_queue")

    assert length == 5
    mock_redis_client.llen.assert_awaited_once_with("test_queue")


@pytest.mark.asyncio
async def test_peek_queue(redis_client, mock_redis_client):
    """Test peeking at queue items."""
    mock_redis_client.lrange.return_value = [
        '{"id": 1}',
        '{"id": 2}',
        "plain_string",
    ]

    items = await redis_client.peek_queue("test_queue", start=0, end=2)

    assert len(items) == 3
    assert items[0] == {"id": 1}
    assert items[1] == {"id": 2}
    assert items[2] == "plain_string"
    mock_redis_client.lrange.assert_awaited_once_with("test_queue", 0, 2)


@pytest.mark.asyncio
async def test_peek_queue_default_limit(redis_client, mock_redis_client):
    """Test peek_queue uses default end=100 instead of full queue."""
    mock_redis_client.lrange.return_value = []

    await redis_client.peek_queue("test_queue")

    # Default end should be 100, not -1 (which would fetch entire queue)
    mock_redis_client.lrange.assert_awaited_once_with("test_queue", 0, 100)


@pytest.mark.asyncio
async def test_peek_queue_end_minus_one_uses_max_items(redis_client, mock_redis_client):
    """Test peek_queue with end=-1 uses max_items cap."""
    mock_redis_client.lrange.return_value = []

    await redis_client.peek_queue("test_queue", start=0, end=-1)

    # end=-1 should convert to max_items - 1 = 999
    mock_redis_client.lrange.assert_awaited_once_with("test_queue", 0, 999)


@pytest.mark.asyncio
async def test_peek_queue_custom_max_items(redis_client, mock_redis_client):
    """Test peek_queue with custom max_items."""
    mock_redis_client.lrange.return_value = []

    await redis_client.peek_queue("test_queue", start=0, end=-1, max_items=500)

    # end=-1 with max_items=500 should convert to 499
    mock_redis_client.lrange.assert_awaited_once_with("test_queue", 0, 499)


@pytest.mark.asyncio
async def test_peek_queue_end_capped_by_max_items(redis_client, mock_redis_client):
    """Test peek_queue caps end at start + max_items - 1."""
    mock_redis_client.lrange.return_value = []

    # Request more items than max_items allows
    await redis_client.peek_queue("test_queue", start=0, end=2000, max_items=1000)

    # end should be capped at 999 (start + max_items - 1)
    mock_redis_client.lrange.assert_awaited_once_with("test_queue", 0, 999)


@pytest.mark.asyncio
async def test_peek_queue_with_offset_and_max_items(redis_client, mock_redis_client):
    """Test peek_queue handles start offset correctly with max_items."""
    mock_redis_client.lrange.return_value = []

    await redis_client.peek_queue("test_queue", start=100, end=5000, max_items=1000)

    # end should be capped at 1099 (start=100 + max_items=1000 - 1)
    mock_redis_client.lrange.assert_awaited_once_with("test_queue", 100, 1099)


@pytest.mark.asyncio
async def test_clear_queue(redis_client, mock_redis_client):
    """Test clearing a queue."""
    mock_redis_client.delete.return_value = 1

    result = await redis_client.clear_queue("test_queue")

    assert result is True
    mock_redis_client.delete.assert_awaited_once_with("test_queue")


@pytest.mark.asyncio
async def test_clear_nonexistent_queue(redis_client, mock_redis_client):
    """Test clearing a queue that doesn't exist."""
    mock_redis_client.delete.return_value = 0

    result = await redis_client.clear_queue("nonexistent_queue")

    assert result is False


# Pub/Sub Tests


@pytest.mark.asyncio
async def test_publish_message(redis_client, mock_redis_client):
    """Test publishing a message to a channel."""
    mock_redis_client.publish.return_value = 2

    result = await redis_client.publish("test_channel", {"event": "test"})

    assert result == 2
    mock_redis_client.publish.assert_awaited_once()
    call_args = mock_redis_client.publish.call_args[0]
    assert call_args[0] == "test_channel"
    assert '"event": "test"' in call_args[1]


@pytest.mark.asyncio
async def test_subscribe_to_channel(redis_client, mock_redis_client):
    """Test subscribing to a channel."""
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_redis_client.pubsub.return_value = mock_pubsub

    pubsub = await redis_client.subscribe("test_channel", "another_channel")

    assert pubsub is not None
    mock_pubsub.subscribe.assert_awaited_once_with("test_channel", "another_channel")


@pytest.mark.asyncio
async def test_unsubscribe_from_channel(redis_client, mock_redis_client):
    """Test unsubscribing from a channel."""
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_redis_client.pubsub.return_value = mock_pubsub

    # First subscribe
    await redis_client.subscribe("test_channel")

    # Then unsubscribe
    await redis_client.unsubscribe("test_channel")

    mock_pubsub.unsubscribe.assert_awaited_once_with("test_channel")


@pytest.mark.asyncio
async def test_listen_to_messages(redis_client, mock_redis_client):
    """Test listening for messages from subscribed channels."""
    mock_pubsub = AsyncMock()

    # Simulate message stream
    async def mock_listen():
        messages = [
            {"type": "subscribe", "channel": "test_channel"},
            {"type": "message", "channel": "test_channel", "data": '{"event": "test"}'},
            {"type": "message", "channel": "test_channel", "data": "plain_text"},
        ]
        for msg in messages:
            yield msg

    mock_pubsub.listen = mock_listen
    mock_redis_client.pubsub.return_value = mock_pubsub

    messages = []
    async for msg in redis_client.listen(mock_pubsub):
        messages.append(msg)

    # Should only get "message" type, not "subscribe"
    assert len(messages) == 2
    assert messages[0]["data"] == {"event": "test"}
    assert messages[1]["data"] == "plain_text"


# Cache Operation Tests


@pytest.mark.asyncio
async def test_cache_get(redis_client, mock_redis_client):
    """Test getting a value from cache."""
    mock_redis_client.get.return_value = '{"key": "value"}'

    result = await redis_client.get("cache_key")

    assert result == {"key": "value"}
    mock_redis_client.get.assert_awaited_once_with("cache_key")


@pytest.mark.asyncio
async def test_cache_get_nonexistent(redis_client, mock_redis_client):
    """Test getting a non-existent cache key."""
    mock_redis_client.get.return_value = None

    result = await redis_client.get("nonexistent_key")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_with_expiry(redis_client, mock_redis_client):
    """Test setting a cache value with expiration."""
    mock_redis_client.set.return_value = True

    result = await redis_client.set("cache_key", {"data": "value"}, expire=300)

    assert result is True
    mock_redis_client.set.assert_awaited_once()
    call_args = mock_redis_client.set.call_args
    assert call_args[0][0] == "cache_key"
    assert call_args[1]["ex"] == 300


@pytest.mark.asyncio
async def test_cache_delete(redis_client, mock_redis_client):
    """Test deleting cache keys."""
    mock_redis_client.delete.return_value = 2

    result = await redis_client.delete("key1", "key2")

    assert result == 2
    mock_redis_client.delete.assert_awaited_once_with("key1", "key2")


@pytest.mark.asyncio
async def test_cache_exists(redis_client, mock_redis_client):
    """Test checking if keys exist."""
    mock_redis_client.exists.return_value = 1

    result = await redis_client.exists("key1", "key2")

    assert result == 1
    mock_redis_client.exists.assert_awaited_once_with("key1", "key2")


# TTL / Expire Operation Tests


@pytest.mark.asyncio
async def test_expire_sets_ttl_on_key(redis_client, mock_redis_client):
    """Test setting TTL on a key."""
    mock_redis_client.expire = AsyncMock(return_value=True)

    result = await redis_client.expire("test_key", 3600)

    assert result is True
    mock_redis_client.expire.assert_awaited_once_with("test_key", 3600)


@pytest.mark.asyncio
async def test_expire_returns_false_for_nonexistent_key(redis_client, mock_redis_client):
    """Test expire returns False for non-existent key."""
    mock_redis_client.expire = AsyncMock(return_value=False)

    result = await redis_client.expire("nonexistent_key", 3600)

    assert result is False
    mock_redis_client.expire.assert_awaited_once_with("nonexistent_key", 3600)


@pytest.mark.asyncio
async def test_expire_with_short_ttl(redis_client, mock_redis_client):
    """Test setting a short TTL (e.g., for testing expiration)."""
    mock_redis_client.expire = AsyncMock(return_value=True)

    result = await redis_client.expire("test_key", 1)

    assert result is True
    mock_redis_client.expire.assert_awaited_once_with("test_key", 1)


# Dependency Injection Tests


@pytest.mark.asyncio
async def test_get_redis_dependency(mock_redis_pool, mock_redis_client):
    """Test get_redis FastAPI dependency."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        # Simulate FastAPI dependency injection
        redis_generator = get_redis()
        client = await anext(redis_generator)

        assert isinstance(client, RedisClient)
        assert client._client is not None

        # Cleanup
        with contextlib.suppress(StopAsyncIteration):
            await redis_generator.asend(None)

        # Cleanup global state
        await close_redis()


@pytest.mark.asyncio
async def test_init_redis_creates_global_client(mock_redis_pool, mock_redis_client):
    """Test init_redis creates and returns global client."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = await init_redis()

        assert isinstance(client, RedisClient)
        assert client._client is not None
        mock_redis_client.ping.assert_awaited()

        # Cleanup
        await close_redis()


@pytest.mark.asyncio
async def test_close_redis_cleans_up_global_client(mock_redis_pool, mock_redis_client):
    """Test close_redis properly cleans up global client."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        await init_redis()
        await close_redis()

        mock_redis_client.close.assert_awaited()


# Integration-style tests using fakeredis (no real Redis required)


@pytest.fixture
def fake_redis_server():
    """Create a fake Redis server for integration-style tests."""
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not installed")
@pytest.mark.asyncio
async def test_redis_integration_queue_operations():
    """Integration-style test for queue operations using fakeredis."""
    # Create a fake Redis client that mimics real behavior
    fake_server = fakeredis.FakeRedis(decode_responses=True)

    # Create our RedisClient and inject the fake client
    client = RedisClient(redis_url="redis://localhost:6379/15")
    client._client = fake_server
    client._pool = MagicMock()  # Mock pool to avoid None checks

    # Test queue operations
    queue_name = "test_integration_queue"

    # Clear any existing data
    await client.clear_queue(queue_name)

    # Add items
    await client.add_to_queue(queue_name, {"id": 1, "data": "test1"})
    await client.add_to_queue(queue_name, {"id": 2, "data": "test2"})

    # Check length
    length = await client.get_queue_length(queue_name)
    assert length == 2

    # Peek at items
    items = await client.peek_queue(queue_name)
    assert len(items) == 2

    # Get items (use lpop instead of blpop since fakeredis blpop behaves differently)
    # We'll test this via direct queue access
    item1_raw = await fake_server.lpop(queue_name)
    item1 = json.loads(item1_raw)
    assert item1["id"] == 1

    item2_raw = await fake_server.lpop(queue_name)
    item2 = json.loads(item2_raw)
    assert item2["id"] == 2

    # Queue should be empty
    length = await client.get_queue_length(queue_name)
    assert length == 0

    # Cleanup
    await client.clear_queue(queue_name)

    # Close fake server
    await fake_server.aclose()


@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not installed")
@pytest.mark.asyncio
async def test_redis_integration_cache_operations():
    """Integration-style test for cache operations using fakeredis."""
    # Create a fake Redis client that mimics real behavior
    fake_server = fakeredis.FakeRedis(decode_responses=True)

    # Create our RedisClient and inject the fake client
    client = RedisClient(redis_url="redis://localhost:6379/15")
    client._client = fake_server
    client._pool = MagicMock()  # Mock pool to avoid None checks

    # Test cache operations
    key = "test_integration_cache_key"

    # Set value
    await client.set(key, {"data": "test_value"}, expire=60)

    # Get value
    value = await client.get(key)
    assert value["data"] == "test_value"

    # Check exists
    exists = await client.exists(key)
    assert exists == 1

    # Delete
    deleted = await client.delete(key)
    assert deleted == 1

    # Verify deleted
    value = await client.get(key)
    assert value is None

    # Close fake server
    await fake_server.aclose()


# Backpressure Tests


@pytest.mark.asyncio
async def test_add_to_queue_logs_warning_on_overflow(redis_client, mock_redis_client, caplog):
    """Test that add_to_queue logs warning when trimming occurs."""
    # Setup: queue already at max capacity, rpush returns count exceeding max
    mock_redis_client.llen.return_value = 10
    mock_redis_client.rpush.return_value = 11  # One more than max

    import logging

    with caplog.at_level(logging.WARNING):
        result = await redis_client.add_to_queue("test_queue", "data", max_size=10)

    assert result == 11
    mock_redis_client.ltrim.assert_awaited_once()
    # Check that warning was logged
    assert any("overflow" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_add_to_queue_safe_reject_policy(redis_client, mock_redis_client):
    """Test add_to_queue_safe rejects items when queue is full with REJECT policy."""
    mock_redis_client.llen.return_value = 10  # Queue is at max

    from backend.core.redis import QueueAddResult, QueueOverflowPolicy

    result = await redis_client.add_to_queue_safe(
        "test_queue",
        {"data": "test"},
        max_size=10,
        overflow_policy=QueueOverflowPolicy.REJECT,
    )

    assert isinstance(result, QueueAddResult)
    assert result.success is False
    assert result.error is not None
    assert "full" in result.error.lower()
    assert result.queue_length == 10
    # rpush should NOT be called when rejecting
    mock_redis_client.rpush.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_to_queue_safe_dlq_policy(redis_client, mock_redis_client):
    """Test add_to_queue_safe moves items to DLQ when queue is full with DLQ policy."""
    mock_redis_client.llen.return_value = 10  # Queue is at max
    mock_redis_client.lpop.return_value = '{"old": "data"}'  # Oldest item
    mock_redis_client.rpush.return_value = 10  # Length after operations

    from backend.core.redis import QueueAddResult, QueueOverflowPolicy

    result = await redis_client.add_to_queue_safe(
        "test_queue",
        {"data": "test"},
        max_size=10,
        overflow_policy=QueueOverflowPolicy.DLQ,
    )

    assert isinstance(result, QueueAddResult)
    assert result.success is True
    assert result.moved_to_dlq_count == 1
    assert result.warning is not None
    # Should have called lpop to remove oldest
    mock_redis_client.lpop.assert_awaited()
    # Should have called rpush twice - once for DLQ, once for new item
    assert mock_redis_client.rpush.await_count == 2


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_oldest_policy(redis_client, mock_redis_client):
    """Test add_to_queue_safe drops oldest items with DROP_OLDEST policy."""
    mock_redis_client.llen.return_value = 10  # Queue is at max
    mock_redis_client.rpush.return_value = 11  # One more than max after push

    from backend.core.redis import QueueAddResult, QueueOverflowPolicy

    result = await redis_client.add_to_queue_safe(
        "test_queue",
        {"data": "test"},
        max_size=10,
        overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
    )

    assert isinstance(result, QueueAddResult)
    assert result.success is True
    assert result.dropped_count == 1
    assert result.warning is not None
    # Should have called ltrim to drop oldest
    mock_redis_client.ltrim.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_to_queue_safe_normal_add(redis_client, mock_redis_client):
    """Test add_to_queue_safe adds normally when queue has space."""
    mock_redis_client.llen.return_value = 5  # Queue has space
    mock_redis_client.rpush.return_value = 6

    from backend.core.redis import QueueAddResult, QueueOverflowPolicy

    result = await redis_client.add_to_queue_safe(
        "test_queue",
        {"data": "test"},
        max_size=10,
        overflow_policy=QueueOverflowPolicy.REJECT,
    )

    assert isinstance(result, QueueAddResult)
    assert result.success is True
    assert result.queue_length == 6
    assert result.dropped_count == 0
    assert result.moved_to_dlq_count == 0
    assert result.error is None
    assert result.warning is None
    assert result.had_backpressure is False


@pytest.mark.asyncio
async def test_add_to_queue_safe_pressure_warning(redis_client, mock_redis_client, caplog):
    """Test add_to_queue_safe logs warning when approaching threshold."""
    # 91% full (above default 90% threshold)
    mock_redis_client.llen.return_value = 91
    mock_redis_client.rpush.return_value = 92

    import logging

    from backend.core.redis import QueueOverflowPolicy

    with caplog.at_level(logging.WARNING):
        result = await redis_client.add_to_queue_safe(
            "test_queue",
            {"data": "test"},
            max_size=100,
            overflow_policy=QueueOverflowPolicy.REJECT,
        )

    assert result.success is True
    # Check that pressure warning was logged
    assert any("pressure" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_add_to_queue_safe_string_policy(redis_client, mock_redis_client):
    """Test add_to_queue_safe accepts string policy."""
    mock_redis_client.llen.return_value = 10  # Queue is at max

    from backend.core.redis import QueueAddResult

    result = await redis_client.add_to_queue_safe(
        "test_queue",
        {"data": "test"},
        max_size=10,
        overflow_policy="reject",  # String instead of enum
    )

    assert isinstance(result, QueueAddResult)
    assert result.success is False


@pytest.mark.asyncio
async def test_add_to_queue_safe_invalid_policy_defaults_to_reject(redis_client, mock_redis_client):
    """Test add_to_queue_safe defaults to REJECT for invalid policy."""
    mock_redis_client.llen.return_value = 10  # Queue is at max

    from backend.core.redis import QueueAddResult

    result = await redis_client.add_to_queue_safe(
        "test_queue",
        {"data": "test"},
        max_size=10,
        overflow_policy="invalid_policy",
    )

    assert isinstance(result, QueueAddResult)
    assert result.success is False  # Should behave like REJECT


@pytest.mark.asyncio
async def test_get_queue_pressure(redis_client, mock_redis_client):
    """Test get_queue_pressure returns correct metrics."""
    mock_redis_client.llen.return_value = 85

    from backend.core.redis import QueuePressureMetrics

    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100)

    assert isinstance(metrics, QueuePressureMetrics)
    assert metrics.queue_name == "test_queue"
    assert metrics.current_length == 85
    assert metrics.max_size == 100
    assert metrics.fill_ratio == 0.85
    assert metrics.is_at_pressure_threshold is False  # 85% < 90% threshold
    assert metrics.is_full is False


@pytest.mark.asyncio
async def test_get_queue_pressure_at_threshold(redis_client, mock_redis_client):
    """Test get_queue_pressure correctly identifies pressure threshold."""
    mock_redis_client.llen.return_value = 95

    from backend.core.redis import QueuePressureMetrics

    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100)

    assert isinstance(metrics, QueuePressureMetrics)
    assert metrics.fill_ratio == 0.95
    assert metrics.is_at_pressure_threshold is True  # 95% >= 90% threshold
    assert metrics.is_full is False


@pytest.mark.asyncio
async def test_get_queue_pressure_full(redis_client, mock_redis_client):
    """Test get_queue_pressure correctly identifies full queue."""
    mock_redis_client.llen.return_value = 100

    from backend.core.redis import QueuePressureMetrics

    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100)

    assert isinstance(metrics, QueuePressureMetrics)
    assert metrics.fill_ratio == 1.0
    assert metrics.is_at_pressure_threshold is True
    assert metrics.is_full is True


@pytest.mark.asyncio
async def test_queue_add_result_had_backpressure_property():
    """Test QueueAddResult.had_backpressure property."""
    from backend.core.redis import QueueAddResult

    # Normal add - no backpressure
    result_normal = QueueAddResult(success=True, queue_length=5)
    assert result_normal.had_backpressure is False

    # Rejected - backpressure
    result_rejected = QueueAddResult(success=False, queue_length=10, error="Queue full")
    assert result_rejected.had_backpressure is True

    # Dropped items - backpressure
    result_dropped = QueueAddResult(success=True, queue_length=10, dropped_count=2)
    assert result_dropped.had_backpressure is True

    # Moved to DLQ - backpressure
    result_dlq = QueueAddResult(success=True, queue_length=10, moved_to_dlq_count=1)
    assert result_dlq.had_backpressure is True


@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not installed")
@pytest.mark.asyncio
async def test_backpressure_integration_reject_policy():
    """Integration test for backpressure with REJECT policy using fakeredis."""
    fake_server = fakeredis.FakeRedis(decode_responses=True)

    client = RedisClient(redis_url="redis://localhost:6379/15")
    client._client = fake_server
    client._pool = MagicMock()

    queue_name = "test_backpressure_reject"
    max_size = 5

    # Clear any existing data
    await client.clear_queue(queue_name)

    from backend.core.redis import QueueOverflowPolicy

    # Fill queue to max
    for i in range(max_size):
        result = await client.add_to_queue_safe(
            queue_name,
            {"id": i},
            max_size=max_size,
            overflow_policy=QueueOverflowPolicy.REJECT,
        )
        assert result.success is True

    # Verify queue is full
    length = await client.get_queue_length(queue_name)
    assert length == max_size

    # Try to add one more - should be rejected
    result = await client.add_to_queue_safe(
        queue_name,
        {"id": "overflow"},
        max_size=max_size,
        overflow_policy=QueueOverflowPolicy.REJECT,
    )
    assert result.success is False
    assert result.error is not None

    # Queue length should still be at max
    length = await client.get_queue_length(queue_name)
    assert length == max_size

    # Cleanup
    await client.clear_queue(queue_name)
    await fake_server.aclose()


@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not installed")
@pytest.mark.asyncio
async def test_backpressure_integration_dlq_policy():
    """Integration test for backpressure with DLQ policy using fakeredis."""
    fake_server = fakeredis.FakeRedis(decode_responses=True)

    client = RedisClient(redis_url="redis://localhost:6379/15")
    client._client = fake_server
    client._pool = MagicMock()

    queue_name = "test_backpressure_dlq"
    dlq_name = f"dlq:overflow:{queue_name}"
    max_size = 5

    # Clear any existing data
    await client.clear_queue(queue_name)
    await client.clear_queue(dlq_name)

    from backend.core.redis import QueueOverflowPolicy

    # Fill queue to max
    for i in range(max_size):
        result = await client.add_to_queue_safe(
            queue_name,
            {"id": i},
            max_size=max_size,
            overflow_policy=QueueOverflowPolicy.DLQ,
        )
        assert result.success is True

    # Try to add one more - should move oldest to DLQ
    result = await client.add_to_queue_safe(
        queue_name,
        {"id": "new"},
        max_size=max_size,
        overflow_policy=QueueOverflowPolicy.DLQ,
    )
    assert result.success is True
    assert result.moved_to_dlq_count == 1

    # Queue length should still be at max
    length = await client.get_queue_length(queue_name)
    assert length == max_size

    # DLQ should have the moved item
    dlq_length = await client.get_queue_length(dlq_name)
    assert dlq_length == 1

    # Cleanup
    await client.clear_queue(queue_name)
    await client.clear_queue(dlq_name)
    await fake_server.aclose()


@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not installed")
@pytest.mark.asyncio
async def test_backpressure_integration_drop_oldest_policy():
    """Integration test for backpressure with DROP_OLDEST policy using fakeredis."""
    fake_server = fakeredis.FakeRedis(decode_responses=True)

    client = RedisClient(redis_url="redis://localhost:6379/15")
    client._client = fake_server
    client._pool = MagicMock()

    queue_name = "test_backpressure_drop"
    max_size = 5

    # Clear any existing data
    await client.clear_queue(queue_name)

    from backend.core.redis import QueueOverflowPolicy

    # Fill queue to max
    for i in range(max_size):
        result = await client.add_to_queue_safe(
            queue_name,
            {"id": i},
            max_size=max_size,
            overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
        )
        assert result.success is True

    # Try to add one more - should drop oldest
    result = await client.add_to_queue_safe(
        queue_name,
        {"id": "new"},
        max_size=max_size,
        overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
    )
    assert result.success is True
    assert result.dropped_count == 1

    # Queue length should still be at max
    length = await client.get_queue_length(queue_name)
    assert length == max_size

    # Peek to verify oldest was dropped (id=0 should be gone)
    items = await client.peek_queue(queue_name)
    ids = [item["id"] for item in items]
    assert 0 not in ids  # Oldest item was dropped
    assert "new" in ids  # New item was added

    # Cleanup
    await client.clear_queue(queue_name)
    await fake_server.aclose()
