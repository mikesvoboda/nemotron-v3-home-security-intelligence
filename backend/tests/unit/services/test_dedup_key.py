"""Unit tests for alert deduplication key building and result dataclasses.

These are pure function tests with no database dependencies.
"""

from backend.services.alert_dedup import DedupResult, build_dedup_key


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
