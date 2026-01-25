"""Unit tests for event clustering Pydantic schemas (NEM-3620)."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.api.schemas.event_cluster import (
    ClusterEventSummary,
    ClusterRiskLevels,
    EventCluster,
    EventClustersResponse,
)


class TestClusterRiskLevels:
    """Tests for ClusterRiskLevels schema validation."""

    def test_valid_risk_levels(self):
        """Test valid ClusterRiskLevels creation."""
        levels = ClusterRiskLevels(critical=5, high=10, medium=15, low=20)
        assert levels.critical == 5
        assert levels.high == 10
        assert levels.medium == 15
        assert levels.low == 20

    def test_default_values_are_zero(self):
        """Test default values are zero."""
        levels = ClusterRiskLevels()
        assert levels.critical == 0
        assert levels.high == 0
        assert levels.medium == 0
        assert levels.low == 0

    def test_negative_values_rejected(self):
        """Test negative values are rejected."""
        with pytest.raises(ValidationError):
            ClusterRiskLevels(critical=-1)

    def test_partial_values(self):
        """Test partial value assignment."""
        levels = ClusterRiskLevels(high=5)
        assert levels.critical == 0
        assert levels.high == 5
        assert levels.medium == 0
        assert levels.low == 0

    def test_json_schema_example(self):
        """Test JSON schema has example."""
        schema = ClusterRiskLevels.model_json_schema()
        assert "example" in schema or "examples" in schema


class TestClusterEventSummary:
    """Tests for ClusterEventSummary schema validation."""

    def test_valid_summary(self):
        """Test valid ClusterEventSummary creation."""
        now = datetime.now(UTC)
        summary = ClusterEventSummary(
            id=1,
            camera_id="front_door",
            started_at=now,
            risk_score=75,
            risk_level="high",
            summary="Person detected",
        )
        assert summary.id == 1
        assert summary.camera_id == "front_door"
        assert summary.started_at == now
        assert summary.risk_score == 75
        assert summary.risk_level == "high"
        assert summary.summary == "Person detected"

    def test_required_fields_only(self):
        """Test creation with only required fields."""
        now = datetime.now(UTC)
        summary = ClusterEventSummary(
            id=1,
            camera_id="cam1",
            started_at=now,
        )
        assert summary.id == 1
        assert summary.risk_score is None
        assert summary.risk_level is None
        assert summary.summary is None

    def test_missing_required_field_rejected(self):
        """Test missing required field raises error."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            ClusterEventSummary(
                id=1,
                started_at=now,
                # missing camera_id
            )

    def test_from_attributes_config(self):
        """Test from_attributes config is enabled."""
        config = ClusterEventSummary.model_config
        assert config.get("from_attributes") is True


class TestEventCluster:
    """Tests for EventCluster schema validation."""

    def test_valid_cluster(self):
        """Test valid EventCluster creation."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            cluster_id="test-uuid-123",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            event_count=3,
            cameras=["front_door", "back_door"],
            risk_levels=ClusterRiskLevels(high=2, medium=1),
            object_types={"person": 2, "vehicle": 1},
            events=[
                ClusterEventSummary(id=1, camera_id="front_door", started_at=now),
            ],
        )
        assert cluster.cluster_id == "test-uuid-123"
        assert cluster.event_count == 3
        assert len(cluster.cameras) == 2

    def test_auto_generated_cluster_id(self):
        """Test cluster_id is auto-generated when not provided."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            start_time=now,
            end_time=now,
            event_count=1,
            cameras=["cam1"],
            risk_levels=ClusterRiskLevels(),
            events=[],
        )
        # UUID format: 8-4-4-4-12 = 36 chars
        assert len(cluster.cluster_id) == 36
        assert "-" in cluster.cluster_id

    def test_event_count_minimum_one(self):
        """Test event_count must be at least 1."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            EventCluster(
                start_time=now,
                end_time=now,
                event_count=0,  # Invalid: must be >= 1
                cameras=["cam1"],
                risk_levels=ClusterRiskLevels(),
                events=[],
            )

    def test_object_types_default_empty_dict(self):
        """Test object_types defaults to empty dict."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            start_time=now,
            end_time=now,
            event_count=1,
            cameras=["cam1"],
            risk_levels=ClusterRiskLevels(),
            events=[],
        )
        assert cluster.object_types == {}

    def test_events_can_be_empty(self):
        """Test events list can be empty."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            start_time=now,
            end_time=now,
            event_count=1,
            cameras=["cam1"],
            risk_levels=ClusterRiskLevels(),
            events=[],
        )
        assert len(cluster.events) == 0

    def test_serialization(self):
        """Test cluster serializes correctly to dict."""
        now = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        cluster = EventCluster(
            cluster_id="test-123",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            event_count=2,
            cameras=["cam1", "cam2"],
            risk_levels=ClusterRiskLevels(high=1, medium=1),
            object_types={"person": 2},
            events=[],
        )
        data = cluster.model_dump()
        assert data["cluster_id"] == "test-123"
        assert data["event_count"] == 2
        assert data["risk_levels"]["high"] == 1
        assert data["object_types"]["person"] == 2


class TestEventClustersResponse:
    """Tests for EventClustersResponse schema validation."""

    def test_valid_response(self):
        """Test valid EventClustersResponse creation."""
        response = EventClustersResponse(
            clusters=[],
            total_clusters=0,
            unclustered_events=5,
        )
        assert response.total_clusters == 0
        assert response.unclustered_events == 5
        assert len(response.clusters) == 0

    def test_response_with_clusters(self):
        """Test response with actual clusters."""
        now = datetime.now(UTC)
        cluster = EventCluster(
            start_time=now,
            end_time=now,
            event_count=2,
            cameras=["cam1"],
            risk_levels=ClusterRiskLevels(medium=2),
            events=[],
        )
        response = EventClustersResponse(
            clusters=[cluster],
            total_clusters=1,
            unclustered_events=0,
        )
        assert response.total_clusters == 1
        assert len(response.clusters) == 1
        assert response.clusters[0].event_count == 2

    def test_negative_total_clusters_rejected(self):
        """Test negative total_clusters is rejected."""
        with pytest.raises(ValidationError):
            EventClustersResponse(
                clusters=[],
                total_clusters=-1,
                unclustered_events=0,
            )

    def test_negative_unclustered_events_rejected(self):
        """Test negative unclustered_events is rejected."""
        with pytest.raises(ValidationError):
            EventClustersResponse(
                clusters=[],
                total_clusters=0,
                unclustered_events=-1,
            )

    def test_serialization_to_json(self):
        """Test response serializes to JSON correctly."""
        now = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)
        cluster = EventCluster(
            cluster_id="abc-123",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            event_count=3,
            cameras=["front_door"],
            risk_levels=ClusterRiskLevels(high=1, medium=2),
            object_types={"person": 3},
            events=[
                ClusterEventSummary(
                    id=1,
                    camera_id="front_door",
                    started_at=now,
                    risk_score=75,
                    risk_level="high",
                    summary="Test event",
                )
            ],
        )
        response = EventClustersResponse(
            clusters=[cluster],
            total_clusters=1,
            unclustered_events=5,
        )
        json_str = response.model_dump_json()
        assert "abc-123" in json_str
        assert "front_door" in json_str
        assert '"total_clusters":1' in json_str.replace(" ", "")
