"""Unit tests for strict mode API request schemas (NEM-3779).

Tests verify that strict mode schemas reject type coercion while accepting
correctly-typed values. This ensures API contract compliance and catches
client-side type bugs early.
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.strict_request_schemas import (
    AlertRuleCreateStrict,
    AlertRuleUpdateStrict,
    CameraCreateStrict,
    CameraUpdateStrict,
    EventFeedbackCreateStrict,
    EventUpdateStrict,
    ZoneCreateStrict,
    ZoneUpdateStrict,
)
from backend.models.enums import CameraStatus


class TestCameraCreateStrict:
    """Tests for CameraCreateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        camera = CameraCreateStrict(
            name="Front Door Camera",
            folder_path="/export/foscam/front_door",
            status=CameraStatus.ONLINE,
        )
        assert camera.name == "Front Door Camera"
        assert camera.folder_path == "/export/foscam/front_door"
        assert camera.status == CameraStatus.ONLINE

    def test_rejects_integer_name(self):
        """Test strict schema rejects integer for name field."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreateStrict(
                name=123,  # Should be string
                folder_path="/export/foscam/front_door",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_rejects_integer_folder_path(self):
        """Test strict schema rejects integer for folder_path field."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreateStrict(
                name="Test Camera",
                folder_path=12345,  # Should be string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("folder_path",) for e in errors)

    def test_inherits_path_traversal_validation(self):
        """Test strict schema still validates path traversal attacks."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreateStrict(
                name="Test Camera",
                folder_path="../../../etc/passwd",
            )
        assert (
            "folder_path" in str(exc_info.value).lower()
            or "path traversal" in str(exc_info.value).lower()
        )

    def test_inherits_name_validation(self):
        """Test strict schema still validates camera name."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreateStrict(
                name="   ",  # Whitespace only
                folder_path="/export/foscam/front_door",
            )
        assert "name" in str(exc_info.value).lower()

    def test_rejects_string_status(self):
        """Test strict schema rejects string status (must use enum instance)."""
        with pytest.raises(ValidationError) as exc_info:
            CameraCreateStrict(
                name="Test Camera",
                folder_path="/export/foscam/front_door",
                status="online",  # Should be CameraStatus.ONLINE
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("status",) for e in errors)

    def test_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = CameraCreateStrict.model_config
        assert config.get("strict") is True


class TestCameraUpdateStrict:
    """Tests for CameraUpdateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed optional values."""
        camera = CameraUpdateStrict(
            name="Updated Camera",
            status=CameraStatus.OFFLINE,
        )
        assert camera.name == "Updated Camera"
        assert camera.status == CameraStatus.OFFLINE

    def test_accepts_none_values(self):
        """Test strict schema accepts None for optional fields."""
        camera = CameraUpdateStrict(name=None, folder_path=None, status=None)
        assert camera.name is None
        assert camera.folder_path is None
        assert camera.status is None

    def test_rejects_integer_name(self):
        """Test strict schema rejects integer for name field."""
        with pytest.raises(ValidationError) as exc_info:
            CameraUpdateStrict(name=456)  # Should be string
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)


class TestEventUpdateStrict:
    """Tests for EventUpdateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        event = EventUpdateStrict(
            reviewed=True,
            flagged=False,
            notes="Test notes",
            version=1,
        )
        assert event.reviewed is True
        assert event.flagged is False
        assert event.notes == "Test notes"
        assert event.version == 1

    def test_rejects_string_boolean(self):
        """Test strict schema rejects string 'true' for boolean field."""
        with pytest.raises(ValidationError) as exc_info:
            EventUpdateStrict(reviewed="true")  # Should be bool, not string
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("reviewed",) for e in errors)

    def test_rejects_integer_boolean(self):
        """Test strict schema rejects integer 1 for boolean field."""
        with pytest.raises(ValidationError) as exc_info:
            EventUpdateStrict(reviewed=1)  # Should be bool, not int
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("reviewed",) for e in errors)

    def test_rejects_string_version(self):
        """Test strict schema rejects string version."""
        with pytest.raises(ValidationError) as exc_info:
            EventUpdateStrict(version="1")  # Should be int, not string
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("version",) for e in errors)

    def test_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = EventUpdateStrict.model_config
        assert config.get("strict") is True


class TestEventFeedbackCreateStrict:
    """Tests for EventFeedbackCreateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        feedback = EventFeedbackCreateStrict(
            event_id=123,
            feedback_type="false_positive",
            notes="Test feedback",
            suggested_score=25,
        )
        assert feedback.event_id == 123
        assert feedback.feedback_type == "false_positive"
        assert feedback.suggested_score == 25

    def test_rejects_string_event_id(self):
        """Test strict schema rejects string event_id."""
        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreateStrict(
                event_id="123",  # Should be int, not string
                feedback_type="false_positive",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)

    def test_rejects_string_suggested_score(self):
        """Test strict schema rejects string suggested_score."""
        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreateStrict(
                event_id=123,
                feedback_type="accurate",
                suggested_score="50",  # Should be int, not string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("suggested_score",) for e in errors)

    def test_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = EventFeedbackCreateStrict.model_config
        assert config.get("strict") is True


class TestAlertRuleCreateStrict:
    """Tests for AlertRuleCreateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        rule = AlertRuleCreateStrict(
            name="Test Alert Rule",
            enabled=True,
            risk_threshold=70,
            cooldown_seconds=300,
        )
        assert rule.name == "Test Alert Rule"
        assert rule.enabled is True
        assert rule.risk_threshold == 70
        assert rule.cooldown_seconds == 300

    def test_rejects_string_risk_threshold(self):
        """Test strict schema rejects string risk_threshold."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreateStrict(
                name="Test Rule",
                risk_threshold="70",  # Should be int, not string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_threshold",) for e in errors)

    def test_rejects_string_boolean_enabled(self):
        """Test strict schema rejects string for boolean enabled."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreateStrict(
                name="Test Rule",
                enabled="true",  # Should be bool, not string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("enabled",) for e in errors)

    def test_rejects_string_cooldown_seconds(self):
        """Test strict schema rejects string cooldown_seconds."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreateStrict(
                name="Test Rule",
                cooldown_seconds="300",  # Should be int, not string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("cooldown_seconds",) for e in errors)

    def test_rejects_string_min_confidence(self):
        """Test strict schema rejects string min_confidence."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleCreateStrict(
                name="Test Rule",
                min_confidence="0.8",  # Should be float, not string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("min_confidence",) for e in errors)

    def test_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = AlertRuleCreateStrict.model_config
        assert config.get("strict") is True


class TestAlertRuleUpdateStrict:
    """Tests for AlertRuleUpdateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed optional values."""
        rule = AlertRuleUpdateStrict(
            enabled=False,
            risk_threshold=80,
        )
        assert rule.enabled is False
        assert rule.risk_threshold == 80

    def test_rejects_string_risk_threshold(self):
        """Test strict schema rejects string risk_threshold."""
        with pytest.raises(ValidationError) as exc_info:
            AlertRuleUpdateStrict(risk_threshold="80")  # Should be int
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("risk_threshold",) for e in errors)


class TestZoneCreateStrict:
    """Tests for ZoneCreateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed values."""
        zone = ZoneCreateStrict(
            camera_id="front_door",
            name="Entry Zone",
            points=[
                {"x": 0.1, "y": 0.1},
                {"x": 0.9, "y": 0.1},
                {"x": 0.9, "y": 0.9},
            ],
            enabled=True,
        )
        assert zone.camera_id == "front_door"
        assert zone.name == "Entry Zone"
        assert len(zone.points) == 3
        assert zone.enabled is True

    def test_rejects_string_boolean_enabled(self):
        """Test strict schema rejects string for boolean enabled."""
        with pytest.raises(ValidationError) as exc_info:
            ZoneCreateStrict(
                camera_id="front_door",
                name="Entry Zone",
                points=[{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}, {"x": 0.9, "y": 0.9}],
                enabled="true",  # Should be bool, not string
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("enabled",) for e in errors)

    def test_rejects_integer_camera_id(self):
        """Test strict schema rejects integer for camera_id."""
        with pytest.raises(ValidationError) as exc_info:
            ZoneCreateStrict(
                camera_id=123,  # Should be string
                name="Entry Zone",
                points=[{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}, {"x": 0.9, "y": 0.9}],
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("camera_id",) for e in errors)

    def test_model_config_is_strict(self):
        """Test that strict variant has strict=True in config."""
        config = ZoneCreateStrict.model_config
        assert config.get("strict") is True


class TestZoneUpdateStrict:
    """Tests for ZoneUpdateStrict schema."""

    def test_accepts_correct_types(self):
        """Test strict schema accepts correctly-typed optional values."""
        zone = ZoneUpdateStrict(
            name="Updated Zone",
            enabled=False,
        )
        assert zone.name == "Updated Zone"
        assert zone.enabled is False

    def test_rejects_string_boolean_enabled(self):
        """Test strict schema rejects string for boolean enabled."""
        with pytest.raises(ValidationError) as exc_info:
            ZoneUpdateStrict(enabled="false")  # Should be bool
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("enabled",) for e in errors)


class TestStrictVsNonStrictComparison:
    """Tests comparing strict vs non-strict schema behavior."""

    def test_both_accept_valid_data(self):
        """Test both strict and non-strict accept properly typed data."""
        from backend.api.schemas.camera import CameraCreate

        # Non-strict accepts string status
        non_strict_data = {
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": "online",
        }
        non_strict = CameraCreate(**non_strict_data)

        # Strict requires enum instance for status
        strict_data = {
            "name": "Front Door Camera",
            "folder_path": "/export/foscam/front_door",
            "status": CameraStatus.ONLINE,
        }
        strict = CameraCreateStrict(**strict_data)

        # Both should produce same results
        assert non_strict.name == strict.name
        assert non_strict.folder_path == strict.folder_path

    def test_strict_serialization_matches(self):
        """Test that strict schema serializes same as non-strict."""
        strict = CameraCreateStrict(
            name="Test Camera",
            folder_path="/export/foscam/test",
            status=CameraStatus.ONLINE,
        )
        data = strict.model_dump()

        assert data["name"] == "Test Camera"
        assert data["folder_path"] == "/export/foscam/test"
        assert data["status"] == CameraStatus.ONLINE
