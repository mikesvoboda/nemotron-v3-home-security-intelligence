"""Unit tests for Track model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Index definitions
- NEM-5053: last_seen index for track queries

These tests verify model structure without database access.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect

from backend.models.track import Track

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Track Model Initialization Tests
# =============================================================================


class TestTrackModelInitialization:
    """Tests for Track model initialization."""

    def test_track_creation_minimal(self):
        """Test creating a track with minimal required fields."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="front_door",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )

        assert track.track_id == 1
        assert track.camera_id == "front_door"
        assert track.object_class == "person"
        assert track.first_seen == now
        assert track.last_seen == now
        assert track.trajectory == []

    def test_track_with_all_fields(self):
        """Test track with all fields populated."""
        now = datetime.now(UTC)
        later = now + timedelta(seconds=30)
        trajectory = [
            {"x": 100.0, "y": 200.0, "timestamp": now.isoformat()},
            {"x": 150.0, "y": 220.0, "timestamp": later.isoformat()},
        ]
        embedding = b"\x00\x01\x02\x03"  # Mock embedding bytes

        track = Track(
            track_id=42,
            camera_id="back_yard",
            object_class="vehicle",
            first_seen=now,
            last_seen=later,
            trajectory=trajectory,
            total_distance=250.5,
            avg_speed=8.35,
            reid_embedding=embedding,
        )

        assert track.track_id == 42
        assert track.camera_id == "back_yard"
        assert track.object_class == "vehicle"
        assert track.first_seen == now
        assert track.last_seen == later
        assert track.trajectory == trajectory
        assert track.total_distance == 250.5
        assert track.avg_speed == 8.35
        assert track.reid_embedding == embedding

    def test_track_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="test_cam",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )

        assert track.total_distance is None
        assert track.avg_speed is None
        assert track.reid_embedding is None


# =============================================================================
# Track Field Tests
# =============================================================================


class TestTrackFields:
    """Tests for Track field values."""

    def test_track_duration_calculation(self):
        """Test track duration can be calculated from first_seen and last_seen."""
        now = datetime.now(UTC)
        later = now + timedelta(minutes=5)

        track = Track(
            track_id=1,
            camera_id="test",
            object_class="person",
            first_seen=now,
            last_seen=later,
            trajectory=[],
        )

        duration = track.last_seen - track.first_seen
        assert duration == timedelta(minutes=5)

    def test_track_object_class_types(self):
        """Test track with different object class types."""
        now = datetime.now(UTC)

        for obj_class in ["person", "vehicle", "animal", "package", "bicycle"]:
            track = Track(
                track_id=1,
                camera_id="test",
                object_class=obj_class,
                first_seen=now,
                last_seen=now,
                trajectory=[],
            )
            assert track.object_class == obj_class

    def test_track_trajectory_with_multiple_points(self):
        """Test track with multiple trajectory points."""
        now = datetime.now(UTC)
        trajectory = [
            {"x": 100.0, "y": 200.0, "timestamp": now.isoformat()},
            {"x": 110.0, "y": 210.0, "timestamp": (now + timedelta(seconds=1)).isoformat()},
            {"x": 120.0, "y": 220.0, "timestamp": (now + timedelta(seconds=2)).isoformat()},
            {"x": 130.0, "y": 230.0, "timestamp": (now + timedelta(seconds=3)).isoformat()},
        ]

        track = Track(
            track_id=1,
            camera_id="test",
            object_class="person",
            first_seen=now,
            last_seen=now + timedelta(seconds=3),
            trajectory=trajectory,
        )

        assert len(track.trajectory) == 4
        assert track.trajectory[0]["x"] == 100.0
        assert track.trajectory[-1]["x"] == 130.0


# =============================================================================
# Track Repr Tests
# =============================================================================


class TestTrackRepr:
    """Tests for Track string representation."""

    def test_track_repr_contains_class_name(self):
        """Test repr contains class name."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="front_door",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        repr_str = repr(track)
        assert "Track" in repr_str

    def test_track_repr_contains_track_id(self):
        """Test repr contains track_id."""
        now = datetime.now(UTC)
        track = Track(
            track_id=42,
            camera_id="front_door",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        repr_str = repr(track)
        assert "track_id=42" in repr_str

    def test_track_repr_contains_camera_id(self):
        """Test repr contains camera_id."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="front_door",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        repr_str = repr(track)
        assert "front_door" in repr_str

    def test_track_repr_contains_object_class(self):
        """Test repr contains object_class."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="front_door",
            object_class="vehicle",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        repr_str = repr(track)
        assert "vehicle" in repr_str

    def test_track_repr_format(self):
        """Test repr has expected format."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="front_door",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        repr_str = repr(track)
        assert repr_str.startswith("<Track(")
        assert repr_str.endswith(")>")


# =============================================================================
# Track Relationship Tests
# =============================================================================


class TestTrackRelationships:
    """Tests for Track relationship definitions."""

    def test_track_has_camera_relationship(self):
        """Test track has camera relationship defined."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="test_cam",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        assert hasattr(track, "camera")

    def test_track_has_action_events_relationship(self):
        """Test track has action_events relationship defined."""
        now = datetime.now(UTC)
        track = Track(
            track_id=1,
            camera_id="test_cam",
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
        )
        assert hasattr(track, "action_events")


# =============================================================================
# Track Table Args Tests
# =============================================================================


class TestTrackTableArgs:
    """Tests for Track table arguments (indexes)."""

    def test_track_has_table_args(self):
        """Test Track model has __table_args__."""
        assert hasattr(Track, "__table_args__")

    def test_track_tablename(self):
        """Test Track has correct table name."""
        assert Track.__tablename__ == "tracks"

    def test_track_has_track_id_index(self):
        """Test Track has track_id index defined (column-level index)."""
        mapper = inspect(Track)
        track_id_col = mapper.columns["track_id"]
        assert track_id_col.index is True

    def test_track_has_camera_track_composite_index(self):
        """Test Track has camera_id + track_id composite index defined."""
        indexes = Track.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_tracks_camera_track" in index_names

    def test_track_camera_track_index_columns(self):
        """Test camera_id + track_id composite index has correct columns."""
        indexes = Track.__table_args__
        composite_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_tracks_camera_track":
                composite_idx = idx
                break
        assert composite_idx is not None
        column_names = [col.name for col in composite_idx.columns]
        assert column_names == ["camera_id", "track_id"]

    def test_track_has_first_seen_index(self):
        """Test Track has first_seen index defined."""
        indexes = Track.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_tracks_first_seen" in index_names

    def test_track_has_object_class_index(self):
        """Test Track has object_class index defined."""
        indexes = Track.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_tracks_object_class" in index_names

    def test_track_has_camera_first_seen_composite_index(self):
        """Test Track has camera_id + first_seen composite index defined."""
        indexes = Track.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_tracks_camera_first_seen" in index_names

    def test_track_camera_first_seen_index_columns(self):
        """Test camera_id + first_seen composite index has correct columns."""
        indexes = Track.__table_args__
        composite_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_tracks_camera_first_seen":
                composite_idx = idx
                break
        assert composite_idx is not None
        column_names = [col.name for col in composite_idx.columns]
        assert column_names == ["camera_id", "first_seen"]


class TestTrackLastSeenIndex:
    """Tests for NEM-5053: last_seen index on Tracks table.

    This index enables efficient queries filtering or sorting by last_seen,
    such as finding recently active tracks or tracks that ended in a time range.
    """

    def test_track_has_last_seen_index(self):
        """Test Track has last_seen index defined (NEM-5053)."""
        indexes = Track.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_tracks_last_seen" in index_names

    def test_track_last_seen_index_columns(self):
        """Test last_seen index has correct column (NEM-5053)."""
        indexes = Track.__table_args__
        last_seen_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_tracks_last_seen":
                last_seen_idx = idx
                break
        assert last_seen_idx is not None
        column_names = [col.name for col in last_seen_idx.columns]
        assert column_names == ["last_seen"]

    def test_track_has_both_first_seen_and_last_seen_indexes(self):
        """Test Track has both first_seen and last_seen indexes (NEM-5053).

        Previously only first_seen was indexed. Now both temporal bounds
        should be indexed for efficient time-range queries.
        """
        indexes = Track.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]

        # Verify both temporal indexes exist
        assert "idx_tracks_first_seen" in index_names, "first_seen index should exist"
        assert "idx_tracks_last_seen" in index_names, "last_seen index should exist (NEM-5053)"
