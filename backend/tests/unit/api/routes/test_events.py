"""Additional unit tests for events API routes to improve coverage.

This test file provides additional unit tests for backend/api/routes/events.py
focusing on helper functions, edge cases, and error handling that are easy to test
without complex async mocking.
"""

import json
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, status

from backend.api.routes.events import (
    CSV_INJECTION_PREFIXES,
    VALID_EVENT_LIST_FIELDS,
    VALID_SEVERITY_VALUES,
    get_detection_ids_from_event,
    parse_detection_ids,
    parse_severity_filter,
    sanitize_csv_value,
)
from backend.models.event import Event


class TestParseDetectionIdsEdgeCases:
    """Additional edge case tests for parse_detection_ids."""

    def test_parse_detection_ids_json_with_string_numbers(self):
        """Test parsing JSON array with string numbers converts to integers."""
        detection_ids_str = '["1", "2", "3"]'
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3]

    def test_parse_detection_ids_whitespace_only(self):
        """Test parsing whitespace-only string returns empty list."""
        detection_ids_str = "   "
        result = parse_detection_ids(detection_ids_str)
        assert result == []

    def test_parse_detection_ids_csv_with_empty_elements(self):
        """Test CSV parsing handles empty elements correctly."""
        detection_ids_str = "1,,2, ,3"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3]

    def test_parse_detection_ids_single_number_string(self):
        """Test parsing single number string.

        A single number like "42" is valid JSON (number type), but parse_detection_ids
        expects an array, so it returns empty list.
        """
        detection_ids_str = "42"
        result = parse_detection_ids(detection_ids_str)
        # Valid JSON but not a list, returns empty
        assert result == []

    def test_parse_detection_ids_json_empty_array(self):
        """Test parsing empty JSON array returns empty list."""
        detection_ids_str = "[]"
        result = parse_detection_ids(detection_ids_str)
        assert result == []


class TestGetDetectionIdsFromEventEdgeCases:
    """Additional edge case tests for get_detection_ids_from_event.

    Note: Legacy detection_ids column was removed in NEM-1592.
    These tests verify the new behavior using only the detections relationship.
    """

    def test_get_detection_ids_empty_relationship_returns_empty(self):
        """Test that empty relationship returns empty list (no legacy fallback)."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []
        mock_event.detection_ids = None  # Fallback to legacy column returns empty

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_get_detection_ids_none_relationship_returns_empty(self):
        """Test that None/missing relationship returns empty list."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []
        mock_event.detection_ids = None  # Fallback to legacy column returns empty

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_get_detection_ids_uses_relationship(self):
        """Test that detection IDs are extracted from relationship."""
        mock_event = Mock(spec=Event)
        mock_event.detections = [Mock(id=1), Mock(id=2)]
        mock_event.detection_id_list = [1, 2]

        result = get_detection_ids_from_event(mock_event)
        assert result == [1, 2]


class TestParseSeverityFilterEdgeCases:
    """Additional edge case tests for parse_severity_filter."""

    def test_parse_severity_filter_case_insensitive(self):
        """Test that severity parsing is case insensitive."""
        result = parse_severity_filter("HIGH,CriTical,Low")
        assert set(result) == {"high", "critical", "low"}

    def test_parse_severity_filter_with_extra_commas(self):
        """Test parsing handles extra commas gracefully."""
        result = parse_severity_filter("high,,medium,")
        assert set(result) == {"high", "medium"}

    def test_parse_severity_filter_mixed_case_with_spaces(self):
        """Test parsing handles mixed case and spaces."""
        result = parse_severity_filter(" HIGH , Medium , low ")
        assert set(result) == {"high", "medium", "low"}

    def test_parse_severity_filter_all_valid_values(self):
        """Test parsing all valid severity values."""
        result = parse_severity_filter("low,medium,high,critical")
        assert set(result) == VALID_SEVERITY_VALUES

    def test_parse_severity_filter_single_invalid(self):
        """Test that single invalid value raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("invalid")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in exc_info.value.detail.lower()
        assert "valid values are" in exc_info.value.detail.lower()

    def test_parse_severity_filter_multiple_invalid(self):
        """Test that multiple invalid values are all reported."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("invalid1,invalid2")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid1" in exc_info.value.detail
        assert "invalid2" in exc_info.value.detail


class TestSanitizeCsvValueEdgeCases:
    """Additional edge case tests for sanitize_csv_value."""

    def test_sanitize_csv_value_all_injection_prefixes(self):
        """Test all CSV injection prefixes are sanitized."""
        for prefix in CSV_INJECTION_PREFIXES:
            test_value = f"{prefix}malicious_formula"
            result = sanitize_csv_value(test_value)
            assert result.startswith("'")
            assert result == f"'{prefix}malicious_formula"

    def test_sanitize_csv_value_equals_only(self):
        """Test single equals sign is sanitized."""
        result = sanitize_csv_value("=")
        assert result == "'="

    def test_sanitize_csv_value_plus_only(self):
        """Test single plus sign is sanitized."""
        result = sanitize_csv_value("+")
        assert result == "'+"

    def test_sanitize_csv_value_minus_only(self):
        """Test single minus sign is sanitized."""
        result = sanitize_csv_value("-")
        assert result == "'-"

    def test_sanitize_csv_value_at_only(self):
        """Test single at sign is sanitized."""
        result = sanitize_csv_value("@")
        assert result == "'@"

    def test_sanitize_csv_value_tab_only(self):
        """Test single tab is sanitized."""
        result = sanitize_csv_value("\t")
        assert result == "'\t"

    def test_sanitize_csv_value_carriage_return_only(self):
        """Test single carriage return is sanitized."""
        result = sanitize_csv_value("\r")
        assert result == "'\r"

    def test_sanitize_csv_value_injection_in_middle_not_modified(self):
        """Test value with injection character in middle is not modified."""
        result = sanitize_csv_value("test=value")
        assert result == "test=value"

    def test_sanitize_csv_value_already_quoted(self):
        """Test value already starting with quote is not modified (quote is not an injection prefix)."""
        result = sanitize_csv_value("'already quoted")
        assert result == "'already quoted"

    def test_sanitize_csv_value_multiple_lines(self):
        """Test multiline value only checks first character."""
        result = sanitize_csv_value("=formula\nline2")
        assert result == "'=formula\nline2"

    def test_sanitize_csv_value_unicode_safe(self):
        """Test Unicode characters are handled safely."""
        result = sanitize_csv_value("Hello 世界")
        assert result == "Hello 世界"

    def test_sanitize_csv_value_numbers_not_modified(self):
        """Test numeric values are not modified."""
        result = sanitize_csv_value("12345")
        assert result == "12345"

    def test_sanitize_csv_value_spaces_at_start_not_modified(self):
        """Test spaces at start are not modified."""
        result = sanitize_csv_value("  value")
        assert result == "  value"


class TestConstantsAndValidation:
    """Tests for constants and validation values."""

    def test_valid_severity_values_complete(self):
        """Test that VALID_SEVERITY_VALUES contains all expected values."""
        assert frozenset({"low", "medium", "high", "critical"}) == VALID_SEVERITY_VALUES

    def test_valid_event_list_fields_complete(self):
        """Test that VALID_EVENT_LIST_FIELDS contains expected fields.

        Note: detection_ids was removed after NEM-1592 migration to junction table.
        """
        expected_fields = {
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
            "thumbnail_url",
        }
        assert frozenset(expected_fields) == VALID_EVENT_LIST_FIELDS

    def test_csv_injection_prefixes_complete(self):
        """Test that CSV_INJECTION_PREFIXES contains all dangerous characters."""
        expected_prefixes = ("=", "+", "-", "@", "\t", "\r")
        assert expected_prefixes == CSV_INJECTION_PREFIXES


class TestHelperFunctionIntegration:
    """Integration tests for helper function combinations."""

    def test_parse_and_sanitize_detection_ids(self):
        """Test parsing detection IDs and using them works correctly."""
        json_ids = "[1, 2, 3]"
        csv_ids = "1, 2, 3"

        json_result = parse_detection_ids(json_ids)
        csv_result = parse_detection_ids(csv_ids)

        assert json_result == csv_result == [1, 2, 3]

    def test_event_detection_ids_with_empty_detections(self):
        """Test event with empty detection relationship and empty legacy column."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_ids = ""

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_csv_sanitization_comprehensive_injection_vectors(self):
        """Test comprehensive CSV injection attack vectors."""
        attack_vectors = [
            ("=1+1", "'=1+1"),
            ("+1+1", "'+1+1"),
            ("-1+1", "'-1+1"),
            ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
            ("\t=1+1", "'\t=1+1"),
            ("\r\n=1+1", "'\r\n=1+1"),
            ("=cmd|'/c calc'!A1", "'=cmd|'/c calc'!A1"),
        ]

        for attack, expected in attack_vectors:
            result = sanitize_csv_value(attack)
            assert result == expected, f"Failed for attack vector: {attack}"

    def test_parse_severity_validates_against_constants(self):
        """Test that parse_severity_filter validates against VALID_SEVERITY_VALUES."""
        # All valid values should pass
        for value in VALID_SEVERITY_VALUES:
            result = parse_severity_filter(value)
            assert result == [value]

        # Invalid value should raise exception
        with pytest.raises(HTTPException):
            parse_severity_filter("super_critical")


class TestEdgeCaseCombinations:
    """Tests for edge case combinations and boundary conditions."""

    def test_parse_detection_ids_very_large_array(self):
        """Test parsing very large array of detection IDs."""
        large_ids = list(range(1, 1001))  # 1000 IDs
        json_str = json.dumps(large_ids)

        result = parse_detection_ids(json_str)
        assert len(result) == 1000
        assert result == large_ids

    def test_parse_detection_ids_with_zero(self):
        """Test parsing array with zero values."""
        json_str = "[0, 1, 2]"
        result = parse_detection_ids(json_str)
        assert result == [0, 1, 2]

    def test_parse_detection_ids_negative_numbers(self):
        """Test parsing with negative numbers (invalid IDs but should parse)."""
        json_str = "[-1, -2, -3]"
        result = parse_detection_ids(json_str)
        assert result == [-1, -2, -3]

    def test_sanitize_csv_value_very_long_string(self):
        """Test sanitizing very long string doesn't cause issues."""
        long_value = "=" + ("a" * 10000)
        result = sanitize_csv_value(long_value)
        assert result.startswith("'=")
        assert len(result) == 10002  # +2 for the quote

    def test_parse_severity_empty_after_whitespace_strip(self):
        """Test parsing severity with only whitespace entries."""
        result = parse_severity_filter(" , , ")
        assert result == []

    def test_get_detection_ids_with_empty_detections(self):
        """Test get_detection_ids returns empty list when no detections.

        Note: Legacy detection_ids column fallback is used when relationship is empty.
        """
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []
        mock_event.detection_ids = None  # Fallback to legacy column returns empty

        result = get_detection_ids_from_event(mock_event)
        assert result == []
