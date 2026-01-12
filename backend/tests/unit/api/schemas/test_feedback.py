"""Unit tests for feedback API schemas.

Tests cover:
- FeedbackType enum validation
- EventFeedbackCreate validation (required fields, notes)
- EventFeedbackResponse serialization
- FeedbackStatsResponse aggregation structure

NEM-1908: Create EventFeedback API schemas and routes
"""

import pytest
from pydantic import ValidationError

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# FeedbackType Enum Tests
# =============================================================================


class TestFeedbackType:
    """Tests for FeedbackType enum."""

    def test_feedback_type_false_positive(self):
        """Test FeedbackType.FALSE_POSITIVE value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.FALSE_POSITIVE == "false_positive"
        assert FeedbackType.FALSE_POSITIVE.value == "false_positive"

    def test_feedback_type_missed_threat(self):
        """Test FeedbackType.MISSED_THREAT value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.MISSED_THREAT == "missed_threat"
        assert FeedbackType.MISSED_THREAT.value == "missed_threat"

    def test_feedback_type_severity_wrong(self):
        """Test FeedbackType.SEVERITY_WRONG value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.SEVERITY_WRONG == "severity_wrong"
        assert FeedbackType.SEVERITY_WRONG.value == "severity_wrong"

    def test_feedback_type_accurate(self):
        """Test FeedbackType.ACCURATE value."""
        from backend.api.schemas.feedback import FeedbackType

        assert FeedbackType.ACCURATE == "accurate"
        assert FeedbackType.ACCURATE.value == "accurate"

    def test_feedback_type_is_string_enum(self):
        """Test FeedbackType inherits from str."""
        from backend.api.schemas.feedback import FeedbackType

        # String enum should be directly usable as string
        feedback_type = FeedbackType.FALSE_POSITIVE
        assert isinstance(feedback_type, str)
        assert feedback_type == "false_positive"


# =============================================================================
# EventFeedbackCreate Tests
# =============================================================================


class TestEventFeedbackCreate:
    """Tests for EventFeedbackCreate schema."""

    def test_create_with_required_fields_only(self):
        """Test creating feedback with only required fields."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        assert feedback.event_id == 123
        assert feedback.feedback_type == FeedbackType.FALSE_POSITIVE
        assert feedback.notes is None

    def test_create_with_notes(self):
        """Test creating feedback with optional notes."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=456,
            feedback_type=FeedbackType.MISSED_THREAT,
            notes="This was my neighbor's car.",
        )

        assert feedback.event_id == 456
        assert feedback.feedback_type == FeedbackType.MISSED_THREAT
        assert feedback.notes == "This was my neighbor's car."

    def test_create_with_string_feedback_type(self):
        """Test creating feedback with string feedback type."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=789,
            feedback_type="severity_wrong",
        )

        assert feedback.feedback_type == FeedbackType.SEVERITY_WRONG

    def test_create_with_accurate_feedback_type(self):
        """Test creating feedback with accurate classification."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        feedback = EventFeedbackCreate(
            event_id=100,
            feedback_type=FeedbackType.ACCURATE,
            notes="Good detection!",
        )

        assert feedback.feedback_type == FeedbackType.ACCURATE

    def test_create_missing_event_id_raises_error(self):
        """Test that missing event_id raises validation error."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)

    def test_create_missing_feedback_type_raises_error(self):
        """Test that missing feedback_type raises validation error."""
        from backend.api.schemas.feedback import EventFeedbackCreate

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=123)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("feedback_type",) for e in errors)

    def test_create_invalid_feedback_type_raises_error(self):
        """Test that invalid feedback_type raises validation error."""
        from backend.api.schemas.feedback import EventFeedbackCreate

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=123, feedback_type="invalid_type")

        errors = exc_info.value.errors()
        assert len(errors) >= 1

    def test_create_event_id_must_be_positive(self):
        """Test that event_id must be positive integer."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=-1, feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)

    def test_create_event_id_zero_invalid(self):
        """Test that event_id cannot be zero."""
        from backend.api.schemas.feedback import EventFeedbackCreate, FeedbackType

        with pytest.raises(ValidationError) as exc_info:
            EventFeedbackCreate(event_id=0, feedback_type=FeedbackType.FALSE_POSITIVE)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)


# =============================================================================
# EventFeedbackResponse Tests
# =============================================================================


class TestEventFeedbackResponse:
    """Tests for EventFeedbackResponse schema."""

    def test_response_contains_all_fields(self):
        """Test response schema has all expected fields."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        now = datetime.now(UTC)
        response = EventFeedbackResponse(
            id=1,
            event_id=123,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes="Test notes",
            created_at=now,
        )

        assert response.id == 1
        assert response.event_id == 123
        assert response.feedback_type == FeedbackType.FALSE_POSITIVE
        assert response.notes == "Test notes"
        assert response.created_at == now

    def test_response_notes_can_be_none(self):
        """Test response handles None notes."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        response = EventFeedbackResponse(
            id=2,
            event_id=456,
            feedback_type=FeedbackType.MISSED_THREAT,
            notes=None,
            created_at=datetime.now(UTC),
        )

        assert response.notes is None

    def test_response_from_attributes(self):
        """Test response can be created from ORM model attributes."""
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from backend.api.schemas.feedback import EventFeedbackResponse

        # Simulate ORM model
        mock_model = MagicMock()
        mock_model.id = 3
        mock_model.event_id = 789
        mock_model.feedback_type = "severity_wrong"
        mock_model.notes = "Severity too high"
        mock_model.created_at = datetime.now(UTC)

        response = EventFeedbackResponse.model_validate(mock_model)

        assert response.id == 3
        assert response.event_id == 789
        assert response.feedback_type == "severity_wrong"
        assert response.notes == "Severity too high"

    def test_response_serialization(self):
        """Test response serializes correctly to JSON-compatible dict."""
        from datetime import UTC, datetime

        from backend.api.schemas.feedback import EventFeedbackResponse, FeedbackType

        response = EventFeedbackResponse(
            id=4,
            event_id=100,
            feedback_type=FeedbackType.ACCURATE,
            notes=None,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        data = response.model_dump(mode="json")

        assert data["id"] == 4
        assert data["event_id"] == 100
        assert data["feedback_type"] == "accurate"
        assert data["notes"] is None
        assert "created_at" in data


# =============================================================================
# FeedbackStatsResponse Tests
# =============================================================================


class TestFeedbackStatsResponse:
    """Tests for FeedbackStatsResponse schema."""

    def test_stats_response_contains_expected_fields(self):
        """Test stats response has all expected aggregation fields."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        stats = FeedbackStatsResponse(
            total_feedback=100,
            by_type={
                "false_positive": 40,
                "missed_threat": 30,
                "severity_wrong": 20,
                "accurate": 10,
            },
            by_camera={
                "front_door": 50,
                "back_yard": 30,
                "garage": 20,
            },
        )

        assert stats.total_feedback == 100
        assert stats.by_type["false_positive"] == 40
        assert stats.by_type["missed_threat"] == 30
        assert stats.by_camera["front_door"] == 50

    def test_stats_response_empty_data(self):
        """Test stats response handles empty data."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        stats = FeedbackStatsResponse(
            total_feedback=0,
            by_type={},
            by_camera={},
        )

        assert stats.total_feedback == 0
        assert stats.by_type == {}
        assert stats.by_camera == {}

    def test_stats_response_total_must_be_non_negative(self):
        """Test total_feedback must be >= 0."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        with pytest.raises(ValidationError) as exc_info:
            FeedbackStatsResponse(
                total_feedback=-1,
                by_type={},
                by_camera={},
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("total_feedback",) for e in errors)

    def test_stats_response_serialization(self):
        """Test stats response serializes correctly."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        stats = FeedbackStatsResponse(
            total_feedback=50,
            by_type={"false_positive": 25, "accurate": 25},
            by_camera={"front_door": 50},
        )

        data = stats.model_dump(mode="json")

        assert data["total_feedback"] == 50
        assert data["by_type"] == {"false_positive": 25, "accurate": 25}
        assert data["by_camera"] == {"front_door": 50}

    def test_stats_response_has_example(self):
        """Test stats response schema has OpenAPI example."""
        from backend.api.schemas.feedback import FeedbackStatsResponse

        schema = FeedbackStatsResponse.model_json_schema()

        # Should have example in schema config
        assert (
            "examples" in schema
            or "example" in schema.get("properties", {}).get("total_feedback", {})
            or FeedbackStatsResponse.model_config.get("json_schema_extra") is not None
        )
