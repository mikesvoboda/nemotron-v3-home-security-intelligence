"""Unit tests for SystemBroadcaster performance history storage.

Tests the circular buffer storage for historical performance metrics
used by the GET /api/system/performance/history endpoint.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.performance import (
    PerformanceUpdate,
    TimeRange,
)
from backend.services.system_broadcaster import SystemBroadcaster

# =============================================================================
# Tests for performance history storage initialization
# =============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_has_history_buffer():
    """Test SystemBroadcaster initializes with history buffer."""
    broadcaster = SystemBroadcaster()

    # Should have a history buffer attribute
    assert hasattr(broadcaster, "_performance_history")
    assert isinstance(broadcaster._performance_history, deque)


@pytest.mark.asyncio
async def test_system_broadcaster_history_buffer_max_size():
    """Test SystemBroadcaster history buffer has correct max size.

    Buffer should store 60 snapshots for the longest time range (60m).
    At 5s intervals, 60 minutes = 720 snapshots, but we sample:
    - 5m: every snapshot (60 points)
    - 15m: every 3rd snapshot (60 points)
    - 60m: every 12th snapshot (60 points)

    So we only need to keep the last 720 snapshots (60min / 5s interval).
    """
    broadcaster = SystemBroadcaster()

    # Buffer should have max size of 720 (60 minutes at 5s intervals)
    assert broadcaster._performance_history.maxlen == 720


# =============================================================================
# Tests for storing snapshots
# =============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_stores_performance_snapshot():
    """Test SystemBroadcaster stores performance snapshot in history."""
    broadcaster = SystemBroadcaster()

    snapshot = PerformanceUpdate(timestamp=datetime.now(UTC))
    broadcaster._store_performance_snapshot(snapshot)

    assert len(broadcaster._performance_history) == 1
    assert broadcaster._performance_history[0] == snapshot


@pytest.mark.asyncio
async def test_system_broadcaster_stores_multiple_snapshots():
    """Test SystemBroadcaster stores multiple snapshots in chronological order."""
    broadcaster = SystemBroadcaster()

    now = datetime.now(UTC)
    snapshots = [
        PerformanceUpdate(timestamp=now - timedelta(seconds=10)),
        PerformanceUpdate(timestamp=now - timedelta(seconds=5)),
        PerformanceUpdate(timestamp=now),
    ]

    for snapshot in snapshots:
        broadcaster._store_performance_snapshot(snapshot)

    assert len(broadcaster._performance_history) == 3
    # Oldest should be first
    assert broadcaster._performance_history[0].timestamp == snapshots[0].timestamp
    # Newest should be last
    assert broadcaster._performance_history[2].timestamp == snapshots[2].timestamp


@pytest.mark.asyncio
async def test_system_broadcaster_history_buffer_evicts_old():
    """Test SystemBroadcaster history buffer evicts old entries when full."""
    broadcaster = SystemBroadcaster()

    # Fill buffer beyond capacity
    max_size = broadcaster._performance_history.maxlen
    for i in range(max_size + 10):
        snapshot = PerformanceUpdate(
            timestamp=datetime.now(UTC) - timedelta(seconds=(max_size + 10 - i) * 5)
        )
        broadcaster._store_performance_snapshot(snapshot)

    # Buffer should be at max size
    assert len(broadcaster._performance_history) == max_size


# =============================================================================
# Tests for get_performance_history method
# =============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_empty():
    """Test get_performance_history returns empty list when no data."""
    broadcaster = SystemBroadcaster()

    result = broadcaster.get_performance_history(TimeRange.FIVE_MIN)

    assert result == []


@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_five_min():
    """Test get_performance_history returns snapshots for 5-minute range.

    5m range at 5s intervals = 60 snapshots max.
    Returns every snapshot from the last 5 minutes.
    """
    broadcaster = SystemBroadcaster()

    now = datetime.now(UTC)
    # Add snapshots for the last 10 minutes (120 snapshots at 5s intervals)
    for i in range(120):
        timestamp = now - timedelta(seconds=(120 - i) * 5)
        snapshot = PerformanceUpdate(timestamp=timestamp)
        broadcaster._store_performance_snapshot(snapshot)

    result = broadcaster.get_performance_history(TimeRange.FIVE_MIN)

    # Should return approximately 60 snapshots (5 minutes at 5s intervals)
    # Allow for slight timing variations (59-60 due to exact timestamp boundary)
    assert 58 <= len(result) <= 60
    # Should be in chronological order (oldest first)
    assert result[0].timestamp < result[-1].timestamp
    # All should be within 5 minutes of the most recent (with small buffer for timing)
    five_min_ago = now - timedelta(minutes=5, seconds=5)
    assert all(s.timestamp >= five_min_ago for s in result)


@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_fifteen_min():
    """Test get_performance_history returns snapshots for 15-minute range.

    15m range returns 60 data points by sampling every 3rd snapshot.
    """
    broadcaster = SystemBroadcaster()

    now = datetime.now(UTC)
    # Add snapshots for the last 20 minutes (240 snapshots at 5s intervals)
    for i in range(240):
        timestamp = now - timedelta(seconds=(240 - i) * 5)
        snapshot = PerformanceUpdate(timestamp=timestamp)
        broadcaster._store_performance_snapshot(snapshot)

    result = broadcaster.get_performance_history(TimeRange.FIFTEEN_MIN)

    # Should return ~60 data points (sampled every 3rd for 15 min range)
    # 15 min = 180 snapshots at 5s, sampling every 3rd = 60 points
    assert len(result) <= 60
    assert len(result) > 0
    # Should be in chronological order
    if len(result) > 1:
        assert result[0].timestamp < result[-1].timestamp


@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_sixty_min():
    """Test get_performance_history returns snapshots for 60-minute range.

    60m range returns 60 data points by sampling every 12th snapshot.
    """
    broadcaster = SystemBroadcaster()

    now = datetime.now(UTC)
    # Add snapshots for the last 60 minutes (720 snapshots at 5s intervals)
    for i in range(720):
        timestamp = now - timedelta(seconds=(720 - i) * 5)
        snapshot = PerformanceUpdate(timestamp=timestamp)
        broadcaster._store_performance_snapshot(snapshot)

    result = broadcaster.get_performance_history(TimeRange.SIXTY_MIN)

    # Should return ~60 data points (sampled every 12th for 60 min range)
    assert len(result) <= 60
    assert len(result) > 0
    # Should be in chronological order
    if len(result) > 1:
        assert result[0].timestamp < result[-1].timestamp


@pytest.mark.asyncio
async def test_system_broadcaster_get_performance_history_partial_data():
    """Test get_performance_history handles partial data gracefully.

    When less data is available than the requested time range.
    """
    broadcaster = SystemBroadcaster()

    now = datetime.now(UTC)
    # Add only 30 snapshots (2.5 minutes of data)
    for i in range(30):
        timestamp = now - timedelta(seconds=(30 - i) * 5)
        snapshot = PerformanceUpdate(timestamp=timestamp)
        broadcaster._store_performance_snapshot(snapshot)

    # Request 5 minutes of data, but only 2.5 minutes available
    result = broadcaster.get_performance_history(TimeRange.FIVE_MIN)

    # Should return all available data (30 snapshots)
    assert len(result) == 30


# =============================================================================
# Tests for integration with broadcast_performance
# =============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_performance_stores_snapshot():
    """Test that broadcast_performance stores snapshot in history."""
    broadcaster = SystemBroadcaster()

    # Create mock performance update
    mock_performance_update = MagicMock(spec=PerformanceUpdate)
    mock_performance_update.model_dump.return_value = {
        "timestamp": datetime.now(UTC).isoformat(),
        "gpu": None,
        "alerts": [],
    }

    mock_collector = AsyncMock()
    mock_collector.collect_all.return_value = mock_performance_update

    broadcaster.set_performance_collector(mock_collector)

    # Add a connection to trigger broadcast
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    await broadcaster.broadcast_performance()

    # Should have stored the snapshot in history
    assert len(broadcaster._performance_history) == 1


@pytest.mark.asyncio
async def test_system_broadcaster_history_stores_actual_update_not_dict():
    """Test that history stores PerformanceUpdate objects, not dicts."""
    broadcaster = SystemBroadcaster()

    # Create an actual PerformanceUpdate
    update = PerformanceUpdate(timestamp=datetime.now(UTC))

    mock_collector = AsyncMock()
    mock_collector.collect_all.return_value = update

    broadcaster.set_performance_collector(mock_collector)

    await broadcaster.broadcast_performance()

    # History should contain PerformanceUpdate objects
    assert len(broadcaster._performance_history) == 1
    assert isinstance(broadcaster._performance_history[0], PerformanceUpdate)
