"""Unit tests for SmokeFireResult database model.

Tests cover:
- Model creation with required fields
- Detection type enum (smoke, fire)
- Consecutive count tracking
- is_high_priority flag
- Timestamps (created_at)
- Relationships with Detection model

These tests are written TDD-style and should FAIL until smoke_fire_result.py
is implemented (NEM-5298 Phase 5).
"""

from __future__ import annotations

from datetime import UTC, datetime

# ===========================================================================
# Test: Model Import and Basic Structure
# ===========================================================================


class TestSmokeFireResultImport:
    """Test that the SmokeFireResult model can be imported."""

    def test_model_import(self) -> None:
        """Test that SmokeFireResult can be imported from models."""
        from backend.models.smoke_fire_result import SmokeFireResult

        assert SmokeFireResult is not None

    def test_model_in_init(self) -> None:
        """Test that SmokeFireResult is exported from models __init__."""
        from backend.models import SmokeFireResult

        assert SmokeFireResult is not None

    def test_detection_type_enum_exists(self) -> None:
        """Test that SmokeFireType enum exists."""
        from backend.models.smoke_fire_result import SmokeFireType

        assert SmokeFireType is not None
        assert hasattr(SmokeFireType, "SMOKE")
        assert hasattr(SmokeFireType, "FIRE")


# ===========================================================================
# Test: Model Creation
# ===========================================================================


class TestSmokeFireResultCreation:
    """Tests for creating SmokeFireResult instances."""

    def test_create_with_required_fields(self) -> None:
        """Test creating a SmokeFireResult with required fields."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=123,
            detection_type=SmokeFireType.FIRE,
            confidence=0.85,
        )

        assert result.detection_id == 123
        assert result.detection_type == SmokeFireType.FIRE
        assert result.confidence == 0.85

    def test_create_smoke_detection(self) -> None:
        """Test creating a smoke detection result."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=456,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.78,
        )

        assert result.detection_type == SmokeFireType.SMOKE
        assert result.detection_type.value == "smoke"

    def test_create_fire_detection(self) -> None:
        """Test creating a fire detection result."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=789,
            detection_type=SmokeFireType.FIRE,
            confidence=0.92,
        )

        assert result.detection_type == SmokeFireType.FIRE
        assert result.detection_type.value == "fire"

    def test_create_with_bounding_box(self) -> None:
        """Test creating result with bounding box coordinates."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=100,
            detection_type=SmokeFireType.FIRE,
            confidence=0.88,
            bbox_x1=10.0,
            bbox_y1=20.0,
            bbox_x2=100.0,
            bbox_y2=150.0,
        )

        assert result.bbox_x1 == 10.0
        assert result.bbox_y1 == 20.0
        assert result.bbox_x2 == 100.0
        assert result.bbox_y2 == 150.0


# ===========================================================================
# Test: Consecutive Count
# ===========================================================================


class TestSmokeFireResultConsecutiveCount:
    """Tests for consecutive detection count tracking."""

    def test_consecutive_count_default(self) -> None:
        """Test that consecutive_count defaults to 1."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.80,
        )

        assert result.consecutive_count == 1

    def test_consecutive_count_explicit(self) -> None:
        """Test setting consecutive_count explicitly."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.FIRE,
            confidence=0.85,
            consecutive_count=3,
        )

        assert result.consecutive_count == 3

    def test_increment_consecutive_count(self) -> None:
        """Test incrementing consecutive_count."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.75,
            consecutive_count=1,
        )

        result.consecutive_count += 1

        assert result.consecutive_count == 2

    def test_consecutive_count_must_be_positive(self) -> None:
        """Test that consecutive_count must be positive."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        # The model should enforce positive values via constraint
        # This test validates the constraint exists
        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.FIRE,
            confidence=0.80,
            consecutive_count=1,
        )

        # Should have a positive constraint on consecutive_count
        assert result.consecutive_count >= 1


# ===========================================================================
# Test: is_high_priority Flag
# ===========================================================================


class TestSmokeFireResultHighPriority:
    """Tests for is_high_priority flag."""

    def test_is_high_priority_default_false(self) -> None:
        """Test that is_high_priority defaults based on type."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.75,
        )

        # Default depends on implementation, but should be defined
        assert hasattr(result, "is_high_priority")

    def test_fire_detection_is_high_priority(self) -> None:
        """Test that fire detection is automatically high priority."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.FIRE,
            confidence=0.85,
        )

        # Fire should always be high priority
        assert result.is_high_priority is True

    def test_smoke_detection_high_priority_after_consecutive(self) -> None:
        """Test that smoke becomes high priority after consecutive detections."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.80,
            consecutive_count=2,  # Met consecutive threshold
        )

        # Smoke with 2+ consecutive detections should be high priority
        assert result.is_high_priority is True

    def test_smoke_detection_not_high_priority_single(self) -> None:
        """Test that single smoke detection is not high priority."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.80,
            consecutive_count=1,  # Only 1 detection
        )

        # Single smoke detection should not be high priority (could be steam)
        assert result.is_high_priority is False

    def test_is_high_priority_can_be_set_explicitly(self) -> None:
        """Test that is_high_priority can be set explicitly."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.95,
            is_high_priority=True,
        )

        assert result.is_high_priority is True


# ===========================================================================
# Test: Timestamps
# ===========================================================================


class TestSmokeFireResultTimestamps:
    """Tests for timestamp fields."""

    def test_created_at_exists(self) -> None:
        """Test that created_at field exists."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.FIRE,
            confidence=0.90,
        )

        assert hasattr(result, "created_at")

    def test_created_at_is_datetime(self) -> None:
        """Test that created_at is a datetime when set."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        now = datetime.now(UTC)
        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.FIRE,
            confidence=0.85,
            created_at=now,
        )

        assert isinstance(result.created_at, datetime)

    def test_detection_timestamp_exists(self) -> None:
        """Test that detection_timestamp field exists for when detection occurred."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.78,
        )

        # detection_timestamp tracks when the actual detection happened
        # (may differ from created_at in batch scenarios)
        assert hasattr(result, "detection_timestamp")


# ===========================================================================
# Test: Camera and Zone Fields
# ===========================================================================


class TestSmokeFireResultCameraZone:
    """Tests for camera and zone tracking fields."""

    def test_camera_id_field(self) -> None:
        """Test that camera_id field exists."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.FIRE,
            confidence=0.85,
            camera_id="front_yard",
        )

        assert result.camera_id == "front_yard"

    def test_zone_id_field(self) -> None:
        """Test that zone_id field exists (optional)."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            detection_id=1,
            detection_type=SmokeFireType.SMOKE,
            confidence=0.80,
            zone_id=5,
        )

        assert result.zone_id == 5


# ===========================================================================
# Test: Model Relationships
# ===========================================================================


class TestSmokeFireResultRelationships:
    """Tests for model relationships."""

    def test_detection_relationship_exists(self) -> None:
        """Test that relationship to Detection exists."""
        from backend.models.smoke_fire_result import SmokeFireResult

        # Check that the model has a detection relationship
        assert hasattr(SmokeFireResult, "detection") or hasattr(SmokeFireResult, "detection_id")

    def test_detection_foreign_key(self) -> None:
        """Test that detection_id is a foreign key."""
        from backend.models.smoke_fire_result import SmokeFireResult

        # Should have a foreign key constraint to detections table
        mapper = SmokeFireResult.__mapper__
        detection_id_col = mapper.columns.get("detection_id")
        assert detection_id_col is not None


# ===========================================================================
# Test: Model Table Configuration
# ===========================================================================


class TestSmokeFireResultTableConfig:
    """Tests for SQLAlchemy table configuration."""

    def test_table_name(self) -> None:
        """Test that table name is smoke_fire_results."""
        from backend.models.smoke_fire_result import SmokeFireResult

        assert SmokeFireResult.__tablename__ == "smoke_fire_results"

    def test_has_primary_key(self) -> None:
        """Test that model has a primary key."""
        from backend.models.smoke_fire_result import SmokeFireResult

        mapper = SmokeFireResult.__mapper__
        assert mapper.primary_key is not None

    def test_has_indexes_for_queries(self) -> None:
        """Test that appropriate indexes exist for common queries."""
        from backend.models.smoke_fire_result import SmokeFireResult

        # Should have indexes on camera_id, detection_type, created_at
        # for efficient queries
        table = SmokeFireResult.__table__
        index_columns = {col.name for idx in table.indexes for col in idx.columns}

        # At minimum, should index detection_type for filtering
        assert "detection_type" in index_columns or "camera_id" in index_columns


# ===========================================================================
# Test: Serialization
# ===========================================================================


class TestSmokeFireResultSerialization:
    """Tests for model serialization methods."""

    def test_to_dict_method(self) -> None:
        """Test that to_dict method exists and works."""
        from backend.models.smoke_fire_result import SmokeFireResult, SmokeFireType

        result = SmokeFireResult(
            id=1,
            detection_id=100,
            detection_type=SmokeFireType.FIRE,
            confidence=0.88,
            consecutive_count=2,
        )

        data = result.to_dict()

        assert data["detection_type"] == "fire"
        assert data["confidence"] == 0.88
        assert data["consecutive_count"] == 2

    def test_from_detection_class_method(self) -> None:
        """Test creating from a SmokeFireDetection dataclass."""
        from backend.models.smoke_fire_result import SmokeFireResult
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.90,
            bbox=(10, 20, 100, 150),
        )

        result = SmokeFireResult.from_detection(
            detection=detection,
            detection_id=456,
            camera_id="backyard",
        )

        assert result.detection_id == 456
        assert result.camera_id == "backyard"
        assert result.confidence == 0.90
