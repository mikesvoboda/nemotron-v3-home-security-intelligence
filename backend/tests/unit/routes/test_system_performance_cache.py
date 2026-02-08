"""Unit tests for /api/system/performance endpoint caching (NEM-5378).

Tests the performance metrics endpoint caching behavior to verify that:
- Cache hits return cached responses without calling the collector
- Cache misses call the collector and cache the result
- Cache expires after TTL and triggers a fresh collection
- Cache is properly cleared by clear_health_cache()
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.api.routes import system as system_routes
from backend.api.schemas.performance import PerformanceUpdate


@pytest.fixture(autouse=True)
def clear_caches_fixture() -> None:
    """Clear all caches before each test to ensure test isolation."""
    system_routes.clear_health_cache()


# =============================================================================
# Tests for get_performance_metrics endpoint caching
# =============================================================================


@pytest.mark.asyncio
async def test_get_performance_metrics_cache_miss_calls_collector() -> None:
    """Test that cache miss calls the performance collector."""
    original_collector = system_routes._performance_collector

    try:
        # Create mock collector
        mock_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(return_value=mock_response)
        system_routes._performance_collector = mock_collector

        # First call should trigger collector
        response = await system_routes.get_performance_metrics()

        assert isinstance(response, PerformanceUpdate)
        mock_collector.collect_all.assert_called_once()
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_get_performance_metrics_cache_hit_skips_collector() -> None:
    """Test that cache hit returns cached response without calling collector."""
    original_collector = system_routes._performance_collector

    try:
        # Create mock collector
        mock_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(return_value=mock_response)
        system_routes._performance_collector = mock_collector

        # First call populates cache
        response1 = await system_routes.get_performance_metrics()
        assert mock_collector.collect_all.call_count == 1

        # Second call should use cache
        response2 = await system_routes.get_performance_metrics()
        assert mock_collector.collect_all.call_count == 1  # Still 1, not called again

        # Responses should be the same object (cached)
        assert response1 is response2
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_get_performance_metrics_cache_expiration() -> None:
    """Test that cache expires after TTL and triggers fresh collection."""
    original_collector = system_routes._performance_collector

    try:
        # Create mock collector
        first_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        second_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(side_effect=[first_response, second_response])
        system_routes._performance_collector = mock_collector

        # First call populates cache
        response1 = await system_routes.get_performance_metrics()
        assert mock_collector.collect_all.call_count == 1
        assert response1 is first_response

        # Manually expire the cache by modifying cached_at
        if system_routes._performance_metrics_cache is not None:
            # Set cached_at to 10 seconds ago (beyond 5s TTL)
            system_routes._performance_metrics_cache.cached_at = time.time() - 10.0

        # Next call should trigger new collection due to expired cache
        response2 = await system_routes.get_performance_metrics()
        assert mock_collector.collect_all.call_count == 2
        assert response2 is second_response
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_get_performance_metrics_clear_cache_invalidates() -> None:
    """Test that clear_health_cache() invalidates the performance cache."""
    original_collector = system_routes._performance_collector

    try:
        # Create mock collector
        first_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        second_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(side_effect=[first_response, second_response])
        system_routes._performance_collector = mock_collector

        # First call populates cache
        response1 = await system_routes.get_performance_metrics()
        assert mock_collector.collect_all.call_count == 1

        # Clear all caches
        system_routes.clear_health_cache()

        # Next call should trigger new collection
        response2 = await system_routes.get_performance_metrics()
        assert mock_collector.collect_all.call_count == 2
        assert response1 is not response2
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_get_performance_metrics_collector_not_initialized() -> None:
    """Test that empty response is returned when collector is not initialized."""
    original_collector = system_routes._performance_collector

    try:
        system_routes._performance_collector = None

        response = await system_routes.get_performance_metrics()

        # Should return graceful empty response instead of raising 503
        assert isinstance(response, PerformanceUpdate)
        assert response.gpu is None
        assert response.ai_models == {}
        assert response.nemotron is None
        assert response.inference is None
        assert response.databases == {}
        assert response.host is None
        assert response.containers == []
        assert response.alerts == []
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_get_performance_metrics_collector_error_not_cached() -> None:
    """Test that collector errors are not cached."""
    original_collector = system_routes._performance_collector

    try:
        # Create mock collector that fails first, succeeds second
        success_response = PerformanceUpdate(timestamp=datetime.now(UTC))
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(
            side_effect=[RuntimeError("test error"), success_response]
        )
        system_routes._performance_collector = mock_collector

        # First call should raise error
        with pytest.raises(HTTPException) as exc_info:
            await system_routes.get_performance_metrics()
        assert exc_info.value.status_code == 500

        # Cache should still be None (error not cached)
        assert system_routes._performance_metrics_cache is None

        # Second call should succeed and populate cache
        response = await system_routes.get_performance_metrics()
        assert response is success_response
        assert system_routes._performance_metrics_cache is not None
    finally:
        system_routes._performance_collector = original_collector


# =============================================================================
# Tests for PerformanceMetricsCacheEntry
# =============================================================================


def test_performance_metrics_cache_entry_is_valid_within_ttl() -> None:
    """Test that cache entry is valid within TTL."""
    entry = system_routes.PerformanceMetricsCacheEntry(
        response=PerformanceUpdate(timestamp=datetime.now(UTC)),
        cached_at=time.time(),  # Just cached
    )
    assert entry.is_valid() is True


def test_performance_metrics_cache_entry_is_invalid_after_ttl() -> None:
    """Test that cache entry is invalid after TTL expires."""
    entry = system_routes.PerformanceMetricsCacheEntry(
        response=PerformanceUpdate(timestamp=datetime.now(UTC)),
        cached_at=time.time() - 10.0,  # Cached 10 seconds ago (beyond 5s TTL)
    )
    assert entry.is_valid() is False


def test_performance_cache_ttl_is_five_seconds() -> None:
    """Test that performance cache TTL is set to 5 seconds."""
    assert system_routes.PERFORMANCE_CACHE_TTL_SECONDS == 5.0
