"""Unit tests for face identity models.

Tests cover:
- FaceDetectionEvent model index definitions
- NEM-5054: match_confidence index for face detection queries

These tests verify model structure without database access.
"""

import pytest
from sqlalchemy import Index

from backend.models.face_identity import FaceDetectionEvent, FaceEmbedding, KnownPerson

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# FaceDetectionEvent Index Tests
# =============================================================================


class TestFaceDetectionEventTableArgs:
    """Tests for FaceDetectionEvent table arguments (indexes)."""

    def test_face_detection_event_has_table_args(self):
        """Test FaceDetectionEvent model has __table_args__."""
        assert hasattr(FaceDetectionEvent, "__table_args__")

    def test_face_detection_event_tablename(self):
        """Test FaceDetectionEvent has correct table name."""
        assert FaceDetectionEvent.__tablename__ == "face_detection_events"

    def test_face_detection_event_has_camera_id_index(self):
        """Test FaceDetectionEvent has camera_id index defined."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_camera_id" in index_names

    def test_face_detection_event_has_timestamp_index(self):
        """Test FaceDetectionEvent has timestamp index defined."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_timestamp" in index_names

    def test_face_detection_event_has_is_unknown_index(self):
        """Test FaceDetectionEvent has is_unknown index defined."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_is_unknown" in index_names

    def test_face_detection_event_has_matched_person_id_index(self):
        """Test FaceDetectionEvent has matched_person_id index defined."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_matched_person_id" in index_names

    def test_face_detection_event_has_camera_timestamp_composite_index(self):
        """Test FaceDetectionEvent has camera_id + timestamp composite index defined."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_camera_timestamp" in index_names

    def test_face_detection_event_has_timestamp_brin_index(self):
        """Test FaceDetectionEvent has BRIN index on timestamp for time-series queries."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_timestamp_brin" in index_names

    def test_face_detection_event_timestamp_brin_index_uses_brin(self):
        """Test timestamp BRIN index uses brin postgresql_using."""
        indexes = FaceDetectionEvent.__table_args__
        brin_index = None
        for idx in indexes:
            if isinstance(idx, Index) and idx.name == "idx_face_events_timestamp_brin":
                brin_index = idx
                break
        assert brin_index is not None
        assert brin_index.kwargs.get("postgresql_using") == "brin"


class TestFaceDetectionEventConfidenceIndex:
    """Tests for NEM-5054: match_confidence index on FaceDetectionEvent.

    This index enables efficient queries filtering by match confidence,
    such as finding high-confidence face matches or sorting by confidence.
    """

    def test_face_detection_event_has_confidence_index(self):
        """Test FaceDetectionEvent has match_confidence index defined (NEM-5054)."""
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_confidence" in index_names

    def test_face_detection_event_confidence_index_columns(self):
        """Test match_confidence index has correct column (NEM-5054)."""
        indexes = FaceDetectionEvent.__table_args__
        confidence_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_face_events_confidence":
                confidence_idx = idx
                break
        assert confidence_idx is not None
        column_names = [col.name for col in confidence_idx.columns]
        assert column_names == ["match_confidence"]

    def test_face_detection_event_has_matched_confidence_composite_index(self):
        """Test FaceDetectionEvent has matched_person_id + match_confidence composite index (NEM-5054).

        This composite index enables efficient queries filtering by matched person
        and then sorting or filtering by confidence, such as:
        - Finding all matches for a specific person sorted by confidence
        - Finding high-confidence matches for a person
        """
        indexes = FaceDetectionEvent.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_events_matched_confidence" in index_names

    def test_face_detection_event_matched_confidence_index_columns(self):
        """Test matched_person_id + match_confidence composite index has correct columns (NEM-5054)."""
        indexes = FaceDetectionEvent.__table_args__
        composite_idx = None
        for idx in indexes:
            if hasattr(idx, "name") and idx.name == "idx_face_events_matched_confidence":
                composite_idx = idx
                break
        assert composite_idx is not None
        column_names = [col.name for col in composite_idx.columns]
        # Column order matters for composite indexes
        assert column_names == ["matched_person_id", "match_confidence"]


# =============================================================================
# KnownPerson Index Tests
# =============================================================================


class TestKnownPersonTableArgs:
    """Tests for KnownPerson table arguments (indexes)."""

    def test_known_person_has_table_args(self):
        """Test KnownPerson model has __table_args__."""
        assert hasattr(KnownPerson, "__table_args__")

    def test_known_person_tablename(self):
        """Test KnownPerson has correct table name."""
        assert KnownPerson.__tablename__ == "known_persons"

    def test_known_person_has_name_index(self):
        """Test KnownPerson has name index defined."""
        indexes = KnownPerson.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_known_persons_name" in index_names

    def test_known_person_has_household_index(self):
        """Test KnownPerson has is_household_member index defined."""
        indexes = KnownPerson.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_known_persons_household" in index_names


# =============================================================================
# FaceEmbedding Index Tests
# =============================================================================


class TestFaceEmbeddingTableArgs:
    """Tests for FaceEmbedding table arguments (indexes)."""

    def test_face_embedding_has_table_args(self):
        """Test FaceEmbedding model has __table_args__."""
        assert hasattr(FaceEmbedding, "__table_args__")

    def test_face_embedding_tablename(self):
        """Test FaceEmbedding has correct table name."""
        assert FaceEmbedding.__tablename__ == "face_embeddings"

    def test_face_embedding_has_person_id_index(self):
        """Test FaceEmbedding has person_id index defined."""
        indexes = FaceEmbedding.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_embeddings_person_id" in index_names

    def test_face_embedding_has_quality_index(self):
        """Test FaceEmbedding has quality_score index defined."""
        indexes = FaceEmbedding.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_face_embeddings_quality" in index_names
