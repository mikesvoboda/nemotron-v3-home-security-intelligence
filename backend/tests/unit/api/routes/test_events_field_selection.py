"""Unit tests for events API field selection (sparse fieldsets).

Tests for the fields query parameter on the list events endpoint that enables
clients to request only specific fields in the response.

TDD Approach: These tests are written FIRST, before the implementation.
"""

from datetime import UTC, datetime
from typing import ClassVar

import pytest


class TestEventsFieldSelectionSchema:
    """Schema-level tests for events field selection behavior."""

    # Define the valid event fields that can be requested
    VALID_EVENT_FIELDS: ClassVar[set[str]] = {
        "id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "reviewed",
        "detection_count",
        "detection_ids",
        "thumbnail_url",
    }

    def test_event_response_fields_documentation(self):
        """Document the fields available in EventResponse for field selection."""
        # This test documents the expected fields for reference
        assert "id" in self.VALID_EVENT_FIELDS
        assert "camera_id" in self.VALID_EVENT_FIELDS
        assert "started_at" in self.VALID_EVENT_FIELDS
        assert "ended_at" in self.VALID_EVENT_FIELDS
        assert "risk_score" in self.VALID_EVENT_FIELDS
        assert "risk_level" in self.VALID_EVENT_FIELDS
        assert "summary" in self.VALID_EVENT_FIELDS
        assert "reasoning" in self.VALID_EVENT_FIELDS
        assert "reviewed" in self.VALID_EVENT_FIELDS
        assert "detection_count" in self.VALID_EVENT_FIELDS
        assert "detection_ids" in self.VALID_EVENT_FIELDS
        assert "thumbnail_url" in self.VALID_EVENT_FIELDS


class TestEventsFieldSelectionLogic:
    """Tests for field selection logic in list_events endpoint."""

    def test_filter_event_dict_single_field(self):
        """Test filtering event dict to single field."""
        from backend.api.utils.field_filter import filter_fields

        event_dict = {
            "id": 1,
            "camera_id": "front_door",
            "started_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "ended_at": datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC),
            "risk_score": 75,
            "risk_level": "medium",
            "summary": "Person detected",
            "reasoning": "Person approaching entrance",
            "reviewed": False,
            "detection_count": 5,
            "detection_ids": [1, 2, 3, 4, 5],
            "thumbnail_url": "/api/media/detections/1",
        }

        result = filter_fields(event_dict, {"id"})
        assert result == {"id": 1}

    def test_filter_event_dict_multiple_fields(self):
        """Test filtering event dict to multiple fields."""
        from backend.api.utils.field_filter import filter_fields

        event_dict = {
            "id": 1,
            "camera_id": "front_door",
            "started_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "ended_at": datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC),
            "risk_score": 75,
            "risk_level": "medium",
            "summary": "Person detected",
            "reasoning": "Person approaching entrance",
            "reviewed": False,
            "detection_count": 5,
            "detection_ids": [1, 2, 3, 4, 5],
            "thumbnail_url": "/api/media/detections/1",
        }

        result = filter_fields(event_dict, {"id", "camera_id", "risk_level", "summary", "reviewed"})
        assert result == {
            "id": 1,
            "camera_id": "front_door",
            "risk_level": "medium",
            "summary": "Person detected",
            "reviewed": False,
        }

    def test_filter_event_dict_preserves_list_fields(self):
        """Test that list fields like detection_ids are preserved."""
        from backend.api.utils.field_filter import filter_fields

        event_dict = {
            "id": 1,
            "detection_ids": [1, 2, 3, 4, 5],
            "detection_count": 5,
        }

        result = filter_fields(event_dict, {"id", "detection_ids"})
        assert result == {
            "id": 1,
            "detection_ids": [1, 2, 3, 4, 5],
        }

    def test_filter_event_dict_handles_none_values(self):
        """Test that None values are correctly preserved when field is selected."""
        from backend.api.utils.field_filter import filter_fields

        event_dict = {
            "id": 1,
            "camera_id": "front_door",
            "ended_at": None,
            "risk_score": None,
            "summary": None,
        }

        result = filter_fields(event_dict, {"id", "ended_at", "summary"})
        assert result == {
            "id": 1,
            "ended_at": None,
            "summary": None,
        }


class TestEventsFieldValidation:
    """Tests for field validation in events endpoint."""

    VALID_EVENT_FIELDS: ClassVar[set[str]] = {
        "id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "reviewed",
        "detection_count",
        "detection_ids",
        "thumbnail_url",
    }

    def test_validate_valid_fields(self):
        """Test validation passes for valid fields."""
        from backend.api.utils.field_filter import validate_fields

        requested = {"id", "camera_id", "risk_level"}
        result = validate_fields(requested, self.VALID_EVENT_FIELDS)
        assert result == {"id", "camera_id", "risk_level"}

    def test_validate_invalid_field_raises_error(self):
        """Test validation raises error for invalid fields."""
        from backend.api.utils.field_filter import FieldFilterError, validate_fields

        requested = {"id", "invalid_field", "camera_id"}

        with pytest.raises(FieldFilterError) as exc_info:
            validate_fields(requested, self.VALID_EVENT_FIELDS)

        assert "invalid_field" in str(exc_info.value)
        assert exc_info.value.invalid_fields == {"invalid_field"}

    def test_validate_all_fields_at_once(self):
        """Test validation with all valid event fields."""
        from backend.api.utils.field_filter import validate_fields

        result = validate_fields(self.VALID_EVENT_FIELDS, self.VALID_EVENT_FIELDS)
        assert result == self.VALID_EVENT_FIELDS


class TestEventsFieldSelectionUsageExample:
    """Example usage tests demonstrating the expected field selection behavior."""

    def test_typical_dashboard_request(self):
        """Test typical dashboard request with minimal fields."""
        from backend.api.utils.field_filter import (
            filter_fields,
            parse_fields_param,
            validate_fields,
        )

        # Dashboard typically needs: id, camera_id, risk_level, summary, reviewed
        fields_param = "id,camera_id,risk_level,summary,reviewed"
        valid_fields = {
            "id",
            "camera_id",
            "started_at",
            "ended_at",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
            "reviewed",
            "detection_count",
            "detection_ids",
            "thumbnail_url",
        }

        # Parse
        requested = parse_fields_param(fields_param)
        assert requested == {"id", "camera_id", "risk_level", "summary", "reviewed"}

        # Validate
        validated = validate_fields(requested, valid_fields)
        assert validated == {"id", "camera_id", "risk_level", "summary", "reviewed"}

        # Apply to event data
        event_dict = {
            "id": 123,
            "camera_id": "front_door",
            "started_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "ended_at": datetime(2025, 12, 23, 12, 5, 0, tzinfo=UTC),
            "risk_score": 75,
            "risk_level": "medium",
            "summary": "Person detected near entrance",
            "reasoning": "Detected person approaching front door during daytime",
            "reviewed": False,
            "detection_count": 5,
            "detection_ids": [1, 2, 3, 4, 5],
            "thumbnail_url": "/api/media/detections/1",
        }

        result = filter_fields(event_dict, validated)
        assert result == {
            "id": 123,
            "camera_id": "front_door",
            "risk_level": "medium",
            "summary": "Person detected near entrance",
            "reviewed": False,
        }

    def test_no_fields_param_returns_all(self):
        """Test that omitting fields param returns all fields."""
        from backend.api.utils.field_filter import filter_fields, parse_fields_param

        fields_param = None
        requested = parse_fields_param(fields_param)
        assert requested is None

        event_dict = {"id": 1, "name": "test", "status": "active"}
        result = filter_fields(event_dict, requested)
        # Should return copy of original (all fields)
        assert result == event_dict
        assert result is not event_dict  # Should be a copy
