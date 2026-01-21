"""Unit tests for summaries API routes.

Tests the event summarization endpoints:
- GET /api/summaries/latest - Get latest hourly and daily summaries
- GET /api/summaries/hourly - Get latest hourly summary
- GET /api/summaries/daily - Get latest daily summary

These tests cover:
- Happy paths with cache hits and misses
- Edge cases (no summaries exist)
- Error handling (cache failures, database failures)
- Response structure and parsing
- Cache invalidation and TTL

The summaries API provides LLM-generated narrative summaries of security events
for dashboard display, with both raw content and structured data (bullet points,
focus areas, patterns, etc.).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.summaries import (
    CACHE_KEY_DAILY,
    CACHE_KEY_HOURLY,
    CACHE_KEY_LATEST,
    SUMMARIES_CACHE_TTL,
)
from backend.models.summary import Summary, SummaryType


class TestGetLatestSummaries:
    """Tests for GET /api/summaries/latest endpoint."""

    @pytest.mark.asyncio
    async def test_get_latest_summaries_cache_hit(self) -> None:
        """Test get_latest_summaries returns cached data when available."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit with both summaries
        cached_data = {
            "hourly": {
                "id": 1,
                "content": "Hourly summary content",
                "event_count": 2,
                "window_start": "2026-01-21T14:00:00Z",
                "window_end": "2026-01-21T15:00:00Z",
                "generated_at": "2026-01-21T14:55:00Z",
                "structured": {
                    "bullet_points": [],
                    "focus_areas": ["Front Door"],
                    "dominant_patterns": [],
                    "max_risk_score": 75,
                    "weather_conditions": [],
                },
            },
            "daily": {
                "id": 2,
                "content": "Daily summary content",
                "event_count": 5,
                "window_start": "2026-01-21T00:00:00Z",
                "window_end": "2026-01-21T15:00:00Z",
                "generated_at": "2026-01-21T14:55:00Z",
                "structured": {
                    "bullet_points": [],
                    "focus_areas": ["Front Door", "Backyard"],
                    "dominant_patterns": [],
                    "max_risk_score": 85,
                    "weather_conditions": [],
                },
            },
        }
        mock_cache.get.return_value = cached_data

        result = await get_latest_summaries(db=mock_db, cache=mock_cache)

        assert result.hourly is not None
        assert result.hourly.id == 1
        assert result.hourly.content == "Hourly summary content"
        assert result.hourly.event_count == 2
        assert result.daily is not None
        assert result.daily.id == 2
        assert result.daily.content == "Daily summary content"
        assert result.daily.event_count == 5

        mock_cache.get.assert_called_once_with(CACHE_KEY_LATEST, cache_type="summaries")
        mock_db.execute.assert_not_called()  # Database not queried on cache hit

    @pytest.mark.asyncio
    async def test_get_latest_summaries_cache_miss(self) -> None:
        """Test get_latest_summaries queries database on cache miss."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            # Create mock summaries
            mock_hourly = MagicMock(spec=Summary)
            mock_hourly.id = 1
            mock_hourly.content = "Hourly summary content"
            mock_hourly.event_count = 2
            mock_hourly.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_hourly.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_hourly.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_daily = MagicMock(spec=Summary)
            mock_daily.id = 2
            mock_daily.content = "Daily summary content"
            mock_daily.event_count = 5
            mock_daily.window_start = datetime(2026, 1, 21, 0, 0, tzinfo=UTC)
            mock_daily.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_daily.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly,
                    "daily": mock_daily,
                }
            )

            # Mock summary parser
            with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
                from backend.services.summary_parser import StructuredSummary

                mock_parse.return_value = StructuredSummary(
                    bullet_points=[],
                    focus_areas=["Front Door"],
                    dominant_patterns=[],
                    max_risk_score=75,
                    weather_conditions=[],
                )

                result = await get_latest_summaries(db=mock_db, cache=mock_cache)

                assert result.hourly is not None
                assert result.hourly.id == 1
                assert result.hourly.content == "Hourly summary content"
                assert result.daily is not None
                assert result.daily.id == 2
                assert result.daily.content == "Daily summary content"

                # Cache should be populated
                mock_cache.set.assert_called_once()
                call_args = mock_cache.set.call_args
                assert call_args[0][0] == CACHE_KEY_LATEST
                assert call_args[1]["ttl"] == SUMMARIES_CACHE_TTL

    @pytest.mark.asyncio
    async def test_get_latest_summaries_no_summaries_exist(self) -> None:
        """Test get_latest_summaries handles case when no summaries exist."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with no summaries
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": None,
                    "daily": None,
                }
            )

            result = await get_latest_summaries(db=mock_db, cache=mock_cache)

            assert result.hourly is None
            assert result.daily is None

            # Cache should still be populated with null values
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_summaries_only_hourly_exists(self) -> None:
        """Test get_latest_summaries when only hourly summary exists."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with only hourly
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_hourly = MagicMock(spec=Summary)
            mock_hourly.id = 1
            mock_hourly.content = "Hourly summary content"
            mock_hourly.event_count = 2
            mock_hourly.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_hourly.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_hourly.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly,
                    "daily": None,
                }
            )

            # Mock summary parser
            with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
                from backend.services.summary_parser import StructuredSummary

                mock_parse.return_value = StructuredSummary(
                    bullet_points=[],
                    focus_areas=[],
                    dominant_patterns=[],
                    max_risk_score=None,
                    weather_conditions=[],
                )

                result = await get_latest_summaries(db=mock_db, cache=mock_cache)

                assert result.hourly is not None
                assert result.hourly.id == 1
                assert result.daily is None

    @pytest.mark.asyncio
    async def test_get_latest_summaries_only_daily_exists(self) -> None:
        """Test get_latest_summaries when only daily summary exists."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with only daily
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_daily = MagicMock(spec=Summary)
            mock_daily.id = 2
            mock_daily.content = "Daily summary content"
            mock_daily.event_count = 5
            mock_daily.window_start = datetime(2026, 1, 21, 0, 0, tzinfo=UTC)
            mock_daily.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_daily.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": None,
                    "daily": mock_daily,
                }
            )

            # Mock summary parser
            with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
                from backend.services.summary_parser import StructuredSummary

                mock_parse.return_value = StructuredSummary(
                    bullet_points=[],
                    focus_areas=[],
                    dominant_patterns=[],
                    max_risk_score=None,
                    weather_conditions=[],
                )

                result = await get_latest_summaries(db=mock_db, cache=mock_cache)

                assert result.hourly is None
                assert result.daily is not None
                assert result.daily.id == 2

    @pytest.mark.asyncio
    async def test_get_latest_summaries_cache_read_failure(self) -> None:
        """Test get_latest_summaries falls back to database on cache read failure."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache read failure
        mock_cache.get.side_effect = Exception("Redis connection failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": None,
                    "daily": None,
                }
            )

            result = await get_latest_summaries(db=mock_db, cache=mock_cache)

            # Should still return result (graceful degradation)
            assert result.hourly is None
            assert result.daily is None

    @pytest.mark.asyncio
    async def test_get_latest_summaries_cache_write_failure(self) -> None:
        """Test get_latest_summaries handles cache write failure gracefully."""
        from backend.api.routes.summaries import get_latest_summaries

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss and write failure
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = Exception("Redis write failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": None,
                    "daily": None,
                }
            )

            result = await get_latest_summaries(db=mock_db, cache=mock_cache)

            # Should still return result (cache write failure doesn't break response)
            assert result.hourly is None
            assert result.daily is None


class TestGetHourlySummary:
    """Tests for GET /api/summaries/hourly endpoint."""

    @pytest.mark.asyncio
    async def test_get_hourly_summary_cache_hit(self) -> None:
        """Test get_hourly_summary returns cached data when available."""
        from backend.api.routes.summaries import get_hourly_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit
        cached_data = {
            "id": 1,
            "content": "Hourly summary content",
            "event_count": 2,
            "window_start": "2026-01-21T14:00:00Z",
            "window_end": "2026-01-21T15:00:00Z",
            "generated_at": "2026-01-21T14:55:00Z",
            "structured": {
                "bullet_points": [],
                "focus_areas": ["Front Door"],
                "dominant_patterns": [],
                "max_risk_score": 75,
                "weather_conditions": [],
            },
        }
        mock_cache.get.return_value = cached_data

        result = await get_hourly_summary(db=mock_db, cache=mock_cache)

        assert result is not None
        assert result.id == 1
        assert result.content == "Hourly summary content"
        assert result.event_count == 2

        mock_cache.get.assert_called_once_with(CACHE_KEY_HOURLY, cache_type="summaries")
        mock_db.execute.assert_not_called()  # Database not queried on cache hit

    @pytest.mark.asyncio
    async def test_get_hourly_summary_cache_hit_null(self) -> None:
        """Test get_hourly_summary handles cached null value correctly."""
        from backend.api.routes.summaries import get_hourly_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit with null (no summary exists)
        mock_cache.get.return_value = "null"

        result = await get_hourly_summary(db=mock_db, cache=mock_cache)

        assert result is None
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_hourly_summary_cache_miss(self) -> None:
        """Test get_hourly_summary queries database on cache miss."""
        from backend.api.routes.summaries import get_hourly_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.content = "Hourly summary content"
            mock_summary.event_count = 2
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_latest_by_type = AsyncMock(return_value=mock_summary)

            # Mock summary parser
            with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
                from backend.services.summary_parser import StructuredSummary

                mock_parse.return_value = StructuredSummary(
                    bullet_points=[],
                    focus_areas=["Front Door"],
                    dominant_patterns=[],
                    max_risk_score=75,
                    weather_conditions=[],
                )

                result = await get_hourly_summary(db=mock_db, cache=mock_cache)

                assert result is not None
                assert result.id == 1
                assert result.content == "Hourly summary content"

                # Verify correct summary type was requested
                mock_repo.get_latest_by_type.assert_called_once_with(SummaryType.HOURLY)

                # Cache should be populated
                mock_cache.set.assert_called_once()
                call_args = mock_cache.set.call_args
                assert call_args[0][0] == CACHE_KEY_HOURLY
                assert call_args[1]["ttl"] == SUMMARIES_CACHE_TTL

    @pytest.mark.asyncio
    async def test_get_hourly_summary_no_summary_exists(self) -> None:
        """Test get_hourly_summary handles case when no summary exists."""
        from backend.api.routes.summaries import get_hourly_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with no summary
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)

            result = await get_hourly_summary(db=mock_db, cache=mock_cache)

            assert result is None

            # Cache should be populated with "null" string
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            assert call_args[0][0] == CACHE_KEY_HOURLY
            assert call_args[0][1] == "null"

    @pytest.mark.asyncio
    async def test_get_hourly_summary_cache_read_failure(self) -> None:
        """Test get_hourly_summary falls back to database on cache read failure."""
        from backend.api.routes.summaries import get_hourly_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache read failure
        mock_cache.get.side_effect = Exception("Redis connection failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)

            result = await get_hourly_summary(db=mock_db, cache=mock_cache)

            # Should still return result (graceful degradation)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_hourly_summary_cache_write_failure(self) -> None:
        """Test get_hourly_summary handles cache write failure gracefully."""
        from backend.api.routes.summaries import get_hourly_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss and write failure
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = Exception("Redis write failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)

            result = await get_hourly_summary(db=mock_db, cache=mock_cache)

            # Should still return result (cache write failure doesn't break response)
            assert result is None


class TestGetDailySummary:
    """Tests for GET /api/summaries/daily endpoint."""

    @pytest.mark.asyncio
    async def test_get_daily_summary_cache_hit(self) -> None:
        """Test get_daily_summary returns cached data when available."""
        from backend.api.routes.summaries import get_daily_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit
        cached_data = {
            "id": 2,
            "content": "Daily summary content",
            "event_count": 5,
            "window_start": "2026-01-21T00:00:00Z",
            "window_end": "2026-01-21T15:00:00Z",
            "generated_at": "2026-01-21T14:55:00Z",
            "structured": {
                "bullet_points": [],
                "focus_areas": ["Front Door", "Backyard"],
                "dominant_patterns": [],
                "max_risk_score": 85,
                "weather_conditions": [],
            },
        }
        mock_cache.get.return_value = cached_data

        result = await get_daily_summary(db=mock_db, cache=mock_cache)

        assert result is not None
        assert result.id == 2
        assert result.content == "Daily summary content"
        assert result.event_count == 5

        mock_cache.get.assert_called_once_with(CACHE_KEY_DAILY, cache_type="summaries")
        mock_db.execute.assert_not_called()  # Database not queried on cache hit

    @pytest.mark.asyncio
    async def test_get_daily_summary_cache_hit_null(self) -> None:
        """Test get_daily_summary handles cached null value correctly."""
        from backend.api.routes.summaries import get_daily_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit with null (no summary exists)
        mock_cache.get.return_value = "null"

        result = await get_daily_summary(db=mock_db, cache=mock_cache)

        assert result is None
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_daily_summary_cache_miss(self) -> None:
        """Test get_daily_summary queries database on cache miss."""
        from backend.api.routes.summaries import get_daily_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 2
            mock_summary.content = "Daily summary content"
            mock_summary.event_count = 5
            mock_summary.window_start = datetime(2026, 1, 21, 0, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_latest_by_type = AsyncMock(return_value=mock_summary)

            # Mock summary parser
            with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
                from backend.services.summary_parser import StructuredSummary

                mock_parse.return_value = StructuredSummary(
                    bullet_points=[],
                    focus_areas=["Front Door", "Backyard"],
                    dominant_patterns=[],
                    max_risk_score=85,
                    weather_conditions=[],
                )

                result = await get_daily_summary(db=mock_db, cache=mock_cache)

                assert result is not None
                assert result.id == 2
                assert result.content == "Daily summary content"

                # Verify correct summary type was requested
                mock_repo.get_latest_by_type.assert_called_once_with(SummaryType.DAILY)

                # Cache should be populated
                mock_cache.set.assert_called_once()
                call_args = mock_cache.set.call_args
                assert call_args[0][0] == CACHE_KEY_DAILY
                assert call_args[1]["ttl"] == SUMMARIES_CACHE_TTL

    @pytest.mark.asyncio
    async def test_get_daily_summary_no_summary_exists(self) -> None:
        """Test get_daily_summary handles case when no summary exists."""
        from backend.api.routes.summaries import get_daily_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with no summary
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)

            result = await get_daily_summary(db=mock_db, cache=mock_cache)

            assert result is None

            # Cache should be populated with "null" string
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            assert call_args[0][0] == CACHE_KEY_DAILY
            assert call_args[0][1] == "null"

    @pytest.mark.asyncio
    async def test_get_daily_summary_cache_read_failure(self) -> None:
        """Test get_daily_summary falls back to database on cache read failure."""
        from backend.api.routes.summaries import get_daily_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache read failure
        mock_cache.get.side_effect = Exception("Redis connection failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)

            result = await get_daily_summary(db=mock_db, cache=mock_cache)

            # Should still return result (graceful degradation)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_daily_summary_cache_write_failure(self) -> None:
        """Test get_daily_summary handles cache write failure gracefully."""
        from backend.api.routes.summaries import get_daily_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss and write failure
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = Exception("Redis write failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)

            result = await get_daily_summary(db=mock_db, cache=mock_cache)

            # Should still return result (cache write failure doesn't break response)
            assert result is None


class TestHelperFunctions:
    """Tests for helper functions in summaries routes."""

    def test_build_events_for_parser(self) -> None:
        """Test _build_events_for_parser returns empty list.

        This is expected since we don't have access to full event data at query time.
        The parser extracts what it can from the content text itself.
        """
        from backend.api.routes.summaries import _build_events_for_parser

        result = _build_events_for_parser()

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_summary_to_response_with_none(self) -> None:
        """Test _summary_to_response returns None when given None."""
        from backend.api.routes.summaries import _summary_to_response

        result = _summary_to_response(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_summary_to_response_with_valid_summary(self) -> None:
        """Test _summary_to_response converts Summary to SummaryResponse."""
        from backend.api.routes.summaries import _summary_to_response

        mock_summary = MagicMock(spec=Summary)
        mock_summary.id = 1
        mock_summary.content = "Test summary content"
        mock_summary.event_count = 3
        mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
        mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

        # Mock summary parser
        with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
            from backend.services.summary_parser import BulletPoint, StructuredSummary

            mock_parse.return_value = StructuredSummary(
                bullet_points=[BulletPoint(icon="camera", text="Test bullet", severity="high")],
                focus_areas=["Front Door"],
                dominant_patterns=["loitering"],
                max_risk_score=85,
                weather_conditions=["nighttime"],
            )

            result = _summary_to_response(mock_summary)

            assert result is not None
            assert result.id == 1
            assert result.content == "Test summary content"
            assert result.event_count == 3
            assert result.structured is not None
            assert len(result.structured.bullet_points) == 1
            assert result.structured.bullet_points[0].icon == "camera"
            assert result.structured.bullet_points[0].text == "Test bullet"
            assert result.structured.bullet_points[0].severity == "high"
            assert result.structured.focus_areas == ["Front Door"]
            assert result.structured.dominant_patterns == ["loitering"]
            assert result.structured.max_risk_score == 85
            assert result.structured.weather_conditions == ["nighttime"]

            # Verify parser was called with empty events list
            mock_parse.assert_called_once()
            call_args = mock_parse.call_args
            assert call_args[0][0] == "Test summary content"
            assert call_args[1]["events"] == []

    @pytest.mark.asyncio
    async def test_summary_to_response_with_no_structured_data(self) -> None:
        """Test _summary_to_response handles summaries with minimal structured data."""
        from backend.api.routes.summaries import _summary_to_response

        mock_summary = MagicMock(spec=Summary)
        mock_summary.id = 1
        mock_summary.content = "All clear, no events."
        mock_summary.event_count = 0
        mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
        mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

        # Mock summary parser returning empty structured data
        with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
            from backend.services.summary_parser import StructuredSummary

            mock_parse.return_value = StructuredSummary(
                bullet_points=[],
                focus_areas=[],
                dominant_patterns=[],
                max_risk_score=None,
                weather_conditions=[],
            )

            result = _summary_to_response(mock_summary)

            assert result is not None
            assert result.id == 1
            assert result.event_count == 0
            assert result.structured is not None
            assert len(result.structured.bullet_points) == 0
            assert result.structured.focus_areas == []
            assert result.structured.max_risk_score is None


class TestCacheConstants:
    """Tests to verify cache constants are correctly defined."""

    def test_cache_keys_are_unique(self) -> None:
        """Test that cache keys are unique to prevent collisions."""
        from backend.api.routes.summaries import (
            CACHE_KEY_DAILY,
            CACHE_KEY_HOURLY,
            CACHE_KEY_LATEST,
        )

        keys = [CACHE_KEY_LATEST, CACHE_KEY_HOURLY, CACHE_KEY_DAILY]
        assert len(keys) == len(set(keys)), "Cache keys must be unique"

    def test_cache_keys_follow_naming_convention(self) -> None:
        """Test that cache keys follow the expected naming pattern."""
        from backend.api.routes.summaries import (
            CACHE_KEY_DAILY,
            CACHE_KEY_HOURLY,
            CACHE_KEY_LATEST,
        )

        # All keys should start with "summaries:"
        assert CACHE_KEY_LATEST.startswith("summaries:")
        assert CACHE_KEY_HOURLY.startswith("summaries:")
        assert CACHE_KEY_DAILY.startswith("summaries:")

    def test_cache_ttl_is_positive(self) -> None:
        """Test that cache TTL is a positive number."""
        from backend.api.routes.summaries import SUMMARIES_CACHE_TTL

        assert SUMMARIES_CACHE_TTL > 0
        assert isinstance(SUMMARIES_CACHE_TTL, int)

    def test_cache_ttl_matches_generation_frequency(self) -> None:
        """Test that cache TTL is appropriate for 5-minute generation frequency.

        Per the module docstring, summaries are generated every 5 minutes,
        so cache TTL should be 300 seconds (5 minutes).
        """
        from backend.api.routes.summaries import SUMMARIES_CACHE_TTL

        assert SUMMARIES_CACHE_TTL == 300, "Cache TTL should match 5-minute generation frequency"
