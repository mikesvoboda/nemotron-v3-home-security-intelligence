"""Unit tests for cursor-based pagination utilities.

Tests for encoding/decoding cursors and pagination logic following TDD approach.
"""

import base64
import json
from datetime import UTC, datetime

import pytest

from backend.api.pagination import (
    CursorData,
    decode_cursor,
    encode_cursor,
    get_deprecation_warning,
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
        with pytest.raises(ValueError, match="Invalid cursor"):
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
