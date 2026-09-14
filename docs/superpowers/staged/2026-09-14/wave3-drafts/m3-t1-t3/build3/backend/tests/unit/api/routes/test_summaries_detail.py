"""Unit tests for summary detail API endpoint.

Tests the expandable detail panel endpoint:
- GET /api/summaries/{id}/detail - Get detailed summary with full narrative and export options

These tests cover:
- Happy path with valid summary ID
- Not found (404) for invalid summary ID
- Response structure with timeline and export formats
- Cache behavior
- Error handling

Related Linear issues: NEM-5425, NEM-5426, NEM-5427
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.summary import Summary


class TestGetSummaryDetail:
    """Tests for GET /api/summaries/{id}/detail endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary_detail_success(self) -> None:
        """Test get_summary_detail returns detailed data for valid summary ID."""
        from backend.api.routes.summaries import get_summary_detail

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.summary_type = "hourly"
            mock_summary.content = "A detailed summary of security events."
            mock_summary.event_count = 3
            mock_summary.event_ids = [101, 102, 103]
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_by_id = AsyncMock(return_value=mock_summary)

            # Mock EventRepository for fetching related events
            with patch("backend.api.routes.summaries.EventRepository") as MockEventRepo:
                mock_event_repo = MockEventRepo.return_value

                mock_event1 = MagicMock()
                mock_event1.id = 101
                mock_event1.started_at = datetime(2026, 1, 21, 14, 10, tzinfo=UTC)
                mock_event1.camera = MagicMock()
                mock_event1.camera.name = "Front Door"
                mock_event1.summary = "Person detected at front door"
                mock_event1.risk_score = 75
                mock_event1.risk_level = "high"
                mock_event1.object_types = "person"

                mock_event2 = MagicMock()
                mock_event2.id = 102
                mock_event2.started_at = datetime(2026, 1, 21, 14, 30, tzinfo=UTC)
                mock_event2.camera = MagicMock()
                mock_event2.camera.name = "Driveway"
                mock_event2.summary = "Vehicle detected"
                mock_event2.risk_score = 50
                mock_event2.risk_level = "medium"
                mock_event2.object_types = "vehicle"

                mock_event3 = MagicMock()
                mock_event3.id = 103
                mock_event3.started_at = datetime(2026, 1, 21, 14, 45, tzinfo=UTC)
                mock_event3.camera = MagicMock()
                mock_event3.camera.name = "Backyard"
                mock_event3.summary = "Motion detected"
                mock_event3.risk_score = 30
                mock_event3.risk_level = "low"
                mock_event3.object_types = "motion"

                mock_event_repo.get_by_ids = AsyncMock(
                    return_value=[mock_event1, mock_event2, mock_event3]
                )

                # Mock summary parser
                with patch("backend.api.routes.summaries.parse_summary_content") as mock_parse:
                    from backend.services.summary_parser import StructuredSummary

                    mock_parse.return_value = StructuredSummary(
                        bullet_points=[],
                        focus_areas=["Front Door", "Driveway", "Backyard"],
                        dominant_patterns=["person", "vehicle"],
                        max_risk_score=75,
                        weather_conditions=[],
                    )

                    result = await get_summary_detail(summary_id=1, db=mock_db, cache=mock_cache)

                    # Verify response structure
                    assert result is not None
                    assert result.id == 1
                    assert result.content == "A detailed summary of security events."
                    assert result.event_count == 3

                    # Verify timeline events
                    assert result.timeline is not None
                    assert len(result.timeline) == 3
                    assert result.timeline[0].event_id == 101
                    assert result.timeline[0].camera_name == "Front Door"
                    assert result.timeline[0].summary == "Person detected at front door"

                    # Verify export options
                    assert result.export_formats is not None
                    assert "json" in result.export_formats
                    assert "csv" in result.export_formats
                    assert "pdf" in result.export_formats

    @pytest.mark.asyncio
    async def test_get_summary_detail_not_found(self) -> None:
        """Test get_summary_detail returns 404 for non-existent summary."""
        from fastapi import HTTPException

        from backend.api.routes.summaries import get_summary_detail

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with no summary
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_summary_detail(summary_id=999, db=mock_db, cache=mock_cache)

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_summary_detail_cache_hit(self) -> None:
        """Test get_summary_detail returns cached data when available."""
        from backend.api.routes.summaries import get_summary_detail

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache hit
        cached_data = {
            "id": 1,
            "summary_type": "hourly",
            "content": "Cached summary content",
            "event_count": 2,
            "window_start": "2026-01-21T14:00:00Z",
            "window_end": "2026-01-21T15:00:00Z",
            "generated_at": "2026-01-21T14:55:00Z",
            "structured": {
                "bullet_points": [],
                "focus_areas": ["Front Door"],
                "dominant_patterns": [],
                "max_risk_score": 60,
                "weather_conditions": [],
            },
            "timeline": [
                {
                    "event_id": 101,
                    "timestamp": "2026-01-21T14:10:00Z",
                    "camera_name": "Front Door",
                    "summary": "Person detected",
                    "risk_score": 60,
                    "risk_level": "medium",
                }
            ],
            "export_formats": ["json", "csv", "pdf"],
        }
        mock_cache.get.return_value = cached_data

        result = await get_summary_detail(summary_id=1, db=mock_db, cache=mock_cache)

        assert result is not None
        assert result.id == 1
        assert result.content == "Cached summary content"
        mock_cache.get.assert_called_once()
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_summary_detail_no_events(self) -> None:
        """Test get_summary_detail handles summary with no related events."""
        from backend.api.routes.summaries import get_summary_detail

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.summary_type = "hourly"
            mock_summary.content = "All clear, no events to report."
            mock_summary.event_count = 0
            mock_summary.event_ids = None  # No event IDs
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_by_id = AsyncMock(return_value=mock_summary)

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

                result = await get_summary_detail(summary_id=1, db=mock_db, cache=mock_cache)

                assert result is not None
                assert result.id == 1
                assert result.event_count == 0
                assert result.timeline == []
                assert result.export_formats is not None

    @pytest.mark.asyncio
    async def test_get_summary_detail_cache_write_failure(self) -> None:
        """Test get_summary_detail handles cache write failure gracefully."""
        from backend.api.routes.summaries import get_summary_detail

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss and write failure
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = Exception("Redis write failed")

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.summary_type = "hourly"
            mock_summary.content = "Test summary content"
            mock_summary.event_count = 0
            mock_summary.event_ids = None
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_by_id = AsyncMock(return_value=mock_summary)

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

                # Should still return result (cache write failure doesn't break response)
                result = await get_summary_detail(summary_id=1, db=mock_db, cache=mock_cache)

                assert result is not None
                assert result.id == 1


class TestExportSummary:
    """Tests for GET /api/summaries/{id}/export endpoint."""

    @pytest.mark.asyncio
    async def test_export_summary_json(self) -> None:
        """Test exporting summary in JSON format."""
        import json

        from starlette.responses import JSONResponse

        from backend.api.routes.summaries import export_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.summary_type = "hourly"
            mock_summary.content = "Test summary"
            mock_summary.event_count = 1
            mock_summary.event_ids = [101]
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_by_id = AsyncMock(return_value=mock_summary)

            # Mock EventRepository
            with patch("backend.api.routes.summaries.EventRepository") as MockEventRepo:
                mock_event_repo = MockEventRepo.return_value
                mock_event = MagicMock()
                mock_event.id = 101
                mock_event.started_at = datetime(2026, 1, 21, 14, 10, tzinfo=UTC)
                mock_event.camera = MagicMock()
                mock_event.camera.name = "Front Door"
                mock_event.summary = "Event summary"
                mock_event.risk_score = 75
                mock_event.risk_level = "high"
                mock_event.object_types = "person"
                mock_event_repo.get_by_ids = AsyncMock(return_value=[mock_event])

                result = await export_summary(
                    summary_id=1, format="json", db=mock_db, _cache=mock_cache
                )

                # JSON format returns a JSONResponse
                assert isinstance(result, JSONResponse)
                # Decode the body to check content
                body = json.loads(result.body.decode("utf-8"))
                assert "summary" in body
                assert "events" in body
                assert body["summary"]["id"] == 1

    @pytest.mark.asyncio
    async def test_export_summary_csv(self) -> None:
        """Test exporting summary in CSV format."""
        from starlette.responses import Response

        from backend.api.routes.summaries import export_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.summary_type = "hourly"
            mock_summary.content = "Test summary"
            mock_summary.event_count = 1
            mock_summary.event_ids = [101]
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_by_id = AsyncMock(return_value=mock_summary)

            # Mock EventRepository
            with patch("backend.api.routes.summaries.EventRepository") as MockEventRepo:
                mock_event_repo = MockEventRepo.return_value
                mock_event = MagicMock()
                mock_event.id = 101
                mock_event.started_at = datetime(2026, 1, 21, 14, 10, tzinfo=UTC)
                mock_event.camera = MagicMock()
                mock_event.camera.name = "Front Door"
                mock_event.summary = "Event summary"
                mock_event.risk_score = 75
                mock_event.risk_level = "high"
                mock_event.object_types = "person"
                mock_event_repo.get_by_ids = AsyncMock(return_value=[mock_event])

                result = await export_summary(
                    summary_id=1, format="csv", db=mock_db, _cache=mock_cache
                )

                # CSV format returns a Response object
                assert isinstance(result, Response)
                assert result.media_type == "text/csv"
                # Decode the body to check content
                body = result.body.decode("utf-8")
                assert "Event ID" in body
                assert "Front Door" in body

    @pytest.mark.asyncio
    async def test_export_summary_not_found(self) -> None:
        """Test export returns 404 for non-existent summary."""
        from fastapi import HTTPException

        from backend.api.routes.summaries import export_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response with no summary
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await export_summary(summary_id=999, format="json", db=mock_db, _cache=mock_cache)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_export_summary_invalid_format(self) -> None:
        """Test export returns 400 for invalid format."""
        from fastapi import HTTPException

        from backend.api.routes.summaries import export_summary

        mock_db = AsyncMock()
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock database response
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = MockRepo.return_value

            mock_summary = MagicMock(spec=Summary)
            mock_summary.id = 1
            mock_summary.summary_type = "hourly"
            mock_summary.content = "Test summary"
            mock_summary.event_count = 0
            mock_summary.event_ids = None
            mock_summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
            mock_summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
            mock_summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)

            mock_repo.get_by_id = AsyncMock(return_value=mock_summary)

            with pytest.raises(HTTPException) as exc_info:
                await export_summary(
                    summary_id=1,
                    format="xml",
                    db=mock_db,
                    _cache=mock_cache,  # Invalid format
                )

            assert exc_info.value.status_code == 400
            assert "format" in str(exc_info.value.detail).lower()
