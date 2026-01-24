"""Unit tests for Redis HyperLogLog operations (NEM-3414).

Tests the HyperLogLog methods in RedisClient for unique entity counting:
- pfadd: Add elements to HyperLogLog
- pfcount: Get cardinality estimate
- pfmerge: Merge multiple HyperLogLogs
"""

from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis

from backend.core.redis import RedisClient


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with HyperLogLog operations."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    mock_client.aclose = AsyncMock()
    # HyperLogLog operations
    mock_client.pfadd = AsyncMock(return_value=1)
    mock_client.pfcount = AsyncMock(return_value=5)
    mock_client.pfmerge = AsyncMock(return_value=True)
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


# pfadd tests


@pytest.mark.asyncio
async def test_pfadd_single_element(redis_client, mock_redis_client):
    """Test adding a single element to HyperLogLog."""
    result = await redis_client.pfadd("hll:test", "element1")

    assert result == 1
    mock_redis_client.pfadd.assert_awaited_once_with("hll:test", "element1")


@pytest.mark.asyncio
async def test_pfadd_multiple_elements(redis_client, mock_redis_client):
    """Test adding multiple elements to HyperLogLog in one call."""
    result = await redis_client.pfadd("hll:test", "elem1", "elem2", "elem3")

    assert result == 1
    mock_redis_client.pfadd.assert_awaited_once_with("hll:test", "elem1", "elem2", "elem3")


@pytest.mark.asyncio
async def test_pfadd_returns_zero_when_cardinality_unchanged(redis_client, mock_redis_client):
    """Test pfadd returns 0 when cardinality estimate doesn't change."""
    mock_redis_client.pfadd.return_value = 0

    result = await redis_client.pfadd("hll:test", "duplicate")

    assert result == 0


@pytest.mark.asyncio
async def test_pfadd_with_camera_id(redis_client, mock_redis_client):
    """Test adding camera ID for unique camera counting."""
    camera_id = "cam-front-door-001"
    result = await redis_client.pfadd("hll:cameras:2024-01-15", camera_id)

    assert result == 1
    mock_redis_client.pfadd.assert_awaited_once_with("hll:cameras:2024-01-15", camera_id)


@pytest.mark.asyncio
async def test_pfadd_with_event_ids(redis_client, mock_redis_client):
    """Test adding multiple event IDs in batch."""
    event_ids = ["event-abc", "event-def", "event-ghi"]
    result = await redis_client.pfadd("hll:events:2024-01-15", *event_ids)

    assert result == 1
    mock_redis_client.pfadd.assert_awaited_once_with("hll:events:2024-01-15", *event_ids)


# pfcount tests


@pytest.mark.asyncio
async def test_pfcount_single_key(redis_client, mock_redis_client):
    """Test getting cardinality from a single HyperLogLog."""
    mock_redis_client.pfcount.return_value = 42

    result = await redis_client.pfcount("hll:cameras:2024-01-15")

    assert result == 42
    mock_redis_client.pfcount.assert_awaited_once_with("hll:cameras:2024-01-15")


@pytest.mark.asyncio
async def test_pfcount_multiple_keys(redis_client, mock_redis_client):
    """Test getting union cardinality from multiple HyperLogLogs."""
    mock_redis_client.pfcount.return_value = 100

    result = await redis_client.pfcount(
        "hll:cameras:2024-01-15",
        "hll:cameras:2024-01-16",
        "hll:cameras:2024-01-17",
    )

    assert result == 100
    mock_redis_client.pfcount.assert_awaited_once_with(
        "hll:cameras:2024-01-15",
        "hll:cameras:2024-01-16",
        "hll:cameras:2024-01-17",
    )


@pytest.mark.asyncio
async def test_pfcount_empty_hyperloglog(redis_client, mock_redis_client):
    """Test getting cardinality from empty/non-existent HyperLogLog."""
    mock_redis_client.pfcount.return_value = 0

    result = await redis_client.pfcount("hll:nonexistent")

    assert result == 0


@pytest.mark.asyncio
async def test_pfcount_large_cardinality(redis_client, mock_redis_client):
    """Test pfcount with large cardinality values."""
    # HyperLogLog can estimate very large cardinalities
    mock_redis_client.pfcount.return_value = 1_000_000

    result = await redis_client.pfcount("hll:large-set")

    assert result == 1_000_000


# pfmerge tests


@pytest.mark.asyncio
async def test_pfmerge_two_hyperloglogs(redis_client, mock_redis_client):
    """Test merging two HyperLogLogs."""
    result = await redis_client.pfmerge(
        "hll:merged",
        "hll:source1",
        "hll:source2",
    )

    assert result is True
    mock_redis_client.pfmerge.assert_awaited_once_with(
        "hll:merged",
        "hll:source1",
        "hll:source2",
    )


@pytest.mark.asyncio
async def test_pfmerge_multiple_hyperloglogs(redis_client, mock_redis_client):
    """Test merging multiple HyperLogLogs (e.g., 7 days of data)."""
    daily_keys = [f"hll:events:2024-01-{15 + i:02d}" for i in range(7)]

    result = await redis_client.pfmerge("hll:events:week-3", *daily_keys)

    assert result is True
    mock_redis_client.pfmerge.assert_awaited_once_with("hll:events:week-3", *daily_keys)


@pytest.mark.asyncio
async def test_pfmerge_returns_true_with_ok_response(redis_client, mock_redis_client):
    """Test pfmerge handles 'OK' string response."""
    mock_redis_client.pfmerge.return_value = "OK"

    result = await redis_client.pfmerge("hll:dest", "hll:src")

    assert result is True


@pytest.mark.asyncio
async def test_pfmerge_returns_true_with_bool_response(redis_client, mock_redis_client):
    """Test pfmerge handles boolean True response."""
    mock_redis_client.pfmerge.return_value = True

    result = await redis_client.pfmerge("hll:dest", "hll:src")

    assert result is True


# Integration scenario tests


@pytest.mark.asyncio
async def test_hyperloglog_camera_counting_workflow(redis_client, mock_redis_client):
    """Test a realistic camera unique counting workflow."""
    # Add cameras throughout the day
    cameras = ["cam-001", "cam-002", "cam-003", "cam-001"]  # cam-001 appears twice

    for camera in cameras:
        await redis_client.pfadd("hll:cameras:today", camera)

    # Verify count call
    await redis_client.pfcount("hll:cameras:today")

    # pfadd should be called 4 times
    assert mock_redis_client.pfadd.await_count == 4


@pytest.mark.asyncio
async def test_hyperloglog_detection_type_counting(redis_client, mock_redis_client):
    """Test counting unique detection types."""
    detection_types = ["person", "vehicle", "animal", "person", "person"]

    for det_type in detection_types:
        await redis_client.pfadd("hll:detection_types:today", det_type)

    mock_redis_client.pfcount.return_value = 3  # 3 unique types

    count = await redis_client.pfcount("hll:detection_types:today")

    assert count == 3


@pytest.mark.asyncio
async def test_hyperloglog_weekly_aggregation(redis_client, mock_redis_client):
    """Test aggregating daily HyperLogLogs into weekly count."""
    # Simulate daily keys
    daily_keys = ["hll:events:day1", "hll:events:day2", "hll:events:day3"]

    # Merge into weekly
    await redis_client.pfmerge("hll:events:week", *daily_keys)

    # Get weekly count
    mock_redis_client.pfcount.return_value = 500

    count = await redis_client.pfcount("hll:events:week")

    assert count == 500


# Edge case tests


@pytest.mark.asyncio
async def test_pfadd_with_empty_string(redis_client, mock_redis_client):
    """Test pfadd handles empty string values."""
    await redis_client.pfadd("hll:test", "")

    mock_redis_client.pfadd.assert_awaited_once_with("hll:test", "")


@pytest.mark.asyncio
async def test_pfadd_with_special_characters(redis_client, mock_redis_client):
    """Test pfadd handles special characters in values."""
    special_values = ["cam:front:door", "event/2024/01", "user@domain"]

    await redis_client.pfadd("hll:test", *special_values)

    mock_redis_client.pfadd.assert_awaited_once_with("hll:test", *special_values)


@pytest.mark.asyncio
async def test_pfcount_with_nonexistent_keys(redis_client, mock_redis_client):
    """Test pfcount with mix of existing and nonexistent keys."""
    mock_redis_client.pfcount.return_value = 10

    result = await redis_client.pfcount(
        "hll:existing",
        "hll:nonexistent1",
        "hll:nonexistent2",
    )

    # Redis treats nonexistent keys as empty HLLs
    assert result == 10


@pytest.mark.asyncio
async def test_pfmerge_overwrites_destination(redis_client, mock_redis_client):
    """Test that pfmerge overwrites existing destination key."""
    # First merge
    await redis_client.pfmerge("hll:dest", "hll:src1")

    # Second merge (overwrites)
    await redis_client.pfmerge("hll:dest", "hll:src2", "hll:src3")

    assert mock_redis_client.pfmerge.await_count == 2
