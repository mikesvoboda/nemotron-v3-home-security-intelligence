"""Unit tests for BackgroundTasks usage in API routes (NEM-3744).

Tests verify that cache invalidation and other non-critical operations
are properly deferred to background tasks to reduce response latency.

This module tests the helper functions used for background task execution
in cameras.py, events.py, and alerts.py routes.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.core.constants import CacheInvalidationReason
from backend.services.cache_service import CacheService


class TestCamerasBackgroundTasks:
    """Tests for background task helpers in cameras.py."""

    @pytest.mark.asyncio
    async def test_invalidate_cameras_cache_background_success(self):
        """Test successful background cache invalidation for cameras."""
        from backend.api.routes.cameras import _invalidate_cameras_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_cameras = AsyncMock()

        await _invalidate_cameras_cache_background(
            mock_cache,
            CacheInvalidationReason.CAMERA_CREATED,
        )

        mock_cache.invalidate_cameras.assert_called_once_with(
            reason=CacheInvalidationReason.CAMERA_CREATED
        )

    @pytest.mark.asyncio
    async def test_invalidate_cameras_cache_background_handles_error(self):
        """Test that background cache invalidation handles errors gracefully."""
        from backend.api.routes.cameras import _invalidate_cameras_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_cameras = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Should not raise exception
        with patch("backend.api.routes.cameras.logger") as mock_logger:
            await _invalidate_cameras_cache_background(
                mock_cache,
                CacheInvalidationReason.CAMERA_UPDATED,
            )

            # Should log warning but not fail
            mock_logger.warning.assert_called_once()
            assert "Background cache invalidation failed" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_all_camera_invalidation_reasons(self):
        """Test background invalidation with all camera-related reasons."""
        from backend.api.routes.cameras import _invalidate_cameras_cache_background

        reasons = [
            CacheInvalidationReason.CAMERA_CREATED,
            CacheInvalidationReason.CAMERA_UPDATED,
            CacheInvalidationReason.CAMERA_DELETED,
            CacheInvalidationReason.CAMERA_RESTORED,
        ]

        for reason in reasons:
            mock_cache = AsyncMock(spec=CacheService)
            mock_cache.invalidate_cameras = AsyncMock()

            await _invalidate_cameras_cache_background(mock_cache, reason)

            mock_cache.invalidate_cameras.assert_called_once_with(reason=reason)


class TestEventsBackgroundTasks:
    """Tests for background task helpers in events.py."""

    @pytest.mark.asyncio
    async def test_invalidate_events_cache_background_success(self):
        """Test successful background cache invalidation for events."""
        from backend.api.routes.events import _invalidate_events_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_events = AsyncMock()
        mock_cache.invalidate_event_stats = AsyncMock()

        await _invalidate_events_cache_background(mock_cache, "event_updated")

        mock_cache.invalidate_events.assert_called_once_with(reason="event_updated")
        mock_cache.invalidate_event_stats.assert_called_once_with(reason="event_updated")

    @pytest.mark.asyncio
    async def test_invalidate_events_cache_background_handles_error(self):
        """Test that background cache invalidation handles errors gracefully."""
        from backend.api.routes.events import _invalidate_events_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_events = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Should not raise exception
        with patch("backend.api.routes.events.logger") as mock_logger:
            await _invalidate_events_cache_background(mock_cache, "event_updated")

            # Should log warning but not fail
            mock_logger.warning.assert_called_once()
            assert "Background cache invalidation failed" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_invalidate_events_cache_different_reasons(self):
        """Test background invalidation with different event reasons."""
        from backend.api.routes.events import _invalidate_events_cache_background

        reasons = ["event_updated", "event_restored", "event_deleted"]

        for reason in reasons:
            mock_cache = AsyncMock(spec=CacheService)
            mock_cache.invalidate_events = AsyncMock()
            mock_cache.invalidate_event_stats = AsyncMock()

            await _invalidate_events_cache_background(mock_cache, reason)

            mock_cache.invalidate_events.assert_called_once_with(reason=reason)
            mock_cache.invalidate_event_stats.assert_called_once_with(reason=reason)


class TestAlertsBackgroundTasks:
    """Tests for background task helpers in alerts.py."""

    @pytest.mark.asyncio
    async def test_invalidate_alerts_cache_background_success(self):
        """Test successful background cache invalidation for alerts."""
        from backend.api.routes.alerts import _invalidate_alerts_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_alerts = AsyncMock()

        await _invalidate_alerts_cache_background(
            mock_cache,
            CacheInvalidationReason.ALERT_RULE_CREATED,
        )

        mock_cache.invalidate_alerts.assert_called_once_with(
            reason=CacheInvalidationReason.ALERT_RULE_CREATED
        )

    @pytest.mark.asyncio
    async def test_invalidate_alerts_cache_background_handles_error(self):
        """Test that background cache invalidation handles errors gracefully."""
        from backend.api.routes.alerts import _invalidate_alerts_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_alerts = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Should not raise exception
        with patch("backend.api.routes.alerts.logger") as mock_logger:
            await _invalidate_alerts_cache_background(
                mock_cache,
                CacheInvalidationReason.ALERT_RULE_DELETED,
            )

            # Should log warning but not fail
            mock_logger.warning.assert_called_once()
            assert "Background cache invalidation failed" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_all_alert_invalidation_reasons(self):
        """Test background invalidation with all alert-related reasons."""
        from backend.api.routes.alerts import _invalidate_alerts_cache_background

        reasons = [
            CacheInvalidationReason.ALERT_RULE_CREATED,
            CacheInvalidationReason.ALERT_RULE_UPDATED,
            CacheInvalidationReason.ALERT_RULE_DELETED,
        ]

        for reason in reasons:
            mock_cache = AsyncMock(spec=CacheService)
            mock_cache.invalidate_alerts = AsyncMock()

            await _invalidate_alerts_cache_background(mock_cache, reason)

            mock_cache.invalidate_alerts.assert_called_once_with(reason=reason)


class TestBackgroundTasksErrorIsolation:
    """Tests to ensure background task errors don't affect main request flow."""

    @pytest.mark.asyncio
    async def test_cameras_error_isolation(self):
        """Test that camera cache errors don't propagate."""
        from backend.api.routes.cameras import _invalidate_cameras_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_cameras = AsyncMock(side_effect=RuntimeError("Connection reset"))

        # This should complete without raising
        result = None
        try:
            await _invalidate_cameras_cache_background(
                mock_cache, CacheInvalidationReason.CAMERA_CREATED
            )
            result = "completed"
        except Exception:
            result = "failed"

        assert result == "completed"

    @pytest.mark.asyncio
    async def test_events_error_isolation(self):
        """Test that event cache errors don't propagate."""
        from backend.api.routes.events import _invalidate_events_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_events = AsyncMock(side_effect=TimeoutError("Operation timed out"))

        # This should complete without raising
        result = None
        try:
            await _invalidate_events_cache_background(mock_cache, "event_updated")
            result = "completed"
        except Exception:
            result = "failed"

        assert result == "completed"

    @pytest.mark.asyncio
    async def test_alerts_error_isolation(self):
        """Test that alert cache errors don't propagate."""
        from backend.api.routes.alerts import _invalidate_alerts_cache_background

        mock_cache = AsyncMock(spec=CacheService)
        mock_cache.invalidate_alerts = AsyncMock(side_effect=ConnectionError("Redis unavailable"))

        # This should complete without raising
        result = None
        try:
            await _invalidate_alerts_cache_background(
                mock_cache, CacheInvalidationReason.ALERT_RULE_UPDATED
            )
            result = "completed"
        except Exception:
            result = "failed"

        assert result == "completed"
