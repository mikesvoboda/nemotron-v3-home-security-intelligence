"""Unit tests for Redis connection and operations."""

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from backend.core.redis import (
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
    mock_client.blpop = AsyncMock(return_value=None)
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
        client._retry_delay = 0.01  # Speed up test
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
        client._retry_delay = 0.01  # Speed up test

        with pytest.raises(ConnectionError):
            await client.connect()


@pytest.mark.asyncio
async def test_redis_disconnect(redis_client):
    """Test Redis disconnection."""
    await redis_client.disconnect()

    assert redis_client._client is None
    assert redis_client._pool is None
    assert redis_client._pubsub is None


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
    """Test adding a dictionary to a queue."""
    mock_redis_client.rpush.return_value = 1

    data = {"key": "value", "number": 42}
    result = await redis_client.add_to_queue("test_queue", data)

    assert result == 1
    mock_redis_client.rpush.assert_awaited_once()
    # Verify JSON serialization happened
    call_args = mock_redis_client.rpush.call_args[0]
    assert call_args[0] == "test_queue"
    assert '"key": "value"' in call_args[1]


@pytest.mark.asyncio
async def test_add_to_queue_with_string(redis_client, mock_redis_client):
    """Test adding a string to a queue."""
    mock_redis_client.rpush.return_value = 2

    result = await redis_client.add_to_queue("test_queue", "simple_string")

    assert result == 2
    mock_redis_client.rpush.assert_awaited_once_with("test_queue", "simple_string")


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
