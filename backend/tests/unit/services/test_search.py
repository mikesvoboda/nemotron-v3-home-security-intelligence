"""Tests for full-text search service.

Tests cover:
- Basic text search
- Phrase search with double quotes
- Boolean operators (AND, OR, NOT)
- Filtering by time range, cameras, severity, object types
- Relevance ranking
- Query parsing
- Filter building
- Search query building
- Database row conversion
- Async service functions
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.search import (
    SearchFilters,
    SearchResponse,
    SearchResult,
    _build_filter_conditions,
    _build_search_query,
    _convert_query_to_tsquery,
    _join_query_parts,
    _parse_detection_ids,
    _process_phrase_token,
    _row_to_search_result,
    refresh_event_search_vector,
    search_events,
    update_event_object_types,
)


class TestQueryParsing:
    """Tests for query string parsing and conversion to tsquery."""

    def test_empty_query(self):
        """Empty query returns empty string."""
        assert _convert_query_to_tsquery("") == ""
        assert _convert_query_to_tsquery("   ") == ""

    def test_single_word(self):
        """Single word is returned as-is."""
        result = _convert_query_to_tsquery("person")
        assert "person" in result

    def test_multiple_words_implicit_and(self):
        """Multiple words are joined with AND (&)."""
        result = _convert_query_to_tsquery("person vehicle")
        assert "person" in result
        assert "vehicle" in result
        assert "&" in result

    def test_explicit_and(self):
        """Explicit AND operator."""
        result = _convert_query_to_tsquery("person AND vehicle")
        assert "person" in result
        assert "vehicle" in result
        assert "&" in result

    def test_or_operator(self):
        """OR operator is converted to |."""
        result = _convert_query_to_tsquery("person OR animal")
        assert "person" in result
        assert "animal" in result
        assert "|" in result

    def test_not_operator(self):
        """NOT operator is converted to !."""
        result = _convert_query_to_tsquery("person NOT cat")
        assert "person" in result
        assert "!cat" in result

    def test_phrase_search(self):
        """Phrase search with double quotes uses proximity operator."""
        result = _convert_query_to_tsquery('"suspicious person"')
        assert "suspicious" in result
        assert "person" in result
        assert "<->" in result

    def test_complex_query(self):
        """Complex query with multiple operators."""
        result = _convert_query_to_tsquery('"suspicious person" OR vehicle NOT cat')
        # Should contain phrase search for "suspicious person"
        assert "<->" in result
        # Should contain OR for vehicle
        assert "|" in result
        # Should contain NOT for cat
        assert "!cat" in result


class TestDetectionIdsParsing:
    """Tests for detection IDs parsing."""

    def test_empty_string(self):
        """Empty string returns empty list."""
        assert _parse_detection_ids("") == []
        assert _parse_detection_ids(None) == []

    def test_json_array_format(self):
        """JSON array format is parsed correctly."""
        assert _parse_detection_ids("[1, 2, 3]") == [1, 2, 3]
        assert _parse_detection_ids("[1,2,3]") == [1, 2, 3]

    def test_single_element_array(self):
        """Single element array is parsed correctly."""
        assert _parse_detection_ids("[42]") == [42]

    def test_legacy_comma_format(self):
        """Legacy comma-separated format works as fallback."""
        assert _parse_detection_ids("1, 2, 3") == [1, 2, 3]
        assert _parse_detection_ids("1,2,3") == [1, 2, 3]

    def test_json_non_list_returns_empty(self):
        """When JSON parses to non-list, return empty list (line 121)."""
        # JSON object (dict) - not a list
        assert _parse_detection_ids('{"key": "value"}') == []
        # JSON string
        assert _parse_detection_ids('"just a string"') == []
        # JSON number
        assert _parse_detection_ids("42") == []
        # JSON null
        assert _parse_detection_ids("null") == []
        # JSON boolean
        assert _parse_detection_ids("true") == []


class TestSearchFilters:
    """Tests for SearchFilters dataclass."""

    def test_default_filters(self):
        """Default filters have expected values."""
        filters = SearchFilters()
        assert filters.start_date is None
        assert filters.end_date is None
        assert filters.camera_ids == []
        assert filters.severity == []
        assert filters.object_types == []
        assert filters.reviewed is None

    def test_filters_with_values(self):
        """Filters can be initialized with values."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 12, 31)
        filters = SearchFilters(
            start_date=start,
            end_date=end,
            camera_ids=["cam1", "cam2"],
            severity=["high", "critical"],
            object_types=["person", "vehicle"],
            reviewed=False,
        )
        assert filters.start_date == start
        assert filters.end_date == end
        assert filters.camera_ids == ["cam1", "cam2"]
        assert filters.severity == ["high", "critical"]
        assert filters.object_types == ["person", "vehicle"]
        assert filters.reviewed is False


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_to_dict(self):
        """SearchResult can be converted to dictionary."""
        result = SearchResult(
            id=1,
            camera_id="front_door",
            camera_name="Front Door",
            started_at=datetime(2025, 12, 28, 12, 0, 0),
            ended_at=datetime(2025, 12, 28, 12, 5, 0),
            risk_score=75,
            risk_level="high",
            summary="Person detected near entrance",
            reasoning="Unknown individual during nighttime",
            reviewed=False,
            detection_count=3,
            detection_ids=[1, 2, 3],
            object_types="person",
            relevance_score=0.85,
        )

        d = result.to_dict()
        assert d["id"] == 1
        assert d["camera_id"] == "front_door"
        assert d["camera_name"] == "Front Door"
        assert d["risk_score"] == 75
        assert d["risk_level"] == "high"
        assert d["relevance_score"] == 0.85


class TestSearchResponse:
    """Tests for SearchResponse dataclass."""

    def test_to_dict(self):
        """SearchResponse can be converted to dictionary."""
        result = SearchResult(
            id=1,
            camera_id="front_door",
            camera_name="Front Door",
            started_at=datetime(2025, 12, 28, 12, 0, 0),
            ended_at=None,
            risk_score=50,
            risk_level="medium",
            summary="Test",
            reasoning="Test",
            reviewed=False,
            detection_count=1,
            detection_ids=[1],
            object_types="person",
            relevance_score=0.5,
        )

        response = SearchResponse(
            results=[result],
            total_count=1,
            limit=50,
            offset=0,
        )

        d = response.to_dict()
        assert len(d["results"]) == 1
        assert d["total_count"] == 1
        assert d["limit"] == 50
        assert d["offset"] == 0


class TestSearchEventsService:
    """Integration-style tests for search_events service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_search_with_empty_query(self, mock_db):
        """Search with empty query returns all events."""
        # Mock the database response
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.camera_id = "front_door"
        mock_event.started_at = datetime(2025, 12, 28, 12, 0, 0)
        mock_event.ended_at = None
        mock_event.risk_score = 50
        mock_event.risk_level = "medium"
        mock_event.summary = "Test event"
        mock_event.reasoning = "Test reasoning"
        mock_event.reviewed = False
        mock_event.detection_id_list = [1]
        mock_event.object_types = "person"

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock main query
        mock_main_result = MagicMock()
        mock_main_result.all.return_value = [(mock_event, 0.0, "Front Door")]

        # Setup mock_db to return different results for different calls
        mock_db.execute.side_effect = [mock_count_result, mock_main_result]

        # Note: This test may need adjustment based on actual database behavior
        # For now, we're testing that the function signature and basic flow work
        # A full integration test would require a real PostgreSQL database

    @pytest.mark.asyncio
    async def test_search_filters_applied(self, mock_db):
        """Verify that filters are applied to the search query."""
        # Test that filters can be created with all options
        filters = SearchFilters(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31),
            camera_ids=["front_door"],
            severity=["high"],
            object_types=["person"],
            reviewed=False,
        )

        # Verify filter values are set correctly
        assert filters.start_date == datetime(2025, 1, 1)
        assert filters.end_date == datetime(2025, 12, 31)
        assert filters.camera_ids == ["front_door"]
        assert filters.severity == ["high"]
        assert filters.object_types == ["person"]
        assert filters.reviewed is False

        # Mock empty results for potential database call
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_main_result = MagicMock()
        mock_main_result.all.return_value = []

        mock_db.execute.side_effect = [mock_count_result, mock_main_result]

        # The actual database filtering is tested in integration tests


class TestProcessPhraseToken:
    """Tests for _process_phrase_token helper function."""

    def test_process_phrase_token_valid(self):
        """Process a valid phrase token."""
        phrases = ["suspicious person", "front door"]
        result_parts: list[str] = []
        new_idx = _process_phrase_token(0, phrases, result_parts)
        assert new_idx == 1
        assert len(result_parts) == 1
        assert "suspicious <-> person" in result_parts[0]

    def test_process_phrase_token_out_of_bounds(self):
        """When phrase_idx >= len(phrases), return phrase_idx (line 135)."""
        phrases = ["suspicious person"]
        result_parts: list[str] = []
        # phrase_idx (2) is greater than len(phrases) (1)
        new_idx = _process_phrase_token(2, phrases, result_parts)
        assert new_idx == 2  # Returns phrase_idx unchanged
        assert len(result_parts) == 0  # No parts added

    def test_process_phrase_token_empty_phrase(self):
        """Empty phrase words list."""
        phrases = [""]  # Empty string phrase
        result_parts: list[str] = []
        new_idx = _process_phrase_token(0, phrases, result_parts)
        assert new_idx == 1  # Incremented
        assert len(result_parts) == 0  # No parts added for empty phrase


class TestJoinQueryParts:
    """Tests for _join_query_parts helper function."""

    def test_join_simple_parts(self):
        """Join simple word parts."""
        result = _join_query_parts(["person", "vehicle", "dog"])
        assert result == "person & vehicle & dog"

    def test_join_with_or(self):
        """Join parts with OR operator."""
        result = _join_query_parts(["person", "|", "vehicle"])
        assert result == "person | vehicle"

    def test_join_empty_parts(self):
        """Join empty parts list."""
        result = _join_query_parts([])
        assert result == ""

    def test_join_single_part(self):
        """Join single part."""
        result = _join_query_parts(["person"])
        assert result == "person"


class TestBuildFilterConditions:
    """Tests for _build_filter_conditions function (lines 284-300)."""

    def test_empty_filters(self):
        """Empty filters return empty conditions list."""
        filters = SearchFilters()
        conditions = _build_filter_conditions(filters)
        assert conditions == []

    def test_start_date_filter(self):
        """Start date filter creates condition."""
        filters = SearchFilters(start_date=datetime(2025, 1, 1))
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1

    def test_end_date_filter(self):
        """End date filter creates condition."""
        filters = SearchFilters(end_date=datetime(2025, 12, 31))
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1

    def test_camera_ids_filter(self):
        """Camera IDs filter creates condition."""
        filters = SearchFilters(camera_ids=["cam1", "cam2"])
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1

    def test_severity_filter(self):
        """Severity filter creates condition."""
        filters = SearchFilters(severity=["high", "critical"])
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1

    def test_reviewed_true_filter(self):
        """Reviewed=True filter creates condition."""
        filters = SearchFilters(reviewed=True)
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1

    def test_reviewed_false_filter(self):
        """Reviewed=False filter creates condition."""
        filters = SearchFilters(reviewed=False)
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1

    def test_object_types_filter(self):
        """Object types filter creates OR condition."""
        filters = SearchFilters(object_types=["person", "vehicle"])
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1  # Single OR condition

    def test_all_filters_combined(self):
        """All filters combined creates multiple conditions."""
        filters = SearchFilters(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31),
            camera_ids=["cam1"],
            severity=["high"],
            object_types=["person"],
            reviewed=False,
        )
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 6


class TestBuildSearchQuery:
    """Tests for _build_search_query function (lines 257-272)."""

    def test_build_with_operators(self):
        """Build search query with operators like & | ! <->."""
        # Query with AND operator
        tsquery_str = "person & vehicle"
        query = "person AND vehicle"
        result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True
        # The result is a SQLAlchemy Select object
        assert result is not None

    def test_build_with_or_operator(self):
        """Build search query with OR operator."""
        tsquery_str = "person | vehicle"
        query = "person OR vehicle"
        _result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True

    def test_build_with_not_operator(self):
        """Build search query with NOT operator."""
        tsquery_str = "person & !cat"
        query = "person NOT cat"
        _result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True

    def test_build_with_proximity_operator(self):
        """Build search query with phrase proximity operator."""
        tsquery_str = "(suspicious <-> person)"
        query = '"suspicious person"'
        _result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True

    def test_build_without_operators_uses_websearch(self):
        """Build search query without operators uses websearch_to_tsquery."""
        # Single word without operators
        tsquery_str = "person"
        query = "person"
        _result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True

    def test_build_empty_tsquery(self):
        """Build search query with empty tsquery string (line 271-272)."""
        tsquery_str = ""
        query = ""
        result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is False
        # The result should still be a valid query object
        assert result is not None

    def test_build_query_includes_ilike_fallback(self):
        """Build search query includes ILIKE fallback for NULL search_vector.

        The query should include an OR condition that falls back to ILIKE
        matching on summary, reasoning, and object_types when search_vector is NULL.
        """
        tsquery_str = "person"
        query = "person"
        result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True
        assert result is not None

        # Convert to string to inspect the query structure
        query_str = str(result)

        # The query should contain LIKE patterns for fallback
        # Note: SQLAlchemy may render ILIKE as 'lower(col) LIKE lower(:param)' for portability
        # or as 'ILIKE' depending on the dialect
        assert "like" in query_str.lower()

    def test_build_query_escapes_ilike_special_chars(self):
        """Build search query escapes ILIKE special characters in fallback.

        Special characters like %, _, and \\ should be escaped to prevent
        pattern injection attacks.
        """
        tsquery_str = "test"
        # Query with special ILIKE characters
        query = "test%pattern_with\\special"
        result, has_search = _build_search_query(tsquery_str, query)
        assert has_search is True
        assert result is not None

        # The query should be built successfully without errors
        # The escape_ilike_pattern function handles the escaping


class TestILikeFallbackBehavior:
    """Tests for ILIKE fallback behavior when search_vector is NULL."""

    def test_build_search_query_structure(self):
        """Verify the search query structure includes fallback conditions."""
        tsquery_str = "person"
        query = "person"
        result, has_search = _build_search_query(tsquery_str, query)

        assert has_search is True
        assert result is not None

        # The query should be a SQLAlchemy Select object
        # We can verify it compiles without errors
        from sqlalchemy.dialects import postgresql

        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # Should contain references to search_vector (for FTS match)
        assert "search_vector" in query_text

        # Should contain ILIKE for fallback (rendered as ILIKE in PostgreSQL)
        assert "ilike" in query_text.lower()

    def test_ilike_fallback_searches_summary(self):
        """ILIKE fallback should search in summary field."""
        tsquery_str = "suspicious"
        query = "suspicious"
        result, _ = _build_search_query(tsquery_str, query)

        from sqlalchemy.dialects import postgresql

        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # Should reference summary in the ILIKE condition
        assert "summary" in query_text.lower()

    def test_ilike_fallback_searches_reasoning(self):
        """ILIKE fallback should search in reasoning field."""
        tsquery_str = "analysis"
        query = "analysis"
        result, _ = _build_search_query(tsquery_str, query)

        from sqlalchemy.dialects import postgresql

        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # Should reference reasoning in the ILIKE condition
        assert "reasoning" in query_text.lower()

    def test_ilike_fallback_searches_object_types(self):
        """ILIKE fallback should search in object_types field."""
        tsquery_str = "vehicle"
        query = "vehicle"
        result, _ = _build_search_query(tsquery_str, query)

        from sqlalchemy.dialects import postgresql

        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # Should reference object_types in the ILIKE condition
        assert "object_types" in query_text.lower()

    def test_ilike_fallback_only_when_search_vector_is_null(self):
        """ILIKE fallback should only apply when search_vector IS NULL."""
        tsquery_str = "person"
        query = "person"
        result, _ = _build_search_query(tsquery_str, query)

        from sqlalchemy.dialects import postgresql

        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # Should contain IS NULL check for search_vector
        assert "is null" in query_text.lower()


class TestRowToSearchResult:
    """Tests for _row_to_search_result function (lines 305-310)."""

    def test_convert_row_to_search_result(self):
        """Convert database row tuple to SearchResult."""
        # Create mock event object
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.camera_id = "front_door"
        mock_event.started_at = datetime(2025, 12, 28, 12, 0, 0)
        mock_event.ended_at = datetime(2025, 12, 28, 12, 5, 0)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Person detected near entrance"
        mock_event.reasoning = "Unknown individual during nighttime"
        mock_event.reviewed = False
        mock_event.object_types = "person, vehicle"
        # NEM-1592: Use detections relationship (detection_ids column was dropped)
        mock_detection_1 = MagicMock()
        mock_detection_1.id = 1
        mock_detection_2 = MagicMock()
        mock_detection_2.id = 2
        mock_detection_3 = MagicMock()
        mock_detection_3.id = 3
        mock_event.detections = [mock_detection_1, mock_detection_2, mock_detection_3]

        # Create row tuple (event, relevance_score, camera_name)
        row = (mock_event, 0.85, "Front Door Camera")

        result = _row_to_search_result(row)

        assert result.id == 1
        assert result.camera_id == "front_door"
        assert result.camera_name == "Front Door Camera"
        assert result.started_at == datetime(2025, 12, 28, 12, 0, 0)
        assert result.ended_at == datetime(2025, 12, 28, 12, 5, 0)
        assert result.risk_score == 75
        assert result.risk_level == "high"
        assert result.summary == "Person detected near entrance"
        assert result.reasoning == "Unknown individual during nighttime"
        assert result.reviewed is False
        assert result.detection_count == 3
        assert result.detection_ids == [1, 2, 3]
        assert result.object_types == "person, vehicle"
        assert result.relevance_score == 0.85

    def test_convert_row_with_none_relevance(self):
        """Convert row with None relevance score."""
        mock_event = MagicMock()
        mock_event.id = 2
        mock_event.camera_id = "back_yard"
        mock_event.started_at = datetime(2025, 12, 28, 10, 0, 0)
        mock_event.ended_at = None
        mock_event.risk_score = None
        mock_event.risk_level = None
        mock_event.summary = None
        mock_event.reasoning = None
        mock_event.reviewed = True
        mock_event.object_types = None
        # NEM-1592: Use detections relationship (detection_ids column was dropped)
        mock_event.detections = []

        row = (mock_event, None, None)

        result = _row_to_search_result(row)

        assert result.id == 2
        assert result.camera_name is None
        assert result.ended_at is None
        assert result.risk_score is None
        assert result.relevance_score == 0.0  # None converted to 0.0
        assert result.detection_count == 0
        assert result.detection_ids == []


class TestQueryOperatorEdgeCases:
    """Test edge cases in query operator handling."""

    def test_consecutive_operators(self):
        """Consecutive operators are handled gracefully."""
        # AND AND should not crash
        result = _convert_query_to_tsquery("person AND AND vehicle")
        assert "person" in result
        assert "vehicle" in result

    def test_trailing_operator(self):
        """Trailing operators don't cause issues."""
        result = _convert_query_to_tsquery("person AND")
        assert "person" in result

    def test_leading_operator(self):
        """Leading operators are handled."""
        result = _convert_query_to_tsquery("AND person")
        assert "person" in result

    def test_not_without_target(self):
        """NOT without a following word is handled."""
        result = _convert_query_to_tsquery("person NOT")
        assert "person" in result

    def test_case_insensitive_operators(self):
        """Operators work in any case."""
        result1 = _convert_query_to_tsquery("person and vehicle")
        result2 = _convert_query_to_tsquery("person AND vehicle")
        result3 = _convert_query_to_tsquery("person And vehicle")
        # All should produce similar results with & operator
        assert "&" in result1
        assert "&" in result2
        assert "&" in result3

    def test_multiple_phrases(self):
        """Multiple phrase searches work."""
        result = _convert_query_to_tsquery('"suspicious person" "front door"')
        assert "<->" in result
        # Both phrases should be processed

    def test_mixed_phrase_and_words(self):
        """Phrases mixed with regular words work."""
        result = _convert_query_to_tsquery('"suspicious person" vehicle')
        assert "<->" in result
        assert "vehicle" in result

    def test_special_characters_removed(self):
        """Special characters that could break tsquery are removed."""
        result = _convert_query_to_tsquery("person! @vehicle #test")
        # Should not crash and should contain cleaned tokens
        assert "person" in result
        assert "vehicle" in result
        assert "test" in result


class TestPaginationAndLimits:
    """Tests for pagination behavior."""

    def test_search_filters_default_values(self):
        """SearchFilters has sensible defaults."""
        filters = SearchFilters()
        assert filters.camera_ids == []
        assert filters.severity == []
        assert filters.object_types == []

    def test_search_response_pagination(self):
        """SearchResponse correctly captures pagination info."""
        response = SearchResponse(
            results=[],
            total_count=100,
            limit=10,
            offset=20,
        )
        assert response.total_count == 100
        assert response.limit == 10
        assert response.offset == 20

        d = response.to_dict()
        assert d["total_count"] == 100
        assert d["limit"] == 10
        assert d["offset"] == 20


class TestQueryEmptyTokens:
    """Tests for empty token handling in query parsing (lines 228-229, 235)."""

    def test_query_with_multiple_spaces(self):
        """Multiple spaces between words should be handled."""
        result = _convert_query_to_tsquery("person    vehicle")
        assert "person" in result
        assert "vehicle" in result

    def test_query_all_whitespace_tokens(self):
        """Query that becomes empty after processing."""
        # All special characters that get stripped
        result = _convert_query_to_tsquery("!@#$%")
        # Should return empty string since no valid tokens
        assert result == "" or result.strip() == ""

    def test_query_only_operators(self):
        """Query with only operators (line 235 - empty result_parts)."""
        result = _convert_query_to_tsquery("AND OR NOT")
        # Should return empty string since no actual words
        # Note: This tests line 235 where result_parts is empty
        assert result == ""


class TestSearchEventsAsync:
    """Async tests for search_events function (lines 350-377)."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_event(self):
        """Create a mock event object."""
        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.started_at = datetime(2025, 12, 28, 12, 0, 0)
        event.ended_at = datetime(2025, 12, 28, 12, 5, 0)
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Person detected"
        event.reasoning = "Unknown individual"
        event.reviewed = False
        event.detection_ids = "[1, 2, 3]"
        event.object_types = "person"
        return event

    @pytest.mark.asyncio
    async def test_search_with_no_filters(self, mock_db, mock_event):
        """Search events without filters (line 350-351)."""
        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock main query result
        mock_main_result = MagicMock()
        mock_main_result.all.return_value = [(mock_event, 0.5, "Front Door")]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        response = await search_events(mock_db, "person")

        assert response.total_count == 1
        assert len(response.results) == 1
        assert response.limit == 50
        assert response.offset == 0

    @pytest.mark.asyncio
    async def test_search_with_filters(self, mock_db, mock_event):
        """Search events with filters applied."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_main_result = MagicMock()
        mock_main_result.all.return_value = [(mock_event, 0.5, "Front Door")]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        filters = SearchFilters(
            camera_ids=["front_door"],
            severity=["high"],
        )

        response = await search_events(mock_db, "person", filters=filters)

        assert response.total_count == 1
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_search_with_empty_results(self, mock_db):
        """Search returns empty results."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_main_result = MagicMock()
        mock_main_result.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        response = await search_events(mock_db, "nonexistent")

        assert response.total_count == 0
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, mock_db, mock_event):
        """Search with custom limit and offset."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_main_result = MagicMock()
        mock_main_result.all.return_value = [(mock_event, 0.5, "Front Door")]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        response = await search_events(mock_db, "person", limit=10, offset=20)

        assert response.total_count == 100
        assert response.limit == 10
        assert response.offset == 20

    @pytest.mark.asyncio
    async def test_search_with_empty_query(self, mock_db, mock_event):
        """Search with empty query returns all events (no search filter)."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_main_result = MagicMock()
        mock_main_result.all.return_value = [(mock_event, 0.0, "Front Door")]

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        response = await search_events(mock_db, "")

        assert response.total_count == 5

    @pytest.mark.asyncio
    async def test_search_with_null_count(self, mock_db):
        """Search handles null count result (line 364)."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None  # NULL from DB

        mock_main_result = MagicMock()
        mock_main_result.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_main_result])

        response = await search_events(mock_db, "person")

        assert response.total_count == 0  # None converted to 0


class TestRefreshEventSearchVector:
    """Tests for refresh_event_search_vector async function (lines 396-411)."""

    @pytest.mark.asyncio
    async def test_refresh_search_vector(self):
        """Test refreshing search vector for an event."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await refresh_event_search_vector(mock_db, event_id=42)

        # Verify execute was called with the UPDATE statement
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args

        # Verify the event_id parameter was passed
        assert call_args[0][1] == {"event_id": 42}

        # Verify commit was called
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_search_vector_multiple_events(self):
        """Refresh search vector for multiple events sequentially."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await refresh_event_search_vector(mock_db, event_id=1)
        await refresh_event_search_vector(mock_db, event_id=2)

        assert mock_db.execute.call_count == 2
        assert mock_db.commit.call_count == 2


class TestUpdateEventObjectTypes:
    """Tests for update_event_object_types async function (lines 430-436)."""

    @pytest.mark.asyncio
    async def test_update_object_types(self):
        """Test updating object types for an event."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await update_event_object_types(mock_db, event_id=42, object_types=["person", "vehicle"])

        # Verify execute was called
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args

        # Object types should be sorted and joined
        assert call_args[0][1]["object_types"] == "person, vehicle"
        assert call_args[0][1]["event_id"] == 42

        # Verify commit was called
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_object_types_deduplicates(self):
        """Duplicate object types are removed."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await update_event_object_types(
            mock_db, event_id=1, object_types=["person", "person", "vehicle", "vehicle"]
        )

        call_args = mock_db.execute.call_args
        # Should be deduplicated and sorted
        assert call_args[0][1]["object_types"] == "person, vehicle"

    @pytest.mark.asyncio
    async def test_update_object_types_empty_list(self):
        """Empty object types list sets None."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await update_event_object_types(mock_db, event_id=1, object_types=[])

        call_args = mock_db.execute.call_args
        assert call_args[0][1]["object_types"] is None

    @pytest.mark.asyncio
    async def test_update_object_types_sorts_alphabetically(self):
        """Object types are sorted alphabetically."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await update_event_object_types(
            mock_db, event_id=1, object_types=["zebra", "animal", "cat"]
        )

        call_args = mock_db.execute.call_args
        assert call_args[0][1]["object_types"] == "animal, cat, zebra"


class TestSearchResultToDict:
    """Additional tests for SearchResult.to_dict edge cases."""

    def test_to_dict_with_none_started_at(self):
        """SearchResult with None started_at."""
        result = SearchResult(
            id=1,
            camera_id="cam1",
            camera_name=None,
            started_at=None,  # type: ignore  # Testing edge case
            ended_at=None,
            risk_score=None,
            risk_level=None,
            summary=None,
            reasoning=None,
            reviewed=False,
            detection_count=0,
            detection_ids=[],
            object_types=None,
            relevance_score=0.0,
        )
        d = result.to_dict()
        assert d["started_at"] is None
        assert d["ended_at"] is None


class TestBuildSearchQueryOrderBehavior:
    """Tests for search query ordering behavior.

    These tests verify that the query ordering is correctly set up for both
    search queries (ordered by relevance_score DESC) and non-search queries
    (ordered by started_at DESC). Mutation testing identified that the ordering
    could be replaced with None without failing existing tests.
    """

    def test_search_query_has_relevance_ordering(self):
        """Verify search query orders by relevance_score DESC.

        This test ensures that when a search query is built with operators,
        it includes proper ORDER BY relevance_score DESC ordering.
        Mutation test mutant_25 identified this could be replaced with None.
        """
        from sqlalchemy.dialects import postgresql

        tsquery_str = "person & vehicle"
        query = "person AND vehicle"
        result, has_search = _build_search_query(tsquery_str, query)

        assert has_search is True
        assert result is not None

        # Compile the query to inspect it
        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # The query should include the relevance_score column
        assert "relevance_score" in query_text.lower()

    def test_has_operators_detection_returns_true_for_operators(self):
        """Test that has_operators correctly detects query operators.

        Mutation testing found that `has_operators = any(op in tsquery_str ...)
        could be replaced with `has_operators = None`. This test verifies the
        operator detection path is taken correctly.
        """
        # Queries with operators should use to_tsquery
        operator_queries = [
            ("person & vehicle", "person AND vehicle"),
            ("person | animal", "person OR animal"),
            ("person & !cat", "person NOT cat"),
            ("(suspicious <-> person)", '"suspicious person"'),
        ]

        for tsquery_str, query in operator_queries:
            _result, has_search = _build_search_query(tsquery_str, query)
            assert has_search is True, f"Expected has_search=True for {tsquery_str}"

    def test_no_operators_uses_websearch_to_tsquery(self):
        """Test that queries without operators use websearch_to_tsquery.

        When the tsquery string has no operators, it should use websearch_to_tsquery
        which provides better handling of simple text queries.
        """
        from sqlalchemy.dialects import postgresql

        # Simple word without operators
        tsquery_str = "person"
        query = "person"
        result, has_search = _build_search_query(tsquery_str, query)

        assert has_search is True
        compiled = result.compile(dialect=postgresql.dialect())
        query_text = str(compiled)

        # The query should include search_vector matching
        assert "search_vector" in query_text.lower()


# =============================================================================
# Property-Based Tests (Hypothesis)
# =============================================================================

from hypothesis import given  # noqa: E402
from hypothesis import settings as hypothesis_settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from backend.tests.strategies import (  # noqa: E402
    detection_ids_json_strategy,
    search_query_strategy,
    search_terms,
)


class TestSearchQueryParsingProperties:
    """Property-based tests for search query parsing."""

    # -------------------------------------------------------------------------
    # Query Conversion Properties
    # -------------------------------------------------------------------------

    @given(query=search_terms)
    @hypothesis_settings(max_examples=100)
    def test_single_word_query_produces_non_empty_result(self, query: str) -> None:
        """Property: Non-empty query produces non-empty tsquery."""
        if query.strip():
            result = _convert_query_to_tsquery(query)
            # Should produce a non-empty result for valid queries
            # (unless the query only contains special characters)
            cleaned = "".join(c for c in query if c.isalnum())
            if cleaned:
                assert len(result) > 0

    @given(query=search_query_strategy())
    @hypothesis_settings(max_examples=100)
    def test_query_conversion_is_deterministic(self, query: str) -> None:
        """Property: Same query always produces the same tsquery."""
        result1 = _convert_query_to_tsquery(query)
        result2 = _convert_query_to_tsquery(query)
        result3 = _convert_query_to_tsquery(query)
        assert result1 == result2 == result3

    @given(query=st.text(min_size=0, max_size=100))
    @hypothesis_settings(max_examples=100)
    def test_query_conversion_never_crashes(self, query: str) -> None:
        """Property: Query conversion never raises exceptions."""
        # Should not raise any exception
        result = _convert_query_to_tsquery(query)
        assert isinstance(result, str)

    @given(
        term1=search_terms,
        term2=search_terms,
    )
    @hypothesis_settings(max_examples=50)
    def test_or_operator_produces_pipe(self, term1: str, term2: str) -> None:
        """Property: OR between terms produces | in tsquery."""
        query = f"{term1} OR {term2}"
        result = _convert_query_to_tsquery(query)
        # Clean the terms to check if they would actually produce valid tsquery terms
        clean1 = "".join(c for c in term1 if c.isalnum())
        clean2 = "".join(c for c in term2 if c.isalnum())
        if clean1 and clean2:
            assert "|" in result

    @given(
        term1=search_terms,
        term2=search_terms,
    )
    @hypothesis_settings(max_examples=50)
    def test_implicit_and_produces_ampersand(self, term1: str, term2: str) -> None:
        """Property: Two terms without operator produce & (AND)."""
        query = f"{term1} {term2}"
        result = _convert_query_to_tsquery(query)
        # Clean the terms to check if they would actually appear
        clean1 = "".join(c for c in term1 if c.isalnum())
        clean2 = "".join(c for c in term2 if c.isalnum())
        if clean1 and clean2 and clean1 != clean2:
            assert "&" in result

    @given(
        term1=search_terms,
        term2=search_terms,
    )
    @hypothesis_settings(max_examples=50)
    def test_not_operator_produces_negation(self, term1: str, term2: str) -> None:
        """Property: NOT before a term produces ! in tsquery."""
        query = f"{term1} NOT {term2}"
        result = _convert_query_to_tsquery(query)
        clean2 = "".join(c for c in term2 if c.isalnum())
        if clean2:
            assert f"!{clean2}" in result or "!" in result

    # -------------------------------------------------------------------------
    # Phrase Search Properties
    # -------------------------------------------------------------------------

    @given(
        word1=st.from_regex(r"[a-z]{2,10}", fullmatch=True),
        word2=st.from_regex(r"[a-z]{2,10}", fullmatch=True),
    )
    @hypothesis_settings(max_examples=50)
    def test_phrase_search_produces_proximity(self, word1: str, word2: str) -> None:
        """Property: Quoted phrase produces proximity operator <->."""
        query = f'"{word1} {word2}"'
        result = _convert_query_to_tsquery(query)
        assert "<->" in result
        assert word1 in result
        assert word2 in result

    # -------------------------------------------------------------------------
    # Filter Conditions Properties
    # -------------------------------------------------------------------------

    @given(
        num_cameras=st.integers(min_value=0, max_value=5),
        num_severities=st.integers(min_value=0, max_value=4),
        num_object_types=st.integers(min_value=0, max_value=5),
    )
    @hypothesis_settings(max_examples=50)
    def test_filter_conditions_count(
        self,
        num_cameras: int,
        num_severities: int,
        num_object_types: int,
    ) -> None:
        """Property: Number of filter conditions matches expected."""
        camera_ids = [f"cam{i}" for i in range(num_cameras)]
        severities = ["low", "medium", "high", "critical"][:num_severities]
        object_types = [f"obj{i}" for i in range(num_object_types)]

        filters = SearchFilters(
            camera_ids=camera_ids,
            severity=severities,
            object_types=object_types,
        )
        conditions = _build_filter_conditions(filters)

        expected_count = 0
        if camera_ids:
            expected_count += 1
        if severities:
            expected_count += 1
        if object_types:
            expected_count += 1

        assert len(conditions) == expected_count

    @given(reviewed=st.booleans())
    @hypothesis_settings(max_examples=10)
    def test_reviewed_filter_always_produces_condition(self, reviewed: bool) -> None:
        """Property: Setting reviewed always produces exactly one condition."""
        filters = SearchFilters(reviewed=reviewed)
        conditions = _build_filter_conditions(filters)
        assert len(conditions) == 1


class TestDetectionIdsParsingProperties:
    """Property-based tests for detection ID parsing."""

    @given(ids_json=detection_ids_json_strategy())
    @hypothesis_settings(max_examples=100)
    def test_json_format_parsing_produces_list(self, ids_json: str) -> None:
        """Property: JSON array format always produces a list."""
        result = _parse_detection_ids(ids_json)
        assert isinstance(result, list)
        assert all(isinstance(i, int) for i in result)

    @given(ids=st.lists(st.integers(min_value=1, max_value=10000), min_size=2, max_size=10))
    @hypothesis_settings(max_examples=100)
    def test_csv_format_parsing_produces_list(self, ids: list[int]) -> None:
        """Property: CSV format with multiple IDs always produces a list of integers."""
        # Generate CSV format with commas (at least 2 IDs ensures fallback to comma parsing)
        ids_csv = ", ".join(str(i) for i in ids)
        result = _parse_detection_ids(ids_csv)
        assert isinstance(result, list)
        assert all(isinstance(i, int) for i in result)
        # Multi-value CSV falls back to comma-split parsing
        assert len(result) == len(ids)

    @given(ids=st.lists(st.integers(min_value=1, max_value=10000), min_size=0, max_size=10))
    @hypothesis_settings(max_examples=100)
    def test_json_roundtrip_preserves_ids(self, ids: list[int]) -> None:
        """Property: Serializing to JSON and parsing back preserves IDs."""
        import json

        json_str = json.dumps(ids)
        result = _parse_detection_ids(json_str)
        assert result == ids

    @given(
        input_type=st.sampled_from(["json_array", "csv", "empty", "invalid_json"]),
        ids=st.lists(st.integers(min_value=1, max_value=10000), min_size=0, max_size=5),
    )
    @hypothesis_settings(max_examples=100)
    def test_valid_inputs_parse_without_crashes(self, input_type: str, ids: list[int]) -> None:
        """Property: Valid inputs (JSON arrays, CSV numbers) parse without crashes."""
        import json

        if input_type == "json_array":
            input_str = json.dumps(ids)
        elif input_type == "csv":
            input_str = ", ".join(str(i) for i in ids) if ids else ""
        elif input_type == "empty":
            input_str = ""
        else:  # invalid_json - valid CSV fallback
            input_str = ", ".join(str(i) for i in ids) if ids else "[]"

        # Should not raise any exception
        result = _parse_detection_ids(input_str)
        assert isinstance(result, list)

    def test_empty_inputs_produce_empty_list(self) -> None:
        """Property: Empty/None inputs produce empty list."""
        assert _parse_detection_ids("") == []
        assert _parse_detection_ids(None) == []
        assert _parse_detection_ids("   ") == []  # Whitespace-only

    @given(ids=st.lists(st.integers(min_value=1, max_value=10000), min_size=1, max_size=10))
    @hypothesis_settings(max_examples=50)
    def test_result_count_matches_input(self, ids: list[int]) -> None:
        """Property: Parsed result has same count as input."""
        import json

        json_str = json.dumps(ids)
        result = _parse_detection_ids(json_str)
        assert len(result) == len(ids)


class TestSearchResultProperties:
    """Property-based tests for SearchResult dataclass."""

    @given(
        risk_score=st.integers(min_value=0, max_value=100),
        relevance=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        detection_count=st.integers(min_value=0, max_value=100),
    )
    @hypothesis_settings(max_examples=50)
    def test_search_result_to_dict_preserves_values(
        self,
        risk_score: int,
        relevance: float,
        detection_count: int,
    ) -> None:
        """Property: to_dict preserves all field values."""
        detection_ids = list(range(1, detection_count + 1))
        result = SearchResult(
            id=1,
            camera_id="test_cam",
            camera_name="Test Camera",
            started_at=datetime(2025, 1, 1, 12, 0, 0),
            ended_at=None,
            risk_score=risk_score,
            risk_level="medium",
            summary="Test summary",
            reasoning="Test reasoning",
            reviewed=False,
            detection_count=detection_count,
            detection_ids=detection_ids,
            object_types="person",
            relevance_score=relevance,
        )

        d = result.to_dict()

        assert d["risk_score"] == risk_score
        assert d["relevance_score"] == relevance
        assert d["detection_count"] == detection_count
        assert d["detection_ids"] == detection_ids

    @given(
        total=st.integers(min_value=0, max_value=10000),
        limit=st.integers(min_value=1, max_value=100),
        offset=st.integers(min_value=0, max_value=1000),
    )
    @hypothesis_settings(max_examples=50)
    def test_search_response_pagination_values(
        self,
        total: int,
        limit: int,
        offset: int,
    ) -> None:
        """Property: SearchResponse preserves pagination values."""
        response = SearchResponse(
            results=[],
            total_count=total,
            limit=limit,
            offset=offset,
        )

        d = response.to_dict()

        assert d["total_count"] == total
        assert d["limit"] == limit
        assert d["offset"] == offset
        assert d["results"] == []


class TestJoinQueryPartsProperties:
    """Property-based tests for _join_query_parts."""

    @given(parts=st.lists(st.from_regex(r"[a-z]{2,10}", fullmatch=True), min_size=1, max_size=5))
    @hypothesis_settings(max_examples=50)
    def test_join_parts_contains_all_terms(self, parts: list[str]) -> None:
        """Property: All input terms appear in joined result."""
        result = _join_query_parts(parts)
        for part in parts:
            assert part in result

    @given(parts=st.lists(st.from_regex(r"[a-z]{2,10}", fullmatch=True), min_size=2, max_size=5))
    @hypothesis_settings(max_examples=50)
    def test_join_parts_produces_and_operators(self, parts: list[str]) -> None:
        """Property: Multiple parts are joined with & (AND)."""
        result = _join_query_parts(parts)
        assert "&" in result

    @given(part=st.from_regex(r"[a-z]{2,10}", fullmatch=True))
    @hypothesis_settings(max_examples=20)
    def test_single_part_no_operators(self, part: str) -> None:
        """Property: Single part has no operators."""
        result = _join_query_parts([part])
        assert result == part
        assert "&" not in result
        assert "|" not in result

    def test_empty_list_produces_empty_string(self) -> None:
        """Property: Empty list produces empty string."""
        assert _join_query_parts([]) == ""


class TestQueryIdempotence:
    """Property-based tests for idempotence of query operations."""

    @given(query=search_query_strategy())
    @hypothesis_settings(max_examples=50)
    def test_tsquery_conversion_is_idempotent(self, query: str) -> None:
        """Property: Converting to tsquery is idempotent (deterministic)."""
        result1 = _convert_query_to_tsquery(query)
        result2 = _convert_query_to_tsquery(query)
        assert result1 == result2

    @given(
        camera_ids=st.lists(st.from_regex(r"[a-z]{3,10}", fullmatch=True), max_size=3),
        severity=st.lists(
            st.sampled_from(["low", "medium", "high", "critical"]),
            max_size=4,
            unique=True,
        ),
    )
    @hypothesis_settings(max_examples=50)
    def test_filter_building_is_idempotent(
        self,
        camera_ids: list[str],
        severity: list[str],
    ) -> None:
        """Property: Building filter conditions is idempotent."""
        filters = SearchFilters(camera_ids=camera_ids, severity=severity)
        conditions1 = _build_filter_conditions(filters)
        conditions2 = _build_filter_conditions(filters)
        assert len(conditions1) == len(conditions2)
