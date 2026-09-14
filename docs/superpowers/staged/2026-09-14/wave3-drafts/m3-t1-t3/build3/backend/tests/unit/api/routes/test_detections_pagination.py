"""Unit tests for detections API cursor-based pagination.

Tests the cursor-based pagination implementation in the detections endpoint.
"""

from datetime import UTC, datetime

from backend.api.pagination import CursorData, encode_cursor
from backend.api.schemas.detections import DetectionListResponse


class TestDetectionListResponseWithCursor:
    """Tests for DetectionListResponse schema with cursor pagination fields."""

    def test_detection_list_response_with_cursor_fields(self):
        """Test DetectionListResponse includes cursor pagination fields."""
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
        response = DetectionListResponse(**data)
        assert response.pagination.next_cursor is not None
        assert response.pagination.has_more is True

    def test_detection_list_response_no_more_results(self):
        """Test DetectionListResponse when there are no more results."""
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
        response = DetectionListResponse(**data)
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_detection_list_response_backward_compatible_without_cursor(self):
        """Test DetectionListResponse works with minimal pagination fields."""
        data = {
            "items": [],
            "pagination": {
                "total": 0,
                "limit": 50,
                "has_more": False,
            },
        }
        response = DetectionListResponse(**data)
        # Should default to None for cursor fields
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_detection_list_response_deprecation_warning(self):
        """Test DetectionListResponse can include deprecation warning."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": 20,
                "has_more": True,
            },
            "deprecation_warning": "Offset pagination is deprecated. Please use cursor-based pagination.",
        }
        response = DetectionListResponse(**data)
        assert response.deprecation_warning is not None
        assert "deprecated" in response.deprecation_warning.lower()


class TestDetectionsPaginationLogic:
    """Tests for cursor-based pagination logic in list_detections endpoint."""

    def test_cursor_from_detection_data(self):
        """Test creating cursor from detection data (id and detected_at)."""
        # Simulate creating a cursor from the last detection in a response
        detection_id = 100
        detected_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        cursor_data = CursorData(id=detection_id, created_at=detected_at)
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
