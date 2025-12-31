"""Unit tests for Event model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Risk scoring fields
- get_severity() method
- Property-based tests for field values
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.enums import Severity
from backend.models.event import Event

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid risk scores (0-100)
risk_scores = st.integers(min_value=0, max_value=100)

# Strategy for risk levels
risk_levels = st.sampled_from(["low", "medium", "high", "critical"])

# Strategy for batch IDs
batch_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        id=1,
        batch_id="batch_20250115_100000_front_door",
        camera_id="front_door",
        started_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2025, 1, 15, 10, 2, 0, tzinfo=UTC),
        risk_score=75,
        risk_level="high",
        summary="Person detected at front door",
        reasoning="Unknown person at entry point during night hours",
        detection_ids="1,2,3",
        reviewed=False,
    )


@pytest.fixture
def minimal_event():
    """Create an event with only required fields."""
    return Event(
        batch_id="batch_001",
        camera_id="test_cam",
        started_at=datetime.now(UTC),
    )


@pytest.fixture
def reviewed_event():
    """Create a reviewed event with notes."""
    return Event(
        id=2,
        batch_id="batch_002",
        camera_id="back_yard",
        started_at=datetime.now(UTC),
        risk_score=25,
        risk_level="low",
        reviewed=True,
        notes="Confirmed as delivery person",
    )


@pytest.fixture
def fast_path_event():
    """Create a fast-path event."""
    return Event(
        batch_id="batch_003",
        camera_id="driveway",
        started_at=datetime.now(UTC),
        is_fast_path=True,
        risk_score=15,
        risk_level="low",
    )


# =============================================================================
# Event Model Initialization Tests
# =============================================================================


class TestEventModelInitialization:
    """Tests for Event model initialization."""

    def test_event_creation_minimal(self):
        """Test creating an event with minimal required fields."""
        now = datetime.now(UTC)
        event = Event(
            batch_id="batch_001",
            camera_id="test_cam",
            started_at=now,
        )

        assert event.batch_id == "batch_001"
        assert event.camera_id == "test_cam"
        assert event.started_at == now

    def test_event_with_all_fields(self, sample_event):
        """Test event with all fields populated."""
        assert sample_event.id == 1
        assert sample_event.batch_id == "batch_20250115_100000_front_door"
        assert sample_event.camera_id == "front_door"
        assert sample_event.risk_score == 75
        assert sample_event.risk_level == "high"
        assert sample_event.summary == "Person detected at front door"
        assert sample_event.reasoning == "Unknown person at entry point during night hours"
        assert sample_event.detection_ids == "1,2,3"
        assert sample_event.reviewed is False

    def test_event_optional_fields_default_to_none(self, minimal_event):
        """Test that optional fields default to None."""
        assert minimal_event.ended_at is None
        assert minimal_event.risk_score is None
        assert minimal_event.risk_level is None
        assert minimal_event.summary is None
        assert minimal_event.reasoning is None
        assert minimal_event.detection_ids is None
        assert minimal_event.notes is None
        assert minimal_event.object_types is None
        assert minimal_event.clip_path is None
        assert minimal_event.search_vector is None

    def test_event_reviewed_default_column_definition(self):
        """Test that reviewed column has False as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Event)
        reviewed_col = mapper.columns["reviewed"]
        assert reviewed_col.default is not None
        assert reviewed_col.default.arg is False

    def test_event_is_fast_path_default_column_definition(self):
        """Test that is_fast_path column has False as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Event)
        is_fast_path_col = mapper.columns["is_fast_path"]
        assert is_fast_path_col.default is not None
        assert is_fast_path_col.default.arg is False


# =============================================================================
# Event Field Tests
# =============================================================================


class TestEventRiskScoring:
    """Tests for Event risk scoring fields."""

    def test_risk_score_low(self):
        """Test event with low risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=10,
            risk_level="low",
        )
        assert event.risk_score == 10
        assert event.risk_level == "low"

    def test_risk_score_medium(self):
        """Test event with medium risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=45,
            risk_level="medium",
        )
        assert event.risk_score == 45
        assert event.risk_level == "medium"

    def test_risk_score_high(self):
        """Test event with high risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=75,
            risk_level="high",
        )
        assert event.risk_score == 75
        assert event.risk_level == "high"

    def test_risk_score_critical(self):
        """Test event with critical risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=95,
            risk_level="critical",
        )
        assert event.risk_score == 95
        assert event.risk_level == "critical"

    def test_risk_score_boundary_zero(self):
        """Test event with zero risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=0,
        )
        assert event.risk_score == 0

    def test_risk_score_boundary_hundred(self):
        """Test event with maximum risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=100,
        )
        assert event.risk_score == 100


class TestEventTimestamps:
    """Tests for Event timestamp fields."""

    def test_event_started_at_required(self, sample_event):
        """Test started_at is set."""
        assert sample_event.started_at is not None

    def test_event_ended_at_optional(self, minimal_event):
        """Test ended_at is optional."""
        assert minimal_event.ended_at is None

    def test_event_with_ended_at(self, sample_event):
        """Test event with ended_at timestamp."""
        assert sample_event.ended_at is not None
        assert sample_event.ended_at > sample_event.started_at

    def test_event_duration_calculation(self, sample_event):
        """Test event duration can be calculated from timestamps."""
        duration = sample_event.ended_at - sample_event.started_at
        assert duration == timedelta(minutes=2)


class TestEventReviewStatus:
    """Tests for Event review status fields."""

    def test_event_notes_default_is_none(self, minimal_event):
        """Test event notes is None by default."""
        assert minimal_event.notes is None

    def test_event_reviewed_with_notes(self, reviewed_event):
        """Test reviewed event with notes."""
        assert reviewed_event.reviewed is True
        assert reviewed_event.notes == "Confirmed as delivery person"


class TestEventFastPath:
    """Tests for Event fast-path processing."""

    def test_fast_path_event(self, fast_path_event):
        """Test fast-path event flag."""
        assert fast_path_event.is_fast_path is True

    def test_regular_event_with_explicit_is_fast_path_false(self):
        """Test regular event with explicit is_fast_path=False."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            is_fast_path=False,
        )
        assert event.is_fast_path is False


class TestEventObjectTypes:
    """Tests for Event object_types field."""

    def test_event_with_object_types(self):
        """Test event with cached object types."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            object_types="person,vehicle",
        )
        assert event.object_types == "person,vehicle"

    def test_event_multiple_object_types(self):
        """Test event with multiple object types."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            object_types="person,vehicle,animal,package",
        )
        assert "person" in event.object_types
        assert "vehicle" in event.object_types


class TestEventClipPath:
    """Tests for Event clip_path field."""

    def test_event_with_clip_path(self):
        """Test event with generated clip path."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            clip_path="/clips/event_1.mp4",
        )
        assert event.clip_path == "/clips/event_1.mp4"

    def test_event_without_clip_path(self, minimal_event):
        """Test event without clip defaults to None."""
        assert minimal_event.clip_path is None


# =============================================================================
# Event Repr Tests
# =============================================================================


class TestEventRepr:
    """Tests for Event string representation."""

    def test_event_repr_contains_class_name(self, sample_event):
        """Test repr contains class name."""
        repr_str = repr(sample_event)
        assert "Event" in repr_str

    def test_event_repr_contains_id(self, sample_event):
        """Test repr contains event id."""
        repr_str = repr(sample_event)
        assert "id=1" in repr_str

    def test_event_repr_contains_batch_id(self, sample_event):
        """Test repr contains batch_id."""
        repr_str = repr(sample_event)
        assert "batch_20250115_100000_front_door" in repr_str

    def test_event_repr_contains_camera_id(self, sample_event):
        """Test repr contains camera_id."""
        repr_str = repr(sample_event)
        assert "front_door" in repr_str

    def test_event_repr_contains_risk_score(self, sample_event):
        """Test repr contains risk_score."""
        repr_str = repr(sample_event)
        assert "75" in repr_str

    def test_event_repr_format(self, sample_event):
        """Test repr has expected format."""
        repr_str = repr(sample_event)
        assert repr_str.startswith("<Event(")
        assert repr_str.endswith(")>")


# =============================================================================
# Event get_severity() Tests
# =============================================================================


class TestEventGetSeverity:
    """Tests for Event.get_severity() method."""

    def test_get_severity_returns_none_when_no_risk_score(self, minimal_event):
        """Test get_severity returns None when risk_score is None."""
        result = minimal_event.get_severity()
        assert result is None

    def test_get_severity_low_score(self):
        """Test get_severity for low risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=10,
        )

        # Mock the severity service function where it's imported from
        with patch("backend.services.severity.get_severity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.risk_score_to_severity.return_value = Severity.LOW
            mock_get_service.return_value = mock_service

            result = event.get_severity()
            assert result == Severity.LOW
            mock_service.risk_score_to_severity.assert_called_once_with(10)

    def test_get_severity_high_score(self):
        """Test get_severity for high risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=75,
        )

        with patch("backend.services.severity.get_severity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.risk_score_to_severity.return_value = Severity.HIGH
            mock_get_service.return_value = mock_service

            result = event.get_severity()
            assert result == Severity.HIGH

    def test_get_severity_critical_score(self):
        """Test get_severity for critical risk score."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=95,
        )

        with patch("backend.services.severity.get_severity_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.risk_score_to_severity.return_value = Severity.CRITICAL
            mock_get_service.return_value = mock_service

            result = event.get_severity()
            assert result == Severity.CRITICAL


# =============================================================================
# Event Relationship Tests
# =============================================================================


class TestEventRelationships:
    """Tests for Event relationship definitions."""

    def test_event_has_camera_relationship(self, sample_event):
        """Test event has camera relationship defined."""
        assert hasattr(sample_event, "camera")

    def test_event_has_alerts_relationship(self, sample_event):
        """Test event has alerts relationship defined."""
        assert hasattr(sample_event, "alerts")


# =============================================================================
# Event Table Args Tests
# =============================================================================


class TestEventTableArgs:
    """Tests for Event table arguments (indexes)."""

    def test_event_has_table_args(self):
        """Test Event model has __table_args__."""
        assert hasattr(Event, "__table_args__")

    def test_event_tablename(self):
        """Test Event has correct table name."""
        assert Event.__tablename__ == "events"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestEventProperties:
    """Property-based tests for Event model."""

    @given(risk_score=risk_scores)
    @settings(max_examples=50)
    def test_risk_score_roundtrip(self, risk_score: int):
        """Property: Risk score values roundtrip correctly."""
        event = Event(
            batch_id="test",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )
        assert event.risk_score == risk_score

    @given(risk_level=risk_levels)
    @settings(max_examples=20)
    def test_risk_level_roundtrip(self, risk_level: str):
        """Property: Risk level values roundtrip correctly."""
        event = Event(
            batch_id="test",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_level=risk_level,
        )
        assert event.risk_level == risk_level

    @given(batch_id=batch_ids, camera_id=st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_required_fields_roundtrip(self, batch_id: str, camera_id: str):
        """Property: Required fields roundtrip correctly."""
        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC),
        )
        assert event.batch_id == batch_id
        assert event.camera_id == camera_id

    @given(summary=st.text(max_size=500), reasoning=st.text(max_size=1000))
    @settings(max_examples=50)
    def test_text_fields_roundtrip(self, summary: str, reasoning: str):
        """Property: Text fields roundtrip correctly."""
        event = Event(
            batch_id="test",
            camera_id="cam",
            started_at=datetime.now(UTC),
            summary=summary,
            reasoning=reasoning,
        )
        assert event.summary == summary
        assert event.reasoning == reasoning

    @given(reviewed=st.booleans(), is_fast_path=st.booleans())
    @settings(max_examples=20)
    def test_boolean_fields_roundtrip(self, reviewed: bool, is_fast_path: bool):
        """Property: Boolean fields roundtrip correctly."""
        event = Event(
            batch_id="test",
            camera_id="cam",
            started_at=datetime.now(UTC),
            reviewed=reviewed,
            is_fast_path=is_fast_path,
        )
        assert event.reviewed == reviewed
        assert event.is_fast_path == is_fast_path

    @given(
        detection_ids=st.lists(st.integers(min_value=1, max_value=10000), min_size=1, max_size=20)
    )
    @settings(max_examples=50)
    def test_detection_ids_can_store_list_as_string(self, detection_ids: list[int]):
        """Property: Detection IDs can be stored as comma-separated string."""
        ids_string = ",".join(str(i) for i in detection_ids)
        event = Event(
            batch_id="test",
            camera_id="cam",
            started_at=datetime.now(UTC),
            detection_ids=ids_string,
        )
        assert event.detection_ids == ids_string
        # Can parse back to list
        parsed = [int(x) for x in event.detection_ids.split(",")]
        assert parsed == detection_ids
