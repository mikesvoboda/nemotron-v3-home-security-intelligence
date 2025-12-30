"""Unit tests for alert deduplication helper functions and dataclasses.

These tests do not require database access and test pure functions/dataclasses.
"""

import pytest

from backend.services.alert_dedup import (
    MAX_DEDUP_KEY_LENGTH,
    DedupResult,
    build_dedup_key,
    validate_dedup_key,
)


class TestBuildDedupKey:
    """Tests for the build_dedup_key helper function."""

    def test_build_dedup_key_camera_only(self):
        """Test building dedup key with camera ID only."""
        key = build_dedup_key("front_door")
        assert key == "front_door"

    def test_build_dedup_key_camera_and_object(self):
        """Test building dedup key with camera and object type."""
        key = build_dedup_key("front_door", object_type="person")
        assert key == "front_door:person"

    def test_build_dedup_key_all_components(self):
        """Test building dedup key with all components."""
        key = build_dedup_key("front_door", object_type="person", zone="entry_zone")
        assert key == "front_door:person:entry_zone"

    def test_build_dedup_key_camera_and_zone(self):
        """Test building dedup key with camera and zone (no object type)."""
        key = build_dedup_key("front_door", zone="entry_zone")
        assert key == "front_door:entry_zone"

    def test_build_dedup_key_empty_strings(self):
        """Test that empty strings are treated as None."""
        # Empty strings should be falsy and excluded
        key = build_dedup_key("front_door", object_type="", zone="")
        assert key == "front_door"


class TestDedupResult:
    """Tests for the DedupResult dataclass."""

    def test_dedup_result_not_duplicate(self):
        """Test DedupResult when not a duplicate."""
        result = DedupResult(is_duplicate=False)
        assert result.is_duplicate is False
        assert result.existing_alert is None
        assert result.existing_alert_id is None
        assert result.seconds_until_cooldown_expires is None

    def test_dedup_result_is_duplicate(self):
        """Test DedupResult when it is a duplicate."""

        # Create a mock alert-like object
        class MockAlert:
            id = "test-alert-123"

        result = DedupResult(
            is_duplicate=True,
            existing_alert=MockAlert(),
            seconds_until_cooldown_expires=180,
        )
        assert result.is_duplicate is True
        assert result.existing_alert_id == "test-alert-123"
        assert result.seconds_until_cooldown_expires == 180


class TestValidateDedupKey:
    """Tests for the validate_dedup_key function."""

    def test_valid_simple_key(self):
        """Test validation of a simple valid key."""
        key = validate_dedup_key("front_door")
        assert key == "front_door"

    def test_valid_key_with_colon(self):
        """Test validation of key with colons."""
        key = validate_dedup_key("front_door:person:zone1")
        assert key == "front_door:person:zone1"

    def test_valid_key_with_hyphen(self):
        """Test validation of key with hyphens."""
        key = validate_dedup_key("front-door-camera")
        assert key == "front-door-camera"

    def test_valid_key_with_dot(self):
        """Test validation of key with dots."""
        key = validate_dedup_key("camera.front.door")
        assert key == "camera.front.door"

    def test_valid_key_with_numbers(self):
        """Test validation of key with numbers."""
        key = validate_dedup_key("camera123:zone456")
        assert key == "camera123:zone456"

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        key = validate_dedup_key("  front_door  ")
        assert key == "front_door"

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_dedup_key("")

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_dedup_key("   ")

    def test_none_raises_error(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="cannot be None"):
            validate_dedup_key(None)

    def test_exceeds_max_length_raises_error(self):
        """Test that key exceeding max length raises ValueError."""
        long_key = "a" * (MAX_DEDUP_KEY_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_dedup_key(long_key)

    def test_max_length_is_valid(self):
        """Test that key at max length is valid."""
        max_key = "a" * MAX_DEDUP_KEY_LENGTH
        key = validate_dedup_key(max_key)
        assert key == max_key

    def test_invalid_character_space_raises_error(self):
        """Test that space in key raises ValueError."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_dedup_key("front door")

    def test_invalid_character_special_raises_error(self):
        """Test that special characters raise ValueError."""
        invalid_chars = ["@", "#", "$", "%", "^", "&", "*", "(", ")", "!", "?", "/", "\\"]
        for char in invalid_chars:
            with pytest.raises(ValueError, match="invalid characters"):
                validate_dedup_key(f"front{char}door")

    def test_invalid_character_newline_raises_error(self):
        """Test that newline raises ValueError."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_dedup_key("front\ndoor")

    def test_invalid_character_tab_raises_error(self):
        """Test that tab raises ValueError."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_dedup_key("front\tdoor")

    def test_sql_injection_attempt_rejected(self):
        """Test that SQL injection attempts are rejected."""
        # These should all fail due to invalid characters
        sql_payloads = [
            "'; DROP TABLE alerts;--",
            "1; DELETE FROM alerts WHERE 1=1",
            "front_door' OR '1'='1",
        ]
        for payload in sql_payloads:
            with pytest.raises(ValueError, match="invalid characters"):
                validate_dedup_key(payload)

    def test_unicode_emoji_rejected(self):
        """Test that unicode emoji characters are rejected."""
        # Use explicit unicode escape for camera emoji
        with pytest.raises(ValueError, match="invalid characters"):
            validate_dedup_key("camera_\U0001f4f7")  # Camera emoji U+1F4F7

    def test_error_message_truncates_long_key(self):
        """Test that error message truncates very long invalid keys."""
        long_invalid = "a b " * 100  # Has spaces, so invalid
        with pytest.raises(ValueError) as exc_info:
            validate_dedup_key(long_invalid)
        # Check that the error message includes truncation indicator
        assert "..." in str(exc_info.value) or len(str(exc_info.value)) < len(long_invalid)
