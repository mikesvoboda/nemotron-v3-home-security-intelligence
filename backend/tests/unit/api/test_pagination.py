"""Unit tests for cursor-based pagination utilities.

Tests for encoding/decoding cursors and pagination logic following TDD approach.
Includes security validation tests for NEM-2602 (cursor injection prevention).
"""

import base64
import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from backend.api.pagination import (
    CURSOR_FORMAT_REGEX,
    MAX_CURSOR_ID,
    MAX_CURSOR_LENGTH,
    CursorData,
    CursorValidationModel,
    decode_cursor,
    encode_cursor,
    get_deprecation_warning,
    set_deprecation_headers,
    validate_cursor_format,
    validate_pagination_params,
)


class TestCursorEncoding:
    """Tests for cursor encoding functionality."""

    def test_encode_cursor_basic(self):
        """Test encoding a basic cursor with id and created_at."""
        cursor_data = CursorData(id=123, created_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC))
        encoded = encode_cursor(cursor_data)

        # Should be a base64-encoded string
        assert isinstance(encoded, str)
        # Should be decodable
        decoded_bytes = base64.urlsafe_b64decode(encoded)
        decoded_json = json.loads(decoded_bytes)
        assert decoded_json["id"] == 123
        assert "created_at" in decoded_json

    def test_encode_cursor_with_large_id(self):
        """Test encoding cursor with large ID."""
        cursor_data = CursorData(
            id=9999999999, created_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        )
        encoded = encode_cursor(cursor_data)

        decoded_bytes = base64.urlsafe_b64decode(encoded)
        decoded_json = json.loads(decoded_bytes)
        assert decoded_json["id"] == 9999999999

    def test_encode_cursor_with_microseconds(self):
        """Test encoding cursor preserves microsecond precision."""
        cursor_data = CursorData(
            id=1, created_at=datetime(2025, 12, 23, 12, 0, 0, 123456, tzinfo=UTC)
        )
        encoded = encode_cursor(cursor_data)

        decoded_bytes = base64.urlsafe_b64decode(encoded)
        decoded_json = json.loads(decoded_bytes)
        assert "123456" in decoded_json["created_at"] or ".123456" in decoded_json["created_at"]


class TestCursorDecoding:
    """Tests for cursor decoding functionality."""

    def test_decode_cursor_basic(self):
        """Test decoding a valid cursor."""
        cursor_data = CursorData(id=456, created_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC))
        encoded = encode_cursor(cursor_data)

        decoded = decode_cursor(encoded)
        assert decoded.id == 456
        assert decoded.created_at.year == 2025
        assert decoded.created_at.month == 12
        assert decoded.created_at.day == 23
        assert decoded.created_at.hour == 14
        assert decoded.created_at.minute == 30

    def test_decode_cursor_invalid_base64(self):
        """Test decoding invalid base64 raises ValueError."""
        # Note: With NEM-2585 format validation, invalid characters are now
        # rejected before base64 decoding. The error message mentions "invalid characters"
        # rather than "Invalid cursor" from base64 decode failure.
        with pytest.raises(ValueError, match="invalid characters"):
            decode_cursor("not-valid-base64!!!")

    def test_decode_cursor_invalid_json(self):
        """Test decoding invalid JSON raises ValueError."""
        # Valid base64 but not JSON
        invalid_cursor = base64.urlsafe_b64encode(b"not json").decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_decode_cursor_missing_id(self):
        """Test decoding cursor missing id field raises ValueError."""
        cursor_json = json.dumps({"created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_decode_cursor_missing_created_at(self):
        """Test decoding cursor missing created_at field raises ValueError."""
        cursor_json = json.dumps({"id": 123})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_decode_cursor_invalid_datetime_format(self):
        """Test decoding cursor with invalid datetime format raises ValueError."""
        cursor_json = json.dumps({"id": 123, "created_at": "invalid-date"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_decode_cursor_none(self):
        """Test decoding None returns None."""
        assert decode_cursor(None) is None

    def test_decode_cursor_empty_string(self):
        """Test decoding empty string returns None."""
        assert decode_cursor("") is None


class TestCursorRoundTrip:
    """Tests for cursor encode/decode round-trip."""

    def test_round_trip_preserves_data(self):
        """Test that encoding then decoding preserves cursor data."""
        original = CursorData(id=789, created_at=datetime(2025, 6, 15, 8, 45, 30, tzinfo=UTC))
        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded.id == original.id
        # Compare without microseconds since JSON encoding might lose precision
        assert decoded.created_at.replace(microsecond=0) == original.created_at.replace(
            microsecond=0
        )

    def test_round_trip_multiple_cursors(self):
        """Test round-trip with multiple different cursors."""
        test_cases = [
            CursorData(id=1, created_at=datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)),
            CursorData(id=999999, created_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)),
            CursorData(id=42, created_at=datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)),
        ]

        for original in test_cases:
            encoded = encode_cursor(original)
            decoded = decode_cursor(encoded)
            assert decoded.id == original.id


class TestDeprecationWarning:
    """Tests for offset pagination deprecation warning."""

    def test_deprecation_warning_with_offset(self):
        """Test deprecation warning is returned when offset is provided without cursor."""
        warning = get_deprecation_warning(cursor=None, offset=10)
        assert warning is not None
        assert "deprecated" in warning.lower()
        assert "cursor" in warning.lower()

    def test_no_warning_with_cursor(self):
        """Test no warning when cursor is provided."""
        warning = get_deprecation_warning(cursor="some_cursor", offset=0)
        assert warning is None

    def test_no_warning_with_zero_offset_no_cursor(self):
        """Test no warning when offset is 0 (default) and no cursor."""
        warning = get_deprecation_warning(cursor=None, offset=0)
        assert warning is None

    def test_no_warning_with_cursor_and_offset(self):
        """Test cursor takes precedence, no warning even if offset provided."""
        warning = get_deprecation_warning(cursor="some_cursor", offset=10)
        assert warning is None


class TestSetDeprecationHeaders:
    """Tests for HTTP Deprecation header setting (NEM-2603)."""

    def test_sets_deprecation_header_with_offset(self):
        """Test Deprecation header is set when offset pagination is used."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.headers = {}

        set_deprecation_headers(mock_response, cursor=None, offset=10)

        assert mock_response.headers["Deprecation"] == "true"

    def test_sets_sunset_header_with_default_date(self):
        """Test Sunset header is set with default date."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.headers = {}

        set_deprecation_headers(mock_response, cursor=None, offset=10)

        assert mock_response.headers["Sunset"] == "2026-06-01"

    def test_sets_custom_sunset_date(self):
        """Test Sunset header can use custom date."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.headers = {}

        set_deprecation_headers(mock_response, cursor=None, offset=10, sunset_date="2027-01-01")

        assert mock_response.headers["Sunset"] == "2027-01-01"

    def test_no_sunset_header_when_none(self):
        """Test Sunset header is not set when sunset_date is None."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.headers = {}

        set_deprecation_headers(mock_response, cursor=None, offset=10, sunset_date=None)

        assert mock_response.headers["Deprecation"] == "true"
        assert "Sunset" not in mock_response.headers

    def test_no_headers_with_cursor(self):
        """Test no headers are set when cursor is provided."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.headers = {}

        set_deprecation_headers(mock_response, cursor="some_cursor", offset=10)

        assert "Deprecation" not in mock_response.headers
        assert "Sunset" not in mock_response.headers

    def test_no_headers_with_zero_offset(self):
        """Test no headers are set when offset is 0."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.headers = {}

        set_deprecation_headers(mock_response, cursor=None, offset=0)

        assert "Deprecation" not in mock_response.headers
        assert "Sunset" not in mock_response.headers


class TestCursorDataModel:
    """Tests for CursorData dataclass/model."""

    def test_cursor_data_creation(self):
        """Test CursorData can be created with required fields."""
        data = CursorData(id=1, created_at=datetime(2025, 1, 1, tzinfo=UTC))
        assert data.id == 1
        assert data.created_at.year == 2025

    def test_cursor_data_from_dict(self):
        """Test CursorData can be created from dictionary."""
        d = {"id": 100, "created_at": datetime(2025, 6, 15, tzinfo=UTC)}
        data = CursorData(**d)
        assert data.id == 100
<<<<<<< HEAD

    def test_cursor_data_with_direction(self):
        """Test CursorData can be created with optional direction field."""
        data = CursorData(id=1, created_at=datetime(2025, 1, 1, tzinfo=UTC), direction="forward")
        assert data.direction == "forward"


class TestValidatePaginationParams:
    """Tests for pagination parameter validation (NEM-2613).

    Ensures that simultaneous offset and cursor pagination is rejected.
    """

    def test_validation_raises_when_both_offset_and_cursor_provided(self):
        """Test that providing both non-zero offset and cursor raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_pagination_params(cursor="some_cursor", offset=10)
        assert "Cannot use both 'offset' and 'cursor' pagination" in str(exc_info.value)

    def test_validation_raises_for_any_positive_offset_with_cursor(self):
        """Test that any positive offset with cursor raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_pagination_params(cursor="abc123", offset=1)
        assert "Cannot use both 'offset' and 'cursor' pagination" in str(exc_info.value)

    def test_validation_allows_cursor_only(self):
        """Test that cursor-only pagination is allowed."""
        # Should not raise
        validate_pagination_params(cursor="some_cursor", offset=None)
        validate_pagination_params(cursor="some_cursor", offset=0)

    def test_validation_allows_offset_only(self):
        """Test that offset-only pagination is allowed."""
        # Should not raise
        validate_pagination_params(cursor=None, offset=10)
        validate_pagination_params(cursor=None, offset=100)

    def test_validation_allows_no_pagination_params(self):
        """Test that no pagination params is allowed (defaults)."""
        # Should not raise
        validate_pagination_params(cursor=None, offset=None)
        validate_pagination_params(cursor=None, offset=0)

    def test_validation_allows_zero_offset_with_cursor(self):
        """Test that zero offset with cursor is allowed (default offset value)."""
        # Should not raise - offset=0 is the default value
        validate_pagination_params(cursor="some_cursor", offset=0)

    def test_validation_error_message_is_clear(self):
        """Test that the error message clearly explains the conflict."""
        with pytest.raises(ValueError) as exc_info:
            validate_pagination_params(cursor="cursor123", offset=50)
        error_message = str(exc_info.value)
        assert "offset" in error_message.lower()
        assert "cursor" in error_message.lower()
        assert "Choose one" in error_message


class TestValidateCursorFormat:
    """Tests for cursor format validation (NEM-2585).

    Validates that cursors conform to base64url encoding format
    and don't exceed maximum length limits.
    """

    def test_validates_none_cursor(self):
        """Test that None cursor is valid (no cursor provided)."""
        assert validate_cursor_format(None) is True

    def test_validates_empty_string_cursor(self):
        """Test that empty string cursor is valid."""
        assert validate_cursor_format("") is True

    def test_validates_valid_base64url_cursor(self):
        """Test that valid base64url cursor passes validation."""
        # Create a real cursor from CursorData
        cursor_data = CursorData(id=123, created_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC))
        encoded = encode_cursor(cursor_data)
        assert validate_cursor_format(encoded) is True

    def test_validates_alphanumeric_cursor(self):
        """Test that alphanumeric cursors are valid."""
        assert validate_cursor_format("abc123XYZ") is True
        assert validate_cursor_format("eyJpZCI6MTIzfQ") is True

    def test_validates_cursor_with_underscores(self):
        """Test that cursors with underscores are valid (base64url)."""
        assert validate_cursor_format("abc_def_123") is True

    def test_validates_cursor_with_hyphens(self):
        """Test that cursors with hyphens are valid (base64url)."""
        assert validate_cursor_format("abc-def-123") is True

    def test_validates_cursor_with_equals_padding(self):
        """Test that cursors with equals padding are valid."""
        assert validate_cursor_format("eyJpZCI6MTIzfQ==") is True
        assert validate_cursor_format("YWJj=") is True

    def test_rejects_cursor_with_invalid_characters(self):
        """Test that cursors with invalid characters are rejected."""
        invalid_cursors = [
            "<script>alert('xss')</script>",  # XSS attempt
            "SELECT * FROM users",  # SQL injection attempt
            "abc def",  # Space
            "abc\tdef",  # Tab
            "abc\ndef",  # Newline
            "abc;def",  # Semicolon
            "abc&def",  # Ampersand
            "abc?def",  # Question mark
            "abc/def",  # Forward slash (not in base64url)
            "abc+def",  # Plus (standard base64, not base64url)
            "abc!def",  # Exclamation
            'abc"def',  # Quote
            "abc'def",  # Single quote
            "abc<def",  # Less than
            "abc>def",  # Greater than
            "abc{def}",  # Braces
            "abc[def]",  # Brackets
            "abc|def",  # Pipe
            "abc\\def",  # Backslash
            "abc`def",  # Backtick
        ]

        for invalid_cursor in invalid_cursors:
            with pytest.raises(ValueError, match="invalid characters"):
                validate_cursor_format(invalid_cursor)

    def test_rejects_cursor_exceeding_max_length(self):
        """Test that cursors exceeding max length are rejected."""
        long_cursor = "a" * (MAX_CURSOR_LENGTH + 1)
        with pytest.raises(ValueError, match="maximum length"):
            validate_cursor_format(long_cursor)

    def test_accepts_cursor_at_max_length(self):
        """Test that cursor at exactly max length is accepted."""
        max_length_cursor = "a" * MAX_CURSOR_LENGTH
        assert validate_cursor_format(max_length_cursor) is True

    def test_max_cursor_length_constant(self):
        """Test that MAX_CURSOR_LENGTH is a reasonable value."""
        # Should be large enough for normal cursors but not unbounded
        assert MAX_CURSOR_LENGTH >= 100  # Minimum for any real cursor
        assert MAX_CURSOR_LENGTH <= 1000  # Reasonable upper bound

    def test_cursor_format_regex_pattern(self):
        """Test that CURSOR_FORMAT_REGEX correctly identifies valid patterns."""
        # Valid patterns
        assert CURSOR_FORMAT_REGEX.match("abc123")
        assert CURSOR_FORMAT_REGEX.match("ABC123")
        assert CURSOR_FORMAT_REGEX.match("abc_123")
        assert CURSOR_FORMAT_REGEX.match("abc-123")
        assert CURSOR_FORMAT_REGEX.match("abc=123")
        assert CURSOR_FORMAT_REGEX.match("abc123==")

        # Invalid patterns
        assert not CURSOR_FORMAT_REGEX.match("abc 123")  # Space
        assert not CURSOR_FORMAT_REGEX.match("abc<123")  # Less than
        assert not CURSOR_FORMAT_REGEX.match("")  # Empty (handled separately)

    def test_decode_cursor_validates_format_first(self):
        """Test that decode_cursor validates format before attempting decode."""
        # Invalid format should raise ValueError mentioning format
        with pytest.raises(ValueError, match="invalid characters"):
            decode_cursor("<script>alert('xss')</script>")

    def test_decode_cursor_validates_length_first(self):
        """Test that decode_cursor validates length before attempting decode."""
        long_cursor = "a" * (MAX_CURSOR_LENGTH + 1)
        with pytest.raises(ValueError, match="maximum length"):
            decode_cursor(long_cursor)

    def test_integration_valid_cursor_round_trip(self):
        """Test that valid cursors pass format validation and decode correctly."""
        # Create cursor
        cursor_data = CursorData(id=999, created_at=datetime(2025, 6, 15, 8, 30, 0, tzinfo=UTC))
        encoded = encode_cursor(cursor_data)

        # Validate format
        assert validate_cursor_format(encoded) is True

        # Decode and verify
        decoded = decode_cursor(encoded)
        assert decoded is not None
        assert decoded.id == 999


class TestCursorSecurityValidation:
    """Security validation tests for cursor injection prevention (NEM-2602).

    These tests verify that the cursor decoding function properly validates
    input to prevent injection attacks and resource exhaustion.
    """

    def test_cursor_length_limit_enforced(self):
        """Test that cursors exceeding max length are rejected."""
        # Create an oversized cursor
        oversized_cursor = "A" * (MAX_CURSOR_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            decode_cursor(oversized_cursor)

    def test_cursor_at_max_length_accepted(self):
        """Test that cursors at exactly max length are processed (may fail for other reasons)."""
        # A cursor at max length should be processed (validation continues)
        max_length_cursor = "A" * MAX_CURSOR_LENGTH
        with pytest.raises(ValueError, match="Invalid cursor"):
            # Will fail for being invalid base64/JSON, but length check passes
            decode_cursor(max_length_cursor)

    def test_negative_id_rejected(self):
        """Test that negative IDs are rejected."""
        cursor_json = json.dumps({"id": -1, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_zero_id_rejected(self):
        """Test that zero ID is rejected."""
        cursor_json = json.dumps({"id": 0, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_excessively_large_id_rejected(self):
        """Test that IDs exceeding PostgreSQL bigint max are rejected."""
        # MAX_CURSOR_ID is 2^63 - 1 (PostgreSQL bigint max)
        cursor_json = json.dumps({"id": MAX_CURSOR_ID + 1, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_valid_large_id_accepted(self):
        """Test that valid large IDs within bounds are accepted."""
        cursor_json = json.dumps({"id": MAX_CURSOR_ID - 1, "created_at": "2025-12-23T12:00:00Z"})
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        result = decode_cursor(valid_cursor)
        assert result.id == MAX_CURSOR_ID - 1

    def test_string_id_rejected(self):
        """Test that string IDs are rejected (type injection)."""
        cursor_json = json.dumps(
            {"id": "123; DROP TABLE events;", "created_at": "2025-12-23T12:00:00Z"}
        )
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_float_id_rejected(self):
        """Test that float IDs are rejected."""
        cursor_json = json.dumps({"id": 123.456, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_datetime_before_minimum_bound_rejected(self):
        """Test that datetimes before 2020 are rejected."""
        cursor_json = json.dumps({"id": 123, "created_at": "2019-12-31T23:59:59Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="datetime before"):
            decode_cursor(invalid_cursor)

    def test_datetime_after_maximum_bound_rejected(self):
        """Test that datetimes after 2100 are rejected."""
        cursor_json = json.dumps({"id": 123, "created_at": "2100-01-02T00:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="datetime after"):
            decode_cursor(invalid_cursor)

    def test_valid_datetime_at_minimum_bound_accepted(self):
        """Test that datetime at minimum bound is accepted."""
        cursor_json = json.dumps({"id": 123, "created_at": "2020-01-01T00:00:00Z"})
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        result = decode_cursor(valid_cursor)
        assert result.created_at.year == 2020

    def test_valid_datetime_near_maximum_bound_accepted(self):
        """Test that datetime near maximum bound is accepted."""
        cursor_json = json.dumps({"id": 123, "created_at": "2099-12-31T23:59:59Z"})
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        result = decode_cursor(valid_cursor)
        assert result.created_at.year == 2099

    def test_invalid_direction_rejected(self):
        """Test that invalid direction values are rejected."""
        cursor_json = json.dumps(
            {"id": 123, "created_at": "2025-12-23T12:00:00Z", "direction": "sideways"}
        )
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_valid_forward_direction_accepted(self):
        """Test that 'forward' direction is accepted."""
        cursor_json = json.dumps(
            {"id": 123, "created_at": "2025-12-23T12:00:00Z", "direction": "forward"}
        )
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        result = decode_cursor(valid_cursor)
        assert result.direction == "forward"

    def test_valid_backward_direction_accepted(self):
        """Test that 'backward' direction is accepted."""
        cursor_json = json.dumps(
            {"id": 123, "created_at": "2025-12-23T12:00:00Z", "direction": "backward"}
        )
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        result = decode_cursor(valid_cursor)
        assert result.direction == "backward"

    def test_null_direction_accepted(self):
        """Test that null/missing direction is accepted."""
        cursor_json = json.dumps({"id": 123, "created_at": "2025-12-23T12:00:00Z"})
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        result = decode_cursor(valid_cursor)
        assert result.direction is None

    def test_array_payload_rejected(self):
        """Test that array payloads are rejected (expecting dict)."""
        cursor_json = json.dumps([123, "2025-12-23T12:00:00Z"])
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="unexpected data format"):
            decode_cursor(invalid_cursor)

    def test_string_payload_rejected(self):
        """Test that string payloads are rejected (expecting dict)."""
        cursor_json = json.dumps("just a string")
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="unexpected data format"):
            decode_cursor(invalid_cursor)

    def test_sql_injection_in_created_at_rejected(self):
        """Test that SQL injection attempts in created_at are rejected."""
        cursor_json = json.dumps({"id": 123, "created_at": "2025-12-23'; DROP TABLE events; --"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_oversized_created_at_string_rejected(self):
        """Test that excessively long created_at strings are rejected."""
        # Attempt to pass a very long string that might cause issues
        long_datetime = "2025-12-23T12:00:00Z" + "X" * 100
        cursor_json = json.dumps({"id": 123, "created_at": long_datetime})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)


class TestCursorSecurityLogging:
    """Tests for security event logging during cursor validation (NEM-2602)."""

    def test_oversized_cursor_logs_security_event(self):
        """Test that oversized cursors trigger security logging."""
        oversized_cursor = "A" * (MAX_CURSOR_LENGTH + 1)
        with patch("backend.api.pagination.logger") as mock_logger:
            with pytest.raises(ValueError):
                decode_cursor(oversized_cursor)
            # Verify warning was logged with security event details
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[1]["extra"]["security_event"] == "cursor_validation_failure"
            assert "exceeds maximum length" in call_args[1]["extra"]["reason"]

    def test_invalid_base64_logs_security_event(self):
        """Test that invalid base64 characters trigger security logging."""
        # Note: "not-valid-base64!!!" contains invalid base64url characters (!)
        # and is rejected at the format validation stage (NEM-2585)
        with patch("backend.api.pagination.logger") as mock_logger:
            with pytest.raises(ValueError):
                decode_cursor("not-valid-base64!!!")
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[1]["extra"]["security_event"] == "cursor_validation_failure"
            # Fails at format validation due to invalid characters
            assert "invalid characters" in call_args[1]["extra"]["reason"].lower()

    def test_invalid_json_logs_security_event(self):
        """Test that invalid JSON triggers security logging."""
        invalid_cursor = base64.urlsafe_b64encode(b"not json").decode()
        with patch("backend.api.pagination.logger") as mock_logger:
            with pytest.raises(ValueError):
                decode_cursor(invalid_cursor)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[1]["extra"]["security_event"] == "cursor_validation_failure"
            assert "JSON" in call_args[1]["extra"]["reason"]

    def test_out_of_bounds_datetime_logs_security_event(self):
        """Test that out-of-bounds datetime triggers security logging."""
        cursor_json = json.dumps({"id": 123, "created_at": "2019-01-01T00:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with patch("backend.api.pagination.logger") as mock_logger:
            with pytest.raises(ValueError):
                decode_cursor(invalid_cursor)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[1]["extra"]["security_event"] == "cursor_validation_failure"
            assert "minimum bound" in call_args[1]["extra"]["reason"]

    def test_cursor_preview_truncated_in_log(self):
        """Test that long cursors are truncated in log output."""
        # Create a cursor that's longer than 100 chars but under max length
        long_payload = {"id": 123, "created_at": "invalid" * 20}
        cursor_json = json.dumps(long_payload)
        long_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()

        with patch("backend.api.pagination.logger") as mock_logger:
            with pytest.raises(ValueError):
                decode_cursor(long_cursor)
            call_args = mock_logger.warning.call_args
            cursor_preview = call_args[1]["extra"]["cursor_preview"]
            # Preview should be truncated if cursor is long
            if len(long_cursor) > 100:
                assert len(cursor_preview) <= 103  # 100 chars + "..."


class TestCursorValidationModel:
    """Tests for the Pydantic CursorValidationModel (NEM-2602)."""

    def test_valid_model_creation(self):
        """Test that valid data creates a model successfully."""
        model = CursorValidationModel(
            id=123,
            created_at="2025-12-23T12:00:00Z",
            direction="forward",
        )
        assert model.id == 123
        assert model.created_at == "2025-12-23T12:00:00Z"
        assert model.direction == "forward"

    def test_model_rejects_negative_id(self):
        """Test that model rejects negative ID."""
        with pytest.raises(Exception):  # Pydantic validation error
            CursorValidationModel(id=-1, created_at="2025-12-23T12:00:00Z")

    def test_model_rejects_zero_id(self):
        """Test that model rejects zero ID."""
        with pytest.raises(Exception):
            CursorValidationModel(id=0, created_at="2025-12-23T12:00:00Z")

    def test_model_rejects_oversized_id(self):
        """Test that model rejects ID exceeding max."""
        with pytest.raises(Exception):
            CursorValidationModel(id=MAX_CURSOR_ID + 1, created_at="2025-12-23T12:00:00Z")

    def test_model_accepts_max_id(self):
        """Test that model accepts ID at max boundary."""
        model = CursorValidationModel(id=MAX_CURSOR_ID, created_at="2025-12-23T12:00:00Z")
        assert model.id == MAX_CURSOR_ID

    def test_model_rejects_invalid_direction(self):
        """Test that model rejects invalid direction."""
        with pytest.raises(Exception):
            CursorValidationModel(id=123, created_at="2025-12-23T12:00:00Z", direction="invalid")

    def test_model_accepts_none_direction(self):
        """Test that model accepts None direction."""
        model = CursorValidationModel(id=123, created_at="2025-12-23T12:00:00Z")
        assert model.direction is None

    def test_model_rejects_oversized_created_at(self):
        """Test that model rejects excessively long created_at."""
        with pytest.raises(Exception):
            CursorValidationModel(id=123, created_at="X" * 100)


class TestCursorMaliciousInputs:
    """Tests for handling various malicious input patterns (NEM-2602)."""

    def test_null_bytes_in_cursor_rejected(self):
        """Test that null bytes in cursor are handled safely."""
        cursor_with_null = base64.urlsafe_b64encode(
            b'{"id": 123\x00, "created_at": "2025-01-01"}'
        ).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(cursor_with_null)

    def test_unicode_injection_in_id_rejected(self):
        """Test that unicode tricks in ID field are rejected."""
        # Unicode fraction 1/2 shouldn't be accepted as ID
        cursor_json = '{"id": "\u00bd", "created_at": "2025-12-23T12:00:00Z"}'
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_nested_json_injection_rejected(self):
        """Test that nested JSON objects in id field are rejected."""
        cursor_json = json.dumps({"id": {"$gt": 0}, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_prototype_pollution_attempt_rejected(self):
        """Test that __proto__ fields don't cause issues."""
        cursor_json = json.dumps(
            {
                "id": 123,
                "created_at": "2025-12-23T12:00:00Z",
                "__proto__": {"admin": True},
            }
        )
        # This should either succeed (ignoring __proto__) or fail safely
        valid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        # Should not raise - extra fields are ignored
        result = decode_cursor(valid_cursor)
        assert result.id == 123

    def test_exponential_notation_id_rejected(self):
        """Test that scientific notation IDs with decimals are handled."""
        # 1e10 in JSON becomes float 10000000000.0, which gets truncated to int
        # Test with a fractional value that clearly shows float behavior
        cursor_json = json.dumps({"id": 1.5e2, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        # 1.5e2 is 150.0 (a float), should be rejected
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_boolean_id_rejected(self):
        """Test that boolean IDs are rejected."""
        cursor_json = json.dumps({"id": True, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_null_id_rejected(self):
        """Test that null IDs are rejected."""
        cursor_json = json.dumps({"id": None, "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_empty_string_id_rejected(self):
        """Test that empty string IDs are rejected."""
        cursor_json = json.dumps({"id": "", "created_at": "2025-12-23T12:00:00Z"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_infinity_value_rejected(self):
        """Test that infinity values are rejected."""
        # JSON doesn't have infinity, but we test edge cases
        cursor_json = (
            '{"id": 9999999999999999999999999999999999999999, "created_at": "2025-12-23T12:00:00Z"}'
        )
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)

    def test_special_characters_in_datetime_rejected(self):
        """Test that special characters in datetime are rejected."""
        cursor_json = json.dumps({"id": 123, "created_at": "2025-12-23T12:00:00Z<script>"})
        invalid_cursor = base64.urlsafe_b64encode(cursor_json.encode()).decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(invalid_cursor)
