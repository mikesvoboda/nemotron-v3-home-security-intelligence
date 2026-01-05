"""Unit tests for date filter validation.

Tests for validating that start_date is not after end_date in date filter parameters.
This validation is used across multiple API endpoints (events, detections, audit, logs).

Test cases:
- Valid date ranges (start < end)
- Invalid date ranges (start > end)
- Edge case: start == end (should be valid)
- Missing dates (should still work)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from backend.api.validators import validate_date_range


class TestValidateDateRange:
    """Tests for the validate_date_range function."""

    def test_valid_date_range_start_before_end(self) -> None:
        """Test that start_date before end_date is valid."""
        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 31, 23, 59, 59)

        # Should not raise any exception
        validate_date_range(start, end)

    def test_valid_date_range_start_equals_end(self) -> None:
        """Test that start_date equals end_date is valid (edge case)."""
        same_date = datetime(2025, 1, 15, 12, 0, 0)

        # Should not raise any exception
        validate_date_range(same_date, same_date)

    def test_invalid_date_range_start_after_end(self) -> None:
        """Test that start_date after end_date raises HTTPException 400."""
        start = datetime(2025, 1, 31, 23, 59, 59)
        end = datetime(2025, 1, 1, 0, 0, 0)

        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(start, end)

        assert exc_info.value.status_code == 400
        assert "start_date" in exc_info.value.detail.lower()
        assert "end_date" in exc_info.value.detail.lower()

    def test_missing_start_date_is_valid(self) -> None:
        """Test that only end_date provided is valid (start_date is None)."""
        end = datetime(2025, 1, 31, 23, 59, 59)

        # Should not raise any exception
        validate_date_range(None, end)

    def test_missing_end_date_is_valid(self) -> None:
        """Test that only start_date provided is valid (end_date is None)."""
        start = datetime(2025, 1, 1, 0, 0, 0)

        # Should not raise any exception
        validate_date_range(start, None)

    def test_both_dates_missing_is_valid(self) -> None:
        """Test that both dates missing is valid."""
        # Should not raise any exception
        validate_date_range(None, None)

    def test_start_one_second_after_end_is_invalid(self) -> None:
        """Test that start_date even one second after end_date is invalid."""
        end = datetime(2025, 1, 15, 12, 0, 0)
        start = end + timedelta(seconds=1)

        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(start, end)

        assert exc_info.value.status_code == 400

    def test_error_message_is_descriptive(self) -> None:
        """Test that error message clearly explains the validation failure."""
        start = datetime(2025, 12, 31)
        end = datetime(2025, 1, 1)

        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(start, end)

        detail = exc_info.value.detail.lower()
        # Should mention what's wrong
        assert "start_date" in detail or "start" in detail
        assert "end_date" in detail or "end" in detail
        # Should indicate the relationship issue
        assert "after" in detail or "before" in detail or "greater" in detail

    def test_timezone_aware_dates_valid_range(self) -> None:
        """Test validation with timezone-aware datetime objects."""
        from datetime import UTC

        start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC)

        # Should not raise any exception
        validate_date_range(start, end)

    def test_timezone_aware_dates_invalid_range(self) -> None:
        """Test validation with timezone-aware datetime objects (invalid)."""
        from datetime import UTC

        start = datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC)
        end = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(start, end)

        assert exc_info.value.status_code == 400
