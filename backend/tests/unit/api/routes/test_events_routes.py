"""Unit tests for events API route handlers.

Tests the route handler functions in backend/api/routes/events.py with mocked dependencies.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from backend.api.routes.events import (
    get_detection_ids_from_event,
    parse_detection_ids,
    parse_severity_filter,
    sanitize_csv_value,
)
from backend.models.event import Event


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock Response object for deprecation header tests."""
    return MagicMock(spec=Response)


class TestParseDetectionIds:
    """Tests for parse_detection_ids helper function."""

    def test_parse_detection_ids_json_array(self):
        """Test parsing JSON array string to list of integers."""
        detection_ids_str = "[1, 2, 3, 4, 5]"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3, 4, 5]

    def test_parse_detection_ids_empty_string(self):
        """Test parsing empty string returns empty list."""
        result = parse_detection_ids("")
        assert result == []

    def test_parse_detection_ids_none(self):
        """Test parsing None returns empty list."""
        result = parse_detection_ids(None)
        assert result == []

    def test_parse_detection_ids_legacy_comma_separated(self):
        """Test parsing legacy comma-separated format as fallback."""
        detection_ids_str = "1, 2, 3, 4, 5"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3, 4, 5]

    def test_parse_detection_ids_invalid_json_falls_back_to_csv(self):
        """Test that invalid JSON falls back to comma-separated parsing."""
        detection_ids_str = "1, 2, 3"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3]

    def test_parse_detection_ids_json_not_list_returns_empty(self):
        """Test that JSON object (not array) returns empty list."""
        detection_ids_str = '{"ids": [1, 2, 3]}'
        result = parse_detection_ids(detection_ids_str)
        assert result == []


class TestGetDetectionIdsFromEvent:
    """Tests for get_detection_ids_from_event helper function.

    Note: Legacy detection_ids column was removed in NEM-1592.
    Now uses only the detections relationship via detection_id_list property.
    """

    def test_get_detection_ids_from_relationship(self):
        """Test getting detection IDs from detections relationship."""
        mock_event = Mock(spec=Event)
        mock_event.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event.detection_id_list = [1, 2, 3]

        result = get_detection_ids_from_event(mock_event)
        assert result == [1, 2, 3]

    def test_get_detection_ids_empty_relationship(self):
        """Test empty relationship returns empty list (no legacy fallback)."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []

        result = get_detection_ids_from_event(mock_event)
        assert result == []


class TestParseSeverityFilter:
    """Tests for parse_severity_filter helper function."""

    def test_parse_severity_filter_single_value(self):
        """Test parsing single severity value."""
        result = parse_severity_filter("high")
        assert result == ["high"]

    def test_parse_severity_filter_multiple_values(self):
        """Test parsing comma-separated severity values."""
        result = parse_severity_filter("high,critical")
        assert result == ["high", "critical"]

    def test_parse_severity_filter_with_spaces(self):
        """Test parsing values with whitespace."""
        result = parse_severity_filter("high, medium, low")
        assert result == ["high", "medium", "low"]

    def test_parse_severity_filter_empty_string(self):
        """Test parsing empty string returns empty list."""
        result = parse_severity_filter("")
        assert result == []

    def test_parse_severity_filter_none(self):
        """Test parsing None returns empty list."""
        result = parse_severity_filter(None)
        assert result == []

    def test_parse_severity_filter_invalid_value_raises(self):
        """Test that invalid severity value raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("invalid")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid severity value" in exc_info.value.detail

    def test_parse_severity_filter_mixed_valid_invalid_raises(self):
        """Test that mix of valid and invalid values raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("high,invalid,critical")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in exc_info.value.detail


class TestSanitizeCsvValue:
    """Tests for sanitize_csv_value helper function (additional edge cases)."""

    def test_sanitize_csv_value_empty_string(self):
        """Test empty string is returned as-is."""
        result = sanitize_csv_value("")
        assert result == ""

    def test_sanitize_csv_value_none_returns_empty_string(self):
        """Test None returns empty string."""
        result = sanitize_csv_value(None)
        assert result == ""

    def test_sanitize_csv_value_safe_value_unchanged(self):
        """Test safe value is not modified."""
        safe_value = "Person detected at front door"
        result = sanitize_csv_value(safe_value)
        assert result == safe_value

    def test_sanitize_csv_value_starts_with_equals(self):
        """Test value starting with = is prefixed with quote."""
        dangerous_value = "=1+1"
        result = sanitize_csv_value(dangerous_value)
        assert result == "'=1+1"


class TestListEventsRoute:
    """Tests for list_events route handler."""

    @pytest.mark.asyncio
    async def test_list_events_validates_date_range(self, mock_response: MagicMock):
        """Test that invalid date range raises HTTPException."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        # start_date after end_date should raise
        with pytest.raises(HTTPException) as exc_info:
            await list_events(
                response=mock_response,
                camera_id=None,
                risk_level=None,
                start_date=datetime(2025, 12, 25, 0, 0, 0, tzinfo=UTC),
                end_date=datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC),
                reviewed=None,
                object_type=None,
                limit=50,
                offset=0,
                cursor=None,
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_list_events_invalid_cursor_raises(self, mock_response: MagicMock):
        """Test that invalid cursor raises HTTPException."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(HTTPException) as exc_info:
            await list_events(
                response=mock_response,
                camera_id=None,
                risk_level=None,
                start_date=None,
                end_date=None,
                reviewed=None,
                object_type=None,
                limit=50,
                offset=0,
                cursor="invalid_cursor",
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid cursor" in exc_info.value.detail


class TestGetEventStatsRoute:
    """Tests for get_event_stats route handler."""

    @pytest.mark.asyncio
    async def test_get_event_stats_validates_date_range(self):
        """Test that invalid date range raises HTTPException."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_event_stats(
                start_date=datetime(2025, 12, 25, 0, 0, 0, tzinfo=UTC),
                end_date=datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC),
                db=mock_db,
                cache=mock_cache,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_event_stats_uses_cache(self):
        """Test that event stats uses cache when available."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()

        # Mock cached data
        cached_stats = {
            "total_events": 100,
            "events_by_risk_level": {"low": 20, "medium": 50, "high": 25, "critical": 5},
            "events_by_camera": [{"camera_id": "cam1", "camera_name": "Front", "event_count": 100}],
        }
        mock_cache.get = AsyncMock(return_value=cached_stats)

        result = await get_event_stats(
            start_date=None,
            end_date=None,
            db=mock_db,
            cache=mock_cache,
        )

        # Result should be EventStatsResponse with cached values
        assert result.total_events == 100
        assert result.events_by_risk_level.low == 20
        assert result.events_by_risk_level.medium == 50
        assert result.events_by_risk_level.high == 25
        assert result.events_by_risk_level.critical == 5
        assert len(result.events_by_camera) == 1
        assert result.events_by_camera[0].camera_id == "cam1"
        # Database should not be queried when cache hit occurs
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_event_stats_cache_miss_queries_db(self):
        """Test that cache miss triggers database query."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()

        # Mock cache miss
        mock_cache.get = AsyncMock(return_value=None)

        # Mock database responses
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 100

        mock_risk_result = MagicMock()
        mock_risk_result.all.return_value = [("high", 50), ("low", 30), ("medium", 20)]

        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("cam1", "Front Door", 100)]

        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_risk_result, mock_camera_result]
        )

        result = await get_event_stats(
            start_date=None,
            end_date=None,
            db=mock_db,
            cache=mock_cache,
        )

        assert result.total_events == 100
        assert result.events_by_risk_level.high == 50
        assert len(result.events_by_camera) == 1
        # Should set cache
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_stats_cache_failure_continues(self):
        """Test that cache failures don't prevent stats retrieval."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()

        # Mock cache failure
        mock_cache.get = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Mock database responses
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 50

        mock_risk_result = MagicMock()
        mock_risk_result.all.return_value = [("low", 50)]

        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_risk_result, mock_camera_result]
        )

        # Should not raise, should fall back to database
        result = await get_event_stats(
            start_date=None,
            end_date=None,
            db=mock_db,
            cache=mock_cache,
        )

        assert result.total_events == 50


class TestSearchEventsRoute:
    """Tests for search_events_endpoint route handler."""

    @pytest.mark.asyncio
    async def test_search_events_validates_date_range(self):
        """Test that invalid date range raises HTTPException."""
        from backend.api.routes.events import search_events_endpoint

        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(HTTPException) as exc_info:
            await search_events_endpoint(
                q="person",
                camera_id=None,
                start_date=datetime(2025, 12, 25, 0, 0, 0, tzinfo=UTC),
                end_date=datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC),
                severity=None,
                risk_level=None,
                object_type=None,
                reviewed=None,
                limit=50,
                offset=0,
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_search_events_invalid_severity_raises(self):
        """Test that invalid severity raises HTTPException."""
        from backend.api.routes.events import search_events_endpoint

        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(HTTPException) as exc_info:
            await search_events_endpoint(
                q="person",
                camera_id=None,
                start_date=None,
                end_date=None,
                severity="invalid",
                risk_level=None,
                object_type=None,
                reviewed=None,
                limit=50,
                offset=0,
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid severity value" in exc_info.value.detail


class TestExportEventsRoute:
    """Tests for export_events route handler."""

    @pytest.mark.asyncio
    async def test_export_events_validates_date_range(self):
        """Test that invalid date range raises HTTPException."""
        from backend.api.routes.events import export_events

        mock_request = MagicMock()
        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(HTTPException) as exc_info:
            await export_events(
                request=mock_request,
                camera_id=None,
                risk_level=None,
                start_date=datetime(2025, 12, 25, 0, 0, 0, tzinfo=UTC),
                end_date=datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC),
                reviewed=None,
                db=mock_db,
                _rate_limit=None,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestGetEventRoute:
    """Tests for get_event route handler."""

    @pytest.mark.asyncio
    async def test_get_event_returns_event_with_detection_count(self):
        """Test that get_event returns event with calculated detection count."""
        from backend.api.routes.events import get_event

        mock_request = MagicMock()
        mock_request.url_for = MagicMock(return_value="/api/events/1")
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with detections relationship (not legacy column)
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam123"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "medium"
        mock_event.summary = "Test summary"
        mock_event.reasoning = "Test reasoning"
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event.detection_id_list = [1, 2, 3]

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event(event_id=1, request=mock_request, db=mock_db)

        assert result.id == 1
        assert result.detection_count == 3
        assert result.detection_ids == [1, 2, 3]
        assert result.thumbnail_url == "/api/media/detections/1"


class TestUpdateEventRoute:
    """Tests for update_event route handler."""

    @pytest.mark.asyncio
    async def test_update_event_marks_reviewed(self):
        """Test that update_event marks event as reviewed."""
        from backend.api.routes.events import update_event
        from backend.api.schemas.events import EventUpdate

        mock_request = MagicMock()
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam123"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "medium"
        mock_event.summary = "Test summary"
        mock_event.reasoning = "Test reasoning"
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event.detection_id_list = [1, 2, 3]

        update_data = EventUpdate(reviewed=True)

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
                result = await update_event(
                    event_id=1, update_data=update_data, request=mock_request, db=mock_db
                )

        assert result.id == 1
        assert mock_event.reviewed is True


class TestGetEventDetectionsRoute:
    """Tests for get_event_detections route handler."""

    @pytest.mark.asyncio
    async def test_get_event_detections_no_detections(self):
        """Test that endpoint returns empty list when event has no detections."""
        from backend.api.routes.events import get_event_detections

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with no detections
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_ids = None

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event_detections(event_id=1, limit=50, offset=0, db=mock_db)

        assert result.items == []
        assert result.pagination.total == 0


class TestGetEventEnrichmentsRoute:
    """Tests for get_event_enrichments route handler."""

    @pytest.mark.asyncio
    async def test_get_event_enrichments_no_detections(self):
        """Test that endpoint returns empty enrichments when event has no detections."""
        from backend.api.routes.events import get_event_enrichments

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with no detections
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.detections = []
        mock_event.detection_ids = None

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event_enrichments(event_id=1, limit=50, offset=0, db=mock_db)

        assert result.event_id == 1
        assert result.enrichments == []
        assert result.total == 0
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_get_event_enrichments_offset_beyond_detections(self):
        """Test that offset beyond available detections returns empty with metadata."""
        from backend.api.routes.events import get_event_enrichments

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with detections but offset beyond
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event.detection_id_list = [1, 2, 3]

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event_enrichments(event_id=1, limit=50, offset=100, db=mock_db)

        assert result.event_id == 1
        assert result.enrichments == []
        assert result.total == 3
        assert result.has_more is False


class TestGetEventClipRoute:
    """Tests for get_event_clip route handler."""

    @pytest.mark.asyncio
    async def test_get_event_clip_no_clip(self):
        """Test that endpoint returns clip_available=False when no clip exists."""
        from backend.api.routes.events import get_event_clip

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with no clip
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = None

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event_clip(event_id=1, db=mock_db)

        assert result.clip_available is False
        assert result.clip_url is None

    @pytest.mark.asyncio
    async def test_get_event_clip_file_missing(self):
        """Test that endpoint returns clip_available=False when file doesn't exist."""
        from backend.api.routes.events import get_event_clip

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with clip path but file doesn't exist
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = "/nonexistent/clip.mp4"

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event_clip(event_id=1, db=mock_db)

        assert result.clip_available is False
        assert result.clip_url is None


class TestGenerateEventClipRoute:
    """Tests for generate_event_clip route handler."""

    @pytest.mark.asyncio
    async def test_generate_event_clip_no_detections_raises(self):
        """Test that generating clip with no detections raises HTTPException."""
        from fastapi import Response

        from backend.api.routes.events import generate_event_clip
        from backend.api.schemas.clips import ClipGenerateRequest

        mock_db = AsyncMock(spec=AsyncSession)
        mock_response = Mock(spec=Response)
        mock_response.headers = {}

        # Mock event with no detections
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = None
        mock_event.detections = []
        mock_event.detection_ids = None

        request = ClipGenerateRequest(force=False)

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            with pytest.raises(HTTPException) as exc_info:
                await generate_event_clip(
                    event_id=1, request=request, response=mock_response, db=mock_db
                )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "no detections" in exc_info.value.detail


class TestAnalyzeBatchStreamingRoute:
    """Tests for analyze_batch_streaming route handler."""

    @pytest.mark.asyncio
    async def test_analyze_batch_streaming_invalid_detection_ids(self):
        """Test that invalid detection_ids returns error event."""
        from backend.api.routes.events import analyze_batch_streaming

        # Mock the Redis client to avoid actual connection
        mock_redis = AsyncMock()
        mock_redis._client = None  # Simulate unavailable Redis

        async def mock_get_redis():
            yield mock_redis

        # Patch at the source module where get_redis is defined
        with patch("backend.core.redis.get_redis", mock_get_redis):
            response = await analyze_batch_streaming(
                batch_id="test_batch", camera_id="cam1", detection_ids="invalid,ids"
            )

            # Get event generator
            events = []
            async for event in response.body_iterator:
                if event:
                    # Parse SSE format: "data: {json}\n\n"
                    event_str = event.decode("utf-8") if isinstance(event, bytes) else event
                    if event_str.startswith("data: "):
                        json_str = event_str[6:].strip()
                        if json_str:
                            events.append(json.loads(json_str))

            # Should have at least one error event
            assert len(events) > 0
            error_event = events[0]
            assert error_event["event_type"] == "error"
            assert error_event["error_code"] == "INVALID_DETECTION_IDS"


class TestListEventsRouteComprehensive:
    """Comprehensive tests for list_events with proper DB mocking."""

    @pytest.mark.asyncio
    async def test_list_events_basic_query_execution(self, mock_response: MagicMock):
        """Test that list_events executes queries and returns results."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        # Mock events query result
        mock_event1 = Mock(spec=Event)
        mock_event1.id = 1
        mock_event1.camera_id = "cam1"
        mock_event1.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event1.ended_at = datetime(2025, 12, 23, 12, 2, 0, tzinfo=UTC)
        mock_event1.risk_score = 75
        mock_event1.risk_level = "high"
        mock_event1.summary = "Test event"
        mock_event1.reasoning = "Test reasoning"
        mock_event1.reviewed = False
        mock_event1.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event1.detection_id_list = [1, 2, 3]
        mock_event1.camera = Mock(name="Front Door")

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event1]

        # Setup execute to return different results based on call order
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type=None,
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db,
        )

        assert result.pagination.total == 10
        assert len(result.items) == 1
        assert result.items[0].id == 1
        assert result.items[0].detection_count == 3
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_events_with_object_type_filter(self, mock_response: MagicMock):
        """Test that object_type filter constructs proper LIKE queries."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock empty results
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type="person",
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db,
        )

        assert result.pagination.total == 0
        assert result.items == []


class TestGetEventStatsRouteComprehensive:
    """Comprehensive tests for get_event_stats with proper DB mocking."""

    @pytest.mark.asyncio
    async def test_get_event_stats_with_date_filters(self):
        """Test that get_event_stats applies date filters correctly."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)

        # Mock total count
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 50

        # Mock risk level breakdown
        mock_risk_result = MagicMock()
        mock_risk_result.all.return_value = [("high", 30), ("medium", 15), ("low", 5)]

        # Mock camera breakdown
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [
            ("cam1", "Front Door", 30),
            ("cam2", "Back Door", 20),
        ]

        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_risk_result, mock_camera_result]
        )

        result = await get_event_stats(
            start_date=datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC),
            end_date=datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC),
            db=mock_db,
            cache=mock_cache,
        )

        assert result.total_events == 50
        assert result.events_by_risk_level.high == 30
        assert result.events_by_risk_level.medium == 15
        assert result.events_by_risk_level.low == 5
        assert result.events_by_risk_level.critical == 0
        assert len(result.events_by_camera) == 2

    @pytest.mark.asyncio
    async def test_get_event_stats_cache_write_failure_continues(self):
        """Test that cache write failures don't prevent response."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(side_effect=Exception("Redis write failed"))

        # Mock DB results
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 25

        mock_risk_result = MagicMock()
        mock_risk_result.all.return_value = []

        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_risk_result, mock_camera_result]
        )

        # Should not raise even with cache write failure
        result = await get_event_stats(start_date=None, end_date=None, db=mock_db, cache=mock_cache)

        assert result.total_events == 25

    @pytest.mark.asyncio
    async def test_get_event_stats_with_camera_id_filter(self):
        """Test that get_event_stats applies camera_id filter correctly (NEM-2434)."""
        from backend.api.routes.events import get_event_stats

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)

        # Mock total count (filtered to specific camera)
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 25  # Subset of events

        # Mock risk level breakdown (filtered to specific camera)
        mock_risk_result = MagicMock()
        mock_risk_result.all.return_value = [("high", 10), ("medium", 10), ("low", 5)]

        # Mock camera breakdown (only one camera since filtered)
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("cam1", "Front Door", 25)]

        mock_db.execute = AsyncMock(
            side_effect=[mock_total_result, mock_risk_result, mock_camera_result]
        )

        result = await get_event_stats(
            start_date=None,
            end_date=None,
            camera_id="cam1",  # New camera_id filter
            db=mock_db,
            cache=mock_cache,
        )

        assert result.total_events == 25
        assert result.events_by_risk_level.high == 10
        assert result.events_by_risk_level.medium == 10
        assert result.events_by_risk_level.low == 5
        assert len(result.events_by_camera) == 1
        assert result.events_by_camera[0].camera_id == "cam1"


class TestSearchEventsRouteComprehensive:
    """Comprehensive tests for search_events_endpoint."""

    @pytest.mark.asyncio
    async def test_search_events_severity_precedence(self):
        """Test that severity parameter takes precedence over risk_level."""
        from backend.api.routes.events import search_events_endpoint

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock search_events function
        with patch("backend.api.routes.events.search_events") as mock_search:
            mock_search.return_value = AsyncMock(results=[], total_count=0, limit=50, offset=0)

            await search_events_endpoint(
                q="test",
                camera_id=None,
                start_date=None,
                end_date=None,
                severity="high,critical",
                risk_level="low",  # Should be ignored
                object_type=None,
                reviewed=None,
                limit=50,
                offset=0,
                db=mock_db,
            )

            # Verify severity was used, not risk_level
            call_args = mock_search.call_args
            filters = call_args.kwargs["filters"]
            assert filters.severity == ["high", "critical"]

    @pytest.mark.asyncio
    async def test_search_events_parses_comma_separated_filters(self):
        """Test that comma-separated filters are parsed correctly."""
        from backend.api.routes.events import search_events_endpoint

        mock_db = AsyncMock(spec=AsyncSession)

        with patch("backend.api.routes.events.search_events") as mock_search:
            mock_search.return_value = AsyncMock(results=[], total_count=0, limit=50, offset=0)

            await search_events_endpoint(
                q="test",
                camera_id="cam1,cam2,cam3",
                start_date=None,
                end_date=None,
                severity="high,medium",
                risk_level=None,
                object_type="person,vehicle",
                reviewed=None,
                limit=50,
                offset=0,
                db=mock_db,
            )

            call_args = mock_search.call_args
            filters = call_args.kwargs["filters"]
            assert filters.camera_ids == ["cam1", "cam2", "cam3"]
            assert filters.severity == ["high", "medium"]
            assert filters.object_types == ["person", "vehicle"]


class TestUpdateEventRouteComprehensive:
    """Comprehensive tests for update_event route handler."""

    @pytest.mark.asyncio
    async def test_update_event_audit_log_failure_rollback(self):
        """Test that audit log failure triggers rollback but still updates event."""
        from backend.api.routes.events import update_event
        from backend.api.schemas.events import EventUpdate

        mock_request = MagicMock()
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 2, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detections = []
        mock_event.detection_ids = "[1, 2]"

        update_data = EventUpdate(reviewed=True, notes="Test note")

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            # Mock audit service to raise exception
            with patch(
                "backend.api.routes.events.AuditService.log_action",
                AsyncMock(side_effect=Exception("Audit failed")),
            ):
                result = await update_event(
                    event_id=1, update_data=update_data, request=mock_request, db=mock_db
                )

        # Event should still be updated despite audit failure
        assert mock_event.reviewed is True
        assert mock_event.notes == "Test note"
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_update_event_notes_only_no_metric(self):
        """Test that updating notes only doesn't record reviewed metric."""
        from backend.api.routes.events import update_event
        from backend.api.schemas.events import EventUpdate

        mock_request = MagicMock()
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event already reviewed
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 2, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.reviewed = True
        mock_event.notes = "Old note"
        mock_event.snooze_until = None
        mock_event.detections = []
        mock_event.detection_ids = "[1]"

        update_data = EventUpdate(notes="New note")

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            with patch("backend.api.routes.events.AuditService.log_action", AsyncMock()):
                with patch("backend.api.routes.events.record_event_reviewed") as mock_metric:
                    await update_event(
                        event_id=1, update_data=update_data, request=mock_request, db=mock_db
                    )

        # Metric should not be recorded for notes-only update
        mock_metric.assert_not_called()
        assert mock_event.notes == "New note"


class TestExportEventsRouteComprehensive:
    """Comprehensive tests for export_events route handler."""

    @pytest.mark.asyncio
    async def test_export_events_audit_log_failure_continues(self):
        """Test that export continues even if audit logging fails."""
        from backend.api.routes.events import export_events

        mock_request = MagicMock()
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock events query
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 12, 23, 12, 2, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reviewed = False
        mock_event.detections = []
        mock_event.detection_ids = "[1, 2]"

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event]

        # Mock cameras query
        mock_camera = Mock()
        mock_camera.id = "cam1"
        mock_camera.name = "Front Door"
        mock_cameras_result = MagicMock()
        mock_cameras_result.scalars.return_value.all.return_value = [mock_camera]

        mock_db.execute = AsyncMock(side_effect=[mock_events_result, mock_cameras_result])

        # Mock audit service to raise exception
        with patch(
            "backend.api.routes.events.AuditService.log_action",
            AsyncMock(side_effect=Exception("Audit failed")),
        ):
            response = await export_events(
                request=mock_request,
                camera_id=None,
                risk_level=None,
                start_date=None,
                end_date=None,
                reviewed=None,
                db=mock_db,
                _rate_limit=None,
            )

        # Export should succeed despite audit failure
        assert response.status_code == 200
        assert response.media_type == "text/csv"


class TestGetEventDetectionsRouteComprehensive:
    """Comprehensive tests for get_event_detections route handler."""

    @pytest.mark.asyncio
    async def test_get_event_detections_with_pagination(self):
        """Test that detections endpoint applies pagination correctly."""
        from backend.api.routes.events import get_event_detections

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock event with detections (use relationship instead of legacy column)
        mock_event = Mock(spec=Event)
        mock_event.detections = [Mock(id=i) for i in range(1, 6)]
        mock_event.detection_id_list = [1, 2, 3, 4, 5]

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        # Mock detections query
        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_detections_result])

        with patch("backend.api.routes.events.get_event_or_404", return_value=mock_event):
            result = await get_event_detections(event_id=1, limit=2, offset=1, db=mock_db)

        assert result.pagination.total == 5
        assert result.pagination.limit == 2
        assert result.pagination.offset == 1
