"""Unit tests for Redis memory management operations (NEM-3416).

Tests the memory management methods in RedisClient:
- config_get: Get Redis configuration
- config_set: Set Redis configuration
- memory_stats: Get memory statistics
- memory_usage: Get memory usage for a key
- dbsize: Get key count
- scan_keys: Scan for keys by pattern
"""

from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis

from backend.core.redis import RedisClient


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with memory management operations."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    mock_client.aclose = AsyncMock()
    # Memory management operations
    mock_client.config_get = AsyncMock(return_value={"maxmemory": "268435456"})
    mock_client.config_set = AsyncMock(return_value=True)
    mock_client.memory_stats = AsyncMock(
        return_value={
            "peak.allocated": 100000000,
            "total.allocated": 50000000,
            "keys.count": 1000,
        }
    )
    mock_client.memory_usage = AsyncMock(return_value=1024)
    mock_client.dbsize = AsyncMock(return_value=5000)

    # Mock scan_iter as an async generator
    async def mock_scan_iter(match="*", count=100):
        keys = [f"key:{i}" for i in range(10)]
        for key in keys:
            yield key

    mock_client.scan_iter = mock_scan_iter
    return mock_client


@pytest.fixture
def mock_redis_pool():
    """Mock Redis connection pool."""
    with patch("backend.core.redis.ConnectionPool") as mock_pool_class:
        mock_pool_instance = AsyncMock()
        mock_pool_instance.disconnect = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool_instance
        yield mock_pool_class


@pytest.fixture
async def redis_client(mock_redis_pool, mock_redis_client):
    """Create a Redis client with mocked connection."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(redis_url="redis://localhost:6379/0")
        await client.connect()
        yield client
        await client.disconnect()


# config_get tests


@pytest.mark.asyncio
async def test_config_get_maxmemory(redis_client, mock_redis_client):
    """Test getting maxmemory configuration."""
    mock_redis_client.config_get.return_value = {"maxmemory": "268435456"}

    result = await redis_client.config_get("maxmemory")

    assert result == {"maxmemory": "268435456"}
    mock_redis_client.config_get.assert_awaited_once_with("maxmemory")


@pytest.mark.asyncio
async def test_config_get_maxmemory_policy(redis_client, mock_redis_client):
    """Test getting maxmemory-policy configuration."""
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}

    result = await redis_client.config_get("maxmemory-policy")

    assert result == {"maxmemory-policy": "volatile-lru"}


@pytest.mark.asyncio
async def test_config_get_pattern_wildcard(redis_client, mock_redis_client):
    """Test getting multiple config values with wildcard pattern."""
    mock_redis_client.config_get.return_value = {
        "maxmemory": "268435456",
        "maxmemory-policy": "volatile-lru",
        "maxmemory-samples": "5",
    }

    result = await redis_client.config_get("maxmemory*")

    assert "maxmemory" in result
    assert "maxmemory-policy" in result


# config_set tests


@pytest.mark.asyncio
async def test_config_set_maxmemory(redis_client, mock_redis_client):
    """Test setting maxmemory configuration."""
    result = await redis_client.config_set("maxmemory", "536870912")

    assert result is True
    mock_redis_client.config_set.assert_awaited_once_with("maxmemory", "536870912")


@pytest.mark.asyncio
async def test_config_set_maxmemory_policy(redis_client, mock_redis_client):
    """Test setting maxmemory-policy configuration."""
    result = await redis_client.config_set("maxmemory-policy", "allkeys-lru")

    assert result is True
    mock_redis_client.config_set.assert_awaited_once_with("maxmemory-policy", "allkeys-lru")


@pytest.mark.asyncio
async def test_config_set_returns_true_with_ok_response(redis_client, mock_redis_client):
    """Test config_set handles 'OK' string response."""
    mock_redis_client.config_set.return_value = "OK"

    result = await redis_client.config_set("maxmemory", "268435456")

    assert result is True


@pytest.mark.asyncio
async def test_config_set_returns_true_with_bool_response(redis_client, mock_redis_client):
    """Test config_set handles boolean True response."""
    mock_redis_client.config_set.return_value = True

    result = await redis_client.config_set("maxmemory", "268435456")

    assert result is True


# memory_stats tests


@pytest.mark.asyncio
async def test_memory_stats_returns_dict(redis_client, mock_redis_client):
    """Test memory_stats returns a dictionary."""
    mock_redis_client.memory_stats.return_value = {
        "peak.allocated": 100000000,
        "total.allocated": 50000000,
        "keys.count": 1000,
        "fragmentation.ratio": 1.2,
    }

    result = await redis_client.memory_stats()

    assert isinstance(result, dict)
    assert "peak.allocated" in result
    assert "total.allocated" in result


@pytest.mark.asyncio
async def test_memory_stats_comprehensive(redis_client, mock_redis_client):
    """Test memory_stats returns comprehensive statistics."""
    mock_redis_client.memory_stats.return_value = {
        "peak.allocated": 104857600,  # 100 MB
        "total.allocated": 52428800,  # 50 MB
        "startup.allocated": 1048576,  # 1 MB
        "replication.backlog": 0,
        "clients.slaves": 0,
        "clients.normal": 10240,
        "aof.buffer": 0,
        "keys.count": 5000,
        "keys.bytes-per-key": 104,
        "fragmentation.ratio": 1.15,
        "overhead.total": 2097152,
    }

    result = await redis_client.memory_stats()

    assert result["peak.allocated"] == 104857600
    assert result["total.allocated"] == 52428800
    assert result["keys.count"] == 5000
    assert result["fragmentation.ratio"] == 1.15


# memory_usage tests


@pytest.mark.asyncio
async def test_memory_usage_existing_key(redis_client, mock_redis_client):
    """Test getting memory usage for an existing key."""
    mock_redis_client.memory_usage.return_value = 1024

    result = await redis_client.memory_usage("cache:events:list")

    assert result == 1024
    mock_redis_client.memory_usage.assert_awaited_once_with("cache:events:list", samples=5)


@pytest.mark.asyncio
async def test_memory_usage_nonexistent_key(redis_client, mock_redis_client):
    """Test getting memory usage for a nonexistent key."""
    mock_redis_client.memory_usage.return_value = None

    result = await redis_client.memory_usage("nonexistent:key")

    assert result is None


@pytest.mark.asyncio
async def test_memory_usage_with_custom_samples(redis_client, mock_redis_client):
    """Test getting memory usage with custom sample count."""
    mock_redis_client.memory_usage.return_value = 2048

    result = await redis_client.memory_usage("large:hash", samples=10)

    assert result == 2048
    mock_redis_client.memory_usage.assert_awaited_once_with("large:hash", samples=10)


@pytest.mark.asyncio
async def test_memory_usage_large_key(redis_client, mock_redis_client):
    """Test memory usage for a large key."""
    mock_redis_client.memory_usage.return_value = 10485760  # 10 MB

    result = await redis_client.memory_usage("large:blob")

    assert result == 10485760


# dbsize tests


@pytest.mark.asyncio
async def test_dbsize_returns_key_count(redis_client, mock_redis_client):
    """Test dbsize returns the number of keys."""
    mock_redis_client.dbsize.return_value = 5000

    result = await redis_client.dbsize()

    assert result == 5000
    mock_redis_client.dbsize.assert_awaited_once()


@pytest.mark.asyncio
async def test_dbsize_empty_database(redis_client, mock_redis_client):
    """Test dbsize with empty database."""
    mock_redis_client.dbsize.return_value = 0

    result = await redis_client.dbsize()

    assert result == 0


@pytest.mark.asyncio
async def test_dbsize_large_database(redis_client, mock_redis_client):
    """Test dbsize with large number of keys."""
    mock_redis_client.dbsize.return_value = 1_000_000

    result = await redis_client.dbsize()

    assert result == 1_000_000


# scan_keys tests


@pytest.mark.asyncio
async def test_scan_keys_default_pattern(redis_client, mock_redis_client):
    """Test scan_keys with default pattern."""
    result = await redis_client.scan_keys()

    assert isinstance(result, list)
    assert len(result) == 10  # Mock returns 10 keys


@pytest.mark.asyncio
async def test_scan_keys_with_pattern(redis_client, mock_redis_client):
    """Test scan_keys with specific pattern."""

    async def mock_scan_iter_pattern(match="*", count=100):
        if "cache" in match:
            keys = ["cache:events:1", "cache:events:2", "cache:cameras:1"]
        else:
            keys = []
        for key in keys:
            yield key

    mock_redis_client.scan_iter = mock_scan_iter_pattern

    result = await redis_client.scan_keys(pattern="cache:*")

    assert len(result) == 3
    assert all(key.startswith("cache:") for key in result)


@pytest.mark.asyncio
async def test_scan_keys_max_keys_limit(redis_client, mock_redis_client):
    """Test scan_keys respects max_keys limit."""

    async def mock_scan_iter_many(match="*", count=100):
        for i in range(1000):
            yield f"key:{i}"

    mock_redis_client.scan_iter = mock_scan_iter_many

    result = await redis_client.scan_keys(max_keys=50)

    assert len(result) == 50


@pytest.mark.asyncio
async def test_scan_keys_empty_result(redis_client, mock_redis_client):
    """Test scan_keys with no matching keys."""

    async def mock_scan_iter_empty(match="*", count=100):
        return
        yield  # Make it an async generator

    mock_redis_client.scan_iter = mock_scan_iter_empty

    result = await redis_client.scan_keys(pattern="nonexistent:*")

    assert result == []


@pytest.mark.asyncio
async def test_scan_keys_custom_count(redis_client, mock_redis_client):
    """Test scan_keys with custom count parameter."""
    # The count parameter is a hint for Redis iteration batch size
    result = await redis_client.scan_keys(count=500)

    assert isinstance(result, list)


# Integration scenario tests


@pytest.mark.asyncio
async def test_memory_configuration_workflow(redis_client, mock_redis_client):
    """Test a typical memory configuration workflow."""
    # 1. Check current configuration
    await redis_client.config_get("maxmemory")
    await redis_client.config_get("maxmemory-policy")

    # 2. Set new memory limit (256 MB)
    await redis_client.config_set("maxmemory", "268435456")

    # 3. Set eviction policy
    await redis_client.config_set("maxmemory-policy", "volatile-lru")

    # Verify calls were made
    assert mock_redis_client.config_get.await_count == 2
    assert mock_redis_client.config_set.await_count == 2


@pytest.mark.asyncio
async def test_memory_analysis_workflow(redis_client, mock_redis_client):
    """Test a memory analysis workflow."""
    # 1. Get overall statistics
    stats = await redis_client.memory_stats()

    # 2. Get key count
    key_count = await redis_client.dbsize()

    # 3. Find large keys
    keys = await redis_client.scan_keys(pattern="cache:*", max_keys=100)

    # 4. Check memory usage of specific key
    for key in keys[:3]:
        await redis_client.memory_usage(key)

    assert stats is not None
    assert key_count >= 0
    assert isinstance(keys, list)


@pytest.mark.asyncio
async def test_eviction_policy_configuration(redis_client, mock_redis_client):
    """Test configuring different eviction policies."""
    policies = [
        "volatile-lru",
        "allkeys-lru",
        "volatile-ttl",
        "volatile-random",
        "allkeys-random",
        "noeviction",
    ]

    for policy in policies:
        await redis_client.config_set("maxmemory-policy", policy)

    assert mock_redis_client.config_set.await_count == len(policies)


# Edge case tests


@pytest.mark.asyncio
async def test_config_get_empty_pattern(redis_client, mock_redis_client):
    """Test config_get with pattern that matches nothing."""
    mock_redis_client.config_get.return_value = {}

    result = await redis_client.config_get("nonexistent*")

    assert result == {}


@pytest.mark.asyncio
async def test_memory_usage_with_special_key_names(redis_client, mock_redis_client):
    """Test memory_usage with special characters in key names."""
    special_keys = [
        "cache:events:{uuid}",
        "hll:cameras:2024-01-15",
        "user:email@domain.com",
    ]

    for key in special_keys:
        await redis_client.memory_usage(key)

    assert mock_redis_client.memory_usage.await_count == len(special_keys)
