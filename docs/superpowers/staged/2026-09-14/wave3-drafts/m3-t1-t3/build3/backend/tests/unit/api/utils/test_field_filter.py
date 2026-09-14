"""Unit tests for field filtering utility (sparse fieldsets).

Tests for the field_filter module that enables clients to request only
specific fields in API responses, reducing payload size and bandwidth.

TDD Approach: These tests are written FIRST, before the implementation.
"""

import pytest

from backend.api.utils.field_filter import (
    FieldFilterError,
    filter_fields,
    parse_fields_param,
    validate_fields,
)


class TestParseFieldsParam:
    """Tests for parsing the fields query parameter."""

    def test_parse_none_returns_none(self):
        """Test that None input returns None (no filtering)."""
        result = parse_fields_param(None)
        assert result is None

    def test_parse_empty_string_returns_none(self):
        """Test that empty string returns None (no filtering)."""
        result = parse_fields_param("")
        assert result is None

    def test_parse_single_field(self):
        """Test parsing a single field."""
        result = parse_fields_param("id")
        assert result == {"id"}

    def test_parse_multiple_fields(self):
        """Test parsing multiple comma-separated fields."""
        result = parse_fields_param("id,camera_id,risk_level")
        assert result == {"id", "camera_id", "risk_level"}

    def test_parse_fields_with_whitespace(self):
        """Test that whitespace is trimmed from field names."""
        result = parse_fields_param("id , camera_id , risk_level")
        assert result == {"id", "camera_id", "risk_level"}

    def test_parse_fields_ignores_empty_values(self):
        """Test that empty values from double commas are ignored."""
        result = parse_fields_param("id,,camera_id,,,risk_level")
        assert result == {"id", "camera_id", "risk_level"}

    def test_parse_fields_lowercase_normalization(self):
        """Test that field names are normalized to lowercase."""
        result = parse_fields_param("ID,Camera_Id,RISK_LEVEL")
        assert result == {"id", "camera_id", "risk_level"}


class TestValidateFields:
    """Tests for validating requested fields against allowed fields."""

    def test_validate_none_fields_returns_none(self):
        """Test that None requested fields returns None."""
        allowed = {"id", "name", "status"}
        result = validate_fields(None, allowed)
        assert result is None

    def test_validate_all_valid_fields(self):
        """Test validation passes when all fields are valid."""
        allowed = {"id", "name", "status", "created_at"}
        requested = {"id", "name", "status"}
        result = validate_fields(requested, allowed)
        assert result == {"id", "name", "status"}

    def test_validate_raises_for_invalid_field(self):
        """Test that invalid field raises FieldFilterError."""
        allowed = {"id", "name", "status"}
        requested = {"id", "invalid_field", "name"}

        with pytest.raises(FieldFilterError) as exc_info:
            validate_fields(requested, allowed)

        assert "invalid_field" in str(exc_info.value)
        assert exc_info.value.invalid_fields == {"invalid_field"}

    def test_validate_raises_with_multiple_invalid_fields(self):
        """Test that multiple invalid fields are all reported."""
        allowed = {"id", "name"}
        requested = {"id", "invalid1", "invalid2", "name"}

        with pytest.raises(FieldFilterError) as exc_info:
            validate_fields(requested, allowed)

        assert exc_info.value.invalid_fields == {"invalid1", "invalid2"}

    def test_validate_provides_valid_fields_in_error(self):
        """Test that error includes list of valid fields for user guidance."""
        allowed = {"id", "name", "status"}
        requested = {"id", "invalid_field"}

        with pytest.raises(FieldFilterError) as exc_info:
            validate_fields(requested, allowed)

        assert exc_info.value.valid_fields == {"id", "name", "status"}


class TestFilterFields:
    """Tests for filtering dictionary fields."""

    def test_filter_none_returns_original(self):
        """Test that None allowed_fields returns the original data unchanged."""
        data = {"id": 1, "name": "test", "status": "active"}
        result = filter_fields(data, None)
        assert result == data
        assert result is not data  # Should be a copy for safety

    def test_filter_empty_set_returns_empty_dict(self):
        """Test that empty allowed_fields returns empty dict."""
        data = {"id": 1, "name": "test", "status": "active"}
        result = filter_fields(data, set())
        assert result == {}

    def test_filter_single_field(self):
        """Test filtering to a single field."""
        data = {"id": 1, "name": "test", "status": "active", "created_at": "2025-01-01"}
        result = filter_fields(data, {"id"})
        assert result == {"id": 1}

    def test_filter_multiple_fields(self):
        """Test filtering to multiple fields."""
        data = {"id": 1, "name": "test", "status": "active", "created_at": "2025-01-01"}
        result = filter_fields(data, {"id", "name", "status"})
        assert result == {"id": 1, "name": "test", "status": "active"}

    def test_filter_preserves_field_order(self):
        """Test that field ordering from original dict is preserved."""
        data = {"id": 1, "name": "test", "status": "active", "created_at": "2025-01-01"}
        result = filter_fields(data, {"name", "id"})
        # Order should match original dict, not the set
        assert list(result.keys()) == ["id", "name"]

    def test_filter_ignores_missing_fields(self):
        """Test that requested fields not in data are simply not included."""
        data = {"id": 1, "name": "test"}
        result = filter_fields(data, {"id", "name", "nonexistent"})
        assert result == {"id": 1, "name": "test"}

    def test_filter_handles_none_values(self):
        """Test that None values are correctly filtered."""
        data = {"id": 1, "name": None, "status": "active"}
        result = filter_fields(data, {"id", "name"})
        assert result == {"id": 1, "name": None}

    def test_filter_handles_nested_dict(self):
        """Test that nested dictionaries are preserved as-is."""
        data = {
            "id": 1,
            "metadata": {"key": "value", "nested": {"deep": True}},
            "status": "active",
        }
        result = filter_fields(data, {"id", "metadata"})
        assert result == {"id": 1, "metadata": {"key": "value", "nested": {"deep": True}}}

    def test_filter_handles_list_values(self):
        """Test that list values are preserved as-is."""
        data = {"id": 1, "tags": ["tag1", "tag2", "tag3"], "status": "active"}
        result = filter_fields(data, {"id", "tags"})
        assert result == {"id": 1, "tags": ["tag1", "tag2", "tag3"]}


class TestFilterFieldsList:
    """Tests for filtering a list of dictionaries."""

    def test_filter_list_of_dicts(self):
        """Test filtering a list of dictionaries."""
        data = [
            {"id": 1, "name": "item1", "status": "active"},
            {"id": 2, "name": "item2", "status": "inactive"},
        ]
        result = [filter_fields(d, {"id", "name"}) for d in data]
        assert result == [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
        ]

    def test_filter_empty_list(self):
        """Test filtering an empty list returns empty list."""
        data: list[dict] = []
        result = [filter_fields(d, {"id"}) for d in data]
        assert result == []


class TestFieldFilterError:
    """Tests for FieldFilterError exception."""

    def test_error_message_contains_invalid_fields(self):
        """Test that error message lists the invalid fields."""
        error = FieldFilterError(
            invalid_fields={"bad_field", "another_bad"},
            valid_fields={"id", "name"},
        )
        message = str(error)
        assert "bad_field" in message or "another_bad" in message

    def test_error_provides_valid_fields_hint(self):
        """Test that error provides hint about valid fields."""
        error = FieldFilterError(
            invalid_fields={"bad_field"},
            valid_fields={"id", "name", "status"},
        )
        message = str(error)
        # Should mention valid fields for user guidance
        assert "id" in message or "name" in message or "valid" in message.lower()

    def test_error_has_invalid_fields_attribute(self):
        """Test that error has invalid_fields attribute for programmatic access."""
        error = FieldFilterError(
            invalid_fields={"field1", "field2"},
            valid_fields={"id"},
        )
        assert error.invalid_fields == {"field1", "field2"}

    def test_error_has_valid_fields_attribute(self):
        """Test that error has valid_fields attribute for programmatic access."""
        error = FieldFilterError(
            invalid_fields={"bad"},
            valid_fields={"id", "name"},
        )
        assert error.valid_fields == {"id", "name"}
