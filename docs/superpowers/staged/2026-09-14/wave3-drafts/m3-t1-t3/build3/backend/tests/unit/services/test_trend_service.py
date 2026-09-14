"""Unit tests for TrendService.

Tests the trend calculation service:
- Time bucket aggregation (5-min for hourly, 1-hour for daily)
- Rolling 24-hour baseline calculations
- Deviation percentage calculations
- Edge cases (no data, single data point, etc.)

The TrendService provides data for sparkline visualizations showing
event count, average risk, and high-risk event counts with baseline comparison.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTrendServiceTimeBucketing:
    """Tests for time bucketing functionality."""

    @pytest.mark.asyncio
    async def test_hourly_uses_5_minute_buckets(self) -> None:
        """Test hourly trend uses 5-minute time buckets."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        # Mock the repository to return events
        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            # Create mock events spanning 1 hour
            now = datetime.now(UTC)
            mock_events = []
            for i in range(12):  # 12 x 5-min buckets = 1 hour
                mock_event = MagicMock()
                mock_event.started_at = now - timedelta(minutes=i * 5 + 2)
                mock_event.risk_score = 50 + i
                mock_events.append(mock_event)

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # Should have 12 buckets for hourly view
            assert len(result["event_count"]["values"]) == 12

    @pytest.mark.asyncio
    async def test_daily_uses_1_hour_buckets(self) -> None:
        """Test daily trend uses 1-hour time buckets."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            # Create mock events spanning 24 hours
            now = datetime.now(UTC)
            mock_events = []
            for i in range(24):
                mock_event = MagicMock()
                mock_event.started_at = now - timedelta(hours=i, minutes=30)
                mock_event.risk_score = 40 + i
                mock_events.append(mock_event)

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("daily")

            # Should have 24 buckets for daily view
            assert len(result["event_count"]["values"]) == 24


class TestTrendServiceBaselineCalculation:
    """Tests for rolling 24-hour baseline calculations."""

    @pytest.mark.asyncio
    async def test_baseline_calculation_average(self) -> None:
        """Test baseline is calculated as average of historical data."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            # Create events with known risk scores
            now = datetime.now(UTC)
            mock_events = []

            # Historical events (for baseline - past 24h before current window)
            for i in range(10):
                mock_event = MagicMock()
                mock_event.started_at = now - timedelta(hours=25 + i)
                mock_event.risk_score = 50  # Consistent score for easy baseline calc
                mock_events.append(mock_event)

            # Current window events
            for i in range(5):
                mock_event = MagicMock()
                mock_event.started_at = now - timedelta(minutes=i * 5)
                mock_event.risk_score = 70  # Higher than baseline
                mock_events.append(mock_event)

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # Baseline should be calculated from historical data
            assert result["avg_risk"]["baseline"] >= 0

    @pytest.mark.asyncio
    async def test_deviation_calculation_above_baseline(self) -> None:
        """Test deviation percentage when current is above baseline."""
        from backend.services.trend_service import _calculate_deviation

        # Current value 50% above baseline
        baseline = 10.0
        current = 15.0
        deviation = _calculate_deviation(current, baseline)
        assert deviation == 50.0

    @pytest.mark.asyncio
    async def test_deviation_calculation_below_baseline(self) -> None:
        """Test deviation percentage when current is below baseline."""
        from backend.services.trend_service import _calculate_deviation

        # Current value 20% below baseline
        baseline = 10.0
        current = 8.0
        deviation = _calculate_deviation(current, baseline)
        assert deviation == -20.0

    @pytest.mark.asyncio
    async def test_deviation_calculation_zero_baseline(self) -> None:
        """Test deviation percentage when baseline is zero."""
        from backend.services.trend_service import _calculate_deviation

        baseline = 0.0
        current = 5.0
        deviation = _calculate_deviation(current, baseline)
        # When baseline is 0, deviation should be 0 to avoid division by zero
        assert deviation == 0.0

    @pytest.mark.asyncio
    async def test_deviation_calculation_equal_values(self) -> None:
        """Test deviation percentage when current equals baseline."""
        from backend.services.trend_service import _calculate_deviation

        baseline = 10.0
        current = 10.0
        deviation = _calculate_deviation(current, baseline)
        assert deviation == 0.0


class TestTrendServiceHighRiskCount:
    """Tests for high-risk event counting."""

    @pytest.mark.asyncio
    async def test_high_risk_threshold_default(self) -> None:
        """Test high-risk events use default threshold of 70."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            now = datetime.now(UTC)
            mock_events = [
                MagicMock(started_at=now - timedelta(minutes=2), risk_score=65),  # Not high
                MagicMock(started_at=now - timedelta(minutes=3), risk_score=70),  # High
                MagicMock(started_at=now - timedelta(minutes=4), risk_score=85),  # High
                MagicMock(started_at=now - timedelta(minutes=5), risk_score=50),  # Not high
            ]

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # Count high-risk events in the result
            total_high_risk = sum(result["high_risk_count"]["values"])
            assert total_high_risk == 2  # Only 70 and 85 are high risk


class TestTrendServiceEdgeCases:
    """Tests for edge cases in trend calculations."""

    @pytest.mark.asyncio
    async def test_no_events_returns_empty_trends(self) -> None:
        """Test trend data when no events exist."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_in_date_range = AsyncMock(return_value=[])

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # Should return empty values with 0 baseline
            assert result["event_count"]["baseline"] == 0.0
            assert result["avg_risk"]["baseline"] == 0.0
            assert result["high_risk_count"]["baseline"] == 0.0
            assert result["event_count"]["deviation_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_single_event_in_window(self) -> None:
        """Test trend data with only a single event."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            now = datetime.now(UTC)
            mock_events = [
                MagicMock(started_at=now - timedelta(minutes=5), risk_score=75),
            ]

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # Should handle single event gracefully
            assert len(result["event_count"]["values"]) == 12
            total_events = sum(result["event_count"]["values"])
            assert total_events == 1

    @pytest.mark.asyncio
    async def test_events_with_null_risk_score(self) -> None:
        """Test trend data handles events with null risk scores."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            now = datetime.now(UTC)
            mock_events = [
                MagicMock(started_at=now - timedelta(minutes=2), risk_score=None),
                MagicMock(started_at=now - timedelta(minutes=3), risk_score=50),
                MagicMock(started_at=now - timedelta(minutes=4), risk_score=None),
            ]

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # Should count all events but only include non-null scores in avg_risk
            total_events = sum(result["event_count"]["values"])
            assert total_events == 3

    @pytest.mark.asyncio
    async def test_insufficient_historical_data(self) -> None:
        """Test trend data with insufficient historical data for baseline."""
        from backend.services.trend_service import TrendService

        mock_db = AsyncMock()

        with patch("backend.services.trend_service.EventRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            # Only current window events, no historical baseline data
            now = datetime.now(UTC)
            mock_events = [
                MagicMock(started_at=now - timedelta(minutes=5), risk_score=75),
                MagicMock(started_at=now - timedelta(minutes=10), risk_score=80),
            ]

            mock_repo.get_in_date_range = AsyncMock(return_value=mock_events)

            service = TrendService(mock_db)
            result = await service.get_trend_data("hourly")

            # With insufficient historical data, should still return valid structure
            assert "event_count" in result
            assert "avg_risk" in result
            assert "high_risk_count" in result


class TestBucketAggregation:
    """Tests for bucket aggregation helper functions."""

    def test_aggregate_events_into_buckets(self) -> None:
        """Test events are correctly aggregated into time buckets."""
        from backend.services.trend_service import _aggregate_into_buckets

        now = datetime.now(UTC)
        bucket_size = timedelta(minutes=5)
        num_buckets = 12

        # Create events at specific times
        events = [
            MagicMock(started_at=now - timedelta(minutes=2), risk_score=50),
            MagicMock(started_at=now - timedelta(minutes=3), risk_score=60),
            MagicMock(started_at=now - timedelta(minutes=7), risk_score=70),
        ]

        buckets = _aggregate_into_buckets(events, now, bucket_size, num_buckets)

        # First bucket (0-5 min ago) should have 2 events
        assert buckets[0]["count"] == 2
        # Second bucket (5-10 min ago) should have 1 event
        assert buckets[1]["count"] == 1
        # Total buckets
        assert len(buckets) == num_buckets

    def test_calculate_bucket_metrics(self) -> None:
        """Test metrics are correctly calculated from bucket data."""
        from backend.services.trend_service import _calculate_metrics_from_buckets

        buckets = [
            {"count": 2, "risk_scores": [50, 50], "high_risk_count": 1},
            {"count": 3, "risk_scores": [55, 60, 65], "high_risk_count": 2},
            {"count": 0, "risk_scores": [], "high_risk_count": 0},
        ]

        metrics = _calculate_metrics_from_buckets(buckets)

        assert metrics["event_counts"] == [2, 3, 0]
        assert metrics["avg_risks"] == [
            50.0,
            60.0,
            0.0,
        ]  # avg([50,50])=50, avg([55,60,65])=60, empty=0
        assert metrics["high_risk_counts"] == [1, 2, 0]
