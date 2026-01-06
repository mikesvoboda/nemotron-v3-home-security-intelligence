"""Unit tests for EventDetection junction table model.

Tests cover:
- Model initialization
- Field validation
- Composite primary key
- Foreign key constraints
- Relationship testing
- Index verification
- String representation (__repr__)
"""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import inspect

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# EventDetection Model Initialization Tests
# =============================================================================


class TestEventDetectionModelInitialization:
    """Tests for EventDetection model initialization."""

    def test_event_detection_creation(self):
        """Test creating an EventDetection with required fields."""
        from backend.models.event_detection import EventDetection

        event_detection = EventDetection(
            event_id=1,
            detection_id=100,
        )

        assert event_detection.event_id == 1
        assert event_detection.detection_id == 100

    def test_event_detection_with_created_at(self):
        """Test EventDetection with explicit created_at timestamp."""
        from backend.models.event_detection import EventDetection

        now = datetime.now(UTC)
        event_detection = EventDetection(
            event_id=1,
            detection_id=100,
            created_at=now,
        )

        assert event_detection.created_at == now

    def test_event_detection_has_composite_primary_key(self):
        """Test that EventDetection uses composite primary key (event_id, detection_id)."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        pk_cols = [col.name for col in mapper.primary_key]

        assert "event_id" in pk_cols
        assert "detection_id" in pk_cols
        assert len(pk_cols) == 2


# =============================================================================
# EventDetection Table Args Tests
# =============================================================================


class TestEventDetectionTableArgs:
    """Tests for EventDetection table arguments (indexes, constraints)."""

    def test_event_detection_tablename(self):
        """Test EventDetection has correct table name."""
        from backend.models.event_detection import EventDetection

        assert EventDetection.__tablename__ == "event_detections"

    def test_event_detection_has_table_args(self):
        """Test EventDetection model has __table_args__."""
        from backend.models.event_detection import EventDetection

        assert hasattr(EventDetection, "__table_args__")

    def test_event_detection_event_id_index(self):
        """Test EventDetection has index on event_id for efficient event lookups."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_event_detections_event_id" in index_names

    def test_event_detection_detection_id_index(self):
        """Test EventDetection has index on detection_id for efficient detection lookups."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_event_detections_detection_id" in index_names

    def test_event_detection_created_at_index(self):
        """Test EventDetection has index on created_at for time-range queries."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_event_detections_created_at" in index_names


# =============================================================================
# EventDetection Foreign Key Tests
# =============================================================================


class TestEventDetectionForeignKeys:
    """Tests for EventDetection foreign key definitions."""

    def test_event_detection_has_event_foreign_key(self):
        """Test EventDetection has foreign key to events table."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        event_id_col = mapper.columns["event_id"]

        # Check foreign key exists
        fks = list(event_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "events.id"

    def test_event_detection_has_detection_foreign_key(self):
        """Test EventDetection has foreign key to detections table."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        detection_id_col = mapper.columns["detection_id"]

        # Check foreign key exists
        fks = list(detection_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "detections.id"

    def test_event_detection_cascade_delete_on_event(self):
        """Test EventDetection has CASCADE delete on event_id FK."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        event_id_col = mapper.columns["event_id"]
        fks = list(event_id_col.foreign_keys)

        assert fks[0].ondelete == "CASCADE"

    def test_event_detection_cascade_delete_on_detection(self):
        """Test EventDetection has CASCADE delete on detection_id FK."""
        from backend.models.event_detection import EventDetection

        mapper = inspect(EventDetection)
        detection_id_col = mapper.columns["detection_id"]
        fks = list(detection_id_col.foreign_keys)

        assert fks[0].ondelete == "CASCADE"


# =============================================================================
# EventDetection Repr Tests
# =============================================================================


class TestEventDetectionRepr:
    """Tests for EventDetection string representation."""

    def test_event_detection_repr_contains_class_name(self):
        """Test repr contains class name."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=1, detection_id=100)
        repr_str = repr(ed)

        assert "EventDetection" in repr_str

    def test_event_detection_repr_contains_event_id(self):
        """Test repr contains event_id."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=42, detection_id=100)
        repr_str = repr(ed)

        assert "42" in repr_str

    def test_event_detection_repr_contains_detection_id(self):
        """Test repr contains detection_id."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=1, detection_id=999)
        repr_str = repr(ed)

        assert "999" in repr_str

    def test_event_detection_repr_format(self):
        """Test repr has expected format."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=1, detection_id=100)
        repr_str = repr(ed)

        assert repr_str.startswith("<EventDetection(")
        assert repr_str.endswith(")>")


# =============================================================================
# EventDetection Relationship Tests
# =============================================================================


class TestEventDetectionRelationships:
    """Tests for EventDetection relationship definitions."""

    def test_event_detection_has_event_relationship(self):
        """Test EventDetection has event relationship defined."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=1, detection_id=100)
        assert hasattr(ed, "event")

    def test_event_detection_has_detection_relationship(self):
        """Test EventDetection has detection relationship defined."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=1, detection_id=100)
        assert hasattr(ed, "detection")


# =============================================================================
# Event Model Relationship Tests (after junction table)
# =============================================================================


class TestEventDetectionIntegration:
    """Tests for Event model's detection_records relationship via junction table."""

    def test_event_has_detection_records_relationship(self):
        """Test Event model has detection_records relationship."""
        from backend.models.event import Event

        assert hasattr(Event, "detection_records")

    def test_detection_has_event_records_relationship(self):
        """Test Detection model has event_records relationship."""
        from backend.models.detection import Detection

        assert hasattr(Detection, "event_records")


# =============================================================================
# Property-based Tests
# =============================================================================


class TestEventDetectionProperties:
    """Property-based tests for EventDetection model."""

    @given(
        event_id=st.integers(min_value=1, max_value=2147483647),
        detection_id=st.integers(min_value=1, max_value=2147483647),
    )
    @settings(max_examples=50)
    def test_event_detection_roundtrip(self, event_id: int, detection_id: int):
        """Property: Event and detection IDs roundtrip correctly."""
        from backend.models.event_detection import EventDetection

        ed = EventDetection(event_id=event_id, detection_id=detection_id)

        assert ed.event_id == event_id
        assert ed.detection_id == detection_id

    @given(
        count=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20)
    def test_multiple_event_detections_can_be_created(self, count: int):
        """Property: Multiple EventDetection records can be created."""
        from backend.models.event_detection import EventDetection

        records = [EventDetection(event_id=1, detection_id=i) for i in range(1, count + 1)]

        assert len(records) == count
        detection_ids = [r.detection_id for r in records]
        assert len(set(detection_ids)) == count  # All unique


# =============================================================================
# Module Export Tests
# =============================================================================


class TestEventDetectionModuleExport:
    """Tests for EventDetection module export."""

    def test_event_detection_exported_from_models(self):
        """Test EventDetection is exported from backend.models."""
        from backend.models import EventDetection

        assert EventDetection is not None

    def test_event_detection_table_exported(self):
        """Test event_detections table association is accessible."""
        from backend.models.event_detection import event_detections

        assert event_detections is not None
        assert event_detections.name == "event_detections"
