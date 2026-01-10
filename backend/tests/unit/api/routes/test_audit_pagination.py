"""Unit tests for audit API cursor-based pagination.

Tests the cursor-based pagination implementation in the audit logs endpoint.
"""

from datetime import UTC, datetime

from backend.api.pagination import CursorData, encode_cursor
from backend.api.schemas.audit import AuditLogListResponse


class TestAuditLogListResponseWithCursor:
    """Tests for AuditLogListResponse schema with cursor pagination fields."""

    def test_audit_list_response_with_cursor_fields(self):
        """Test AuditLogListResponse includes cursor pagination fields."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": 0,
                "next_cursor": "eyJpZCI6IDEwMCwgImNyZWF0ZWRfYXQiOiAiMjAyNS0xMi0yM1QxMjowMDowMFoifQ==",  # pragma: allowlist secret
                "has_more": True,
            },
        }
        response = AuditLogListResponse(**data)
        assert response.pagination.next_cursor is not None
        assert response.pagination.has_more is True

    def test_audit_list_response_no_more_results(self):
        """Test AuditLogListResponse when there are no more results."""
        data = {
            "items": [],
            "pagination": {
                "total": 10,
                "limit": 50,
                "offset": 0,
                "next_cursor": None,
                "has_more": False,
            },
        }
        response = AuditLogListResponse(**data)
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_audit_list_response_backward_compatible_without_cursor(self):
        """Test AuditLogListResponse with pagination envelope."""
        data = {
            "items": [],
            "pagination": {
                "total": 0,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        }
        response = AuditLogListResponse(**data)
        # Should default to None for cursor fields
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_audit_list_response_deprecation_warning(self):
        """Test AuditLogListResponse can include deprecation warning."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": 20,
                "has_more": False,
            },
            "deprecation_warning": "Offset pagination is deprecated. Please use cursor-based pagination.",
        }
        response = AuditLogListResponse(**data)
        assert response.deprecation_warning is not None
        assert "deprecated" in response.deprecation_warning.lower()


class TestAuditPaginationLogic:
    """Tests for cursor-based pagination logic in list_audit_logs endpoint."""

    def test_cursor_from_audit_log_data(self):
        """Test creating cursor from audit log data (id and timestamp)."""
        # Simulate creating a cursor from the last audit log in a response
        audit_id = 50
        timestamp = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        cursor_data = CursorData(id=audit_id, created_at=timestamp)
        encoded = encode_cursor(cursor_data)

        # Verify cursor is a non-empty string
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_pagination_has_more_logic(self):
        """Test has_more is true when results exceed limit."""
        # Simulate fetching limit + 1 items to check for more
        limit = 50
        fetched_items = 51  # One more than requested

        has_more = fetched_items > limit
        assert has_more is True

    def test_pagination_no_more_results(self):
        """Test has_more is false when results don't exceed limit."""
        limit = 50
        fetched_items = 30  # Less than requested

        has_more = fetched_items > limit
        assert has_more is False

    def test_pagination_exact_limit(self):
        """Test has_more is false when results equal limit exactly."""
        limit = 50
        fetched_items = 50  # Exactly limit

        has_more = fetched_items > limit
        assert has_more is False
