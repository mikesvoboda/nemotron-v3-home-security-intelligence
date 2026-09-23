"""Unit tests for the ActionEvent model.

Tests cover:
- Table name, column definitions, and nullability
- Default values (is_suspicious, frame_count, timestamp, created_at)
- Check constraints (confidence range, frame_count positivity)
- Index definitions incl. the BRIN time index
- Relationship definitions (camera, track)
- __repr__ format

The X-CLIP analyze path that first populated this table was archived
2026-09-23 (full-removal owner ruling); rows are written through the
/api/action-events CRUD routes, so the table contract is pinned here at
unit tier (no database) alongside the route-level integration coverage.

Reference: backend/models/action_event.py
Linear issue: NEM-3714
"""

from datetime import datetime
from typing import ClassVar

import pytest
from sqlalchemy import CheckConstraint, inspect
from sqlalchemy.dialects.postgresql import JSONB

from backend.models.action_event import ActionEvent

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


class TestActionEventTableStructure:
    """Column and table-level schema contract."""

    def test_tablename(self):
        assert ActionEvent.__tablename__ == "action_events"

    def test_columns_present_and_typed(self):
        columns = ActionEvent.__table__.columns
        assert set(columns.keys()) == {
            "id",
            "camera_id",
            "track_id",
            "action",
            "confidence",
            "is_suspicious",
            "timestamp",
            "frame_count",
            "all_scores",
            "created_at",
        }
        assert isinstance(columns["all_scores"].type, JSONB)

    def test_nullability(self):
        columns = ActionEvent.__table__.columns
        assert columns["camera_id"].nullable is False
        assert columns["action"].nullable is False
        assert columns["confidence"].nullable is False
        assert columns["is_suspicious"].nullable is False
        assert columns["timestamp"].nullable is False
        assert columns["frame_count"].nullable is False
        # Optional columns
        assert columns["track_id"].nullable is True
        assert columns["all_scores"].nullable is True

    def test_primary_key_and_autoincrement(self):
        pk = ActionEvent.__table__.primary_key.columns["id"]
        assert pk.autoincrement in (True, "auto")

    def test_foreign_keys(self):
        fks = {fk.column.table.name: fk for fk in ActionEvent.__table__.foreign_keys}
        assert fks["cameras"].column.name == "id"
        assert fks["cameras"].ondelete == "CASCADE"
        assert fks["tracks"].ondelete == "SET NULL"

    def test_timezone_aware_timestamps(self):
        columns = ActionEvent.__table__.columns
        assert columns["timestamp"].type.timezone is True
        assert columns["created_at"].type.timezone is True


class TestActionEventDefaults:
    """Column default contract (pre-flush metadata; ORM applies defaults at INSERT)."""

    def test_is_suspicious_defaults_false(self):
        assert ActionEvent.__table__.columns["is_suspicious"].default.arg is False

    def test_frame_count_default_is_eight(self):
        # The legacy X-CLIP window analyzed 16 frames; the model default of 8
        # is the frame_count contract writers inherit when they omit it.
        assert ActionEvent.__table__.columns["frame_count"].default.arg == 8

    def test_timestamp_defaults_are_utc(self):
        for col in ("timestamp", "created_at"):
            default = ActionEvent.__table__.columns[col].default
            value = default.arg(None) if callable(default.arg) else default.arg
            assert isinstance(value, datetime)
            assert value.tzinfo is not None


class TestActionEventConstraints:
    def test_check_constraints_defined(self):
        names = {
            c.name
            for c in inspect(ActionEvent.__table__).constraints
            if isinstance(c, CheckConstraint)
        } | {c.name for c in ActionEvent.__table__.constraints if isinstance(c, CheckConstraint)}
        assert "ck_action_events_confidence_range" in names
        assert "ck_action_events_frame_count_positive" in names

    def test_confidence_range_sql(self):
        by_name = {
            c.name: str(c.sqltext)
            for c in ActionEvent.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert "confidence >= 0.0" in by_name["ck_action_events_confidence_range"]
        assert "confidence <= 1.0" in by_name["ck_action_events_confidence_range"]
        assert "frame_count > 0" in by_name["ck_action_events_frame_count_positive"]


class TestActionEventIndexes:
    EXPECTED: ClassVar[frozenset[str]] = frozenset(
        {
            "idx_action_events_camera_id",
            "idx_action_events_track_id",
            "idx_action_events_timestamp",
            "idx_action_events_action",
            "idx_action_events_is_suspicious",
            "idx_action_events_camera_suspicious",
            "idx_action_events_camera_time",
            "ix_action_events_timestamp_brin",
        }
    )

    def test_index_names(self):
        names = {idx.name for idx in ActionEvent.__table__.indexes}
        assert names >= self.EXPECTED

    def test_composite_camera_suspicious_index(self):
        by_name = {idx.name: [c.name for c in idx.columns] for idx in ActionEvent.__table__.indexes}
        assert by_name["idx_action_events_camera_suspicious"] == [
            "camera_id",
            "is_suspicious",
        ]

    def test_brin_index_on_timestamp(self):
        by_name = {idx.name: idx for idx in ActionEvent.__table__.indexes}
        brin = by_name["ix_action_events_timestamp_brin"]
        assert [c.name for c in brin.columns] == ["timestamp"]
        assert brin.dialect_options["postgresql"].get("using") == "brin"


class TestActionEventRelationships:
    def test_camera_relationship(self):
        rel = inspect(ActionEvent).relationships["camera"]
        assert rel.mapper.class_.__name__ == "Camera"
        assert rel.backref is None  # back_populates wiring, not backref

    def test_track_relationship_is_optional(self):
        rel = inspect(ActionEvent).relationships["track"]
        assert rel.mapper.class_.__name__ == "Track"
        assert rel.uselist is False


class TestActionEventRepr:
    def test_repr_format(self):
        event = ActionEvent(
            id=7,
            camera_id="front-door",
            action="loitering",
            confidence=0.83,
            is_suspicious=True,
        )
        text = repr(event)
        assert "id=7" in text
        assert "camera_id='front-door'" in text
        assert "action='loitering'" in text
        assert "confidence=0.83" in text
        assert "is_suspicious=True" in text
