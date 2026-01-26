"""Unit tests for settings API schema validation.

Tests for BatchSettingsUpdate cross-field validation.

@see NEM-3873 - Batch Config Validation
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas.settings_api import (
    BatchSettings,
    BatchSettingsUpdate,
    SeveritySettingsUpdate,
)


class TestBatchSettings:
    """Tests for BatchSettings schema."""

    def test_valid_batch_settings(self) -> None:
        """Test that valid batch settings pass validation."""
        settings = BatchSettings(window_seconds=90, idle_timeout_seconds=30)
        assert settings.window_seconds == 90
        assert settings.idle_timeout_seconds == 30

    def test_window_seconds_must_be_positive(self) -> None:
        """Test that window_seconds must be > 0."""
        with pytest.raises(ValidationError) as exc_info:
            BatchSettings(window_seconds=0, idle_timeout_seconds=30)
        assert "window_seconds" in str(exc_info.value)

    def test_idle_timeout_must_be_positive(self) -> None:
        """Test that idle_timeout_seconds must be > 0."""
        with pytest.raises(ValidationError) as exc_info:
            BatchSettings(window_seconds=90, idle_timeout_seconds=0)
        assert "idle_timeout_seconds" in str(exc_info.value)


class TestBatchSettingsUpdate:
    """Tests for BatchSettingsUpdate schema with cross-field validation."""

    def test_valid_update_both_fields(self) -> None:
        """Test that valid update with both fields passes validation."""
        update = BatchSettingsUpdate(window_seconds=90, idle_timeout_seconds=30)
        assert update.window_seconds == 90
        assert update.idle_timeout_seconds == 30

    def test_valid_update_window_only(self) -> None:
        """Test that update with only window_seconds is valid."""
        update = BatchSettingsUpdate(window_seconds=120)
        assert update.window_seconds == 120
        assert update.idle_timeout_seconds is None

    def test_valid_update_idle_only(self) -> None:
        """Test that update with only idle_timeout_seconds is valid."""
        update = BatchSettingsUpdate(idle_timeout_seconds=45)
        assert update.idle_timeout_seconds == 45
        assert update.window_seconds is None

    def test_window_max_constraint(self) -> None:
        """Test that window_seconds cannot exceed 600."""
        with pytest.raises(ValidationError) as exc_info:
            BatchSettingsUpdate(window_seconds=601)
        assert "window_seconds" in str(exc_info.value)

    def test_idle_max_constraint(self) -> None:
        """Test that idle_timeout_seconds cannot exceed 300."""
        with pytest.raises(ValidationError) as exc_info:
            BatchSettingsUpdate(idle_timeout_seconds=301)
        assert "idle_timeout_seconds" in str(exc_info.value)

    def test_cross_field_validation_idle_greater_than_window(self) -> None:
        """Test that idle_timeout >= window_seconds raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BatchSettingsUpdate(window_seconds=60, idle_timeout_seconds=90)
        error_str = str(exc_info.value)
        assert "idle_timeout_seconds" in error_str or "must be less than" in error_str

    def test_cross_field_validation_idle_equal_window(self) -> None:
        """Test that idle_timeout == window_seconds raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BatchSettingsUpdate(window_seconds=60, idle_timeout_seconds=60)
        error_str = str(exc_info.value)
        assert "idle_timeout_seconds" in error_str or "must be less than" in error_str

    def test_cross_field_validation_valid_relationship(self) -> None:
        """Test that idle_timeout < window_seconds passes validation."""
        update = BatchSettingsUpdate(window_seconds=90, idle_timeout_seconds=30)
        assert update.window_seconds == 90
        assert update.idle_timeout_seconds == 30

    def test_cross_field_validation_skipped_when_single_field(self) -> None:
        """Test that cross-field validation is skipped when only one field provided."""
        # These should not raise even though values alone might be edge cases
        update1 = BatchSettingsUpdate(window_seconds=30)
        assert update1.window_seconds == 30

        update2 = BatchSettingsUpdate(idle_timeout_seconds=100)
        assert update2.idle_timeout_seconds == 100

    def test_empty_update_is_valid(self) -> None:
        """Test that empty update (no fields) is valid."""
        update = BatchSettingsUpdate()
        assert update.window_seconds is None
        assert update.idle_timeout_seconds is None


class TestSeveritySettingsUpdateCrossValidation:
    """Tests for SeveritySettingsUpdate cross-field validation (existing)."""

    def test_valid_severity_ordering(self) -> None:
        """Test that properly ordered severity thresholds pass validation."""
        update = SeveritySettingsUpdate(low_max=25, medium_max=50, high_max=75)
        assert update.low_max == 25
        assert update.medium_max == 50
        assert update.high_max == 75

    def test_invalid_low_greater_than_medium(self) -> None:
        """Test that low_max >= medium_max raises validation error."""
        with pytest.raises(ValidationError):
            SeveritySettingsUpdate(low_max=60, medium_max=50)

    def test_invalid_medium_greater_than_high(self) -> None:
        """Test that medium_max >= high_max raises validation error."""
        with pytest.raises(ValidationError):
            SeveritySettingsUpdate(medium_max=80, high_max=75)

    def test_single_field_update_no_validation(self) -> None:
        """Test that single field updates skip cross-field validation."""
        update = SeveritySettingsUpdate(low_max=50)
        assert update.low_max == 50
