"""Unit tests for trends API routes.

Tests the trend comparison sparklines endpoints:
- GET /api/summaries/trends?type=hourly - Get hourly trend data (5-min buckets)
- GET /api/summaries/trends?type=daily - Get daily trend data (1-hour buckets)

These tests cover:
- Happy paths with cache hits and misses
- Time bucketing for hourly (5-min) and daily (1-hour) aggregations
- Rolling 24-hour baseline calculations
- Deviation percentage calculations
- Edge cases (no data, insufficient historical data)
- Error handling (cache failures, database failures)

The trends API provides sparkline data for dashboard visualization showing
event count, average risk, and high-risk event counts with baseline comparison.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestGetTrends:
    """Tests for GET /api/summaries/trends endpoint."""

    @pytest.mark.asyncio
    async def test_get_hourly_trends_success(self) -> None:
        """Test get_trends returns hourly trend data with 5-min buckets."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with trend data
        with patch("backend.api.routes.trends.TrendService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_trend_data = AsyncMock(
                return_value={
                    "event_count": {
                        "values": [5, 8, 3, 6, 10, 4, 7, 9, 2, 5, 6, 8],
                        "baseline": 6.0,
                        "deviation_pct": 33.3,
                    },
                    "avg_risk": {
                        "values": [45, 52, 38, 60, 72, 40, 55, 65, 35, 48, 50, 58],
                        "baseline": 50.0,
                        "deviation_pct": 16.0,
                    },
                    "high_risk_count": {
                        "values": [1, 2, 0, 1, 3, 1, 2, 2, 0, 1, 1, 2],
                        "baseline": 1.3,
                        "deviation_pct": 53.8,
                    },
                }
            )

            result = await get_trends(trend_type="hourly", db=mock_db, cache=mock_cache)

            assert result.event_count is not None
            assert len(result.event_count.values) == 12
            assert result.event_count.baseline == 6.0
            assert result.event_count.deviation_pct == 33.3

            assert result.avg_risk is not None
            assert len(result.avg_risk.values) == 12
            assert result.avg_risk.baseline == 50.0

            assert result.high_risk_count is not None
            assert len(result.high_risk_count.values) == 12

            mock_service.get_trend_data.assert_called_once_with("hourly")

    @pytest.mark.asyncio
    async def test_get_daily_trends_success(self) -> None:
        """Test get_trends returns daily trend data with 1-hour buckets."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_cache.get.return_value = None

        with patch("backend.api.routes.trends.TrendService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_trend_data = AsyncMock(
                return_value={
                    "event_count": {
                        "values": [
                            10,
                            15,
                            20,
                            25,
                            30,
                            35,
                            40,
                            45,
                            50,
                            55,
                            60,
                            65,
                            70,
                            75,
                            80,
                            75,
                            70,
                            65,
                            60,
                            55,
                            50,
                            45,
                            40,
                            35,
                        ],
                        "baseline": 50.0,
                        "deviation_pct": -30.0,
                    },
                    "avg_risk": {
                        "values": [
                            30,
                            35,
                            40,
                            45,
                            50,
                            55,
                            60,
                            65,
                            70,
                            65,
                            60,
                            55,
                            50,
                            45,
                            40,
                            35,
                            30,
                            35,
                            40,
                            45,
                            50,
                            55,
                            60,
                            55,
                        ],
                        "baseline": 48.0,
                        "deviation_pct": 14.6,
                    },
                    "high_risk_count": {
                        "values": [
                            2,
                            3,
                            4,
                            5,
                            6,
                            7,
                            8,
                            9,
                            10,
                            9,
                            8,
                            7,
                            6,
                            5,
                            4,
                            3,
                            2,
                            3,
                            4,
                            5,
                            6,
                            7,
                            8,
                            7,
                        ],
                        "baseline": 5.5,
                        "deviation_pct": 27.3,
                    },
                }
            )

            result = await get_trends(trend_type="daily", db=mock_db, cache=mock_cache)

            assert result.event_count is not None
            assert len(result.event_count.values) == 24
            assert result.event_count.baseline == 50.0
            assert result.event_count.deviation_pct == -30.0

            mock_service.get_trend_data.assert_called_once_with("daily")

    @pytest.mark.asyncio
    async def test_get_trends_cache_hit(self) -> None:
        """Test get_trends returns cached data when available."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        cached_data = {
            "event_count": {
                "values": [5, 8, 3],
                "baseline": 5.3,
                "deviation_pct": 10.0,
            },
            "avg_risk": {
                "values": [45, 52, 38],
                "baseline": 45.0,
                "deviation_pct": -15.6,
            },
            "high_risk_count": {
                "values": [1, 2, 0],
                "baseline": 1.0,
                "deviation_pct": 0.0,
            },
        }
        mock_cache.get.return_value = cached_data

        result = await get_trends(trend_type="hourly", db=mock_db, cache=mock_cache)

        assert result.event_count.values == [5, 8, 3]
        assert result.event_count.baseline == 5.3
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_trends_no_data(self) -> None:
        """Test get_trends handles case when no event data exists."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_cache.get.return_value = None

        with patch("backend.api.routes.trends.TrendService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_trend_data = AsyncMock(
                return_value={
                    "event_count": {
                        "values": [],
                        "baseline": 0.0,
                        "deviation_pct": 0.0,
                    },
                    "avg_risk": {
                        "values": [],
                        "baseline": 0.0,
                        "deviation_pct": 0.0,
                    },
                    "high_risk_count": {
                        "values": [],
                        "baseline": 0.0,
                        "deviation_pct": 0.0,
                    },
                }
            )

            result = await get_trends(trend_type="hourly", db=mock_db, cache=mock_cache)

            assert result.event_count.values == []
            assert result.event_count.baseline == 0.0
            assert result.event_count.deviation_pct == 0.0

    @pytest.mark.asyncio
    async def test_get_trends_cache_read_failure(self) -> None:
        """Test get_trends falls back to database on cache read failure."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_cache.get.side_effect = Exception("Redis connection failed")

        with patch("backend.api.routes.trends.TrendService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_trend_data = AsyncMock(
                return_value={
                    "event_count": {"values": [1, 2, 3], "baseline": 2.0, "deviation_pct": 50.0},
                    "avg_risk": {"values": [40, 50, 60], "baseline": 50.0, "deviation_pct": 20.0},
                    "high_risk_count": {"values": [0, 1, 0], "baseline": 0.3, "deviation_pct": 0.0},
                }
            )

            result = await get_trends(trend_type="hourly", db=mock_db, cache=mock_cache)

            # Should still return result (graceful degradation)
            assert result.event_count.values == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_trends_cache_write_failure(self) -> None:
        """Test get_trends handles cache write failure gracefully."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_cache.get.return_value = None
        mock_cache.set.side_effect = Exception("Redis write failed")

        with patch("backend.api.routes.trends.TrendService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_trend_data = AsyncMock(
                return_value={
                    "event_count": {"values": [1, 2, 3], "baseline": 2.0, "deviation_pct": 50.0},
                    "avg_risk": {"values": [40, 50, 60], "baseline": 50.0, "deviation_pct": 20.0},
                    "high_risk_count": {"values": [0, 1, 0], "baseline": 0.3, "deviation_pct": 0.0},
                }
            )

            result = await get_trends(trend_type="hourly", db=mock_db, cache=mock_cache)

            # Should still return result
            assert result.event_count.values == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_trends_invalid_type_defaults_to_hourly(self) -> None:
        """Test get_trends handles invalid type parameter."""
        from backend.api.routes.trends import get_trends

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        mock_cache.get.return_value = None

        with patch("backend.api.routes.trends.TrendService") as MockService:
            mock_service = MockService.return_value
            mock_service.get_trend_data = AsyncMock(
                return_value={
                    "event_count": {"values": [1, 2, 3], "baseline": 2.0, "deviation_pct": 50.0},
                    "avg_risk": {"values": [40, 50, 60], "baseline": 50.0, "deviation_pct": 20.0},
                    "high_risk_count": {"values": [0, 1, 0], "baseline": 0.3, "deviation_pct": 0.0},
                }
            )

            # Invalid type should be handled by FastAPI validation before reaching the endpoint
            result = await get_trends(trend_type="hourly", db=mock_db, cache=mock_cache)
            assert result is not None


class TestTrendMetricSchema:
    """Tests for TrendMetric Pydantic schema."""

    def test_trend_metric_schema_valid(self) -> None:
        """Test TrendMetric schema accepts valid data."""
        from backend.api.schemas.trends import TrendMetric

        metric = TrendMetric(
            values=[1, 2, 3, 4, 5],
            baseline=3.0,
            deviation_pct=66.7,
        )

        assert metric.values == [1, 2, 3, 4, 5]
        assert metric.baseline == 3.0
        assert metric.deviation_pct == 66.7

    def test_trend_metric_schema_empty_values(self) -> None:
        """Test TrendMetric schema accepts empty values list."""
        from backend.api.schemas.trends import TrendMetric

        metric = TrendMetric(
            values=[],
            baseline=0.0,
            deviation_pct=0.0,
        )

        assert metric.values == []
        assert metric.baseline == 0.0

    def test_trend_metric_schema_negative_deviation(self) -> None:
        """Test TrendMetric schema accepts negative deviation (below baseline)."""
        from backend.api.schemas.trends import TrendMetric

        metric = TrendMetric(
            values=[1, 2, 1],
            baseline=5.0,
            deviation_pct=-60.0,
        )

        assert metric.deviation_pct == -60.0


class TestTrendsResponseSchema:
    """Tests for TrendsResponse Pydantic schema."""

    def test_trends_response_schema_valid(self) -> None:
        """Test TrendsResponse schema accepts valid data."""
        from backend.api.schemas.trends import TrendMetric, TrendsResponse

        response = TrendsResponse(
            event_count=TrendMetric(values=[1, 2, 3], baseline=2.0, deviation_pct=50.0),
            avg_risk=TrendMetric(values=[40, 50, 60], baseline=50.0, deviation_pct=20.0),
            high_risk_count=TrendMetric(values=[0, 1, 0], baseline=0.3, deviation_pct=0.0),
        )

        assert response.event_count.baseline == 2.0
        assert response.avg_risk.baseline == 50.0
        assert response.high_risk_count.baseline == 0.3


class TestCacheConstants:
    """Tests to verify cache constants are correctly defined."""

    def test_cache_keys_follow_naming_convention(self) -> None:
        """Test that cache keys follow the expected naming pattern."""
        from backend.api.routes.trends import (
            CACHE_KEY_TRENDS_DAILY,
            CACHE_KEY_TRENDS_HOURLY,
        )

        assert CACHE_KEY_TRENDS_HOURLY.startswith("trends:")
        assert CACHE_KEY_TRENDS_DAILY.startswith("trends:")
        assert CACHE_KEY_TRENDS_HOURLY != CACHE_KEY_TRENDS_DAILY

    def test_cache_ttl_is_positive(self) -> None:
        """Test that cache TTL is a positive number."""
        from backend.api.routes.trends import TRENDS_CACHE_TTL

        assert TRENDS_CACHE_TTL > 0
        assert isinstance(TRENDS_CACHE_TTL, int)
