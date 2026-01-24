"""Unit tests for UniqueCounterService (NEM-3414).

Tests the HyperLogLog-based unique entity counting service:
- Camera unique counting
- Event unique counting
- Detection unique counting
- Entity (person/vehicle) unique counting
- Time window management
- Batch operations
- Statistics aggregation
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.unique_counter_service import (
    CardinalityStats,
    TimeWindow,
    UniqueCounterService,
    _get_time_key,
)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for UniqueCounterService tests."""
    mock_client = AsyncMock()
    mock_client.pfadd = AsyncMock(return_value=1)
    mock_client.pfcount = AsyncMock(return_value=10)
    mock_client.pfmerge = AsyncMock(return_value=True)
    mock_client.expire = AsyncMock(return_value=True)
    mock_client.exists = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def mock_settings():
    """Mock settings for UniqueCounterService."""
    mock = AsyncMock()
    mock.hll_ttl_seconds = 86400
    mock.hll_key_prefix = "hll"
    mock.redis_key_prefix = "nemotron"
    return mock


@pytest.fixture
def counter_service(mock_redis_client, mock_settings):
    """Create UniqueCounterService with mocked dependencies."""
    with patch("backend.services.unique_counter_service.get_settings", return_value=mock_settings):
        service = UniqueCounterService(mock_redis_client)
        return service


# Time key generation tests
# Note: These tests use freezegun instead of mocking datetime.now
# because datetime.strftime is read-only and cannot be mocked


def test_get_time_key_hourly():
    """Test hourly time key format."""
    # Use the actual function and verify the format is correct
    key = _get_time_key("hourly")
    # Format should be YYYY-MM-DD-HH
    assert len(key) == 13
    parts = key.split("-")
    assert len(parts) == 4
    assert len(parts[0]) == 4  # Year
    assert len(parts[1]) == 2  # Month
    assert len(parts[2]) == 2  # Day
    assert len(parts[3]) == 2  # Hour


def test_get_time_key_daily():
    """Test daily time key format."""
    key = _get_time_key("daily")
    # Format should be YYYY-MM-DD
    assert len(key) == 10
    parts = key.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4  # Year
    assert len(parts[1]) == 2  # Month
    assert len(parts[2]) == 2  # Day


def test_get_time_key_weekly():
    """Test weekly time key format."""
    key = _get_time_key("weekly")
    # Format should be YYYY-WWW
    assert key.startswith("20")  # Year starts with 20
    assert "-W" in key


def test_get_time_key_monthly():
    """Test monthly time key format."""
    key = _get_time_key("monthly")
    # Format should be YYYY-MM
    assert len(key) == 7
    parts = key.split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 4  # Year
    assert len(parts[1]) == 2  # Month


# Camera counting tests


@pytest.mark.asyncio
async def test_add_unique_camera(counter_service, mock_redis_client):
    """Test adding a unique camera."""
    result = await counter_service.add_unique_camera("cam-front-door")

    assert result is True
    mock_redis_client.pfadd.assert_awaited_once()
    mock_redis_client.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_unique_camera_duplicate(counter_service, mock_redis_client):
    """Test adding a duplicate camera returns False."""
    mock_redis_client.pfadd.return_value = 0

    result = await counter_service.add_unique_camera("cam-front-door")

    assert result is False


@pytest.mark.asyncio
async def test_get_unique_camera_count(counter_service, mock_redis_client):
    """Test getting unique camera count."""
    mock_redis_client.pfcount.return_value = 5

    count = await counter_service.get_unique_camera_count()

    assert count == 5


@pytest.mark.asyncio
async def test_get_unique_camera_count_hourly(counter_service, mock_redis_client):
    """Test getting hourly unique camera count."""
    mock_redis_client.pfcount.return_value = 3

    count = await counter_service.get_unique_camera_count(window="hourly")

    assert count == 3


# Event counting tests


@pytest.mark.asyncio
async def test_add_unique_event(counter_service, mock_redis_client):
    """Test adding a unique event."""
    result = await counter_service.add_unique_event("event-123")

    assert result is True
    mock_redis_client.pfadd.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_unique_event_count(counter_service, mock_redis_client):
    """Test getting unique event count."""
    mock_redis_client.pfcount.return_value = 42

    count = await counter_service.get_unique_event_count()

    assert count == 42


# Detection counting tests


@pytest.mark.asyncio
async def test_add_unique_detection(counter_service, mock_redis_client):
    """Test adding a unique detection."""
    result = await counter_service.add_unique_detection("det-456")

    assert result is True


@pytest.mark.asyncio
async def test_get_unique_detection_count(counter_service, mock_redis_client):
    """Test getting unique detection count."""
    mock_redis_client.pfcount.return_value = 100

    count = await counter_service.get_unique_detection_count()

    assert count == 100


# Entity counting tests


@pytest.mark.asyncio
async def test_add_unique_entity(counter_service, mock_redis_client):
    """Test adding a unique entity (person/vehicle)."""
    result = await counter_service.add_unique_entity("entity-person-001")

    assert result is True


@pytest.mark.asyncio
async def test_get_unique_entity_count(counter_service, mock_redis_client):
    """Test getting unique entity count."""
    mock_redis_client.pfcount.return_value = 15

    count = await counter_service.get_unique_entity_count()

    assert count == 15


# Detection type counting tests


@pytest.mark.asyncio
async def test_add_detection_type(counter_service, mock_redis_client):
    """Test adding a detection type."""
    result = await counter_service.add_detection_type("person")

    assert result is True


@pytest.mark.asyncio
async def test_get_unique_detection_type_count(counter_service, mock_redis_client):
    """Test getting unique detection type count."""
    mock_redis_client.pfcount.return_value = 5

    count = await counter_service.get_unique_detection_type_count()

    assert count == 5


# Batch operation tests


@pytest.mark.asyncio
async def test_add_batch_cameras(counter_service, mock_redis_client):
    """Test adding multiple cameras in batch."""
    cameras = ["cam-001", "cam-002", "cam-003"]

    result = await counter_service.add_batch_cameras(cameras)

    assert result == 1
    mock_redis_client.pfadd.assert_awaited_once()
    # Verify all cameras were passed
    call_args = mock_redis_client.pfadd.call_args
    assert "cam-001" in call_args[0]
    assert "cam-002" in call_args[0]
    assert "cam-003" in call_args[0]


@pytest.mark.asyncio
async def test_add_batch_cameras_empty_list(counter_service, mock_redis_client):
    """Test adding empty list of cameras."""
    result = await counter_service.add_batch_cameras([])

    assert result == 0
    mock_redis_client.pfadd.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_batch_events(counter_service, mock_redis_client):
    """Test adding multiple events in batch."""
    events = ["event-a", "event-b", "event-c", "event-d"]

    result = await counter_service.add_batch_events(events)

    assert result == 1


@pytest.mark.asyncio
async def test_add_batch_events_empty_list(counter_service, mock_redis_client):
    """Test adding empty list of events."""
    result = await counter_service.add_batch_events([])

    assert result == 0
    mock_redis_client.pfadd.assert_not_awaited()


# Merged count tests


@pytest.mark.asyncio
async def test_get_merged_count(counter_service, mock_redis_client):
    """Test getting merged count across multiple windows."""
    mock_redis_client.pfcount.return_value = 150

    windows = ["2024-01-15", "2024-01-16", "2024-01-17"]
    count = await counter_service.get_merged_count("cameras", windows)

    assert count == 150


@pytest.mark.asyncio
async def test_get_merged_count_no_existing_keys(counter_service, mock_redis_client):
    """Test merged count when no keys exist."""
    mock_redis_client.exists.return_value = 0

    windows = ["2024-01-01", "2024-01-02"]
    count = await counter_service.get_merged_count("cameras", windows)

    assert count == 0


# Statistics tests


@pytest.mark.asyncio
async def test_get_cardinality_stats(counter_service, mock_redis_client):
    """Test getting cardinality statistics."""
    # Set up different return values for each pfcount call
    mock_redis_client.pfcount.side_effect = [10, 50, 200, 5]

    stats = await counter_service.get_cardinality_stats()

    assert isinstance(stats, CardinalityStats)
    assert stats.unique_cameras == 10
    assert stats.unique_events == 50
    assert stats.unique_detections == 200
    assert stats.unique_entities == 5
    assert stats.time_window == "daily"
    assert stats.estimated_error_rate == 0.0081


@pytest.mark.asyncio
async def test_get_cardinality_stats_hourly(counter_service, mock_redis_client):
    """Test getting hourly cardinality statistics."""
    mock_redis_client.pfcount.side_effect = [2, 10, 30, 1]

    stats = await counter_service.get_cardinality_stats(window="hourly")

    assert stats.time_window == "hourly"
    assert stats.unique_cameras == 2


# Key building tests


def test_build_key_daily(counter_service):
    """Test building a daily key."""
    with patch("backend.services.unique_counter_service._get_time_key", return_value="2024-01-15"):
        key = counter_service._build_key("cameras", "daily")

    assert key == "nemotron:hll:cameras:2024-01-15"


def test_build_key_hourly(counter_service):
    """Test building an hourly key."""
    with patch(
        "backend.services.unique_counter_service._get_time_key", return_value="2024-01-15-14"
    ):
        key = counter_service._build_key("events", "hourly")

    assert key == "nemotron:hll:events:2024-01-15-14"


# Time window types


def test_time_window_types():
    """Test that TimeWindow type includes all expected values."""
    windows: list[TimeWindow] = ["hourly", "daily", "weekly", "monthly"]

    for window in windows:
        # Should not raise any type errors
        assert window in ["hourly", "daily", "weekly", "monthly"]


# CardinalityStats dataclass tests


def test_cardinality_stats_creation():
    """Test CardinalityStats dataclass creation."""
    stats = CardinalityStats(
        unique_cameras=10,
        unique_events=50,
        unique_detections=200,
        unique_entities=5,
        time_window="daily",
        window_start="2024-01-15T00:00:00+00:00",
    )

    assert stats.unique_cameras == 10
    assert stats.unique_events == 50
    assert stats.unique_detections == 200
    assert stats.unique_entities == 5
    assert stats.time_window == "daily"
    assert stats.estimated_error_rate == 0.0081  # Default


def test_cardinality_stats_frozen():
    """Test CardinalityStats is frozen (immutable)."""
    stats = CardinalityStats(
        unique_cameras=10,
        unique_events=50,
        unique_detections=200,
        unique_entities=5,
        time_window="daily",
        window_start="2024-01-15T00:00:00+00:00",
    )

    # Should raise FrozenInstanceError
    with pytest.raises(Exception):
        stats.unique_cameras = 20  # type: ignore[misc]


# Integration scenario tests


@pytest.mark.asyncio
async def test_daily_analytics_workflow(counter_service, mock_redis_client):
    """Test a realistic daily analytics workflow."""
    # Simulate events throughout the day
    cameras = ["cam-001", "cam-002", "cam-001", "cam-003"]
    events = ["event-a", "event-b", "event-c"]
    detection_types = ["person", "vehicle", "person", "animal"]

    # Add cameras
    for cam in cameras:
        await counter_service.add_unique_camera(cam)

    # Add events
    for event in events:
        await counter_service.add_unique_event(event)

    # Add detection types
    for det_type in detection_types:
        await counter_service.add_detection_type(det_type)

    # Verify pfadd was called appropriate number of times
    # 4 cameras + 3 events + 4 detection types = 11 calls
    assert mock_redis_client.pfadd.await_count == 11


@pytest.mark.asyncio
async def test_batch_processing_workflow(counter_service, mock_redis_client):
    """Test batch processing for high-throughput scenarios."""
    # Simulate batch from detection pipeline
    camera_batch = [f"cam-{i:03d}" for i in range(100)]
    event_batch = [f"event-{i}" for i in range(500)]

    await counter_service.add_batch_cameras(camera_batch)
    await counter_service.add_batch_events(event_batch)

    # Should be 2 pfadd calls (one per batch)
    assert mock_redis_client.pfadd.await_count == 2
