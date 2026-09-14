"""Unit tests for PackageEvent model (NEM-5293).

Tests for package event storage model that tracks package delivery/removal events.
This module follows TDD - all tests are written BEFORE implementation.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- PackageEventType enum
- Timestamps and duration calculation
- Zone and camera relationships
- Index definitions
- Property-based tests for field values

IMPORTANT: These tests are designed to FAIL until implementation is complete.
This is Phase 4 (Red phase) of TDD - writing failing tests first.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid confidence scores (0-100 as integer for percentage)
confidence_percentages = st.integers(min_value=0, max_value=100)

# Strategy for valid confidence scores (0-1 as float)
confidence_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for camera IDs
camera_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)

# Strategy for zone IDs
zone_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)


# =============================================================================
# PackageEvent Import Tests (will fail until implemented)
# =============================================================================


class TestPackageEventImports:
    """Test that PackageEvent module can be imported."""

    def test_package_event_model_importable(self) -> None:
        """Test PackageEvent model can be imported."""
        from backend.models.package_event import PackageEvent

        assert PackageEvent is not None

    def test_package_event_type_enum_importable(self) -> None:
        """Test PackageEventType enum can be imported."""
        from backend.models.package_event import PackageEventType

        assert PackageEventType is not None

    def test_package_event_in_models_init(self) -> None:
        """Test PackageEvent is exported from models __init__."""
        from backend.models import PackageEvent

        assert PackageEvent is not None

    def test_package_event_type_in_models_init(self) -> None:
        """Test PackageEventType is exported from models __init__."""
        from backend.models import PackageEventType

        assert PackageEventType is not None


# =============================================================================
# PackageEventType Enum Tests
# =============================================================================


class TestPackageEventTypeEnum:
    """Tests for PackageEventType enum."""

    def test_event_type_delivered(self) -> None:
        """Test DELIVERED event type exists and has correct value."""
        from backend.models.package_event import PackageEventType

        assert PackageEventType.DELIVERED.value == "delivered"

    def test_event_type_removed(self) -> None:
        """Test REMOVED event type exists and has correct value."""
        from backend.models.package_event import PackageEventType

        assert PackageEventType.REMOVED.value == "removed"

    def test_event_type_theft_suspected(self) -> None:
        """Test THEFT_SUSPECTED event type exists and has correct value."""
        from backend.models.package_event import PackageEventType

        assert PackageEventType.THEFT_SUSPECTED.value == "theft_suspected"

    def test_event_type_retrieved_by_owner(self) -> None:
        """Test RETRIEVED_BY_OWNER event type exists and has correct value."""
        from backend.models.package_event import PackageEventType

        assert PackageEventType.RETRIEVED_BY_OWNER.value == "retrieved_by_owner"

    def test_event_type_is_string_enum(self) -> None:
        """Test that PackageEventType is a string enum."""
        from backend.models.package_event import PackageEventType

        for event_type in PackageEventType:
            assert isinstance(event_type, str)
            assert isinstance(event_type.value, str)

    def test_event_type_count(self) -> None:
        """Test PackageEventType has expected number of values."""
        from backend.models.package_event import PackageEventType

        # Should have at least 4 types
        assert len(PackageEventType) >= 4


# =============================================================================
# PackageEvent Model Initialization Tests
# =============================================================================


class TestPackageEventModelInitialization:
    """Tests for PackageEvent model initialization."""

    def test_package_event_creation_minimal(self) -> None:
        """Test creating a PackageEvent with minimal required fields."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.camera_id == "front_door"
        assert event.event_type == PackageEventType.DELIVERED
        assert event.detected_at is not None

    def test_package_event_with_delivery_timestamp(self) -> None:
        """Test PackageEvent with delivery_timestamp set."""
        from backend.models.package_event import PackageEvent, PackageEventType

        delivery_time = datetime.now(UTC)

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=delivery_time,
            delivery_timestamp=delivery_time,
        )

        assert event.delivery_timestamp == delivery_time

    def test_package_event_with_removal_timestamp(self) -> None:
        """Test PackageEvent with removal_timestamp set."""
        from backend.models.package_event import PackageEvent, PackageEventType

        delivery_time = datetime.now(UTC) - timedelta(hours=2)
        removal_time = datetime.now(UTC)

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.REMOVED,
            detected_at=removal_time,
            delivery_timestamp=delivery_time,
            removal_timestamp=removal_time,
        )

        assert event.delivery_timestamp == delivery_time
        assert event.removal_timestamp == removal_time

    def test_package_event_links_to_zone(self) -> None:
        """Test PackageEvent links to zone via zone_id."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.zone_id == "delivery_zone_001"

    def test_package_event_links_to_camera(self) -> None:
        """Test PackageEvent links to camera via camera_id."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.camera_id == "front_door"

    def test_package_event_with_all_fields(self) -> None:
        """Test PackageEvent with all fields populated."""
        from backend.models.package_event import PackageEvent, PackageEventType

        delivery_time = datetime.now(UTC) - timedelta(hours=3)
        removal_time = datetime.now(UTC)

        event = PackageEvent(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            event_type=PackageEventType.THEFT_SUSPECTED,
            detected_at=removal_time,
            delivery_timestamp=delivery_time,
            removal_timestamp=removal_time,
            confidence=0.85,
            bbox={"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
            package_class="Amazon box",
            household_member_present=False,
            delivery_person_present=False,
            notes="Package removed by unknown individual",
        )

        assert event.camera_id == "front_door"
        assert event.zone_id == "delivery_zone_001"
        assert event.event_type == PackageEventType.THEFT_SUSPECTED
        assert event.confidence == 0.85
        assert event.household_member_present is False


# =============================================================================
# PackageEvent Field Tests
# =============================================================================


class TestPackageEventFields:
    """Tests for PackageEvent field definitions and constraints."""

    def test_event_id_is_primary_key(self) -> None:
        """Test that id is the primary key."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        pk_cols = [col.name for col in mapper.primary_key]
        assert "id" in pk_cols

    def test_event_id_is_auto_increment(self) -> None:
        """Test that id auto-increments."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        id_col = mapper.columns["id"]
        assert id_col.autoincrement is True or id_col.autoincrement == "auto"

    def test_camera_id_is_foreign_key(self) -> None:
        """Test that camera_id is a foreign key to cameras table."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        camera_id_col = mapper.columns["camera_id"]

        # Check foreign key constraint exists
        fks = list(camera_id_col.foreign_keys)
        assert len(fks) == 1
        assert "cameras.id" in str(fks[0])

    def test_zone_id_is_nullable(self) -> None:
        """Test that zone_id is nullable (package may not be in a zone)."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        zone_id_col = mapper.columns["zone_id"]
        assert zone_id_col.nullable is True

    def test_detected_at_not_nullable(self) -> None:
        """Test that detected_at is not nullable."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        detected_at_col = mapper.columns["detected_at"]
        assert detected_at_col.nullable is False

    def test_event_type_not_nullable(self) -> None:
        """Test that event_type is not nullable."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        event_type_col = mapper.columns["event_type"]
        assert event_type_col.nullable is False

    def test_confidence_is_nullable(self) -> None:
        """Test that confidence is nullable."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        confidence_col = mapper.columns["confidence"]
        assert confidence_col.nullable is True

    def test_bbox_is_jsonb(self) -> None:
        """Test that bbox is a JSONB column."""
        from sqlalchemy import inspect
        from sqlalchemy.dialects.postgresql import JSONB

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        bbox_col = mapper.columns["bbox"]
        assert isinstance(bbox_col.type, JSONB)

    def test_delivery_timestamp_is_nullable(self) -> None:
        """Test that delivery_timestamp is nullable."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        col = mapper.columns["delivery_timestamp"]
        assert col.nullable is True

    def test_removal_timestamp_is_nullable(self) -> None:
        """Test that removal_timestamp is nullable."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        col = mapper.columns["removal_timestamp"]
        assert col.nullable is True


# =============================================================================
# PackageEvent Default Values Tests
# =============================================================================


class TestPackageEventDefaults:
    """Tests for PackageEvent column default values."""

    def test_household_member_present_default_is_none(self) -> None:
        """Test household_member_present defaults to None (unknown)."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.household_member_present is None

    def test_delivery_person_present_default_is_none(self) -> None:
        """Test delivery_person_present defaults to None (unknown)."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.delivery_person_present is None

    def test_created_at_has_default(self) -> None:
        """Test created_at has a default value function."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        created_at_col = mapper.columns["created_at"]
        assert created_at_col.default is not None


# =============================================================================
# PackageEvent Timestamp Tests
# =============================================================================


class TestPackageEventTimestamps:
    """Tests for PackageEvent timestamp fields."""

    def test_detected_at_is_timezone_aware(self) -> None:
        """Test detected_at column has timezone support."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        detected_at_col = mapper.columns["detected_at"]
        assert detected_at_col.type.timezone is True

    def test_delivery_timestamp_is_timezone_aware(self) -> None:
        """Test delivery_timestamp column has timezone support."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        col = mapper.columns["delivery_timestamp"]
        assert col.type.timezone is True

    def test_removal_timestamp_is_timezone_aware(self) -> None:
        """Test removal_timestamp column has timezone support."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        col = mapper.columns["removal_timestamp"]
        assert col.type.timezone is True

    def test_duration_calculation(self) -> None:
        """Test duration can be calculated from delivery and removal timestamps."""
        from backend.models.package_event import PackageEvent, PackageEventType

        delivery_time = datetime.now(UTC) - timedelta(hours=2)
        removal_time = datetime.now(UTC)

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.REMOVED,
            detected_at=removal_time,
            delivery_timestamp=delivery_time,
            removal_timestamp=removal_time,
        )

        # Should have a duration property or method
        duration = event.duration
        assert duration is not None
        # Duration should be approximately 2 hours
        assert abs(duration.total_seconds() - 7200) < 60  # Within 1 minute tolerance


# =============================================================================
# PackageEvent Repr Tests
# =============================================================================


class TestPackageEventRepr:
    """Tests for PackageEvent string representation."""

    def test_repr_contains_class_name(self) -> None:
        """Test repr contains class name."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            id=1,
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        repr_str = repr(event)
        assert "PackageEvent" in repr_str

    def test_repr_contains_id(self) -> None:
        """Test repr contains event id."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            id=42,
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        repr_str = repr(event)
        assert "42" in repr_str

    def test_repr_contains_event_type(self) -> None:
        """Test repr contains event type."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            id=1,
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        repr_str = repr(event)
        assert "delivered" in repr_str.lower()

    def test_repr_contains_camera_id(self) -> None:
        """Test repr contains camera_id."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            id=1,
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        repr_str = repr(event)
        assert "front_door" in repr_str


# =============================================================================
# PackageEvent Relationship Tests
# =============================================================================


class TestPackageEventRelationships:
    """Tests for PackageEvent relationship definitions."""

    def test_has_camera_relationship(self) -> None:
        """Test PackageEvent has camera relationship defined."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert hasattr(event, "camera")

    def test_has_zone_relationship(self) -> None:
        """Test PackageEvent has zone relationship defined."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            zone_id="delivery_zone_001",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert hasattr(event, "zone")


# =============================================================================
# PackageEvent Table Args Tests
# =============================================================================


class TestPackageEventTableArgs:
    """Tests for PackageEvent table arguments (indexes)."""

    def test_has_table_args(self) -> None:
        """Test PackageEvent model has __table_args__."""
        from backend.models.package_event import PackageEvent

        assert hasattr(PackageEvent, "__table_args__")

    def test_tablename(self) -> None:
        """Test PackageEvent has correct table name."""
        from backend.models.package_event import PackageEvent

        assert PackageEvent.__tablename__ == "package_events"

    def test_has_camera_id_index(self) -> None:
        """Test PackageEvent has index on camera_id."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_package_events_camera_id" in index_names

    def test_has_detected_at_index(self) -> None:
        """Test PackageEvent has index on detected_at for time-range queries."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_package_events_detected_at" in index_names

    def test_has_event_type_index(self) -> None:
        """Test PackageEvent has index on event_type."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_package_events_event_type" in index_names

    def test_has_zone_id_index(self) -> None:
        """Test PackageEvent has index on zone_id."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_package_events_zone_id" in index_names


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPackageEventProperties:
    """Property-based tests for PackageEvent model."""

    @given(confidence=confidence_scores)
    @settings(max_examples=30)
    def test_confidence_roundtrip(self, confidence: float) -> None:
        """Property: Confidence values roundtrip correctly."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="test_cam",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
            confidence=confidence,
        )

        assert event.confidence == pytest.approx(confidence, rel=1e-6)

    @given(camera_id=camera_ids)
    @settings(max_examples=30)
    def test_camera_id_roundtrip(self, camera_id: str) -> None:
        """Property: Camera ID values roundtrip correctly."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id=camera_id,
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.camera_id == camera_id

    @given(zone_id=zone_ids)
    @settings(max_examples=30)
    def test_zone_id_roundtrip(self, zone_id: str) -> None:
        """Property: Zone ID values roundtrip correctly."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="test_cam",
            zone_id=zone_id,
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.zone_id == zone_id


# =============================================================================
# PackageEvent Factory Tests
# =============================================================================


class TestPackageEventFactory:
    """Tests for PackageEvent factory (will fail until factory is created)."""

    def test_factory_creates_valid_event(self) -> None:
        """Test PackageEventFactory creates valid PackageEvent."""
        from backend.tests.factories import PackageEventFactory

        event = PackageEventFactory()

        assert event.camera_id is not None
        assert event.event_type is not None
        assert event.detected_at is not None

    def test_factory_delivered_trait(self) -> None:
        """Test PackageEventFactory delivered trait."""
        from backend.models.package_event import PackageEventType
        from backend.tests.factories import PackageEventFactory

        event = PackageEventFactory(delivered=True)

        assert event.event_type == PackageEventType.DELIVERED
        assert event.delivery_timestamp is not None

    def test_factory_theft_suspected_trait(self) -> None:
        """Test PackageEventFactory theft_suspected trait."""
        from backend.models.package_event import PackageEventType
        from backend.tests.factories import PackageEventFactory

        event = PackageEventFactory(theft_suspected=True)

        assert event.event_type == PackageEventType.THEFT_SUSPECTED
        assert event.household_member_present is False


# =============================================================================
# PackageEvent Method Tests
# =============================================================================


class TestPackageEventMethods:
    """Tests for PackageEvent methods."""

    def test_is_theft_suspected_property(self) -> None:
        """Test is_theft_suspected property returns correct value."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.THEFT_SUSPECTED,
            detected_at=datetime.now(UTC),
        )

        assert event.is_theft_suspected is True

    def test_is_theft_suspected_false_for_delivered(self) -> None:
        """Test is_theft_suspected is False for DELIVERED events."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.is_theft_suspected is False

    def test_duration_none_when_no_removal(self) -> None:
        """Test duration is None when removal_timestamp is not set."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
            delivery_timestamp=datetime.now(UTC),
            removal_timestamp=None,
        )

        assert event.duration is None

    def test_to_dict_serialization(self) -> None:
        """Test to_dict method for API serialization."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            id=1,
            camera_id="front_door",
            zone_id="delivery_zone_001",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
            confidence=0.85,
        )

        d = event.to_dict()

        assert d["id"] == 1
        assert d["camera_id"] == "front_door"
        assert d["zone_id"] == "delivery_zone_001"
        assert d["event_type"] == "delivered"
        assert d["confidence"] == 0.85


# =============================================================================
# Soft Delete Tests
# =============================================================================


class TestPackageEventSoftDelete:
    """Tests for PackageEvent soft delete support."""

    def test_has_deleted_at_column(self) -> None:
        """Test PackageEvent has deleted_at column for soft delete."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        assert "deleted_at" in mapper.columns

    def test_deleted_at_is_nullable(self) -> None:
        """Test deleted_at is nullable (active records have NULL)."""
        from sqlalchemy import inspect

        from backend.models.package_event import PackageEvent

        mapper = inspect(PackageEvent)
        deleted_at_col = mapper.columns["deleted_at"]
        assert deleted_at_col.nullable is True

    def test_deleted_at_default_is_none(self) -> None:
        """Test deleted_at defaults to None."""
        from backend.models.package_event import PackageEvent, PackageEventType

        event = PackageEvent(
            camera_id="front_door",
            event_type=PackageEventType.DELIVERED,
            detected_at=datetime.now(UTC),
        )

        assert event.deleted_at is None
