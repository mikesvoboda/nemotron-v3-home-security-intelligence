"""Unit tests for ExperimentResult model (NEM-3023).

These tests cover:
1. ExperimentResult model creation
2. Field validations and constraints
3. Relationships and foreign keys
4. Index definitions for query performance

TDD: Write tests first (RED), then implement to make them GREEN.
"""

from __future__ import annotations

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: ExperimentResult Model Creation
# =============================================================================


class TestExperimentResultModelCreation:
    """Tests for ExperimentResult model creation."""

    def test_model_can_be_imported(self):
        """Test ExperimentResult model can be imported."""
        from backend.models.experiment_result import ExperimentResult

        assert ExperimentResult is not None

    def test_model_has_required_columns(self):
        """Test ExperimentResult model has all required columns."""
        from backend.models.experiment_result import ExperimentResult

        # Check for required columns
        mapper = ExperimentResult.__mapper__
        column_names = {col.name for col in mapper.columns}

        required_columns = {
            "id",
            "experiment_name",
            "camera_id",
            "created_at",
            "v1_risk_score",
            "v2_risk_score",
            "v1_latency_ms",
            "v2_latency_ms",
            "experiment_version",
        }

        for col in required_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_model_has_optional_columns(self):
        """Test ExperimentResult model has optional analysis columns."""
        from backend.models.experiment_result import ExperimentResult

        mapper = ExperimentResult.__mapper__
        column_names = {col.name for col in mapper.columns}

        optional_columns = {
            "score_diff",
            "v1_risk_level",
            "v2_risk_level",
            "event_id",
            "batch_id",
        }

        for col in optional_columns:
            assert col in column_names, f"Missing optional column: {col}"

    def test_model_instance_creation(self):
        """Test ExperimentResult instance can be created."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="nemotron_prompt_v2",
            camera_id="front_door",
            v1_risk_score=50,
            v2_risk_score=45,
            v1_latency_ms=150.0,
            v2_latency_ms=180.0,
            experiment_version="shadow",
        )

        assert result.experiment_name == "nemotron_prompt_v2"
        assert result.camera_id == "front_door"
        assert result.v1_risk_score == 50
        assert result.v2_risk_score == 45
        assert result.v1_latency_ms == 150.0
        assert result.v2_latency_ms == 180.0

    def test_model_with_all_fields(self):
        """Test ExperimentResult with all fields populated."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="nemotron_prompt_v2",
            camera_id="backyard",
            v1_risk_score=60,
            v2_risk_score=40,
            v1_latency_ms=120.0,
            v2_latency_ms=150.0,
            score_diff=20,
            v1_risk_level="medium",
            v2_risk_level="low",
            event_id=123,
            batch_id="batch_abc123",
            experiment_version="ab_test_30pct",
        )

        assert result.score_diff == 20
        assert result.v1_risk_level == "medium"
        assert result.v2_risk_level == "low"
        assert result.event_id == 123
        assert result.batch_id == "batch_abc123"


# =============================================================================
# Test: Model Table Definition
# =============================================================================


class TestExperimentResultTableDefinition:
    """Tests for ExperimentResult table definition."""

    def test_table_name_is_correct(self):
        """Test table name is 'experiment_results'."""
        from backend.models.experiment_result import ExperimentResult

        assert ExperimentResult.__tablename__ == "experiment_results"

    def test_primary_key_is_id(self):
        """Test primary key is the id column."""
        from backend.models.experiment_result import ExperimentResult

        mapper = ExperimentResult.__mapper__
        pk_columns = [col.name for col in mapper.primary_key]

        assert "id" in pk_columns

    def test_id_column_is_autoincrement(self):
        """Test id column auto-increments."""
        from backend.models.experiment_result import ExperimentResult

        id_col = ExperimentResult.__table__.c.id
        assert id_col.autoincrement is True or id_col.autoincrement == "auto"


# =============================================================================
# Test: Model Indexes
# =============================================================================


class TestExperimentResultIndexes:
    """Tests for ExperimentResult model indexes."""

    def test_has_experiment_name_index(self):
        """Test index exists on experiment_name for filtering."""
        from backend.models.experiment_result import ExperimentResult

        table = ExperimentResult.__table__
        index_columns = {tuple(col.name for col in idx.columns) for idx in table.indexes}

        # Should have an index on experiment_name (possibly composite)
        has_experiment_index = any("experiment_name" in cols for cols in index_columns)
        assert has_experiment_index, "Missing index on experiment_name"

    def test_has_camera_id_index(self):
        """Test index exists on camera_id for filtering."""
        from backend.models.experiment_result import ExperimentResult

        table = ExperimentResult.__table__
        index_columns = {tuple(col.name for col in idx.columns) for idx in table.indexes}

        # Should have an index on camera_id (possibly composite)
        has_camera_index = any("camera_id" in cols for cols in index_columns)
        assert has_camera_index, "Missing index on camera_id"

    def test_has_created_at_index(self):
        """Test index exists on created_at for time-based queries."""
        from backend.models.experiment_result import ExperimentResult

        table = ExperimentResult.__table__
        index_columns = {tuple(col.name for col in idx.columns) for idx in table.indexes}

        # Should have an index on created_at (possibly composite)
        has_created_at_index = any("created_at" in cols for cols in index_columns)
        assert has_created_at_index, "Missing index on created_at"


# =============================================================================
# Test: Model Relationships
# =============================================================================


class TestExperimentResultRelationships:
    """Tests for ExperimentResult model relationships."""

    def test_event_id_is_optional(self):
        """Test event_id column is nullable (optional)."""
        from backend.models.experiment_result import ExperimentResult

        event_id_col = ExperimentResult.__table__.c.event_id
        assert event_id_col.nullable is True


# =============================================================================
# Test: Score Diff Calculation
# =============================================================================


class TestExperimentResultScoreDiff:
    """Tests for score difference calculation."""

    def test_score_diff_calculated_property(self):
        """Test calculated_score_diff property returns correct value."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            camera_id="cam1",
            v1_risk_score=60,
            v2_risk_score=45,
            v1_latency_ms=100.0,
            v2_latency_ms=120.0,
            experiment_version="test",
        )

        # Test calculated property
        assert result.calculated_score_diff == 15

    def test_score_diff_always_positive(self):
        """Test calculated_score_diff is always positive (absolute)."""
        from backend.models.experiment_result import ExperimentResult

        # V2 higher than V1
        result1 = ExperimentResult(
            experiment_name="test",
            camera_id="cam1",
            v1_risk_score=30,
            v2_risk_score=60,
            v1_latency_ms=100.0,
            v2_latency_ms=120.0,
            experiment_version="test",
        )
        assert result1.calculated_score_diff == 30

        # V1 higher than V2
        result2 = ExperimentResult(
            experiment_name="test",
            camera_id="cam1",
            v1_risk_score=70,
            v2_risk_score=40,
            v1_latency_ms=100.0,
            v2_latency_ms=120.0,
            experiment_version="test",
        )
        assert result2.calculated_score_diff == 30


# =============================================================================
# Test: Latency Comparison
# =============================================================================


class TestExperimentResultLatencyComparison:
    """Tests for latency comparison helpers."""

    def test_latency_diff_ms_property(self):
        """Test latency_diff_ms property returns correct value."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            camera_id="cam1",
            v1_risk_score=50,
            v2_risk_score=50,
            v1_latency_ms=100.0,
            v2_latency_ms=150.0,
            experiment_version="test",
        )

        # V2 is 50ms slower
        assert result.latency_diff_ms == 50.0

    def test_latency_increase_pct_property(self):
        """Test latency_increase_pct property returns correct value."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            camera_id="cam1",
            v1_risk_score=50,
            v2_risk_score=50,
            v1_latency_ms=100.0,
            v2_latency_ms=150.0,
            experiment_version="test",
        )

        # V2 is 50% slower
        assert result.latency_increase_pct == 50.0

    def test_latency_increase_pct_with_zero_v1(self):
        """Test latency_increase_pct handles zero v1 latency."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test",
            camera_id="cam1",
            v1_risk_score=50,
            v2_risk_score=50,
            v1_latency_ms=0.0,
            v2_latency_ms=100.0,
            experiment_version="test",
        )

        # Should handle gracefully (return 0 or None, not divide by zero)
        assert result.latency_increase_pct is not None


# =============================================================================
# Test: Serialization
# =============================================================================


class TestExperimentResultSerialization:
    """Tests for ExperimentResult serialization."""

    def test_to_dict_returns_all_fields(self):
        """Test to_dict method returns all fields."""
        from backend.models.experiment_result import ExperimentResult

        result = ExperimentResult(
            experiment_name="test_exp",
            camera_id="front_door",
            v1_risk_score=50,
            v2_risk_score=45,
            v1_latency_ms=100.0,
            v2_latency_ms=120.0,
            score_diff=5,
            v1_risk_level="medium",
            v2_risk_level="medium",
            experiment_version="shadow",
        )

        data = result.to_dict()

        assert data["experiment_name"] == "test_exp"
        assert data["camera_id"] == "front_door"
        assert data["v1_risk_score"] == 50
        assert data["v2_risk_score"] == 45
        assert data["v1_latency_ms"] == 100.0
        assert data["v2_latency_ms"] == 120.0
