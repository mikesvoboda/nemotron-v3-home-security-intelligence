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
from backend.tests.factories import EventFactory

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
    """Create a sample event for testing using factory."""
    return EventFactory(
        id=1,
        batch_id="batch_20250115_100000_front_door",
        camera_id="front_door",
        started_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        ended_at=datetime(2025, 1, 15, 10, 2, 0, tzinfo=UTC),
        risk_score=75,
        risk_level="high",
        summary="Person detected at front door",
        reasoning="Unknown person at entry point during night hours",
        reviewed=False,
    )


@pytest.fixture
def minimal_event():
    """Create an event with only required fields using factory."""
    return EventFactory.build(
        batch_id="batch_001",
        camera_id="test_cam",
        started_at=datetime.now(UTC),
        ended_at=None,
        risk_score=None,
        risk_level=None,
        summary=None,
        reasoning=None,
        notes=None,
        object_types=None,
        clip_path=None,
    )


@pytest.fixture
def reviewed_event():
    """Create a reviewed event with notes using factory."""
    return EventFactory(
        id=2,
        batch_id="batch_002",
        camera_id="back_yard",
        low_risk=True,  # Use factory trait
        reviewed=True,
        notes="Confirmed as delivery person",
    )


@pytest.fixture
def fast_path_event():
    """Create a fast-path event using factory."""
    return EventFactory(
        batch_id="batch_003",
        camera_id="driveway",
        fast_path=True,  # Use factory trait
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
        assert sample_event.reviewed is False

    def test_event_optional_fields_default_to_none(self, minimal_event):
        """Test that optional fields default to None."""
        assert minimal_event.ended_at is None
        assert minimal_event.risk_score is None
        assert minimal_event.risk_level is None
        assert minimal_event.summary is None
        assert minimal_event.reasoning is None
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

    def test_event_indexes_defined(self):
        """Test Event has expected indexes."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        # Check for existing indexes
        assert "idx_events_camera_id" in index_names
        assert "idx_events_started_at" in index_names
        assert "idx_events_risk_score" in index_names
        assert "idx_events_reviewed" in index_names
        assert "idx_events_batch_id" in index_names
        assert "idx_events_search_vector" in index_names

    def test_event_composite_risk_level_started_at_index(self):
        """Test Event has composite index on (risk_level, started_at) for filtering.

        NEM-1529: Composite index enables efficient combined filtering on risk_level
        and started_at for dashboard queries like "show all high-risk events from today".
        """
        from sqlalchemy import inspect

        mapper = inspect(Event)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_events_risk_level_started_at" in index_names

        # Verify index columns
        for idx in table.indexes:
            if idx.name == "idx_events_risk_level_started_at":
                col_names = [col.name for col in idx.columns]
                assert col_names == ["risk_level", "started_at"]
                break

    def test_event_covering_index_for_export(self):
        """Test Event has covering index for export query.

        NEM-1535: Covering index includes all columns needed for export queries
        to avoid table lookups (index-only scans).
        """
        from sqlalchemy import inspect

        mapper = inspect(Event)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_events_export_covering" in index_names

        # Verify index columns include export fields
        for idx in table.indexes:
            if idx.name == "idx_events_export_covering":
                col_names = [col.name for col in idx.columns]
                # Should include: id, started_at, ended_at, risk_level, risk_score,
                # camera_id, object_types, summary
                assert "id" in col_names
                assert "started_at" in col_names
                assert "ended_at" in col_names
                assert "risk_level" in col_names
                assert "risk_score" in col_names
                assert "camera_id" in col_names
                assert "object_types" in col_names
                assert "summary" in col_names
                break

    def test_event_partial_index_unreviewed(self):
        """Test Event has partial index for unreviewed events.

        NEM-1536: Partial index WHERE reviewed = false enables efficient
        dashboard queries for unreviewed event counts.
        """
        from sqlalchemy import inspect

        mapper = inspect(Event)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_events_unreviewed" in index_names

        # Verify partial index has WHERE clause
        for idx in table.indexes:
            if idx.name == "idx_events_unreviewed":
                # Check that the index has a WHERE clause (partial index)
                # SQLAlchemy stores this in postgresql_where
                assert idx.dialect_options.get("postgresql", {}).get("where") is not None
                # Verify it indexes the 'id' column (for counting)
                col_names = [col.name for col in idx.columns]
                assert "id" in col_names
                break


# =============================================================================
# Property-based Tests
# =============================================================================


class TestEventProperties:
    """Property-based tests for Event model."""

    @given(risk_score=risk_scores)
    @settings(max_examples=20)
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
    @settings(max_examples=20)
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
    @settings(max_examples=20)
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


# =============================================================================
# Event Snooze Tests (NEM-2359)
# =============================================================================


class TestEventSnooze:
    """Tests for Event snooze_until field (NEM-2359).

    The snooze_until field allows temporarily suppressing alerts for an event
    until a specified timestamp. When set, alerts for the event are snoozed
    until that time.
    """

    def test_snooze_until_default_is_none(self):
        """Test snooze_until is None by default."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
        )
        assert event.snooze_until is None

    def test_snooze_until_can_be_set(self):
        """Test snooze_until can be set to a future timestamp."""
        snooze_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            snooze_until=snooze_time,
        )
        assert event.snooze_until == snooze_time

    def test_snooze_until_with_timezone(self):
        """Test snooze_until preserves timezone-aware datetime."""
        snooze_time = datetime(2025, 6, 15, 18, 30, 0, tzinfo=UTC)
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            snooze_until=snooze_time,
        )
        assert event.snooze_until == snooze_time
        assert event.snooze_until.tzinfo is not None

    def test_snooze_until_can_be_cleared(self):
        """Test snooze_until can be cleared by setting to None."""
        snooze_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            snooze_until=snooze_time,
        )
        assert event.snooze_until == snooze_time

        # Clear the snooze
        event.snooze_until = None
        assert event.snooze_until is None

    def test_is_snoozed_when_snooze_until_in_future(self):
        """Test event is considered snoozed when snooze_until is in the future."""
        future_time = datetime.now(UTC) + timedelta(hours=1)
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            snooze_until=future_time,
        )
        assert event.is_snoozed is True

    def test_is_snoozed_when_snooze_until_in_past(self):
        """Test event is not snoozed when snooze_until is in the past."""
        past_time = datetime.now(UTC) - timedelta(hours=1)
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            snooze_until=past_time,
        )
        assert event.is_snoozed is False

    def test_is_snoozed_when_snooze_until_is_none(self):
        """Test event is not snoozed when snooze_until is None."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            snooze_until=None,
        )
        assert event.is_snoozed is False

    def test_snooze_until_column_is_nullable(self):
        """Test that snooze_until column is defined as nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        snooze_col = mapper.columns["snooze_until"]
        assert snooze_col.nullable is True

    def test_snooze_until_column_is_datetime_with_timezone(self):
        """Test that snooze_until column is DateTime with timezone."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        snooze_col = mapper.columns["snooze_until"]
        # Check it's a DateTime type
        assert hasattr(snooze_col.type, "timezone")
        assert snooze_col.type.timezone is True

    def test_snooze_event_factory(self):
        """Test EventFactory can create snoozed events."""
        from backend.tests.factories import EventFactory

        snooze_time = datetime(2025, 2, 1, 10, 0, 0, tzinfo=UTC)
        event = EventFactory(snooze_until=snooze_time)
        assert event.snooze_until == snooze_time

    def test_snooze_event_factory_default(self):
        """Test EventFactory creates events without snooze by default."""
        from backend.tests.factories import EventFactory

        event = EventFactory()
        assert event.snooze_until is None


# =============================================================================
# Event Computed Risk Level Tests (NEM-3404)
# =============================================================================


class TestEventComputedRiskLevel:
    """Tests for Event.computed_risk_level hybrid property (NEM-3404).

    The computed_risk_level property dynamically computes risk level from
    risk_score using configurable thresholds, working both in Python and SQL.
    """

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with default severity thresholds."""
        mock_settings = MagicMock()
        mock_settings.severity_low_max = 29
        mock_settings.severity_medium_max = 59
        mock_settings.severity_high_max = 84
        return mock_settings

    def test_computed_risk_level_none_when_no_risk_score(self):
        """Test computed_risk_level returns None when risk_score is None."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            risk_score=None,
        )
        assert event.computed_risk_level is None

    def test_computed_risk_level_low(self, mock_settings):
        """Test computed_risk_level returns 'low' for score 0-29."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            for score in [0, 10, 20, 29]:
                event = Event(
                    batch_id="b1",
                    camera_id="cam",
                    started_at=datetime.now(UTC),
                    risk_score=score,
                )
                assert event.computed_risk_level == "low", f"Failed for score {score}"

    def test_computed_risk_level_medium(self, mock_settings):
        """Test computed_risk_level returns 'medium' for score 30-59."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            for score in [30, 45, 59]:
                event = Event(
                    batch_id="b1",
                    camera_id="cam",
                    started_at=datetime.now(UTC),
                    risk_score=score,
                )
                assert event.computed_risk_level == "medium", f"Failed for score {score}"

    def test_computed_risk_level_high(self, mock_settings):
        """Test computed_risk_level returns 'high' for score 60-84."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            for score in [60, 70, 84]:
                event = Event(
                    batch_id="b1",
                    camera_id="cam",
                    started_at=datetime.now(UTC),
                    risk_score=score,
                )
                assert event.computed_risk_level == "high", f"Failed for score {score}"

    def test_computed_risk_level_critical(self, mock_settings):
        """Test computed_risk_level returns 'critical' for score 85-100."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            for score in [85, 95, 100]:
                event = Event(
                    batch_id="b1",
                    camera_id="cam",
                    started_at=datetime.now(UTC),
                    risk_score=score,
                )
                assert event.computed_risk_level == "critical", f"Failed for score {score}"

    def test_computed_risk_level_boundary_29_30(self, mock_settings):
        """Test boundary between low and medium (29 vs 30)."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            low_event = Event(
                batch_id="b1",
                camera_id="cam",
                started_at=datetime.now(UTC),
                risk_score=29,
            )
            medium_event = Event(
                batch_id="b1",
                camera_id="cam",
                started_at=datetime.now(UTC),
                risk_score=30,
            )
            assert low_event.computed_risk_level == "low"
            assert medium_event.computed_risk_level == "medium"

    def test_computed_risk_level_boundary_59_60(self, mock_settings):
        """Test boundary between medium and high (59 vs 60)."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            medium_event = Event(
                batch_id="b1",
                camera_id="cam",
                started_at=datetime.now(UTC),
                risk_score=59,
            )
            high_event = Event(
                batch_id="b1",
                camera_id="cam",
                started_at=datetime.now(UTC),
                risk_score=60,
            )
            assert medium_event.computed_risk_level == "medium"
            assert high_event.computed_risk_level == "high"

    def test_computed_risk_level_boundary_84_85(self, mock_settings):
        """Test boundary between high and critical (84 vs 85)."""
        with patch("backend.core.config.get_settings", return_value=mock_settings):
            high_event = Event(
                batch_id="b1",
                camera_id="cam",
                started_at=datetime.now(UTC),
                risk_score=84,
            )
            critical_event = Event(
                batch_id="b1",
                camera_id="cam",
                started_at=datetime.now(UTC),
                risk_score=85,
            )
            assert high_event.computed_risk_level == "high"
            assert critical_event.computed_risk_level == "critical"

    def test_computed_risk_level_sql_expression_exists(self):
        """Test that computed_risk_level has a SQL expression for queries."""

        # The hybrid property should have an expression
        assert hasattr(Event.computed_risk_level, "expression")
        # The expression should be callable and return a CASE clause
        expr = Event.computed_risk_level.expression
        assert expr is not None


# =============================================================================
# Event Version Column Tests (NEM-3408)
# =============================================================================


class TestEventVersionColumn:
    """Tests for Event.version column for optimistic locking (NEM-3408).

    The version column enables optimistic locking to prevent concurrent
    modification conflicts.
    """

    def test_version_column_exists(self):
        """Test that version column is defined on Event model."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        assert "version" in mapper.columns

    def test_version_column_default(self):
        """Test that version column has default value of 1."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        version_col = mapper.columns["version"]
        assert version_col.default is not None
        assert version_col.default.arg == 1

    def test_version_column_server_default(self):
        """Test that version column has server_default of '1'."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        version_col = mapper.columns["version"]
        assert version_col.server_default is not None
        assert version_col.server_default.arg == "1"

    def test_version_column_not_nullable(self):
        """Test that version column is NOT nullable."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        version_col = mapper.columns["version"]
        assert version_col.nullable is False

    def test_mapper_args_has_version_id_col(self):
        """Test that __mapper_args__ configures version_id_col."""
        from sqlalchemy import inspect

        mapper = inspect(Event)
        # In SQLAlchemy 2.0, version_id_col is accessible via mapper.version_id_col
        assert mapper.version_id_col is not None
        assert mapper.version_id_col.name == "version"

    def test_event_with_explicit_version(self):
        """Test creating an event with explicit version."""
        event = Event(
            batch_id="b1",
            camera_id="cam",
            started_at=datetime.now(UTC),
            version=5,
        )
        assert event.version == 5


# =============================================================================
# ORM Utils Tests (NEM-3405, NEM-3407)
# =============================================================================


class TestOrmUtils:
    """Tests for backend.core.orm_utils utility functions."""

    def test_is_development_mode_default(self, monkeypatch):
        """Test is_development_mode returns False for production."""
        from backend.core.orm_utils import is_development_mode

        monkeypatch.setenv("ENVIRONMENT", "production")
        # Need to reload or call without cache
        import os

        os.environ["ENVIRONMENT"] = "production"
        # Since function reads os.environ directly, this should work
        assert is_development_mode() is False

    def test_is_development_mode_development(self, monkeypatch):
        """Test is_development_mode returns True for development."""
        import os

        os.environ["ENVIRONMENT"] = "development"
        from backend.core.orm_utils import is_development_mode

        assert is_development_mode() is True

    def test_is_development_mode_test(self, monkeypatch):
        """Test is_development_mode returns True for test environment."""
        import os

        os.environ["ENVIRONMENT"] = "test"
        from backend.core.orm_utils import is_development_mode

        assert is_development_mode() is True

    def test_get_relationship_lazy_mode_production(self, monkeypatch):
        """Test get_relationship_lazy_mode returns 'select' in production."""
        import os

        os.environ["ENVIRONMENT"] = "production"
        from backend.core.orm_utils import get_relationship_lazy_mode

        result = get_relationship_lazy_mode()
        assert result == "select"

    def test_get_relationship_lazy_mode_development(self, monkeypatch):
        """Test get_relationship_lazy_mode returns 'raise_on_sql' in development."""
        import os

        os.environ["ENVIRONMENT"] = "development"
        from backend.core.orm_utils import get_relationship_lazy_mode

        result = get_relationship_lazy_mode()
        assert result == "raise_on_sql"

    def test_get_relationship_lazy_mode_custom_default(self, monkeypatch):
        """Test get_relationship_lazy_mode with custom default."""
        import os

        os.environ["ENVIRONMENT"] = "production"
        from backend.core.orm_utils import get_relationship_lazy_mode

        result = get_relationship_lazy_mode(default="selectin")
        assert result == "selectin"
