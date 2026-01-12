"""Unit tests for Redis connection and operations."""

import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError

import backend.core.redis as redis_module
from backend.core.redis import (
    QueueAddResult,
    QueueOverflowPolicy,
    RedisClient,
    _get_redis_init_lock,
    close_redis,
    get_redis,
    get_redis_client_sync,
    get_redis_optional,
    init_redis,
)
from backend.tests.conftest import unique_id

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
        mock_pool_instance = AsyncMock(spec=ConnectionPool)
        mock_pool_instance.disconnect = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool_instance
        yield mock_pool_class


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with common operations."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.aclose = AsyncMock()
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
    mock_client.pubsub = MagicMock(spec=PubSub)
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
async def test_add_to_queue_safe_with_dict(redis_client, mock_redis_client):
    """Test adding a dictionary to a queue using add_to_queue_safe."""
    mock_redis_client.rpush.return_value = 1
    mock_redis_client.llen.return_value = 0

    data = {"key": "value", "number": 42}
    result = await redis_client.add_to_queue_safe("test_queue", data)

    assert result.success is True
    assert result.queue_length == 1
    mock_redis_client.rpush.assert_awaited_once()
    # Verify JSON serialization happened
    call_args = mock_redis_client.rpush.call_args[0]
    assert call_args[0] == "test_queue"
    assert '"key": "value"' in call_args[1]


@pytest.mark.asyncio
async def test_add_to_queue_safe_with_string(redis_client, mock_redis_client):
    """Test adding a string to a queue using add_to_queue_safe."""
    mock_redis_client.rpush.return_value = 2
    mock_redis_client.llen.return_value = 1

    result = await redis_client.add_to_queue_safe("test_queue", "simple_string")

    assert result.success is True
    assert result.queue_length == 2
    mock_redis_client.rpush.assert_awaited_once_with("test_queue", "simple_string")


@pytest.mark.asyncio
async def test_add_to_queue_safe_returns_detailed_result(redis_client, mock_redis_client):
    """Test add_to_queue_safe returns QueueAddResult with details."""
    mock_redis_client.rpush.return_value = 5

    result = await redis_client.add_to_queue_safe("test_queue", {"data": "value"})

    assert isinstance(result, QueueAddResult)
    assert result.queue_length == 5
    assert result.dropped_count == 0
    assert result.success is True


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_oldest_reports_dropped(redis_client, mock_redis_client):
    """Test DROP_OLDEST strategy reports how many items were dropped."""
    # Queue must be at capacity for DROP_OLDEST to trigger trim logic
    mock_redis_client.llen.return_value = 100  # Queue at capacity
    mock_redis_client.rpush.return_value = 105  # 5 over the limit after push

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=100, overflow_policy=QueueOverflowPolicy.DROP_OLDEST
    )

    assert result.queue_length == 100
    assert result.dropped_count == 5
    assert result.success is True


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_newest_rejects_when_full(redis_client, mock_redis_client):
    """Test REJECT policy rejects items when queue is full."""
    mock_redis_client.llen.return_value = 100  # Queue at capacity

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=100, overflow_policy=QueueOverflowPolicy.REJECT
    )

    assert result.queue_length == 100
    assert result.dropped_count == 0
    assert result.success is False
    assert result.error is not None  # Should have error message
    # rpush should NOT be called when rejected
    mock_redis_client.rpush.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_to_queue_safe_drop_newest_accepts_when_space(redis_client, mock_redis_client):
    """Test REJECT policy accepts items when queue has space."""
    mock_redis_client.llen.return_value = 50  # Queue has space
    mock_redis_client.rpush.return_value = 51

    result = await redis_client.add_to_queue_safe(
        "test_queue", "data", max_size=100, overflow_policy=QueueOverflowPolicy.REJECT
    )

    assert result.queue_length == 51
    assert result.dropped_count == 0
    assert result.success is True
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
    """Test subscribing to a channel using shared pubsub."""
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_redis_client.pubsub.return_value = mock_pubsub

    pubsub = await redis_client.subscribe("test_channel", "another_channel")

    assert pubsub is not None
    mock_pubsub.subscribe.assert_awaited_once_with("test_channel", "another_channel")


@pytest.mark.asyncio
async def test_create_pubsub_returns_new_instance(redis_client, mock_redis_client):
    """Test create_pubsub returns a new PubSub instance each time."""
    mock_pubsub1 = MagicMock(spec=PubSub)
    mock_pubsub2 = MagicMock(spec=PubSub)
    mock_redis_client.pubsub.side_effect = [mock_pubsub1, mock_pubsub2]

    pubsub1 = redis_client.create_pubsub()
    pubsub2 = redis_client.create_pubsub()

    assert pubsub1 is not pubsub2
    assert mock_redis_client.pubsub.call_count == 2


@pytest.mark.asyncio
async def test_subscribe_dedicated_creates_new_pubsub(redis_client, mock_redis_client):
    """Test subscribe_dedicated creates a dedicated pubsub connection."""
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_redis_client.pubsub.return_value = mock_pubsub

    pubsub = await redis_client.subscribe_dedicated("test_channel")

    assert pubsub is mock_pubsub
    mock_pubsub.subscribe.assert_awaited_once_with("test_channel")
    # Should NOT set internal _pubsub (that's for shared instance)
    # The dedicated pubsub is returned for caller to manage


@pytest.mark.asyncio
async def test_subscribe_dedicated_multiple_calls_create_separate_connections(
    redis_client, mock_redis_client
):
    """Test multiple subscribe_dedicated calls create separate connections."""
    mock_pubsub1 = AsyncMock()
    mock_pubsub1.subscribe = AsyncMock()
    mock_pubsub2 = AsyncMock()
    mock_pubsub2.subscribe = AsyncMock()
    mock_redis_client.pubsub.side_effect = [mock_pubsub1, mock_pubsub2]

    pubsub1 = await redis_client.subscribe_dedicated("channel1")
    pubsub2 = await redis_client.subscribe_dedicated("channel2")

    assert pubsub1 is not pubsub2
    assert mock_redis_client.pubsub.call_count == 2
    mock_pubsub1.subscribe.assert_awaited_once_with("channel1")
    mock_pubsub2.subscribe.assert_awaited_once_with("channel2")


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
# These tests manipulate global state (_redis_client), so we patch it to ensure isolation


@pytest.mark.asyncio
async def test_get_redis_dependency(mock_redis_pool, mock_redis_client):
    """Test get_redis FastAPI dependency."""
    # Patch global state to ensure test isolation in parallel execution
    with (
        patch("backend.core.redis._redis_client", None),
        patch("backend.core.redis.Redis", return_value=mock_redis_client),
    ):
        # Simulate FastAPI dependency injection
        redis_generator = get_redis()
        client = await anext(redis_generator)

        assert isinstance(client, RedisClient)
        assert client._client is not None

        # Cleanup
        with contextlib.suppress(StopAsyncIteration):
            await redis_generator.asend(None)


@pytest.mark.asyncio
async def test_init_redis_creates_global_client(mock_redis_pool, mock_redis_client):
    """Test init_redis creates and returns global client."""
    # Patch global state to ensure test isolation in parallel execution
    with (
        patch("backend.core.redis._redis_client", None),
        patch("backend.core.redis.Redis", return_value=mock_redis_client),
    ):
        client = await init_redis()

        assert isinstance(client, RedisClient)
        assert client._client is not None
        mock_redis_client.ping.assert_awaited()


@pytest.mark.asyncio
async def test_close_redis_cleans_up_global_client(mock_redis_pool, mock_redis_client):
    """Test close_redis properly cleans up global client."""
    # Patch global state to ensure test isolation in parallel execution
    with (
        patch("backend.core.redis._redis_client", None),
        patch("backend.core.redis.Redis", return_value=mock_redis_client),
    ):
        await init_redis()
        await close_redis()

        # RedisClient.disconnect() internally calls _client.aclose()
        mock_redis_client.aclose.assert_awaited()


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
    client._pool = MagicMock(spec=ConnectionPool)  # Mock pool to avoid None checks

    # Test queue operations - use unique key to prevent parallel test conflicts
    queue_name = unique_id("test_integration_queue")

    # Clear any existing data
    await client.clear_queue(queue_name)

    # Add items using add_to_queue_safe
    result1 = await client.add_to_queue_safe(queue_name, {"id": 1, "data": "test1"})
    assert result1.success is True
    result2 = await client.add_to_queue_safe(queue_name, {"id": 2, "data": "test2"})
    assert result2.success is True

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
    client._pool = MagicMock(spec=ConnectionPool)  # Mock pool to avoid None checks

    # Test cache operations - use unique key to prevent parallel test conflicts
    key = unique_id("test_integration_cache_key")

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
    # 91% full (above default 80% threshold)
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
    # Use 75% fill to be below the default 80% threshold
    mock_redis_client.llen.return_value = 75

    from backend.core.redis import QueuePressureMetrics

    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100)

    assert isinstance(metrics, QueuePressureMetrics)
    assert metrics.queue_name == "test_queue"
    assert metrics.current_length == 75
    assert metrics.max_size == 100
    assert metrics.fill_ratio == 0.75
    assert metrics.is_at_pressure_threshold is False  # 75% < 80% threshold
    assert metrics.is_full is False


@pytest.mark.asyncio
async def test_get_queue_pressure_at_threshold(redis_client, mock_redis_client):
    """Test get_queue_pressure correctly identifies pressure threshold."""
    mock_redis_client.llen.return_value = 95

    from backend.core.redis import QueuePressureMetrics

    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100)

    assert isinstance(metrics, QueuePressureMetrics)
    assert metrics.fill_ratio == 0.95
    assert metrics.is_at_pressure_threshold is True  # 95% >= 80% threshold
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
async def test_get_queue_pressure_with_timeout(redis_client, mock_redis_client):
    """Test get_queue_pressure respects timeout parameter."""
    mock_redis_client.llen.return_value = 50

    from backend.core.redis import QueuePressureMetrics

    # Should work with explicit timeout
    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100, timeout=10.0)

    assert isinstance(metrics, QueuePressureMetrics)
    assert metrics.current_length == 50


@pytest.mark.asyncio
async def test_get_queue_pressure_timeout_on_slow_redis(redis_client, mock_redis_client):
    """Test get_queue_pressure raises TimeoutError when Redis is slow."""

    async def slow_llen(*args, **kwargs):
        await asyncio.sleep(0.1)  # Longer than 0.01s timeout
        return 50

    mock_redis_client.llen = slow_llen

    with pytest.raises(asyncio.TimeoutError):
        # Use very short timeout to trigger timeout
        await redis_client.get_queue_pressure("test_queue", max_size=100, timeout=0.01)


@pytest.mark.asyncio
async def test_get_queue_pressure_uses_default_timeout(redis_client, mock_redis_client):
    """Test get_queue_pressure uses default _MONITORING_TIMEOUT when not specified."""
    mock_redis_client.llen.return_value = 50

    # Verify the default timeout constant exists
    assert hasattr(redis_client, "_MONITORING_TIMEOUT")
    assert redis_client._MONITORING_TIMEOUT == 5.0

    from backend.core.redis import QueuePressureMetrics

    # Should work with default timeout
    metrics = await redis_client.get_queue_pressure("test_queue", max_size=100)

    assert isinstance(metrics, QueuePressureMetrics)


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
    client._pool = MagicMock(spec=ConnectionPool)

    # Use unique key to prevent parallel test conflicts
    queue_name = unique_id("test_backpressure_reject")
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
    client._pool = MagicMock(spec=ConnectionPool)

    # Use unique key to prevent parallel test conflicts
    queue_name = unique_id("test_backpressure_dlq")
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
    client._pool = MagicMock(spec=ConnectionPool)

    # Use unique key to prevent parallel test conflicts
    queue_name = unique_id("test_backpressure_drop")
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


# ==============================================================================
# Bug Fix Tests - Redis Singleton Race Condition (wa0t.4)
# ==============================================================================


@pytest.fixture
def reset_redis_global_state():
    """Reset global Redis client state before and after each test."""
    # Reset before test
    redis_module._redis_client = None
    redis_module._redis_init_lock = None
    yield
    # Reset after test
    redis_module._redis_client = None
    redis_module._redis_init_lock = None


@pytest.mark.asyncio
async def test_get_redis_init_lock_creates_lock():
    """Test that _get_redis_init_lock creates an asyncio.Lock."""
    # Reset lock state
    redis_module._redis_init_lock = None

    lock = _get_redis_init_lock()

    assert lock is not None
    assert isinstance(lock, asyncio.Lock)

    # Cleanup
    redis_module._redis_init_lock = None


@pytest.mark.asyncio
async def test_get_redis_init_lock_returns_same_lock():
    """Test that _get_redis_init_lock returns the same lock instance."""
    # Reset lock state
    redis_module._redis_init_lock = None

    lock1 = _get_redis_init_lock()
    lock2 = _get_redis_init_lock()

    assert lock1 is lock2

    # Cleanup
    redis_module._redis_init_lock = None


@pytest.mark.asyncio
async def test_init_redis_concurrent_initialization(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test that concurrent init_redis calls don't create multiple clients.

    This tests the race condition fix (wa0t.4) by calling init_redis()
    concurrently from multiple coroutines.
    """
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        # Call init_redis concurrently from multiple coroutines
        results = await asyncio.gather(
            init_redis(),
            init_redis(),
            init_redis(),
            init_redis(),
            init_redis(),
        )

        # All results should be the same instance
        first_client = results[0]
        for client in results[1:]:
            assert client is first_client

        # connect (ping) should only have been called once
        # due to the double-check locking pattern
        assert mock_redis_client.ping.await_count == 1


@pytest.mark.asyncio
async def test_get_redis_concurrent_initialization(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test that concurrent get_redis calls don't create multiple clients."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        # Call get_redis concurrently
        generators = [get_redis() for _ in range(5)]
        clients = await asyncio.gather(*[anext(gen) for gen in generators])

        # All clients should be the same instance
        first_client = clients[0]
        for client in clients[1:]:
            assert client is first_client

        # Cleanup generators
        for gen in generators:
            with contextlib.suppress(StopAsyncIteration):
                await gen.asend(None)


@pytest.mark.asyncio
async def test_get_redis_optional_concurrent_initialization(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test that concurrent get_redis_optional calls don't create multiple clients."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        # Call get_redis_optional concurrently
        generators = [get_redis_optional() for _ in range(5)]
        clients = await asyncio.gather(*[anext(gen) for gen in generators])

        # All clients should be the same instance (not None)
        first_client = clients[0]
        assert first_client is not None
        for client in clients[1:]:
            assert client is first_client

        # Cleanup generators
        for gen in generators:
            with contextlib.suppress(StopAsyncIteration):
                await gen.asend(None)


@pytest.mark.asyncio
async def test_close_redis_resets_lock(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test that close_redis resets the initialization lock."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        await init_redis()

        # Lock should exist after initialization
        assert redis_module._redis_init_lock is not None

        await close_redis()

        # Lock should be reset after close
        assert redis_module._redis_init_lock is None
        assert redis_module._redis_client is None


# ==============================================================================
# Sync Access Tests - get_redis_client_sync
# ==============================================================================


def test_get_redis_client_sync_returns_none_when_not_initialized():
    """Test get_redis_client_sync returns None when Redis not initialized."""
    with patch.object(redis_module, "_redis_client", None):
        result = get_redis_client_sync()
        assert result is None


def test_get_redis_client_sync_returns_client_when_initialized():
    """Test get_redis_client_sync returns client when already initialized."""
    mock_client = MagicMock(spec=RedisClient)
    with patch.object(redis_module, "_redis_client", mock_client):
        result = get_redis_client_sync()
        assert result is mock_client


@pytest.mark.asyncio
async def test_get_redis_client_sync_after_init_redis(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test get_redis_client_sync returns client after init_redis is called."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        # Before init, should return None
        assert get_redis_client_sync() is None

        # Initialize Redis
        await init_redis()

        # After init, should return the client
        result = get_redis_client_sync()
        assert result is not None
        assert isinstance(result, RedisClient)


# ==============================================================================
# Bug Fix Tests - BLPOP Minimum Timeout (wa0t.5)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_from_queue_enforces_minimum_timeout(redis_client, mock_redis_client):
    """Test that get_from_queue enforces minimum timeout of 5 seconds.

    This tests the BLPOP timeout fix (wa0t.5) that prevents indefinite blocking.
    """
    mock_redis_client.blpop.return_value = None

    # Call with timeout=0 (would block indefinitely without fix)
    await redis_client.get_from_queue("test_queue", timeout=0)

    # Should have been called with minimum timeout (5), not 0
    mock_redis_client.blpop.assert_awaited_once_with(["test_queue"], timeout=5)


@pytest.mark.asyncio
async def test_get_from_queue_enforces_minimum_on_small_timeout(redis_client, mock_redis_client):
    """Test that get_from_queue enforces minimum timeout for small values."""
    mock_redis_client.blpop.return_value = None

    # Call with timeout less than minimum
    await redis_client.get_from_queue("test_queue", timeout=2)

    # Should have been called with minimum timeout (5), not 2
    mock_redis_client.blpop.assert_awaited_once_with(["test_queue"], timeout=5)


@pytest.mark.asyncio
async def test_get_from_queue_preserves_large_timeout(redis_client, mock_redis_client):
    """Test that get_from_queue preserves timeout values >= minimum."""
    mock_redis_client.blpop.return_value = None

    # Call with timeout greater than minimum
    await redis_client.get_from_queue("test_queue", timeout=30)

    # Should use the provided timeout
    mock_redis_client.blpop.assert_awaited_once_with(["test_queue"], timeout=30)


@pytest.mark.asyncio
async def test_get_from_queue_min_blpop_timeout_class_attribute():
    """Test that RedisClient has _MIN_BLPOP_TIMEOUT class attribute set to 5."""
    assert RedisClient._MIN_BLPOP_TIMEOUT == 5


@pytest.mark.asyncio
async def test_get_from_queue_with_retry_enforces_minimum_timeout(redis_client, mock_redis_client):
    """Test that get_from_queue_with_retry also enforces minimum timeout."""
    mock_redis_client.blpop.return_value = None

    # Call with timeout=0
    await redis_client.get_from_queue_with_retry("test_queue", timeout=0)

    # Should have been called with minimum timeout
    mock_redis_client.blpop.assert_awaited_once_with(["test_queue"], timeout=5)


# ==============================================================================
# SSL/TLS Tests
# ==============================================================================


def test_redis_client_ssl_settings_from_constructor():
    """Test that RedisClient accepts SSL settings via constructor."""
    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="required",
        ssl_ca_certs="/path/to/ca.crt",
        ssl_certfile="/path/to/client.crt",
        ssl_keyfile="/path/to/client.key",
        ssl_check_hostname=True,
    )

    assert client._ssl_enabled is True
    assert client._ssl_cert_reqs == "required"
    assert client._ssl_ca_certs == "/path/to/ca.crt"
    assert client._ssl_certfile == "/path/to/client.crt"
    assert client._ssl_keyfile == "/path/to/client.key"
    assert client._ssl_check_hostname is True


def test_redis_client_ssl_defaults_from_settings():
    """Test that RedisClient uses settings defaults when constructor values are None."""
    # Create client without explicit SSL settings
    client = RedisClient(redis_url="redis://localhost:6379/0")

    # Should use defaults from settings (ssl_enabled defaults to False)
    assert client._ssl_enabled is False


def test_redis_client_create_ssl_context_returns_none_when_disabled():
    """Test that _create_ssl_context returns None when SSL is disabled."""
    client = RedisClient(redis_url="redis://localhost:6379/0", ssl_enabled=False)

    ssl_context = client._create_ssl_context()

    assert ssl_context is None


def test_redis_client_create_ssl_context_creates_context_when_enabled():
    """Test that _create_ssl_context creates context when SSL is enabled."""
    import ssl

    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="none",  # Use 'none' to avoid needing actual certs
        ssl_check_hostname=False,
    )

    ssl_context = client._create_ssl_context()

    assert ssl_context is not None
    assert isinstance(ssl_context, ssl.SSLContext)
    assert ssl_context.verify_mode == ssl.CERT_NONE
    assert ssl_context.check_hostname is False


def test_redis_client_create_ssl_context_with_cert_required():
    """Test SSL context creation with certificate required mode."""
    import ssl

    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="required",
        ssl_check_hostname=True,
    )

    ssl_context = client._create_ssl_context()

    assert ssl_context is not None
    assert ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert ssl_context.check_hostname is True


def test_redis_client_create_ssl_context_with_cert_optional():
    """Test SSL context creation with certificate optional mode."""
    import ssl

    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="optional",
        ssl_check_hostname=False,
    )

    ssl_context = client._create_ssl_context()

    assert ssl_context is not None
    assert ssl_context.verify_mode == ssl.CERT_OPTIONAL


def test_redis_client_create_ssl_context_missing_ca_cert_raises():
    """Test that missing CA certificate file raises FileNotFoundError."""
    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="required",
        ssl_ca_certs="/nonexistent/path/to/ca.crt",
    )

    with pytest.raises(FileNotFoundError, match="Redis SSL CA certificate file not found"):
        client._create_ssl_context()


def test_redis_client_create_ssl_context_missing_client_cert_raises():
    """Test that missing client certificate file raises FileNotFoundError."""
    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="none",
        ssl_check_hostname=False,  # Required when cert_reqs is 'none'
        ssl_certfile="/nonexistent/path/to/client.crt",
    )

    with pytest.raises(FileNotFoundError, match="Redis SSL client certificate file not found"):
        client._create_ssl_context()


def test_redis_client_create_ssl_context_missing_client_key_raises():
    """Test that missing client key file raises FileNotFoundError."""
    import tempfile
    from pathlib import Path

    # Create a temporary certificate file (content doesn't matter for this test)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as f:
        f.write("dummy cert")
        temp_cert = f.name

    try:
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            ssl_enabled=True,
            ssl_cert_reqs="none",
            ssl_check_hostname=False,  # Required when cert_reqs is 'none'
            ssl_certfile=temp_cert,
            ssl_keyfile="/nonexistent/path/to/client.key",
        )

        with pytest.raises(FileNotFoundError, match="Redis SSL client key file not found"):
            client._create_ssl_context()
    finally:
        Path(temp_cert).unlink()


@pytest.mark.asyncio
async def test_redis_connect_with_ssl_enabled(mock_redis_pool, mock_redis_client):
    """Test that connect() passes SSL context to ConnectionPool when enabled."""
    import ssl

    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            ssl_enabled=True,
            ssl_cert_reqs="none",
            ssl_check_hostname=False,
        )
        await client.connect()

        # Verify ConnectionPool.from_url was called with ssl parameter
        call_kwargs = mock_redis_pool.from_url.call_args[1]
        assert "ssl" in call_kwargs
        assert isinstance(call_kwargs["ssl"], ssl.SSLContext)

        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connect_without_ssl(mock_redis_pool, mock_redis_client):
    """Test that connect() does not pass SSL context when disabled."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            ssl_enabled=False,
        )
        await client.connect()

        # Verify ConnectionPool.from_url was called without ssl parameter
        call_kwargs = mock_redis_pool.from_url.call_args[1]
        assert "ssl" not in call_kwargs

        await client.disconnect()


# ==============================================================================
# Password Authentication Tests (NEM-1089)
# NOTE: S105/S106 are false positives - these are test fixtures, not real passwords
# ==============================================================================


def test_redis_client_password_from_constructor():
    """Test that RedisClient accepts password via constructor."""
    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        password="test_password",  # noqa: S106  # pragma: allowlist secret
    )

    assert client._password == "test_password"  # noqa: S105  # pragma: allowlist secret


def test_redis_client_password_none_by_default():
    """Test that RedisClient password defaults to None (no auth)."""
    with patch("backend.core.redis.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.redis_password = None  # Default is no password
        mock_settings.redis_ssl_enabled = False
        mock_settings.redis_ssl_cert_reqs = "required"
        mock_settings.redis_ssl_ca_certs = None
        mock_settings.redis_ssl_certfile = None
        mock_settings.redis_ssl_keyfile = None
        mock_settings.redis_ssl_check_hostname = True
        mock_get_settings.return_value = mock_settings

        client = RedisClient(redis_url="redis://localhost:6379/0")

        assert client._password is None


def test_redis_client_password_from_settings():
    """Test that RedisClient uses password from settings when not provided in constructor."""
    with patch("backend.core.redis.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.redis_password = "settings_password"  # noqa: S105  # pragma: allowlist secret
        mock_settings.redis_ssl_enabled = False
        mock_settings.redis_ssl_cert_reqs = "required"
        mock_settings.redis_ssl_ca_certs = None
        mock_settings.redis_ssl_certfile = None
        mock_settings.redis_ssl_keyfile = None
        mock_settings.redis_ssl_check_hostname = True
        mock_get_settings.return_value = mock_settings

        client = RedisClient()

        assert client._password == "settings_password"  # noqa: S105  # pragma: allowlist secret


def test_redis_client_constructor_password_overrides_settings():
    """Test that constructor password takes precedence over settings."""
    with patch("backend.core.redis.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.redis_password = "settings_password"  # noqa: S105  # pragma: allowlist secret
        mock_settings.redis_ssl_enabled = False
        mock_settings.redis_ssl_cert_reqs = "required"
        mock_settings.redis_ssl_ca_certs = None
        mock_settings.redis_ssl_certfile = None
        mock_settings.redis_ssl_keyfile = None
        mock_settings.redis_ssl_check_hostname = True
        mock_get_settings.return_value = mock_settings

        client = RedisClient(password="constructor_password")  # noqa: S106  # pragma: allowlist secret

        assert client._password == "constructor_password"  # noqa: S105  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_redis_connect_with_password(mock_redis_pool, mock_redis_client):
    """Test that connect() passes password to ConnectionPool when provided."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            password="test_password",  # noqa: S106  # pragma: allowlist secret
        )
        await client.connect()

        # Verify ConnectionPool.from_url was called with password parameter
        call_kwargs = mock_redis_pool.from_url.call_args[1]
        assert "password" in call_kwargs
        assert call_kwargs["password"] == "test_password"  # noqa: S105  # pragma: allowlist secret

        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connect_without_password(mock_redis_pool, mock_redis_client):
    """Test that connect() does not pass password when not provided."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            password=None,
        )
        await client.connect()

        # Verify ConnectionPool.from_url was called without password parameter
        call_kwargs = mock_redis_pool.from_url.call_args[1]
        assert call_kwargs.get("password") is None

        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connect_with_empty_password(mock_redis_pool, mock_redis_client):
    """Test that connect() does not pass password when empty string provided."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            password="",
        )
        await client.connect()

        # Empty string should be treated as None (no password)
        call_kwargs = mock_redis_pool.from_url.call_args[1]
        assert call_kwargs.get("password") is None

        await client.disconnect()


@pytest.mark.asyncio
async def test_redis_connect_with_password_and_ssl(mock_redis_pool, mock_redis_client):
    """Test that connect() can use both password and SSL together."""
    import ssl

    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(
            redis_url="redis://localhost:6379/0",
            password="secure_password",  # noqa: S106  # pragma: allowlist secret
            ssl_enabled=True,
            ssl_cert_reqs="none",
            ssl_check_hostname=False,
        )
        await client.connect()

        # Verify both password and SSL are passed
        call_kwargs = mock_redis_pool.from_url.call_args[1]
        assert "password" in call_kwargs
        assert call_kwargs["password"] == "secure_password"  # noqa: S105  # pragma: allowlist secret
        assert "ssl" in call_kwargs
        assert isinstance(call_kwargs["ssl"], ssl.SSLContext)

        await client.disconnect()


# ==============================================================================
# SETEX Operation Tests (NEM-1746)
# ==============================================================================


@pytest.mark.asyncio
async def test_setex_sets_key_with_expiration(redis_client, mock_redis_client):
    """Test setex sets a key with expiration time."""
    mock_redis_client.setex = AsyncMock(return_value=True)

    result = await redis_client.setex("test_key", 3600, '{"data": "value"}')

    assert result is True
    mock_redis_client.setex.assert_awaited_once_with("test_key", 3600, '{"data": "value"}')


@pytest.mark.asyncio
async def test_setex_with_short_ttl(redis_client, mock_redis_client):
    """Test setex works with short TTL values."""
    mock_redis_client.setex = AsyncMock(return_value=True)

    result = await redis_client.setex("temp_key", 60, "temporary")

    assert result is True
    mock_redis_client.setex.assert_awaited_once_with("temp_key", 60, "temporary")


@pytest.mark.asyncio
async def test_setex_with_long_ttl(redis_client, mock_redis_client):
    """Test setex works with long TTL values (e.g., 24 hours)."""
    mock_redis_client.setex = AsyncMock(return_value=True)

    # 24 hours in seconds = 86400
    result = await redis_client.setex("entity_key", 86400, '{"entity": "data"}')

    assert result is True
    mock_redis_client.setex.assert_awaited_once_with("entity_key", 86400, '{"entity": "data"}')


@pytest.mark.asyncio
async def test_setex_overwrites_existing_key(redis_client, mock_redis_client):
    """Test setex overwrites existing key value and TTL."""
    mock_redis_client.setex = AsyncMock(return_value=True)

    # First set
    await redis_client.setex("key", 100, "value1")
    # Overwrite with new value and TTL
    result = await redis_client.setex("key", 200, "value2")

    assert result is True
    assert mock_redis_client.setex.await_count == 2
    # Verify last call was with new values
    mock_redis_client.setex.assert_awaited_with("key", 200, "value2")


@pytest.mark.asyncio
async def test_setex_returns_false_on_failure(redis_client, mock_redis_client):
    """Test setex returns False when operation fails."""
    mock_redis_client.setex = AsyncMock(return_value=False)

    result = await redis_client.setex("test_key", 3600, "value")

    assert result is False


@pytest.mark.asyncio
async def test_setex_raises_when_not_connected():
    """Test setex raises RuntimeError when client not connected."""
    client = RedisClient()

    with pytest.raises(RuntimeError, match="Redis client not connected"):
        await client.setex("key", 3600, "value")


@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not installed")
@pytest.mark.asyncio
async def test_setex_integration():
    """Integration-style test for setex using fakeredis."""
    fake_server = fakeredis.FakeRedis(decode_responses=True)

    client = RedisClient(redis_url="redis://localhost:6379/15")
    client._client = fake_server
    client._pool = MagicMock(spec=ConnectionPool)

    # Use unique key to prevent parallel test conflicts
    key = unique_id("test_setex_key")

    # Set with expiration
    result = await client.setex(key, 3600, '{"test": "data"}')
    assert result is True

    # Verify value was stored
    stored_value = await fake_server.get(key)
    assert stored_value == '{"test": "data"}'

    # Verify TTL was set (should be less than or equal to 3600)
    ttl = await fake_server.ttl(key)
    assert 0 < ttl <= 3600

    # Cleanup
    await fake_server.delete(key)
    await fake_server.aclose()


# ==============================================================================
# SSL Certificate Path Loading Tests
# ==============================================================================


def test_redis_client_create_ssl_context_with_ca_cert(tmp_path):
    """Test SSL context loads CA certificate when provided."""
    import ssl

    # Create a temporary CA certificate file
    ca_cert_file = tmp_path / "ca.crt"
    ca_cert_file.write_text("FAKE CA CERTIFICATE")

    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="required",
        ssl_ca_certs=str(ca_cert_file),
    )

    # Mock load_verify_locations to avoid actual SSL operations
    with patch("ssl.SSLContext.load_verify_locations") as mock_load:
        ssl_context = client._create_ssl_context()

        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        # Verify load_verify_locations was called with the correct path
        mock_load.assert_called_once_with(cafile=str(ca_cert_file))


def test_redis_client_create_ssl_context_with_client_cert(tmp_path):
    """Test SSL context loads client certificate when provided."""
    import ssl

    # Create temporary certificate files
    cert_file = tmp_path / "client.crt"
    cert_file.write_text("FAKE CLIENT CERTIFICATE")

    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="none",
        ssl_check_hostname=False,
        ssl_certfile=str(cert_file),
    )

    # Mock load_cert_chain to avoid actual SSL operations
    with patch("ssl.SSLContext.load_cert_chain") as mock_load:
        ssl_context = client._create_ssl_context()

        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        # Verify load_cert_chain was called with the correct path
        mock_load.assert_called_once_with(certfile=str(cert_file), keyfile=None)


def test_redis_client_create_ssl_context_with_client_cert_and_key(tmp_path):
    """Test SSL context loads client certificate and key when both provided."""
    import ssl

    # Create temporary certificate files
    cert_file = tmp_path / "client.crt"
    cert_file.write_text("FAKE CLIENT CERTIFICATE")
    key_file = tmp_path / "client.key"
    key_file.write_text("FAKE CLIENT KEY")

    client = RedisClient(
        redis_url="redis://localhost:6379/0",
        ssl_enabled=True,
        ssl_cert_reqs="none",
        ssl_check_hostname=False,
        ssl_certfile=str(cert_file),
        ssl_keyfile=str(key_file),
    )

    # Mock load_cert_chain to avoid actual SSL operations
    with patch("ssl.SSLContext.load_cert_chain") as mock_load:
        ssl_context = client._create_ssl_context()

        assert ssl_context is not None
        assert isinstance(ssl_context, ssl.SSLContext)
        # Verify load_cert_chain was called with both cert and key
        mock_load.assert_called_once_with(certfile=str(cert_file), keyfile=str(key_file))


# ==============================================================================
# Retry Logic Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_with_retry_raises_runtime_error_on_no_error(redis_client):
    """Test with_retry raises RuntimeError when all retries exhausted without error."""
    # This is an edge case that should never happen in practice

    async def operation_that_never_succeeds():
        # Simulate an operation that doesn't raise but also doesn't return
        raise RuntimeError("Simulated failure")

    with pytest.raises(RuntimeError, match="Simulated failure"):
        await redis_client.with_retry(
            operation=operation_that_never_succeeds,
            operation_name="test_operation",
            max_retries=1,
        )


# ==============================================================================
# Non-blocking Pop Operation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_pop_from_queue_nonblocking_with_data(redis_client, mock_redis_client):
    """Test pop_from_queue_nonblocking returns data immediately."""
    mock_redis_client.lpop.return_value = '{"key": "value"}'

    result = await redis_client.pop_from_queue_nonblocking("test_queue")

    assert result == {"key": "value"}
    mock_redis_client.lpop.assert_awaited_once_with("test_queue")


@pytest.mark.asyncio
async def test_pop_from_queue_nonblocking_empty(redis_client, mock_redis_client):
    """Test pop_from_queue_nonblocking returns None for empty queue."""
    mock_redis_client.lpop.return_value = None

    result = await redis_client.pop_from_queue_nonblocking("test_queue")

    assert result is None


@pytest.mark.asyncio
async def test_pop_from_queue_nonblocking_plain_string(redis_client, mock_redis_client):
    """Test pop_from_queue_nonblocking handles plain strings."""
    mock_redis_client.lpop.return_value = "plain_string"

    result = await redis_client.pop_from_queue_nonblocking("test_queue")

    assert result == "plain_string"


# ==============================================================================
# Sorted Set Operations Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_zadd_adds_members_to_sorted_set(redis_client, mock_redis_client):
    """Test zadd adds members to sorted set."""
    mock_redis_client.zadd = AsyncMock(return_value=2)

    result = await redis_client.zadd("sorted_set", {"member1": 1.0, "member2": 2.0})

    assert result == 2
    mock_redis_client.zadd.assert_awaited_once_with("sorted_set", {"member1": 1.0, "member2": 2.0})


@pytest.mark.asyncio
async def test_zpopmax_pops_highest_score(redis_client, mock_redis_client):
    """Test zpopmax removes and returns highest score members."""
    mock_redis_client.zpopmax = AsyncMock(return_value=[("member1", 5.0)])

    result = await redis_client.zpopmax("sorted_set", count=1)

    assert result == [("member1", 5.0)]
    mock_redis_client.zpopmax.assert_awaited_once_with("sorted_set", 1)


@pytest.mark.asyncio
async def test_zcard_returns_set_size(redis_client, mock_redis_client):
    """Test zcard returns number of elements in sorted set."""
    mock_redis_client.zcard = AsyncMock(return_value=10)

    result = await redis_client.zcard("sorted_set")

    assert result == 10
    mock_redis_client.zcard.assert_awaited_once_with("sorted_set")


@pytest.mark.asyncio
async def test_zrange_returns_elements(redis_client, mock_redis_client):
    """Test zrange returns elements in index range."""
    mock_redis_client.zrange = AsyncMock(return_value=["member1", "member2"])

    result = await redis_client.zrange("sorted_set", 0, 10)

    assert result == ["member1", "member2"]
    mock_redis_client.zrange.assert_awaited_once_with("sorted_set", 0, 10)


@pytest.mark.asyncio
async def test_zrem_removes_members(redis_client, mock_redis_client):
    """Test zrem removes members from sorted set."""
    mock_redis_client.zrem = AsyncMock(return_value=2)

    result = await redis_client.zrem("sorted_set", "member1", "member2")

    assert result == 2
    mock_redis_client.zrem.assert_awaited_once_with("sorted_set", "member1", "member2")


@pytest.mark.asyncio
async def test_zscore_returns_member_score(redis_client, mock_redis_client):
    """Test zscore returns score of a member."""
    mock_redis_client.zscore = AsyncMock(return_value=5.0)

    result = await redis_client.zscore("sorted_set", "member1")

    assert result == 5.0
    mock_redis_client.zscore.assert_awaited_once_with("sorted_set", "member1")


@pytest.mark.asyncio
async def test_zscore_returns_none_for_nonexistent_member(redis_client, mock_redis_client):
    """Test zscore returns None for non-existent member."""
    mock_redis_client.zscore = AsyncMock(return_value=None)

    result = await redis_client.zscore("sorted_set", "nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_zrangebyscore_returns_elements_in_score_range(redis_client, mock_redis_client):
    """Test zrangebyscore returns elements within score range."""
    mock_redis_client.zrangebyscore = AsyncMock(return_value=["member1", "member2"])

    result = await redis_client.zrangebyscore("sorted_set", 0.0, 10.0)

    assert result == ["member1", "member2"]
    mock_redis_client.zrangebyscore.assert_awaited_once_with("sorted_set", 0.0, 10.0)


@pytest.mark.asyncio
async def test_zrangebyscore_with_pagination(redis_client, mock_redis_client):
    """Test zrangebyscore with pagination parameters."""
    mock_redis_client.zrangebyscore = AsyncMock(return_value=["member1", "member2"])

    result = await redis_client.zrangebyscore("sorted_set", 0.0, 10.0, start=0, num=2)

    assert result == ["member1", "member2"]
    mock_redis_client.zrangebyscore.assert_awaited_once_with(
        "sorted_set", 0.0, 10.0, start=0, num=2
    )


@pytest.mark.asyncio
async def test_zrangebyscore_with_infinite_bounds(redis_client, mock_redis_client):
    """Test zrangebyscore with infinite score bounds."""
    mock_redis_client.zrangebyscore = AsyncMock(return_value=["member1"])

    result = await redis_client.zrangebyscore("sorted_set", "-inf", "+inf")

    assert result == ["member1"]
    mock_redis_client.zrangebyscore.assert_awaited_once_with("sorted_set", "-inf", "+inf")


@pytest.mark.asyncio
async def test_llen_returns_list_length(redis_client, mock_redis_client):
    """Test llen returns length of a list."""
    mock_redis_client.llen = AsyncMock(return_value=5)

    result = await redis_client.llen("list_key")

    assert result == 5
    mock_redis_client.llen.assert_awaited_once_with("list_key")


# ==============================================================================
# Server Info Operations Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_info_all_sections(redis_client, mock_redis_client):
    """Test info returns all sections when no section specified."""
    mock_redis_client.info = AsyncMock(return_value={"server": {}, "memory": {}})

    result = await redis_client.info()

    assert "server" in result
    assert "memory" in result
    mock_redis_client.info.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_info_specific_section(redis_client, mock_redis_client):
    """Test info returns specific section when requested."""
    mock_redis_client.info = AsyncMock(return_value={"redis_version": "7.0.0"})

    result = await redis_client.info("server")

    assert "redis_version" in result
    mock_redis_client.info.assert_awaited_once_with("server")


@pytest.mark.asyncio
async def test_pubsub_channels_returns_active_channels(redis_client, mock_redis_client):
    """Test pubsub_channels returns list of active channels."""
    mock_redis_client.pubsub_channels = AsyncMock(return_value=["channel1", "channel2"])

    result = await redis_client.pubsub_channels()

    assert result == ["channel1", "channel2"]
    mock_redis_client.pubsub_channels.assert_awaited_once_with("*")


@pytest.mark.asyncio
async def test_pubsub_channels_with_pattern(redis_client, mock_redis_client):
    """Test pubsub_channels with custom pattern."""
    mock_redis_client.pubsub_channels = AsyncMock(return_value=["test:channel1"])

    result = await redis_client.pubsub_channels("test:*")

    assert result == ["test:channel1"]
    mock_redis_client.pubsub_channels.assert_awaited_once_with("test:*")


@pytest.mark.asyncio
async def test_pubsub_numsub_returns_subscriber_counts(redis_client, mock_redis_client):
    """Test pubsub_numsub returns subscriber counts for channels."""
    mock_redis_client.pubsub_numsub = AsyncMock(return_value=[("channel1", 5), ("channel2", 3)])

    result = await redis_client.pubsub_numsub("channel1", "channel2")

    assert result == [("channel1", 5), ("channel2", 3)]
    mock_redis_client.pubsub_numsub.assert_awaited_once_with("channel1", "channel2")


# ==============================================================================
# get_redis_optional Error Handling Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_get_redis_optional_returns_none_on_connection_error(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test get_redis_optional returns None on connection error."""
    mock_redis_client.ping.side_effect = ConnectionError("Connection failed")

    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        redis_generator = get_redis_optional()
        client = await anext(redis_generator)

        assert client is None

        # Cleanup
        with contextlib.suppress(StopAsyncIteration):
            await redis_generator.asend(None)


@pytest.mark.asyncio
async def test_get_redis_optional_returns_none_on_timeout_error(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test get_redis_optional returns None on timeout error."""
    from redis.exceptions import TimeoutError as RedisTimeoutError

    mock_redis_client.ping.side_effect = RedisTimeoutError("Timeout")

    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        redis_generator = get_redis_optional()
        client = await anext(redis_generator)

        assert client is None

        # Cleanup
        with contextlib.suppress(StopAsyncIteration):
            await redis_generator.asend(None)


@pytest.mark.asyncio
async def test_get_redis_optional_returns_none_on_generic_exception(
    mock_redis_pool, mock_redis_client, reset_redis_global_state
):
    """Test get_redis_optional returns None on generic exception."""
    mock_redis_client.ping.side_effect = Exception("Generic error")

    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        redis_generator = get_redis_optional()
        client = await anext(redis_generator)

        assert client is None

        # Cleanup
        with contextlib.suppress(StopAsyncIteration):
            await redis_generator.asend(None)


# ==============================================================================
# Additional Retry Logic Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_with_retry_executes_with_connection_error(redis_client):
    """Test with_retry handles ConnectionError retries properly."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    call_count = 0

    async def operation_with_retries():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RedisConnectionError("Connection failed")
        return "success"

    result = await redis_client.with_retry(
        operation=operation_with_retries,
        operation_name="test_operation",
        max_retries=3,
    )

    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_with_retry_executes_with_timeout_error(redis_client):
    """Test with_retry handles TimeoutError retries properly."""
    from redis.exceptions import TimeoutError as RedisTimeoutError

    call_count = 0

    async def operation_with_timeouts():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RedisTimeoutError("Operation timed out")
        return "success"

    result = await redis_client.with_retry(
        operation=operation_with_timeouts,
        operation_name="test_operation",
        max_retries=3,
    )

    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_with_retry_executes_with_redis_error(redis_client):
    """Test with_retry handles generic RedisError retries properly."""
    from redis.exceptions import RedisError

    call_count = 0

    async def operation_with_redis_errors():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RedisError("Redis error")
        return "success"

    result = await redis_client.with_retry(
        operation=operation_with_redis_errors,
        operation_name="test_operation",
        max_retries=3,
    )

    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_with_retry_all_retries_exhausted_connection_error(redis_client):
    """Test with_retry raises ConnectionError after all retries exhausted."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    async def operation_always_fails():
        raise RedisConnectionError("Connection failed")

    redis_client._base_delay = 0.01  # Speed up test
    with pytest.raises(RedisConnectionError, match="Connection failed"):
        await redis_client.with_retry(
            operation=operation_always_fails,
            operation_name="test_operation",
            max_retries=2,
        )


@pytest.mark.asyncio
async def test_with_retry_all_retries_exhausted_timeout_error(redis_client):
    """Test with_retry raises TimeoutError after all retries exhausted."""
    from redis.exceptions import TimeoutError as RedisTimeoutError

    async def operation_always_times_out():
        raise RedisTimeoutError("Timeout")

    redis_client._base_delay = 0.01  # Speed up test
    with pytest.raises(RedisTimeoutError, match="Timeout"):
        await redis_client.with_retry(
            operation=operation_always_times_out,
            operation_name="test_operation",
            max_retries=2,
        )


@pytest.mark.asyncio
async def test_get_from_queue_with_retry_success(redis_client, mock_redis_client):
    """Test get_from_queue_with_retry returns data successfully."""
    mock_redis_client.blpop.return_value = ("queue", '{"key": "value"}')

    result = await redis_client.get_from_queue_with_retry("queue", timeout=5)

    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_get_queue_length_with_retry_success(redis_client, mock_redis_client):
    """Test get_queue_length_with_retry returns length successfully."""
    mock_redis_client.llen.return_value = 10

    result = await redis_client.get_queue_length_with_retry("queue")

    assert result == 10


@pytest.mark.asyncio
async def test_get_with_retry_success(redis_client, mock_redis_client):
    """Test get_with_retry returns value successfully."""
    mock_redis_client.get.return_value = '{"key": "value"}'

    result = await redis_client.get_with_retry("key")

    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_set_with_retry_success(redis_client, mock_redis_client):
    """Test set_with_retry sets value successfully."""
    mock_redis_client.set.return_value = True

    result = await redis_client.set_with_retry("key", {"data": "value"}, expire=300)

    assert result is True


@pytest.mark.asyncio
async def test_add_to_queue_safe_with_retry_success(redis_client, mock_redis_client):
    """Test add_to_queue_safe_with_retry adds successfully."""
    mock_redis_client.llen.return_value = 5
    mock_redis_client.rpush.return_value = 6

    result = await redis_client.add_to_queue_safe_with_retry("queue", {"data": "test"})

    assert result.success is True
    assert result.queue_length == 6


# ==============================================================================
# Cache JSON Decode Error Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_get_returns_string_on_json_decode_error(redis_client, mock_redis_client):
    """Test get returns plain string when JSON decode fails."""
    mock_redis_client.get.return_value = "not json content"

    result = await redis_client.get("key")

    assert result == "not json content"
