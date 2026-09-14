"""Unit tests for shared API validators.

Tests for reusable validation functions that can be used across multiple
API endpoints to ensure consistent validation behavior.

Test cases:
- Camera ID format validation
- Risk score range validation
- Date range validation (already tested in test_date_filter_validation.py)
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api.validators import (
    CAMERA_ID_MAX_LENGTH,
    CAMERA_ID_MIN_LENGTH,
    CAMERA_ID_PATTERN,
    RISK_SCORE_MAX,
    RISK_SCORE_MIN,
    validate_camera_id_format,
    validate_risk_score_range,
)


class TestValidateCameraIdFormat:
    """Tests for the validate_camera_id_format function."""

    def test_valid_camera_id_simple(self) -> None:
        """Test that simple alphanumeric camera IDs are valid."""
        # Should not raise any exception
        result = validate_camera_id_format("front_door")
        assert result == "front_door"

    def test_valid_camera_id_with_hyphens(self) -> None:
        """Test that camera IDs with hyphens are valid."""
        result = validate_camera_id_format("front-door-camera")
        assert result == "front-door-camera"

    def test_valid_camera_id_with_underscores(self) -> None:
        """Test that camera IDs with underscores are valid."""
        result = validate_camera_id_format("back_yard_cam")
        assert result == "back_yard_cam"

    def test_valid_camera_id_with_numbers(self) -> None:
        """Test that camera IDs with numbers are valid."""
        result = validate_camera_id_format("camera123")
        assert result == "camera123"

    def test_valid_camera_id_mixed(self) -> None:
        """Test that camera IDs with mixed characters are valid."""
        result = validate_camera_id_format("cam_1-front")
        assert result == "cam_1-front"

    def test_invalid_camera_id_empty(self) -> None:
        """Test that empty camera ID raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format("")

        assert exc_info.value.status_code == 400
        assert "camera_id" in exc_info.value.detail.lower()

    def test_invalid_camera_id_too_short(self) -> None:
        """Test that camera ID shorter than minimum length raises error."""
        # Single character should fail if min_length > 1
        if CAMERA_ID_MIN_LENGTH > 1:
            short_id = "a" * (CAMERA_ID_MIN_LENGTH - 1)
            with pytest.raises(HTTPException) as exc_info:
                validate_camera_id_format(short_id)
            assert exc_info.value.status_code == 400

    def test_invalid_camera_id_too_long(self) -> None:
        """Test that camera ID longer than maximum length raises error."""
        long_id = "a" * (CAMERA_ID_MAX_LENGTH + 1)
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format(long_id)

        assert exc_info.value.status_code == 400
        assert "camera_id" in exc_info.value.detail.lower()

    def test_invalid_camera_id_with_spaces(self) -> None:
        """Test that camera IDs with spaces are invalid."""
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format("front door")

        assert exc_info.value.status_code == 400

    def test_invalid_camera_id_with_special_chars(self) -> None:
        """Test that camera IDs with special characters are invalid."""
        invalid_ids = [
            "camera@123",
            "camera#1",
            "camera$dollar",
            "camera%percent",
            "camera&amp",
            "camera*star",
            "camera/slash",
            "camera\\backslash",
        ]
        for invalid_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                validate_camera_id_format(invalid_id)
            assert exc_info.value.status_code == 400

    def test_invalid_camera_id_path_traversal(self) -> None:
        """Test that camera IDs with path traversal are invalid."""
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format("../etc/passwd")

        assert exc_info.value.status_code == 400

    def test_invalid_camera_id_with_dots(self) -> None:
        """Test that camera IDs with dots are invalid (security)."""
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format("camera.name")

        assert exc_info.value.status_code == 400

    def test_camera_id_none_raises_error(self) -> None:
        """Test that None camera ID raises appropriate error."""
        with pytest.raises((HTTPException, TypeError, ValueError)):
            validate_camera_id_format(None)  # type: ignore

    def test_camera_id_minimum_length(self) -> None:
        """Test that camera ID at minimum length is valid."""
        min_id = "a" * CAMERA_ID_MIN_LENGTH
        result = validate_camera_id_format(min_id)
        assert result == min_id

    def test_camera_id_maximum_length(self) -> None:
        """Test that camera ID at maximum length is valid."""
        max_id = "a" * CAMERA_ID_MAX_LENGTH
        result = validate_camera_id_format(max_id)
        assert result == max_id

    def test_camera_id_pattern_matches_expected(self) -> None:
        """Test that CAMERA_ID_PATTERN constant matches expected pattern."""
        import re

        pattern = re.compile(CAMERA_ID_PATTERN)

        # Valid patterns
        assert pattern.match("front_door")
        assert pattern.match("camera123")
        assert pattern.match("cam-1")

        # Invalid patterns
        assert not pattern.match("camera.name")
        assert not pattern.match("camera@name")
        assert not pattern.match("")


class TestValidateRiskScoreRange:
    """Tests for the validate_risk_score_range function."""

    def test_valid_risk_score_zero(self) -> None:
        """Test that risk score of 0 is valid."""
        result = validate_risk_score_range(0)
        assert result == 0

    def test_valid_risk_score_max(self) -> None:
        """Test that risk score of 100 is valid."""
        result = validate_risk_score_range(100)
        assert result == 100

    def test_valid_risk_score_middle(self) -> None:
        """Test that risk score in middle of range is valid."""
        result = validate_risk_score_range(50)
        assert result == 50

    def test_valid_risk_score_low_threshold(self) -> None:
        """Test risk score at low/medium boundary."""
        result = validate_risk_score_range(29)
        assert result == 29

    def test_valid_risk_score_medium_threshold(self) -> None:
        """Test risk score at medium/high boundary."""
        result = validate_risk_score_range(59)
        assert result == 59

    def test_valid_risk_score_high_threshold(self) -> None:
        """Test risk score at high/critical boundary."""
        result = validate_risk_score_range(84)
        assert result == 84

    def test_invalid_risk_score_negative(self) -> None:
        """Test that negative risk score raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_risk_score_range(-1)

        assert exc_info.value.status_code == 400
        assert "risk_score" in exc_info.value.detail.lower()

    def test_invalid_risk_score_above_max(self) -> None:
        """Test that risk score above 100 raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_risk_score_range(101)

        assert exc_info.value.status_code == 400

    def test_invalid_risk_score_way_above_max(self) -> None:
        """Test that risk score way above max raises error."""
        with pytest.raises(HTTPException) as exc_info:
            validate_risk_score_range(1000)

        assert exc_info.value.status_code == 400

    def test_invalid_risk_score_way_below_min(self) -> None:
        """Test that risk score way below min raises error."""
        with pytest.raises(HTTPException) as exc_info:
            validate_risk_score_range(-100)

        assert exc_info.value.status_code == 400

    def test_risk_score_none_raises_error(self) -> None:
        """Test that None risk score raises appropriate error."""
        with pytest.raises((HTTPException, TypeError, ValueError)):
            validate_risk_score_range(None)  # type: ignore

    def test_risk_score_string_raises_error(self) -> None:
        """Test that string risk score raises appropriate error."""
        with pytest.raises((HTTPException, TypeError, ValueError)):
            validate_risk_score_range("high")  # type: ignore

    def test_risk_score_float_raises_error(self) -> None:
        """Test that float risk score raises error (integer expected)."""
        # Float should be rejected if we want integers only
        with pytest.raises((HTTPException, TypeError, ValueError)):
            validate_risk_score_range(50.5)  # type: ignore

    def test_risk_score_constants_valid(self) -> None:
        """Test that RISK_SCORE_MIN and RISK_SCORE_MAX constants are correct."""
        assert RISK_SCORE_MIN == 0
        assert RISK_SCORE_MAX == 100


class TestValidateCameraIdFormatErrorMessages:
    """Tests for error message quality in camera ID validation."""

    def test_error_message_includes_pattern_info(self) -> None:
        """Test that error message explains valid pattern."""
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format("invalid@id")

        detail = exc_info.value.detail.lower()
        # Should explain what's expected
        assert "alphanumeric" in detail or "pattern" in detail or "format" in detail

    def test_error_message_includes_length_info(self) -> None:
        """Test that error message explains length constraints."""
        long_id = "a" * (CAMERA_ID_MAX_LENGTH + 1)
        with pytest.raises(HTTPException) as exc_info:
            validate_camera_id_format(long_id)

        detail = exc_info.value.detail.lower()
        # Should mention length
        assert "length" in detail or "character" in detail or "long" in detail


class TestValidateRiskScoreRangeErrorMessages:
    """Tests for error message quality in risk score validation."""

    def test_error_message_includes_range_info(self) -> None:
        """Test that error message explains valid range."""
        with pytest.raises(HTTPException) as exc_info:
            validate_risk_score_range(150)

        detail = exc_info.value.detail.lower()
        # Should explain the valid range
        assert "0" in detail or "100" in detail or "range" in detail
