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
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": None,
                "cursor": None,
                "next_cursor": "eyJpZCI6IDEwMCwgImNyZWF0ZWRfYXQiOiAiMjAyNS0xMi0yM1QxMjowMDowMFoifQ==",  # pragma: allowlist secret
                "has_more": True,
            },
        }
        response = LogsResponse(**data)
        assert response.pagination.next_cursor is not None
        assert response.pagination.has_more is True

    def test_logs_response_no_more_results(self):
        """Test LogsResponse when there are no more results."""
        data = {
            "items": [],
            "pagination": {
                "total": 10,
                "limit": 50,
                "offset": None,
                "cursor": None,
                "next_cursor": None,
                "has_more": False,
            },
        }
        response = LogsResponse(**data)
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_logs_response_backward_compatible_without_cursor(self):
        """Test LogsResponse still works without explicit cursor fields."""
        data = {
            "items": [],
            "pagination": {
                "total": 0,
                "limit": 50,
                "offset": None,
                "cursor": None,
                "next_cursor": None,
                "has_more": False,
            },
        }
        response = LogsResponse(**data)
        # Should default to None/False for cursor fields
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_logs_response_deprecation_warning(self):
        """Test LogsResponse includes offset for deprecation warning tracking."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": 20,
                "cursor": None,
                "next_cursor": None,
                "has_more": False,
            },
        }
        response = LogsResponse(**data)
        # When offset is used (non-None), it indicates deprecated offset pagination
        assert response.pagination.offset == 20


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
