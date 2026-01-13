"""Unit tests for cursor-based pagination utilities.

Tests for encoding/decoding cursors and pagination logic following TDD approach.
"""

import base64
import json
from datetime import UTC, datetime

import pytest

from backend.api.pagination import (
    CURSOR_FORMAT_REGEX,
    MAX_CURSOR_LENGTH,
    CursorData,
    decode_cursor,
    encode_cursor,
    get_deprecation_warning,
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
