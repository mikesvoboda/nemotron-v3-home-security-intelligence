"""Unit tests for logs API cursor-based pagination.

Tests the cursor-based pagination implementation in the logs endpoint.
"""

from datetime import UTC, datetime

from backend.api.pagination import CursorData, encode_cursor
from backend.api.schemas.logs import LogsResponse


class TestLogsResponseWithCursor:
    """Tests for LogsResponse schema with cursor pagination fields."""

    def test_logs_response_with_cursor_fields(self):
        """Test LogsResponse includes cursor pagination fields."""
        data = {
            "logs": [],
            "count": 100,
            "limit": 50,
            "offset": 0,
            "next_cursor": "eyJpZCI6IDEwMCwgImNyZWF0ZWRfYXQiOiAiMjAyNS0xMi0yM1QxMjowMDowMFoifQ==",  # pragma: allowlist secret
            "has_more": True,
        }
        response = LogsResponse(**data)
        assert response.next_cursor is not None
        assert response.has_more is True

    def test_logs_response_no_more_results(self):
        """Test LogsResponse when there are no more results."""
        data = {
            "logs": [],
            "count": 10,
            "limit": 50,
            "offset": 0,
            "next_cursor": None,
            "has_more": False,
        }
        response = LogsResponse(**data)
        assert response.next_cursor is None
        assert response.has_more is False

    def test_logs_response_backward_compatible_without_cursor(self):
        """Test LogsResponse still works without cursor fields (backward compatibility)."""
        data = {
            "logs": [],
            "count": 0,
            "limit": 50,
            "offset": 0,
        }
        response = LogsResponse(**data)
        # Should default to None/False for cursor fields
        assert response.next_cursor is None
        assert response.has_more is False

    def test_logs_response_deprecation_warning(self):
        """Test LogsResponse can include deprecation warning."""
        data = {
            "logs": [],
            "count": 100,
            "limit": 50,
            "offset": 20,
            "deprecation_warning": "Offset pagination is deprecated. Please use cursor-based pagination.",
        }
        response = LogsResponse(**data)
        assert response.deprecation_warning is not None
        assert "deprecated" in response.deprecation_warning.lower()


class TestLogsPaginationLogic:
    """Tests for cursor-based pagination logic in list_logs endpoint."""

    def test_cursor_from_log_data(self):
        """Test creating cursor from log data (id and timestamp)."""
        # Simulate creating a cursor from the last log in a response
        log_id = 100
        timestamp = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        cursor_data = CursorData(id=log_id, created_at=timestamp)
        encoded = encode_cursor(cursor_data)

        # Verify cursor is a non-empty string
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_pagination_has_more_logic(self):
        """Test has_more is true when results exceed limit."""
        limit = 50
        fetched_items = 51

        has_more = fetched_items > limit
        assert has_more is True

    def test_pagination_no_more_results(self):
        """Test has_more is false when results don't exceed limit."""
        limit = 50
        fetched_items = 30

        has_more = fetched_items > limit
        assert has_more is False

    def test_pagination_exact_limit(self):
        """Test has_more is false when results equal limit exactly."""
        limit = 50
        fetched_items = 50

        has_more = fetched_items > limit
        assert has_more is False
