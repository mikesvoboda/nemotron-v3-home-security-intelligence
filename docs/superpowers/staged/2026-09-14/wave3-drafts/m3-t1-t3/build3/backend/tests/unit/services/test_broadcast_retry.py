"""Unit tests for broadcast retry mechanism (NEM-2582).

Tests cover:
- broadcast_with_retry function
- BroadcastRetryMetrics class
- broadcast_alert_with_retry_background function
- Exponential backoff behavior
- Metrics tracking
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.services.event_broadcaster import (
    BroadcastRetryMetrics,
    broadcast_alert_with_retry_background,
    broadcast_with_retry,
)

# =============================================================================
# BroadcastRetryMetrics Tests
# =============================================================================


class TestBroadcastRetryMetrics:
    """Tests for BroadcastRetryMetrics dataclass."""

    def test_initial_state(self) -> None:
        """Test that metrics start at zero."""
        metrics = BroadcastRetryMetrics()

        assert metrics.total_attempts == 0
        assert metrics.successful_broadcasts == 0
        assert metrics.failed_broadcasts == 0
        assert metrics.retries_exhausted == 0
        assert metrics.retry_counts == {0: 0, 1: 0, 2: 0, 3: 0}

    def test_record_first_attempt_success(self) -> None:
        """Test recording a success on first attempt."""
        metrics = BroadcastRetryMetrics()

        metrics.record_success(attempts=1)

        assert metrics.total_attempts == 1
        assert metrics.successful_broadcasts == 1
        assert metrics.failed_broadcasts == 0
        assert metrics.retry_counts[0] == 1  # 0 retries needed

    def test_record_success_after_retries(self) -> None:
        """Test recording a success after retry attempts."""
        metrics = BroadcastRetryMetrics()

        # Success on third attempt (2 retries)
        metrics.record_success(attempts=3)

        assert metrics.total_attempts == 3
        assert metrics.successful_broadcasts == 1
        assert metrics.retry_counts[2] == 1  # 2 retries needed

    def test_record_failure(self) -> None:
        """Test recording a failure after all retries exhausted."""
        metrics = BroadcastRetryMetrics()

        metrics.record_failure(attempts=4)

        assert metrics.total_attempts == 4
        assert metrics.failed_broadcasts == 1
        assert metrics.retries_exhausted == 1

    def test_to_dict(self) -> None:
        """Test converting metrics to dictionary."""
        metrics = BroadcastRetryMetrics()
        metrics.record_success(attempts=1)
        metrics.record_success(attempts=2)
        metrics.record_failure(attempts=4)

        result = metrics.to_dict()

        assert result["total_attempts"] == 7  # 1 + 2 + 4
        assert result["successful_broadcasts"] == 2
        assert result["failed_broadcasts"] == 1
        assert result["retries_exhausted"] == 1
        assert "success_rate" in result
        # Success rate should be 2/3 = ~0.666
        assert abs(result["success_rate"] - 0.666) < 0.01

    def test_success_rate_zero_broadcasts(self) -> None:
        """Test success rate when no broadcasts recorded."""
        metrics = BroadcastRetryMetrics()

        result = metrics.to_dict()

        assert result["success_rate"] == 0.0


# =============================================================================
# broadcast_with_retry Tests
# =============================================================================


class TestBroadcastWithRetry:
    """Tests for broadcast_with_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        """Test successful broadcast on first attempt."""
        mock_func = AsyncMock(return_value=5)
        metrics = BroadcastRetryMetrics()

        result = await broadcast_with_retry(
            mock_func,
            message_type="test_event",
            max_retries=3,
            metrics=metrics,
        )

        assert result == 5
        mock_func.assert_called_once()
        assert metrics.successful_broadcasts == 1
        assert metrics.total_attempts == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self) -> None:
        """Test successful broadcast after retry."""
        mock_func = AsyncMock(side_effect=[Exception("Fail 1"), 5])
        metrics = BroadcastRetryMetrics()

        with patch("backend.services.event_broadcaster.asyncio.sleep") as mock_sleep:
            result = await broadcast_with_retry(
                mock_func,
                message_type="test_event",
                max_retries=3,
                base_delay=1.0,
                metrics=metrics,
            )

        assert result == 5
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once()
        assert metrics.successful_broadcasts == 1
        assert metrics.total_attempts == 2

    @pytest.mark.asyncio
    async def test_success_on_last_retry(self) -> None:
        """Test success on the final retry attempt."""
        mock_func = AsyncMock(
            side_effect=[
                Exception("Fail 1"),
                Exception("Fail 2"),
                Exception("Fail 3"),
                10,
            ]
        )
        metrics = BroadcastRetryMetrics()

        with patch("backend.services.event_broadcaster.asyncio.sleep"):
            result = await broadcast_with_retry(
                mock_func,
                message_type="test_event",
                max_retries=3,
                metrics=metrics,
            )

        assert result == 10
        assert mock_func.call_count == 4  # Initial + 3 retries
        assert metrics.successful_broadcasts == 1
        assert metrics.total_attempts == 4

    @pytest.mark.asyncio
    async def test_failure_after_all_retries(self) -> None:
        """Test that exception is raised after all retries exhausted."""
        mock_func = AsyncMock(side_effect=Exception("Persistent failure"))
        metrics = BroadcastRetryMetrics()

        with patch("backend.services.event_broadcaster.asyncio.sleep"):
            with pytest.raises(Exception, match="Persistent failure"):
                await broadcast_with_retry(
                    mock_func,
                    message_type="test_event",
                    max_retries=3,
                    metrics=metrics,
                )

        assert mock_func.call_count == 4  # Initial + 3 retries
        assert metrics.failed_broadcasts == 1
        assert metrics.retries_exhausted == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test that delays use exponential backoff."""
        mock_func = AsyncMock(
            side_effect=[
                Exception("Fail 1"),
                Exception("Fail 2"),
                5,
            ]
        )
        delays = []

        async def capture_sleep(delay: float) -> None:
            delays.append(delay)

        with patch(
            "backend.services.event_broadcaster.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            await broadcast_with_retry(
                mock_func,
                message_type="test_event",
                max_retries=3,
                base_delay=1.0,
            )

        # Should have 2 delays (before retry 1 and retry 2)
        assert len(delays) == 2
        # First delay should be around 1.0 + jitter (1.1 - 1.3)
        assert 1.0 <= delays[0] <= 1.4
        # Second delay should be around 2.0 + jitter (2.2 - 2.6)
        assert 2.0 <= delays[1] <= 2.7

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        mock_func = AsyncMock(side_effect=[Exception("Fail"), 5])
        delays = []

        async def capture_sleep(delay: float) -> None:
            delays.append(delay)

        with patch(
            "backend.services.event_broadcaster.asyncio.sleep",
            side_effect=capture_sleep,
        ):
            await broadcast_with_retry(
                mock_func,
                message_type="test_event",
                max_retries=1,
                base_delay=100.0,  # Would be 100s without cap
                max_delay=5.0,  # Cap at 5s
            )

        # Delay should be capped at max_delay (5.0) + jitter
        assert delays[0] <= 6.5  # 5.0 + max 30% jitter

    @pytest.mark.asyncio
    async def test_no_metrics_provided(self) -> None:
        """Test that function works without metrics."""
        mock_func = AsyncMock(return_value=5)

        result = await broadcast_with_retry(
            mock_func,
            message_type="test_event",
            metrics=None,
        )

        assert result == 5
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_max_retries(self) -> None:
        """Test with max_retries=0 (no retries)."""
        mock_func = AsyncMock(side_effect=Exception("Fail"))
        metrics = BroadcastRetryMetrics()

        with pytest.raises(Exception, match="Fail"):
            await broadcast_with_retry(
                mock_func,
                message_type="test_event",
                max_retries=0,
                metrics=metrics,
            )

        mock_func.assert_called_once()
        assert metrics.failed_broadcasts == 1


# =============================================================================
# broadcast_alert_with_retry_background Tests
# =============================================================================


class TestBroadcastAlertWithRetryBackground:
    """Tests for broadcast_alert_with_retry_background function."""

    @pytest.mark.asyncio
    async def test_successful_broadcast(self) -> None:
        """Test successful broadcast in background task."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast_alert = AsyncMock(return_value=5)
        metrics = BroadcastRetryMetrics()
        alert_data = {"id": "test-123", "severity": "high"}

        await broadcast_alert_with_retry_background(
            mock_broadcaster,
            alert_data,
            WebSocketAlertEventType.ALERT_ACKNOWLEDGED,
            max_retries=3,
            metrics=metrics,
        )

        mock_broadcaster.broadcast_alert.assert_called_once()
        assert metrics.successful_broadcasts == 1

    @pytest.mark.asyncio
    async def test_failed_broadcast_does_not_raise(self) -> None:
        """Test that failures don't raise in background task."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast_alert = AsyncMock(side_effect=Exception("Broadcast failed"))
        metrics = BroadcastRetryMetrics()
        alert_data = {"id": "test-123", "severity": "high"}

        # Should not raise
        with patch("backend.services.event_broadcaster.asyncio.sleep"):
            await broadcast_alert_with_retry_background(
                mock_broadcaster,
                alert_data,
                WebSocketAlertEventType.ALERT_ACKNOWLEDGED,
                max_retries=2,
                metrics=metrics,
            )

        # Should have tried multiple times
        assert mock_broadcaster.broadcast_alert.call_count == 3  # Initial + 2 retries
        assert metrics.failed_broadcasts == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self) -> None:
        """Test background task succeeds after retry."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast_alert = AsyncMock(side_effect=[Exception("Fail"), 5])
        metrics = BroadcastRetryMetrics()
        alert_data = {"id": "test-123", "severity": "high"}

        with patch("backend.services.event_broadcaster.asyncio.sleep"):
            await broadcast_alert_with_retry_background(
                mock_broadcaster,
                alert_data,
                WebSocketAlertEventType.ALERT_DISMISSED,
                max_retries=3,
                metrics=metrics,
            )

        assert mock_broadcaster.broadcast_alert.call_count == 2
        assert metrics.successful_broadcasts == 1
        assert metrics.failed_broadcasts == 0


# =============================================================================
# EventBroadcaster Metrics Integration Tests
# =============================================================================


class TestEventBroadcasterMetricsIntegration:
    """Tests for metrics integration with EventBroadcaster."""

    def test_broadcaster_has_metrics(self) -> None:
        """Test that EventBroadcaster has metrics instance."""
        from backend.services.event_broadcaster import EventBroadcaster

        mock_redis = MagicMock()
        broadcaster = EventBroadcaster(mock_redis)

        assert hasattr(broadcaster, "broadcast_metrics")
        assert isinstance(broadcaster.broadcast_metrics, BroadcastRetryMetrics)

    def test_get_broadcast_metrics(self) -> None:
        """Test get_broadcast_metrics returns dictionary."""
        from backend.services.event_broadcaster import EventBroadcaster

        mock_redis = MagicMock()
        broadcaster = EventBroadcaster(mock_redis)

        # Record some metrics
        broadcaster.broadcast_metrics.record_success(1)
        broadcaster.broadcast_metrics.record_failure(3)

        metrics_dict = broadcaster.get_broadcast_metrics()

        assert isinstance(metrics_dict, dict)
        assert metrics_dict["successful_broadcasts"] == 1
        assert metrics_dict["failed_broadcasts"] == 1
        assert "success_rate" in metrics_dict
