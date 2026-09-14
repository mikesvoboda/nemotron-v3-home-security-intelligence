"""Unit tests for RedisMemoryService (NEM-3416).

Tests the Redis memory optimization service:
- Memory limit configuration
- Eviction policy management
- Memory statistics collection
- Large key identification
- Memory optimization recommendations
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.redis_memory_service import (
    KeyMemoryInfo,
    MemoryStats,
    RedisMemoryService,
)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for RedisMemoryService tests."""
    mock_client = AsyncMock()
    mock_client.config_get = AsyncMock(return_value={"maxmemory-policy": "volatile-lru"})
    mock_client.config_set = AsyncMock(return_value=True)
    mock_client.info = AsyncMock(
        return_value={
            "used_memory": 52428800,  # 50 MB
            "used_memory_peak": 104857600,  # 100 MB
            "maxmemory": 268435456,  # 256 MB
            "mem_fragmentation_ratio": 1.15,
        }
    )
    mock_client.memory_usage = AsyncMock(return_value=1024)
    mock_client.dbsize = AsyncMock(return_value=5000)
    mock_client.scan_keys = AsyncMock(return_value=["key:1", "key:2", "key:3"])
    mock_client.exists = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def mock_settings():
    """Mock settings for RedisMemoryService."""
    mock = AsyncMock()
    mock.redis_memory_limit_mb = 256
    mock.redis_memory_policy = "volatile-lru"
    mock.redis_memory_apply_on_startup = True
    return mock


@pytest.fixture
def memory_service(mock_redis_client, mock_settings):
    """Create RedisMemoryService with mocked dependencies."""
    with patch("backend.services.redis_memory_service.get_settings", return_value=mock_settings):
        service = RedisMemoryService(mock_redis_client)
        return service


# configure_memory_limits tests


@pytest.mark.asyncio
async def test_configure_memory_limits_success(memory_service, mock_redis_client):
    """Test successful memory limit configuration."""
    result = await memory_service.configure_memory_limits()

    assert result["applied"] is True
    assert result["maxmemory_mb"] == 256
    assert result["maxmemory_policy"] == "volatile-lru"
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_configure_memory_limits_skipped_when_disabled(mock_redis_client, mock_settings):
    """Test configuration is skipped when apply_on_startup is False."""
    mock_settings.redis_memory_apply_on_startup = False

    with patch("backend.services.redis_memory_service.get_settings", return_value=mock_settings):
        service = RedisMemoryService(mock_redis_client)
        result = await service.configure_memory_limits()

    assert result["applied"] is False
    assert result["skipped"] is True
    mock_redis_client.config_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_configure_memory_limits_no_limit_when_zero(mock_redis_client, mock_settings):
    """Test no memory limit is set when configured as 0."""
    mock_settings.redis_memory_limit_mb = 0

    with patch("backend.services.redis_memory_service.get_settings", return_value=mock_settings):
        service = RedisMemoryService(mock_redis_client)
        result = await service.configure_memory_limits()

    # Should only set policy, not maxmemory
    assert result["maxmemory_mb"] is None
    assert result["maxmemory_policy"] == "volatile-lru"


@pytest.mark.asyncio
async def test_configure_memory_limits_handles_error(memory_service, mock_redis_client):
    """Test graceful handling of configuration errors."""
    mock_redis_client.config_set.side_effect = [
        Exception("Permission denied"),
        True,
    ]

    result = await memory_service.configure_memory_limits()

    assert result["applied"] is False
    assert len(result["errors"]) == 1
    assert "Permission denied" in result["errors"][0]


# get_memory_stats tests


@pytest.mark.asyncio
async def test_get_memory_stats(memory_service, mock_redis_client):
    """Test getting memory statistics."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 104857600,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.15,
        },
        {"evicted_keys": 100},
        {"db0": {"keys": 5000, "expires": 3000, "avg_ttl": 3600}},
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}
    mock_redis_client.dbsize.return_value = 5000

    stats = await memory_service.get_memory_stats()

    assert isinstance(stats, MemoryStats)
    assert stats.used_memory_bytes == 52428800
    assert stats.used_memory_mb == pytest.approx(50.0, rel=0.1)
    assert stats.maxmemory_bytes == 268435456
    assert stats.maxmemory_policy == "volatile-lru"
    assert stats.is_memory_limited is True


@pytest.mark.asyncio
async def test_get_memory_stats_unlimited(memory_service, mock_redis_client):
    """Test memory stats when no memory limit is set."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 104857600,
            "maxmemory": 0,  # No limit
            "mem_fragmentation_ratio": 1.15,
        },
        {"evicted_keys": 0},
        {},
    ]

    stats = await memory_service.get_memory_stats()

    assert stats.is_memory_limited is False
    assert stats.memory_usage_percent == 0.0


@pytest.mark.asyncio
async def test_get_memory_stats_calculates_usage_percent(memory_service, mock_redis_client):
    """Test memory usage percentage calculation."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 134217728,  # 128 MB
            "used_memory_peak": 134217728,
            "maxmemory": 268435456,  # 256 MB
            "mem_fragmentation_ratio": 1.0,
        },
        {"evicted_keys": 0},
        {},
    ]

    stats = await memory_service.get_memory_stats()

    # 128 / 256 = 50%
    assert stats.memory_usage_percent == pytest.approx(50.0, rel=0.1)


# get_current_config tests


@pytest.mark.asyncio
async def test_get_current_config(memory_service, mock_redis_client):
    """Test getting current Redis configuration."""
    mock_redis_client.config_get.side_effect = [
        {"maxmemory": "268435456"},
        {"maxmemory-policy": "volatile-lru"},
    ]

    config = await memory_service.get_current_config()

    assert config["maxmemory_bytes"] == "268435456"
    assert config["maxmemory_mb"] == "256.00"
    assert config["maxmemory_policy"] == "volatile-lru"
    assert config["maxmemory_human"] == "256MB"


@pytest.mark.asyncio
async def test_get_current_config_unlimited(memory_service, mock_redis_client):
    """Test current config when no memory limit is set."""
    mock_redis_client.config_get.side_effect = [
        {"maxmemory": "0"},
        {"maxmemory-policy": "noeviction"},
    ]

    config = await memory_service.get_current_config()

    assert config["maxmemory_bytes"] == "0"
    assert config["maxmemory_human"] == "unlimited"


# find_large_keys tests


@pytest.mark.asyncio
async def test_find_large_keys(memory_service, mock_redis_client):
    """Test finding large keys."""
    mock_redis_client.scan_keys.return_value = ["key:1", "key:2", "key:3"]
    mock_redis_client.memory_usage.side_effect = [2048, 1024, 4096]

    large_keys = await memory_service.find_large_keys(min_size_bytes=1024)

    assert len(large_keys) == 3
    # Should be sorted by size descending
    assert large_keys[0].memory_bytes == 4096
    assert large_keys[1].memory_bytes == 2048
    assert large_keys[2].memory_bytes == 1024


@pytest.mark.asyncio
async def test_find_large_keys_filters_small_keys(memory_service, mock_redis_client):
    """Test that small keys are filtered out."""
    mock_redis_client.scan_keys.return_value = ["key:1", "key:2", "key:3"]
    mock_redis_client.memory_usage.side_effect = [512, 2048, 256]

    large_keys = await memory_service.find_large_keys(min_size_bytes=1024)

    # Only key:2 should be included
    assert len(large_keys) == 1
    assert large_keys[0].memory_bytes == 2048


@pytest.mark.asyncio
async def test_find_large_keys_respects_max_keys(memory_service, mock_redis_client):
    """Test that max_keys limit is respected."""
    mock_redis_client.scan_keys.return_value = [f"key:{i}" for i in range(100)]
    mock_redis_client.memory_usage.return_value = 2048

    large_keys = await memory_service.find_large_keys(max_keys=10)

    assert len(large_keys) <= 10


@pytest.mark.asyncio
async def test_find_large_keys_handles_nonexistent_keys(memory_service, mock_redis_client):
    """Test handling of keys that return None for memory usage."""
    mock_redis_client.scan_keys.return_value = ["key:1", "key:2", "key:3"]
    mock_redis_client.memory_usage.side_effect = [2048, None, 1024]

    large_keys = await memory_service.find_large_keys(min_size_bytes=1024)

    # key:2 should be skipped
    assert len(large_keys) == 2


# get_key_memory_usage tests


@pytest.mark.asyncio
async def test_get_key_memory_usage(memory_service, mock_redis_client):
    """Test getting memory usage for a specific key."""
    mock_redis_client.memory_usage.return_value = 4096

    usage = await memory_service.get_key_memory_usage("cache:events:list")

    assert usage == 4096


@pytest.mark.asyncio
async def test_get_key_memory_usage_nonexistent(memory_service, mock_redis_client):
    """Test memory usage for nonexistent key."""
    mock_redis_client.memory_usage.return_value = None

    usage = await memory_service.get_key_memory_usage("nonexistent")

    assert usage is None


# get_memory_recommendations tests


@pytest.mark.asyncio
async def test_recommendations_no_memory_limit(memory_service, mock_redis_client):
    """Test recommendations when no memory limit is set."""
    mock_redis_client.info.side_effect = [
        {"used_memory": 52428800, "used_memory_peak": 52428800, "maxmemory": 0},
        {"evicted_keys": 0},
        {},
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "noeviction"}

    recommendations = await memory_service.get_memory_recommendations()

    assert any("memory limit" in r.lower() for r in recommendations)


@pytest.mark.asyncio
async def test_recommendations_high_memory_usage(memory_service, mock_redis_client):
    """Test recommendations when memory usage is high."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 245366784,  # ~234 MB (92% of 256 MB)
            "used_memory_peak": 245366784,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.1,
        },
        {"evicted_keys": 0},
        {},
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}

    recommendations = await memory_service.get_memory_recommendations()

    assert any("critically high" in r.lower() or "elevated" in r.lower() for r in recommendations)


@pytest.mark.asyncio
async def test_recommendations_noeviction_with_limit(memory_service, mock_redis_client):
    """Test recommendations for noeviction policy with memory limit."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 52428800,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.1,
        },
        {"evicted_keys": 0},
        {},
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "noeviction"}

    recommendations = await memory_service.get_memory_recommendations()

    assert any("noeviction" in r.lower() for r in recommendations)


@pytest.mark.asyncio
async def test_recommendations_high_fragmentation(memory_service, mock_redis_client):
    """Test recommendations for high memory fragmentation."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 52428800,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 2.0,  # High fragmentation
        },
        {"evicted_keys": 0},
        {},
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}

    recommendations = await memory_service.get_memory_recommendations()

    assert any("fragmentation" in r.lower() for r in recommendations)


@pytest.mark.asyncio
async def test_recommendations_evicted_keys(memory_service, mock_redis_client):
    """Test recommendations when keys have been evicted."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 104857600,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.1,
        },
        {"evicted_keys": 500},
        {},
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}

    recommendations = await memory_service.get_memory_recommendations()

    assert any("evicted" in r.lower() for r in recommendations)


@pytest.mark.asyncio
async def test_recommendations_healthy_config(memory_service, mock_redis_client):
    """Test recommendations for healthy configuration."""
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 26214400,  # 25 MB (10% usage)
            "used_memory_peak": 26214400,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.05,
        },
        {"evicted_keys": 0},
        {"db0": {"keys": 1000, "expires": 800}},  # 80% have TTL
    ]
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}
    mock_redis_client.dbsize.return_value = 1000

    recommendations = await memory_service.get_memory_recommendations()

    assert any("healthy" in r.lower() for r in recommendations)


# Data class tests


def test_memory_stats_dataclass():
    """Test MemoryStats dataclass creation."""
    stats = MemoryStats(
        used_memory_bytes=52428800,
        used_memory_mb=50.0,
        used_memory_peak_bytes=104857600,
        used_memory_peak_mb=100.0,
        maxmemory_bytes=268435456,
        maxmemory_mb=256.0,
        maxmemory_policy="volatile-lru",
        memory_fragmentation_ratio=1.15,
        total_keys=5000,
        keys_with_ttl=3000,
        evicted_keys=0,
        is_memory_limited=True,
        memory_usage_percent=19.53,
    )

    assert stats.used_memory_bytes == 52428800
    assert stats.maxmemory_policy == "volatile-lru"
    assert stats.is_memory_limited is True


def test_key_memory_info_dataclass():
    """Test KeyMemoryInfo dataclass creation."""
    key_info = KeyMemoryInfo(
        key="cache:events:list",
        memory_bytes=4096,
        memory_kb=4.0,
        key_type="list",
    )

    assert key_info.key == "cache:events:list"
    assert key_info.memory_bytes == 4096
    assert key_info.memory_kb == 4.0
    assert key_info.key_type == "list"


def test_key_memory_info_default_type():
    """Test KeyMemoryInfo with default key_type."""
    key_info = KeyMemoryInfo(
        key="test:key",
        memory_bytes=1024,
        memory_kb=1.0,
    )

    assert key_info.key_type is None


# Integration scenario tests


@pytest.mark.asyncio
async def test_memory_optimization_workflow(memory_service, mock_redis_client):
    """Test a complete memory optimization workflow."""
    # 1. Get current configuration
    mock_redis_client.config_get.side_effect = [
        {"maxmemory": "268435456"},
        {"maxmemory-policy": "volatile-lru"},
    ]

    config = await memory_service.get_current_config()
    assert config["maxmemory_policy"] == "volatile-lru"

    # Reset mock for stats - set side_effect to None to use return_value
    mock_redis_client.config_get.reset_mock()
    mock_redis_client.config_get.side_effect = None
    mock_redis_client.config_get.return_value = {"maxmemory-policy": "volatile-lru"}

    # 2. Get memory statistics
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 104857600,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.15,
        },
        {"evicted_keys": 0},
        {},
    ]

    stats = await memory_service.get_memory_stats()
    assert stats.is_memory_limited is True

    # 3. Find large keys
    mock_redis_client.scan_keys.return_value = ["cache:large:1", "cache:large:2"]
    mock_redis_client.memory_usage.side_effect = None
    mock_redis_client.memory_usage.side_effect = [10240, 8192]

    large_keys = await memory_service.find_large_keys(min_size_bytes=4096)
    assert len(large_keys) == 2

    # 4. Get recommendations - reset info side_effect
    mock_redis_client.info.side_effect = [
        {
            "used_memory": 52428800,
            "used_memory_peak": 104857600,
            "maxmemory": 268435456,
            "mem_fragmentation_ratio": 1.15,
        },
        {"evicted_keys": 0},
        {},
    ]

    recommendations = await memory_service.get_memory_recommendations()
    assert len(recommendations) >= 1
