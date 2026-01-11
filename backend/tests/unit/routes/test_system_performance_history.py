"""Unit tests for GET /api/system/performance/history endpoint.

Tests the performance history endpoint that returns historical performance
metrics using circular buffer storage in SystemBroadcaster.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from backend.api.routes import system as system_routes
from backend.api.schemas.performance import (
    PerformanceHistoryResponse,
    PerformanceUpdate,
    TimeRange,
)

# =============================================================================
# Tests for get_performance_history endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_get_performance_history_returns_empty_when_no_data() -> None:
    """Test performance history endpoint returns empty list when no data collected."""
    # Save original broadcaster
    original_broadcaster = system_routes._system_broadcaster

    try:
        # Mock broadcaster with empty history
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_performance_history.return_value = []
        system_routes._system_broadcaster = mock_broadcaster

        response = await system_routes.get_performance_history(
            time_range=TimeRange.FIVE_MIN,
        )

        assert isinstance(response, PerformanceHistoryResponse)
        assert response.snapshots == []
        assert response.time_range == TimeRange.FIVE_MIN
        assert response.count == 0
        mock_broadcaster.get_performance_history.assert_called_once_with(TimeRange.FIVE_MIN)
    finally:
        system_routes._system_broadcaster = original_broadcaster


@pytest.mark.asyncio
async def test_get_performance_history_returns_snapshots() -> None:
    """Test performance history endpoint returns collected snapshots."""
    original_broadcaster = system_routes._system_broadcaster

    try:
        # Create mock snapshots
        now = datetime.now(UTC)
        mock_snapshots = [
            PerformanceUpdate(timestamp=now - timedelta(seconds=10)),
            PerformanceUpdate(timestamp=now - timedelta(seconds=5)),
            PerformanceUpdate(timestamp=now),
        ]

        mock_broadcaster = MagicMock()
        mock_broadcaster.get_performance_history.return_value = mock_snapshots
        system_routes._system_broadcaster = mock_broadcaster

        response = await system_routes.get_performance_history(
            time_range=TimeRange.FIVE_MIN,
        )

        assert isinstance(response, PerformanceHistoryResponse)
        assert response.snapshots == mock_snapshots
        assert response.time_range == TimeRange.FIVE_MIN
        assert response.count == 3
    finally:
        system_routes._system_broadcaster = original_broadcaster


@pytest.mark.asyncio
async def test_get_performance_history_with_fifteen_min_range() -> None:
    """Test performance history endpoint with 15-minute time range."""
    original_broadcaster = system_routes._system_broadcaster

    try:
        mock_snapshots = [PerformanceUpdate(timestamp=datetime.now(UTC))]
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_performance_history.return_value = mock_snapshots
        system_routes._system_broadcaster = mock_broadcaster

        response = await system_routes.get_performance_history(
            time_range=TimeRange.FIFTEEN_MIN,
        )

        assert response.time_range == TimeRange.FIFTEEN_MIN
        mock_broadcaster.get_performance_history.assert_called_once_with(TimeRange.FIFTEEN_MIN)
    finally:
        system_routes._system_broadcaster = original_broadcaster


@pytest.mark.asyncio
async def test_get_performance_history_with_sixty_min_range() -> None:
    """Test performance history endpoint with 60-minute time range."""
    original_broadcaster = system_routes._system_broadcaster

    try:
        mock_snapshots = [PerformanceUpdate(timestamp=datetime.now(UTC))]
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_performance_history.return_value = mock_snapshots
        system_routes._system_broadcaster = mock_broadcaster

        response = await system_routes.get_performance_history(
            time_range=TimeRange.SIXTY_MIN,
        )

        assert response.time_range == TimeRange.SIXTY_MIN
        mock_broadcaster.get_performance_history.assert_called_once_with(TimeRange.SIXTY_MIN)
    finally:
        system_routes._system_broadcaster = original_broadcaster


@pytest.mark.asyncio
async def test_get_performance_history_default_time_range() -> None:
    """Test performance history endpoint uses 5m as default time range."""
    original_broadcaster = system_routes._system_broadcaster

    try:
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_performance_history.return_value = []
        system_routes._system_broadcaster = mock_broadcaster

        # Call with explicit default value (FastAPI would inject this)
        # Direct function calls bypass FastAPI's Query default handling
        response = await system_routes.get_performance_history(
            time_range=TimeRange.FIVE_MIN,
        )

        assert response.time_range == TimeRange.FIVE_MIN
        mock_broadcaster.get_performance_history.assert_called_once_with(TimeRange.FIVE_MIN)
    finally:
        system_routes._system_broadcaster = original_broadcaster


@pytest.mark.asyncio
async def test_get_performance_history_broadcaster_not_initialized() -> None:
    """Test performance history endpoint handles uninitialized broadcaster."""
    original_broadcaster = system_routes._system_broadcaster

    try:
        system_routes._system_broadcaster = None

        response = await system_routes.get_performance_history(
            time_range=TimeRange.FIVE_MIN,
        )

        # Should return empty response when broadcaster not available
        assert isinstance(response, PerformanceHistoryResponse)
        assert response.snapshots == []
        assert response.count == 0
    finally:
        system_routes._system_broadcaster = original_broadcaster
